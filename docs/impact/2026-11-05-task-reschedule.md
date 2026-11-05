# 单任务改日期影响分析

日期 2026-11-05。性质：补齐 P1 项。整体改期只对没开始的计划可用，已经开始的计划提示「请逐条调整任务日期」，但 `PATCH /tasks/{task_id}` 只能改时间和提醒开关，这句提示指向的能力其实没有。本次把单任务改日期补上，整体改期的兜底提示才成立。

## 允许的条件

- 任务所在版本必须是计划当前版本。旧版本任务已经归档，改了也不影响生效版本，会出现两套数据。
- 计划状态是 `active` 或 `pending_review`。
- 新日期不早于今天，且落在计划起止日期范围内。计划外日期的任务不会出现在周期总结里。
- 该任务没有打卡记录。打卡唯一键是 `(task_id, checkin_date)`，把日期挪走会让已完成记录挂在一个不存在的日期上，状态与日期对不上。

## 改动文件

后端

- `app/services/plan_service.py` `patch_task` 增加日期分支，按上面四条校验，通过后只改 `PlanTask.scheduled_date`。
- `app/repositories/plan.py` 新增 `task_with_plan` 取任务连同计划与版本，新增 `checkin_count_of_task` 统计单任务打卡。
- `app/schemas/plan.py` `TaskPatchIn` 增加 `scheduled_date`。
- `app/api/v1/endpoints/plans.py` 任务修改接口的响应补 `scheduled_date`。

前端

- `views/PlansView.vue` 任务卡片增加改期入口，已打卡的任务不显示。
- `api/index.ts` `patchTask` 入参补 `scheduled_date`。

测试

- `tests/regression/test_task_reschedule.py` 覆盖正常改期、早于今天、超出周期、已打卡、旧版本任务、他人任务。

## 依赖的公共方法

- `app.repositories.plan.task_with_plan`：一次查出任务、计划、版本，避免在服务层拼三次查询。
- `app.repositories.plan.checkin_count_of_task`：与 `checkin_count_of_version` 同口径，都用 `func.count()`。
- `app.services.plan_service.detail`：前端改期后重新拉详情，不复用 PATCH 返回值。

## 受影响旧模块

- 打卡：只改日期，任务 id 不变，历史打卡记录仍按 id 挂得住，但已打卡任务被拒改，不会产生错位。
- 提醒：按任务 `scheduled_date` 生成，改期后自然跟着走，不改生成逻辑。
- 周期总结：按计划起止日期取打卡，任务挪到周期内所以统计口径不变。
- 整体改期：`shift` 复制任务时读的是当前版本任务日期，单任务改期后的日期会被带进新版本。
- 迁移：表结构未变，不需要新迁移。

## 权限与数据范围检查

- `task_with_plan` 的查询条件带 `HealthPlan.user_id == user_id`，他人任务返回 `None` 即 404，与 `task_of` 同口径。
- 版本归属校验在内层，先确认任务属于该计划，再比对 `current_version_id`，不接受前端传入的版本 id。
- 日期区间校验在服务端做，前端 `min`/`max` 只做提示。

## 回归用例

- RT-02 版本切换，确认改期不改变 `current_version_id`。
- RT-05 越权，确认他人任务返回 404。
- NH-06 打卡，确认改期后仍能打卡，且已打卡任务被拒改。
- S-01 至 S-07 整体改期，确认复制任务时用的是改后的日期。
