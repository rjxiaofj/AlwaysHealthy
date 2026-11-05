import { describe, expect, it } from 'vitest'

import { buildChart, buildMultiChart, formatTick, nearestIndex, niceDomain } from '@/components/chartGeometry'

const point = (day: string, value: number) => ({ measured_at: `2026-11-${day}T08:00:00`, value })

/** 把 `M x y C ...` 拆成逐段的三次贝塞尔，方便断言曲线真的经过关键点 */
function cubicSegments(path: string) {
  const segments: Array<{ from: [number, number]; c1: [number, number]; c2: [number, number]; to: [number, number] }> = []
  const start = /^M ([-\d.]+) ([-\d.]+)/.exec(path)
  if (!start) return segments

  let cursor: [number, number] = [Number(start[1]), Number(start[2])]
  const pattern = /C ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(path))) {
    const to: [number, number] = [Number(match[5]), Number(match[6])]
    segments.push({
      from: cursor,
      c1: [Number(match[1]), Number(match[2])],
      c2: [Number(match[3]), Number(match[4])],
      to,
    })
    cursor = to
  }
  return segments
}

describe('趋势图几何', () => {
  it('没有数据时返回空布局，不画空框', () => {
    const layout = buildChart([], { width: 600, height: 260 })

    expect(layout.points).toEqual([])
    expect(layout.line).toBe('')
    expect(layout.yTicks).toEqual([])
  })

  it('容器宽度还没量出来时不画，免得刻度挤成一团', () => {
    const layout = buildChart([point('01', 1)], { width: 40, height: 260 })

    expect(layout.points).toHaveLength(0)
  })

  it('过滤掉非有限值，否则坐标算出来是 NaN，整条路径作废', () => {
    const layout = buildChart(
      [point('01', 70), { measured_at: '2026-11-02T08:00:00', value: Number.NaN }, point('03', 72)],
      { width: 600, height: 260 },
    )

    expect(layout.points).toHaveLength(2)
    expect(layout.line).not.toContain('NaN')
  })

  it('只有一次测量时点落在画布中间，不贴在左边', () => {
    const layout = buildChart([point('01', 70)], { width: 600, height: 260 })

    expect(layout.points).toHaveLength(1)
    expect(layout.points[0].x).toBeCloseTo(46 + (600 - 46 - 16) / 2)
    expect(layout.line).toMatch(/^M [\d.]+ [\d.]+$/)
  })

  it('纵轴刻度包住所有数据，且首尾都落在画布内', () => {
    const layout = buildChart([point('01', 118), point('02', 132), point('03', 126)], { width: 600, height: 260 })
    const ticks = layout.yTicks.map((tick) => Number(tick.text))

    expect(Math.min(...ticks)).toBeLessThanOrEqual(118)
    expect(Math.max(...ticks)).toBeGreaterThanOrEqual(132)
    for (const tick of layout.yTicks) {
      expect(tick.y).toBeGreaterThanOrEqual(16)
      expect(tick.y).toBeLessThanOrEqual(layout.baseline)
    }
  })

  it('所有值一样时纵轴撑开，线不会贴在底边', () => {
    const layout = buildChart([point('01', 70), point('02', 70)], { width: 600, height: 260 })

    for (const item of layout.points) {
      expect(item.y).toBeLessThan(layout.baseline)
      expect(item.y).toBeGreaterThan(16)
    }
  })

  it('曲线起点和终点就是首尾两个测量值', () => {
    const layout = buildChart([point('01', 118), point('02', 132), point('03', 126), point('04', 130)], {
      width: 600,
      height: 260,
    })
    const segments = cubicSegments(layout.line)
    const first = layout.points[0]
    const last = layout.points[layout.points.length - 1]

    expect(segments).toHaveLength(3)
    expect(segments[0].from[0]).toBeCloseTo(first.x)
    expect(segments[0].from[1]).toBeCloseTo(first.y)
    expect(segments[2].to[0]).toBeCloseTo(last.x)
    expect(segments[2].to[1]).toBeCloseTo(last.y)
  })

  it('相邻两点的曲线不越过它们的纵坐标——平滑不能凭空画出一个没测到的峰', () => {
    // 中间一个尖峰，普通 Catmull-Rom 会在两侧鼓出去
    const layout = buildChart(
      [point('01', 118), point('02', 119), point('03', 165), point('04', 120), point('05', 118)],
      { width: 600, height: 260 },
    )

    for (const segment of cubicSegments(layout.line)) {
      const low = Math.min(segment.from[1], segment.to[1])
      const high = Math.max(segment.from[1], segment.to[1])
      const epsilon = 0.01
      expect(segment.c1[1]).toBeGreaterThanOrEqual(low - epsilon)
      expect(segment.c1[1]).toBeLessThanOrEqual(high + epsilon)
      expect(segment.c2[1]).toBeGreaterThanOrEqual(low - epsilon)
      expect(segment.c2[1]).toBeLessThanOrEqual(high + epsilon)
    }
  })

  it('填充区域从折线闭合到底边', () => {
    const layout = buildChart([point('01', 70), point('02', 72)], { width: 600, height: 260 })

    expect(layout.area.startsWith(layout.line)).toBe(true)
    expect(layout.area.endsWith('Z')).toBe(true)
    expect(layout.area).toContain(String(layout.baseline))
  })

  it('横轴标签太多时隔几个取一个，但首尾一定留着', () => {
    const points = Array.from({ length: 30 }, (_, index) => point(String(index + 1).padStart(2, '0'), 70 + index))
    const layout = buildChart(points, { width: 360, height: 260 })

    expect(layout.xTicks.length).toBeLessThanOrEqual(8)
    expect(layout.xTicks[0].anchor).toBe('start')
    expect(layout.xTicks[layout.xTicks.length - 1].anchor).toBe('end')
    expect(layout.xTicks[layout.xTicks.length - 1].x).toBeCloseTo(layout.points[layout.points.length - 1].x)
  })

  it('点少的时候每个都标，不会被抽稀', () => {
    const layout = buildChart([point('01', 70), point('02', 72), point('03', 71)], { width: 600, height: 260 })

    expect(layout.xTicks.map((tick) => tick.text)).toEqual(['11-01', '11-02', '11-03'])
  })
})

