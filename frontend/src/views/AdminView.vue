<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminApi } from '@/api'
import type { AccountRole, AdminUser, SecurityIncident, ServiceStatus } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const auth = useAuthStore()
const services = ref<ServiceStatus | null>(null)
const incidents = ref<SecurityIncident[]>([])
const users = ref<AdminUser[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const servicesFailed = ref(false)
const incidentsFailed = ref(false)
const usersFailed = ref(false)
const loading = ref(true)
const busyId = ref('')

const selfId = computed(() => auth.user?.id ?? null)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

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
  servicesFailed.value = false
  incidentsFailed.value = false
  usersFailed.value = false
  // 三张卡片各读各的：用 Promise.all 会让一个接口挂掉连另外两路成功的数据一起丢，
  // 管理页就整屏空白，还看不出是哪一路坏了
  const [status, list, accounts] = await Promise.allSettled([
    adminApi.services(),
    adminApi.incidents(),
    adminApi.users(page.value, pageSize),
  ])
  const failures: string[] = []
  if (status.status === 'fulfilled') services.value = status.value
  else {
    servicesFailed.value = true
    failures.push(status.reason instanceof Error ? status.reason.message : '读取服务状态失败')
  }
  if (list.status === 'fulfilled') incidents.value = list.value
  else {
    incidentsFailed.value = true
    failures.push(list.reason instanceof Error ? list.reason.message : '读取安全事件失败')
  }
  if (accounts.status === 'fulfilled') {
    users.value = accounts.value.items
    total.value = accounts.value.total
  } else {
    usersFailed.value = true
    failures.push(accounts.reason instanceof Error ? accounts.reason.message : '读取账号列表失败')
  }
  if (failures.length) toast.error(failures[0])
  loading.value = false
}

function goPage(next: number) {
  if (next < 1 || next > pageCount.value || next === page.value) return
  page.value = next
  void load()
}

async function changeRole(item: AdminUser) {
  const next: AccountRole = item.role === 'admin' ? 'user' : 'admin'
  busyId.value = item.id
  try {
    const updated = await adminApi.setRole(item.id, next)
    users.value = users.value.map((row) => (row.id === item.id ? updated : row))
    toast.success(next === 'admin' ? `${item.username} 已设为管理员` : `${item.username} 已取消管理员`)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '更新角色失败')
  } finally {
    busyId.value = ''
  }
}

async function resolve(item: SecurityIncident) {
  busyId.value = item.id
  try {
    const updated = await adminApi.resolveIncident(item.id)
    incidents.value = incidents.value.map((row) => (row.id === item.id ? updated : row))
    toast.success('事件已处置')
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '处置事件失败')
  } finally {
    busyId.value = ''
  }
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
          服务状态、账号角色与登录安全事件。管理员不查看任何人的健康档案、评估或计划。
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
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-[15px] font-semibold">账号与角色</h2>
          <span class="chip">共 {{ total }} 个账号</span>
        </div>
        <div v-if="users.length" class="mt-4 flex flex-col gap-2">
          <article
            v-for="item in users"
            :key="item.id"
            class="flex flex-wrap items-center gap-2 rounded-2xl px-4 py-3"
            :style="{ background: 'var(--color-bg-secondary)' }"
          >
            <span class="text-[13px] font-medium">{{ item.username }}</span>
            <span class="chip">{{ item.role === 'admin' ? '管理员' : '普通用户' }}</span>
            <span v-if="item.id === selfId" class="chip">当前账号</span>
            <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              {{ formatTime(item.created_at) }}
            </span>
            <button
              class="btn btn-ghost ml-auto"
              type="button"
              :disabled="item.id === selfId || busyId === item.id"
              @click="changeRole(item)"
            >
              {{ item.role === 'admin' ? '取消管理员' : '设为管理员' }}
            </button>
          </article>
          <div v-if="pageCount > 1" class="mt-2 flex items-center justify-end gap-2">
            <span class="text-[11px]" :style="{ color: 'var(--color-text-secondary)' }">
              第 {{ page }} / {{ pageCount }} 页
            </span>
            <button class="btn btn-ghost" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
            <button class="btn btn-ghost" type="button" :disabled="page >= pageCount" @click="goPage(page + 1)">
              下一页
            </button>
          </div>
        </div>
        <EmptyState
          v-else
          :title="usersFailed ? '账号列表读取失败' : '暂无账号'"
          :description="usersFailed ? '请稍后点「刷新」重试' : '注册后的账号会显示在这里'"
        />
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
              <span class="chip">{{ item.status === 'resolved' ? '已处置' : item.status }}</span>
              <span class="ml-auto text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                {{ formatTime(item.occurred_at) }}
              </span>
            </div>
            <p class="mt-2 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
              {{ item.description || '无描述' }}
            </p>
            <div class="mt-2 flex flex-wrap items-center gap-2">
              <button
                v-if="item.status === 'open'"
                class="btn btn-ghost"
                type="button"
                :disabled="busyId === item.id"
                @click="resolve(item)"
              >
                标记为已处置
              </button>
              <span v-else class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                处置时间 {{ formatTime(item.resolved_at) }}
              </span>
            </div>
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
