import { describe, expect, it } from 'vitest'

import router from '@/router'

/**
 * 路由形状守卫。
 *
 * AdminLayout.spec.ts 只验外壳内部长什么样，管不住「/admin 被挂回 AppLayout」这种回归——
 * 那是路由表的事。这里直接解析真实路由表，钉住后台是顶层布局、不套用户端外壳。
 */
describe('后台路由形状', () => {
  it('/admin 是顶层布局，不挂在用户端外壳下', () => {
    const resolved = router.resolve('/admin/overview')
    const paths = resolved.matched.map((record) => record.path)

    // 挂回 AppLayout 会变成 ['/', '/admin']，这条立刻挂
    expect(paths).toEqual(['/admin', '/admin/overview'])
  })

  it('/admin 的布局组件就是 AdminLayout', async () => {
    const parent = router.resolve('/admin/overview').matched[0]
    const loader = parent.components?.default as () => Promise<{ default: { __name?: string } }>
    const mod = await loader()
    // 换成 AppLayout 就会把用户端侧边栏带进后台，这条直接挂
    expect(mod.default.__name).toBe('AdminLayout')
  })

  it('每个后台面板都带 panel 标记，组件复用同一份', () => {
    const panels = ['overview', 'analytics', 'accounts', 'audit', 'incidents', 'runtime']

    for (const panel of panels) {
      const resolved = router.resolve(`/admin/${panel}`)
      expect(resolved.meta.panel).toBe(panel)
      // meta 从父路由合并下来，权限判断必须能拿到
      expect(resolved.meta.requiresAdmin).toBe(true)
      expect(resolved.meta.requiresAuth).toBe(true)
    }
  })

  it('/admin 根路径重定向到总览', () => {
    const resolved = router.resolve('/admin')
    // 父路由 path='/admin'、子路由 path='' + redirect，解析结果就是这条重定向记录
    expect(resolved.matched.map((record) => record.path)).toEqual(['/admin', '/admin'])
    expect(resolved.matched[1].redirect).toBe('/admin/overview')
  })

  it('前台根路由仍是用户端外壳，没有被后台占用', () => {
    const resolved = router.resolve('/')
    // 父 '/' + 子 path=''，两条都指向根，这是 AppLayout 套 DashboardView 的形状
    expect(resolved.matched.map((record) => record.path)).toEqual(['/', '/'])
    expect(resolved.matched[0].meta.requiresAuth).toBe(true)
    expect(resolved.matched[0].path).not.toBe('/admin')
  })
})
