# 后台管理系统

本文定义 `/admin` 这套后台管理系统的技术栈、能力清单与不可越过的边界。项目定位见 `AGENTS.md` 第 1 节，认证与数据隔离见 `docs/rules/auth-and-isolation.md`。

## 为什么必须有

毕业设计交付物要能被运维。管理员不连数据库、不改库就能管理账号与角色、处置安全事件、查看审计与模型/Agent 运行状态。只挂几个只读卡片、把运维动作全留在接口和 SQL 里，不算后台管理系统。

健康数据属于敏感个人信息。后台一旦能顺手查档案，权限提升就会直接变成数据泄露。所以后台管的是账号、平台安全与运行状态，不是用户的健康数据。

## 技术栈

完全沿用现有栈，不引入任何新框架：

| 层 | 选型 |
| --- | --- |
| 后端 | FastAPI + SQLAlchemy 2.1 async + asyncpg，接口统一挂 `/api/v1/admin/*` |
| 认证/权限 | JWT + `admin_user` 依赖，按库里 `User.role` 判断 |
| 前端 | Vue 3 + Pinia + vue-router，`/admin` 独立布局 `AdminLayout`，**不挂在 `AppLayout` 下**；复用 `.glass`/`.segment`/`.chip` 等玻璃拟态 token |
| 样式/可视化 | Tailwind；不引入 UI 组件库、不引入 echarts；折线与条形图用手写 SVG / div |
| 调度 | 不引入 APScheduler，与「无后台调度」原则一致 |

禁止为后台单独引入 Element Plus 之类的组件库——会破坏现有玻璃拟态风格、拉大体积、多维护一套组件约定。

## 页面结构

后台是独立外壳，侧边栏只放管理菜单。用户端导航（健康首页、智能助手、健康评估、健康管理、指标趋势、个人中心、待办提醒）不得出现在后台任何位置；管理员在后台看到的应该是管理能力，不是自己的健康入口。

路由与菜单一一对应，刷新和直达链接都能进：

| 菜单 | 路由 | 内容 |
| --- | --- | --- |
| 总览 | `/admin/overview` | 用户总数、管理员数、待处置事件、今日登录失败、今日新增账号、服务状态 |
| 数据看板 | `/admin/analytics` | 近 7 天新增账号与登录失败折线、账号角色/状态分布、审计动作 Top、事件分级、工作流状态 |
| 账号 | `/admin/accounts` | 列表（搜索/筛选/分页）、角色变更、停用/启用、硬删除 |
| 审计 | `/admin/audit` | `security_audit_logs` 分页查询，按 action / actor / result 过滤 |
| 安全事件 | `/admin/incidents` | 列表（按 status/severity 筛选）、`open -> resolved` 处置 |
| 模型与 Agent | `/admin/runtime` | 模型参数在线管理、Agent 清单加载状态、工作流运行统计、知识库状态 |

外壳保留「返回前台」「切换主题」「退出登录」三个出口，这三个不算用户端菜单。

## 能力清单

### 账号与角色

- 分页列出账号元数据；支持 `keyword`（用户名模糊）、`role`、`status` 过滤。
- 角色变更 `user <-> admin`；禁止改自己、禁止把最后一个管理员降权；非法 role 走 422。
- 停用/启用：`status` 在 `active` / `disabled` 之间切换；停用后该账号登录返回 401，已签发令牌随 `current_user` 的 `status != active` 校验失效。
- 硬删除：物理删除 `users` 行并级联其数据。必须输入目标用户名做二次确认、禁止删除自己、禁止删除最后一个管理员；写审计后不可恢复。

### 安全事件

- 列出最近事件，按 `status`（open/resolved）、`severity` 筛选。
- 处置只允许 `open -> resolved` 单向收敛并写 `resolved_at`；不改描述、级别、发生时间，不删记录、不开放重开；重复处置幂等。

### 审计日志

- `GET /admin/audit-logs` 分页返回审计记录，支持按 `action`、`actor_user_id`、`result` 过滤，按时间倒序。
- 只读，不提供删除或修改审计；审计本身只追加不覆盖。

### 统计总览

- `GET /admin/overview` 返回：用户总数、管理员数、待处置（open）事件数、今日登录失败数、今日新增账号数。

### 数据看板

- `GET /admin/analytics` 返回可视化数据，后台必须有图表，不能只有一行行数字。
- 折线：近 7 天每日新增账号、每日登录失败。横轴固定 7 天且连续，缺的那天补 0，否则折线的 x 轴会跳日。
- 条形：账号角色分布、账号状态分布、审计动作 Top N、安全事件分级、工作流运行状态。
- 时间归日按业务时区（`BUSINESS_TZ`）算，不在 SQL 里按天分组——SQLite 与 Postgres 对带时区时间戳的 `date()` 语义不同，同一份 SQL 会切出不同日界。
- 图表手写 SVG / div，不引图表库；颜色走 CSS 变量，深浅主题自动跟随。

