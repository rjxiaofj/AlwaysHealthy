import { tokens } from './client'

const BASE = '/api/v1'

export type StreamHandler = (event: string, data: Record<string, unknown>) => void

async function readStream(response: Response, onEvent: StreamHandler) {
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(text || `请求失败 ${response.status}`)
  }
  if (!response.body) throw new Error('浏览器不支持流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let index = buffer.indexOf('\n\n')
    while (index >= 0) {
      const block = buffer.slice(0, index)
      buffer = buffer.slice(index + 2)
      let event = 'message'
      const dataLines: string[] = []
      block.split('\n').forEach((line) => {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      })
      if (dataLines.length) {
        try {
          onEvent(event, JSON.parse(dataLines.join('\n')))
        } catch {
          onEvent(event, { raw: dataLines.join('\n') })
        }
      }
      index = buffer.indexOf('\n\n')
    }
  }
}

async function postStream(path: string, body: unknown, onEvent: StreamHandler, signal?: AbortSignal) {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${tokens.access}`,
    },
    body: JSON.stringify(body),
    signal,
  })
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
