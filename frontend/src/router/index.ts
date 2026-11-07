import { createRouter, createWebHistory } from 'vue-router'

import { tokens } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
        { path: 'chat', name: 'chat', component: () => import('@/views/ChatView.vue') },
        { path: 'assessment', name: 'assessment', component: () => import('@/views/AssessmentView.vue') },
        { path: 'plans', name: 'plans', component: () => import('@/views/PlansView.vue') },
        { path: 'trends', name: 'trends', component: () => import('@/views/TrendsView.vue') },
        { path: 'profile', name: 'profile', component: () => import('@/views/ProfileView.vue') },
        { path: 'reminders', name: 'reminders', component: () => import('@/views/RemindersView.vue') },
        { path: 'reports/:id', name: 'report', component: () => import('@/views/ReportDetailView.vue') },
      ],
    },
    {
      // 管理后台走独立外壳 AdminLayout，不挂在 AppLayout 下：
      // 挂进去就会带出用户端侧边栏（健康首页、智能助手、待办提醒），
      // 管理员在后台看到的应该是管理菜单，而不是自己的健康入口。
      path: '/admin',
      component: () => import('@/layouts/AdminLayout.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
      children: [
        { path: '', redirect: '/admin/overview' },
        { path: 'overview', name: 'admin-overview', component: () => import('@/views/AdminView.vue'), meta: { panel: 'overview' } },
        { path: 'analytics', name: 'admin-analytics', component: () => import('@/views/AdminView.vue'), meta: { panel: 'analytics' } },
        { path: 'accounts', name: 'admin-accounts', component: () => import('@/views/AdminView.vue'), meta: { panel: 'accounts' } },
        { path: 'audit', name: 'admin-audit', component: () => import('@/views/AdminView.vue'), meta: { panel: 'audit' } },
        { path: 'incidents', name: 'admin-incidents', component: () => import('@/views/AdminView.vue'), meta: { panel: 'incidents' } },
        { path: 'runtime', name: 'admin-runtime', component: () => import('@/views/AdminView.vue'), meta: { panel: 'runtime' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.requiresAuth && !tokens.access) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && tokens.access) {
    return { name: 'dashboard' }
  }
  if (to.meta.requiresAdmin) {
    // 前端守卫只是别让普通用户白跑一趟；真正拦数据是后端 admin_user 依赖。
    // 角色取 /users/me（库里的 role），不取令牌里的 role，改权限能立即生效
    const auth = useAuthStore()
    const user = await auth.ensureUser().catch(() => null)
    if (user?.role !== 'admin') return { name: 'dashboard' }
  }
  return true
})

export default router