### 模型与 Agent

- 模型参数可在线修改并热生效：`llm_model`、`llm_api_key`、`embedding_backend`。
- 配置可回显（含 `llm_api_key` 明文），但每次修改写审计、记操作者与时间，不记 key 明文到日志。
- 展示 Agent 清单（supervisor、emergency_router、data_collector、risk_assessment、intervention、plan、health_tracking、report 等）的加载状态。
- 展示 `workflow_runs` 运行统计：running / waiting_user / cancelled / failed 各状态的计数。
- 展示知识库状态：知识源数量、同步状态、检索 chunk 数。

模型/Agent 管理是**可观测 + 可调参**，不是切换或训练模型。切换本地 LLM 仍只需改配置，后台只是把改配置这一步搬到界面上并留审计。

## 不可绕过的条件

1. 每个管理接口都依赖 `admin_user`，按数据库里的 `User.role` 判断，不看令牌里的 role。
2. 新增管理接口统一挂 `/api/v1/admin/*`。已有的 `/health/services` 与 `/api/v1/security/incidents` 是历史路径，保留但同样依赖 `admin_user`。
3. 管理响应只含账号元数据、审计、安全事件、运行状态与模型配置。禁止出现健康档案、评估、计划、报告、打卡、上传文件、聊天内容、LLM 提示词。
4. 角色变更、停用/启用、删除、事件处置、参数修改都要写审计，先提交再返回。`result` 是 `varchar(16)`，只写短状态词；失败分支先提交审计再抛错。
5. 删除账号是硬删除、不可恢复：必须输入目标用户名二次确认、禁止删自己、禁止删最后一个管理员。
6. 模型参数在线修改写入运行时配置并持久化，重启后仍生效；`llm_api_key` 回显给管理员但不得写进审计或日志明文。
7. 事件处置保持单向收敛，不开放重开。
8. 前端 `requiresAdmin` 守卫不是权限边界；多路首屏读取用 `Promise.allSettled` 各自降级，读失败要说「读取失败」。
9. 不新造响应体、错误码、分页格式。列表统一 `page`、`page_size`，返回 `{items, total, page, page_size}`。
10. 后台走独立布局，不复用 `AppLayout`。侧边栏不得出现用户端导航项，也不得出现「待办提醒」这类个人入口——管理员的个人健康入口只在前台。
11. 后台必须有可视化数据，至少覆盖 7 日趋势与分布统计；图表不引 echarts 或其他图表库。

## 与「无后台调度」区分

`AGENTS.md` 第 2 节与 `docs/rules/plan-and-checkin.md` 里的「没有后台调度」说的是不引入 APScheduler、提醒按用户访问时生成，指的是定时任务。它和本规则要求的后台管理系统是两件事，不要混为一谈，更不要拿它当作不做管理能力的理由。

## 实现状态

2026-11-06 已落地：登录身份选项卡、管理员邀请码注册、`/health/services`、`/api/v1/security/incidents`、`/api/v1/admin/users`（分页）、`PATCH /api/v1/admin/users/{id}/role`、`POST /api/v1/admin/incidents/{id}/resolve`。

本轮按完整方案补齐：账号搜索/停用/硬删除、审计查询、事件筛选、统计总览、模型与 Agent 在线管理、后台侧边栏多菜单。详见 `docs/impact/2026-11-06-admin-console.md`。

2026-11-07 补齐：管理后台改为独立外壳 `AdminLayout`（`/admin` 不再挂在 `AppLayout` 下，侧边栏只剩管理菜单）、六个路由化面板、`GET /api/v1/admin/analytics` 与数据看板（7 日折线 + 五组分布条形）。详见 `docs/impact/2026-11-07-admin-shell-and-analytics.md`。

## 回归范围

- `backend/tests/api/test_admin_console.py`：权限、字段范围、角色/状态/删除护栏、事件收敛、审计、模型参数、看板聚合。
- `backend/tests/api/test_auth_role.py`：邀请码注册这条建管理员入口。
- `backend/tests/contract/test_frontend_types.py`：管理接口响应的字段一致性。
- `frontend/src/layouts/AdminLayout.spec.ts`：侧边栏只含管理菜单、用户端入口不出现、菜单改路由、退出登录。
- `frontend/src/views/AdminView.spec.ts`：按路由渲染面板、看板图表、写操作、二次确认与失败降级。
- `docs/rules/auth-and-isolation.md` 的越权自测清单：普通用户与未登录访问管理接口必须被拒。
