<script setup lang="ts">
import { computed } from 'vue'

// 横向条形图：后台看板里的分布类数据（角色、状态、事件分级、工作流）都是
// 「若干名字 + 计数」，横向条形比饼图好读，名字也不用挤在扇区旁边。
// 手写 div 就够，不用引图表库。
const props = withDefaults(
  defineProps<{
    items: { label: string; value: number }[]
    emptyText?: string
    unit?: string
  }>(),
  { emptyText: '暂无数据', unit: '' },
)

const max = computed(() => Math.max(1, ...props.items.map((item) => item.value)))
const total = computed(() => props.items.reduce((sum, item) => sum + item.value, 0))

function ratio(value: number): number {
  return Math.max(2, Math.round((value / max.value) * 100))
}

function share(value: number): string {
  if (!total.value) return '0%'
  return `${Math.round((value / total.value) * 100)}%`
}
</script>

<template>
  <div v-if="items.length" class="flex flex-col gap-2.5">
    <div v-for="item in items" :key="item.label" class="flex items-center gap-3">
      <span class="w-[76px] shrink-0 truncate text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
        {{ item.label }}
      </span>
      <div class="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full" :style="{ background: 'var(--color-bg-secondary)' }">
        <div
          class="h-full rounded-full"
          :style="{ width: `${ratio(item.value)}%`, background: 'var(--color-info)' }"
        />
      </div>
      <span class="w-[54px] shrink-0 text-right text-[12px] font-medium tabular-nums">
        {{ item.value }}{{ unit }}
      </span>
      <span class="w-[38px] shrink-0 text-right text-[11px] tabular-nums" :style="{ color: 'var(--color-text-tertiary)' }">
        {{ share(item.value) }}
      </span>
    </div>
  </div>
  <p v-else class="py-4 text-center text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">
    {{ emptyText }}
  </p>
</template>
