/**
 * 趋势图的几何计算。
 *
 * 只有一条折线加虚线网格，用 echarts 要背 466 kB（gzip 157）。这里把「值 → 屏幕坐标」
 * 这件事算成纯数据，组件只负责把数字拼进 SVG，所以能写单测。
 */

export interface ChartPointInput {
  measured_at: string
  value: number
}

/** 多序列对比里的一条线。key 用于稳定 key 与图例区分，color 由组件按顺序分配。 */
export interface ChartSeriesInput {
  key: string
  label: string
  points: ChartPointInput[]
}

export interface ChartPointLayout {
  x: number
  y: number
  value: number
  label: string
}

export interface ChartSeriesLayout {
  key: string
  label: string
  points: ChartPointLayout[]
  line: string
  area: string
}

export interface ChartTick {
  x: number
  text: string
  /** 首尾刻度靠边，用 start/end 锚点防止被画布裁掉 */
  anchor: 'start' | 'middle' | 'end'
}

export interface ChartYAxisTick {
  y: number
  text: string
}

export interface ChartLayout {
  width: number
  height: number
  points: ChartPointLayout[]
  /** 折线（单调三次贝塞尔，不过冲） */
  line: string
  /** 折线 + 落到底边的闭合路径，用来填渐变 */
  area: string
  baseline: number
  yTicks: ChartYAxisTick[]
  xTicks: ChartTick[]
}

/** 多序列对比布局。Y 轴按所有序列的全局 min/max 统一缩放，各序列独立铺满横轴。 */
export interface MultiChartLayout {
  width: number
  height: number
  series: ChartSeriesLayout[]
  baseline: number
  yTicks: ChartYAxisTick[]
  xTicks: ChartTick[]
}

const PADDING = { left: 46, right: 16, top: 16, bottom: 30 }

const emptyLayout = (width: number, height: number): ChartLayout => ({
  width,
  height,
  points: [],
  line: '',
  area: '',
  baseline: 0,
  yTicks: [],
  xTicks: [],
})

const round = (value: number): number => Math.round(value * 1e6) / 1e6

/** 刻度间隔按 1 / 2 / 2.5 / 5 / 10 取整，避免出现 0.3333 这种读不出来的数 */
export function niceDomain(min: number, max: number): { min: number; max: number; step: number; ticks: number[] } {
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return { min: 0, max: 1, step: 0.5, ticks: [0, 0.5, 1] }
  }

  let low = min
  let high = max
  if (low === high) {
    // 只有一次测量时，上下各撑一点，否则整条线贴在画布边上
    const pad = Math.abs(low) * 0.1 || 1
    low -= pad
    high += pad
  }

  const rawStep = (high - low) / 4
  const magnitude = 10 ** Math.floor(Math.log10(rawStep))
  const normalized = rawStep / magnitude
  const factor = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10
  const step = factor * magnitude

  const startIndex = Math.floor(low / step)
  const endIndex = Math.ceil(high / step)
  const ticks: number[] = []
  for (let index = startIndex; index <= endIndex; index += 1) {
    ticks.push(round(index * step))
  }

  return {
    min: ticks[0],
    max: ticks[ticks.length - 1],
    step,
    // 上面按 4 段取步长，正常是 5 个刻度；真出现病态输入也不让网格铺满屏幕
    ticks: ticks.length > 12 ? [ticks[0], ticks[ticks.length - 1]] : ticks,
  }
}

/** 刻度文字：步长小于 1 才有小数位，免得「7.0 小时」这种多余精度 */
export function formatTick(value: number, step: number): string {
  const decimals = step >= 1 ? 0 : step >= 0.1 ? 1 : 2
  return value.toFixed(decimals)
}

/** `2026-11-05T08:00:00` → `11-05`，跟前端别处一致 */
function formatDay(measuredAt: string): string {
  const day = measuredAt.slice(5, 10)
  return day.length === 5 ? day : measuredAt
}

/**
 * 单调三次贝塞尔的控制点斜率（Fritsch–Carlson）。
 *
 * 用普通 Catmull-Rom 平滑会在两个相近测量值之间鼓出比原始数据更高的峰，
 * 指标图上等于凭空画出一个没测到过的值。这套算法保证曲线不越过相邻点。
 */
