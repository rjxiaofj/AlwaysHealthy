import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setSessionExpiredHandler, tokens } from '@/api/client'
import { streamMessage } from '@/api/stream'
import type { TokenPayload } from '@/api/types'

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

function envelope(data: unknown, code = 'SUCCESS', message = 'success') {
  return { code, message, data, request_id: 'req_test' }
}

/** 造一个能按片吐字的流式响应。chunks 里每一片模拟一次 reader.read()。 */
function streamResponse(chunks: string[]) {
  let index = 0
  const encoder = new TextEncoder()
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () => {
          if (index >= chunks.length) return { done: true, value: undefined }
          return { done: false, value: encoder.encode(chunks[index++]) }
        },
      }),
    },
    text: async () => '',
  }
}

function errorResponse(status: number, body: string) {
  return {
    ok: false,
    status,
    body: null,
    text: async () => body,
  }
}

let fetchMock: ReturnType<typeof vi.fn>

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

describe('流式请求', () => {
  it('分片到达时也能拼出完整事件', async () => {
    tokens.save(tokenPayload('a1', 'r1'))
    // 第二个事件的 JSON 被切成两片，只有第二次 read 之后才完整
    fetchMock.mockResolvedValueOnce(streamResponse(['event: token\ndata: {"content":"你"}\n\nevent: token\ndata: {"cont', 'ent":"好"}\n\n']))
    const events: Array<[string, Record<string, unknown>]> = []

    await streamMessage('c1', '你好', (event, data) => events.push([event, data]))

    expect(events).toEqual([
      ['token', { content: '你' }],
      ['token', { content: '好' }],
    ])
  })

  it('data 不是合法 JSON 时给 raw', async () => {
    tokens.save(tokenPayload('a1', 'r1'))
    fetchMock.mockResolvedValueOnce(streamResponse(['event: token\ndata: 不是json\n\n']))
    const events: Array<[string, Record<string, unknown>]> = []

    await streamMessage('c1', '你好', (event, data) => events.push([event, data]))

    expect(events).toEqual([['token', { raw: '不是json' }]])
  })

  it('401 时续一次令牌再重放', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    let streamCalls = 0
    fetchMock.mockImplementation(async (input: string, init: { headers?: Record<string, string> }) => {
      if (String(input).includes('/auth/refresh')) return { ok: true, status: 200, json: async () => envelope(tokenPayload('new', 'r2')) }
      streamCalls += 1
      if (init.headers?.Authorization === 'Bearer old') return errorResponse(401, JSON.stringify(envelope(null, 'AUTH_UNAUTHORIZED', '登录已过期')))
      return streamResponse(['event: token\ndata: {"content":"好"}\n\n'])
    })
    const events: Array<[string, Record<string, unknown>]> = []

    await streamMessage('c1', '你好', (event, data) => events.push([event, data]))

    expect(streamCalls).toBe(2)
    expect(tokens.access).toBe('new')
    expect(events).toEqual([['token', { content: '好' }]])
  })

  it('续期也失败时抛出后端的中文提示，而不是整段 JSON', async () => {
    tokens.save(tokenPayload('old', 'r1'))
    fetchMock.mockImplementation(async (input: string) => {
      if (String(input).includes('/auth/refresh')) return { ok: false, status: 401, json: async () => envelope(null, 'AUTH_UNAUTHORIZED') }
      return errorResponse(401, JSON.stringify(envelope(null, 'AUTH_UNAUTHORIZED', '登录已过期，请重新登录')))
    })

    await expect(streamMessage('c1', '你好', () => undefined)).rejects.toThrow('登录已过期，请重新登录')
  })

  it('非 401 的错误也用后端 message', async () => {
    tokens.save(tokenPayload('a1', 'r1'))
    fetchMock.mockResolvedValueOnce(errorResponse(409, JSON.stringify(envelope(null, 'RESOURCE_CONFLICT', '这个计划已经生效'))))

    await expect(streamMessage('c1', '你好', () => undefined)).rejects.toThrow('这个计划已经生效')
  })

  it('错误响应体不是 JSON 时退回状态码', async () => {
    tokens.save(tokenPayload('a1', 'r1'))
    fetchMock.mockResolvedValueOnce(errorResponse(502, ''))

    await expect(streamMessage('c1', '你好', () => undefined)).rejects.toThrow('请求失败 502')
  })
})
