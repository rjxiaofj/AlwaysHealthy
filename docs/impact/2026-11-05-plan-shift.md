# 计划整体改期影响分析

日期 2026-11-05。性质：补齐 P1 项。原来 `adjust` 只复制任务结构，日期原样带过去，用户想把 14 天计划整体推迟一周没有办法。

## 允许的条件

- 计划状态是 `active` 或 `pending_review`。
- 计划还没开始，即 `start_date` 不早于今天。
- 当前版本下没有任何打卡记录。

已经开始或已有打卡的计划不给整体改期。任务 id 是按版本生成的，改期会换一套新任务，旧打卡记录还挂在旧任务上，硬挪会让已完成的部分变成未完成。这类计划应该逐条改任务日期，走 `PATCH /tasks/{task_id}`。

## 改动文件

后端

- `app/services/plan_service.py` 新增 `shift`。生成新版本，任务日期整体平移，旧版本置 `superseded`，计划起止日期同步后移，写一条 `approval_status=approved` 的调整记录。
- `app/repositories/plan.py` 新增 `checkin_count_of_version`，按版本统计打卡数。
- `app/schemas/plan.py` 新增 `PlanShiftIn`。
- `app/api/v1/endpoints/plans.py` 新增 `POST /plans/{plan_id}/shift`，返回计划详情。

前端

- `views/PlansView.vue` 加改期入口，只在允许改期时显示。
- `api/types.ts`、`api/index.ts` 增加对应调用。

测试

- `tests/regression/test_regression.py` 增加改期用例：正常平移、日期早于今天被拒、已开始的计划被拒、有打卡记录的版本被拒、旧版本变 superseded。

## 依赖的公共方法

- `app.repositories.plan.version_of`、`tasks_of`、`next_version_no`：与 `adjust` 共用。
- `app.services.plan_service.detail`：接口返回复用，不另建响应体。
- `app.db.models.PlanAdjustmentRecord`：调整留痕复用，`approval_status` 取 `approved` 表示用户主动发起且立即生效。

## 受影响旧模块

- 打卡：新版本任务 id 全变，旧版本打卡记录不变，仍可查历史。
- 提醒：按当前版本任务日期生成，改期后自然跟着新日期走。
- 趋势与周期总结：读打卡记录，不依赖任务日期，不受影响。
- 评估：不读计划日期。
- 迁移：表结构未变，不需要新迁移。

## 权限与数据范围检查

- `repo.plan_of(session, user_id, plan_id)` 先行，拿不到即 404。
- 打卡统计按版本 id 查，版本必须先经 `plan_of` 确认归属，不存在跨用户读取路径。
- 新开始日期下界校验在服务端，不依赖前端控件。

## 回归用例

- RT-02 新计划生效顶替旧版本，确认 `current_version_id` 与版本状态的收敛逻辑没被改坏。
- RT-05 四组越权，确认新接口没有绕过归属校验。
- NH-06 计划打卡，确认改期后新任务能正常打卡。
