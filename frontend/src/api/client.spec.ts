import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, setSessionExpiredHandler, tokens } from '@/api/client'
import type { TokenPayload } from '@/api/types'

type FakeResponse = { ok: boolean; status: number; json: () => Promise<unknown> }

function tokenPayload(access: string, refresh: string): TokenPayload {
  return {
    access_token: access,
    refresh_token: refresh,
    expires_in: 3600,
    user_id: 'u_test',
    username: 'demo',
    role: 'user',
  }
}

function reply(status: number, body: unknown): FakeResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }
}

function envelope(data: unknown, code = 'SUCCESS') {
  return { code, message: code === 'SUCCESS' ? 'success' : '出错了', data, request_id: 'req_test' }
}

let fetchMock: ReturnType<typeof vi.fn>

function calls() {
  return fetchMock.mock.calls.map((call) => String(call[0]))
}

beforeEach(() => {
  localStorage.clear()
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  setSessionExpiredHandler(null)
  localStorage.clear()
})

describe('api 请求封装', () => {
  it('带上访问令牌并返回 data', async () => {
    tokens.save(tokenPayload('a1', 'r1'))
    fetchMock.mockResolvedValueOnce(reply(200, envelope([{ id: 'x' }])))

    const data = await api<{ id: string }[]>('/conversations')

    expect(data).toEqual([{ id: 'x' }])
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer a1')
  })

  it('401 时刷新令牌并重放一次请求', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    fetchMock
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
      .mockResolvedValueOnce(reply(200, envelope(tokenPayload('new', 'r2'))))
      .mockResolvedValueOnce(reply(200, envelope({ ok: true })))

    const data = await api<{ ok: boolean }>('/profiles/me')

    expect(data).toEqual({ ok: true })
    expect(calls()[1]).toContain('/auth/refresh')
    expect(calls().filter((url) => url.includes('/profiles/me'))).toHaveLength(2)
    expect(tokens.access).toBe('new')
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('刷新失败时清空令牌并抛出原请求的错误', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    fetchMock
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))

    await expect(api('/profiles/me')).rejects.toBeInstanceOf(ApiError)
    expect(tokens.access).toBe('')
    expect(tokens.refresh).toBe('')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('重放后仍然 401 不会无限重试', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    fetchMock
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
      .mockResolvedValueOnce(reply(200, envelope(tokenPayload('new', 'r2'))))
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))

    await expect(api('/profiles/me')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('声明 retry false 时不尝试刷新', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    fetchMock.mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))

    await expect(api('/profiles/me', { retry: false })).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('业务错误码原样带到 ApiError', async () => {
    fetchMock.mockResolvedValueOnce(reply(409, envelope({ hint: '已存在' }, 'RESOURCE_CONFLICT')))

    const error = await api('/plans/1/adjust').catch((err: unknown) => err)

    expect(error).toBeInstanceOf(ApiError)
    const apiError = error as ApiError
    expect(apiError.code).toBe('RESOURCE_CONFLICT')
    expect(apiError.status).toBe(409)
    expect(apiError.message).toBe('出错了')
    expect(apiError.detail).toEqual({ hint: '已存在' })
  })

  it('响应不是合法 JSON 时给出兜底错误', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error('not json')
      },
    })

    const error = (await api('/health').catch((err: unknown) => err)) as ApiError
    expect(error.code).toBe('INTERNAL_ERROR')
    expect(error.message).toBe('请求失败 502')
  })
})

