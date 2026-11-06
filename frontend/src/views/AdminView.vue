<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminApi } from '@/api'
import type { SecurityIncident, ServiceStatus } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const services = ref<ServiceStatus | null>(null)
const incidents = ref<SecurityIncident[]>([])
const incidentsFailed = ref(false)
const loading = ref(true)

const serviceRows = computed(() => {
  const data = services.value
  if (!data) return []
  return [
    { label: '断点存储', value: data.checkpointer === 'postgres' ? 'Postgres' : '内存（开发）' },
    { label: '检索通道', value: data.embedding_backend === 'bge' ? 'BGE-M3 + Chroma' : '本地关键词' },
    { label: '模型接口', value: data.llm_configured ? '已配置' : '未配置（规则回答）' },
    { label: '工作流', value: data.graph_loaded ? '已加载' : '未加载' },
  ]
})

async function load() {
  loading.value = true
  incidentsFailed.value = false
  // 两张卡片各读各的：用 Promise.all 会让一个接口挂掉连另一路成功的数据一起丢，
  // 管理页就整屏空白，还看不出是哪一路坏了
  const [status, list] = await Promise.allSettled([adminApi.services(), adminApi.incidents()])
  let failure: unknown = null
  if (status.status === 'fulfilled') services.value = status.value
  else failure = status.reason
  if (list.status === 'fulfilled') incidents.value = list.value
  else {
    incidentsFailed.value = true
    failure ??= list.reason
  }
  if (failure !== null) {
    toast.error(failure instanceof Error ? failure.message : '读取管理信息失败')
  }
  loading.value = false
}

onMounted(load)

function formatTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
}

function severityClass(value: string | null): string {
  if (value === 'high' || value === 'critical') return 'level-high'
  if (value === 'medium' || value === 'warning') return 'level-mid'
  if (value === 'low') return 'level-low'
  return 'level-unknown'
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="glass card-pad flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 class="text-[20px] font-semibold">管理后台</h1>
        <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
          服务运行状态与登录安全事件。管理员不查看任何人的健康档案、评估或计划。
        </p>
      </div>
      <button class="btn btn-ghost" type="button" :disabled="loading" @click="load">刷新</button>
    </section>

    <div v-if="loading" class="glass card-pad text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">加载中</div>

    <template v-else>
      <section class="glass card-pad">
        <h2 class="text-[15px] font-semibold">服务状态</h2>
        <div v-if="serviceRows.length" class="mt-4 grid gap-3 sm:grid-cols-2">
          <div
            v-for="row in serviceRows"
            :key="row.label"
            class="flex items-center justify-between rounded-2xl px-4 py-3"
            :style="{ background: 'var(--color-bg-secondary)' }"
          >
            <span class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">{{ row.label }}</span>
            <span class="text-[13px] font-medium">{{ row.value }}</span>
          </div>
        </div>
        <EmptyState v-else title="服务状态读取失败" description="请稍后点「刷新」重试" />
      </section>

      <section class="glass card-pad">
        <div class="flex items-center justify-between">
          <h2 class="text-[15px] font-semibold">安全事件</h2>
          <span class="chip">最近 {{ incidents.length }} 条</span>
        </div>
        <div v-if="incidents.length" class="mt-4 flex flex-col gap-2">
          <article
            v-for="item in incidents"
            :key="item.id"
            class="rounded-2xl px-4 py-3"
            :style="{ background: 'var(--color-bg-secondary)' }"
          >
            <div class="flex flex-wrap items-center gap-2">
              <span class="chip" :class="severityClass(item.severity)">{{ item.severity || '未分级' }}</span>
              <span class="text-[13px] font-medium">{{ item.incident_type }}</span>
              <span class="chip">{{ item.status }}</span>
              <span class="ml-auto text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                {{ formatTime(item.occurred_at) }}
              </span>
            </div>
            <p class="mt-2 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
              {{ item.description || '无描述' }}
            </p>
          </article>
        </div>
        <EmptyState
          v-else
          :title="incidentsFailed ? '安全事件读取失败' : '暂无安全事件'"
          :description="incidentsFailed ? '请稍后点「刷新」重试' : '连续登录失败达到阈值时会在这里留一条记录'"
        />
      </section>
    </template>
  </div>
</template>
