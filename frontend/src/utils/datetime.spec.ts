import { describe, expect, it } from 'vitest'

import { localDateInput, localDateTimeInput, localToday } from '@/utils/datetime'

// 东八区偏移是 -480 分钟。显式传进去，测试结果就与跑测试的机器时区无关
const UTC8 = -480

describe('本地日期', () => {
  it('UTC 还是前一天时，东八区已经算今天', () => {
    // 2026-11-04T17:30Z 等于东八区 11-05 凌晨 1:30
    const moment = new Date('2026-11-04T17:30:00Z')

    expect(moment.toISOString().slice(0, 10)).toBe('2026-11-04')
    expect(localToday(moment, UTC8)).toBe('2026-11-05')
  })

  it('东八区 23:30 仍然算当天，不提前跳到明天', () => {
    expect(localToday(new Date('2026-11-05T15:30:00Z'), UTC8)).toBe('2026-11-05')
  })

  it('跨年边界按本地日期走', () => {
    expect(localToday(new Date('2026-12-31T16:30:00Z'), UTC8)).toBe('2027-01-01')
  })

  it('不传偏移时跟随运行环境的时区', () => {
    const moment = new Date(2026, 10, 5, 0, 30)
    const local = `${moment.getFullYear()}-${String(moment.getMonth() + 1).padStart(2, '0')}-${String(moment.getDate()).padStart(2, '0')}`

    expect(localToday(moment)).toBe(local)
  })
})

describe('本地时间串', () => {
  it('给 datetime-local 用的串不带时区也不带秒', () => {
    expect(localDateTimeInput(new Date('2026-11-04T17:30:45Z'), UTC8)).toBe('2026-11-05T01:30')
  })

  it('与 localToday 用的是同一套偏移', () => {
    const moment = new Date('2026-11-04T17:30:00Z')

    expect(localDateTimeInput(moment, UTC8).slice(0, 10)).toBe(localToday(moment, UTC8))
  })

  it('同一天本地时间的首尾时刻给同一个日期', () => {
    expect(localToday(new Date('2026-11-04T16:00:00Z'), UTC8)).toBe('2026-11-05')
    expect(localToday(new Date('2026-11-05T15:59:00Z'), UTC8)).toBe('2026-11-05')
  })

  it('localDateInput 保留完整的 ISO 形态，便于排查', () => {
    expect(localDateInput(new Date('2026-11-04T17:30:00Z'), UTC8)).toBe('2026-11-05T01:30:00.000Z')
  })
})