describe('令牌刷新的并发合并', () => {
  // 布局与页面会同时发请求，令牌过期时它们会同时拿到 401。refreshTask 是模块级变量，
  // 靠它把这几路合并成一次 /auth/refresh，不然刷新接口会被打成并发调用、后到的那次把前一次作废
  function routeByAuthHeader(onRefresh: () => FakeResponse) {
    return async (input: string, init: { headers?: Record<string, string> }) => {
      if (String(input).includes('/auth/refresh')) return onRefresh()
      if (init.headers?.Authorization === 'Bearer old') return reply(401, envelope(null, 'AUTH_UNAUTHORIZED'))
      return reply(200, envelope({ url: String(input) }))
    }
  }

  it('两个请求同时 401 时只刷新一次，各自重放', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    let refreshCount = 0
    fetchMock.mockImplementation(
      routeByAuthHeader(() => {
        refreshCount += 1
        return reply(200, envelope(tokenPayload('new', 'r2')))
      }),
    )

    const [alpha, beta] = await Promise.all([api<{ url: string }>('/alpha'), api<{ url: string }>('/beta')])

    expect(refreshCount).toBe(1)
    expect(alpha.url).toContain('/alpha')
    expect(beta.url).toContain('/beta')
    expect(tokens.access).toBe('new')
    // 2 次原请求 + 1 次刷新 + 2 次重放
    expect(fetchMock).toHaveBeenCalledTimes(5)
  })

  it('刷新失败时并发请求都失败，不会各自再刷一次', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    let refreshCount = 0
    fetchMock.mockImplementation(
      routeByAuthHeader(() => {
        refreshCount += 1
        return reply(401, envelope(null, 'AUTH_UNAUTHORIZED'))
      }),
    )

    const results = await Promise.allSettled([api('/alpha'), api('/beta')])

    expect(refreshCount).toBe(1)
    expect(results.map((item) => item.status)).toEqual(['rejected', 'rejected'])
    expect(tokens.access).toBe('')
    expect(tokens.refresh).toBe('')
    // 刷新失败后不重放，只有 2 次原请求与 1 次刷新
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('刷新成功后 refreshTask 归零，令牌再次过期仍能刷新', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    let refreshCount = 0
    fetchMock.mockImplementation(
      routeByAuthHeader(() => {
        refreshCount += 1
        return reply(200, envelope(tokenPayload(`new-${refreshCount}`, 'r1')))
      }),
    )

    await api('/alpha')
    expect(refreshCount).toBe(1)

    // 模拟令牌再次过期：本地访问令牌回退到旧值
    tokens.save(tokenPayload('old', 'r1'))
    await api('/beta')

    expect(refreshCount).toBe(2)
    expect(tokens.access).toBe('new-2')
  })
})

describe('会话过期的回调', () => {
  // 令牌过期且续不上时，各页面只会拿到一串 401。若没人通知上层跳登录页，
  // 用户看到的是一个什么都加载不出来的空壳子，还以为数据丢了
  it('带令牌被拒且续期失败时通知一次', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    fetchMock
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
    const expired = vi.fn()
    setSessionExpiredHandler(expired)

    await expect(api('/profiles/me')).rejects.toBeInstanceOf(ApiError)

    expect(expired).toHaveBeenCalledTimes(1)
    expect(tokens.access).toBe('')
    expect(tokens.refresh).toBe('')
  })

  it('多个请求同时过期也只通知一次', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    fetchMock.mockImplementation(async (input: string) => {
      if (String(input).includes('/auth/refresh')) return reply(401, envelope(null, 'AUTH_UNAUTHORIZED'))
      return reply(401, envelope(null, 'AUTH_UNAUTHORIZED'))
    })
    const expired = vi.fn()
    setSessionExpiredHandler(expired)

    await Promise.allSettled([api('/alpha'), api('/beta'), api('/gamma')])

    expect(expired).toHaveBeenCalledTimes(1)
  })

  it('登录接口自己返回 401 不算会话过期', async () => {
    fetchMock.mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_INVALID_CREDENTIALS')))
    const expired = vi.fn()
    setSessionExpiredHandler(expired)

    await expect(api('/auth/login', { body: { username: 'demo', password: 'x' } })).rejects.toBeInstanceOf(ApiError)

    expect(expired).not.toHaveBeenCalled()
  })

  it('续期成功后重放仍被拒也通知', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    fetchMock
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
      .mockResolvedValueOnce(reply(200, envelope(tokenPayload('new', 'r2'))))
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
    const expired = vi.fn()
    setSessionExpiredHandler(expired)

    await expect(api('/profiles/me')).rejects.toBeInstanceOf(ApiError)

    expect(expired).toHaveBeenCalledTimes(1)
  })

  it('重新登录后再次过期还能再通知', async () => {
    const expired = vi.fn()
    setSessionExpiredHandler(expired)

    tokens.save(tokenPayload('old', 'r1'))
    fetchMock
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
    await expect(api('/profiles/me')).rejects.toBeInstanceOf(ApiError)
    expect(expired).toHaveBeenCalledTimes(1)

    // 重新登录会调用 tokens.save，通知开关要跟着复位
    tokens.save(tokenPayload('again', 'r2'))
    fetchMock
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
      .mockResolvedValueOnce(reply(401, envelope(null, 'AUTH_UNAUTHORIZED')))
    await expect(api('/profiles/me')).rejects.toBeInstanceOf(ApiError)

    expect(expired).toHaveBeenCalledTimes(2)
  })
})
