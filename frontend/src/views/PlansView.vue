<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { planApi } from '@/api'
import type { Plan, PlanSummary, Task } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const plans = ref<PlanSummary[]>([])
const selected = ref<Plan | null>(null)
const loading = ref(true)
const busy = ref(false)
const duration = ref(14)
const goal = ref('')
const adjustReason = ref('')
const feedbackTask = ref('')
const feedbackText = ref('')

const today = new Date().toISOString().slice(0, 10)

const grouped = computed(() => {
  if (!selected.value) return []
  const map = new Map<string, Task[]>()
  selected.value.tasks.forEach((task) => {
    const list = map.get(task.scheduled_date) || []
    list.push(task)
    map.set(task.scheduled_date, list)
  })
  return Array.from(map.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, tasks]) => ({ date, tasks }))
})

const activeVersion = computed(() => {
  if (!selected.value) return null
  return selected.value.versions.find((item) => item.id === selected.value?.current_version_id) || null
})

const canApprove = computed(() => selected.value?.status === 'pending_review' && activeVersion.value?.status === 'draft')

async function load(preferId?: string) {
  loading.value = true
  try {
    plans.value = await planApi.list()
    const target = preferId || selected.value?.id || plans.value[0]?.id
    selected.value = target ? await planApi.detail(target) : null
  } finally {
    loading.value = false
  }
}

async function generate() {
  busy.value = true
  try {
    const plan = await planApi.generate(duration.value, goal.value || undefined)
    toast.success('计划草稿已生成，确认后生效')
    await load(plan.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '生成失败')
  } finally {
    busy.value = false
  }
}

async function approve() {
  if (!selected.value || !selected.value.current_version_id) return
  busy.value = true
  try {
    selected.value = await planApi.approve(selected.value.id, selected.value.current_version_id)
    toast.success('计划已生效')
    await load(selected.value.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '确认失败')
  } finally {
    busy.value = false
  }
}

async function adjust() {
  if (!selected.value || adjustReason.value.trim().length < 2) {
    toast.error('填写调整原因')
    return
  }
  busy.value = true
  try {
    await planApi.adjust(selected.value.id, adjustReason.value.trim())
    adjustReason.value = ''
    toast.success('已生成新版本草稿')
    await load(selected.value.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '调整失败')
  } finally {
    busy.value = false
  }
}

async function cancelPlan() {
  if (!selected.value) return
  busy.value = true
  try {
    await planApi.cancel(selected.value.id)
    toast.success('计划已取消')
    await load(selected.value.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '取消失败')
  } finally {
    busy.value = false
  }
}

function openFeedback(task: Task) {
  feedbackTask.value = feedbackTask.value === task.id ? '' : task.id
  feedbackText.value = ''
}

async function checkin(task: Task, status: 'completed' | 'partial' | 'skipped') {
  busy.value = true
  try {
    const feedback = feedbackTask.value === task.id ? feedbackText.value : undefined
    await planApi.checkin(task.id, status, feedback)
    feedbackTask.value = ''
    await load(selected.value?.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '打卡失败')
  } finally {
    busy.value = false
  }
}

