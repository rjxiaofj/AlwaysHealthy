import { effectScope, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useToday } from '@/utils/today'

function scopeWithToday() {
  const scope = effectScope()
  const today = scope.run(() => useToday())
  return { scope, today: today! }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('跨零点的今日', () => {
  it('挂载时给的是当前本地日期', () => {
    vi.setSystemTime(new Date(2026, 10, 5, 23, 50))

    const { scope, today } = scopeWithToday()

    expect(today.value).toBe('2026-11-05')
    scope.stop()
  })

  it('过零点后定时器把日期翻过来', async () => {
    vi.setSystemTime(new Date(2026, 10, 5, 23, 59, 40))
    const { scope, today } = scopeWithToday()

    vi.setSystemTime(new Date(2026, 10, 6, 0, 0, 10))
    vi.advanceTimersByTime(30_000)
    await nextTick()

    expect(today.value).toBe('2026-11-06')
    scope.stop()
  })

  it('没跨天时值不变', async () => {
    vi.setSystemTime(new Date(2026, 10, 5, 8, 0, 0))
    const { scope, today } = scopeWithToday()

    vi.advanceTimersByTime(60_000)
    await nextTick()

    expect(today.value).toBe('2026-11-05')
    scope.stop()
  })

  it('多个使用方共享同一个日期，只起一个定时器', () => {
    vi.setSystemTime(new Date(2026, 10, 5, 12, 0, 0))

    const first = scopeWithToday()
    const second = scopeWithToday()

    expect(first.today).toBe(second.today)
    expect(vi.getTimerCount()).toBe(1)

    first.scope.stop()
    second.scope.stop()
  })

  it('全部卸载后定时器停掉', () => {
    vi.setSystemTime(new Date(2026, 10, 5, 12, 0, 0))

    const first = scopeWithToday()
    const second = scopeWithToday()
    expect(vi.getTimerCount()).toBe(1)

    first.scope.stop()
    expect(vi.getTimerCount()).toBe(1)

    second.scope.stop()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('重新挂载会先对齐一次，不会沿用上次的旧日期', () => {
    vi.setSystemTime(new Date(2026, 10, 5, 12, 0, 0))
    const first = scopeWithToday()
    expect(first.today.value).toBe('2026-11-05')
    first.scope.stop()

    vi.setSystemTime(new Date(2026, 11, 1, 9, 0, 0))
    const second = scopeWithToday()

    expect(second.today.value).toBe('2026-12-01')
    second.scope.stop()
  })
})
