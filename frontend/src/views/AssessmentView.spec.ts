import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useToastStore } from '@/stores/toast'
import AssessmentView from '@/views/AssessmentView.vue'

/**
 * 评估页渲染层守卫：首屏 latest + list 两路并发、历史条目点击走 detail。
 * load 之前只有 finally，读失败会掉进「还没有可用的评估」空状态，
 * 用户以为没做过评估，其实是这次没读出来。
 */
const mocks = vi.hoisted(() => ({
  latest: vi.fn(),
  list: vi.fn(),
  detail: vi.fn(),
  create: vi.fn(),
}))

vi.mock('@/api', () => ({
  assessmentApi: {
    latest: mocks.latest,
    list: mocks.list,
    detail: mocks.detail,
    create: mocks.create,
  },
}))

function mountAssessment() {
  const pinia = createPinia()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  const wrapper = mount(AssessmentView, { global: { plugins: [pinia, router] } })
  return { wrapper, pinia }
}

const assessment = {
  id: 'a1',
  overall_level: '低',
  urgency: '非紧急',
  rule_engine_version: 'v1.0',
  knowledge_version: 'kb-2026-11',
  created_at: '2026-11-06T10:00:00Z',
  profile_version: 3,
  dimensions: [
    {
      dimension: 'cardiovascular',
      level: '中',
      risk_factors: [{ rule_id: 'r1', message: '收缩压偏高', value: 138, unit: 'mmHg' }],
      missing_data: [],
      explanation: '血压略高于参考区间',
      limitations: ['仅按自报数据'],
      evidence_sources: [{ source_id: 's1', title: '血压管理指南', version: '2024', page: 12 }],
    },
  ],
  recommendations: [
    {
      id: 'rec1',
      dimension: 'cardiovascular',
      category: '饮食',
      priority: 'high',
      title: '减少钠盐',
      description: '',
      action_items: ['每天食盐少于 5g'],
      cautions: [],
      requires_professional_consultation: false,
    },
  ],
}

const historyItem = {
  id: 'a0',
  overall_level: '中',
  urgency: '非紧急',
  created_at: '2026-11-01T10:00:00Z',
  profile_version: 2,
}

beforeEach(() => {
  mocks.latest.mockReset().mockResolvedValue(assessment)
  mocks.list.mockReset().mockResolvedValue({ items: [historyItem] })
  mocks.detail.mockReset().mockResolvedValue(assessment)
  mocks.create.mockReset().mockResolvedValue(assessment)
})

describe('评估页首屏', () => {
  it('两路都成功时渲染维度、建议与历史记录，不弹提示', async () => {
    const { wrapper, pinia } = mountAssessment()
    await flushPromises()

    expect(wrapper.text()).toContain('健康评估')
    expect(wrapper.text()).toContain('心血管健康')
    expect(wrapper.text()).toContain('减少钠盐')
    expect(wrapper.text()).toContain('档案 v2')
    expect(wrapper.text()).not.toContain('加载中')
    expect(useToastStore(pinia).items).toHaveLength(0)
  })

  it('最新评估读失败时弹出后端文案，且不再卡在加载中', async () => {
    mocks.latest.mockRejectedValue(new Error('评估服务 503'))
    const { wrapper, pinia } = mountAssessment()
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('评估服务 503')
    expect(wrapper.text()).not.toContain('加载中')
  })

  it('历史列表读失败也要提示，不能静默当成没有历史', async () => {
    mocks.list.mockRejectedValue(new Error('历史列表超时'))
    const { pinia } = mountAssessment()
    await flushPromises()

    const toasts = useToastStore(pinia).items
    expect(toasts.map((item) => item.text)).toContain('历史列表超时')
    expect(toasts.every((item) => item.tone === 'error')).toBe(true)
  })

  it('确实没有评估时走空状态，不弹提示', async () => {
    mocks.latest.mockResolvedValue(null)
    mocks.list.mockResolvedValue({ items: [] })
    const { wrapper, pinia } = mountAssessment()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有可用的评估')
    expect(useToastStore(pinia).items).toHaveLength(0)
  })
})

describe('评估页历史条目', () => {
  it('点击历史条目会读取详情并替换当前评估', async () => {
    mocks.detail.mockResolvedValue({ ...assessment, id: 'a0', rule_engine_version: 'v0.9' })
    const { wrapper, pinia } = mountAssessment()
    await flushPromises()

    await wrapper.find('li.cursor-pointer').trigger('click')
    await flushPromises()

    expect(mocks.detail).toHaveBeenCalledWith('a0')
    expect(wrapper.text()).toContain('v0.9')
    expect(useToastStore(pinia).items).toHaveLength(0)
  })

  it('历史评估已被清理时给出提示，而不是点了没反应', async () => {
    mocks.detail.mockRejectedValue(new Error('历史评估已清理'))
    const { wrapper, pinia } = mountAssessment()
    await flushPromises()

    await wrapper.find('li.cursor-pointer').trigger('click')
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('历史评估已清理')
  })
})