function monotoneSlopes(points: ChartPointLayout[]): number[] {
  const count = points.length
  const gaps: number[] = []
  const deltas: number[] = []

  for (let index = 0; index < count - 1; index += 1) {
    const gap = points[index + 1].x - points[index].x
    gaps.push(gap)
    deltas.push(gap === 0 ? 0 : (points[index + 1].y - points[index].y) / gap)
  }

  const slopes = new Array<number>(count)
  slopes[0] = deltas[0]
  slopes[count - 1] = deltas[count - 2]
  for (let index = 1; index < count - 1; index += 1) {
    // 拐点：两侧方向相反或有一侧是平的，斜率取 0，曲线在此不再冲出去
    slopes[index] = deltas[index - 1] * deltas[index] <= 0 ? 0 : (deltas[index - 1] + deltas[index]) / 2
  }

  for (let index = 0; index < count - 1; index += 1) {
    if (deltas[index] === 0) {
      slopes[index] = 0
      slopes[index + 1] = 0
      continue
    }
    const left = slopes[index] / deltas[index]
    const right = slopes[index + 1] / deltas[index]
    const magnitude = left * left + right * right
    if (magnitude > 9) {
      const scale = 3 / Math.sqrt(magnitude)
      slopes[index] = scale * left * deltas[index]
      slopes[index + 1] = scale * right * deltas[index]
    }
  }

  return slopes
}

function smoothPath(points: ChartPointLayout[]): string {
  if (!points.length) return ''
  if (points.length === 1) return `M ${round(points[0].x)} ${round(points[0].y)}`
  if (points.length === 2) {
    return `M ${round(points[0].x)} ${round(points[0].y)} L ${round(points[1].x)} ${round(points[1].y)}`
  }

  const slopes = monotoneSlopes(points)
  let path = `M ${round(points[0].x)} ${round(points[0].y)}`
  for (let index = 0; index < points.length - 1; index += 1) {
    const from = points[index]
    const to = points[index + 1]
    const gap = to.x - from.x
    const c1x = round(from.x + gap / 3)
    const c1y = round(from.y + (slopes[index] * gap) / 3)
    const c2x = round(to.x - gap / 3)
    const c2y = round(to.y - (slopes[index + 1] * gap) / 3)
    path += ` C ${c1x} ${c1y} ${c2x} ${c2y} ${round(to.x)} ${round(to.y)}`
  }
  return path
}

function buildXTicks(points: ChartPointLayout[], plotWidth: number): ChartTick[] {
  const maxLabels = Math.max(2, Math.floor(plotWidth / 56))
  const stride = Math.max(1, Math.ceil(points.length / maxLabels))
  const ticks: ChartTick[] = []

  for (let index = 0; index < points.length; index += stride) {
    ticks.push({
      x: points[index].x,
      text: points[index].label,
      anchor: index === 0 ? 'start' : 'middle',
    })
  }

  const last = points[points.length - 1]
  const tail = ticks[ticks.length - 1]
  if (tail.x !== last.x) {
    // 末尾这个点最重要（最新一次测量），挤在一起时宁愿少标一个中间的也要留着它
    if (last.x - tail.x < 44) ticks.pop()
    ticks.push({ x: last.x, text: last.label, anchor: 'end' })
  }

  return ticks
}

export function buildChart(
  input: readonly ChartPointInput[],
  size: { width: number; height: number },
): ChartLayout {
  const width = Math.max(0, size.width)
  const height = Math.max(0, size.height)
  const points = input.filter((item) => Number.isFinite(item.value))

  if (!points.length || width <= PADDING.left + PADDING.right || height <= PADDING.top + PADDING.bottom) {
    return emptyLayout(width, height)
  }

  const plotLeft = PADDING.left
  const plotRight = width - PADDING.right
  const plotTop = PADDING.top
  const plotBottom = height - PADDING.bottom
  const plotWidth = plotRight - plotLeft
  const plotHeight = plotBottom - plotTop

  const values = points.map((item) => item.value)
  const domain = niceDomain(Math.min(...values), Math.max(...values))
  const span = domain.max - domain.min || 1
  const toY = (value: number) => plotBottom - ((value - domain.min) / span) * plotHeight

  const step = points.length === 1 ? 0 : plotWidth / (points.length - 1)
  const laidOut: ChartPointLayout[] = points.map((item, index) => ({
    x: points.length === 1 ? plotLeft + plotWidth / 2 : round(plotLeft + index * step),
    y: round(toY(item.value)),
    value: item.value,
    label: formatDay(item.measured_at),
  }))

  const line = smoothPath(laidOut)
  const first = laidOut[0]
  const last = laidOut[laidOut.length - 1]

  return {
    width,
    height,
    points: laidOut,
    line,
    area: `${line} L ${round(last.x)} ${round(plotBottom)} L ${round(first.x)} ${round(plotBottom)} Z`,
    baseline: round(plotBottom),
    yTicks: domain.ticks.map((value) => ({ y: round(toY(value)), text: formatTick(value, domain.step) })),
    xTicks: buildXTicks(laidOut, plotWidth),
  }
}

