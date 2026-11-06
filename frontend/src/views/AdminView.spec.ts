import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import AdminView from '@/views/AdminView.vue'

/**
 * 管理页三路并发读取：一路挂掉不能把另外两路成功的数据一起丢掉，
 * 也不能停在「加载中」或把读失败误报成「暂无」。写操作失败要显示后端文案、不误改本地行。
 */
const mocks = vi.hoisted(() => ({
  services: vi.fn(),
  incidents: vi.fn(),
  users: vi.fn(),
  setRole: vi.fn(),
  resolveIncident: vi.fn(),
}))

vi.mock('@/api', () => ({
  authApi: { me: vi.fn(), login: vi.fn(), register: vi.fn(), logout: vi.fn() },
  adminApi: {
    services: mocks.services,
    incidents: mocks.incidents,
    users: mocks.users,
    setRole: mocks.setRole,
    resolveIncident: mocks.resolveIncident,
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

const account = {
  id: 'u1',
  username: 'alice',
  email: null,
  role: 'user',
  status: 'active',
  created_at: '2026-11-06T09:00:00Z',
  last_login_at: null,
}

function mountAdmin(selfId: string | null = null) {
  const pinia = createPinia()
  if (selfId !== null) {
    useAuthStore(pinia).user = { ...account, id: selfId, role: 'admin' }
  }
  const wrapper = mount(AdminView, { global: { plugins: [pinia] } })
  return { wrapper, pinia }
}

function buttonByText(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

beforeEach(() => {
  mocks.services.mockReset().mockResolvedValue(status)
  mocks.incidents.mockReset().mockResolvedValue([incident])
  mocks.users.mockReset().mockResolvedValue({ items: [account], total: 1, page: 1, page_size: 20 })
  mocks.setRole.mockReset().mockResolvedValue({ ...account, role: 'admin' })
  mocks.resolveIncident.mockReset().mockResolvedValue({ ...incident, status: 'resolved', resolved_at: '2026-11-06T12:00:00Z' })
})

describe('管理页首屏', () => {
  it('三路都成功时渲染服务状态、账号与安全事件，不弹提示', async () => {
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    expect(wrapper.text()).toContain('断点存储')
    expect(wrapper.text()).toContain('Postgres')
    expect(wrapper.text()).toContain('未配置（规则回答）')
    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).toContain('普通用户')
    expect(wrapper.text()).toContain('login_bruteforce')
    expect(wrapper.text()).toContain('account=tester 连续失败 5 次')
    expect(useToastStore(pinia).items).toHaveLength(0)
    expect(mocks.users).toHaveBeenCalledWith(1, 20)
  })

  it('没有事件时走空状态', async () => {
    mocks.incidents.mockResolvedValue([])
    const { wrapper } = mountAdmin()
    await flushPromises()

    expect(wrapper.text()).toContain('暂无安全事件')
    expect(wrapper.text()).toContain('断点存储')
  })

  it('服务状态读失败时弹提示，但账号与事件列表仍渲染', async () => {
    mocks.services.mockRejectedValue(new Error('服务状态 503'))
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('服务状态 503')
    expect(wrapper.text()).not.toContain('加载中')
    expect(wrapper.text()).toContain('login_bruteforce')
    expect(wrapper.text()).toContain('alice')
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

  it('账号列表读失败时单独降级，不拖垮另外两张卡片', async () => {
    mocks.users.mockRejectedValue(new Error('账号接口 500'))
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('账号接口 500')
    expect(wrapper.text()).toContain('账号列表读取失败')
    expect(wrapper.text()).not.toContain('暂无账号')
    expect(wrapper.text()).toContain('断点存储')
    expect(wrapper.text()).toContain('login_bruteforce')
  })

  it('三路都失败也不停在加载中', async () => {
    mocks.services.mockRejectedValue(new Error('服务状态 503'))
    mocks.incidents.mockRejectedValue(new Error('事件接口超时'))
    mocks.users.mockRejectedValue(new Error('账号接口 500'))
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    expect(wrapper.text()).not.toContain('加载中')
    expect(useToastStore(pinia).items).toHaveLength(1)
  })

  it('点刷新会重新拉三路数据', async () => {
    const { wrapper } = mountAdmin()
    await flushPromises()
    expect(mocks.services).toHaveBeenCalledTimes(1)

    const refresh = buttonByText(wrapper, '刷新')
    expect(refresh).toBeDefined()
    await refresh!.trigger('click')
    await flushPromises()

    expect(mocks.services).toHaveBeenCalledTimes(2)
    expect(mocks.incidents).toHaveBeenCalledTimes(2)
    expect(mocks.users).toHaveBeenCalledTimes(2)
  })

  it('时间是无效字符串也不把页面渲染崩', async () => {
    mocks.incidents.mockResolvedValue([{ ...incident, occurred_at: 'not-a-date', severity: null }])
    const { wrapper } = mountAdmin()
    await flushPromises()

    expect(wrapper.text()).toContain('not-a-date')
    expect(wrapper.text()).toContain('未分级')
  })
})

describe('管理页写操作', () => {
  it('点设为管理员会带 admin 提交，成功后就地更新行', async () => {
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    await buttonByText(wrapper, '设为管理员')!.trigger('click')
    await flushPromises()

    expect(mocks.setRole).toHaveBeenCalledWith('u1', 'admin')
    expect(wrapper.text()).toContain('管理员')
    expect(wrapper.text()).toContain('取消管理员')
    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('alice 已设为管理员')
  })

  it('角色变更失败显示后端文案，本地行不误改成管理员', async () => {
    mocks.setRole.mockRejectedValue(new Error('至少需要保留一个管理员'))
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    await buttonByText(wrapper, '设为管理员')!.trigger('click')
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('至少需要保留一个管理员')
    expect(wrapper.text()).toContain('普通用户')
    expect(wrapper.text()).not.toContain('取消管理员')
  })

  it('当前账号的操作按钮禁用，标记成「当前账号」', async () => {
    const { wrapper } = mountAdmin('u1')
    await flushPromises()

    expect(wrapper.text()).toContain('当前账号')
    const button = buttonByText(wrapper, '设为管理员')!
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')
    await flushPromises()
    expect(mocks.setRole).not.toHaveBeenCalled()
  })

  it('点标记为已处置会提交并替换那一行', async () => {
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    await buttonByText(wrapper, '标记为已处置')!.trigger('click')
    await flushPromises()

    expect(mocks.resolveIncident).toHaveBeenCalledWith('i1')
    expect(wrapper.text()).toContain('已处置')
    expect(wrapper.text()).not.toContain('标记为已处置')
    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('事件已处置')
  })

  it('处置失败显示后端文案，事件仍是 open 且按钮还在', async () => {
    mocks.resolveIncident.mockRejectedValue(new Error('该事件状态不能处置'))
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    await buttonByText(wrapper, '标记为已处置')!.trigger('click')
    await flushPromises()

    expect(useToastStore(pinia).items.map((item) => item.text)).toContain('该事件状态不能处置')
    expect(wrapper.text()).toContain('标记为已处置')
  })

  it('已处置事件不再给处置按钮，显示处置时间', async () => {
    mocks.incidents.mockResolvedValue([{ ...incident, status: 'resolved', resolved_at: '2026-11-06T12:00:00Z' }])
    const { wrapper } = mountAdmin()
    await flushPromises()

    expect(wrapper.text()).toContain('处置时间')
    expect(buttonByText(wrapper, '标记为已处置')).toBeUndefined()
  })

  it('分页点下一页会按第二页重拉账号列表', async () => {
    mocks.users.mockResolvedValue({ items: [account], total: 25, page: 1, page_size: 20 })
    const { wrapper } = mountAdmin()
    await flushPromises()

    await buttonByText(wrapper, '下一页')!.trigger('click')
    await flushPromises()

    expect(mocks.users).toHaveBeenLastCalledWith(2, 20)
    expect(wrapper.text()).toContain('第 2 / 2 页')
  })
})
