import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useToastStore } from '@/stores/toast'
import AdminView from '@/views/AdminView.vue'

/**
 * 管理页首屏两路并发读取。一路挂掉不能把另一路成功的数据一起丢掉，
 * 也不能停在「加载中」或把读失败误报成「暂无事件」。
 */
const mocks = vi.hoisted(() => ({
  services: vi.fn(),
  incidents: vi.fn(),
}))

vi.mock('@/api', () => ({
  adminApi: {
    services: mocks.services,
    incidents: mocks.incidents,
  },
}))

const status = {
  checkpointer: 'postgres',
  embedding_backend: 'keyword',
  llm_configured: false,
  graph_loaded: true,
}

const incident = {
  id: 'i1',
  incident_type: 'login_bruteforce',
  severity: 'medium',
  description: 'account=tester 连续失败 5 次',
  status: 'open',
  occurred_at: '2026-11-06T10:00:00Z',
  resolved_at: null,
}

function mountAdmin() {
  const pinia = createPinia()
  const wrapper = mount(AdminView, { global: { plugins: [pinia] } })
  return { wrapper, pinia }
}

beforeEach(() => {
  mocks.services.mockReset().mockResolvedValue(status)
  mocks.incidents.mockReset().mockResolvedValue([incident])
})

describe('管理页首屏', () => {
  it('两路都成功时渲染服务状态与安全事件，不弹提示', async () => {
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    expect(wrapper.text()).toContain('断点存储')
    expect(wrapper.text()).toContain('Postgres')
    expect(wrapper.text()).toContain('未配置（规则回答）')
    expect(wrapper.text()).toContain('login_bruteforce')
    expect(wrapper.text()).toContain('account=tester 连续失败 5 次')
    expect(useToastStore(pinia).items).toHaveLength(0)
  })

  it('没有事件时走空状态', async () => {
    mocks.incidents.mockResolvedValue([])
    const { wrapper } = mountAdmin()
    await flushPromises()

    expect(wrapper.text()).toContain('暂无安全事件')
    expect(wrapper.text()).toContain('断点存储')
  })

  it('服务状态读失败时弹提示，但事件列表仍渲染', async () => {
    mocks.services.mockRejectedValue(new Error('服务状态 503'))
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('服务状态 503')
    expect(wrapper.text()).not.toContain('加载中')
    expect(wrapper.text()).toContain('login_bruteforce')
    expect(wrapper.text()).toContain('服务状态读取失败')
  })

  it('事件读失败时明确说「读取失败」，不误导成「暂无事件」', async () => {
    mocks.incidents.mockRejectedValue(new Error('事件接口超时'))
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('事件接口超时')
    expect(wrapper.text()).toContain('安全事件读取失败')
    expect(wrapper.text()).not.toContain('暂无安全事件')
    expect(wrapper.text()).toContain('断点存储')
  })

  it('两路都失败也不停在加载中', async () => {
    mocks.services.mockRejectedValue(new Error('服务状态 503'))
    mocks.incidents.mockRejectedValue(new Error('事件接口超时'))
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    expect(wrapper.text()).not.toContain('加载中')
    expect(useToastStore(pinia).items).toHaveLength(1)
  })

  it('点刷新会重新拉两路数据', async () => {
    const { wrapper } = mountAdmin()
    await flushPromises()
    expect(mocks.services).toHaveBeenCalledTimes(1)

    const refresh = wrapper.findAll('button').find((item) => item.text() === '刷新')
    expect(refresh).toBeDefined()
    await refresh!.trigger('click')
    await flushPromises()

    expect(mocks.services).toHaveBeenCalledTimes(2)
    expect(mocks.incidents).toHaveBeenCalledTimes(2)
  })

  it('时间是无效字符串也不把页面渲染崩', async () => {
    mocks.incidents.mockResolvedValue([{ ...incident, occurred_at: 'not-a-date', severity: null }])
    const { wrapper } = mountAdmin()
    await flushPromises()

    expect(wrapper.text()).toContain('not-a-date')
    expect(wrapper.text()).toContain('未分级')
  })
})
