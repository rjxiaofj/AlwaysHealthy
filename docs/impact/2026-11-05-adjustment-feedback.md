# 计划调整的确认出口与用户反馈影响分析

日期 2026-11-05。性质：修断链 + 补闭环。

原计划只做一件事：`plan_adjustment_records.user_feedback` 建表起一直为空，调整完没人问过用户「这次调整解决问题没有」。动手时发现更前面的问题——**调整产生的草稿根本没有确认入口**。

- 后端 `adjust` 新建 `status=draft` 的版本，不动 `current_version_id`。
- 前端 `canApprove` 要求 `plan.status === 'pending_review'`，而调整后的计划仍是 `active`，按钮不出现。
- 前端 `approve()` 传的是 `current_version_id`，也就是还生效的旧版本，不是草稿。

三条叠起来的结果：用户点「生成调整版本」后，页面上既不能确认，也不能退回，草稿永远躺在 `versions` 里。`user_feedback` 之所以为空，是因为它依赖的确认动作从来走不到。

## 改动文件

后端

- `app/services/plan_service.py`
  - `reject_version` 按来源分流：初次计划的草稿被否，计划一并取消；调整产生的草稿被否，只作废这一版，计划继续用原版本。返回一句给用户看的结论。
  - `detail` 增加 `adjustment`：当前版本由调整产生且已生效时返回原因、状态、创建时间与已有反馈。
  - 新增 `submit_adjustment_feedback`：只接受当前生效版本，且该版本必须有已通过的调整记录。
  - 新增 `_approved_adjustment`：详情与提交两处共用，避免各写一份过滤条件。
- `app/schemas/plan.py` 新增 `AdjustmentOut`、`AdjustmentFeedbackIn`，`PlanOut` 加 `adjustment`。
- `app/api/v1/endpoints/plans.py` 新增 `POST /plans/{plan_id}/versions/{version_id}/reject` 与 `POST /plans/{plan_id}/adjustment-feedback`。拒绝接口返回计划详情，前端不用二次拉取。

前端

- `api/types.ts` 新增 `PlanAdjustment`，`Plan.adjustment` 可空。
- `api/index.ts` 新增 `planApi.adjustmentFeedback` 与 `planApi.rejectVersion`。
- `views/PlansView.vue`
  - 待确认版本改为从 `versions` 里找 `status === 'draft'`，不再依赖 `plan.status`。
  - `approve()` 传待确认版本的 id。
  - 待确认时显示一行说明与两个出口：确认启用、放弃这次调整或取消计划。
  - 调整生效后显示「这次调整合适吗」，三个快捷选项加一句可选补充；已有反馈时只展示那句话。

测试

- `tests/regression/test_plan_adjustment_feedback.py` 10 项：生效后反馈、重复提交覆盖、未生效版本拒绝、原生版本拒绝、他人计划 404、空白反馈 422、放弃调整后计划仍在跑、初次草稿被否计划取消、重复拒绝 409、计划不存在 404。

## 依赖的公共方法

- `plan_service.approve`：不动。它仍负责把 `pending` 记录置 `approved` 并填 `confirmed_at`，反馈卡片的展示前提由它决定。
- `repo.adjustment_log`：原先定义了没人调，现在被 `_approved_adjustment` 用上。
- `graph_service.resume_run`：调用 `reject_version` 但不看返回值，返回值从 `None` 改成字符串不影响它。

## 受影响旧模块

- 初次计划流程：`canApprove` 口径从「计划待确认」改成「存在草稿版本」，两条路径合一，初次计划行为不变；被否时仍然取消计划。
- 改期：也换版本，但不写调整记录，`adjustment` 为 `null`，页面不出现反馈卡片。
- 打卡与提醒：不涉及。调整复制任务时仍沿用原 `reminder_enabled`。
- 阶段报告：只读打卡与总结，不读反馈文本。
- 迁移：表与列都已存在，不需要 Alembic。

## 权限与数据范围检查

- 两个新接口都先按 `user_id` 取计划，他人计划 404。
- 反馈的 `version_id` 必须是当前生效版本；拒绝的 `version_id` 必须是该计划下的草稿版本。
- 反馈长度 2 到 200，服务端再 strip，空白串不落库。
- 同一条记录重复提交覆盖，不追加，避免同一次调整出现互相矛盾的结论。

## 回归用例

- S-01 至 S-07 改期链路，确认 `adjustment` 为 null 且不误显示卡片。
- P-01 至 P-08 阶段报告，确认报告口径不含反馈文本。
- W-01 至 W-05 提醒开关，确认调整复制版本仍沿用原任务开关。
- 初次计划确认与拒绝：`tests/api/test_features.py` 与 `tests/regression/test_regression.py` 里的计划确认路径，确认 `canApprove` 口径改动没影响原有确认行为。
