import { createRouter, createWebHistory } from 'vue-router'

import { tokens } from '@/api/client'

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
        { path: 'reports/:id', name: 'report', component: () => import('@/views/ReportDetailView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !tokens.access) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && tokens.access) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
