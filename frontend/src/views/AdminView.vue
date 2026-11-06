<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminApi } from '@/api'
import type {
  AccountRole,
  AdminOverview,
  AdminUser,
  AgentStatus,
  AuditLog,
  RuntimeConfig,
  SecurityIncident,
  ServiceStatus,
} from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const auth = useAuthStore()

type MenuKey = 'overview' | 'accounts' | 'audit' | 'incidents' | 'runtime'

const menu: { key: MenuKey; label: string }[] = [
  { key: 'overview', label: '总览' },
  { key: 'accounts', label: '账号' },
  { key: 'audit', label: '审计' },
  { key: 'incidents', label: '安全事件' },
  { key: 'runtime', label: '模型与 Agent' },
]

const active = ref<MenuKey>('overview')

const services = ref<ServiceStatus | null>(null)
const servicesFailed = ref(false)
const overview = ref<AdminOverview | null>(null)
const overviewFailed = ref(false)
const users = ref<AdminUser[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const roleFilter = ref('')
const statusFilter = ref('')
const usersFailed = ref(false)
const audits = ref<AuditLog[]>([])
const auditTotal = ref(0)
const auditPage = ref(1)
const auditAction = ref('')
const auditFailed = ref(false)
const incidents = ref<SecurityIncident[]>([])
const incidentStatus = ref('')
const incidentSeverity = ref('')
const incidentsFailed = ref(false)
const runtime = ref<RuntimeConfig | null>(null)
const runtimeForm = ref<Partial<RuntimeConfig>>({})
const agents = ref<AgentStatus[]>([])
const workflowStats = ref<Record<string, number>>({})
const knowledge = ref<{ chunks: number }>({ chunks: 0 })
const runtimeFailed = ref(false)

const loading = ref(true)
const busyId = ref('')

const selfId = computed(() => auth.user?.id ?? null)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const auditPageCount = computed(() => Math.max(1, Math.ceil(auditTotal.value / pageSize)))

const serviceRows = computed(() => {
  const data = services.value
  if (!data) return []
  return [
    { label: '断点存储', value: data.checkpointer === 'postgres' ? 'Postgres' : '内存（开发）' },
    { label: '检索通道', value: data.embedding_backend === 'bge' ? 'BGE-M3 + Chroma' : '本地关键词' },
    { label: '模型接口', value: data.llm_configured ? `已配置（${data.llm_model}）` : '未配置（规则回答）' },
    { label: '工作流', value: data.graph_loaded ? '已加载' : '未加载' },
  ]
})

function msg(reason: unknown): string {
  return reason instanceof Error ? reason.message : '读取管理信息失败'
}

async function loadActive() {
  loading.value = true
  const results = await Promise.allSettled([
    adminApi.services(),
    adminApi.overview(),
    adminApi.users(page.value, pageSize, {
      keyword: keyword.value || undefined,
      role: roleFilter.value || undefined,
      status: statusFilter.value || undefined,
    }),
    adminApi.audits(auditPage.value, pageSize, { action: auditAction.value || undefined }),
    adminApi.incidents(20, incidentStatus.value || undefined, incidentSeverity.value || undefined),
    adminApi.runtime(),
    adminApi.agents(),
    adminApi.workflowStats(),
    adminApi.knowledge(),
  ])

  const [svc, ov, us, au, inc, rt, ag, ws, kn] = results
  const failures: string[] = []
  if (svc.status === 'fulfilled') services.value = svc.value
  else { servicesFailed.value = true; failures.push(msg(svc.reason)) }
  if (ov.status === 'fulfilled') overview.value = ov.value
  else { overviewFailed.value = true; failures.push(msg(ov.reason)) }
  if (us.status === 'fulfilled') { users.value = us.value.items; total.value = us.value.total }
  else { usersFailed.value = true; failures.push(msg(us.reason)) }
  if (au.status === 'fulfilled') { audits.value = au.value.items; auditTotal.value = au.value.total }
  else { auditFailed.value = true; failures.push(msg(au.reason)) }
  if (inc.status === 'fulfilled') incidents.value = inc.value
  else { incidentsFailed.value = true; failures.push(msg(inc.reason)) }
  if (rt.status === 'fulfilled') { runtime.value = rt.value; runtimeForm.value = { ...rt.value } }
  else { runtimeFailed.value = true; failures.push(msg(rt.reason)) }
  if (ag.status === 'fulfilled') agents.value = ag.value
  if (ws.status === 'fulfilled') workflowStats.value = ws.value
  if (kn.status === 'fulfilled') knowledge.value = kn.value
  if (failures.length) toast.error(failures[0])
  loading.value = false
}

function switchMenu(key: MenuKey) {
  if (active.value === key) return
  active.value = key
}

function goPage(next: number) {
  if (next < 1 || next > pageCount.value || next === page.value) return
  page.value = next
  void loadActive()
}

function goAuditPage(next: number) {
  if (next < 1 || next > auditPageCount.value || next === auditPage.value) return
  auditPage.value = next
  void loadActive()
}

function applyFilters() {
  page.value = 1
  auditPage.value = 1
  void loadActive()
}

async function changeRole(item: AdminUser) {
  const next: AccountRole = item.role === 'admin' ? 'user' : 'admin'
  if (!window.confirm(`确认把 ${item.username} 改为${next === 'admin' ? '管理员' : '普通用户'}？`)) return
  busyId.value = item.id
  try {
    const updated = await adminApi.setRole(item.id, next)
    users.value = users.value.map((row) => (row.id === item.id ? updated : row))
    toast.success(next === 'admin' ? `${item.username} 已设为管理员` : `${item.username} 已取消管理员`)
  } catch (error) {
    toast.error(msg(error))
  } finally {
    busyId.value = ''
  }
}

async function toggleStatus(item: AdminUser) {
  const next = item.status === 'active' ? 'disabled' : 'active'
  busyId.value = item.id
  try {
    const updated = await adminApi.setStatus(item.id, next)
    users.value = users.value.map((row) => (row.id === item.id ? updated : row))
    toast.success(`${item.username} 已${next === 'active' ? '启用' : '停用'}`)
  } catch (error) {
    toast.error(msg(error))
  } finally {
    busyId.value = ''
  }
}

async function removeUser(item: AdminUser) {
  const confirmName = window.prompt(`删除账号「${item.username}」及其全部数据，不可恢复。请输入用户名确认：`)
  if (confirmName === null) return
  if (confirmName !== item.username) {
    toast.error('用户名不匹配，未删除')
    return
  }
  busyId.value = item.id
  try {
    await adminApi.deleteUser(item.id, confirmName)
    users.value = users.value.filter((row) => row.id !== item.id)
    total.value -= 1
    toast.success(`${item.username} 已删除`)
  } catch (error) {
    toast.error(msg(error))
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
    toast.error(msg(error))
  } finally {
    busyId.value = ''
  }
}

async function saveRuntime() {
  const patch: Partial<RuntimeConfig> = {}
  if (runtimeForm.value.llm_model !== runtime.value?.llm_model) patch.llm_model = runtimeForm.value.llm_model
  if (runtimeForm.value.llm_api_key !== runtime.value?.llm_api_key) patch.llm_api_key = runtimeForm.value.llm_api_key
  if (runtimeForm.value.embedding_backend !== runtime.value?.embedding_backend)
    patch.embedding_backend = runtimeForm.value.embedding_backend
  if (!Object.keys(patch).length) {
    toast.error('没有修改')
    return
  }
  try {
    const updated = await adminApi.setRuntime(patch)
    runtime.value = updated
    runtimeForm.value = { ...updated }
    toast.success('运行配置已更新')
    void loadActive()
  } catch (error) {
    toast.error(msg(error))
  }
}

onMounted(() => {
  void loadActive()
})

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
  <div class="flex flex-col gap-4 lg:flex-row lg:items-start">
    <aside class="glass card-pad flex shrink-0 flex-row flex-wrap gap-2 lg:w-[200px] lg:flex-col lg:gap-1">
      <button
        v-for="item in menu"
        :key="item.key"
        type="button"
        class="rounded-xl px-3 py-2 text-left text-[13px]"
        :class="active === item.key ? 'segment-item is-active' : ''"
        :style="active !== item.key ? { color: 'var(--color-text-secondary)' } : {}"
        @click="switchMenu(item.key)"
      >
        {{ item.label }}
      </button>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col gap-4">
      <section class="glass card-pad flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 class="text-[20px] font-semibold">管理后台</h1>
          <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
            账号、审计、安全事件与运行状态。管理员不查看任何人的健康档案、评估或计划。
          </p>
        </div>
        <button class="btn btn-ghost" type="button" :disabled="loading" @click="loadActive">刷新</button>
      </section>

      <div v-if="loading" class="glass card-pad text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">加载中</div>

      <!-- 总览 -->
      <template v-else-if="active === 'overview'">
        <section class="glass card-pad">
          <h2 class="text-[15px] font-semibold">统计总览</h2>
          <div v-if="overview" class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div
              v-for="row in [
                { label: '用户总数', value: overview.user_total },
                { label: '管理员', value: overview.admin_total },
                { label: '待处置事件', value: overview.open_incidents },
                { label: '今日登录失败', value: overview.login_fail_today },
                { label: '今日新增账号', value: overview.new_users_today },
              ]"
              :key="row.label"
              class="rounded-2xl px-4 py-3"
              :style="{ background: 'var(--color-bg-secondary)' }"
            >
              <div class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">{{ row.label }}</div>
              <div class="mt-1 text-[20px] font-semibold">{{ row.value }}</div>
            </div>
          </div>
          <EmptyState
            v-else
            :title="overviewFailed ? '总览读取失败' : '暂无数据'"
            :description="overviewFailed ? '请稍后点「刷新」重试' : ''"
          />
        </section>

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
      </template>

      <!-- 账号 -->
      <template v-else-if="active === 'accounts'">
        <section class="glass card-pad">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-[15px] font-semibold">账号与角色</h2>
            <span class="chip">共 {{ total }} 个账号</span>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <input v-model="keyword" class="field w-auto" placeholder="用户名" @keyup.enter="applyFilters" />
            <select v-model="roleFilter" class="field w-auto" @change="applyFilters">
              <option value="">全部角色</option>
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
            <select v-model="statusFilter" class="field w-auto" @change="applyFilters">
              <option value="">全部状态</option>
              <option value="active">启用</option>
              <option value="disabled">停用</option>
            </select>
            <button class="btn btn-ghost" type="button" @click="applyFilters">筛选</button>
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
              <span class="chip" :class="item.status === 'disabled' ? 'level-unknown' : 'level-low'">
                {{ item.status === 'active' ? '启用' : '停用' }}
              </span>
              <span v-if="item.id === selfId" class="chip">当前账号</span>
              <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                {{ formatTime(item.created_at) }}
              </span>
              <div class="ml-auto flex gap-2">
                <button
                  class="btn btn-ghost"
                  type="button"
                  :disabled="item.id === selfId || busyId === item.id"
                  @click="changeRole(item)"
                >
                  {{ item.role === 'admin' ? '取消管理员' : '设为管理员' }}
                </button>
                <button
                  class="btn btn-ghost"
                  type="button"
                  :disabled="item.id === selfId || busyId === item.id"
                  @click="toggleStatus(item)"
                >
                  {{ item.status === 'active' ? '停用' : '启用' }}
                </button>
                <button
                  class="btn btn-ghost"
                  type="button"
                  :disabled="item.id === selfId || busyId === item.id"
                  @click="removeUser(item)"
                >
                  删除
                </button>
              </div>
            </article>
            <div v-if="pageCount > 1" class="mt-2 flex items-center justify-end gap-2">
              <span class="text-[11px]" :style="{ color: 'var(--color-text-secondary)' }">第 {{ page }} / {{ pageCount }} 页</span>
              <button class="btn btn-ghost" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
              <button class="btn btn-ghost" type="button" :disabled="page >= pageCount" @click="goPage(page + 1)">下一页</button>
            </div>
          </div>
          <EmptyState
            v-else
            :title="usersFailed ? '账号列表读取失败' : '暂无账号'"
            :description="usersFailed ? '请稍后点「刷新」重试' : '注册后的账号会显示在这里'"
          />
        </section>
      </template>

      <!-- 审计 -->
      <template v-else-if="active === 'audit'">
        <section class="glass card-pad">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-[15px] font-semibold">审计日志</h2>
            <span class="chip">共 {{ auditTotal }} 条</span>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <input v-model="auditAction" class="field w-auto" placeholder="动作（如 login）" @keyup.enter="applyFilters" />
            <button class="btn btn-ghost" type="button" @click="applyFilters">筛选</button>
          </div>
          <div v-if="audits.length" class="mt-4 flex flex-col gap-2">
            <article
              v-for="item in audits"
              :key="item.id"
              class="rounded-2xl px-4 py-3"
              :style="{ background: 'var(--color-bg-secondary)' }"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-[13px] font-medium">{{ item.action }}</span>
                <span class="chip">{{ item.result }}</span>
                <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                  {{ item.resource_type }} / {{ item.resource_id }}
                </span>
                <span class="ml-auto text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                  {{ formatTime(item.created_at) }}
                </span>
              </div>
            </article>
            <div v-if="auditPageCount > 1" class="mt-2 flex items-center justify-end gap-2">
              <span class="text-[11px]" :style="{ color: 'var(--color-text-secondary)' }">第 {{ auditPage }} / {{ auditPageCount }} 页</span>
              <button class="btn btn-ghost" type="button" :disabled="auditPage <= 1" @click="goAuditPage(auditPage - 1)">上一页</button>
              <button class="btn btn-ghost" type="button" :disabled="auditPage >= auditPageCount" @click="goAuditPage(auditPage + 1)">下一页</button>
            </div>
          </div>
          <EmptyState
            v-else
            :title="auditFailed ? '审计读取失败' : '暂无审计'"
            :description="auditFailed ? '请稍后点「刷新」重试' : '操作留痕会显示在这里'"
          />
        </section>
      </template>

      <!-- 安全事件 -->
      <template v-else-if="active === 'incidents'">
        <section class="glass card-pad">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-[15px] font-semibold">安全事件</h2>
            <span class="chip">最近 {{ incidents.length }} 条</span>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <select v-model="incidentStatus" class="field w-auto" @change="applyFilters">
              <option value="">全部状态</option>
              <option value="open">未处置</option>
              <option value="resolved">已处置</option>
            </select>
            <select v-model="incidentSeverity" class="field w-auto" @change="applyFilters">
              <option value="">全部级别</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="critical">严重</option>
            </select>
            <button class="btn btn-ghost" type="button" @click="applyFilters">筛选</button>
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

      <!-- 模型与 Agent -->
      <template v-else-if="active === 'runtime'">
        <section class="glass card-pad">
          <h2 class="text-[15px] font-semibold">模型参数</h2>
          <div v-if="runtime" class="mt-4 flex flex-col gap-3">
            <div>
              <label class="label" for="rt-model">模型名</label>
              <input id="rt-model" v-model="runtimeForm.llm_model" class="field" />
            </div>
            <div>
              <label class="label" for="rt-key">模型密钥（明文回显，修改请谨慎）</label>
              <input id="rt-key" v-model="runtimeForm.llm_api_key" class="field" type="text" />
            </div>
            <div>
              <label class="label" for="rt-embed">检索通道</label>
              <select id="rt-embed" v-model="runtimeForm.embedding_backend" class="field">
                <option value="keyword">本地关键词</option>
                <option value="bge">BGE-M3 + Chroma</option>
              </select>
            </div>
            <button class="btn btn-primary w-full" type="button" @click="saveRuntime">保存配置</button>
          </div>
          <EmptyState v-else :title="runtimeFailed ? '配置读取失败' : '暂无配置'" :description="runtimeFailed ? '请稍后点「刷新」重试' : ''" />
        </section>

        <section class="glass card-pad">
          <h2 class="text-[15px] font-semibold">Agent 清单</h2>
          <div v-if="agents.length" class="mt-4 grid gap-2 sm:grid-cols-2">
            <div
              v-for="item in agents"
              :key="item.name"
              class="flex items-center justify-between rounded-2xl px-4 py-2"
              :style="{ background: 'var(--color-bg-secondary)' }"
            >
              <span class="text-[13px]">{{ item.name }}</span>
              <span class="chip" :class="item.loaded ? 'level-low' : 'level-unknown'">{{ item.loaded ? '已加载' : '未加载' }}</span>
            </div>
          </div>
        </section>

        <section class="glass card-pad">
          <h2 class="text-[15px] font-semibold">工作流运行统计</h2>
          <div v-if="Object.keys(workflowStats).length" class="mt-4 grid gap-2 sm:grid-cols-3">
            <div
              v-for="(value, key) in workflowStats"
              :key="key"
              class="rounded-2xl px-4 py-2"
              :style="{ background: 'var(--color-bg-secondary)' }"
            >
              <span class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">{{ key }}</span>
              <span class="ml-2 text-[13px] font-medium">{{ value }}</span>
            </div>
          </div>
          <div class="mt-4 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
            知识库 chunk 数：{{ knowledge.chunks }}
          </div>
        </section>
      </template>
    </div>
  </div>
</template>
