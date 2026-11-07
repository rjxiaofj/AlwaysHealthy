import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'

import AdminLayout from '@/layouts/AdminLayout.vue'

/**
 * 管理后台外壳的核心约束：侧边栏只放管理菜单。
 * 之前 /admin 挂在 AppLayout 下面，进后台就会看到健康首页、智能助手、待办提醒，
 * 这些是用户端入口，管理员在后台不该看到。这里把这条约束钉死。
 */
const EMPTY = { template: '<div />' }

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: EMPTY },
      {
        path: '/admin',
        component: EMPTY,
        children: [
          { path: 'overview', component: EMPTY },
          { path: 'analytics', component: EMPTY },
          { path: 'accounts', component: EMPTY },
          { path: 'audit', component: EMPTY },
          { path: 'incidents', component: EMPTY },
          { path: 'runtime', component: EMPTY },
        ],
      },
      { path: '/login', component: EMPTY },
    ],
  })
}

async function mountLayout(path = '/admin/overview') {
  const pinia = createPinia()
  const router = buildRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(AdminLayout, {
    global: { plugins: [pinia, router], stubs: { RouterView: true } },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('管理后台外壳', () => {
  it('侧边栏只有管理菜单，没有用户端入口', async () => {
    const { wrapper } = await mountLayout()
    const labels = wrapper.findAll('aside nav a').map((link) => link.text())

    expect(labels).toEqual(['总览', '数据看板', '账号', '审计', '安全事件', '模型与 Agent'])

    const text = wrapper.text()
    for (const userEntry of ['健康首页', '智能助手', '健康评估', '健康管理', '指标趋势', '个人中心', '待办提醒']) {
      expect(text).not.toContain(userEntry)
    }
  })

  it('点菜单改路由，当前项高亮', async () => {
    const { wrapper, router } = await mountLayout()

    const analyticsLink = wrapper.findAll('aside nav a').find((link) => link.text() === '数据看板')!
    await analyticsLink.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/admin/analytics')
    expect(analyticsLink.classes()).toContain('is-active')
  })

  it('顶栏标题跟着当前路由', async () => {
    const { wrapper } = await mountLayout('/admin/incidents')
    expect(wrapper.text()).toContain('管理后台 · 安全事件')
  })

  it('退出登录清会话并回登录页', async () => {
    const { wrapper, router } = await mountLayout()
    const logoutButton = wrapper.find('aside button[aria-label="退出登录"]')
    await logoutButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('提供返回前台入口', async () => {
    const { wrapper } = await mountLayout()
    const homeLink = wrapper.find('aside a[aria-label="返回前台"]')
    expect(homeLink.attributes('href')).toBe('/')
  })
})