describe('纵轴刻度取整', () => {
  it('刻度落在 1/2/2.5/5/10 的整数倍上', () => {
    const domain = niceDomain(63.2, 71.8)

    expect(domain.step).toBe(2.5)
    expect(domain.ticks).toEqual([62.5, 65, 67.5, 70, 72.5])
  })

  it('区间很小时用两位小数，不会全挤成同一个整数', () => {
    const domain = niceDomain(0.42, 0.55)

    expect(new Set(domain.ticks).size).toBeGreaterThan(1)
    expect(formatTick(domain.ticks[1], domain.step)).toMatch(/^0\.\d{2}$/)
  })

  it('步长大于等于 1 时不带小数位', () => {
    expect(formatTick(70, 2.5)).toBe('70')
    expect(formatTick(7.5, 0.5)).toBe('7.5')
  })

  it('负值也能正常分格', () => {
    const domain = niceDomain(-8, -2)

    expect(domain.min).toBeLessThanOrEqual(-8)
    expect(domain.max).toBeGreaterThanOrEqual(-2)
  })
})

describe('提示框选点', () => {
  const points = [{ x: 46 }, { x: 200 }, { x: 354 }]

  it('取横坐标最近的那个点', () => {
    expect(nearestIndex(points, 50)).toBe(0)
    expect(nearestIndex(points, 210)).toBe(1)
    expect(nearestIndex(points, 340)).toBe(2)
  })

  it('越过两端时夹到首尾', () => {
    expect(nearestIndex(points, -100)).toBe(0)
    expect(nearestIndex(points, 9999)).toBe(2)
  })

  it('没有点时返回 null，组件据此不显示提示框', () => {
    expect(nearestIndex([], 100)).toBeNull()
  })
})

describe('多序列对比几何', () => {
  const series = (key: string, label: string, values: number[]) => ({
    key,
    label,
    points: values.map((value, index) => ({ measured_at: `2026-11-${String(index + 1).padStart(2, '0')}T08:00:00`, value })),
  })

  it('空序列或全空值时返回空布局', () => {
    expect(buildMultiChart([], { width: 600, height: 260 }).series).toEqual([])
    expect(buildMultiChart([series('a', 'A', [Number.NaN])], { width: 600, height: 260 }).series).toEqual([])
  })

  it('过滤掉没有有效点的序列，保留有数据的', () => {
    const layout = buildMultiChart(
      [series('empty', '空', [Number.NaN]), series('ok', '有', [120, 122])],
      { width: 600, height: 260 },
    )

    expect(layout.series.map((item) => item.key)).toEqual(['ok'])
  })

  it('Y 轴按所有序列的全局值域缩放，同量纲下能直接比高低', () => {
    const layout = buildMultiChart(
      [series('sys', '收缩压', [120, 130, 125]), series('dia', '舒张压', [80, 85, 82])],
      { width: 600, height: 260 },
    )

    // 收缩压 130 是所有值里最大的，应该画得最高（y 最小）
    const sysMax = layout.series[0].points[1]
    const diaMax = layout.series[1].points[1]
    expect(sysMax.y).toBeLessThan(diaMax.y)
    // 刻度包住所有值
    const ticks = layout.yTicks.map((tick) => Number(tick.text))
    expect(Math.min(...ticks)).toBeLessThanOrEqual(80)
    expect(Math.max(...ticks)).toBeGreaterThanOrEqual(130)
  })

  it('每条序列各自铺满横轴，首尾点在画布两端', () => {
    const layout = buildMultiChart(
      [series('a', 'A', [1, 2, 3]), series('b', 'B', [5, 6])],
      { width: 600, height: 260 },
    )

    for (const item of layout.series) {
      const first = item.points[0]
      const last = item.points[item.points.length - 1]
      expect(first.x).toBeCloseTo(46)
      expect(last.x).toBeCloseTo(600 - 16)
    }
  })

  it('横轴刻度用点数最多的序列，避免空出大半截', () => {
    const layout = buildMultiChart(
      [series('sparse', '少', [1, 2]), series('dense', '多', [1, 2, 3, 4, 5])],
      { width: 600, height: 260 },
    )

    const lastTick = layout.xTicks[layout.xTicks.length - 1]
    expect(lastTick.x).toBeCloseTo(layout.series[1].points[4].x)
  })

  it('不同序列值域差异大时也能正常缩放（不假设同量纲）', () => {
    const layout = buildMultiChart(
      [series('bp', '血压', [130, 135]), series('weight', '体重', [70, 71])],
      { width: 600, height: 260 },
    )

    // 两条线都有点，体重 70 在全局值域里偏低，画得比血压低
    const bp = layout.series[0].points[0]
    const weight = layout.series[1].points[0]
    expect(bp.y).toBeLessThan(weight.y)
  })
})
