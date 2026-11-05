# 阶段跟踪报告落库影响分析

日期 2026-11-05。性质：补断掉的闭环。`agents/report.py` 里 `build_tracking_report` 写完没有任何调用方，`health_reports.report_type` 恒为 `assessment`；`tracking_summaries` 表建了但零写入，周期总结每次实时算完就丢。用户做完一个周期，系统里留不下这东西。

## 目标

计划周期结束后，用户可以生成一份阶段跟踪报告：完成率、任务数、指标变化、口径说明，落 `tracking_summaries` 与 `health_reports`，在报告列表里可查、可导出。

## 允许的条件

- 计划属于当前用户，否则 404。
- 计划状态是 `active` 或 `completed`。`cancelled`、`pending_review`、`superseded` 不给生成，没有可解释的周期。
- `end_date` 不晚于今天。周期没结束就生成，完成率与指标区间都是半截，报告会误导人。
- 同一个计划与同一个周期结束日只生成一份。重复点击返回已有报告，不新增行。

## 改动文件

后端

- `app/services/tracking_service.py` 新增 `generate_report`：校验状态与周期，算总结，写 `tracking_summaries`，调 `build_tracking_report` 生成内容，再走 `report_service.save_report` 落 `health_reports`。
- `app/repositories/plan.py` `latest_summary` 改成 `summary_of_period`，按计划与周期结束日精确查，幂等判断用它。
- `app/repositories/chat.py` 新增 `report_of_summary`，按 `tracking_summary_id` 找已生成的报告。
- `app/db/models.py` `TrackingSummary` 加唯一约束 `(plan_id, period_end)`，防并发双击写出两行。
- `app/api/v1/endpoints/plans.py` 新增 `POST /plans/{plan_id}/report`，返回报告详情。
- 新迁移：给 `tracking_summaries` 加唯一约束，升降级都实现。

前端

- `api/index.ts` `reportApi` 加 `createTracking(planId)`。
- `views/PlansView.vue` 周期收尾卡片加「生成本周期报告」按钮，成功后跳到报告详情。

测试

- `tests/regression/test_tracking_report.py` 覆盖：周期未结束 409、已结束生成成功、重复生成返回同一份、取消的计划 409、他人计划 404、导出内容含完成率。

## 依赖的公共方法

- `tracking_service.summary`：唯一的周期统计口径，报告与页面共用，不另算一套。
- `report_service.save_report`：报告落库唯一入口，`report_type` 从 payload 取。
- `agents.report.build_tracking_report`：报告结构生成器，本次只接线不改结构。
- `plan_repo.tasks_of`、`checkins_between`：`summary` 内部已在用。

## 受影响旧模块

- 评估报告：`report_type` 仍为 `assessment`，详情与导出走同一套渲染，不受影响。报告列表会多出 `tracking` 类型，前端列表当前只显示标题，不需要改。
- 周期总结页面：仍走实时计算，本次不改 `summary` 的返回结构。
- 提醒：不读报告表。
- 迁移：只加一个唯一约束，不改列。已有多行同周期数据不存在（此前零写入），不会冲突。

## 权限与数据范围检查

- `plan_of(session, user_id, plan_id)` 先行，拿不到即 404。
- `summary_of_period`、`report_of_summary` 都带 `user_id` 条件。
- 报告详情的读取仍走 `report_service.detail` 的既有归属校验。
- 入参只有 `plan_id`，不接受前端传入周期或完成率。

## 回归用例

- RT-03 报告读快照，确认新报告不影响历史评估报告内容。
- RT-05 越权，确认他人计划生成报告返回 404。
- NH-06 报告生成与导出，确认两种报告类型都能导出。
- E2E-02 计划到打卡到周期总结，确认统计口径与报告数字一致。
