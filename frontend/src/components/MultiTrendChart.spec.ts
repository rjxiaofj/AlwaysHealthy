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
