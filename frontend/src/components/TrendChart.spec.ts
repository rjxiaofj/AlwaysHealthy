import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import TrendChart from '@/components/TrendChart.vue'

/**
 * 组件层的守卫。几何计算已经有单测（chartGeometry.spec.ts），这里只看
 * 「算出来的数字有没有真的变成 SVG」以及悬停交互——那部分纯函数覆盖不到。
 */

const WIDTH = 400

class ResizeObserverStub {
  private callback: ResizeObserverCallback

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }

  observe() {
    // happy-dom 没有布局，直接给一个固定宽度，让组件按 400px 算坐标
    this.callback([{ contentRect: { width: WIDTH } }] as unknown as ResizeObserverEntry[], this as unknown as ResizeObserver)
  }

  unobserve() {}

  disconnect() {}
}

const points = [
  { measured_at: '2026-11-01T08:00:00', value: 118 },
  { measured_at: '2026-11-02T08:00:00', value: 132 },
  { measured_at: '2026-11-03T08:00:00', value: 126 },
]

function mountChart(input = points) {
  return mount(TrendChart, {
    props: { points: input, label: '收缩压', unit: 'mmHg' },
  })
}

beforeEach(() => {
  // 组件挂载时会 new ResizeObserver，happy-dom 里没有这个全局对象
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
})

describe('趋势图组件', () => {
  it('没有数据时给占位文案，不画空坐标系', () => {
    const wrapper = mountChart([])

    expect(wrapper.find('svg').exists()).toBe(false)
    expect(wrapper.text()).toContain('暂无可画的数据')
  })

  it('有数据时把每个测量点画成圆点，并画出折线路径', async () => {
    const wrapper = mountChart()
    await nextTick()

    expect(wrapper.findAll('circle')).toHaveLength(3)
    const line = wrapper.find('path.chart-line')
    expect(line.exists()).toBe(true)
    expect(line.attributes('d')).toMatch(/^M [\d.]+ [\d.]+ C /)
  })

  it('宽度取自容器实测值，不是写死的', async () => {
    const wrapper = mountChart()
    await nextTick()

    expect(wrapper.find('svg').attributes('width')).toBe(String(WIDTH))
    // 纵轴留白 46、右侧 16，最后一个点贴右边
    const dots = wrapper.findAll('circle')
    expect(Number(dots[dots.length - 1].attributes('cx'))).toBeCloseTo(WIDTH - 16, 0)
  })

  it('横向移动时在最近的点上给出提示，离开就收起', async () => {
    const wrapper = mountChart()
    await nextTick()

    const root = wrapper.find('div')
    await root.trigger('pointermove', { clientX: 215 })
    await nextTick()

    const tooltip = wrapper.find('.chart-tooltip')
    expect(tooltip.exists()).toBe(true)
    expect(tooltip.text()).toContain('11-02')
    expect(tooltip.text()).toContain('132')
    expect(tooltip.text()).toContain('mmHg')

    await root.trigger('pointerleave')
    await nextTick()
    expect(wrapper.find('.chart-tooltip').exists()).toBe(false)
  })

  it('提示框贴着左右边时向内收，不会被容器切掉', async () => {
    const wrapper = mountChart()
    await nextTick()

    const root = wrapper.find('div')
    await root.trigger('pointermove', { clientX: 0 })
    await nextTick()

    const left = Number.parseFloat((wrapper.find('.chart-tooltip').element as HTMLElement).style.left)
    expect(left).toBeGreaterThanOrEqual(64)
  })

  it('坐标标签不会画到画布外面', async () => {
    const wrapper = mountChart()
    await nextTick()
    const height = Number(wrapper.find('svg').attributes('height'))

    for (const label of wrapper.findAll('text.chart-label')) {
      const y = Number(label.attributes('y'))
      expect(y).toBeGreaterThan(0)
      expect(y).toBeLessThanOrEqual(height)
    }
  })
})
