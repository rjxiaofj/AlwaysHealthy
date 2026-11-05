# 影响分析：工作流自己收口（后端超时）

日期：2026-11-05

## 问题

前端有两道闸：空闲 45 秒、总时长 180 秒。但这两道都在浏览器这一侧——断连只是不再读，后端那趟 `astream` 还在跑，`workflow_runs.status` 会一直停在 `running`。用户回到聊天页，看到一条永远「进行中」的记录，也没有任何提示说它其实永远不会完成。

`recursion_limit: 30` 只限制节点步数，管不住「单个节点卡住」：模型不返回、检索挂起，都发生在一步之内。而 LLM 客户端自己有 45 秒超时加一次重试，最坏情况一步就接近 90 秒，五个节点串起来可以远超前端那 180 秒。

## 做法

`GraphService._stream` 用 `asyncio.timeout(settings.workflow_timeout_seconds)` 包住整个 `astream`：

- 超时 → `_fail(ctx, ..., code="WORKFLOW_TIMEOUT")` 把 run 标成 failed，再发一条 `run_error` 事件，前端现成的 toast 就会显示「这次分析没有在预期时间内完成，请稍后重试或把问题拆小一点」。
- `_fail` 增加 `code` 参数，让「超时」与「普通崩溃」在库里能区分开，排查时不用靠错误文案猜。
- 默认 150 秒（`WORKFLOW_TIMEOUT_SECONDS`）。**必须比前端的 180 短**：先由后端收口才能把状态写对；反过来是前端先断、后端还在算。

`except TimeoutError` 必须写在 `except Exception` 前面。`TimeoutError` 是 `OSError` 的子类，顺序写反的话超时会被当成普通崩溃，用户拿到的建议（「稍后重试」）与文案完全错位——这一点单独有一条用例守着。

## 验证

| 编号 | 输入 | 期望 | 实际 |
|---|---|---|---|
| WT-01 | `astream` 永久挂起，预算 0.05 秒 | 只发一条 `run_error`，code 为 `WORKFLOW_TIMEOUT`，`_fail` 收到同一错误码，上游被真正取消 | 符合（用例断言 `graph.cancelled is True`，不是「只是不读了」） |
| WT-02 | `astream` 抛 `ValueError` | code 是 `GRAPH_EXECUTION_ERROR`，不能说成超时 | 符合 |

变异：把超时分支里的 code 改成 `GRAPH_EXECUTION_ERROR`，WT-01 挂。后端 260 → 262 项。

测试绕过 `__init__`（它会去 `build_main_graph`），直接给 `_stream` 一个假图与假 settings——这条分支不需要真的跑图，跑真图反而验不到「卡住」。

## 取舍

- 150 秒是硬上限。长对话（多轮确认 + 重新评估）如果本来就要跑更久，会被截断。真要按需放宽，应该按运行类型分别设，而不是全局调大。
- 超时只覆盖「工作流跑不完」。LLM 单次调用 45 秒 + 一次重试 = 90 秒的粒度没变，那段仍可能在预算内白白消耗。
- 取消依赖 LangGraph 对 `CancelledError` 的处理：内存 checkpointer 下实测能干净退出；Postgres checkpointer 上（部署形态）还没在真库里验过断点状态是否一致，容器冒烟不含这一条。
