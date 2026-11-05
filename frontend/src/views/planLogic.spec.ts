import { describe, expect, it } from 'vitest'

import type { Plan, Task } from '@/api/types'
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

function task(overrides: Partial<Task> = {}): Task {
  return {
    id: 't1',
    title: '早餐记录',
    category: 'diet',
    description: null,
    scheduled_date: '2026-11-05',
    scheduled_time: null,
    frequency: null,
    duration_minutes: null,
    completion_criteria: '记录早餐内容',
    checkin_type: 'manual',
    reminder_enabled: true,
    status: 'active',
    checkin_status: null,
    ...overrides,
  }
}

function plan(overrides: Partial<Plan> = {}): Plan {
  return {
    id: 'p1',
    title: '两周计划',
    duration_days: 14,
    start_date: '2026-11-05',
    end_date: '2026-11-18',
    status: 'active',
    current_version_id: 'v1',
    assessment_id: null,
    created_at: '2026-11-05T00:00:00Z',
    adjustment: null,
    pending_version: null,
    tasks: [],
    versions: [],
    ...overrides,
  }
}

describe('任务按日期分组', () => {
  it('没有任务时返回空数组', () => {
    expect(groupTasksByDate([])).toEqual([])
  })

  it('同一天的任务归到一组，并保持原先顺序', () => {
    const groups = groupTasksByDate([
      task({ id: 'a', scheduled_date: '2026-11-05' }),
      task({ id: 'b', scheduled_date: '2026-11-06' }),
      task({ id: 'c', scheduled_date: '2026-11-05' }),
    ])

    expect(groups.map((group) => group.date)).toEqual(['2026-11-05', '2026-11-06'])
    expect(groups[0].tasks.map((item) => item.id)).toEqual(['a', 'c'])
    expect(groups[1].tasks.map((item) => item.id)).toEqual(['b'])
  })

  it('日期按字符串升序，不依赖任务到达顺序', () => {
    const groups = groupTasksByDate([
      task({ id: 'late', scheduled_date: '2026-11-09' }),
      task({ id: 'early', scheduled_date: '2026-11-01' }),
      task({ id: 'mid', scheduled_date: '2026-11-05' }),
    ])

    expect(groups.map((group) => group.date)).toEqual(['2026-11-01', '2026-11-05', '2026-11-09'])
  })

  it('跨月的日期仍按时间先后排序', () => {
    const groups = groupTasksByDate([
      task({ id: 'next', scheduled_date: '2026-12-01' }),
      task({ id: 'prev', scheduled_date: '2026-10-31' }),
    ])

    expect(groups.map((group) => group.date)).toEqual(['2026-10-31', '2026-12-01'])
  })
})

describe('距周期结束还有几天', () => {
  it('同一天为 0', () => {
    expect(daysUntil('2026-11-05', '2026-11-05')).toBe(0)
  })

  it('往后两天为 2', () => {
    expect(daysUntil('2026-11-07', '2026-11-05')).toBe(2)
  })

  it('已过去为负数', () => {
    expect(daysUntil('2026-11-01', '2026-11-05')).toBe(-4)
  })

  it('跨月与跨年都算对', () => {
    expect(daysUntil('2026-12-01', '2026-11-28')).toBe(3)
    expect(daysUntil('2027-01-02', '2026-12-30')).toBe(3)
  })
})

describe('能否整体改期', () => {
  const today = '2026-11-05'

  it('没有选中计划时为否', () => {
    expect(canShiftPlan(null, today)).toBe(false)
  })

  it('只有执行中与待确认的计划能改期', () => {
    expect(canShiftPlan(plan({ status: 'active' }), today)).toBe(true)
    expect(canShiftPlan(plan({ status: 'pending_review' }), today)).toBe(true)
    expect(canShiftPlan(plan({ status: 'draft' }), today)).toBe(false)
    expect(canShiftPlan(plan({ status: 'completed' }), today)).toBe(false)
    expect(canShiftPlan(plan({ status: 'cancelled' }), today)).toBe(false)
  })

  it('计划已经开始就不能改期', () => {
    expect(canShiftPlan(plan({ start_date: '2026-11-04' }), today)).toBe(false)
  })

  it('当天开始仍可改期', () => {
    expect(canShiftPlan(plan({ start_date: today }), today)).toBe(true)
  })

  it('任意任务已有打卡就不能改期', () => {
    for (const status of ['completed', 'partial', 'skipped']) {
      expect(canShiftPlan(plan({ tasks: [task({ checkin_status: status })] }), today)).toBe(false)
    }
    expect(canShiftPlan(plan({ tasks: [task({ checkin_status: null })] }), today)).toBe(true)
  })
})

