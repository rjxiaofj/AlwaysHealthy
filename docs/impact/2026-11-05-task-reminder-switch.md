# 任务提醒开关生效影响分析

日期 2026-11-05。性质：修死配置。`plan_tasks.reminder_enabled` 有列、有 PATCH 入参、有返回值，但 `reminder_service.sync` 完全不读它，用户把开关关掉依旧会收到当天的任务待完成提醒。开关不生效比没有开关更容易误导人，本次要么让它生效，要么删掉，选择让它生效。

## 语义定稿

- 开关按任务粒度生效，只管 `task_due` 这一类提醒，即「今天这个任务还没打卡」。
- `plan_overdue`、`plan_end` 属于计划级提醒，不受单个任务开关影响。
- 新建与复制任务时默认开启。已有数据里该列默认 `False`，本次改动后老计划的当天任务不再产生 `task_due` 提醒，演示库直接重建，不做数据回填。

## 改动文件

后端

- `app/services/plan_service.py` 三处生成任务的地方显式写 `reminder_enabled=True`；`adjust` 与 `shift` 复制任务时沿用原任务的开关值，不重置用户的关闭状态。详情返回补 `reminder_enabled`。
- `app/services/reminder_service.py` `sync` 跳过关闭了提醒的任务，其余逻辑与去重键不变。
- `app/schemas/plan.py` `TaskOut` 补 `reminder_enabled`。

前端

- `api/types.ts` `Task` 补 `reminder_enabled`。
- `views/PlansView.vue` 任务卡片的调整面板加提醒开关与时间，提交仍走一次 `PATCH /tasks/{task_id}`。

测试

- `tests/regression/test_task_reschedule.py` 补：关闭提醒后不再生成当天任务提醒；开启后恢复；时间格式不合法返回 422。
- 既有 NH-07 与 RT-04 依赖默认开启，改动后行为不变。

## 依赖的公共方法

- `app.repositories.plan.tasks_of`：提醒与详情共用，一次取当天任务。
- `app.repositories.chat.notification_by_dedup`：去重键仍是 `task_due:{task_id}:{date}`，关掉再打开不会补发历史提醒。
- `app.services.plan_service.patch_task`：开关的写入口，与改日期共用同一段校验。

## 受影响旧模块

- 提醒列表：条数变少只发生在用户主动关闭之后，未关闭的任务行为不变。
- 周期总结与趋势：不读提醒，不受影响。
- 计划校验：`plan_validator` 不校验该字段，草稿到生效的流程不变。
- 迁移：列已存在，不需要新迁移。

## 权限与数据范围检查

- 开关写入走 `patch_task`，先查任务归属，他人任务 404。
- 提醒生成本就按 `user_id` 取计划与打卡，跳过逻辑只读当前用户任务行，没有跨用户路径。

## 回归用例

- NH-07 当天任务生成提醒，确认默认开启后仍生成。
- RT-04 重复访问不重复生成，确认去重键没被改坏。
- T-01 至 T-07 单任务改期，确认新加的开关分支不影响日期分支。
