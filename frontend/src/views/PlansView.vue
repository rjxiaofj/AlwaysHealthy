<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { assessmentApi, planApi, reportApi, trackingApi } from '@/api'
import type { Plan, PlanSummary, Task, TrackingSummary } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import { useToastStore } from '@/stores/toast'
import {
  buildTaskPatch,
  canCancelPlan,
  canCheckinPlan,
  canReassessPlan,
  canShiftPlan,
  daysUntil,
  groupTasksByDate,
  isAdjustmentPending,
} from '@/views/planLogic'

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
const adjustmentNote = ref('')
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
const reporting = ref(false)

const today = new Date().toISOString().slice(0, 10)

const grouped = computed(() => (selected.value ? groupTasksByDate(selected.value.tasks) : []))

// 调整产生的草稿不会动 current_version_id，待确认版本由后端单独返回
const pendingVersion = computed(() => selected.value?.pending_version || null)

const canApprove = computed(() => !!pendingVersion.value)

const pendingIsAdjustment = computed(() => isAdjustmentPending(selected.value))

const adjustment = computed(() => selected.value?.adjustment || null)

const canCheckin = computed(() => canCheckinPlan(selected.value))

const canCancel = computed(() => canCancelPlan(selected.value))

const canShift = computed(() => canShiftPlan(selected.value, today))

const daysLeft = computed(() => {
  const plan = selected.value
  if (!plan) return 0
  return daysUntil(plan.end_date, today)
})

const canReassess = computed(() => canReassessPlan(selected.value, daysLeft.value))

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
  const version = pendingVersion.value
  if (!selected.value || !version) return
  busy.value = true
  try {
    selected.value = await planApi.approve(selected.value.id, version.id)
    toast.success('新版本已生效')
    await load(selected.value.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '确认失败')
  } finally {
    busy.value = false
  }
}

async function rejectPending() {
  const version = pendingVersion.value
  if (!selected.value || !version) return
  busy.value = true
  try {
    const plan = await planApi.rejectVersion(selected.value.id, version.id)
    toast.success(pendingIsAdjustment.value ? '这次调整已作废，计划保持原样' : '计划已取消')
    await load(plan.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '作废失败')
  } finally {
    busy.value = false
  }
}

async function removeDraftTask(taskId: string) {
  const plan = selected.value
  const version = pendingVersion.value
  if (!plan || !version) return
  busy.value = true
  try {
    selected.value = await planApi.removeDraftTask(plan.id, version.id, taskId)
    toast.success('已从待确认版本里删掉')
    await loadSummary()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '删除失败')
  } finally {
    busy.value = false
  }
}

async function submitAdjustmentFeedback(verdict: string) {
  const plan = selected.value
  const record = adjustment.value
  if (!plan || !record?.version_id) return
  const note = adjustmentNote.value.trim()
  const text = note ? `${verdict}：${note}` : verdict
  busy.value = true
  try {
    await planApi.adjustmentFeedback(plan.id, record.version_id, text)
    adjustmentNote.value = ''
    toast.success('反馈已记下')
    await load(plan.id)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '提交失败')
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

async function createTrackingReport() {
  if (!selected.value) return
  reporting.value = true
  try {
    const report = await reportApi.createTracking(selected.value.id)
    toast.success('本周期报告已生成')
    router.push(`/reports/${report.id}`)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '生成报告失败')
  } finally {
    reporting.value = false
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
  const patch = buildTaskPatch(task, {
    scheduled_date: rescheduleDate.value,
    scheduled_time: editTime.value,
    reminder_enabled: editReminder.value,
  })
  if (!patch.changed) {
    toast.error('日期、时间与提醒都没有变化')
    return
  }
  busy.value = true
  try {
    await planApi.patchTask(task.id, patch.body)
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
              <button v-if="canApprove" class="btn btn-ghost" :disabled="busy" @click="rejectPending">
                {{ pendingIsAdjustment ? '放弃这次调整' : '不接受这份计划' }}
              </button>
              <button v-if="canCancel" class="btn btn-ghost" :disabled="busy" @click="cancelPlan">取消计划</button>
            </div>
          </div>

          <div
            v-if="pendingVersion"
            class="mt-3 rounded-[14px] border px-3 py-2"
            :style="{ borderColor: 'var(--color-border)' }"
          >
            <p class="text-[11px] leading-relaxed" :style="{ color: 'var(--color-text-secondary)' }">
              待确认 v{{ pendingVersion.version_no }}：{{ pendingVersion.change_reason || '首次生成的计划' }}。
              确认后任务按这一版执行{{ pendingIsAdjustment ? '，放弃则继续用原来的版本' : '，不接受则计划取消' }}。
            </p>
            <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              这一版共 {{ pendingVersion.tasks.length }} 项任务，觉得多可以逐条删掉再确认
            </p>
            <ul class="mt-1 flex flex-col gap-1">
              <li
                v-for="item in pendingVersion.tasks.slice(0, 6)"
                :key="item.id"
                class="flex items-center justify-between gap-2 text-[11px]"
              >
                <span class="truncate">{{ item.scheduled_date }} {{ item.scheduled_time || '' }} {{ item.title }}</span>
                <button class="btn btn-ghost !px-2 !py-0.5 text-[11px]" :disabled="busy" @click="removeDraftTask(item.id)">
                  删掉
                </button>
              </li>
            </ul>
            <p v-if="pendingVersion.tasks.length > 6" class="mt-1 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              只列出前六项
            </p>
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

          <div v-if="adjustment" class="mt-4 rounded-[14px] border px-3 py-3" :style="{ borderColor: 'var(--color-border)' }">
            <p class="text-[12px] font-medium">这次调整合适吗</p>
            <p class="mt-1 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              调整原因：{{ adjustment.reason || '当时没有填写' }}
            </p>
            <template v-if="!adjustment.feedback">
              <div class="mt-2 flex flex-wrap gap-2">
                <button class="btn btn-ghost" :disabled="busy" @click="submitAdjustmentFeedback('更合适了')">更合适了</button>
                <button class="btn btn-ghost" :disabled="busy" @click="submitAdjustmentFeedback('差别不大')">差别不大</button>
                <button class="btn btn-ghost" :disabled="busy" @click="submitAdjustmentFeedback('还是不合适')">还是不合适</button>
              </div>
              <input v-model="adjustmentNote" class="field mt-2" maxlength="60" placeholder="想补充一句就写在这里，可留空" />
            </template>
            <p v-else class="mt-2 text-[12px]">已记录：{{ adjustment.feedback }}</p>
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
            <button
              v-if="selected.status === 'completed'"
              class="btn btn-ghost"
              :disabled="reporting"
              @click="createTrackingReport"
            >
              {{ reporting ? '生成中' : '生成本周期报告' }}
            </button>
            <button class="btn btn-primary" :disabled="reassessing" @click="reassess">
              {{ reassessing ? '评估中' : '基于当前档案重新评估' }}
            </button>
          </div>
          <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            报告含完成率与指标变化，生成后在个人中心的报告列表里可以回看与导出；历史评估、报告与这个周期的打卡记录都保留
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
