# 打卡后清理待完成提醒影响分析

日期 2026-11-05。性质：修状态不同步。Dashboard 接上直接打卡之后，用户完成任务，未读提醒里那条「今日任务待完成」仍然挂着。`sync` 只在生成时看打卡状态，已经生成的提醒不会跟着任务状态变。

## 现象

`reminder_service.sync` 的循环里已经有 `if task.id in checked: continue`，所以打卡之后不会再新生成这条提醒；但去重键 `task_due:{task_id}:{date}` 已存在的那条还在 `notifications` 表里，`read_at` 仍为空。Dashboard 过滤未读，用户刚点完「完成」还看到「待完成」，看起来像没生效。

## 做法

在 `sync` 里把今天已打卡任务对应的未读 `task_due` 提醒标为已读。不删除行：通知属于历史记录，标已读既能从首页未读列表消失，又能在提醒页查到当时发生过什么。

- 只处理 `notification_type=task_due`、去重键精确等于今天的那批。
- 计划级的两条提醒不动。
- 只按 `user_id` 查自己名下的行。

## 改动文件

后端

- `app/repositories/chat.py` 新增 `unread_task_reminders`，按用户、任务 id 集合与当天去重键查未读行。
- `app/services/reminder_service.py` `sync` 末尾把查到的行标 `read_at`，与新增提醒共用一次提交。

前端

- `views/DashboardView.vue` 今日任务加「完成」按钮，只在计划 active 且任务未完成时显示，打卡成功后重新拉一遍数据。
- `views/PlansView.vue` 「生成调整版本」入口按计划状态收口，非 active 计划不再露出。

测试

- `tests/regression/test_reminder_switch.py` 补：打卡后对应提醒 read_at 非空、未打卡任务的提醒仍为未读、他人提醒不受影响。

## 依赖的公共方法

- `app.repositories.plan.checkins_between`：`sync` 已经在用，今天打卡任务集合直接复用。
- `app.repositories.chat.notification_by_dedup`：去重键口径不变，清理逻辑按同一口径构造键，不另立一套。

## 受影响旧模块

- 提醒页：已读提醒仍然列出，只是首页未读里不再出现。
- 周期总结与趋势：不读通知表。
- 打卡：不改动打卡逻辑，只读它落下的记录。
- 迁移：表结构未变。

## 权限与数据范围检查

- 查询条件带 `Notification.user_id == user_id`，任务 id 集合来自同一用户今天的打卡记录。
- 去重键带任务 id 与日期，不会误伤别的日期或别的任务的提醒。

## 回归用例

- RT-04 重复访问不重复生成提醒，确认清理没有破坏去重。
- NH-07 当天任务生成提醒，确认未打卡任务仍正常生成。
- W-01 至 W-05 提醒开关，确认关掉提醒的任务不会被误标。
