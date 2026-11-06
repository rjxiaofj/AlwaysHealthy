# 计划与打卡

## 版本模型

`health_plans` 是计划主体，`health_plan_versions` 是版本，`plan_tasks` 挂在版本上。
同一时间一个用户只有一份 active 计划。确认新计划时，原 active 置 superseded，不删除。
调整计划生成新版本，旧版本保留，`health_plans.current_version_id` 指向当前版本。

为什么不用一张表存历史：版本要能对比，任务要能按版本追溯，覆盖写会毁掉历史打卡的归属。

## 不可绕过的校验

1. 周期 7 到 30 天，后端校验，数据库有 CHECK 约束。
2. 任务日期必须落在计划周期内。
3. 每个任务必须有完成标准。
4. 任务文案不得出现确诊、处方、剂量、停药、换药、加量。`app/tools/plan_validator.py` 里是硬拦截。
5. 未通过校验的草稿不允许确认。确认接口只接受 draft 或 pending_review 的版本。
6. 打卡只允许当前 active 版本的任务。历史版本任务不能打卡。

## 打卡幂等

唯一键 `(task_id, checkin_date)`。同一天重复提交按更新处理，返回同一条记录。
前端重复点击、网络重试都不会产生第二条。

## 任务设计原则

每天最多 3 项。模板在 `app/agents/plan.py`，按维度取任务，不做无限扩展。
任务要能在一句话里说清完成标准。写不清的任务说明还没想明白怎么执行。

未完成任务允许填写原因。完成率只反映执行情况，不解释为健康改善或恶化，报告与跟踪文案都要保持这个口径。

## 改期

两种粒度，别混用：

- `POST /plans/{id}/shift` 整体平移。只在计划没开始且当前版本没有打卡时可用，会生成新版本，任务 id 全变。
- `PATCH /tasks/{id}` 单条调整。只能动当前版本的任务，日期要在计划周期内、不早于今天，任务已有打卡就拒绝。

已经开始的计划一律走单条调整。整体改期会把旧打卡挂到不存在的任务上。

`scheduled_time` 的语义按字段是否出现区分：不出现是不改，显式传 `null` 是把时间去掉（任务没有时间表示任意时间）。服务端用 `payload.model_fields_set` 判断，不能用 `is not None`，否则清空请求会被当成没传，任务一旦设过时间就再也删不掉。`scheduled_date` 与 `reminder_enabled` 没有「清空」这一说，仍按 `is not None` 处理。

## 提醒

提醒按访问时生成，没有后台调度。`plan_tasks.reminder_enabled` 只挡当天任务待完成这一条，计划级的逾期与结束提醒不受它影响。新建任务默认开启，复制版本沿用原值。

这里的「没有后台调度」只指不引入 APScheduler 之类的定时任务，与 `docs/rules/admin-console.md` 要求的后台管理系统无关。

## 调整与版本确认

调整是两步：`POST /plans/{id}/adjust` 生成草稿版本，`POST /plans/{id}/approve` 才让它生效。草稿不动 `current_version_id`，也不改计划状态，所以前端不能用计划状态判断「有没有待确认版本」，要从 `versions` 里找 `status=draft`。

草稿的两个出口语义不同，不要合并处理：

- 确认：`approve` 把版本置 `active`、把调整记录置 `approved` 并填 `confirmed_at`，旧版本置 `superseded`。
- 放弃：`POST /plans/{id}/versions/{version_id}/reject`。调整产生的草稿被放弃，只作废这一版，计划继续用原版本；初次计划的草稿被放弃，计划一并取消。两者都会把调整记录置 `rejected` 并填 `confirmed_at`，不允许停在 `pending`。

调整生效后可以补一句反馈，写 `plan_adjustment_records.user_feedback`。只接受当前生效版本，重复提交覆盖同一条，不追加。反馈不参与风险分级，也不进报告口径。

调整版本沿用原任务结构，任务数不会因为「任务太多」这个原因自己变少。要让计划真变，只能在待确认版本里逐条删任务：`DELETE /plans/{plan_id}/versions/{version_id}/tasks/{task_id}`。删的是草稿里的新行，原版本任务与打卡不动；至少要留一项，删到空会让确认后的计划没有内容。删完不确认等于没删，草稿被放弃时删除一并作废。

## 回归

`tests/unit/test_plan_validator.py`、`tests/api/test_features.py::test_nh_04_plan_generate_approve_checkin_adjust`。
改确认流程还要跑 `tests/regression/test_regression.py::test_rt_02_plan_versions_match_current`，确认计划状态与版本号正确。
