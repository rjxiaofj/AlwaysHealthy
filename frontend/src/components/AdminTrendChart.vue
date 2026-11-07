<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

// 管理看板的 7 日折线：新增账号与登录失败两条线画在同一张图上，
// x 轴按日期对齐（同一天两条线的点在同一个 x 上）。点数固定很少，
// 直接算坐标即可，不需要旧的 buildChart 那套平滑曲线。
const props = defineProps<{
  series: { name: string; color: string; points: { date: string; count: number }[] }[]
}>()

const HEIGHT = 216
const PAD = { left: 36, right: 14, top: 16, bottom: 26 }

const holder = ref<HTMLDivElement | null>(null)
const width = ref(0)
const active = ref<number | null>(null)
let observer: ResizeObserver | null = null

onMounted(() => {
  const element = holder.value
  if (!element) return
  width.value = element.clientWidth
  observer = new ResizeObserver((entries) => {
    const next = entries[0]?.contentRect.width ?? 0
    if (next > 0) width.value = next
  })
  observer.observe(element)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})

const labels = computed(() => props.series[0]?.points.map((point) => point.date) ?? [])

const yMax = computed(() => {
  const peak = Math.max(
    0,
    ...props.series.flatMap((item) => item.points.map((point) => point.count)),
  )
  // 全是 0 时给个 4 的刻度，否则整张图贴到底部看不出网格
  return Math.max(4, peak)
})

const plotW = computed(() => Math.max(120, (width.value || 480) - PAD.left - PAD.right))
const plotH = HEIGHT - PAD.top - PAD.bottom
const baseY = PAD.top + plotH

function xOf(index: number): number {
  const count = labels.value.length
  if (count <= 1) return PAD.left + plotW.value / 2
  return PAD.left + (plotW.value * index) / (count - 1)
}

// 5 条横向网格（0 到最大值均分），都比 0 值线更淡
const gridLines = computed(() =>
  Array.from({ length: 5 }, (_, index) => {
    const value = Math.round((yMax.value * index) / 4)
    return { value, y: baseY - (plotH * index) / 4 }
  }),
)

function yOf(count: number): number {
  return baseY - (plotH * count) / yMax.value
}

const paths = computed(() =>
  props.series.map((item) => ({
    ...item,
    d: item.points
      .map((point, index) => `${index === 0 ? 'M' : 'L'}${xOf(index)},${yOf(point.count)}`)
      .join(' '),
  })),
)

const hoveredIndex = computed(() => active.value)
const tooltipLeft = computed(() => {
  if (active.value === null) return 0
  const x = xOf(active.value)
  return Math.min(Math.max(x, 70), Math.max(plotW.value + PAD.left - 70, 70))
})

function handleMove(event: PointerEvent) {
  const count = labels.value.length
  if (!count) return
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const x = event.clientX - rect.left
  const step = count > 1 ? plotW.value / (count - 1) : plotW.value
  const index = Math.round((x - PAD.left) / (step || 1))
  active.value = Math.min(count - 1, Math.max(0, index))
}

function shortDate(value: string): string {
  const parts = value.split('-')
  return parts.length === 3 ? `${Number(parts[1])}/${Number(parts[2])}` : value
}
</script>

<template>
  <div>
    <div class="mb-3 flex flex-wrap items-center gap-4">
      <span v-for="item in series" :key="item.name" class="flex items-center gap-1.5 text-[11px]">
        <span class="h-2 w-2 rounded-full" :style="{ background: item.color }" />
        <span :style="{ color: 'var(--color-text-secondary)' }">{{ item.name }}</span>
      </span>
    </div>

    <div
      ref="holder"
      class="relative w-full"
      :style="{ height: `${HEIGHT}px` }"
      @pointermove="handleMove"
      @pointerleave="active = null"
    >
      <svg
        v-if="labels.length"
        class="block"
        :width="width || 480"
        :height="HEIGHT"
        role="img"
        :aria-label="`近 ${labels.length} 天趋势`"
      >
        <g>
          <line
            v-for="line in gridLines"
            :key="`grid-${line.value}`"
            class="chart-grid"
            :x1="PAD.left"
            :x2="PAD.left + plotW"
            :y1="line.y"
            :y2="line.y"
          />
          <text
            v-for="line in gridLines"
            :key="`tick-${line.value}`"
            class="chart-label"
            :x="PAD.left - 8"
            :y="line.y + 4"
            text-anchor="end"
          >
            {{ line.value }}
          </text>
        </g>

        <text
          v-for="(label, index) in labels"
          :key="`x-${label}`"
          class="chart-label"
          :x="xOf(index)"
          :y="HEIGHT - 8"
          text-anchor="middle"
        >
          {{ shortDate(label) }}
        </text>

        <line
          v-if="hoveredIndex !== null"
          class="chart-guide"
          :x1="xOf(hoveredIndex)"
          :x2="xOf(hoveredIndex)"
          :y1="PAD.top"
          :y2="baseY"
        />

        <g v-for="item in paths" :key="item.name">
          <path class="chart-line" :d="item.d" :style="{ stroke: item.color }" />
          <circle
            v-for="(point, index) in item.points"
            :key="`${item.name}-${point.date}`"
            class="chart-dot"
            :style="{ fill: item.color }"
            :cx="xOf(index)"
            :cy="yOf(point.count)"
            :r="hoveredIndex === index ? 4 : 2.6"
          />
        </g>
      </svg>

      <p
        v-else
        class="absolute inset-0 flex items-center justify-center text-[12px]"
        :style="{ color: 'var(--color-text-tertiary)' }"
      >
        暂无数据
      </p>

      <div
        v-if="hoveredIndex !== null && labels[hoveredIndex]"
        class="chart-tooltip"
        :style="{ left: `${tooltipLeft}px`, top: '4px' }"
      >
        <p class="chart-tooltip-title">{{ labels[hoveredIndex] }}</p>
        <p v-for="item in series" :key="item.name" class="chart-tooltip-row">
          <span :style="{ color: item.color }">{{ item.name }}</span>
          <span class="tabular-nums">{{ item.points[hoveredIndex]?.count ?? 0 }}</span>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-grid {
  stroke: var(--color-border);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.chart-line {
  fill: none;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chart-guide {
  stroke: var(--color-border);
  stroke-width: 1;
}

.chart-dot {
  transition: r 120ms ease;
}

.chart-label {
  fill: var(--color-text-tertiary);
  font-size: 11px;
}

.chart-tooltip {
  position: absolute;
  transform: translateX(-50%);
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  background: var(--color-surface-glass-strong);
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 22px var(--color-shadow);
  pointer-events: none;
  white-space: nowrap;
}

.chart-tooltip-title {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.chart-tooltip-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: var(--color-text-primary);
}
</style>
