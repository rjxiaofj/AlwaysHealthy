# 紧急提示记录展示影响分析

日期 2026-11-05。性质：补展示缺口。对话触发紧急提示时写 `emergency_events`，字段有触发原因、命中规则、紧急级别与处置状态，但除了写库没有任何读取入口。用户被提示过一次「立刻就医」，事后在应用里找不到这条记录，也说不清自己触发过几次。

## 改动文件

后端

- `app/repositories/chat.py` 的 `emergency_events_of` 加 `limit` 参数，默认 20，按 `triggered_at` 倒序。
- `app/api/v1/endpoints/profiles.py` 新增 `GET /profiles/me/emergency-events`，返回 `id`、`triggered_at`、`trigger_reason`、`matched_rules`、`urgency`、`response_status`。

前端

- `api/types.ts` 新增 `EmergencyEvent`，`api/index.ts` 新增 `profileApi.emergencyEvents`。
- `views/ProfileView.vue` 加「紧急提示记录」区块，有记录才显示，列出触发原因、时间、级别，底下写明这不代表诊断也不改变当时的处置建议。

测试

- `tests/api/test_emergency_events.py`：两条记录倒序返回、`matched_rules` 原样带出、跨用户不可见。

## 依赖的公共方法

- `chat_repo.emergency_events_of`：本次唯一读取入口。原先只有 `record_emergency` 写入，读取侧没人调。
- `chat_repo.audit`：不受影响，紧急事件不写审计表。

## 受影响旧模块

- 安全护栏：只加读取，`record_emergency` 的写入路径与字段没动，触发即写库的行为不变。
- 首页与提醒中心：紧急事件不生成通知，列表口径不变。
- 风险分级：紧急事件不参与五维分级，也不进评估快照。
- 迁移：表与列都没动，不需要 Alembic。

## 权限与数据范围检查

- 查询条件带 `EmergencyEvent.user_id == user_id`，取当前登录用户，不接受前端传 `user_id`。
- 上限 20 条写在仓库层，前端无法传参放大。
- 返回体只给展示所需字段，不带 `conversation_id` 与 `run_id`，避免暴露其他会话标识。

## 回归用例

- X-01 至 X-06 重新评估链路，确认审计写入未受影响。
- F-06 紧急提示，确认触发时仍然写库并返回急救文案。
- RT-05 越权，确认他人紧急事件不会出现在列表里。
