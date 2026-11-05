<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import EmptyState from '@/components/EmptyState.vue'
import { useReminderStore } from '@/stores/reminders'
import { useToastStore } from '@/stores/toast'

const store = useReminderStore()
const toast = useToastStore()
const filter = ref<'unread' | 'all'>('unread')
const busy = ref('')

const typeLabels: Record<string, string> = {
  task_due: '今日任务',
  task_overdue: '未记录任务',
  plan_end: '周期收尾',
}

const shown = computed(() => (filter.value === 'unread' ? store.items.filter((item) => !item.read_at) : store.items))

function formatTime(value: string) {
  return new Date(value).toLocaleString('zh-CN')
}

async function markRead(id: string) {
  busy.value = id
  try {
    await store.read(id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '标记失败')
  } finally {
    busy.value = ''
  }
}

onMounted(() => store.load().catch(() => toast.error('提醒加载失败')))
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="glass card-pad">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 class="text-[20px] font-semibold">提醒中心</h1>
          <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
            提醒在你访问页面时按需生成，平台不会在后台推送通知。已读记录保留在这里。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button class="chip" :class="filter === 'unread' ? 'level-low' : ''" @click="filter = 'unread'">
            未读 {{ store.unread }}
          </button>
          <button class="chip" :class="filter === 'all' ? 'level-low' : ''" @click="filter = 'all'">
            全部 {{ store.items.length }}
          </button>
        </div>
      </div>
    </section>

    <section class="glass card-pad">
      <EmptyState v-if="!shown.length" :title="filter === 'unread' ? '没有未读提醒' : '还没有提醒'" />
      <ul v-else class="flex flex-col gap-2">
        <li
          v-for="item in shown"
          :key="item.id"
          class="flex flex-wrap items-start justify-between gap-3 rounded-[16px] border px-3 py-3"
          :style="{ borderColor: 'var(--color-border)' }"
        >
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="chip" :class="item.read_at ? '' : 'level-unknown'">
                {{ typeLabels[item.notification_type] || item.notification_type }}
              </span>
              <span class="text-[13px] font-medium">{{ item.title }}</span>
              <span v-if="!item.read_at" class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">未读</span>
            </div>
            <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">{{ item.content }}</p>
            <p class="mt-1 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">{{ formatTime(item.created_at) }}</p>
          </div>
          <button
            v-if="!item.read_at"
            class="btn btn-ghost !px-3 !py-1 text-[11px]"
            :disabled="busy === item.id"
            @click="markRead(item.id)"
          >
            标为已读
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>
