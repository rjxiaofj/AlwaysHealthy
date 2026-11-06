# 首次搭建影响分析

日期 2026-11-04。改动性质：从空目录建立完整工程，没有既有线上模块，所以"受影响旧模块"一栏按未来维护视角记录约束，不作为本次回归依据。

## 改动文件

后端

- `backend/app/core/*` 配置、错误码、响应体、安全工具、SSE 映射
- `backend/app/db/models.py` 全部业务表模型
- `backend/app/repositories/*` 数据访问，全部按 user_id 收口
- `backend/app/services/*` 业务编排，GraphService 承担落库
- `backend/app/agents/*` 八个业务角色与两个确定性校验器
- `backend/app/graph/*` HealthState、节点、主图
- `backend/app/tools/risk_engine/*` YAML 规则、加载、匹配、汇总
- `backend/app/tools/knowledge_base/retriever.py` 关键词检索通道
- `backend/app/api/v1/*` 26 个接口
- `backend/migrations/versions/ebfa31c139b9_initial_schema.py` 初始迁移

前端

- `frontend/src/api/*` 请求封装、SSE 解析、类型定义
- `frontend/src/stores/*` 认证、主题、提示
- `frontend/src/layouts/AppLayout.vue` 侧栏与移动端抽屉
- `frontend/src/views/*` 七个页面
- `frontend/src/components/*` 图表、风险标签、空状态、图标

部署

- `backend/Dockerfile`、`deployment/docker-compose.yml`、备份脚本两份

## 依赖的公共方法

- `app.api.deps.current_user` 全部业务接口的认证入口
- `app.core.response.ok/paged` 统一响应体
- `app.core.exceptions.AppError` 及子类 统一错误出口
- `app.core.sse.SSEEventMapper` 事件白名单
- `app.db.session.SessionLocal` 独立会话，GraphService 内部自开会话
- `app.services.profile_service.build_snapshot` 评估与跟踪共用快照
- `app.tools.risk_engine.engine.get_engine` 规则单例

以上任一签名变化都会影响多个模块，属于大动脉。

## 受影响模块

无既有模块。需要提前说明的关联面：

- 定时任务：本版没有调度器。到期任务与提醒在用户访问时生成，相关逻辑在 `reminder_service.sync`。
- 报表：报告读取快照，档案变更不应改变历史报告。
- 工作流节点：节点名称出现在 SSE 事件与前端进度文案里，改名要同步 `NODE_LABELS` 与前端展示。
- 管理端：只保留 `/health/services`，没有用户数据查看入口。

## 权限与数据范围检查项

逐条确认，全部有对应用例或在代码中强制：

1. 评估、计划、任务、指标、报告、会话、文件查询都带 user_id 条件。
2. 计划与任务确认前校验归属，错误统一返回 404。
3. 工作流恢复校验 run 与 conversation 归属。
4. 文件下载校验路径在 storage/uploads 之内。
5. 管理员只能看服务状态，不看健康档案。（2026-11-06 补注：这句是首版的实现范围。「不看健康档案」这条边界始终有效；「只能看服务状态」已被 `docs/rules/admin-console.md` 取代，后台管理系统是必需能力，另需账号角色管理与安全事件处置。）
6. 日志不记录密码、令牌、完整档案。

## 回归用例

新增功能

- NH-01 注册登录与刷新轮换
- NH-02 档案保存与 BMI 计算
- NH-03 评估五维输出与来源
- NH-04 计划生成、确认、打卡、调整
- NH-05 指标录入与趋势
- NH-06 报告生成与导出
- NH-07 提醒生成

关联回测

- RT-01 评估历史列表分页
- RT-02 计划版本列表与当前版本一致
- RT-03 档案变更后历史报告内容不变
- RT-04 提醒重复访问不重复生成
- RT-05 跨用户读取计划、任务、报告、会话一律 404

全链路

- E2E-01 登录到评估到报告
- E2E-02 计划确认到打卡到周期总结
- E2E-03 高危消息阻断普通流程
- E2E-04 中断后恢复不重复写入

用例落点

| 编号 | 文件 |
|---|---|
| NH-01 | `backend/tests/api/test_auth.py` |
| NH-02 至 NH-07 | `backend/tests/api/test_features.py` |
| RT-01 至 RT-04 | `backend/tests/regression/test_regression.py` |
| RT-05 | `backend/tests/regression/test_data_scope.py` |
| E2E-01 至 E2E-04 | `backend/tests/e2e/test_e2e.py` |

流程片段集中在 `backend/tests/helpers.py`，改确认步骤只改一处。

执行结果见根目录 MEMORY.md。
