import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useToastStore } from '@/stores/toast'
import PlansView from '@/views/PlansView.vue'

/**
 * 计划页首屏：list -> detail -> summary 串行读取。
 * 前两级挂掉必须把后端文案说出来；第三级只是打卡概览，读不到该静默降级。
 * 之前 load 只有 finally 没有 catch，失败会变成没人处理的 rejection + 一片空状态。
 */
const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  detail: vi.fn(),
  summary: vi.fn(),
}))

vi.mock('@/api', () => ({
  planApi: {
    list: mocks.list,
    detail: mocks.detail,
    generate: vi.fn(),
    approve: vi.fn(),
    rejectVersion: vi.fn(),
    removeDraftTask: vi.fn(),
    adjustmentFeedback: vi.fn(),
    adjust: vi.fn(),
    shift: vi.fn(),
    cancel: vi.fn(),
    patchTask: vi.fn(),
    checkin: vi.fn(),
  },
  trackingApi: { summary: mocks.summary },
  assessmentApi: { generate: vi.fn() },
  reportApi: { generate: vi.fn() },
}))

function mountPlans() {
  const pinia = createPinia()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  const wrapper = mount(PlansView, { global: { plugins: [pinia, router] } })
  return { wrapper, pinia }
}

const planSummary = {
  id: 'p1',
  title: '两周作息调整',
  duration_days: 14,
  start_date: '2026-11-01',
  end_date: '2026-11-15',
  status: 'active',
  created_at: '',
  current_version_id: 'v1',
}

const planDetail = {
  ...planSummary,
  assessment_id: null,
  adjustment: null,
  pending_version: null,
  tasks: [],
  versions: [],
}

const trackingSummary = {
  period_start: '2026-11-01',
  period_end: '2026-11-15',
  completion_rate: 0,
  task_total: 0,
  task_completed: 0,
  metrics: [],
  notes: [],
}

beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue([planSummary])
  mocks.detail.mockReset().mockResolvedValue(planDetail)
  mocks.summary.mockReset().mockResolvedValue(trackingSummary)
})

describe('计划页首屏', () => {
  it('三路都成功时渲染计划标题，且不弹提示', async () => {
    const { wrapper, pinia } = mountPlans()
    await flushPromises()

    expect(wrapper.text()).toContain('健康管理')
    expect(wrapper.text()).toContain('两周作息调整')
    expect(mocks.detail).toHaveBeenCalledWith('p1')
    expect(useToastStore(pinia).items).toHaveLength(0)
  })

  it('计划列表读失败时弹出后端给的文案', async () => {
    mocks.list.mockRejectedValue(new Error('计划服务 503'))
    const { pinia } = mountPlans()
    await flushPromises()

    const toasts = useToastStore(pinia).items
    expect(toasts.map((item) => item.text)).toContain('计划服务 503')
    expect(toasts.every((item) => item.tone === 'error')).toBe(true)
    expect(mocks.detail).not.toHaveBeenCalled()
  })

  it('详情读失败时也要提示，不能静默当成「没有计划」', async () => {
    mocks.detail.mockRejectedValue(new Error('详情接口超时'))
    const { pinia } = mountPlans()
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('详情接口超时')
  })

  it('打卡总结是附加信息，读失败不弹提示也不影响计划详情', async () => {
    mocks.summary.mockRejectedValue(new Error('统计服务挂了'))
    const { wrapper, pinia } = mountPlans()
    await flushPromises()

    expect(useToastStore(pinia).items).toHaveLength(0)
    expect(wrapper.text()).toContain('两周作息调整')
  })

  it('一个计划都没有时走空状态，不去请求详情', async () => {
    mocks.list.mockResolvedValue([])
    const { wrapper, pinia } = mountPlans()
    await flushPromises()

    expect(wrapper.text()).toContain('暂无计划')
    expect(mocks.detail).not.toHaveBeenCalled()
    expect(useToastStore(pinia).items).toHaveLength(0)
  })
})
