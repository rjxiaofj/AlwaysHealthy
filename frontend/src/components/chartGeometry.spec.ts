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

  it('横轴是各序列日期的并集，同一天的测量落在同一条竖线上', () => {
    const at = (day: string, value: number) => ({ measured_at: `2026-11-${day}T08:00:00`, value })
    const layout = buildMultiChart(
      [
        { key: 'a', label: 'A', points: [at('01', 1), at('02', 2), at('03', 3)] },
        // 这条线晚一天才开始测，旧实现会把它按点数重新铺满，11-02 就被拉到左端了
        { key: 'b', label: 'B', points: [at('02', 4), at('03', 5)] },
      ],
      { width: 600, height: 260 },
    )

    expect(layout.dates).toEqual(['2026-11-01', '2026-11-02', '2026-11-03'])
    // 两条线在 11-02 的点横坐标必须相等，否则「同一天一起涨了没有」根本没法看
    expect(layout.series[0].points[1].x).toBe(layout.series[1].points[0].x)
    expect(layout.series[1].points[0].x).toBeGreaterThan(46)
    expect(layout.series[1].points[1].x).toBeCloseTo(600 - 16)
  })

  it('共享轴取所有序列的日期，后一条序列多出来的日期也要算进来', () => {
    const at = (day: string, value: number) => ({ measured_at: `2026-11-${day}T08:00:00`, value })
    const layout = buildMultiChart(
      [
        // 故意让第一条最稀疏：只取首条序列的日期时，后两条线会被挤到中间
        { key: 'a', label: 'A', points: [at('01', 1)] },
        { key: 'b', label: 'B', points: [at('01', 2), at('02', 3), at('03', 4)] },
      ],
      { width: 600, height: 260 },
    )

    expect(layout.dates).toEqual(['2026-11-01', '2026-11-02', '2026-11-03'])
    expect(layout.series[0].points[0].x).toBeCloseTo(46)
    expect(layout.series[1].points[2].x).toBeCloseTo(600 - 16)
    expect(layout.xTicks[layout.xTicks.length - 1].text).toBe('11-03')
  })

  it('横轴刻度覆盖共享日期轴，不随某条稀疏序列缩短', () => {
    const layout = buildMultiChart(
      [series('sparse', '少', [1, 2]), series('dense', '多', [1, 2, 3, 4, 5])],
      { width: 600, height: 260 },
    )

    expect(layout.dates).toHaveLength(5)
    const lastTick = layout.xTicks[layout.xTicks.length - 1]
    expect(lastTick.x).toBeCloseTo(600 - 16)
    expect(lastTick.text).toBe('11-05')
  })

  it('缺测的日期留空档，横向间距按真实天数铺开', () => {
    const dense = ['01', '02', '03', '04', '05'].map((day, index) => ({
      measured_at: `2026-11-${day}T08:00:00`,
      value: index + 1,
    }))
    const layout = buildMultiChart(
      [
        { key: 'dense', label: '每天', points: dense },
        {
          key: 'sparse',
          label: '隔天',
          points: [
            { measured_at: '2026-11-01T08:00:00', value: 1 },
            { measured_at: '2026-11-05T08:00:00', value: 5 },
          ],
        },
      ],
      { width: 600, height: 260 },
    )

    expect(layout.dates).toHaveLength(5)
    expect(layout.series[1].points[0].x).toBeCloseTo(46)
    expect(layout.series[1].points[1].x).toBeCloseTo(600 - 16)
    // 中间那天在画布正中，说明空档没有被压缩成「相邻两点」
    expect(layout.series[0].points[2].x).toBeCloseTo((46 + (600 - 16)) / 2)
  })

  it('输入乱序时按日期排好，路径的 x 单调递增', () => {
    const layout = buildMultiChart(
      [
        {
          key: 'a',
          label: 'A',
          points: [
            { measured_at: '2026-11-03T08:00:00', value: 3 },
            { measured_at: '2026-11-01T08:00:00', value: 1 },
            { measured_at: '2026-11-02T08:00:00', value: 2 },
          ],
        },
      ],
      { width: 600, height: 260 },
    )

    const points = layout.series[0].points
    expect(points.map((item) => item.date)).toEqual(['2026-11-01', '2026-11-02', '2026-11-03'])
    expect(points[0].x).toBeLessThan(points[1].x)
    expect(points[1].x).toBeLessThan(points[2].x)
  })

  it('同一天多次测量共用一个横坐标，不擅自挑一条', () => {
    const layout = buildMultiChart(
      [
        {
          key: 'a',
          label: 'A',
          points: [
            { measured_at: '2026-11-01T08:00:00', value: 1 },
            { measured_at: '2026-11-01T20:00:00', value: 2 },
          ],
        },
      ],
      { width: 600, height: 260 },
    )

    expect(layout.dates).toEqual(['2026-11-01'])
    expect(layout.series[0].points).toHaveLength(2)
    expect(layout.series[0].points[0].x).toBe(layout.series[0].points[1].x)
    expect(layout.series[0].points[0].x).toBeCloseTo((46 + (600 - 16)) / 2)
    // 日期对齐后才会出现「相邻两点 x 相同」的零间距段：两点时是一条垂直直线
    expect(layout.series[0].line).toContain(' L ')
    expect(layout.series[0].line).not.toMatch(/NaN|Infinity/)
  })

  it('三点以上含零间距段时，贝塞尔控制点不会算出 NaN', () => {
    const layout = buildMultiChart(
      [
        {
          key: 'a',
          label: 'A',
          points: [
            { measured_at: '2026-11-01T08:00:00', value: 1 },
            { measured_at: '2026-11-01T20:00:00', value: 2 },
            { measured_at: '2026-11-02T08:00:00', value: 3 },
          ],
        },
      ],
      { width: 600, height: 260 },
    )

    const points = layout.series[0].points
    expect(points[0].x).toBe(points[1].x)
    expect(points[2].x).toBeGreaterThan(points[1].x)
    expect(layout.series[0].line).toContain(' C ')
    expect(layout.series[0].line).not.toMatch(/NaN|Infinity/)
  })

  it('全是无效值的序列不会把自己的日期带进共享横轴', () => {
    const ok = series('ok', 'O', [1, 2])
    const layout = buildMultiChart(
      [
        { key: 'bad', label: 'B', points: [{ measured_at: '2026-10-01T08:00:00', value: Number.NaN }] },
        ok,
      ],
      { width: 600, height: 260 },
    )

    expect(layout.dates).toEqual(['2026-11-01', '2026-11-02'])
    expect(layout.series[0].points[0].x).toBeCloseTo(46)
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
