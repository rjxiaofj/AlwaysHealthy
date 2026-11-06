import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import LoginView from '@/views/LoginView.vue'

/**
 * 登录页身份选项卡：两个通道的文案、请求参数、跳转与错误提示都要跟着身份走。
 * 切换身份不能把上一个通道的密码/错误/注册态带过去。
 */
const mocks = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  me: vi.fn(),
}))

vi.mock('@/api', () => ({
  authApi: {
    login: mocks.login,
    register: mocks.register,
    me: mocks.me,
    logout: vi.fn(),
  },
}))

const token = (role: string) => ({
  access_token: `access-${role}`,
  refresh_token: `refresh-${role}`,
  expires_in: 1800,
  user_id: 'u1',
  username: 'tester',
  role,
})

const profile = (role: string) => ({
  id: 'u1',
  username: 'tester',
  email: null,
  role,
  status: 'active',
  created_at: '2026-11-06T00:00:00Z',
  last_login_at: null,
})

async function mountLogin() {
  const pinia = createPinia()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/login', component: { template: '<div />' } },
      { path: '/admin', component: { template: '<div />' } },
    ],
  })
  await router.push('/login')
  await router.isReady()
  const wrapper = mount(LoginView, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router, pinia }
}

type Wrapper = Awaited<ReturnType<typeof mountLogin>>['wrapper']

async function fill(wrapper: Wrapper) {
  await wrapper.find('#username').setValue('tester')
  await wrapper.find('#password').setValue('demo12345')
}

function tabAt(wrapper: Wrapper, index: number) {
  return wrapper.findAll('[role="tab"]')[index]
}

function buttonWith(wrapper: Wrapper, text: string) {
  const found = wrapper.findAll('button').find((item) => item.text().includes(text))
  if (!found) throw new Error(`找不到按钮：${text}`)
  return found
}

beforeEach(() => {
  let currentRole = 'user'
  mocks.login.mockReset().mockImplementation(async (_u: string, _p: string, role?: string) => {
    currentRole = role ?? 'user'
    return token(currentRole)
  })
  mocks.register.mockReset().mockImplementation(async (_u: string, _p: string, role?: string) => {
    currentRole = role ?? 'user'
    return token(currentRole)
  })
  mocks.me.mockReset().mockImplementation(async () => profile(currentRole))
  localStorage.clear()
})

describe('登录页身份选项卡', () => {
  it('默认停在用户登录，两个选项卡都在', async () => {
    const { wrapper } = await mountLogin()
    const tabs = wrapper.findAll('[role="tab"]')

    expect(tabs.map((item) => item.text())).toEqual(['用户登录', '管理员登录'])
    expect(tabs[0].attributes('aria-selected')).toBe('true')
    expect(tabs[1].attributes('aria-selected')).toBe('false')
    expect(wrapper.text()).toContain('没有账号，去注册')
  })

  it('切到管理员登录后标题、按钮与底部提示一起变', async () => {
    const { wrapper } = await mountLogin()
    await tabAt(wrapper, 1).trigger('click')

    expect(tabAt(wrapper, 1).attributes('aria-selected')).toBe('true')
    expect(wrapper.text()).toContain('管理员登录')
    expect(wrapper.text()).toContain('进入管理后台')
    expect(wrapper.text()).toContain('没有管理员账号？管理员注册')
  })

  it('切回用户登录能恢复普通注册提示', async () => {
    const { wrapper } = await mountLogin()
    await tabAt(wrapper, 1).trigger('click')
    await tabAt(wrapper, 0).trigger('click')

    expect(wrapper.text()).toContain('没有账号，去注册')
    expect(wrapper.text()).not.toContain('管理员注册')
    expect(wrapper.text()).toContain('登录')
  })

  it('切换身份清掉密码与错误提示，但保留用户名', async () => {
    mocks.login.mockRejectedValueOnce(new ApiError('X', '登录失败', 400))
    const { wrapper } = await mountLogin()
    await fill(wrapper)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('登录失败')

    await tabAt(wrapper, 1).trigger('click')

    expect((wrapper.find('#username').element as HTMLInputElement).value).toBe('tester')
    expect((wrapper.find('#password').element as HTMLInputElement).value).toBe('')
    expect(wrapper.text()).not.toContain('登录失败')
  })

  it('用户登录走 user 通道并回到首页', async () => {
    const { wrapper, router } = await mountLogin()
    await fill(wrapper)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mocks.login).toHaveBeenCalledWith('tester', 'demo12345', 'user')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('管理员登录走 admin 通道并进管理页', async () => {
    const { wrapper, router } = await mountLogin()
    await tabAt(wrapper, 1).trigger('click')
    await fill(wrapper)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mocks.login).toHaveBeenCalledWith('tester', 'demo12345', 'admin')
    expect(router.currentRoute.value.path).toBe('/admin')
  })

  it('管理员注册带邀请码提交，成功后进管理页', async () => {
    const { wrapper, router } = await mountLogin()
    await tabAt(wrapper, 1).trigger('click')
    await buttonWith(wrapper, '管理员注册').trigger('click')
    expect(wrapper.find('#admin-code').exists()).toBe(true)

    await fill(wrapper)
    await wrapper.find('#admin-code').setValue('secret-code')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mocks.register).toHaveBeenCalledWith('tester', 'demo12345', 'admin', 'secret-code')
    expect(router.currentRoute.value.path).toBe('/admin')
  })

  it('管理员注册不填邀请码时先拦在前端', async () => {
    const { wrapper } = await mountLogin()
    await tabAt(wrapper, 1).trigger('click')
    await buttonWith(wrapper, '管理员注册').trigger('click')
    await fill(wrapper)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请填写管理员邀请码')
    expect(mocks.register).not.toHaveBeenCalled()
  })

  it('普通用户注册不出现邀请码输入框', async () => {
    const { wrapper } = await mountLogin()
    await buttonWith(wrapper, '没有账号').trigger('click')

    expect(wrapper.find('#admin-code').exists()).toBe(false)
  })

  it('切换身份把注册态收回登录态，不残留邀请码表单', async () => {
    const { wrapper } = await mountLogin()
    await buttonWith(wrapper, '没有账号').trigger('click')
    expect(wrapper.text()).toContain('注册新账号')

    await tabAt(wrapper, 1).trigger('click')

    expect(wrapper.find('#admin-code').exists()).toBe(false)
    expect(wrapper.text()).toContain('进入管理后台')
  })

  it('后端拒绝普通账号冒充管理员时显示后端文案且留在登录页', async () => {
    mocks.login.mockRejectedValueOnce(
      new ApiError('RESOURCE_FORBIDDEN', '该账号不是管理员，请切换为「用户登录」', 403),
    )
    const { wrapper, router } = await mountLogin()
    await tabAt(wrapper, 1).trigger('click')
    await fill(wrapper)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('该账号不是管理员，请切换为「用户登录」')
    expect(router.currentRoute.value.path).toBe('/login')
  })
})
