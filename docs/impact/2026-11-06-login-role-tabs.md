# 登录页身份选项卡与只读管理页

## 问题

用户要求登录页能在「用户登录 / 管理员登录」之间自由切换，并选择了「新建管理页」+「管理员选项卡下提示管理员注册」。

动手前的现状：

- 后端已有 `User.role` / `admin_user` 依赖，以及 `/health/services`、`/security/incidents` 两个管理接口；但 `docs/rules/auth-and-isolation.md` 写着「项目没有后台管理系统，没有页面入口」。
- 登录接口不校验期望角色，注册只会建 `role=user`，库里也没有管理员账号的初始化入口。只加一层选项卡 UI 的话，普通账号点「管理员登录」照样能进，选项卡只是文案。
- 让用户自助注册管理员等于把 `admin_user` 这道权限直接送人，不可接受。

## 方案

把身份做成**端到端可验证的通道**，并给管理员注册加一道可配置准入：

| 决策 | 做法 | 理由 |
| --- | --- | --- |
| 管理员账号从哪来 | 管理员注册入口 + `ADMIN_REGISTRATION_CODE` 邀请码，留空则不开放 | 满足「下面提示管理员注册」，又不让权限裸奔 |
| 选项卡是否校验 | 登录传 `expected_role`，后端按**库里的 role** 校验 | 前端文案不算权限；改库里的 role 应立刻生效 |
| 用户通道能否被管理员用 | 允许 | 选项卡是最低身份要求，不是精确匹配；管理员也要能看自己的前台 |
| 管理页边界 | 只读服务状态 + 安全事件 | 规则文档要求管理员不能查看他人健康档案，不新开任何档案查询入口 |
| 成功去向 | 管理员通道 → `/admin`；用户通道 → 原 redirect | 按**选中的通道**跳，不按账号 role，避免管理员从用户通道被硬塞进后台 |

## 改动

**后端**

- `app/core/config.py`：`admin_registration_code: str = ""`，留空 = 关闭管理员自助注册。
- `app/schemas/health.py`：`RegisterIn` 加 `role: Literal["user","admin"]` 与 `admin_code`；`LoginIn` 加 `expected_role`。
- `app/services/auth_service.py`：注册管理员时用 `secrets.compare_digest` 校验邀请码并写 `register_admin` 审计；登录时普通账号冒充管理员返回 403、写 `result=fail` 审计但**不**计入密码失败封禁阈值。
- 配置透传：`backend/.env.example`、`deployment/.env.example`、`deployment/docker-compose.yml`（`${ADMIN_REGISTRATION_CODE:-}`，默认关闭）。

**前端**

- `api/client.ts`：`api()` 增加可选 `base`，因为 `/health/*` 挂在 app 根路径、不在 `/api/v1` 下。
- `api/index.ts`：`authApi.login/register` 带上角色参数；新增 `adminApi`（services / incidents）。
- `api/types.ts`：`AccountRole`、`ServiceStatus`、`SecurityIncident`；契约守卫把后两者登记进 `NO_MODEL` 并补运行时键断言。
- `stores/auth.ts`：login/register 返回 `UserInfo`，新增 `isAdmin`（取 `/users/me` 的 role）。
- `views/LoginView.vue`：玻璃拟态分段选项卡；切换身份清密码/错误/邀请码、保留用户名、注册态收回登录态；管理员注册多一个邀请码输入；登录成功按通道跳转；错误展示后端 `message`。
- `router/index.ts`：`/admin` + `requiresAdmin` 守卫（按 `/users/me` 的 role，失败回首页）。
- `layouts/AppLayout.vue`：导航改 computed，管理员才追加「管理后台」；`AppIcon` 加 `shield` 图标。
- `views/AdminView.vue`：两路读取用 `Promise.allSettled`，一路挂掉另一路成功数据仍在；分别给「服务状态读取失败」「安全事件读取失败」空态，不把读失败误报成「暂无事件」。

## 验证

| 编号 | 场景 | 期望 |
| --- | --- | --- |
| AR-01~11 | 管理员注册（未配置/缺码/错码/正确码/非法 role/审计/真能读管理接口） | 只有正确码能建出真 admin |
| AR-12~16 | 登录角色（普通账号冒充被拒、审计、管理员走管理员通道、管理员也能走用户通道、老客户端不带字段照常登录） | 403 文案准确、不带字段向后兼容 |
| LT-01~11 | 登录页选项卡（默认态、双向切换、切换清态、两种通道的请求参数与跳转、邀请码表单、后端文案） | 11 条全绿 |
| AV-01~07 | 管理页（成功渲染、空态、两路各自失败、双失败、刷新、无效时间） | 7 条全绿 |
| CT-01~02 | 契约守卫对 `ServiceStatus` / `SecurityIncident` 的运行时键断言 | 端点少字段会挂 |

全量：后端 **315 passed**（301 + 12 条角色用例 + 2 条契约键断言）、前端 **212 passed**（194 + 18），`vue-tsc` / `vite build` / `npm run size` 全绿（首屏 50.1/58 kB、totalJs 89.4/100 kB）。

变异验证 **8/8 被捕获**：去掉后端 `expected_role` 校验、去掉邀请码校验、注册忽略 `role`、登录请求不带 `expected_role`、管理员不再跳 `/admin`、去掉邀请码前端拦截、事件失败不置 `incidentsFailed`、管理页退回 `Promise.all`——对应用例全部挂。脚本跑完无条件还原源码，已核对三个关键锚点都在。

## 残留取舍

1. 邀请码是**共享密钥**，不是按人分发的邀请链接：拿到它的人都能建管理员。演示够用；正式系统应改成一次性邀请令牌或由已有管理员审批。
2. 管理员注册成功后会立刻签发登录态并进 `/admin`，没有「待审核」状态。
3. `/admin` 目前只有两个只读卡片，没有账号管理、事件处置（把 `status` 改成 resolved）等操作；安全事件仍只能靠接口或改库处置。
4. 前端 `requiresAdmin` 守卫会在每次进 `/admin` 时走 `ensureUser()`（有 store 缓存，不重复发请求）；它只是少跑一趟，不是权限边界。
5. `expected_role` 是可选字段，老客户端不带时照常登录——向后兼容的代价是「不传字段」无法享受角色校验，但那种客户端本来也没有管理员选项卡。

## 后续修订：规则口径改为「项目必须有后台管理系统」

用户随后明确「项目需要有后台管理系统，把规则更新一下」。本文当时的方案表把「管理页边界」写成只读服务状态 + 安全事件，那是**当时的实现范围**，不是产品口径；残留取舍第 3 条记录的两个缺口现在属于必须补齐的能力，不再是允许长期留着的取舍。

本文保留原样不改历史事实，规则改动落在：

- `AGENTS.md` 第 1、2、3、4、5 节：后台管理系统列为交付物必需能力；「无后台调度」与后台管理系统消歧；大动脉表加管理接口；事件处置单向收敛；新增管理接口路径与依赖约定。
- 新增 `docs/rules/admin-console.md`：五项必需能力、九条不可绕过条件、实现状态与回归范围。
- `docs/rules/auth-and-isolation.md`：去掉「只读管理页」定性，新增「后台管理系统」小节；`docs/rules/plan-and-checkin.md` 补「没有后台调度」的消歧句。
- `README.md` 增加后台管理系统说明；`MEMORY.md` 追加规则变更段并修正已知取舍第 7 条。
- 后续实现见 `docs/impact/2026-11-06-admin-console.md`。
