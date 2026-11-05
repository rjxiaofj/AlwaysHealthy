# 重新评估闭环与审计字段溢出影响分析

日期 2026-11-05。性质：修一个只在 Postgres 上炸的缺陷，同时把重新评估的入口接到前端。

## 发现的缺陷

`tracking_service.reassessment_request` 把用户填的原因写进审计的 `result` 字段：

```python
result=reason[:120]
```

`security_audit_logs.result` 在各库里都是 `varchar(16)`，模型定义 `String(16)`。SQLite 不校验长度，测试环境从来没炸；Postgres 在一次性库上实测直接报 `value too long for type character varying(16)`，接口会 500。

```
$ psql -c "insert into security_audit_logs (id, action, resource_type, result)
           values (gen_random_uuid(), 'probe', 'test', repeat('x', 17))"
ERROR:  value too long for type character varying(16)
```

其他审计调用点写的都是 `success` / `fail` / `ignored` 这类短状态词，只有这一处把自由文本塞进去，属于写法跑偏而不是列定义太窄。

## 修法

`result` 写 `requested`，原因不再落审计。原因本身没有分析价值，审计要证明的是「这个用户在某天主动要求过重新评估」。给它单开一列要加迁移，为一个演示用途的短文本不值。

同时在前端把入口接上。`trackingApi.reassessment` 早就定义好了，没有任何页面调用，等于这个接口只有测试价值没有产品价值。

## 改动文件

后端

- `app/services/tracking_service.py` `reassessment_request` 改 `result="requested"`，注释写明 16 字符限制。

前端

- `views/PlansView.vue` 加「周期收尾」卡片，只在计划已结束或距结束两天内出现。原因输入加一个按钮，先登记诉求再基于当前档案生成新评估，成功后跳到评估页。
- 复用 `trackingApi.reassessment` 与 `assessmentApi.create`，不新增接口。

测试

- `tests/api/test_reassessment.py` 三条：原因过短 422、成功写一条 `reassessment_request` 审计、`result` 不超过 16 字符。

## 依赖的公共方法

- `app.repositories.chat.audit`：审计唯一写入口，本次只改调用方传参。
- `app.services.assessment_service.save_assessment`：新评估落库走既有路径，快照用当前档案，不动历史的评估与报告。

## 受影响旧模块

- 审计：只影响 `reassessment_request` 这一条的 `result` 内容，其他调用点不动。历史行里若已被截断写入的脏数据保留，不做数据修复。
- 评估：新评估是一条新记录，旧评估、旧报告、旧计划的快照都不动。
- 计划：不自动取消或生成计划，用户仍需自己确认下一周期。
- 迁移：不改表结构。

## 权限与数据范围检查

- 两个接口都走 `current_user`，审计的 `actor_user_id` 取自令牌。
- `assessmentApi.create` 内部 `build_snapshot` 按 user_id 取档案，没有跨用户入口。
- 前端按钮只在本人计划上出现，最终以接口归属校验为准。

## 回归用例

- RT-03 报告快照不变，确认新评估不改历史报告。
- RT-05 四组越权，确认新入口没绕过归属校验。
- W-01 至 W-05 提醒开关，确认改动没碰到提醒路径。
