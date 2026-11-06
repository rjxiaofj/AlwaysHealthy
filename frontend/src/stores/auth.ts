import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi } from '@/api'
import { tokens } from '@/api/client'
import type { AccountRole, UserInfo } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const pending = ref(false)
  // 以 /users/me 的 role 为准，不看令牌里的 role：库里改权限能立即生效
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username: string, password: string, expectedRole?: AccountRole): Promise<UserInfo> {
    pending.value = true
    try {
      const payload = await authApi.login(username, password, expectedRole)
      tokens.save(payload)
      user.value = await authApi.me()
      return user.value
    } finally {
      pending.value = false
    }
  }

  async function register(
    username: string,
    password: string,
    role: AccountRole = 'user',
    adminCode?: string,
  ): Promise<UserInfo> {
    pending.value = true
    try {
      const payload = await authApi.register(username, password, role, adminCode)
      tokens.save(payload)
      user.value = await authApi.me()
      return user.value
    } finally {
      pending.value = false
    }
  }

  async function ensureUser() {
    if (!tokens.access) return null
    if (user.value) return user.value
    user.value = await authApi.me()
    return user.value
  }

  async function logout() {
    const refresh = tokens.refresh
    try {
      if (refresh) await authApi.logout(refresh)
    } finally {
      tokens.clear()
      user.value = null
    }
  }

  return { user, pending, isAdmin, login, register, ensureUser, logout }
})
