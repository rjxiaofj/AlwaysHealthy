import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { reminderApi } from '@/api'
import type { Reminder } from '@/api/types'

let inflight: Promise<void> | null = null

export const useReminderStore = defineStore('reminders', () => {
  const items = ref<Reminder[]>([])
  const loading = ref(false)

  // 顶部未读数、首页未读列表、提醒中心都读这一份，标已读后不用等下次进页面才同步
  const unread = computed(() => items.value.filter((item) => !item.read_at).length)

  async function load() {
    // 布局与页面会同时进首页，两个并行的 /reminders 会各自去生成同一批提醒，撞唯一键
    if (inflight) return inflight
    inflight = (async () => {
      loading.value = true
      try {
        items.value = await reminderApi.list()
      } finally {
        loading.value = false
      }
    })().finally(() => {
      inflight = null
    })
    return inflight
  }

  async function read(id: string) {
    await reminderApi.read(id)
    const row = items.value.find((item) => item.id === id)
    if (row) row.read_at = new Date().toISOString()
  }

  return { items, loading, unread, load, read }
})
