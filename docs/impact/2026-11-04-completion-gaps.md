# 补 P0 缺口影响分析

日期 2026-11-04。性质：对照 FDE V1.3 的 P0 清单与 9.2 页面要求，补齐未落地的几处。

## 改动文件

后端

- `app/integrations/wearable.py` 新增。`WearableReading` 固定字段口径，`WearableDataAdapter` 留厂商实现位，`ingest` 统一落库。
- `app/repositories/health.py` `latest_metrics` 增加设备读数质量过滤。
- `app/schemas/tracking.py` 把测量时间校验从服务层移到入参，未来时间返回 422 而不是 500。
- `app/services/tracking_service.py` 移除重复的时间校验。
- `app/services/consent_service.py`、`app/api/v1/endpoints/consents.py` 新增。授权与撤回各写一条记录。
- `app/services/auth_service.py` 登录、令牌重用、退出写审计；失败分支先提交再抛错。
- `app/api/v1/endpoints/auth.py` 传请求编号，移除未使用的导入。
- `app/api/v1/router.py` 注册授权路由。

前端

- `views/PlansView.vue` 加 7 天与 14 天快捷选项、周期总结卡片。
- `views/TrendsView.vue` 加身体感受反馈表单。
- `views/DashboardView.vue` 未读提醒支持标记已读。
- `views/ProfileView.vue` 加隐私与授权区、资料下载按钮。
- `views/AssessmentView.vue` 医学依据补页码。
- `api/types.ts`、`api/index.ts` 加授权记录类型与接口。

## 依赖的公共方法

- `app.repositories.health.latest_metrics`：评估快照取指标的唯一入口，改过滤条件影响所有评估结果。
- `app.repositories.chat.audit`：审计唯一写入口。
- `app.services.tracking_service.trends` 与 `summary`：趋势与周期总结共用。
- `app.core.exceptions.AppError`：新增的 422 走 `InvalidHealthData`，没有新错误码。

## 受影响旧模块

- 评估：`build_snapshot` 取指标的口径变化，只有设备读数受影响，手动录入行为不变。
- 提醒：Dashboard 标记已读只改 `notifications.read_at`，不影响按需生成与去重。
- 报表：报告读快照，本次没有改动。
- 工作流节点：没有新增或改名，`NODE_LABELS` 不变。
- 迁移：表结构未变，不需要新迁移。

## 权限与数据范围检查

1. `/consents` 两个接口都带 `current_user`，查询按 user_id 过滤。
2. 授权记录只追加，撤回写新记录，不改历史行。
3. `ingest` 只接收调用方传入的 user_id，没有跨用户入口。
4. 审计失败分支写的是用户名与用户 id，不写密码。
5. 设备读数过滤在仓储层，前端无法绕过。

## 回归用例

- 新增：NH-08 授权记录留痕、NH-09 设备读数质量过滤、NH-10 未来测量时间返回 422、NH-11 登录失败写审计。
- 关联：RT-03 报告快照不变、RT-04 提醒去重、RT-05 数据范围。
- 全链路：E2E-01 评估到报告、E2E-04 中断恢复不重复写入。

执行结果见根目录 MEMORY.md。
