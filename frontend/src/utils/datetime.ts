// toISOString 走 UTC。东八区凌晨 0 点到 8 点之间，它给出的是前一天的日期，
// 「今日任务」会空、距周期结束的天数会多一天、改期的最小日期也会差一天。
// 这里统一按本地时间取日历日期，offsetMinutes 只为测试时能固定时区。
export function localDateInput(now: Date = new Date(), offsetMinutes?: number): string {
  const offset = offsetMinutes === undefined ? now.getTimezoneOffset() : offsetMinutes
  return new Date(now.getTime() - offset * 60000).toISOString()
}

export function localToday(now: Date = new Date(), offsetMinutes?: number): string {
  return localDateInput(now, offsetMinutes).slice(0, 10)
}

// datetime-local 输入框要的就是不带时区的本地时间串
export function localDateTimeInput(now: Date = new Date(), offsetMinutes?: number): string {
  return localDateInput(now, offsetMinutes).slice(0, 16)
}
