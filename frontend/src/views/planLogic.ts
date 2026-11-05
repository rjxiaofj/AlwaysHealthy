import type { Plan, Task } from '@/api/types'

const DAY_MS = 86400000
const SHIFTABLE_STATUSES = ['active', 'pending_review']
const CHECKED_STATUSES = ['completed', 'partial', 'skipped']

export interface TaskGroup {
  date: string
  tasks: Task[]
}

export interface TaskDraft {
  scheduled_date: string
  scheduled_time: string
  reminder_enabled: boolean
}

export interface TaskPatch {
  body: Record<string, unknown>
  changed: boolean
}

export function groupTasksByDate(tasks: Task[]): TaskGroup[] {
  const map = new Map<string, Task[]>()
  tasks.forEach((task) => {
    const list = map.get(task.scheduled_date) || []
    list.push(task)
    map.set(task.scheduled_date, list)
  })
  return Array.from(map.entries())
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(([date, rows]) => ({ date, tasks: rows }))
}

// 两端都按本地零点取时间戳，跨月跨年靠 Math.round 吸收夏令时造成的整点偏移
export function daysUntil(endDate: string, today: string): number {
  const end = new Date(`${endDate}T00:00:00`).getTime()
  const now = new Date(`${today}T00:00:00`).getTime()
  return Math.round((end - now) / DAY_MS)
}

// 后端按版本统计打卡，前端只能按当前版本任务的打卡状态粗判，最终拦截以接口为准
export function canShiftPlan(plan: Plan | null, today: string): boolean {
  if (!plan) return false
  if (!SHIFTABLE_STATUSES.includes(plan.status)) return false
  if (plan.start_date < today) return false
  return !plan.tasks.some((task) => CHECKED_STATUSES.includes(task.checkin_status || ''))
}

// 周期结束或只剩两天时才给重新评估入口，平台不自动发起下一周期
export function canReassessPlan(plan: Plan | null, daysLeft: number): boolean {
  if (!plan) return false
  if (plan.status === 'completed') return true
  return plan.status === 'active' && daysLeft <= 2
}

// 打卡只允许 active 计划的当前版本任务
export function canCheckinPlan(plan: Plan | null): boolean {
  return plan?.status === 'active'
}

export function canCancelPlan(plan: Plan | null): boolean {
  return ['active', 'pending_review'].includes(plan?.status || '')
}

// 待确认版本配 active 计划说明这是调整草稿，否掉只作废这一版，不动计划本身
export function isAdjustmentPending(plan: Plan | null): boolean {
  if (!plan?.pending_version) return false
  return plan.status === 'active'
}

// 时间可以清空：没有时间表示任意时间。清空要发 null，缺字段才是「不改」，
// 所以这里不能沿用「值非空才算改」的写法，否则用户点掉时间后请求里根本没有这个字段
export function buildTaskPatch(task: Task, draft: TaskDraft): TaskPatch {
  const body: Record<string, unknown> = {}
  if (draft.scheduled_date !== task.scheduled_date) body.scheduled_date = draft.scheduled_date
  const nextTime = draft.scheduled_time.trim()
  if (nextTime !== (task.scheduled_time || '')) body.scheduled_time = nextTime || null
  if (draft.reminder_enabled !== task.reminder_enabled) body.reminder_enabled = draft.reminder_enabled
  return { body, changed: Object.keys(body).length > 0 }
}
