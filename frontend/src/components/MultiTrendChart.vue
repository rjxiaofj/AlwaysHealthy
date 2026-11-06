<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type { MetricPoint } from '@/api/types'
import { buildMultiChart, nearestIndex } from '@/components/chartGeometry'

// 多指标同图对比。跟 TrendChart 的区别：这里画多条线，每条一个颜色，带图例。
// 颜色固定一套，深浅主题下都用描边，不依赖 currentColor（那只能有一种颜色）。
interface Series {
  key: string
  label: string
  unit: string
  points: MetricPoint[]
}

const props = defineProps<{ series: Series[] }>()

const HEIGHT = 280
const SERIES_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']

const holder = ref<HTMLDivElement | null>(null)
const width = ref(0)
const active = ref<{ series: number; index: number } | null>(null)

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

const layout = computed(() =>
  buildMultiChart(
    props.series.map((item) => ({ key: item.key, label: item.label, points: item.points })),
    { width: width.value || 640, height: HEIGHT },
  ),
)

function colorAt(index: number) {
  return SERIES_COLORS[index % SERIES_COLORS.length]
}

const hovered = computed(() => {
  if (active.value === null) return null
  const series = layout.value.series[active.value.series]
  if (!series) return null
  const point = series.points[active.value.index]
  if (!point) return null
  return { series: active.value.series, point }
})

// 几何层会丢掉全是无效值的序列，单位按 key 查，别按数组下标直接对 props.series
const unitByKey = computed(() => new Map(props.series.map((item) => [item.key, item.unit])))

/**
 * 悬停某一天时把各序列在这一天的测量一起列出来。
 * 横轴已经按日期对齐了，提示框却只报一条线的话，对齐的意义就少了一半；
 * 没测的指标直接不列，不拿别天的值凑数。
 */
const sameDateRows = computed(() => {
  const hover = hovered.value
  if (!hover) return []
  return layout.value.series.flatMap((item, index) => {
    const point = item.points.find((candidate) => candidate.date === hover.point.date)
    if (!point) return []
    return [
      {
        key: item.key,
        label: item.label,
        unit: unitByKey.value.get(item.key) || '',
        value: point.value,
        color: colorAt(index),
      },
    ]
  })
})

const tooltipStyle = computed(() => {
  const hover = hovered.value
  if (!hover) return {}
  const half = 64
  const left = Math.min(Math.max(hover.point.x, half), Math.max(layout.value.width - half, half))
  const above = hover.point.y >= 64
  return {
    left: `${left}px`,
    top: `${hover.point.y + (above ? -14 : 14)}px`,
    transform: above ? 'translate(-50%, -100%)' : 'translate(-50%, 0)',
  }
})

function handleMove(event: PointerEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const targetX = event.clientX - rect.left
  // 找离鼠标最近的点，跨所有序列一起比，选真正最近的那个
  let best: { series: number; index: number } | null = null
  let bestDistance = Number.POSITIVE_INFINITY
  for (let seriesIndex = 0; seriesIndex < layout.value.series.length; seriesIndex += 1) {
    const item = layout.value.series[seriesIndex]
    const index = nearestIndex(item.points, targetX)
    if (index === null) continue
    const distance = Math.abs(item.points[index].x - targetX)
    if (distance < bestDistance) {
      bestDistance = distance
      best = { series: seriesIndex, index }
    }
  }
  active.value = best
}
</script>

<template>
  <div class="w-full">
    <div
      ref="holder"
      class="relative w-full"
      :style="{ height: `${HEIGHT}px` }"
      @pointermove="handleMove"
      @pointerleave="active = null"
    >
      <svg
        v-if="layout.series.length"
        class="block"
        :width="layout.width"
        :height="layout.height"
        role="img"
        :aria-label="`${layout.series.map((item) => item.label).join('与')}对比`"
      >
      <g>
        <line
          v-for="tick in layout.yTicks"
          :key="`grid-${tick.text}`"
          class="chart-grid"
          :x1="46"
          :x2="layout.width - 16"
          :y1="tick.y"
          :y2="tick.y"
        />
        <text
          v-for="tick in layout.yTicks"
          :key="`label-${tick.text}`"
          class="chart-label"
          :x="38"
          :y="tick.y + 4"
          text-anchor="end"
        >
          {{ tick.text }}
        </text>
      </g>

      <line class="chart-axis" :x1="46" :x2="layout.width - 16" :y1="layout.baseline" :y2="layout.baseline" />
      <text
        v-for="tick in layout.xTicks"
        :key="`x-${tick.text}-${tick.x}`"
        class="chart-label"
        :x="tick.x"
        :y="layout.height - 8"
        :text-anchor="tick.anchor"
      >
        {{ tick.text }}
      </text>

      <template v-for="(item, seriesIndex) in layout.series" :key="item.key">
        <path :d="item.line" class="chart-line" :stroke="colorAt(seriesIndex)" />
        <circle
          v-for="(point, index) in item.points"
          :key="`dot-${seriesIndex}-${index}`"
          class="chart-dot"
          :class="{ 'is-active': hovered?.point.date === point.date }"
          :cx="point.x"
          :cy="point.y"
          :r="hovered?.point.date === point.date ? 4.5 : 2.8"
          :fill="colorAt(seriesIndex)"
        />
      </template>

      <line v-if="hovered" class="chart-guide" :x1="hovered.point.x" :x2="hovered.point.x" :y1="16" :y2="layout.baseline" />
      </svg>

      <p v-else class="absolute inset-0 flex items-center justify-center text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">
        暂无可画的数据
      </p>

      <div v-if="hovered" class="chart-tooltip" :style="tooltipStyle">
        <p class="chart-tooltip-title">{{ hovered.point.label }}</p>
        <div v-for="row in sameDateRows" :key="row.key" class="chart-tooltip-row">
          <span class="inline-block h-[3px] w-3 shrink-0 rounded" :style="{ background: row.color }" />
          <span class="chart-tooltip-name">{{ row.label }}</span>
          <span class="chart-tooltip-num">{{ row.value }}<span class="chart-tooltip-unit">{{ row.unit }}</span></span>
        </div>
      </div>
    </div>

    <div v-if="layout.series.length" class="mt-2 flex flex-wrap gap-3">
      <span v-for="(item, index) in layout.series" :key="item.key" class="flex items-center gap-1.5 text-[12px]">
        <span class="inline-block h-[3px] w-4 rounded" :style="{ background: colorAt(index) }" />
        <span :style="{ color: 'var(--color-text-secondary)' }">{{ item.label }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.chart-grid {
  stroke: var(--color-border);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.chart-axis {
  stroke: var(--color-border);
  stroke-width: 1;
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
  transform: translate(-50%, -100%);
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
  margin-bottom: 3px;
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.chart-tooltip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.chart-tooltip-name {
  flex: 1;
}

.chart-tooltip-num {
  font-weight: 600;
  color: var(--color-text-primary);
}

.chart-tooltip-unit {
  margin-left: 4px;
  font-size: 11px;
  font-weight: 400;
  color: var(--color-text-secondary);
}
</style>
