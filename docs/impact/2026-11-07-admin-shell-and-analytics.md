# 后台独立外壳与数据看板

## 前置影响分析（AGENTS.md 第 7 节）

改动文件：

- 新增 `frontend/src/layouts/AdminLayout.vue`：管理端外壳，侧边栏只放管理菜单。
- 新增 `frontend/src/components/AdminTrendChart.vue`（多序列折线）、`frontend/src/components/AdminBarChart.vue`（横向条形）。
- 改 `frontend/src/router/index.ts`：`/admin` 从 `AppLayout` 的子路由提到顶层，挂 `AdminLayout`，下挂 6 个子路由，每带一个 `meta.panel`。
- 改 `frontend/src/views/AdminView.vue`：删掉组件内的侧边菜单，改成按 `route.meta.panel` 渲染面板；新增「数据看板」面板。
- 改 `frontend/src/components/AppIcon.vue`：补 `grid`、`list` 两个图标。
- 改 `frontend/src/api/types.ts`、`frontend/src/api/index.ts`：新增 `AdminAnalytics`/`AnalyticsBucket`/`AnalyticsDay` 与 `adminApi.analytics()`。
- 改 `backend/app/repositories/admin.py`（新增 `analytics_counts`）、`backend/app/services/admin_service.py`（新增 `analytics`）、`backend/app/api/v1/endpoints/admin.py`（新增 `GET /admin/analytics`）。
- 新增 `frontend/src/layouts/AdminLayout.spec.ts`；重写 `frontend/src/views/AdminView.spec.ts`。
- 契约守卫改 `backend/tests/contract/test_frontend_types.py`；`backend/tests/api/test_admin_console.py` 加看板用例。
- 不改数据库模型、不加迁移：聚合只读 `users`、`security_audit_logs`、`security_incidents`、`workflow_runs`。

公共方法依赖：

- `admin_service.analytics` → `admin_repo.analytics_counts`（`group_by` + `func.count()`）→ `_count_by_day` 按 `BUSINESS_TZ` 归日 → 端点经 `core/response.ok` 包装。
- `AdminLayout` → `useAuthStore.ensureUser`（拿用户名显示）、`useThemeStore.toggle`、`useAuthStore.logout`。
- `AdminView` → `useRoute().meta.panel`；十路 `Promise.allSettled` 各带降级，新增的一路是 `adminApi.analytics()`。

受影响旧模块：

- `AppLayout` 一行未改。它仍给前台页面提供用户端侧边栏，`/admin` 只是不再挂在它下面。
- 原 `/admin` 路由名 `admin` 被删除。全仓只有 `LoginView` 用路径 `/admin` 跳转，没有按 name 跳的地方，改路径后跳转依然成立，落到 `/admin` 会重定向到 `/admin/overview`。
- 其余路由、守卫、SSE、工作流、计划与提醒链路均未改动。
- 统计口径不变：`/admin/overview` 的 5 个计数逻辑原样保留，看板是新增接口，不回填也不改写旧数。

权限与数据范围检查：

- `GET /api/v1/admin/analytics` 依赖 `admin_user`，未登录 401、普通用户 403，与其它管理接口一致。
- 聚合结果只含计数与动作名：不含用户名、邮箱、健康档案、评估、计划、聊天内容。审计动作名是系统内部枚举，不是用户数据。
- 归日按 `BUSINESS_TZ` 做，不在 SQL 里用 `date()`：SQLite 与 Postgres 对带时区时间戳的 `date()` 语义不同，同一份 SQL 会在两个库切出不同日界。
- 只取近 7 天，`since` 由服务层算好再传进查询，不在仓库层做时间运算，避免两处口径漂移。

回归用例：

- `frontend/src/layouts/AdminLayout.spec.ts`：侧边栏只有 6 个管理菜单；健康首页/智能助手/健康评估/健康管理/指标趋势/个人中心/待办提醒一律不出现；点菜单改路由并高亮；顶栏标题跟路由；退出登录回 `/login`；有返回前台入口。
- `frontend/src/views/AdminView.spec.ts`：按 `meta.panel` 渲染对应面板；看板渲染 7 天两条线（4 个数据点）与 5 组分布；看板读取失败降级但其它面板不受影响。
- `backend/tests/api/test_admin_console.py`：普通用户 403；7 天序列长度与日期连续；今日注册落在最后一格；登录失败进今日格子；审计动作 Top 倒序且不超过 8 条。
- `backend/tests/contract/test_frontend_types.py`：`AdminAnalytics` 顶层键、分桶与折线点两种嵌套结构逐层比。
