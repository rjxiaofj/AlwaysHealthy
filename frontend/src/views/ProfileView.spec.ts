import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useToastStore } from '@/stores/toast'
import ProfileView from '@/views/ProfileView.vue'

/**
 * 档案页首屏：五路并发读取，任一路挂掉都得说清楚，不能只剩一片空状态。
 * 之前 load 没有 catch，onMounted(load) 直接抛成没人处理的 rejection。
 */
const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  files: vi.fn(),
  emergencyEvents: vi.fn(),
  reports: vi.fn(),
  consents: vi.fn(),
}))

vi.mock('@/api', () => ({
  profileApi: {
    get: mocks.get,
    files: mocks.files,
    emergencyEvents: mocks.emergencyEvents,
    addHistory: vi.fn(),
    upload: vi.fn(),
    extracted: vi.fn(),
    applyExtracted: vi.fn(),
    patch: vi.fn(),
  },
  reportApi: { list: mocks.reports },
  consentApi: { list: mocks.consents, set: vi.fn() },
}))

function mountProfile() {
  const pinia = createPinia()
  const wrapper = mount(ProfileView, {
    global: { plugins: [pinia], stubs: { RouterLink: true } },
  })
  return { wrapper, pinia }
}

const emptyProfile = {
  id: 'u1',
  birth_date: null,
  sex: null,
  height_cm: null,
  weight_kg: null,
  waist_cm: null,
  occupation: null,
  lifestyle: {},
  age: null,
  age_source: null,
  histories: [],
  conditions: [],
  created_at: '',
  updated_at: '',
}

beforeEach(() => {
  mocks.get.mockReset().mockResolvedValue(emptyProfile)
  mocks.files.mockReset().mockResolvedValue([])
  mocks.emergencyEvents.mockReset().mockResolvedValue([])
  mocks.reports.mockReset().mockResolvedValue([])
  mocks.consents.mockReset().mockResolvedValue([])
})

describe('档案页首屏', () => {
  it('五路都成功时正常渲染，不弹提示', async () => {
    const { wrapper, pinia } = mountProfile()
    await flushPromises()

    expect(wrapper.text()).toContain('个人中心')
    expect(useToastStore(pinia).items).toHaveLength(0)
  })

  it('档案主数据读失败时弹出后端给的文案', async () => {
    mocks.get.mockRejectedValue(new Error('档案读取 503'))
    const { pinia } = mountProfile()
    await flushPromises()

    const toasts = useToastStore(pinia).items
    expect(toasts.map((item) => item.text)).toContain('档案读取 503')
    expect(toasts.every((item) => item.tone === 'error')).toBe(true)
  })

  it('报告列表读失败也要提示，不能静默变成空列表', async () => {
    mocks.reports.mockRejectedValue(new Error('报告服务超时'))
    const { pinia } = mountProfile()
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('报告服务超时')
  })

  it('急救事件是附加信息，读失败不拖垮整页', async () => {
    mocks.emergencyEvents.mockRejectedValue(new Error('事件接口挂了'))
    const { wrapper, pinia } = mountProfile()
    await flushPromises()

    expect(useToastStore(pinia).items).toHaveLength(0)
    expect(wrapper.text()).toContain('个人中心')
  })
})
