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

- `health_metric_records.source_type` 区分 manual、wearable 等来源，`measurement_context` 只记设备类型与来源。
- 质量状态只有一处真相：`health_metric_records.quality_status` 列。取值 `valid` 人工录入与确认后的体检解析结果、`pending` 未核验的设备读数、`verified` 已核验、`rejected` 已判废。禁止再把状态写进 `measurement_context`，2026-11-05 之前就是两份真相并存，谁按列过滤都会把 pending 数据当成已验证。
- 设备读数只有在 `quality_status=verified` 时才允许进入评估快照，其余只进指标表。
- 过滤点在 `app/repositories/health.py::latest_metrics`。绕过它取最新值就会让手环估算顶掉用户手动录入的测量。
- `POST /tracking/metrics` 的 `context.quality_status` 会被校验，非法值返回 `INVALID_HEALTH_DATA`。这一栏来自请求体，不校验等于允许往状态列写任意字符串。
- 可穿戴适配统一走 `app/integrations/wearable.py`，厂商差异只在该文件实现。
- 同一指标同一测量时间的设备读数只入库一次，去重点在 `wearable.ingest`。

## 资料解析

- 体检资料上传后立刻解析，状态落在 `file_assets.parse_status`：`parsed`、`unsupported`、`failed`。不存在长期停在 `pending` 的中间态。
- `file_assets.admission_status` 记入库前的准入校验结果，通过写 `passed`。校验内容是扩展名白名单、单文件大小上限、文件头签名与扩展名一致，**不做病毒扫描**，列值不要写成 `verified` 之类让人误以为杀过毒。被拒的请求在写盘前就抛错，库里不该出现失败态。
- 识别结果只写 `file_assets.parsed_payload`，用户逐项确认后才写 `health_metric_records`，来源记 `document`。跳过确认直接入库会让认错的数字顺着评估链路放大成错误风险等级。
- 只解析 PDF 文本层，不做 OCR。图片与扫描件记 `unsupported` 并保留原件，不用模型猜字段。
- 命中值必须落在 `app/tools/metrics.py` 的取值区间内，超出即丢弃。报告用 mg/dL 时按指标系数换算，换算后再校验区间。
- 同一编码在一份报告里出现多次时按原文位置取最靠前的一条，其余留给用户看原文自行判断。
- 重复确认同一份资料不会产生重复记录，测量时间取文件上传时刻，去重点在 `file_service.apply_extracted`。

## 周期总结与阶段报告

- `tracking_summaries` 按 `(plan_id, period_end)` 唯一。一个计划的一个周期只留一份总结，重复生成走已有记录。
- 只有周期结束日不晚于今天的计划才允许生成报告。周期没结束就算完成率，数字会误导人。
- `cancelled`、`pending_review`、`superseded` 的计划不生成周期报告，没有可解释的执行周期。
- 报告内容由 `app/agents/report.py::build_tracking_report` 生成，落 `health_reports.content_snapshot`，`report_type=tracking`，`tracking_summary_id` 指向总结行。
- 完成率口径与页面一致，都走 `tracking_service.summary`，不另算一套。

## 迁移

- 所有结构变更走 Alembic，`backend/migrations/versions`。
- 生成命令：`alembic revision --autogenerate -m "说明"`。
- 生成后人工检查：JSONB 变体是否正确、索引是否遗漏、是否有意外删表。
- 本地验证升降级都要跑：`alembic upgrade head`、`alembic downgrade base`、再 `upgrade head`。
- 演示库不允许手工改表。

## 演示数据

默认全部为模拟数据。不要导入真实体检报告。
演示账号通过注册接口创建，不在代码里内置固定密码。
