import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import AdminView from '@/views/AdminView.vue'

/**
 * 后台多菜单页：侧边栏五个视图，九路接口首屏各自降级，
 * 写操作（角色/状态/删除/处置/运行时配置）成功更新、失败显示后端文案且不误改本地行。
 */
const mocks = vi.hoisted(() => ({
  services: vi.fn(),
  overview: vi.fn(),
  users: vi.fn(),
  setRole: vi.fn(),
  setStatus: vi.fn(),
  deleteUser: vi.fn(),
  audits: vi.fn(),
  incidents: vi.fn(),
  resolveIncident: vi.fn(),
  runtime: vi.fn(),
  setRuntime: vi.fn(),
  agents: vi.fn(),
  workflowStats: vi.fn(),
  knowledge: vi.fn(),
}))

vi.mock('@/api', () => ({
  authApi: { me: vi.fn(), login: vi.fn(), register: vi.fn(), logout: vi.fn() },
  adminApi: {
    services: mocks.services,
    overview: mocks.overview,
    users: mocks.users,
    setRole: mocks.setRole,
    setStatus: mocks.setStatus,
    deleteUser: mocks.deleteUser,
    audits: mocks.audits,
    incidents: mocks.incidents,
    resolveIncident: mocks.resolveIncident,
    runtime: mocks.runtime,
    setRuntime: mocks.setRuntime,
    agents: mocks.agents,
    workflowStats: mocks.workflowStats,
    knowledge: mocks.knowledge,
  },
}))

const status = {
  checkpointer: 'postgres',
  embedding_backend: 'keyword',
  llm_configured: false,
  llm_model: 'deepseek-chat',
  graph_loaded: true,
}

const overview = {
  user_total: 3,
  admin_total: 1,
  open_incidents: 2,
  login_fail_today: 5,
  new_users_today: 1,
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

const audit = {
  id: 'a1',
  actor_user_id: null,
  action: 'login',
  resource_type: 'user',
  resource_id: 'alice',
  result: 'fail',
  request_id: 'req1',
  created_at: '2026-11-06T09:00:00Z',
}

const runtime = { llm_model: 'deepseek-chat', llm_api_key: 'sk-test', embedding_backend: 'keyword' }

function mountAdmin(selfId: string | null = null) {
  const pinia = createPinia()
  if (selfId !== null) {
    useAuthStore(pinia).user = { ...account, id: selfId, role: 'admin' }
  }
  const wrapper = mount(AdminView, { global: { plugins: [pinia] } })
  return { wrapper, pinia }
}

function buttonByText(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text().includes(text))
}

beforeEach(() => {
  mocks.services.mockReset().mockResolvedValue(status)
  mocks.overview.mockReset().mockResolvedValue(overview)
  mocks.users.mockReset().mockResolvedValue({ items: [account], total: 1, page: 1, page_size: 20 })
  mocks.setRole.mockReset().mockResolvedValue({ ...account, role: 'admin' })
  mocks.setStatus.mockReset().mockResolvedValue({ ...account, status: 'disabled' })
  mocks.deleteUser.mockReset().mockResolvedValue(null)
  mocks.audits.mockReset().mockResolvedValue({ items: [audit], total: 1, page: 1, page_size: 20 })
  mocks.incidents.mockReset().mockResolvedValue([incident])
  mocks.resolveIncident.mockReset().mockResolvedValue({ ...incident, status: 'resolved', resolved_at: '2026-11-06T12:00:00Z' })
  mocks.runtime.mockReset().mockResolvedValue(runtime)
  mocks.setRuntime.mockReset().mockResolvedValue(runtime)
  mocks.agents.mockReset().mockResolvedValue([{ name: 'supervisor', loaded: true }])
  mocks.workflowStats.mockReset().mockResolvedValue({ running: 0, waiting_user: 0, cancelled: 0, failed: 0, completed: 1 })
  mocks.knowledge.mockReset().mockResolvedValue({ chunks: 48 })
})

describe('后台多菜单页', () => {
  it('默认停在总览，显示统计与服务状态', async () => {
    const { wrapper, pinia } = await (async () => {
      const r = mountAdmin()
      await flushPromises()
      return r
    })()

    expect(wrapper.text()).toContain('用户总数')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('断点存储')
    expect(wrapper.text()).toContain('Postgres')
    expect(useToastStore(pinia).items).toHaveLength(0)
  })

  it('五个菜单都在，点账号切到账号视图', async () => {
    const { wrapper } = mountAdmin()
    await flushPromises()

    const navButtons = wrapper.findAll('aside button')
    expect(navButtons.map((b) => b.text())).toEqual(['总览', '账号', '审计', '安全事件', '模型与 Agent'])

    await navButtons.find((b) => b.text() === '账号')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('账号与角色')
    expect(wrapper.text()).toContain('alice')
  })

  it('模型与 Agent 视图显示参数表单与 Agent 清单', async () => {
    const { wrapper } = mountAdmin()
    await flushPromises()

    const navButtons = wrapper.findAll('aside button')
    await navButtons.find((b) => b.text() === '模型与 Agent')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('模型参数')
    expect(wrapper.text()).toContain('supervisor')
    expect(wrapper.text()).toContain('知识库 chunk 数：48')
  })

  it('服务状态读失败时弹提示，但总览仍渲染', async () => {
    mocks.services.mockRejectedValue(new Error('服务状态 503'))
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()

    expect(useToastStore(pinia).items.map((i) => i.text)).toContain('服务状态 503')
    expect(wrapper.text()).toContain('用户总数')
    expect(wrapper.text()).toContain('服务状态读取失败')
  })

  it('九路都不失败时不停在加载中', async () => {
    mocks.services.mockRejectedValue(new Error('x'))
    mocks.overview.mockRejectedValue(new Error('x'))
    mocks.users.mockRejectedValue(new Error('x'))
    mocks.audits.mockRejectedValue(new Error('x'))
    mocks.incidents.mockRejectedValue(new Error('x'))
    mocks.runtime.mockRejectedValue(new Error('x'))
    const { wrapper } = mountAdmin()
    await flushPromises()
    expect(wrapper.text()).not.toContain('加载中')
  })
})

