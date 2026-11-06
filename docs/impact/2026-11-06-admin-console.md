# 后台管理系统：账号角色管理与安全事件处置

## 前置影响分析（AGENTS.md 第 7 节）

改动文件：

- 新增 `backend/app/repositories/admin.py`、`backend/app/services/admin_service.py`、`backend/app/schemas/admin.py`、`backend/app/api/v1/endpoints/admin.py`。
- 改 `backend/app/api/v1/router.py`（挂 admin 路由）、`backend/app/repositories/security.py`（补按 id 取事件）。
- 前端改 `src/api/types.ts`、`src/api/index.ts`、`src/views/AdminView.vue`、`src/views/AdminView.spec.ts`。
- 契约守卫改 `backend/tests/contract/test_frontend_types.py`；新增 `backend/tests/api/test_admin_console.py`。
- 不改数据库模型、不加迁移：账号与事件两张表、`security_audit_logs` 都已存在，本次只加接口与服务。

公共方法依赖：

- `admin_user`（`app/api/deps.py`）→ `current_user` → `repositories/health.get_user`，每次请求读库里的 `User.role`。
- `admin_service.list_users` → `repositories/admin.list_users`（`select(User)` + `func.count()`），输出走 `schemas/admin.AdminUserOut`，再由 `core/response.paged` 包 `{items,total,page,page_size}`。
- `admin_service.set_role` → `repositories/admin.user_of / count_admins` → `repositories/chat.audit` → `session.commit`，输出 `AdminUserOut`。
- `admin_service.resolve_incident` → `repositories/security.incident_of / as_dict` → `repositories/chat.audit` → `session.commit`。
- `security_service.note_login_failure` 仍是事件唯一采集点，本次不改它的 `flush`、阈值与去重逻辑。
- 前端 `adminApi` → `api/client.ts::api`（`base` 只给 `/health/services` 用，新接口都在 `/api/v1` 下）。

受影响旧模块：

- 列表：`/api/v1/security/incidents`、`/health/services` 保持原样；新增 `/api/v1/admin/users` 是独立的账号元数据列表，不复用任何健康业务列表。
- 定时任务：无。本改动不涉及「没有后台调度」那条约束，提醒按访问时生成的路径一行未动。
- 报表：无。报告导出、趋势统计不读 `users` 表。
- 工作流节点：无。`graph_service`、checkpointer、SSE 事件白名单都不变。
- 认证：`auth_service` 的注册/登录角色校验不改。角色变更让库里的 `role` 变化，`admin_user` 与登录 `expected_role` 会自动跟着生效，这正是按库校验想要的效果。

权限与数据范围检查：

- 三个新接口全部 `Depends(admin_user)`；未登录 401、普通用户 403。前端 `requiresAdmin` 仍只是少跑一趟。
- 账号列表用显式字段白名单 `AdminUserOut`，不 `model_dump` 整个 `User`：`password_hash`、刷新令牌、任何健康档案关联都不进响应。
- 管理接口不做 `user_id` 归属过滤（管理员看的是全站账号元数据），所以更要用字段白名单兜住范围；一旦有人往 `AdminUserOut` 加业务字段，契约守卫与字段范围用例会挂。
- 角色变更：`target` 不存在 404；禁止改自己、禁止把最后一个管理员降权，两条拒绝都先写 `result=fail` 审计并提交再抛 409；`role` 用 `Literal["user","admin"]`，非法值 422 不靠前端。
- 事件处置：只允许 `open -> resolved` 单向收敛，写 `resolved_at`；不改 `description`、`severity`、`occurred_at`，不删记录、不开放重开；重复处置返回当前状态不报错。
- 写操作审计只用短状态词（`varchar(16)`），先 `session.commit()` 再返回；读操作不写审计。
- 响应字典在 `commit()` 之前组装，避免 SQLAlchemy 异步会话 commit 后过期属性触发隐式 IO。

回归用例：

