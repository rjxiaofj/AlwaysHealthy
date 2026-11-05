<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { assessmentApi, planApi, trackingApi } from '@/api'
import type { Plan, PlanSummary, Task, TrackingSummary } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const router = useRouter()
const plans = ref<PlanSummary[]>([])
const selected = ref<Plan | null>(null)
const summary = ref<TrackingSummary | null>(null)
const loading = ref(true)
const busy = ref(false)
const duration = ref(14)
const goal = ref('')
const adjustReason = ref('')
const shiftStart = ref('')
const shiftReason = ref('')
const feedbackTask = ref('')
const feedbackText = ref('')
const rescheduleTask = ref('')
const rescheduleDate = ref('')
const editTime = ref('')
const editReminder = ref(true)
const reassessReason = ref('')
const reassessing = ref(false)

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

// 打卡只允许 active 计划的当前版本任务，已结束或未生效的计划不该再露出打卡按钮
const canCheckin = computed(() => selected.value?.status === 'active')

const canCancel = computed(() => ['active', 'pending_review'].includes(selected.value?.status || ''))

const canShift = computed(() => {
  const plan = selected.value
  if (!plan) return false
  if (!['active', 'pending_review'].includes(plan.status)) return false
  // 后端按版本统计打卡记录，前端只能按当前版本任务的打卡状态粗判，最终拦截以接口为准
  if (plan.start_date < today) return false
  return !plan.tasks.some((task) => ['completed', 'partial', 'skipped'].includes(task.checkin_status || ''))
})

const daysLeft = computed(() => {
  const plan = selected.value
  if (!plan) return 0
  const end = new Date(`${plan.end_date}T00:00:00`).getTime()
  const now = new Date(`${today}T00:00:00`).getTime()
  return Math.round((end - now) / 86400000)
})

// 周期结束或只剩两天时给重新评估入口，平台不自动发起，也不自动生成下一周期计划
const canReassess = computed(() => {
  const plan = selected.value
  if (!plan) return false
  if (plan.status === 'completed') return true
  return plan.status === 'active' && daysLeft.value <= 2
})

