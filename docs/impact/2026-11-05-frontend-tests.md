# 影响分析：前端测试骨架

日期：2026-11-05

## 变更意图

前端此前零自动化测试，只有 `vue-tsc --noEmit` 与 `vite build` 两道静态关。类型能过、构建能过，但「401 之后到底刷新了几次」「顶部未读数和提醒中心是不是同一份数据」这类行为没人验证过，改一处要在浏览器里手点五六个页面才能确认。

本轮只补两处地基，不追覆盖率：

1. `src/api/client.ts`：令牌注入、401 刷新与重放、刷新失败清令牌、业务错误码透传。
2. `src/stores/reminders.ts`：并发加载合并成一次请求、标已读后未读数就地同步。

## 为什么是这两处

- `client.ts` 是全站唯一出口。它错了，所有页面一起错，且错法隐蔽：刷新失败不清令牌会让用户卡在「有令牌但一直 401」；重放没有终止条件会打成死循环。
- `reminders.ts` 是唯一被三处同时读的状态（顶部红点、首页未读列表、提醒中心）。它的 `inflight` 合并是因为布局与页面会同时进首页，两个并行的 `/reminders` 会各自生成同一批提醒撞唯一键。这条约束只写在注释里，没有测试守着，后来的人很容易顺手删掉。

## 影响面

| 范围 | 是否受影响 | 说明 |
|---|---|---|
| 后端接口 | 否 | 只读现有响应体形状，不改任何接口 |
| 前端运行时代码 | 否 | `client.ts`、`stores/reminders.ts` 未改动一个字符 |
| 前端构建产物 | 否 | `*.spec.ts` 不在 `vite build` 的入口图里，不进包 |
| 依赖 | 是 | 新增 `vitest`、`happy-dom` 两个 devDependency，不进生产依赖 |
| CI / 本地流程 | 是 | `npm test` 成为新增命令，`npm run build` 与 `type-check` 不变 |

## 关键取舍

1. 不引 `@vue/test-utils`。本轮不测组件，测的是模块行为，引了就是白付一层抽象。测试环境用 `happy-dom` 而非 `jsdom`：需要的是 `window.location.origin` 与 `localStorage`，happy-dom 启动快一个量级。
2. 测试文件与源码同目录（`*.spec.ts`），不放 `tests/` 目录。理由是 `tsconfig.json` 的 `include` 是 `src/**/*.ts`，同目录能被 `vue-tsc` 一并类型检查，测试里的类型写错构建前就暴露。
3. `tokens.save` 的入参必须是完整 `TokenPayload`。初版用 `as never` 绕过缺字段，等于把「调用方少传字段」这个真实风险静默掉，改成 `tokenPayload()` 工厂函数。
4. `reminders` 的 `inflight` 是模块级变量，跨用例会残留。每个用例前 `vi.resetModules()` 再动态 `import`，不复用同一个 store 实例。
5. 只断言可观察行为，不断言实现细节。比如「刷新失败清令牌」断言 `tokens.access === ''`，不断言内部调了几次 `tokens.clear()`。

## 验证

- `npm test`：2 个文件 13 项通过。
- `npx vue-tsc --noEmit`：无输出，spec 文件一并类型检查通过。
- `npm run build`：产物与改动前一致，`*.spec.ts` 未进包。

## 遗留

- 组件层（`PlansView`、`ChatView`、`ReportDetailView`）仍无测试。这三处渲染分支最多，但也最依赖真实接口形状，单测收益低于补接口契约测试，留到接口稳定后再做。
- 未配覆盖率阈值。当前只有两个文件，配阈值会给出虚高的数字。
