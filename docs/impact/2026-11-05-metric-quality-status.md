# 指标质量状态的单一真相影响分析

日期 2026-11-05。性质：修数据缺陷。

`health_metric_records` 有 `quality_status` 列，默认 `valid`；但设备读数入库时把质量状态塞进了 `measurement_context["quality_status"]`，列一栏没填。评估快照的过滤条件 `_counting_for_assessment` 读的是 JSON。

同一件事两份真相，现在靠「大家记得读 JSON」维持正确。谁哪天按列过滤，`pending` 的消费级设备估算值就会被当成已验证数据进入风险评估——这不是显示问题，是把不可靠读数算进健康结论。

## 改动文件

后端

- `app/integrations/wearable.py`
  - 新增 `QUALITY_VALID` 与 `ALL_QUALITY_STATUSES`：设备只允许 `pending`、`verified`、`rejected`，`valid` 留给人工录入与确认后的体检解析结果。
  - `ingest` 写入 `quality_status` 列，`measurement_context` 退回纯设备上下文，只留 `device_type` 与 `source`。
- `app/repositories/health.py` 的 `_counting_for_assessment` 改读列，非设备来源仍然一律计入。
- `app/services/tracking_service.py` 的 `add_metric` 写入列，默认 `valid`；`context` 里传了 `quality_status` 就校验取值，非法值直接拒绝。`context` 是请求体里用户可传的字段，不校验等于允许往状态列写任意字符串。

迁移

- `migrations/versions/*_指标质量状态回填.py`：把设备来源、列仍为 `valid`、JSON 里有 `quality_status` 的行按 JSON 回填。Postgres 用 `->>`，SQLite 用 `json_extract`，按方言分支。downgrade 把设备行重置回 `valid`。

测试

- `tests/unit/test_wearable.py` 的 `metric_row` 改为用列构造，补三条：入库后列被正确写入、`pending` 不进评估快照、非法状态被拒绝。
- `tests/api/test_features.py` 里的指标录入路径确认默认 `valid`。

## 依赖的公共方法

- `_counting_for_assessment`：评估快照的唯一过滤点。改它等于改「哪些数据算数」，回归必须覆盖 `tests/unit/test_risk_engine.py` 与评估接口用例。
- `ingest`：设备数据唯一入口，目前没有真实厂商适配器调用，改动不涉及线上路径。

## 受影响旧模块

- 评估快照：口径不变。`pending` 依然不进，`verified` 依然进，只是判断依据从 JSON 换成列。
- 指标趋势与列表：只读值与时间，不读质量状态，不受影响。
- 体检解析：确认后写 `health_metric_records` 走 `add_metric`，默认 `valid`，与之前一致。
- 前端：没有读取质量状态的地方，不改。

## 权限与数据范围检查

- 质量状态只能由服务端写入，接口不接受任意值，非法值返回 `INVALID_HEALTH_DATA`。
- 回填只动 `source_type='wearable'` 且列为默认值的行，人工录入与解析结果不碰。

## 回归用例

- `tests/unit/test_risk_engine.py`：确认分级口径没变。
- `tests/api/test_features.py::test_nh_05_metric_records_and_trends`：确认手工录入仍进快照。
- `tests/unit/test_wearable.py`：确认设备三态的过滤行为。
