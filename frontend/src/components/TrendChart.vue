<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useId } from 'vue'

import type { MetricPoint } from '@/api/types'
import { buildChart, nearestIndex } from '@/components/chartGeometry'

// 一条折线加虚线网格，手写 SVG 就够。原来用 echarts 要背 466 kB（gzip 157），
// 而这里用到的只有「直线 + 网格 + 悬停提示」三样东西。
const props = defineProps<{ points: MetricPoint[]; label: string; unit: string }>()

const HEIGHT = 260
const holder = ref<HTMLDivElement | null>(null)
const width = ref(0)
const active = ref<number | null>(null)
const gradientId = `trend-fill-${useId()}`

let observer: ResizeObserver | null = null

onMounted(() => {
  const element = holder.value
  if (!element) return
  width.value = element.clientWidth
  // 侧栏折叠、窗口缩放都会改宽度。SVG 不像 canvas 那样能整体缩放，
  // 得按真实像素重算坐标，所以宽度要跟着走
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

const layout = computed(() => buildChart(props.points, { width: width.value || 640, height: HEIGHT }))
const hovered = computed(() => {
  if (active.value === null) return null
  return layout.value.points[active.value] ?? null
})
const tooltipStyle = computed(() => {
  const point = hovered.value
  if (!point) return {}
  // 贴近两边时把提示框拉回来，别被容器切掉
  const half = 64
  const left = Math.min(Math.max(point.x, half), Math.max(layout.value.width - half, half))
  // 点靠近顶部时翻到下方：最高点上方就是指标切换栏，压上去会挡住可点的按钮
  const above = point.y >= 64
  return {
    left: `${left}px`,
    top: `${point.y + (above ? -14 : 14)}px`,
    transform: above ? 'translate(-50%, -100%)' : 'translate(-50%, 0)',
  }
})

function handleMove(event: PointerEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  active.value = nearestIndex(layout.value.points, event.clientX - rect.left)
}
</script>

<template>
  <div
    ref="holder"
    class="relative w-full"
    :style="{ height: `${HEIGHT}px` }"
    @pointermove="handleMove"
    @pointerleave="active = null"
  >
    <svg
      v-if="layout.points.length"
      class="block"
      :width="layout.width"
      :height="layout.height"
      role="img"
      :aria-label="`${label}趋势，共 ${layout.points.length} 次测量`"
    >
      <defs>
        <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="currentColor" stop-opacity="0.16" />
          <stop offset="100%" stop-color="currentColor" stop-opacity="0" />
        </linearGradient>
      </defs>

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

      <path :d="layout.area" :fill="`url(#${gradientId})`" />
      <path class="chart-line" :d="layout.line" />

      <line v-if="hovered" class="chart-guide" :x1="hovered.x" :x2="hovered.x" :y1="16" :y2="layout.baseline" />
      <circle
        v-for="(point, index) in layout.points"
        :key="`dot-${index}`"
        class="chart-dot"
        :class="{ 'is-active': active === index }"
        :cx="point.x"
        :cy="point.y"
        :r="active === index ? 4.5 : 2.8"
      />
    </svg>

    <p v-else class="absolute inset-0 flex items-center justify-center text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">
      暂无可画的数据
    </p>

    <div v-if="hovered" class="chart-tooltip" :style="tooltipStyle">
      <p class="chart-tooltip-title">{{ hovered.label }}</p>
      <p class="chart-tooltip-value">
        {{ hovered.value }}<span class="chart-tooltip-unit">{{ unit }}</span>
      </p>
    </div>
  </div>
</template>

<style scoped>
/* currentColor 由外层决定，深浅两套主题只换变量，不用在脚本里判断 mode */
div {
  color: var(--color-text-primary);
}

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
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chart-guide {
  stroke: var(--color-border);
  stroke-width: 1;
}

.chart-dot {
  fill: currentColor;
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
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.chart-tooltip-value {
  font-size: 14px;
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
