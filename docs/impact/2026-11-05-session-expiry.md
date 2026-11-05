# 影响分析：登录态过期后回登录页、首屏读不到数据要说话

日期：2026-11-05

## 一、令牌过期后续不上，人卡在空壳页面里

`api()` 收到 401 会尝试 `/auth/refresh`，刷新失败时 `tokens.clear()` 然后抛出 `ApiError`。到这里就断了：没人告诉应用「这个人的会话没了」。

实际表现是：

- `AppLayout` 的 `onMounted` 里 `await auth.ensureUser()` 抛出，后面那行 `reminders.load()` 根本不执行，还留一条未处理的 promise 拒绝在控制台。
- 各个页面拿到一串 401，各自弹自己的错误提示，一屏能叠三四条。
- 页面结构还在（导航、头部照常显示），但所有数据区都是空状态。用户看着像「我的记录全没了」，而不是「我该重新登录了」。
- 唯一的出路是自己在左下角找到退出按钮。移动端抽屉里，这个按钮要展开菜单才看得到。

### 做法

在 `api/client.ts` 里加一个回调注册位，而不是让 api 层去 `import router`（那会让 api 反向依赖路由，环）。

```ts
export function setSessionExpiredHandler(handler: (() => void) | null)
```

`api()` 的 401 分支改成：

1. 先按原逻辑尝试刷新并重放。
2. 重放仍失败、或刷新本身失败，就检查**这次请求有没有带 `Authorization`**。带了才调 `notifySessionExpired()`。

为什么要看这个头：登录接口密码错也是 401，但那次请求不带令牌。不加这个判断的话，密码输错一次就会被当成「登录过期」，把用户刚填的用户名冲掉。

`notifySessionExpired()` 里做三件事：置一次性开关、清本地令牌、叫一声。开关的作用是并发去重——布局和页面同时发请求时会有多个 401 一起回来，不拦的话提示会叠一屏。开关在 `tokens.save()` 时复位，否则退出再登录之后，第二次过期不会再跳。

`main.ts` 里注册具体动作：弹一条「登录已过期，请重新登录」，把当前路径塞进 `redirect`，跳登录页。已经在登录页就不重复跳。

`AppLayout` 的 `ensureUser()` 补 `.catch(() => undefined)`：跳转的事已经有人负责，这里只是别让它变成未处理拒绝、别挡住后面的提醒加载。

### 二、首屏请求失败时页面只剩空状态

`DashboardView.load()` 和 `TrendsView.load()` 只有 `finally` 没有 `catch`。`Promise.all` 里任何一路挂掉（不是 401 也算，比如后端 500、网络断），整个函数就停在那里：`loading` 归位，但页面上全是「还没有评估结果」「还没有指标记录」这类空状态。

这两句文案的语义是「你还没填」，用在一个读失败的时刻就是在误导。两处都补 `catch`，走 toast 说清楚读失败了。

`TrendsView` 里 `load` 还挂在观察范围的 `@change` 上，补 `catch` 之后这条链路也不会再往下抛。

### 三、回跳地址只认站内路径

`LoginView` 原来是 `(route.query.redirect as string) || '/'`。两个问题：

- 传 `?redirect=//evil.com` 时，浏览器把 `//` 开头的地址当协议相对地址，跳到外站。用户在登录页输完密码，落点却是别人的页面——钓鱼最省事的一步。
- 同一个参数出现多次时，`route.query.redirect` 是数组，`router.push(数组)` 行为不可预期。

抽成 `src/utils/redirect.ts` 的 `safeRedirect()`：只接受以单个 `/` 开头的字符串，其余一律回首页。数组取第一个。

底层还是 `router.push()`，vue-router 对不匹配的路径有兜底重定向，所以这不是唯一防线；但让不该进来的值进到路由里，本身就没什么好处。

### 四、顺带

`stores/auth.ts` 的 `loggedIn` 是 `computed(() => Boolean(tokens.access))`，全仓没人用。而且 `tokens.access` 读的是 `localStorage`，不是响应式数据，这个 computed 没有任何依赖，算一次就永久缓存——真有人拿来当登录态用，登录成功后它也不会变。删掉。

## 测试

`client.spec.ts` 新增 5 项：

| 编号 | 场景 | 期望 |
|---|---|---|
| SE-01 | 带令牌 401，刷新也 401 | 回调调 1 次，令牌清空 |
| SE-02 | 三个请求同时过期 | 回调只调 1 次 |
| SE-03 | 登录接口自己返回 401 | 回调不调 |
| SE-04 | 刷新成功但重放仍 401 | 回调调 1 次 |
| SE-05 | 重新登录（`tokens.save`）后再次过期 | 回调能再调，累计 2 次 |

`redirect.spec.ts` 新增 7 项：站内路径、缺参数、`//` 开头、带协议、不以斜杠开头、参数重复、非字符串。

变异验证：

| 改坏的地方 | 挂掉的用例 |
|---|---|
| 删掉 `if (headers.Authorization) notifySessionExpired()` | SE-01~05 共 4 项（SE-03 应保持绿，实际保持绿） |
| 删掉 `tokens.save()` 里的开关复位 | 4 项 |
| 删掉 `notifySessionExpired()` 开头的去重判断 | 只有 SE-02 |

## 影响面

| 范围 | 是否受影响 | 说明 |
|---|---|---|
| 接口 | 否 | 只改前端 |
| 401 语义 | 是 | 带令牌的 401 现在会清令牌并跳登录页 |
| 登录页 | 是 | `redirect` 只接受站内绝对路径 |
| 首屏提示 | 是 | 首页与趋势页读失败会弹提示，不再只有空状态 |
| 后端 | 否 | 无改动 |

## 验证

- 前端 `npm test` 89 项通过（新增 5 项会话过期、7 项回跳）。
- `vue-tsc --noEmit` 与 `npm run build` 通过。
- CI 上一次运行（`925a9f0`）两 job 均绿。

## 遗留

- 回调目前只在 `main.ts` 注册一处，跳转依赖 `router` 已创建。若以后有单测要覆盖 `main.ts` 这段，得把它抽成可注入的函数。
- 会话过期是「事后发现」。想提前处理可以在 `tokens.save()` 里按 `expires_in` 记一个到期时间，到点主动续一次；现在的刷新是请求驱动的，用户空闲时不产生刷新。
- `DashboardView.load()` 里 `Promise.all` 塞了四个 promise 却只解构三个（第四个 `reminderStore.load()` 靠 `Promise.all` 等着）。功能上没错，但读起来像漏了一个，以后动这块容易改错。