/** 鼠标横坐标离哪个点最近，用来决定提示框落在哪。空图返回 null */
export function nearestIndex(points: readonly { x: number }[], targetX: number): number | null {
  if (!points.length) return null
  let best = 0
  let bestDistance = Math.abs(points[0].x - targetX)
  for (let index = 1; index < points.length; index += 1) {
    const distance = Math.abs(points[index].x - targetX)
    if (distance < bestDistance) {
      best = index
      bestDistance = distance
    }
  }
  return best
}

/**
 * 多指标同图对比的几何计算。
 *
 * 跟单序列不同：这里各条线的值域可能差很远（收缩压 130 vs 体重 75），所以 Y 轴按
 * 所有序列的全局 min/max 统一缩放——这样同量纲的「收缩压 vs 舒张压」能直接看谁高谁
 * 低、趋势是否同步。横轴各序列独立铺满，不做日期对齐：多指标通常同时测，点数接近，
 * 对齐的复杂度不值当；点数不同时仍能比趋势方向。
 */
export function buildMultiChart(
  seriesInput: readonly ChartSeriesInput[],
  size: { width: number; height: number },
): MultiChartLayout {
  const width = Math.max(0, size.width)
  const height = Math.max(0, size.height)
  const empty: MultiChartLayout = { width, height, series: [], baseline: 0, yTicks: [], xTicks: [] }

  const series = seriesInput
    .map((item) => ({
      ...item,
      points: item.points.filter((point) => Number.isFinite(point.value)),
    }))
    .filter((item) => item.points.length > 0)

  if (!series.length || width <= PADDING.left + PADDING.right || height <= PADDING.top + PADDING.bottom) {
    return empty
  }

  const plotLeft = PADDING.left
  const plotRight = width - PADDING.right
  const plotTop = PADDING.top
  const plotBottom = height - PADDING.bottom
  const plotWidth = plotRight - plotLeft
  const plotHeight = plotBottom - plotTop

  // 全局值域：所有序列一起决定 Y 轴，保证同量纲下能直接比高低
  const allValues = series.flatMap((item) => item.points.map((point) => point.value))
  const domain = niceDomain(Math.min(...allValues), Math.max(...allValues))
  const span = domain.max - domain.min || 1
  const toY = (value: number) => plotBottom - ((value - domain.min) / span) * plotHeight

  const laidOut = series.map((item) => {
    const count = item.points.length
    const step = count === 1 ? 0 : plotWidth / (count - 1)
    const points: ChartPointLayout[] = item.points.map((point, index) => ({
      x: count === 1 ? plotLeft + plotWidth / 2 : round(plotLeft + index * step),
      y: round(toY(point.value)),
      value: point.value,
      label: formatDay(point.measured_at),
    }))
    return { key: item.key, label: item.label, points, line: smoothPath(points), area: '' }
  })

  // 横轴刻度用点数最多的那条序列，避免因某条序列点太少而空出大半截
  const densest = laidOut.reduce((best, item) => (item.points.length > best.points.length ? item : best), laidOut[0])

  return {
    width,
    height,
    series: laidOut,
    baseline: round(plotBottom),
    yTicks: domain.ticks.map((value) => ({ y: round(toY(value)), text: formatTick(value, domain.step) })),
    xTicks: buildXTicks(densest.points, plotWidth),
  }
}
