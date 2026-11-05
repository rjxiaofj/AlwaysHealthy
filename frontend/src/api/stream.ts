import { refreshSession, tokens } from './client'
import { splitSseFrames } from '@/utils/sse'

const BASE = '/api/v1'

export type StreamHandler = (event: string, data: Record<string, unknown>) => void

async function readStream(response: Response, onEvent: StreamHandler) {
  if (!response.ok) {
    // 后端错误是 {code, message, ...} 的 JSON 包。原来直接把整段文本抛出去，
    // 用户会在气泡里看到一串 {"code":"AUTH_UNAUTHORIZED","message":"…"}
    const text = await response.text().catch(() => '')
    let message = text
    try {
      const body = JSON.parse(text) as { message?: string }
      if (body?.message) message = body.message
    } catch {
      // 不是 JSON 就按原文给
    }
    throw new Error(message || `请求失败 ${response.status}`)
  }
  if (!response.body) throw new Error('浏览器不支持流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // 切帧的逻辑单独放在 utils/sse.ts：换行符归一化、半个事件留在缓冲区，
    // 这些用真实流才能验，放在这里就没法写单测了
    const { frames, rest } = splitSseFrames(buffer)
    buffer = rest
    for (const frame of frames) {
      if (!frame.data) continue
      try {
        onEvent(frame.event, JSON.parse(frame.data))
      } catch {
        onEvent(frame.event, { raw: frame.data })
      }
    }
  }
}

async function sendStream(path: string, body: unknown, signal?: AbortSignal) {
  return fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${tokens.access}`,
    },
    body: JSON.stringify(body),
    signal,
  })
}

async function postStream(path: string, body: unknown, onEvent: StreamHandler, signal?: AbortSignal) {
  let response = await sendStream(path, body, signal)
  if (response.status === 401) {
    // 和 api() 一样先续一次再重放。这层原来没有：会话过了两小时，
    // 聊天会直接失败，而同一个页面上的其他请求都能自动续期
    const refreshed = await refreshSession()
    if (refreshed) response = await sendStream(path, body, signal)
  }
  await readStream(response, onEvent)
}

export function streamMessage(conversationId: string, content: string, onEvent: StreamHandler, signal?: AbortSignal) {
  return postStream(`/conversations/${conversationId}/messages/stream`, { content }, onEvent, signal)
}

export function streamResume(
  runId: string,
  payload: {
    approval_type: 'profile' | 'plan'
    decision: 'approve' | 'modify' | 'reject'
    business_id?: string | null
    version_id?: string | null
    feedback?: string | null
  },
  onEvent: StreamHandler,
  signal?: AbortSignal,
) {
  return postStream(`/runs/${runId}/resume/stream`, payload, onEvent, signal)
}
