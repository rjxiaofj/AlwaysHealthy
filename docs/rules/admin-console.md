# 后台管理系统

本文定义 `/admin` 这套后台管理系统必须具备的能力与不可越过的边界。项目定位见 `AGENTS.md` 第 1 节，认证与数据隔离见 `docs/rules/auth-and-isolation.md`。

## 为什么必须有

毕业设计交付物要能被运维。管理员不连数据库、不改库就得能看出谁有管理员权限、处置连续登录失败、确认服务可用；只挂两个只读卡片、把运维动作全留在接口和 SQL 里，不算后台管理系统。

健康数据属于敏感个人信息。后台一旦能顺手查档案，权限提升就会直接变成数据泄露。所以后台管的是账号与平台安全，不是用户的健康数据。

## 必须有的能力

| 能力 | 验收口径 |
| --- | --- |
| 独立身份通道 | 登录页「用户登录 / 管理员登录」自由切换；管理员通道按库里的 role 校验；管理员登录后进 `/admin`，普通用户登录回前台 |
| 服务状态巡检 | 断点存储、检索通道、模型接口、工作流加载状态可读；接口失败有明确的「读取失败」提示，不误报成空数据 |
| 账号与角色管理 | 分页列出账号元数据（id、用户名、邮箱、role、status、创建时间、最后登录）；可把 `user` 改成 `admin` 或反向；操作后列表立即反映新角色 |
| 安全事件处置 | 列出最近事件；可把 `open` 处置成 `resolved` 并写 `resolved_at`；重复处置不报错；已处置事件不能被改回 |
| 审计留痕 | 角色变更与事件处置各写一条 `security_audit_logs`，记操作者、动作、资源、结果、请求编号 |

## 不可绕过的条件

1. 每个管理接口都依赖 `admin_user`，按数据库里的 `User.role` 判断，不看令牌里的 role。改库里的角色应立刻生效。
2. 新增管理接口统一挂 `/api/v1/admin/*`。已有的 `/health/services`（app 根路径，不在 `/api/v1` 下）与 `/api/v1/security/incidents` 是历史路径，保留但同样必须依赖 `admin_user`。
3. 管理响应只含账号元数据与安全事件。禁止出现 `password_hash`、刷新令牌、健康档案、评估、计划、报告、打卡、上传文件、LLM 提示词。
4. 角色变更禁止改自己的角色，禁止把最后一个管理员降为普通用户。`role` 只接受 `user` 与 `admin`，非法值走 422，不靠前端校验。
5. 建管理员只有两个入口：凭 `ADMIN_REGISTRATION_CODE` 邀请码注册，以及后台角色变更。两条都写审计。不做「普通用户自助申请管理员」「前端传 role 就生效」这类旁路。
6. 事件处置只允许 `open -> resolved` 单向收敛并写 `resolved_at`。不改 `description`、`severity`、`occurred_at`，不删记录，不开放重新打开。
7. 每个写操作都写审计，先提交再返回。`result` 是 `varchar(16)`，只写短状态词；失败分支要先提交审计再抛错，异常抛出后事务会被丢弃。
8. 前端 `requiresAdmin` 守卫不是权限边界。管理页多路首屏读取用 `Promise.allSettled` 各自降级，读失败要说「读取失败」，不能误报成「暂无数据」。
9. 不新造响应体、错误码、分页格式。列表统一 `page`、`page_size`，返回 `{items, total, page, page_size}`。

## 与「无后台调度」区分

`AGENTS.md` 第 2 节与 `docs/rules/plan-and-checkin.md` 里的「没有后台调度」说的是不引入 APScheduler、提醒按用户访问时生成，指的是定时任务。它和本规则要求的后台管理系统是两件事，改动时不要混为一谈，更不要拿它当作不做管理能力的理由。

## 实现状态

2026-11-06 已落地：登录身份选项卡、管理员邀请码注册、`/health/services`、`/api/v1/security/incidents`；新增 `GET /api/v1/admin/users`（分页账号元数据）、`PATCH /api/v1/admin/users/{id}/role`、`POST /api/v1/admin/incidents/{id}/resolve`，以及 `/admin` 页的账号管理与事件处置交互，详见 `docs/impact/2026-11-06-admin-console.md`。

后续加管理模块仍受本文约束；「当前只实现了 X」是进度描述，不是规则上限，不许反过来把规则削到只覆盖现状。

未纳入本轮：账号停用/启用、删除账号、事件重开、按用户名搜索、批量操作。要做这些先补影响分析与回归用例。

## 回归范围

- `backend/tests/api/test_admin_console.py`：权限、字段范围、角色护栏、状态收敛、审计与幂等。
- `backend/tests/api/test_auth_role.py`：邀请码注册这条建管理员入口。
- `backend/tests/contract/test_frontend_types.py`：管理接口响应的字段一致性。
- `frontend/src/views/AdminView.spec.ts`：多路首屏读取、写操作与失败降级。
- `docs/rules/auth-and-isolation.md` 的越权自测清单：普通用户与未登录访问管理接口必须被拒。