describe('能否发起重新评估', () => {
  it('没有选中计划时为否', () => {
    expect(canReassessPlan(null, 5)).toBe(false)
  })

  it('已结束的计划总是可以', () => {
    expect(canReassessPlan(plan({ status: 'completed' }), 30)).toBe(true)
  })

  it('执行中的计划只剩两天以内才可以', () => {
    expect(canReassessPlan(plan({ status: 'active' }), 2)).toBe(true)
    expect(canReassessPlan(plan({ status: 'active' }), 0)).toBe(true)
    expect(canReassessPlan(plan({ status: 'active' }), 3)).toBe(false)
  })

  it('未生效与已取消的计划都不给入口', () => {
    expect(canReassessPlan(plan({ status: 'draft' }), 0)).toBe(false)
    expect(canReassessPlan(plan({ status: 'cancelled' }), 0)).toBe(false)
  })
})

describe('打卡与取消的入口', () => {
  it('只有执行中的计划能打卡', () => {
    expect(canCheckinPlan(plan({ status: 'active' }))).toBe(true)
    expect(canCheckinPlan(plan({ status: 'completed' }))).toBe(false)
    expect(canCheckinPlan(null)).toBe(false)
  })

  it('执行中与待确认的计划能取消', () => {
    expect(canCancelPlan(plan({ status: 'active' }))).toBe(true)
    expect(canCancelPlan(plan({ status: 'pending_review' }))).toBe(true)
    expect(canCancelPlan(plan({ status: 'completed' }))).toBe(false)
    expect(canCancelPlan(null)).toBe(false)
  })
})

describe('待确认版本是不是调整草稿', () => {
  const pending = { id: 'v2', version_no: 2, change_reason: null, tasks: [] }

  it('没有待确认版本时为否', () => {
    expect(isAdjustmentPending(plan())).toBe(false)
    expect(isAdjustmentPending(null)).toBe(false)
  })

  it('待确认版本配执行中的计划算调整草稿', () => {
    expect(isAdjustmentPending(plan({ status: 'active', pending_version: pending }))).toBe(true)
  })

  it('首次生成的草稿计划不算调整', () => {
    expect(isAdjustmentPending(plan({ status: 'draft', pending_version: pending }))).toBe(false)
  })
})

describe('任务改期的请求体', () => {
  const base = task({ scheduled_date: '2026-11-05', scheduled_time: '08:00', reminder_enabled: true })

  it('什么都没改时不发请求体', () => {
    const patch = buildTaskPatch(base, {
      scheduled_date: '2026-11-05',
      scheduled_time: '08:00',
      reminder_enabled: true,
    })

    expect(patch.changed).toBe(false)
    expect(patch.body).toEqual({})
  })

  it('只带真正变了的字段', () => {
    const patch = buildTaskPatch(base, {
      scheduled_date: '2026-11-06',
      scheduled_time: '08:00',
      reminder_enabled: true,
    })

    expect(patch.changed).toBe(true)
    expect(patch.body).toEqual({ scheduled_date: '2026-11-06' })
  })

  it('清空时间发 null，不是省略字段', () => {
    const patch = buildTaskPatch(base, {
      scheduled_date: '2026-11-05',
      scheduled_time: '',
      reminder_enabled: true,
    })

    expect(patch.changed).toBe(true)
    expect(patch.body).toEqual({ scheduled_time: null })
  })

  it('本来就没有时间的任务填了空白不算改动', () => {
    const noTime = task({ scheduled_time: null })
    const patch = buildTaskPatch(noTime, {
      scheduled_date: noTime.scheduled_date,
      scheduled_time: '  ',
      reminder_enabled: true,
    })

    expect(patch.changed).toBe(false)
  })

  it('时间两端的空格会去掉再比对', () => {
    const patch = buildTaskPatch(base, {
      scheduled_date: '2026-11-05',
      scheduled_time: ' 08:00 ',
      reminder_enabled: true,
    })

    expect(patch.changed).toBe(false)
  })

  it('只改提醒开关', () => {
    const patch = buildTaskPatch(base, {
      scheduled_date: '2026-11-05',
      scheduled_time: '08:00',
      reminder_enabled: false,
    })

    expect(patch.body).toEqual({ reminder_enabled: false })
  })

  it('三个字段一起改时都带上', () => {
    const patch = buildTaskPatch(base, {
      scheduled_date: '2026-11-08',
      scheduled_time: '21:00',
      reminder_enabled: false,
    })

    expect(patch.body).toEqual({
      scheduled_date: '2026-11-08',
      scheduled_time: '21:00',
      reminder_enabled: false,
    })
  })
})
