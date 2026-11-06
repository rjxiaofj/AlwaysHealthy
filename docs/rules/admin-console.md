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
| 前端 | Vue 3 + Pinia + vue-router，`/admin` 独立路由，复用 `.glass`/`.segment`/`.chip` 等玻璃拟态 token |
| 样式/可视化 | Tailwind；不引入 UI 组件库、不引入 echarts；趋势图用手写 SVG |
| 调度 | 不引入 APScheduler，与「无后台调度」原则一致 |

禁止为后台单独引入 Element Plus 之类的组件库——会破坏现有玻璃拟态风格、拉大体积、多维护一套组件约定。

## 页面结构

后台改为侧边栏多菜单，五个视图：

| 菜单 | 内容 |
| --- | --- |
| 总览 | 用户总数、管理员数、待处置事件、今日登录失败、今日新增账号 |
| 账号 | 列表（搜索/筛选/分页）、角色变更、停用/启用、硬删除 |
| 审计 | `security_audit_logs` 分页查询，按 action / actor / result 过滤 |
| 安全事件 | 列表（按 status/severity 筛选）、`open -> resolved` 处置 |
| 模型与 Agent | 模型参数在线管理、Agent 清单加载状态、工作流运行统计、知识库状态 |

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

## 与「无后台调度」区分

`AGENTS.md` 第 2 节与 `docs/rules/plan-and-checkin.md` 里的「没有后台调度」说的是不引入 APScheduler、提醒按用户访问时生成，指的是定时任务。它和本规则要求的后台管理系统是两件事，不要混为一谈，更不要拿它当作不做管理能力的理由。

## 实现状态

2026-11-06 已落地：登录身份选项卡、管理员邀请码注册、`/health/services`、`/api/v1/security/incidents`、`/api/v1/admin/users`（分页）、`PATCH /api/v1/admin/users/{id}/role`、`POST /api/v1/admin/incidents/{id}/resolve`。

本轮按完整方案补齐：账号搜索/停用/硬删除、审计查询、事件筛选、统计总览、模型与 Agent 在线管理、后台侧边栏多菜单。详见 `docs/impact/2026-11-06-admin-console.md`。

## 回归范围

- `backend/tests/api/test_admin_console.py`：权限、字段范围、角色/状态/删除护栏、事件收敛、审计、模型参数。
- `backend/tests/api/test_auth_role.py`：邀请码注册这条建管理员入口。
- `backend/tests/contract/test_frontend_types.py`：管理接口响应的字段一致性。
- `frontend/src/views/AdminView.spec.ts`：多视图首屏读取、写操作、二次确认与失败降级。
- `docs/rules/auth-and-isolation.md` 的越权自测清单：普通用户与未登录访问管理接口必须被拒。
