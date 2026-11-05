# 登录失败聚合为安全事件影响分析

日期 2026-11-05。性质：把空壳表接上采集与查询。

`security_incidents` 建表起一行没写过。审计表里其实已经记了每次登录失败（`action=login`、`result=fail`、`resource_id=用户名`），但没人把它变成「事件」——运维侧看到的是散落的失败记录，看不出「这个账号正在被撞库」。

选登录失败做采集点，不选越权 404：越权在正常使用里也会出现（用户点错链接、前端缓存了别人的 id），做事件会淹掉真正的信号；连续错密码是明确攻击模式，阈值判定干净。

## 改动文件

后端

- `app/repositories/security.py` 新增：`count_login_failures`、`open_incident_for`、`add_incident`、`incidents_of`、`as_dict`。
- `app/services/security_service.py` 新增
  - `note_login_failure`：窗口 15 分钟、阈值 5 次，达标且窗口内没有未处置事件时插一条 `login_bruteforce`。统计前先 `flush`，否则本次失败的审计还没进事务，永远差一条，阈值触发不了。
  - `list_incidents`。
- `app/services/auth_service.py`：登录失败分支在写审计后调用 `note_login_failure`，仍由原来的 `commit` 一起提交。
- `app/api/v1/endpoints/security.py` 新增 `GET /security/incidents`，用 `admin_user` 依赖，`limit` 夹在 1 到 100。
- `app/api/v1/router.py` 注册路由。

测试

- `tests/api/test_security_incidents.py` 6 项：第 4 次失败不产生事件、第 5 次产生一条、继续失败不新增、两个账号各一条、普通用户 403、管理员可读、未登录 401。

## 依赖的公共方法

- `chat_repo.audit`：登录失败的审计写入点。改它的字段口径会同时影响这里的统计条件。
- `admin_user`：`app/api/deps.py` 里既有依赖，按数据库里的 `role` 判断，不看令牌里的 role，改权限立即生效。

## 受影响旧模块

- 登录流程：失败分支多一次按索引的 count 查询，成功分支不查。演示规模下可忽略。
- 审计：不改结构与写入内容。
- 用户表：不改。
- 迁移：`security_incidents` 表已存在，本次不新增列，不需要 Alembic。

## 权限与数据范围检查

- 事件是系统级的，没有 `user_id`，只给管理员看，普通用户 403。
- description 只写账号与前缀固定格式 `account=<用户名> failures=<次数> window=<分钟>min`，不写密码、不写令牌、不写请求体。
- 去重用 `description LIKE 'account=<账号> %'` 前缀匹配，避免 `demo` 与 `demo2` 互相吃掉对方的事件。
- 同一账号窗口内只留一条未处置事件，暴力破解期间不会把表刷爆。

## 回归用例

- `tests/api/test_auth.py`：确认登录成功与失败的响应没变。
- `tests/api/test_security_incidents.py`：本次新增。
- 容器实测：连续 6 次错密码只落一条事件；普通用户 403，改成管理员后能读到该条。