describe('账号写操作', () => {
  async function goAccounts() {
    const { wrapper, pinia } = mountAdmin('self-id')
    await flushPromises()
    const navButtons = wrapper.findAll('aside button')
    await navButtons.find((b) => b.text() === '账号')!.trigger('click')
    await flushPromises()
    return { wrapper, pinia }
  }

  it('设管理员前弹确认，确认后提交', async () => {
    vi.stubGlobal('confirm', vi.fn().mockReturnValue(true))
    const { wrapper } = await goAccounts()

    await buttonByText(wrapper, '设为管理员')!.trigger('click')
    await flushPromises()

    expect(mocks.setRole).toHaveBeenCalledWith('u1', 'admin')
    expect(window.confirm).toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('取消确认不提交', async () => {
    vi.stubGlobal('confirm', vi.fn().mockReturnValue(false))
    const { wrapper } = await goAccounts()

    await buttonByText(wrapper, '设为管理员')!.trigger('click')
    await flushPromises()

    expect(mocks.setRole).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('停用账号提交并更新行', async () => {
    const { wrapper, pinia } = await goAccounts()

    await buttonByText(wrapper, '停用')!.trigger('click')
    await flushPromises()

    expect(mocks.setStatus).toHaveBeenCalledWith('u1', 'disabled')
    expect(useToastStore(pinia).items.map((i) => i.text)).toContain('alice 已停用')
  })

  it('删除前要输入用户名，不匹配则拦截', async () => {
    vi.stubGlobal('prompt', vi.fn().mockReturnValue('wrong'))
    const { wrapper, pinia } = await goAccounts()

    await buttonByText(wrapper, '删除')!.trigger('click')
    await flushPromises()

    expect(mocks.deleteUser).not.toHaveBeenCalled()
    expect(useToastStore(pinia).items.map((i) => i.text)).toContain('用户名不匹配，未删除')
    vi.unstubAllGlobals()
  })

  it('删除确认成功从列表移除', async () => {
    vi.stubGlobal('prompt', vi.fn().mockReturnValue('alice'))
    const { wrapper, pinia } = await goAccounts()

    await buttonByText(wrapper, '删除')!.trigger('click')
    await flushPromises()

    expect(mocks.deleteUser).toHaveBeenCalledWith('u1', 'alice')
    expect(useToastStore(pinia).items.map((i) => i.text)).toContain('alice 已删除')
    vi.unstubAllGlobals()
  })
})

describe('运行时配置', () => {
  it('修改模型名保存后调用接口并回显', async () => {
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()
    const navButtons = wrapper.findAll('aside button')
    await navButtons.find((b) => b.text() === '模型与 Agent')!.trigger('click')
    await flushPromises()

    const modelInput = wrapper.find('#rt-model')
    await modelInput.setValue('gpt-4o')
    await buttonByText(wrapper, '保存配置')!.trigger('click')
    await flushPromises()

    expect(mocks.setRuntime).toHaveBeenCalledWith({ llm_model: 'gpt-4o' })
    expect(useToastStore(pinia).items.map((i) => i.text)).toContain('运行配置已更新')
  })

  it('没有修改时点保存给提示不调接口', async () => {
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()
    const navButtons = wrapper.findAll('aside button')
    await navButtons.find((b) => b.text() === '模型与 Agent')!.trigger('click')
    await flushPromises()

    await buttonByText(wrapper, '保存配置')!.trigger('click')
    await flushPromises()

    expect(mocks.setRuntime).not.toHaveBeenCalled()
    expect(useToastStore(pinia).items.map((i) => i.text)).toContain('没有修改')
  })
})

describe('安全事件处置', () => {
  it('标记为已处置提交并替换行', async () => {
    const { wrapper, pinia } = mountAdmin()
    await flushPromises()
    const navButtons = wrapper.findAll('aside button')
    await navButtons.find((b) => b.text() === '安全事件')!.trigger('click')
    await flushPromises()

    await buttonByText(wrapper, '标记为已处置')!.trigger('click')
    await flushPromises()

    expect(mocks.resolveIncident).toHaveBeenCalledWith('i1')
    expect(wrapper.text()).toContain('已处置')
  })
})
