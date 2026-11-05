# 影响分析：打包体积进 CI

日期：2026-11-05

## 为什么

echarts 那 466 kB 是手工翻构建输出发现的，删掉之后也没有东西拦着它再回来。前端体积目前只有「人看一眼构建日志」这一道，等于没有。

## 做法

`frontend/scripts/check-bundle-size.mjs`，`npm run size`：

- 读 `dist/assets`，用 `zlib.gzipSync(level: 9)` 算每个文件的 gzip 大小。
- **首屏** = `dist/index.html` 里直接引用的那些文件（entry 与 `modulepreload`）。路由 chunk 不算，它们要等用户点进去才下。
- 汇总四项：`firstLoad`、`totalJs`、`totalCss`、`singleChunk`（最大的那个 JS）。
- 与 `frontend/bundle-budget.json` 比，超了退出码 1，并把「实测 vs 预算」打出来。
- `--report` 只打印不判，调预算时用。

CI 在 `npm run build` 之后加一步 `npm run size`。

## 预算怎么定

按当前实测留约 15–20% 余量：

| 项 | 实测（gzip） | 预算 | 余量 |
|---|---|---|---|
| firstLoad | 48.7 kB | 58 kB | 9.3 kB |
| totalJs | 84.0 kB | 100 kB | 16.0 kB |
| totalCss | 4.8 kB | 8 kB | 3.2 kB |
| singleChunk | 44.3 kB | 60 kB | 15.7 kB |

`singleChunk` 现在是入口自己（44.3 kB）。60 kB 的红线意味着单个路由 chunk 不可能再塞进一个图表库——真塞进来会立刻红。

## 验证

把 `firstLoad` 改成 10 kB，脚本报 `firstLoad: 48.7 kB > 预算 10 kB` 并退出 1；改回来退出 0。

## 取舍

- 只量 gzip，不量解析/执行时间。体积不等于性能，但在这份应用里两者高度相关（首屏只有一个入口 chunk）。
- 首屏判定基于 `index.html` 的引用列表。如果哪天改成运行时动态 `import()` 入口，这条会失真。
- 预算写死数字，没有按路由细分。真出现「某个路由页太重」需要单独设限时再加。
