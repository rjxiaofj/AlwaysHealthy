# 认证与数据隔离

本文约束登录、令牌和跨用户访问。改动这里先按 AGENTS.md 第 3 节回答四个问题。

## 为什么这样设计

健康数据属于敏感个人信息，越权读一次就是泄露事故。平台没有多租户概念，隔离边界就是 user_id。
项目必须交付后台管理系统，但管理员管理的是账号与平台安全，不是用户的健康数据：管理员默认不能查看他人健康档案，避免后台权限直接变成数据出口。后台的能力清单与禁止项另见 `docs/rules/admin-console.md`。

## 不可绕过的条件

1. 所有业务查询必须带用户归属条件。`app/repositories/*.py` 里每个函数第一参数是 user_id，不允许出现只按业务 id 查询的公共方法。
2. 资源不存在与资源不属于当前用户返回同一个 404。区分这两种情况会暴露 id 是否存在。
3. 刷新令牌只存 sha256 哈希。轮换时旧令牌立即置 revoked_at，重复使用按失效处理。
4. Access Token 只放 Authorization 头。SSE 也用 fetch 携带，不放查询参数，避免进入访问日志。
5. 工作流恢复前先查 conversation.user_id，再查 workflow_runs.user_id，最后才按 thread_id 恢复。

## 令牌与密码

- 密码用 Argon2id，参数 time_cost=3、memory_cost=65536、parallelism=2。
- Access Token 默认 30 分钟，演示环境可调到 120 分钟，只影响本地体验。
- Refresh Token 默认 14 天，一次一换。
- 密钥从环境变量读取。仓库里只有 `.env.example`。

## 审计与授权留痕

- 登录成功、登录失败、令牌重用、退出都写 `security_audit_logs`。
- 审计只记动作、资源、结果、请求编号。禁止写密码、令牌原文、完整档案。
- `result` 列是 `varchar(16)`，只能写 `success`、`fail`、`requested` 这类短状态词。往里面塞自由文本在 SQLite 上不会报错、在 Postgres 上直接 `value too long`，2026-11-05 的重新评估接口就是这么炸的。需要记原因就写日志，不写审计。
- 登录失败分支要先提交审计再抛错，异常抛出后事务会被丢弃，漏提交等于没有审计。
- 知情同意每发生一次状态变化写一条 `consent_records`，授权与撤回都留痕，撤回不覆盖旧记录。
- 同意类型只开放 `health_data` 与 `ai_analysis`，新增类型要同步前端文案与授权说明。

## 安全事件

- `security_incidents` 目前只有一个采集点：登录连续失败。窗口 15 分钟、阈值 5 次，同一账号在窗口内只留一条未处置事件。
- 采集实现在 `app/services/security_service.py::note_login_failure`，由 `auth_service.login` 的失败分支调用。统计前必须 `flush`，否则本次失败的审计还没进事务，统计永远差一条，阈值一辈子触发不了。
- `description` 固定前缀 `account=<用户名>`，去重靠这个前缀精确匹配，避免 `demo` 与 `demo2` 互相吃掉对方的事件。禁止把密码、令牌、请求体写进这一栏。
- 不拿越权 404 做采集点。正常使用里的 404 噪声会淹掉真实信号，越权行为靠接口用例覆盖而不是靠事件表。
- 读取只开 `GET /security/incidents`，用 `admin_user` 依赖，按数据库里的 `role` 判断，不看令牌里的 role。后台管理系统是项目必需交付物，前端入口是 `/admin`；它能管账号与安全事件，但不提供任何健康档案、评估、计划的查询入口，`admin_user` 依赖仍是唯一的数据边界。具体能力清单见 `docs/rules/admin-console.md`。

## 管理员账号与身份选项卡

- 注册接口默认只建 `role=user`。要建管理员必须同时传 `role=admin` 与 `admin_code`，后者和 `ADMIN_REGISTRATION_CODE` 做常量时间比较；配置留空 = 不开放管理员自助注册，这是安全默认值。
- 登录页的「管理员登录」传 `expected_role=admin`，后端按**库里的 role** 校验。普通账号从管理员通道进来返回 403 并留一条 `result=fail` 审计；密码是对的，不计入 `note_login_failure` 的封禁阈值。
- 「用户登录」是最低身份要求而不是精确匹配：管理员也能从用户通道进前台，侧边栏管理入口按 `/users/me` 的 role 显示。
- 前端 `/admin` 的路由守卫只用来别让普通用户白跑一趟，**不是权限边界**；真正拦数据的仍是后端 `admin_user`。
- 管理员注册与角色不符都留审计。审计字段只写短状态词，禁止写邀请码、密码或令牌。
- 后台的角色变更是建管理员的第二个入口，和邀请码注册同等敏感：只有管理员本人能操作，必须写审计，禁止改自己的角色，禁止把最后一个管理员降成普通用户。

## 后台管理系统

项目必须有后台管理系统，不能只交付一个只读看板。它至少提供账号与角色管理、安全事件处置、服务状态巡检，且每个写操作留审计。完整规则在 `docs/rules/admin-console.md`；这里只重申两条最容易踩的红线：

1. 管理接口一律用 `admin_user` 按库里的 `role` 判断。前端 `/admin` 的 `requiresAdmin` 守卫只减少普通用户白跑一趟，不是权限边界。
2. 管理接口只能返回账号元数据与安全事件。任何把档案、评估、计划、报告、打卡、上传文件拼进管理响应的改动，都视为越权数据出口，先改文档也不放行。

## 越权自测清单

- 用户 A 拿用户 B 的 plan_id 请求 `/plans/{id}`，应返回 404。
- 用户 A 提交用户 B 的 task_id 打卡，应返回 404。
- 用户 A 用用户 B 的 run_id 恢复工作流，应返回空响应且不泄露状态。
- 未登录访问任意业务接口，应返回 401 且 code 为 AUTH_UNAUTHORIZED。
- 过期 Access Token 应触发一次刷新，刷新失败后清理本地令牌。

## 前端会话失效

令牌在浏览器侧的收尾放在 `api/client.ts` 一处，别在各页面各写一份：

- 401 先尝试刷新并重放一次，失败才认为会话结束。并发的 401 由模块级 `refreshTask` 合并成一次 `/auth/refresh`。
- 只在**这次请求带了 `Authorization`** 时才判定会话过期。登录接口密码错也是 401，那次请求不带令牌，不加这个判断会把刚填的用户名冲掉、还弹一条「登录已过期」。
- 判定过期后调 `setSessionExpiredHandler` 注册的回调（`main.ts` 里注册，跳登录页并把当前路径塞进 `redirect`），同时清令牌。回调里自己去重：布局和页面会同时拿到 401。
- 通知开关在 `tokens.save()` 时复位，否则退出再登录后第二次过期不会再跳。
- 登录页的 `redirect` 只接受站内绝对路径（`utils/redirect.ts`）。`//evil.com` 会被浏览器当成协议相对地址跳到外站，数组形态则让 `router.push` 行为不可预期。

对应自动化用例：`tests/api/test_auth.py`、`tests/api/test_auth_role.py`、`tests/api/test_admin_console.py`、`tests/regression/test_data_scope.py`、`src/api/client.spec.ts`、`src/views/AdminView.spec.ts`、`src/utils/redirect.spec.ts`。
