# 影响分析：流式超时、离开页面中断、以及字段可空性的契约守卫

日期：2026-11-05

补的是上一轮标记为「没做完」的两件事。

## 一、流式请求没有任何超时

`readStream` 的 `await reader.read()` 会一直等下去。后端卡住不返回（模型挂了、连接被中间设备吞掉、容器被暂停）时，前端表现是输入框上方一直显示「正在处理」，没有超时也没有报错，用户只能刷新页面。

### 做法

`src/api/stream.ts` 里给每次 `read()` 套一个 45 秒的空闲计时：

```ts
async function readWithIdle(reader, timeoutMs) {
  let timer
  try {
    return await Promise.race([reader.read(), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new IdleTimeout()), timeoutMs)
    })])
  } finally {
    if (timer) clearTimeout(timer)
  }
}
```

超时后主动 `reader.cancel()`，抛 `服务端超过 45 秒没有返回数据，请稍后重试`。

计时是**空闲**计时不是总时长：每收到一片数据就重新计。一次完整的评估链路在前面的实测里跑过二十多秒，卡 45 秒没数据才算异常。

### 二、离开页面不断开

`ChatView` 原来调 `streamMessage(...)` 不传 `AbortSignal`，`stream.ts` 那三个函数虽然都留了 `signal` 参数，一直没人用。切到别的路由后流还在读，读完再往已卸载的组件里写 `streamingText`，同时触发一次 `refreshMessages()`。

现在组件持有模块级 `controller`：

- `startStream()` 每次发消息前先 `abort()` 上一个，避免上一轮的 token 拼进新消息。
- `onBeforeUnmount` 里 `abort()`，并置 `destroyed = true`，`finally` 里的 `refreshMessages()` 跳过。
- `catch` 里用 `isAbortError` 把主动取消过滤掉，不弹「发送失败」——那是用户自己切页面造成的。

抽了 `src/utils/abort.ts` 的 `isAbortError`，三行，配三条用例（DOMException、普通 Error、非对象）。

注意：这是**客户端**断开，后端的图还在跑，回复仍会落库，下次进来能看到。加「停止生成」按钮会让人以为后端也停了，所以没加。

## 三、契约只比字段名，不比可空性

上一轮那层守卫只验证「前端声明过的字段，模型里有没有」。类型对不对完全没管，而这一类里有一个方向会真的崩：

模型写 `str | None`、前端写 `string`，模板里 `item.title.length` 拿到 null 就是 `TypeError: Cannot read properties of null`。反过来（前端写 `| null`、后端永远给值）只是声明松一点，不会崩。

### 做法

解析 `types.ts` 时连类型文本一起抓（`key: type` 的 type 部分，`?` 表示可选）。新增 `test_frontend_allows_null_when_model_can`：模型字段注解含 `None` 时，前端必须写 `| null` 或者标 `?`。

跳过三类：`Any` 注解（pydantic 里的万能类型，等于没约束）、`Record<` 与内联对象字面量（结构性类型，与 null 无关）、`unknown`/`any`。

### 抓到的问题

`EvidenceSource` 的 `source_id`、`title`、`version` 在前端是 `string`，后端 `SourceOut` 三个都是 `str | None = None`。这不是模型写松了——`risk_assessment.py` 里除了规则引擎给的标准来源，还会合并 LLM 造出来的 `evidence_sources`，那边只保证 `source_id` 非空，`title`/`version` 可能缺。

前端声明改成 `string | null` 之后 `vue-tsc` 立刻报了一个真错：`AssessmentView` 里 `:key="source.source_id"` 不接受 null。改成 `source.source_id || index`，索引来自 `v-for`。

## 测试

| 编号 | 场景 | 期望 |
|---|---|---|
| ST-01 | 45 秒没收到任何数据 | 主动 cancel 并抛出「服务端超过 45 秒没有返回数据」 |
| ST-02 | 每 30 秒来一片数据，累计 60 秒 | 不中断，两个事件都派发出去 |
| AB-01~03 | `isAbortError` 对 DOMException、普通 Error、非对象 | 只有 AbortError 为真 |
| NC-01~24 | 每个映射过的接口逐个字段比可空性 | 前端不许漏 `| null` |

变异验证：把 `IDLE_TIMEOUT_MS` 从 45 秒改成 90 秒，ST-01 挂（测试只把时钟推到 45 秒，`readWithIdle` 永远不 reject，用例超时）。复原后全绿。

## 影响面

| 范围 | 是否受影响 | 说明 |
|---|---|---|
| 接口 | 否 | 后端没动 |
| 聊天 | 是 | 45 秒无数据会报错；切页会断开客户端连接 |
| 类型 | 是 | `EvidenceSource` 三个字段改成可空，`AssessmentView` 的 key 跟着改 |
| 其他页面 | 否 | 不经过流式 |
| 测试 | 是 | 前端 110 → 115，后端 205 → 231（新增 26 条可空性参数化） |

## 遗留

- 超时只覆盖「读不到数据」。如果服务端每 44 秒发一个心跳，链路实际已经死了，前端还是会一直等。真正要治得在后端给工作流加超时，或者前端按总时长封顶（比如 3 分钟），两者都还没做。
- 可空性只检查模型注解，不看字段默认值。`title: str = ""` 这种注解非空、实际能塞进 None 的情况（pydantic 默认不校验赋值）漏不掉也拦不住。
- 反过来那个方向（前端写了 `| null`、模型不可能给 null）故意不检查：声明松一点不会崩，查了只会逼着改一堆无害的地方。
