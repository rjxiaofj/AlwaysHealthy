import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Reminder } from '@/api/types'

const list = vi.fn<() => Promise<Reminder[]>>()
const read = vi.fn<(id: string) => Promise<null>>()

vi.mock('@/api', () => ({
  reminderApi: {
    list: () => list(),
    read: (id: string) => read(id),
  },
}))

// store 里 inflight 是模块级变量，必须每次重新 import 才能拿到干净状态
async function freshStore() {
  vi.resetModules()
  const { useReminderStore } = await import('@/stores/reminders')
  return useReminderStore()
}

function reminder(id: string, readAt: string | null = null): Reminder {
  return {
    id,
    notification_type: 'metric_abnormal',
    title: `提醒 ${id}`,
    content: '内容',
    related_object_id: null,
    read_at: readAt,
    created_at: '2026-11-05T08:00:00Z',
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  list.mockReset()
  read.mockReset()
})

describe('提醒 store', () => {
  it('并发加载只发一次请求', async () => {
    let release: (rows: Reminder[]) => void = () => {}
    list.mockImplementation(
      () =>
        new Promise<Reminder[]>((resolve) => {
          release = resolve
        }),
    )

    const store = await freshStore()
    const first = store.load()
    const second = store.load()

    expect(list).toHaveBeenCalledTimes(1)
    expect(store.loading).toBe(true)

    release([reminder('a'), reminder('b', '2026-11-05T09:00:00Z')])
    await Promise.all([first, second])

    expect(store.items).toHaveLength(2)
    expect(store.loading).toBe(false)
  })

  it('上一轮结束后可以再次加载，不会被 inflight 卡死', async () => {
    list.mockResolvedValue([reminder('a')])

    const store = await freshStore()
    await store.load()
    await store.load()

    expect(list).toHaveBeenCalledTimes(2)
  })

  it('加载失败后 loading 归位并允许重试', async () => {
    list.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce([reminder('a')])

    const store = await freshStore()
    await expect(store.load()).rejects.toThrow('boom')
    expect(store.loading).toBe(false)

    await store.load()
    expect(store.items).toHaveLength(1)
  })

  it('标已读后未读数就地同步', async () => {
    list.mockResolvedValue([reminder('a'), reminder('b'), reminder('c', '2026-11-05T09:00:00Z')])
    read.mockResolvedValue(null)

    const store = await freshStore()
    await store.load()
    expect(store.unread).toBe(2)

    await store.read('a')
    expect(read).toHaveBeenCalledWith('a')
    expect(store.unread).toBe(1)
    expect(store.items.find((item) => item.id === 'a')?.read_at).toBeTruthy()
  })

  it('标已读接口失败时不改本地状态', async () => {
    list.mockResolvedValue([reminder('a'), reminder('b')])
    read.mockRejectedValue(new Error('network'))

    const store = await freshStore()
    await store.load()

    await expect(store.read('a')).rejects.toThrow('network')
    expect(store.unread).toBe(2)
    expect(store.items.every((item) => item.read_at === null)).toBe(true)
  })

  it('标记不存在的 id 不报错也不影响未读数', async () => {
    list.mockResolvedValue([reminder('a')])
    read.mockResolvedValue(null)

    const store = await freshStore()
    await store.load()

    await store.read('missing')
    expect(store.unread).toBe(1)
  })
})
