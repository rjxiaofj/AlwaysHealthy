# 数据与迁移

## 表结构约定

- 主键 UUID，`sa.Uuid` 类型，跨数据库可用。
- 时间用 `TIMESTAMPTZ`，存 UTC。取回后比较前用 `app/core/timeutil.py` 的 `as_utc`，sqlite 不带时区。
- 灵活结构用 JSON，PostgreSQL 下自动变 JSONB。
- 计划执行日期用 DATE，不用时间戳，避免时区导致跨天。

## 历史不可覆盖

- `risk_assessments.profile_snapshot` 保存评估当时的档案快照。报告读快照，不读当前档案。
- `health_plan_versions` 只增不改。任务随版本复制。
- 报告 `content_snapshot` 保存生成时的完整内容。

改报告或评估逻辑后，老报告内容不能变。验证方式：生成一份报告，改档案，再读报告，内容应保持一致。

## 指标来源与质量

- `health_metric_records.source_type` 区分 manual、wearable 等来源，`measurement_context` 记设备类型与质量状态。
- 设备读数只有在 `quality_status=verified` 时才允许进入评估快照，其余只进指标表。
- 过滤点在 `app/repositories/health.py::latest_metrics`。绕过它取最新值就会让手环估算顶掉用户手动录入的测量。
- 可穿戴适配统一走 `app/integrations/wearable.py`，厂商差异只在该文件实现。

## 迁移

- 所有结构变更走 Alembic，`backend/migrations/versions`。
- 生成命令：`alembic revision --autogenerate -m "说明"`。
- 生成后人工检查：JSONB 变体是否正确、索引是否遗漏、是否有意外删表。
- 本地验证升降级都要跑：`alembic upgrade head`、`alembic downgrade base`、再 `upgrade head`。
- 演示库不允许手工改表。

## 演示数据

默认全部为模拟数据。不要导入真实体检报告。
演示账号通过注册接口创建，不在代码里内置固定密码。
