# workflow_runs 生命周期收口（断连 / 顶替 / 重复恢复）

## 问题

真 Postgres 上验过：LangGraph 的 checkpointer 按 `conversation.thread_id` 只存**一份**断点，同会话所有 run 共用；而 `workflow_runs` 是按 run 一行。上一轮修了「旧确认卡片把新一轮断点当成旧 run 继续」，但状态机还留着三个口子：

1. **断连孤儿**：`StreamingResponse` 的生成器在前端 abort / 关标签页时被取消，抛的是 `CancelledError` 或 `GeneratorExit`，两者都是 `BaseException`。`_stream` 原来只有 `except TimeoutError` / `except Exception`，接不住，`_fail` 不会执行，这条 run 永远停在 `running`，`completed_at` 空着。
2. **cancelled 能被复活**：`_finish` / `_fail` / `_mark_waiting` 无条件写状态。旧流被新消息顶替后仍在 `astream` 里跑，晚一步走到 interrupt 就把自己写回 `waiting_user`——那时断点已属于新一轮，resume 守卫反而会放行，同时还会往会话里追加一张没人该点的确认卡片。
3. **重叠窗口与双标签**：`expire_pending_runs` 只收 `waiting_user`；`resume_run` 是「先 SELECT 判断 status，再 Python 里赋值 running」。两个标签页同时点同一张卡片时两边都读到 `waiting_user`，会把两条 `Command(resume=...)` 打进同一个 thread。

## 方案

把 `cancelled` 定为**终态**，状态转移全部下推成带条件的 SQL `UPDATE`，用 `rowcount` 判定谁真正拿到了状态：

- 同会话「活状态」= `running` + `waiting_user`，新一轮开跑前一次性收干净；
- 断连收口只把 `running` → `cancelled`，不碰任何终态；
- `waiting_user` → `running` 由数据库原子抢占，抢不到的请求直接回 `RUN_NOT_RESUMABLE`；
- 三个收尾方法遇到 `cancelled` 一律直接返回，不改状态、不追加消息。

`asyncio.timeout` 内部也用 `CancelledError` 实现，所以取消分支必须放在 `except TimeoutError` **之后**；`__aexit__` 会先把内部超时转成 `TimeoutError`，外部取消才落到新分支。新增 WT 类用例专门守这个顺序。

## 改动

- `app/repositories/chat.py`
  - `expire_pending_runs` → `cancel_live_runs`：`status.in_(LIVE_RUN_STATUSES)` 条件更新，写 `cancelled` + `completed_at` + `SUPERSEDED`。
  - 新增 `cancel_run(session, run_id, code)`：仅 `running` 可改，终态不覆盖。
  - 新增 `claim_resume(session, run_id)`：`waiting_user` → `running` 的 CAS，返回 `bool(rowcount)`。
  - 三处都带 `execution_options={"synchronize_session": False}`，走纯 SQL，不让 ORM 同步或额外 `RETURNING` 干扰已在 identity map 里的 `run`。
- `app/services/graph_service.py`
  - `start_run` 改调 `cancel_live_runs`。
  - `resume_run`：参数校验 → `claim_resume` → **立刻 commit**（另一个标签才看不到 `waiting_user`）→ 计划确认/拒绝。前置校验失败时 `rollback` + `cancel_run(..., "RESUME_PRECHECK_FAILED")`，不留没人跑的 `running`。
  - `_stream` 新增 `except (asyncio.CancelledError, GeneratorExit)`：调 `_cancel` 后 `raise`，不吞取消。
  - 新增 `_cancel(ctx, code)`；`_finish` / `_fail` / `_mark_waiting` 开头加 `cancelled` 终态守卫。
  - 错误码新增 `CLIENT_DISCONNECTED` / `SUPERSEDED` / `RESUME_PRECHECK_FAILED`（`String(48)` 内）。
- `backend/tests/regression/test_run_lifecycle.py`：新增 10 条，用 `_HangGraph`（吐一个节点后永久挂住）模拟断连，不依赖 Docker / 真 Postgres。

## 验证

| 编号 | 场景 | 期望 |
|---|---|---|
| LC-01 | `task.cancel()` 取消流 | `cancelled` / `CLIENT_DISCONNECTED` / `completed_at` 非空 |
| LC-02 | `stream.aclose()` 抛 `GeneratorExit` | 同样收口 |
| LC-03 | `budget=0.01` 触发 `asyncio.timeout` | 仍是 `failed` / `WORKFLOW_TIMEOUT`，不被取消分支吞掉 |
| LC-04 | cancelled 后调 `_finish` | 状态不变、不追加 assistant 消息 |
| LC-05 | cancelled 后调 `_fail` / `_mark_waiting` | 状态不变、不追加确认卡片 |
| LC-06 | 旧 `running` 被顶替后迟到 `_mark_waiting` | 保持 `cancelled` / `SUPERSEDED` |
| LC-07 | 发新消息时同会话有 `running` 旧 run | 旧 run 收口、新 run 不被误伤 |
| LC-08 | `claim_resume` 连调两次 | 第一次 True、第二次 False |
| LC-09 | 抢占失败（打桩模拟双标签） | `RUN_NOT_RESUMABLE` +「已被处理」，状态仍是 `waiting_user` |
| LC-10 | 计划版本失效导致前置校验失败 | `cancelled` / `RESUME_PRECHECK_FAILED`，不留孤儿 |

全量：后端 **301 passed**（275 → 301 的累积口径，本轮 +10），前端 194 passed / `vue-tsc` / `vite build` / `npm run size` 全绿。

变异验证 6/6 被捕获：去掉取消分支、去掉 `_finish` 守卫、把 live 状态退回只收 `waiting_user`、去掉 CAS 条件、前置校验失败不收口、把取消分支放宽成 `BaseException` 并前移——对应用例全部挂。

## 残留取舍

- `cancelled` 只写业务表，**不删 checkpointer 里的旧断点**。真 Postgres 实测该 thread 的 checkpoint 行数仍会增长，靠新一轮从 `START` 重跑覆盖。要彻底清理得给 checkpointer 加按 thread 的删除策略，属于另一层改动。
- 取消状态**不会中止已经在跑的图**：断连后那条 `astream` 仍可能继续到 `asyncio.timeout` 的预算上限，期间会占用模型/检索资源，并且仍在写同一个 thread 的断点。真正的隔离需要按 `thread_id` 串行的执行锁，本次没有引入（锁要跨 150s LLM 调用，风险比收益大）。
- `cancel_live_runs` 会把同会话所有 `running` 收掉。这是基于「一个 thread 一份断点」的必然结论，但也意味着后端重启/多实例下若有跨进程并发，后启动的那轮会顶掉先启动的。单实例部署成立。