- T-新增：`tests/api/test_admin_console.py` 11 条（三接口权限、字段范围、分页、角色提升/降权、自身与末位护栏、非法角色、账号不存在、事件收敛、幂等、事件不存在、拒绝后落库未变、审计留痕）。
- R-关联：`tests/api/test_auth_role.py` 全量重跑（角色校验与邀请码注册）、`tests/contract/test_frontend_types.py`（`AdminUser` 映射 + 运行时键断言）、`tests/api/test_security.py` 若有事件采集用例一并重跑。
- E-全链路：注册普通账号 → 管理员读账号列表 → 提升为 admin → 该账号读管理接口 → 处置一条真实登录失败事件 → 再读列表与事件确认状态收敛；前端 `AdminView.spec.ts` 覆盖三路首屏读取、写操作与失败降级。

## 问题

规则已确立后台管理系统是必需能力（`docs/rules/admin-console.md`），但 2026-11-06 的 `/admin` 只有服务状态与安全事件两张只读卡片：管理员看得到「谁在暴力破解」，却不能处置；想改角色只能改库，想列账号只能连数据库。运维动作全留在 SQL 里，不符合规则。

## 方案

| 决策 | 做法 | 理由 |
| --- | --- | --- |
| 新接口放哪 | 统一 `/api/v1/admin/*`，不动已有 `/health/services` 与 `/security/incidents` | 规则要求新增管理接口统一前缀；历史路径改了会打断现有调用 |
| 账号列表输出 | 独立 `AdminUserOut` 字段白名单 + `paged` | 直接 `model_dump(User)` 会把 `password_hash` 带出去 |
| 建管理员的第二入口 | 后台角色变更，写审计、禁改自己、保留至少一个 admin | 与邀请码注册同等敏感，不能留无痕提权路径 |
| 事件处置语义 | `POST /admin/incidents/{id}/resolve`，幂等、单向收敛 | 前端按钮重复点、多标签同时点都不该炸；不允许把已处置事件改回 |
| 前端交互 | 服务状态 / 账号角色 / 安全事件三张卡片，三路 `Promise.allSettled` 各自降级 | 沿用现有读取降级策略，新增一路不能把整页拖空 |
| 失败提示 | 后端 `message` 直接展示，读失败与空数据分开 | 不误报「暂无」，也不让写操作静默失败 |

## 改动

**后端**

- 新增 `repositories/admin.py`（账号分页、按 id 取账号、数管理员）、`schemas/admin.py`（`AdminUserOut` 字段白名单、`RolePatchIn` 的 `Literal["user","admin"]`）、`services/admin_service.py`、`api/v1/endpoints/admin.py`；`api/v1/router.py` 挂上 `/api/v1/admin/*`。
- `admin_service.set_role`：不存在 404、改自己 409、末位管理员降权 409，三条拒绝都先写 `result=fail` 审计并提交再抛错；成功写 `result=success` 审计。角色相同直接返回当前值，不刷审计。
- `admin_service.resolve_incident`：`open -> resolved` 单向收敛、写 `resolved_at`、幂等返回当前状态，成功写审计；不改描述、级别、发生时间，不删记录、不开放重开。
- 写操作响应都在 `commit()` 之前组装，避免提交后再回读 ORM 对象触发异步会话隐式 IO。
- `repositories/security.py` 补 `incident_of`；`as_dict` 把 `occurred_at` / `resolved_at` 统一成带 `+00:00` 的 ISO 串。SQLite 存不下时区，刚写的 aware 时间与读回的 naive 时间原来会让同一条事件在「处置响应」和「列表」里字符串不一致，幂等断言就是这么先挂的。

**前端**

