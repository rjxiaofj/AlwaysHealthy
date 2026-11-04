# 主工作流

本文约束 `app/graph/` 与 `app/services/graph_service.py` 的改动。

## 结构

单一 MainGraph，评估与跟踪是主图里的两条分支，不拆子图。
节点顺序：

```
safety -> supervisor -> collect -> validate -> review_profile -> assess
       -> intervene -> plan -> validate_plan -> review_plan -> final_check -> report
```

咨询、跟踪、报告查询、计划调整是旁路，直接进对应节点后结束。
高危消息在 safety 节点拦下，进入 emergency 节点，不经过任何普通节点。

## 为什么节点不写业务表

`interrupt()` 恢复时节点会从函数开头重新执行。节点内如果有数据库写入，恢复就会重复写。
所以节点只做三件事：读数据、算结果、返回状态增量。评估、计划、报告、高危事件的落库全部由 GraphService 在节点更新或中断时统一处理。

新增节点前先确认它不写库、不调外部副作用接口。必须写库时，改为把结果放进 state，由 service 落库。

## 中断与恢复

- 确认点只有两个：健康画像确认、计划确认。
- 恢复前 `resume_run` 校验 run 归属与 conversation 归属。
- 计划确认在恢复前先落库，status 由 pending_review 改 active，旧版本置 superseded。
- 确认 paylaod 必须带 business_id 与 version_id，不允许只按 plan_id 确认，否则并发下会确认错版本。
- 修改计划走 revise_draft，生成新版本，不覆盖旧版本。修改轮次上限 2，超过后直接出结果，避免死循环。

## SSE

- 事件白名单在 `app/core/sse.py`。新增事件必须同时改前端 `src/api/stream.ts` 的解析。
- 只推业务阶段名，不推节点内部状态、提示词、工具参数。
- 客户端断开不重发。前端凭 run_id 查询状态，避免重复执行。

## 改动回归范围

改 safety 或 emergency：`tests/unit/test_emergency_router.py`、`tests/api/test_flow.py::test_emergency_message_skips_normal_flow`。
改中断或恢复：`test_assessment_flow_reaches_report`、`test_checkin_is_idempotent`。
改节点顺序：全部 graph 相关用例，并人工走一遍从采集到报告的页面流程。
