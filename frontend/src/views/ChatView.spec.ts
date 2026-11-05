import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useToastStore } from '@/stores/toast'
import ChatView from '@/views/ChatView.vue'

/**
 * 聊天页的渲染层守卫。流式那套（切帧、401、超时）在 api/stream.spec.ts 里验过，
 * 这里验的是「事件到了，界面有没有照着变」：token 累积、错误提示、离开页面断流。
 */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  messages: vi.fn(),
  streamMessage: vi.fn(),
  streamResume: vi.fn(),
}))

vi.mock('@/api', () => ({
  chatApi: { list: mocks.list, create: mocks.create, messages: mocks.messages },
}))

vi.mock('@/api/stream', () => ({
  streamMessage: mocks.streamMessage,
  streamResume: mocks.streamResume,
}))

function deferred() {
  let resolve!: () => void
  const promise = new Promise<void>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function abortError() {
  return Object.assign(new Error('aborted'), { name: 'AbortError' })
}

async function mountChat() {
  const pinia = createPinia()
  const wrapper = mount(ChatView, { global: { plugins: [pinia] } })
  await flushPromises()
  return { wrapper, pinia }
}

async function sendMessage(wrapper: Awaited<ReturnType<typeof mountChat>>['wrapper'], text: string) {
  await wrapper.find('footer textarea').setValue(text)
  await wrapper.find('footer button').trigger('click')
  await flushPromises()
}

beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue([{ id: 'c1', title: '第一次对话', last_message: '', created_at: '' }])
  mocks.create.mockReset().mockResolvedValue({ id: 'c1', title: '新的健康对话', last_message: '', created_at: '' })
  mocks.messages.mockReset().mockResolvedValue([])
  mocks.streamMessage.mockReset()
  mocks.streamResume.mockReset()
  // happy-dom 没有实现元素滚动，组件里会调 scrollTo
  Element.prototype.scrollTo = (() => undefined) as never
})

describe('聊天页渲染', () => {
  it('发送后先把用户这句话放上屏，token 到达时逐字追加', async () => {
    const gate = deferred()
    mocks.streamMessage.mockImplementation(async (_id: string, _content: string, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      onEvent('token', { content: '你' })
      onEvent('token', { content: '好' })
      await gate.promise
    })

    const { wrapper } = await mountChat()
    await sendMessage(wrapper, '我最近睡不好')

    expect(wrapper.text()).toContain('我最近睡不好')
    expect(wrapper.text()).toContain('你好')

    gate.resolve()
    await flushPromises()
  })

  it('run_error 事件弹出后端给的提示，不是空白失败', async () => {
    mocks.streamMessage.mockImplementation(async (_id: string, _content: string, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      onEvent('run_error', { code: 'WORKFLOW_TIMEOUT', message: '这次分析没有在预期时间内完成，请稍后重试' })
    })

    const { wrapper, pinia } = await mountChat()
    await sendMessage(wrapper, '帮我看看体检报告')

    const toasts = useToastStore(pinia).items
    expect(toasts.some((item) => item.text.includes('没有在预期时间内完成'))).toBe(true)
    expect(toasts.every((item) => item.tone === 'error')).toBe(true)
  })

  it('节点进度显示在标题栏，流结束后清掉', async () => {
    const gate = deferred()
    mocks.streamMessage.mockImplementation(async (_id: string, _content: string, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      onEvent('node_progress', { message: '正在评估风险' })
      await gate.promise
    })

    const { wrapper } = await mountChat()
    await sendMessage(wrapper, '我最近头晕')

    expect(wrapper.text()).toContain('正在评估风险')

    gate.resolve()
    await flushPromises()
    expect(wrapper.text()).not.toContain('正在评估风险')
  })

  it('离开页面时把在跑的流掐掉', async () => {
    const gate = deferred()
    let captured: AbortSignal | undefined
    mocks.streamMessage.mockImplementation(
      async (_id: string, _content: string, _onEvent: unknown, signal?: AbortSignal) => {
        captured = signal
        await gate.promise
      },
    )

    const { wrapper } = await mountChat()
    await sendMessage(wrapper, '我最近心率有点快')

    expect(captured?.aborted).toBe(false)
    wrapper.unmount()
    expect(captured?.aborted).toBe(true)

    gate.resolve()
  })

  it('用户自己取消时不弹错误提示', async () => {
    mocks.streamMessage.mockRejectedValue(abortError())

    const { wrapper, pinia } = await mountChat()
    await sendMessage(wrapper, '随便问问')

    expect(useToastStore(pinia).items).toHaveLength(0)
  })

  it('普通失败仍然要给提示', async () => {
    mocks.streamMessage.mockRejectedValue(new Error('请求失败 502'))

    const { wrapper, pinia } = await mountChat()
    await sendMessage(wrapper, '随便问问')

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('请求失败 502')
  })
})
