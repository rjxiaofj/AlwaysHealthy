# 影响分析：计划页判定逻辑抽成纯函数，任务时间可清空

日期：2026-11-05

## 变更意图

`PlansView.vue` 是这批页面里分支最多的一个。六处「能不能做某个操作」的判定、一处任务分组、一处请求体拼装，都内联在 `<script setup>` 的 computed 里，跟模板缠在一起。这类逻辑的验证手段只有点页面，改一个状态字符串要考虑七八个页面的可见性。

本轮把它抽出去，顺带修掉抽取过程中暴露的一个缺陷。

## 抽了什么

新建 `frontend/src/views/planLogic.ts`，八个纯函数：

| 函数 | 原位置 | 覆盖的分支 |
|---|---|---|
| `groupTasksByDate` | `grouped` computed | 空列表、同日归组、按日期升序、跨月跨年 |
| `daysUntil` | `daysLeft` computed | 同天 0、正数、负数、跨月跨年 |
| `canShiftPlan` | `canShift` computed | 状态白名单、计划已开始、任一任务已打卡三种状态 |
| `canReassessPlan` | `canReassess` computed | completed 恒可、active 剩 2 天内、draft 与 cancelled |
| `canCheckinPlan` | `canCheckin` computed | 只有 active |
| `canCancelPlan` | `canCancel` computed | active 与 pending_review |
| `isAdjustmentPending` | `pendingIsAdjustment` computed | 待确认版本配 active 才是调整草稿 |
| `buildTaskPatch` | `reschedule()` 内联 diff | 无改动、单字段、三字段同时改、清空时间 |

组件里对应的 computed 改成一行调用，模板未动。

## 修掉的缺陷

`reschedule()` 原本这样判断时间有没有改：

```ts
const timeChanged = editTime.value && editTime.value !== (task.scheduled_time || '')
```

用户把时间输入框清空时 `editTime.value` 是空串，整个表达式为假。结果有两个：请求里根本不带 `scheduled_time`，以及日期与提醒都没改时界面提示「日期、时间与提醒都没有变化」。也就是说任务一旦设过时间，用户无法再把它改回「任意时间」。

后端同一个毛病，`if payload.scheduled_time is not None` 判断，显式传 `null` 被当成没传。

两侧一起改：

- 后端改用 `"scheduled_time" in payload.model_fields_set`，字段不出现才是不改，显式传 `null` 表示去掉。
- 前端 `buildTaskPatch` 比对后，清空时发 `scheduled_time: null`。
- `planApi.patchTask` 的入参类型放宽为 `string | null`。

`scheduled_date` 与 `reminder_enabled` 保留 `is not None` 判断，它们没有「清空」这种操作。

## 顺手修的测试基础设施

`tests/conftest.py` 把 `DATABASE_URL` 写成 `./test_alwayshealthy.db`，但删库语句删的是 `Path(__file__).parents[1] / "test_alwayshealthy.db"`（即 `backend/` 下）。从 `backend/` 目录跑 pytest 时两者一致；从仓库根跑时数据库落在仓库根，删的是另一个不存在的文件，等于没清库。

后果是第二轮跑测试时，凡是硬编码用户名的用例（`taskmover`、`shifttaker` 等六处）注册都会 409。这个坑之前没暴露是因为一直从 `backend/` 目录跑。

改成绝对路径，库里外一致。

## 影响面

| 范围 | 是否受影响 | 说明 |
|---|---|---|
| 接口路径与响应体 | 否 | `PATCH /tasks/{id}` 的请求字段语义扩展了一个值（`null`），响应不变 |
| 其他接口 | 否 | 无改动 |
| 历史数据 | 否 | 不涉及迁移，`scheduled_time` 本来就是可空列 |
| 前端构建产物 | 是 | `PlansView` chunk 从 20.22 kB 到 20.53 kB，逻辑搬进独立模块 |
| 后端测试库 | 是 | 库文件固定落在 `backend/test_alwayshealthy.db` |
| 依赖 | 否 | 无新增 |

## 验证

- `pytest`：156 项通过，连跑两次结果一致（改动前 154 项）。
- 前端 `npm test`：45 项通过（`client` 10、`planLogic` 29、`reminders` 6）。
- `vue-tsc --noEmit` 与 `npm run build`：均通过。
- 变异验证两处：服务端改回 `is not None`，T-08 失败；前端改回「值非空才算改」，对应的「清空时间发 null」用例失败。均已复原。

## 遗留

- 组件仍然没有渲染测试。`PlansView` 里还剩「哪个区块在什么状态下显示」这类判断留在模板，抽函数收益不大，要测只能上组件测试。
- `daysUntil` 依赖 `Math.round` 吸收时区与夏令时偏移，国内无夏令时，没在 DST 时区验证过。
