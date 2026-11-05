# 身体感受历史展示影响分析

日期 2026-11-05。性质：补展示缺口。趋势页有身体感受表单，提交后写 `health_feedback_records`，但全项目没有读取入口，`repositories/plan.py::feedbacks_between` 定义后零调用。用户填完就再也看不到，等于白填。

## 改动文件

后端

- `app/services/tracking_service.py` 新增 `list_feedback`，按用户与天数窗口取记录，倒序返回。
- `app/api/v1/endpoints/tracking.py` 新增 `GET /tracking/feedback`，参数 `days` 默认 30，上限 365。

前端

- `api/types.ts` 新增 `FeedbackRecord`，`api/index.ts` 新增 `trackingApi.feedbackList`。
- `views/TrendsView.vue` 底部加「最近的身体感受」列表，随观察范围一起刷新，提交后立即回填。

测试

- `tests/api/test_feedback_list.py`：提交两条后倒序返回、天数窗口过滤、跨用户不可见。

## 依赖的公共方法

- `plan_repo.feedbacks_between`：本次唯一的读取入口，原先没人调，改它的日期口径会同时影响这里。
- `tracking_service.add_feedback`：写入路径不动。

## 受影响旧模块

- 指标趋势：不读反馈表。
- 周期总结与报告：也不读反馈，报告口径不变。
- 风险分级：反馈不参与分级，这一点在页面文案与代码注释里都写明。
- 迁移：表与列都没动。

## 权限与数据范围检查

- 查询条件带 `HealthFeedbackRecord.user_id == user_id`，跨用户返回空列表。
- 天数窗口由服务端夹在 1 到 365，前端传多少都不会拉全表。

## 回归用例

- NH-06 报告生成，确认反馈没有混进报告口径。
- RT-05 越权，确认他人反馈不会出现在列表里。
- W-01 提醒开关与 Z-01 打卡清理，确认这两条链路没被改动波及。
