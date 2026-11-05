# 体检资料文字识别影响分析

日期 2026-11-05。性质：补齐 P1 项。原来上传只做类型与大小校验，`parse_status` 一直是 `pending`，等于收了文件不认内容。

## 能力边界

只解析 PDF 的文本层，不做 OCR。图片仍可上传保存，但解析状态记 `unsupported`，不假装识别过。扫描件 PDF 没有文本层时同样落 `unsupported`。

识别结果不直接写库。先返回候选字段与命中的原文片段，用户在页面上确认后才写入指标记录。这条是硬要求：体检单上的数字一旦认错，会顺着评估链路放大到风险等级。

## 改动文件

后端

- `app/services/document_parser.py` 新增。`extract_pdf_text` 取文本层，`parse_text` 按规则表匹配指标，命中值必须落在 `METRIC_DEFS` 的取值区间内，超出即丢弃。报告用 mg/dL 的按指标系数换算成 mmol/L。
- `app/db/models.py` `FileAsset` 增加 `parsed_payload` 与 `parse_message` 两列，前者存候选字段，后者存不可解析的原因。
- `migrations/versions/` 新增迁移，两个可空列，升降级都写了。
- `app/services/file_service.py` `save_upload` 落盘后同步解析并更新状态；新增 `get_extracted` 与 `apply_extracted`。
- `app/api/v1/endpoints/profiles.py` 增加 `GET /profiles/me/documents/{file_id}/extracted` 与 `POST /profiles/me/documents/{file_id}/apply`。
- `app/schemas/health.py` 增加 `ApplyExtractedIn`。
- `requirements.txt` 增加 `pypdf`。

前端

- `views/ProfileView.vue` 资料列表增加识别结果展开、勾选与写入按钮，不可解析时显示原因。
- `api/types.ts`、`api/index.ts` 增加对应类型与调用。

测试

- `tests/unit/test_document_parser.py` 覆盖血压合并写法、单位换算、超区间丢弃、无文本层。
- `tests/api/test_document_extract.py` 覆盖上传后状态流转、越权读取他人文件、重复应用幂等。

## 依赖的公共方法

- `app.tools.metrics.METRIC_DEFS`：候选字段的编码与区间都来自这里，新增指标只需改规则表。
- `app.repositories.chat.file_of`：按 `user_id` 取文件，越权在读之前就被拦住。
- `app.services.tracking_service` 的写入路径复用 `HealthMetricRecord`，`source_type` 取 `document`，与 `manual`、`wearable` 区分。
- `app.repositories.health._counting_for_assessment`：只对 `wearable` 做质量过滤，`document` 按用户确认过的数据处理，本次不改。

## 受影响旧模块

- 上传：多一步同步解析，大文件耗时增加。PDF 只读文本层，限制在现有 10MB 上限内可接受。
- 指标与评估：只有用户点确认才写记录，不点就没有新数据，评估结果不变。
- 文件下载：路径未变。
- 趋势与提醒：读的是指标表，来源多一种取值，展示逻辑不变。
- 迁移：新增两列，均允许空，旧数据无需回填。

## 权限与数据范围检查

- 三个文件接口都先经 `file_of(session, user_id, file_id)`，拿不到即 404，不区分「不存在」与「不属于你」。
- `apply_extracted` 只接受该文件 `parsed_payload` 里存在的编码，前端传别的编码直接拒绝，避免借接口写任意指标。
- 解析在服务端完成，前端拿不到文件绝对路径。

## 回归用例

- RT-05 四组越权，确认新增接口没有绕过归属校验。
- NH-02 至 NH-07 指标录入与趋势，确认 `source_type` 多一个取值不影响原有查询。
- E2E-01 至 E2E-04 全链路，确认评估快照没被未确认的候选污染。