onMounted(() => load())
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="glass card-pad">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 class="text-[20px] font-semibold">健康管理</h1>
          <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
            计划周期 7 到 30 天，未确认的版本不会生效，旧版本保留
          </p>
        </div>
        <div class="flex flex-wrap items-end gap-2">
          <div>
            <label class="label" for="duration">周期天数</label>
            <input id="duration" v-model.number="duration" class="field w-[110px]" type="number" min="7" max="30" />
          </div>
          <div>
            <label class="label" for="goal">阶段目标</label>
            <input id="goal" v-model="goal" class="field w-[200px]" placeholder="可留空" />
          </div>
          <button class="btn btn-primary" :disabled="busy" @click="generate">生成计划草稿</button>
        </div>
      </div>
    </section>

    <div class="grid gap-4 xl:grid-cols-[240px_1fr]">
      <aside class="glass p-3">
        <p class="px-2 pb-2 text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">计划列表</p>
        <EmptyState v-if="!plans.length" title="暂无计划" />
        <button
          v-for="item in plans"
          :key="item.id"
          class="mb-1 w-full rounded-[14px] px-3 py-2 text-left text-[12px]"
          :style="{
            background: item.id === selected?.id ? 'rgba(23,25,29,0.06)' : 'transparent',
          }"
          @click="load(item.id)"
        >
          <p class="truncate font-medium">{{ item.title }}</p>
          <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            {{ item.start_date }} 至 {{ item.end_date }}
          </p>
          <span class="chip mt-1">{{ item.status }}</span>
        </button>
      </aside>

      <section v-if="selected" class="flex flex-col gap-4">
        <div class="glass card-pad">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 class="text-[16px] font-semibold">{{ selected.title }}</h2>
              <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
                {{ selected.start_date }} 至 {{ selected.end_date }}，共 {{ selected.duration_days }} 天
              </p>
            </div>
            <div class="flex flex-wrap gap-2">
              <button v-if="canApprove" class="btn btn-primary" :disabled="busy" @click="approve">确认启用</button>
              <button class="btn btn-ghost" :disabled="busy" @click="cancelPlan">取消计划</button>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap items-end gap-2">
            <div class="min-w-[220px] flex-1">
              <label class="label" for="reason">调整原因</label>
              <input id="reason" v-model="adjustReason" class="field" placeholder="例如：任务太多，想减少到每天两项" />
            </div>
            <button class="btn btn-ghost" :disabled="busy" @click="adjust">生成调整版本</button>
          </div>

          <div class="mt-4">
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">版本记录</p>
            <ul class="mt-1 flex flex-col gap-1">
              <li v-for="version in selected.versions" :key="version.id" class="text-[12px]">
                v{{ version.version_no }} · {{ version.status }}
                <span v-if="version.change_reason" :style="{ color: 'var(--color-text-tertiary)' }"> · {{ version.change_reason }}</span>
              </li>
            </ul>
          </div>
        </div>

        <div class="glass card-pad">
          <h2 class="mb-3 text-[14px] font-semibold">每日任务</h2>
          <EmptyState v-if="!grouped.length" title="计划没有任务" />
          <div v-else class="flex flex-col gap-4">
            <div v-for="group in grouped" :key="group.date">
              <p class="mb-2 text-[12px] font-medium" :style="{ color: group.date === today ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }">
                {{ group.date }}{{ group.date === today ? ' 今天' : '' }}
              </p>
              <div class="flex flex-col gap-2">
                <div
                  v-for="task in group.tasks"
                  :key="task.id"
                  class="rounded-[16px] border p-3"
                  :style="{ borderColor: 'var(--color-border)' }"
                >
                  <div class="flex flex-wrap items-start justify-between gap-2">
                    <div class="min-w-0">
                      <p class="text-[13px] font-medium">{{ task.title }}</p>
                      <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                        {{ task.scheduled_time || '任意时间' }} · {{ task.completion_criteria }}
                      </p>
                      <p v-if="task.description" class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
                        {{ task.description }}
                      </p>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="chip" :class="task.checkin_status === 'completed' ? 'level-low' : 'level-unknown'">
                        {{ task.checkin_status === 'completed' ? '已完成' : task.checkin_status === 'partial' ? '部分完成' : '待完成' }}
                      </span>
                      <button class="btn btn-ghost !px-2 !py-1 text-[11px]" @click="openFeedback(task)">未完成原因</button>
                      <button class="btn btn-primary !px-3 !py-1 text-[11px]" :disabled="busy" @click="checkin(task, 'completed')">完成</button>
                      <button class="btn btn-ghost !px-3 !py-1 text-[11px]" :disabled="busy" @click="checkin(task, 'skipped')">跳过</button>
                    </div>
                  </div>
                  <div v-if="feedbackTask === task.id" class="mt-2">
                    <textarea v-model="feedbackText" class="field h-16 resize-none" placeholder="填写执行困难或原因，不会据此判断健康变差" />
                    <button class="btn btn-ghost mt-2 !py-1 text-[11px]" :disabled="busy" @click="checkin(task, 'partial')">提交部分完成</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-else class="glass card-pad">
        <EmptyState title="还没有计划" description="先完成一次评估，再按周期生成计划草稿" action="去评估" @action="$router.push('/assessment')" />
      </section>
    </div>
  </div>
</template>
