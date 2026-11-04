<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { MetricPoint } from '@/api/types'
import { useThemeStore } from '@/stores/theme'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{ points: MetricPoint[]; label: string; unit: string }>()
const theme = useThemeStore()
const holder = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!holder.value) return
  if (!chart) chart = echarts.init(holder.value)
  const dark = theme.mode === 'dark'
  const line = dark ? '#F4F5F7' : '#17191D'
  const axis = dark ? 'rgba(255,255,255,0.18)' : 'rgba(35,40,50,0.12)'
  const muted = dark ? '#969EAA' : '#858B96'

  chart.setOption(
    {
      grid: { left: 44, right: 18, top: 28, bottom: 34 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: dark ? 'rgba(43,49,59,0.94)' : 'rgba(255,255,255,0.94)',
        borderColor: axis,
        textStyle: { color: dark ? '#F4F5F7' : '#17191D', fontSize: 12 },
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: props.points.map((item) => item.measured_at.slice(5, 10)),
        axisLine: { lineStyle: { color: axis } },
        axisTick: { show: false },
        axisLabel: { color: muted, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { color: axis, type: 'dashed' } },
        axisLabel: { color: muted, fontSize: 11 },
      },
      series: [
        {
          name: `${props.label}（${props.unit}）`,
          type: 'line',
          smooth: 0.3,
          symbolSize: 5,
          data: props.points.map((item) => item.value),
          lineStyle: { width: 2, color: line },
          itemStyle: { color: line },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: dark ? 'rgba(244,245,247,0.16)' : 'rgba(23,25,29,0.10)' },
              { offset: 1, color: 'rgba(23,25,29,0)' },
            ]),
          },
        },
      ],
    },
    true,
  )
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})

watch(() => [props.points, theme.mode], render, { deep: true })
</script>

<template>
  <div ref="holder" class="h-[260px] w-full" />
</template>
