import { describe, expect, it } from 'vitest'

import { parseSseFrame, splitSseFrames } from '@/utils/sse'

describe('SSE 切帧', () => {
  it('按空行切出多个事件', () => {
    const raw = 'event: token\ndata: {"content":"你"}\n\nevent: node_progress\ndata: {"node":"assess"}\n\n'

    const { frames, rest } = splitSseFrames(raw)

    expect(frames.map((item) => item.event)).toEqual(['token', 'node_progress'])
    expect(frames[0].data).toBe('{"content":"你"}')
    expect(rest).toBe('')
  })

  it('半截事件留在缓冲区', () => {
    const { frames, rest } = splitSseFrames('event: token\ndata: {"content":"你"}\n\nevent: token\ndata: {"con')

    expect(frames).toHaveLength(1)
    expect(rest).toBe('event: token\ndata: {"con')
  })

  it('CRLF 分隔也能切出来', () => {
    // '/r/n/r/n' 里没有相邻的两个 /n，直接 indexOf('/n/n') 会一个都找不到
    const raw = 'event: token\r\ndata: {"content":"你"}\r\n\r\n'

    const { frames } = splitSseFrames(raw)

    expect(frames).toHaveLength(1)
    expect(frames[0].event).toBe('token')
    expect(frames[0].data).toBe('{"content":"你"}')
  })

  it('多行 data 拼回一个字符串', () => {
    const { frames } = splitSseFrames('event: report\ndata: 第一行\ndata: 第二行\n\n')

    expect(frames[0].data).toBe('第一行\n第二行')
  })

  it('没有 event 字段时按 message 处理', () => {
    const { frames } = splitSseFrames('data: {"ok":true}\n\n')

    expect(frames[0].event).toBe('message')
  })

  it('只有空行的块不算事件', () => {
    const { frames } = splitSseFrames('\n\n\n\nevent: token\ndata: {"a":1}\n\n')

    expect(frames).toHaveLength(1)
  })

  it('没有 data 的块给空字符串', () => {
    const frame = parseSseFrame('event: heartbeat')

    expect(frame).toEqual({ event: 'heartbeat', data: '' })
  })

  it('event 与 data 之间多打的空格不影响', () => {
    const frame = parseSseFrame('event:   token  \ndata:   {"a":1}  ')

    expect(frame.event).toBe('token')
    expect(frame.data).toBe('{"a":1}')
  })
})
