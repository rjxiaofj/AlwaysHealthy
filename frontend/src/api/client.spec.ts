import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, tokens } from '@/api/client'
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
