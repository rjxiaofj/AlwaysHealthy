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

describe('确认卡片', () => {
  function triggerConfirmation(onEvent: (event: string, data: Record<string, unknown>) => void) {
    onEvent('confirmation_required', {
      run_id: 'r1',
      approval_type: 'profile',
      message: '请确认以下信息是否正确',
      summary: { 年龄: '39', 身高: '175' },
      plan_id: null,
      plan_version_id: null,
    })
  }

  it('confirmation_required 事件弹出确认卡片，带摘要', async () => {
    mocks.streamMessage.mockImplementation(async (_id: string, _content: string, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      triggerConfirmation(onEvent)
    })

    const { wrapper } = await mountChat()
    await sendMessage(wrapper, '我 39 岁，身高 175')

    expect(wrapper.text()).toContain('请确认以下信息是否正确')
    expect(wrapper.text()).toContain('年龄')
  })

  it('approve 调用 streamResume 并清掉确认卡片', async () => {
    mocks.streamMessage.mockImplementation(async (_id: string, _content: string, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      triggerConfirmation(onEvent)
    })
    mocks.streamResume.mockResolvedValue(undefined)

    const { wrapper } = await mountChat()
    await sendMessage(wrapper, '我 39 岁')

    await wrapper.findAll('button').find((b) => b.text().includes('信息正确'))!.trigger('click')
    await flushPromises()

    expect(mocks.streamResume).toHaveBeenCalledTimes(1)
    const args = mocks.streamResume.mock.calls[0]
    expect(args[0]).toBe('r1')
    expect(args[1].decision).toBe('approve')
    expect(args[1].approval_type).toBe('profile')
    // 确认卡片消失：message 文案不再出现（外层 section 也是 glass-strong，不能按类名找）
    expect(wrapper.text()).not.toContain('请确认以下信息是否正确')
  })

  it('reject 调用 streamResume 并清掉确认卡片', async () => {
    mocks.streamMessage.mockImplementation(async (_id: string, _content: string, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      triggerConfirmation(onEvent)
    })
    mocks.streamResume.mockResolvedValue(undefined)

    const { wrapper } = await mountChat()
    await sendMessage(wrapper, '我 39 岁')

    await wrapper.findAll('button').find((b) => b.text().trim() === '放弃')!.trigger('click')
    await flushPromises()

    const args = mocks.streamResume.mock.calls[0]
    expect(args[1].decision).toBe('reject')
    expect(wrapper.text()).not.toContain('请确认以下信息是否正确')
  })

  it('待确认时又发新消息，旧确认卡片作废', async () => {
    mocks.streamMessage.mockImplementation(async (_id: string, _content: string, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      triggerConfirmation(onEvent)
    })

    const { wrapper } = await mountChat()
    await sendMessage(wrapper, '我 39 岁，身高 175')
    expect(wrapper.text()).toContain('请确认以下信息是否正确')

    // 新一轮没有再弹确认：卡片不该留在页面上让人点一个已经 cancelled 的 run
    mocks.streamMessage.mockImplementation(async () => {})
    await sendMessage(wrapper, '再问一句')
    expect(wrapper.text()).not.toContain('请确认以下信息是否正确')
  })

  it('恢复被拒时清掉过期卡片（modify 分支自己不会清）', async () => {
    mocks.streamMessage.mockImplementation(async (_id: string, _content: string, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      triggerConfirmation(onEvent)
    })
    mocks.streamResume.mockImplementation(async (_id: string, _payload: unknown, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      onEvent('run_error', { code: 'RUN_NOT_RESUMABLE', message: '这次确认已经过期' })
    })

    const { wrapper, pinia } = await mountChat()
    await sendMessage(wrapper, '我 39 岁')

    const modifyBtn = () => wrapper.findAll('button').find((b) => b.text().includes('需要补充'))!
    await modifyBtn().trigger('click')
    await flushPromises()
    await wrapper.find('textarea[placeholder="说明需要调整的地方"]').setValue('身高其实 178')
    await modifyBtn().trigger('click')
    await flushPromises()

    expect(useToastStore(pinia).items.some((item) => item.text.includes('过期'))).toBe(true)
    expect(wrapper.text()).not.toContain('请确认以下信息是否正确')
  })

  it('modify 没填反馈时先展开输入框，不调 streamResume；填了再提交', async () => {
    mocks.streamMessage.mockImplementation(async (_id: string, _content: string, onEvent: (event: string, data: Record<string, unknown>) => void) => {
      triggerConfirmation(onEvent)
    })
    mocks.streamResume.mockResolvedValue(undefined)

    const { wrapper } = await mountChat()
    await sendMessage(wrapper, '我 39 岁')

    // 第一次点「需要补充」：没填反馈，只展开 textarea，不发起 resume
    const modifyBtn = () => wrapper.findAll('button').find((b) => b.text().includes('需要补充'))!
    await modifyBtn().trigger('click')
    await flushPromises()
    expect(mocks.streamResume).not.toHaveBeenCalled()
    const textarea = wrapper.find('textarea[placeholder="说明需要调整的地方"]')
    expect(textarea.exists()).toBe(true)

    // 填上反馈再点：这次发起 modify
    await textarea.setValue('身高其实 178')
    await modifyBtn().trigger('click')
    await flushPromises()

    const args = mocks.streamResume.mock.calls[0]
    expect(args[1].decision).toBe('modify')
    expect(args[1].feedback).toBe('身高其实 178')
  })
})
