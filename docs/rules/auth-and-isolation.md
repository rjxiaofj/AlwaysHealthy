# 认证与数据隔离

本文约束登录、令牌和跨用户访问。改动这里先按 AGENTS.md 第 3 节回答四个问题。

## 为什么这样设计

健康数据属于敏感个人信息，越权读一次就是泄露事故。平台没有多租户概念，隔离边界就是 user_id。
管理员默认不能查看他人健康档案，避免后台权限直接变成数据出口。

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

## 越权自测清单

- 用户 A 拿用户 B 的 plan_id 请求 `/plans/{id}`，应返回 404。
- 用户 A 提交用户 B 的 task_id 打卡，应返回 404。
- 用户 A 用用户 B 的 run_id 恢复工作流，应返回空响应且不泄露状态。
- 未登录访问任意业务接口，应返回 401 且 code 为 AUTH_UNAUTHORIZED。
- 过期 Access Token 应触发一次刷新，刷新失败后清理本地令牌。

对应自动化用例：`tests/api/test_auth.py`、`tests/regression/test_data_scope.py`。