- `types.ts` 加 `AdminUser`；`adminApi` 加 `users / setRole / resolveIncident`。`AdminUser` 登记进契约守卫 `MAPPED`（对 `AdminUserOut`），另补两条运行时键断言。
- `AdminView.vue` 从两张卡片扩成三张：服务状态、账号与角色（分页、当前账号禁用操作、就地更新行）、安全事件（`open` 事件才有处置按钮，已处置显示处置时间）。三路首屏仍是 `Promise.allSettled` 各自降级，读失败各有对应空态；写操作失败显示后端 `message`，不误改本地行。
- `AdminView.spec.ts` 7 条首屏用例扩到 15 条，覆盖写操作、当前账号禁用、分页与失败降级。`vi.mock('@/api')` 要顺带提供 `authApi`，否则 `stores/auth.ts` 的具名导入在 mock 模块里取不到。

## 验证

| 编号 | 场景 | 结果 |
| --- | --- | --- |
| `test_admin_console.py` | 三接口未登录/普通用户被拒、字段白名单、分页、角色提升与降权、自身与末位护栏、非法角色、账号不存在、审计 | 9 条全绿 |
| 同上 | 事件收敛、幂等、证据字段不变、事件不存在 404 与审计 | 2 条全绿 |
| 契约守卫 | `AdminUser` 静态映射 + 账号列表/处置响应的运行时键断言 | 2 条全绿 |
| `AdminView.spec.ts` | 管理页三路读取、各自失败、写操作成功/失败、当前账号禁用、分页 | 15 条全绿 |

全量：后端 **331 passed**、前端 **220 passed**（212 + 8 条净增），`vue-tsc` / `vite build` / `npm run size` 全绿（首屏 50.2/58 kB、totalJs 90.4/100 kB）。

提交 `39d0954`，CI `42242946785` **success**。Docker 镜像重建后三容器 healthy，`/health/live` 200、`/health/ready` 的 database/knowledge 都是 up，镜像内含 `app/services/admin_service.py`。真容器端到端冒烟 **22/22**：SPA 与 `/api/docs`、普通/管理员注册、未登录 401 与普通用户 403、账号列表分页与字段白名单、角色提升后旧令牌立即生效、非法角色 422、禁止改自己 409、连续失败生成事件、处置收敛与幂等、`resolved_at` 带 UTC 偏移、普通用户不能处置。

变异验证 **5/5 被捕获**：去掉 `admin_user` 角色判断（3 条挂）、去掉禁止改自己角色（1 条挂）、事件字典丢 `resolved_at`（3 条挂）、管理页退回 `Promise.all`（首屏失败用例挂）、角色变更不再翻转角色（写操作用例挂）。脚本跑完无条件还原源码，五个锚点都核对过。

两处测试自己先挂出来的真问题，已修：

- `test_last_admin_cannot_be_demoted` 初版假绿：测试库全量用例共用，前面已建了多个 admin，`count_admins <= 1` 不成立。改成先把其他账号降权、断言库里确实只剩一个 admin 再触发护栏；`_audits` 也必须按 `resource_id` 过滤，否则别的用例留下的审计行会喂出假绿。
- `resolved_at` 字符串不一致：见上文 `as_dict` 的时区归一化。

## 残留取舍

1. 账号列表只按创建时间排序、不带搜索与筛选；账号规模大时翻页找人不方便。
2. 未做账号停用/启用、删除、事件重开、批量操作。规则里也没要求，但要加必须先走影响分析。
3. 角色变更没有二次确认弹窗，点一下就生效，靠后端护栏与审计兜底；演示够用，正式系统建议加确认并记录变更原因。
4. 「末位管理员」护栏在现有接口路径下不可达：操作者本身必须是 admin，自改又被禁，所以库里至少有两个 admin 才能触发降权分支。用服务层用例单独守着它，防的是将来放开自改或并发降权。
5. 角色变更不主动吊销目标账号已有令牌：`admin_user` 每次读库，所以降权立刻生效；但令牌里原有的 role 字段仍是旧值，只作展示，不作权限判断。
6. 管理页首屏现在并发读三路，任一失败只弹第一条错误文案，避免刷屏；后两路失败靠卡片上的「读取失败」空态区分。
