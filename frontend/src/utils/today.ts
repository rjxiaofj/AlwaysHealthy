import { computed, onScopeDispose, ref, type ComputedRef } from 'vue'

import { localToday } from '@/utils/datetime'

// 页面挂着过零点不会自己刷新，今日任务、距结束天数都会停在昨天。
// 三十秒查一次足够：跨零点后最多晚半分钟翻页，代价可以忽略
const INTERVAL_MS = 30_000

const current = ref(localToday())
const today = computed(() => current.value)

let timer: ReturnType<typeof setInterval> | null = null
let users = 0

function sync() {
  const next = localToday()
  if (next !== current.value) current.value = next
}

function start() {
  // 切回标签页立刻对一次，后台标签页的定时器会被浏览器节流
  sync()
  timer = setInterval(sync, INTERVAL_MS)
  document.addEventListener('visibilitychange', sync)
}

function stop() {
  if (timer !== null) clearInterval(timer)
  timer = null
  document.removeEventListener('visibilitychange', sync)
}

export function useToday(): ComputedRef<string> {
  users += 1
  // 第一个使用者进来先对齐一次，避免上一次挂载留下的旧值
  if (users === 1) start()
  onScopeDispose(() => {
    users -= 1
    if (users === 0) stop()
  })
  return today
}
