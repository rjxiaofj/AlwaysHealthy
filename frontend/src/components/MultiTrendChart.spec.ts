import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import MultiTrendChart from '@/components/MultiTrendChart.vue'

const WIDTH = 400

class ResizeObserverStub {
  private callback: ResizeObserverCallback

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }

  observe() {
    this.callback([{ contentRect: { width: WIDTH } }] as unknown as ResizeObserverEntry[], this as unknown as ResizeObserver)
  }

  unobserve() {}
  disconnect() {}
}

const series = [
  { key: 'systolic_bp', label: '收缩压', unit: 'mmHg', points: [{ measured_at: '2026-11-01T08:00:00', value: 120 }, { measured_at: '2026-11-02T08:00:00', value: 130 }] },
  { key: 'diastolic_bp', label: '舒张压', unit: 'mmHg', points: [{ measured_at: '2026-11-01T08:00:00', value: 80 }, { measured_at: '2026-11-02T08:00:00', value: 85 }] },
]

// 舒张压晚一天才开始测：宽 400 时共享日期轴是 x = 46 / 215 / 384
const misaligned = [
  {
    key: 'systolic_bp',
    label: '收缩压',
    unit: 'mmHg',
    points: [
      { measured_at: '2026-11-01T08:00:00', value: 120 },
      { measured_at: '2026-11-02T08:00:00', value: 130 },
      { measured_at: '2026-11-03T08:00:00', value: 125 },
    ],
  },
  {
    key: 'diastolic_bp',
    label: '舒张压',
    unit: 'mmHg',
    points: [
      { measured_at: '2026-11-02T08:00:00', value: 80 },
      { measured_at: '2026-11-03T08:00:00', value: 85 },
    ],
  },
]

beforeEach(() => {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
})

describe('多序列对比图组件', () => {
  it('没有序列时给占位文案', () => {
    const wrapper = mount(MultiTrendChart, { props: { series: [] } })
    expect(wrapper.find('svg').exists()).toBe(false)
    expect(wrapper.text()).toContain('暂无可画的数据')
  })

  it('每个序列各画一条折线，点的总数等于各序列点之和', async () => {
    const wrapper = mount(MultiTrendChart, { props: { series } })
    await nextTick()

    expect(wrapper.findAll('path.chart-line')).toHaveLength(2)
    expect(wrapper.findAll('circle')).toHaveLength(4)
  })

  it('不同序列用不同颜色描边', async () => {
    const wrapper = mount(MultiTrendChart, { props: { series } })
    await nextTick()

    const lines = wrapper.findAll('path.chart-line')
    expect(lines[0].attributes('stroke')).not.toBe(lines[1].attributes('stroke'))
  })

  it('图例列出所有序列的名称', async () => {
    const wrapper = mount(MultiTrendChart, { props: { series } })
    await nextTick()

    expect(wrapper.text()).toContain('收缩压')
    expect(wrapper.text()).toContain('舒张压')
  })

  it('悬停时在最近的点上给出提示，包含序列名、值与单位', async () => {
    const wrapper = mount(MultiTrendChart, { props: { series } })
    await nextTick()

    const root = wrapper.find('div.relative')
    await root.trigger('pointermove', { clientX: 200 })
    await nextTick()

    const tooltip = wrapper.find('.chart-tooltip')
    expect(tooltip.exists()).toBe(true)
    expect(tooltip.text()).toContain('mmHg')

    await root.trigger('pointerleave')
    await nextTick()
    expect(wrapper.find('.chart-tooltip').exists()).toBe(false)
  })

  it('离开时收起提示框', async () => {
    const wrapper = mount(MultiTrendChart, { props: { series } })
    await nextTick()

    const root = wrapper.find('div.relative')
    await root.trigger('pointermove', { clientX: 200 })
    await nextTick()
    expect(wrapper.find('.chart-tooltip').exists()).toBe(true)

    await root.trigger('pointerleave')
    await nextTick()
    expect(wrapper.find('.chart-tooltip').exists()).toBe(false)
  })
})

describe('多序列对比图 · 日期对齐后的提示', () => {
  it('渲染出的 SVG 里，同一天两条线的点共用同一个 cx', async () => {
    const wrapper = mount(MultiTrendChart, { props: { series: misaligned } })
    await nextTick()

    const dots = wrapper.findAll('circle')
    // 收缩压 3 个点在前、舒张压 2 个点在后；舒张压最早是 11-02
    expect(dots).toHaveLength(5)
    expect(dots[1].attributes('cx')).toBe(dots[3].attributes('cx'))
    // 而且 11-02 不该被拉到画布左端
    expect(Number(dots[3].attributes('cx'))).toBeGreaterThan(46)
  })

  it('悬停某一天时把各序列这一天的测量一起列出并标出日期', async () => {
    const wrapper = mount(MultiTrendChart, { props: { series: misaligned } })
    await nextTick()

    await wrapper.find('div.relative').trigger('pointermove', { clientX: 215 })
    await nextTick()

    const tooltip = wrapper.find('.chart-tooltip')
    expect(tooltip.exists()).toBe(true)
    expect(tooltip.text()).toContain('11-02')
    expect(tooltip.text()).toContain('收缩压')
    expect(tooltip.text()).toContain('舒张压')
    expect(tooltip.text()).toContain('130')
    expect(tooltip.text()).toContain('80')
  })

  it('某条序列当天没测就不编数据，提示里只列真正测过的', async () => {
    const wrapper = mount(MultiTrendChart, { props: { series: misaligned } })
    await nextTick()

    await wrapper.find('div.relative').trigger('pointermove', { clientX: 46 })
    await nextTick()

    const tooltip = wrapper.find('.chart-tooltip')
    expect(tooltip.text()).toContain('收缩压')
    expect(tooltip.text()).not.toContain('舒张压')
  })

  it('同一天的点跨序列一起高亮，视觉上能看出它们对齐了', async () => {
    const wrapper = mount(MultiTrendChart, { props: { series: misaligned } })
    await nextTick()

    await wrapper.find('div.relative').trigger('pointermove', { clientX: 215 })
    await nextTick()

    const enlarged = wrapper.findAll('circle').filter((dot) => dot.attributes('r') === '4.5')
    expect(enlarged).toHaveLength(2)
  })
})
