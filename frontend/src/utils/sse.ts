export interface SseFrame {
  event: string
  data: string
}

/**
 * 从缓冲区里切出已经完整的 SSE 帧，返回剩下的半截。
 *
 * 服务端用 `\n\n` 分隔事件，但经过某些代理（或者客户端自己拼过）会变成 `\r\n\r\n`。
 * 那种情况下 `indexOf('\n\n')` 一个都找不到——`\r\n\r\n` 里没有两个相邻的 `\n`——
 * 整条流会一个事件都出不来，缓冲区一直涨到流结束。所以先归一化再切。
 */
export function splitSseFrames(buffer: string): { frames: SseFrame[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')
  // 最后一段没有以空行收尾，可能只到了半个事件，留在缓冲区里等下一片
  const rest = parts.pop() ?? ''
  const frames = parts.filter((block) => block.trim()).map(parseSseFrame)
  return { frames, rest }
}

export function parseSseFrame(block: string): SseFrame {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trim())
  }
  // 规范里多行 data 用 \n 拼回一个字符串
  return { event, data: data.join('\n') }
}