async function load(preferId?: string) {
  loading.value = true
  try {
    plans.value = await planApi.list()
    const target = preferId || selected.value?.id || plans.value[0]?.id
    selected.value = target ? await planApi.detail(target) : null
    shiftStart.value = selected.value?.start_date || ''
    shiftReason.value = ''
    await loadSummary()
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  const plan = selected.value
  // 草稿计划还没有打卡记录，取总结只会得到全零，不展示
  if (!plan || !['active', 'completed'].includes(plan.status)) {
    summary.value = null
    return
  }
  summary.value = await trackingApi.summary(plan.id).catch(() => null)
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

async function shiftPlan() {
  const plan = selected.value
  if (!plan) return
  if (!shiftStart.value || shiftStart.value === plan.start_date) {
    toast.error('新的开始日期要与当前不同')
    return
  }
  busy.value = true
  try {
    selected.value = await planApi.shift(plan.id, shiftStart.value, shiftReason.value.trim() || undefined)
    toast.success('已整体改期，任务日期同步平移')
    await load(plan.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '改期失败')
  } finally {
    busy.value = false
  }
}

async function reassess() {
  if (!selected.value) return
  const reason = reassessReason.value.trim() || '计划周期结束，主动发起重新评估'
  reassessing.value = true
  try {
    await trackingApi.reassessment(reason)
    await assessmentApi.create()
    reassessReason.value = ''
    toast.success('新的评估已生成，可以按新结果生成下一周期计划')
    router.push('/assessment')
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '重新评估失败')
  } finally {
    reassessing.value = false
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

function openReschedule(task: Task) {
  rescheduleTask.value = rescheduleTask.value === task.id ? '' : task.id
  rescheduleDate.value = task.scheduled_date
  editTime.value = task.scheduled_time || ''
  editReminder.value = task.reminder_enabled
}

async function reschedule(task: Task) {
  if (!rescheduleDate.value) {
    toast.error('选择新的任务日期')
    return
  }
  const dateChanged = rescheduleDate.value !== task.scheduled_date
  const timeChanged = editTime.value && editTime.value !== (task.scheduled_time || '')
  const reminderChanged = editReminder.value !== task.reminder_enabled
  if (!dateChanged && !timeChanged && !reminderChanged) {
    toast.error('日期、时间与提醒都没有变化')
    return
  }
  busy.value = true
  try {
    await planApi.patchTask(task.id, {
      ...(dateChanged ? { scheduled_date: rescheduleDate.value } : {}),
      ...(timeChanged ? { scheduled_time: editTime.value } : {}),
      ...(reminderChanged ? { reminder_enabled: editReminder.value } : {}),
    })
    rescheduleTask.value = ''
    toast.success('任务已更新')
    await load(selected.value?.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '调整失败')
  } finally {
    busy.value = false
  }
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
            <div class="flex items-center gap-1">
              <button
                v-for="option in [7, 14]"
                :key="option"
                class="chip"
                :class="duration === option ? 'level-low' : ''"
                @click="duration = option"
              >
                {{ option }} 天
              </button>
              <input id="duration" v-model.number="duration" class="field w-[92px]" type="number" min="7" max="30" />
            </div>
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
              <button v-if="canCancel" class="btn btn-ghost" :disabled="busy" @click="cancelPlan">取消计划</button>
            </div>
          </div>

          <div v-if="canCancel" class="mt-4 flex flex-wrap items-end gap-2">
            <div class="min-w-[220px] flex-1">
              <label class="label" for="reason">调整原因</label>
              <input id="reason" v-model="adjustReason" class="field" placeholder="例如：任务太多，想减少到每天两项" />
            </div>
            <button class="btn btn-ghost" :disabled="busy" @click="adjust">生成调整版本</button>
          </div>

          <div v-if="canShift" class="mt-4 flex flex-wrap items-end gap-2">
            <div>
              <label class="label" for="shift-start">新的开始日期</label>
              <input id="shift-start" v-model="shiftStart" class="field w-[168px]" type="date" :min="today" />
            </div>
            <div class="min-w-[220px] flex-1">
              <label class="label" for="shift-reason">改期原因</label>
              <input id="shift-reason" v-model="shiftReason" class="field" placeholder="可留空，例如：下周出差，整体推迟三天" />
            </div>
            <button class="btn btn-ghost" :disabled="busy" @click="shiftPlan">整体改期</button>
            <p class="w-full text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              只平移开始与结束日期，任务内容不变；计划一旦开始或已有打卡就不能整体改期
            </p>
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

        <div v-if="summary" class="glass card-pad">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-[14px] font-semibold">周期总结</h2>
            <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              {{ summary.period_start }} 至 {{ summary.period_end }}
            </span>
          </div>
          <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div>
              <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">完成率</p>
              <p class="text-[18px] font-semibold">{{ summary.completion_rate }}%</p>
            </div>
            <div>
              <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">已完成任务</p>
              <p class="text-[18px] font-semibold">{{ summary.task_completed }} / {{ summary.task_total }}</p>
            </div>
            <div>
              <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">指标记录</p>
              <p class="text-[18px] font-semibold">{{ summary.metrics.length }} 项</p>
            </div>
          </div>
          <ul v-if="summary.notes.length" class="mt-3 flex flex-col gap-1">
            <li v-for="line in summary.notes" :key="line" class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
              {{ line }}
            </li>
          </ul>
          <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            完成率只反映执行情况，不代表身体指标改善或恶化
          </p>
        </div>

        <div v-if="canReassess" class="glass card-pad">
          <h2 class="text-[14px] font-semibold">周期收尾</h2>
          <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
            {{ selected.status === 'completed' ? '这个周期已经结束。' : `距离周期结束还有 ${daysLeft} 天。` }}
            平台不会自动帮你重新评估，也不会自动生成下一周期计划，是否继续由你决定。
          </p>
          <div class="mt-3 flex flex-wrap items-end gap-2">
            <div class="min-w-[220px] flex-1">
              <label class="label" for="reassess">重新评估的原因</label>
              <input id="reassess" v-model="reassessReason" class="field" placeholder="例如：一个周期做完了，想看看指标有没有变化" />
            </div>
            <button class="btn btn-primary" :disabled="reassessing" @click="reassess">
              {{ reassessing ? '评估中' : '基于当前档案重新评估' }}
            </button>
          </div>
          <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            会读取你现在的档案与指标生成新评估，历史评估、报告与这个周期的打卡记录都保留
          </p>
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
                      <template v-if="canCheckin">
                        <button class="btn btn-ghost !px-2 !py-1 text-[11px]" @click="openFeedback(task)">未完成原因</button>
                        <button
                          v-if="!task.checkin_status"
                          class="btn btn-ghost !px-2 !py-1 text-[11px]"
                          @click="openReschedule(task)"
                        >
                          调整
                        </button>
                        <button class="btn btn-primary !px-3 !py-1 text-[11px]" :disabled="busy" @click="checkin(task, 'completed')">完成</button>
                        <button class="btn btn-ghost !px-3 !py-1 text-[11px]" :disabled="busy" @click="checkin(task, 'skipped')">跳过</button>
                      </template>
                      <span v-else class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">计划不在执行中，只读</span>
                    </div>
                  </div>
                  <div v-if="rescheduleTask === task.id" class="mt-2 flex flex-wrap items-end gap-2">
                    <div>
                      <label class="label" :for="`reschedule-${task.id}`">新的日期</label>
                      <input
                        :id="`reschedule-${task.id}`"
                        v-model="rescheduleDate"
                        class="field w-[168px]"
                        type="date"
                        :min="selected.start_date > today ? selected.start_date : today"
                        :max="selected.end_date"
                      />
                    </div>
                    <div>
                      <label class="label" :for="`time-${task.id}`">提醒时间</label>
                      <input :id="`time-${task.id}`" v-model="editTime" class="field w-[112px]" placeholder="HH:MM" />
                    </div>
                    <label class="flex items-center gap-2 pb-2 text-[12px]">
                      <input v-model="editReminder" type="checkbox" />
                      当天提醒
                    </label>
                    <button class="btn btn-primary !py-1 text-[11px]" :disabled="busy" @click="reschedule(task)">
                      保存调整
                    </button>
                    <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                      日期只能落在计划周期内，已打卡的任务不能改日期，关掉提醒后当天不再提示这个任务
                    </p>
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
