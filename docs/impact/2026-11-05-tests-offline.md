# 影响分析：测试不再真的调用模型

日期：2026-11-05

## 现象

本地 `pytest backend` 从三十秒左右变成九分二十三秒（563.10s），231 项全绿，CI 上同样是绿、只要二十五秒。同样的代码，本地慢二十倍。

追下去发现不是慢，是在等网络。`--durations` 排前面的用例全是八到十五秒：

```
15.33s call  tests/api/test_features.py::test_nh_03_assessment_has_five_dimensions_with_sources
14.52s call  tests/regression/test_regression.py::test_rt_02_new_active_plan_supersedes_old_version
 8.43s call  tests/regression/test_plan_adjustment_feedback.py::test_feedback_rejects_other_users_plan
```

单独跑其中一个做 `cProfile`，最热的函数是 `_overlapped.GetQueuedCompletionStatus`（7.14s / 2939 次）——事件循环在空转等 I/O，不是算力问题。再把 `asyncio.sleep` 与 `time.sleep` 打桩，日志里直接露出：

```
INFO httpx HTTP Request: POST https://api.deepseek.com/v1/chat/completions "HTTP/1.1 200 OK"
```

一个用例五次，每次 1.5 到 2 秒。

## 根因

`backend/.env` 里有跑演示时填的真实 `LLM_API_KEY`（`.env` 不入库，但本地一直在）。`tests/conftest.py` 只覆盖了 `DATABASE_URL`、`CHECKPOINTER`、`JWT_SECRET` 这些，没管模型密钥。`Settings` 用 `env_file=".env"`，于是本地测试读到了真密钥，`GraphDeps.use_llm=True`，整条评估链路都去打 DeepSeek。

CI 上 `.env` 不存在，密钥为空，`use_llm=False`，走的是确定性回退——所以 CI 一直是对的，本地反而是例外。

## 做法

`tests/conftest.py` 在所有 `app.*` 导入之前加一行，把密钥显式清空：

```python
os.environ["LLM_API_KEY"] = ""
```

环境变量优先级高于 `.env`，所以本地与 CI 从此跑的是同一条「模型不可用」路径。

再加 `tests/unit/test_offline.py` 两条守卫：

- `test_model_key_is_blank_so_tests_never_call_the_api`：密钥一旦被改回来就红，避免下次又悄悄联网。
- `test_unavailable_model_returns_none_instead_of_raising`：`try_complete` 在无密钥时返回 `None` 而不是抛，所有调用方都靠这个约定回落到确定性文案。

## 结果

| | 改动前 | 改动后 |
|---|---|---|
| 本地 `pytest backend` | 563.10s | 33.10s |
| 用例数 | 231 | 233 |
| 是否联网 | 是，每轮数十次真实模型调用 | 否 |
| 与 CI 路径 | 不一致（本地走模型，CI 走回退） | 一致 |

顺带的收益：测试结果不再随模型输出浮动。之前本地能过、CI 能过是运气——两边的文案本来就不一样，只是断言都写得足够宽。
