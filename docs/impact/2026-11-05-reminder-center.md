# 提醒中心影响分析

日期 2026-11-05。性质：补页面缺口。顶部「待办提醒」带着未读数，点进去却回到首页；Dashboard 的未读列表只显示三条，标完已读之后这些提醒就再也看不到了。后端 `/reminders` 已经返回全部提醒，缺的是承载它的页面和一份共享的未读状态。

## 改动文件

前端

- `stores/reminders.ts` 新增。集中放提醒列表、未读数、标记已读，AppLayout、Dashboard、提醒中心共用一份，避免三个页面各自拉数据后数字对不上。同一时刻的 `load` 合并成一次请求，因为两个并行的 `/reminders` 会各自去生成同一批提醒，可能撞 `dedup_key` 唯一约束。
- `views/RemindersView.vue` 新增。全部提醒按时间倒序，未读与全部两个筛选，单条标已读，类型显示中文标签。
- `router/index.ts` 加 `/reminders` 子路由。
- `layouts/AppLayout.vue` 顶部入口改指 `/reminders`，未读数改读 store。
- `views/DashboardView.vue` 标记已读改走 store，并在「未读提醒」区加「全部提醒」入口。

后端不改。`/reminders` 返回最近 50 条，字段与 `/reminders/{id}/read` 的归属校验都已就位。

## 依赖的公共方法

- `reminderApi.list`、`reminderApi.read`：唯一的数据出入口。
- `useToastStore`：失败提示沿用现有样式。
- `EmptyState`：空列表沿用现有组件。

## 受影响旧模块

- 侧栏导航：不新增条目，顶部入口复用，移动端布局不变。
- 提醒生成：`sync` 不受影响，页面只在访问时拉列表。
- 打卡清理提醒：标已读同样通过 store 更新本地行，顶部未读数立即跟着变。
- 接口契约：一个字段都没改，不需要改 `api/types.ts`。

## 权限与数据范围检查

- 列表与标记已读都走 `/api/v1`，令牌由 `api/client.ts` 统一注入。
- 服务端 `/reminders/{id}/read` 先比对 `user_id`，他人提醒返回 404，前端不做归属判断。

## 回归用例

- NH-07 当天任务生成提醒，确认页面能列出 `task_due`。
- RT-04 重复访问不重复生成，确认页面反复进入不会多出提醒。
- RT-05 越权，确认标记他人提醒仍返回 404。
- Z-01 至 Z-04 打卡清理提醒，确认已读状态在三个页面一致。
