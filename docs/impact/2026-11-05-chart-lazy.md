# 影响分析：图表组件改成按需加载

日期：2026-11-05

## 现象

`TrendChart.vue` 用的是 `echarts/core` 加按需注册（LineChart、Grid、Tooltip、Canvas），这部分没问题。问题是它的引入方式：`DashboardView` 与 `TrendsView` 都是 `import TrendChart from '@/components/TrendChart.vue'`，静态引入。

构建产物里这个 chunk 是 466.48 kB（gzip 157.25 kB），比其余所有页面加起来还大。静态引入意味着它会跟着路由 chunk 一起被请求——用户进首页就在下这 466 kB，哪怕他一条指标都没录过。

而首页的模板本来就写着 `v-if="selectedTrend && selectedTrend.points.length"`：没有数据时渲染的是 `EmptyState`，图表组件根本不挂载。也就是说，新用户下完 466 kB 之后看到的是「还没有指标记录」，这一趟白跑。

演示环境里更明显：新注册的账号第一次进首页，这是最常走的一条路径。

## 做法

两处改 `defineAsyncComponent(() => import('@/components/TrendChart.vue'))`，模板里把 `v-if` 从组件挪到外层 `div`，外层带 `min-h-[260px]`。

`v-if` 挪到外层是必须的：原来 `v-if` 挂在组件上，没有数据时组件不渲染；改成按需加载后，`v-if` 若留在组件上，组件被渲染时才触发 chunk 下载，下载完之前 DOM 里什么都没有，那 260px 的高度会塌一下再弹回来。外层的 `min-h` 把这段高度先占住。

`EmptyState` 的 `v-else` 位置跟着变，与新的 `div` 配对。

## 体积

构建产物对比，首屏指进入 `/` 时实际请求的 JS：

| 项 | 改动前 | 改动后 |
|---|---|---|
| 入口 chunk | 115.65 kB / gzip 45.37 kB | 117.78 kB / gzip 46.20 kB |
| API 层 | 在入口里 | 2.63 kB / gzip 1.01 kB |
| DashboardView | 8.13 kB / gzip 3.40 kB | 8.13 kB / gzip 3.40 kB |
| TrendChart | 466.48 kB / gzip 157.25 kB | 有数据才加载 |
| 首屏合计（无指标的新用户） | 约 590 kB / gzip 202.6 kB | 约 129 kB / gzip 50.6 kB |

入口从 115.65 涨到 117.78、外加拆出 2.63 kB 的 API chunk，合计多约 4.8 kB。这是拆包本身的成本（多一个 chunk 的 import/export 桩、preload 辅助函数），换来的是 466 kB 移出首屏。有指标的用户总量基本不变，多那几 kB。

`dist/assets/DashboardView-*.js` 里确认是 `import("./TrendChart-*.js")`，不是静态 import。

## 影响面

| 范围 | 是否受影响 | 说明 |
|---|---|---|
| 接口 | 否 | 只改前端 |
| 首屏请求 | 是 | 无指标时不请求 echarts |
| 有指标时 | 是 | 多一次网络往返，首次绘制晚一点；本地与内网可忽略，弱网能看到 260px 的占位区 |
| 测试 | 否 | 组件没有渲染测试，这一层改动没有自动化覆盖 |
| 构建 | 是 | 产物 chunk 划分变了，API 层被单独拆出 |

## 验证

- `npm test` 89 项通过。
- `vue-tsc --noEmit`、`npm run build` 通过。
- 产物核对：`index.html` 只引入口；`DashboardView` 与 `TrendsView` 两个 chunk 里指向 TrendChart 的都是 `import("./TrendChart-*.js")`。

## 遗留

- 这一改没有测试兜住。要真验，得用 Playwright 之类的浏览器测试统计首屏请求，当前没有这套设施。体积数字是构建输出，不是运行时观测。
- `min-h-[260px]` 与 `TrendChart` 里的 `h-[260px]` 是两处写死的高度，改一处忘另一处会错位。想彻底解决可以把它变成 CSS 变量或用 `aspect-ratio`。
- echarts 仍然占 466 kB。真要继续压，只有两条路：换成手写 SVG 折线（这条曲线只有一条线加虚线网格，手写大约一百多行，能省掉整个依赖），或者换更轻的图表库。前者收益最大，但要重做交互，暂不动。
