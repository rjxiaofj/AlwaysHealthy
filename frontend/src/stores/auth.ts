import { defineStore } from 'pinia'
import { ref } from 'vue'

import { authApi } from '@/api'
import { tokens } from '@/api/client'
import type { UserInfo } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const pending = ref(false)

  async function login(username: string, password: string) {
    pending.value = true
    try {
      const payload = await authApi.login(username, password)
      tokens.save(payload)
      user.value = await authApi.me()
    } finally {
      pending.value = false
    }
  }

  async function register(username: string, password: string) {
    pending.value = true
    try {
      const payload = await authApi.register(username, password)
      tokens.save(payload)
      user.value = await authApi.me()
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

  return { user, pending, login, register, ensureUser, logout }
})
