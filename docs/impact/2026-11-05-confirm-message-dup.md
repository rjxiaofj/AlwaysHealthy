# 影响分析：计划确认阶段重复写了一条画像确认的消息

日期：2026-11-05

## 现象

走完一次评估后，聊天里出现两条一字不差的「已记录：年龄 39，height_cm 175.0，…」。用接口验证不是前端渲染的问题，库里确实有两条 `message_type=confirm` 的消息，内容完全相同：

```
user      | text    | 我今年39岁，男，身高175…
assistant | confirm | 已记录：年龄 39，height_cm 175.0…
assistant | confirm | 已记录：年龄 39，height_cm 175.0…
assistant | text    | 评估完成，总体风险提示为高…
```

正确的情况应该是：画像确认阶段一条「已记录：…」，计划确认阶段一条提示「计划需要你确认后才会生效」。

## 根因

`graph_service._stream()` 收尾这段：

```python
snapshot = await self.graph.aget_state(config)
values = dict(snapshot.values or {})
reply = values.get("reply") or reply
```

`values["reply"]` 是**整条链上最后一次写进去的**回复，不是「这一段」的回复。恢复运行后：

- 画像确认这一段：data_collector 节点写了 `reply`，本地变量 `reply` 有值，落库正确。
- 计划确认这一段：assess → intervene → plan → plan_validator 四个节点都不写 `reply`，本地变量还是空，`values.get("reply")` 拿到的是 data_collector 那句旧文案。`_mark_waiting()` 把它当成本阶段的确认提示存了一条。

于是同一个字符串被存了两次。节点自己也是这么设计的——两个 `interrupt()` 都带了本阶段的 `message`：

- `review_profile_node`：`"请确认以上健康信息是否准确，确认后才会进入风险评估"`
- `review_plan_node`：`"计划需要你确认后才会生效，确认前可以要求修改"`

这两句才是该进聊天记录的东西。`_mark_waiting` 一直没用它。

## 做法

把「本地变量里这一段有没有新 reply」与「state 里的整体 reply」分开：

```python
fresh_reply = reply                      # 这一段里节点新产出的
reply = values.get("reply") or reply     # 补全用（_finish 仍然要它）

if interrupted is not None:
    payload = await self._enrich_interrupt(ctx, interrupted)
    yield ("confirmation_required", payload)
    text = fresh_reply or payload.get("message") or ""
    await self._mark_waiting(ctx, values, text)
    return
```

优先级是：本阶段有新回复就用新回复（画像确认阶段保住「已记录：…」这条用户真正需要看的信息），没有就用这次 interrupt 自带的阶段提示。

`_finish()` 那条路径不动，它本来就该用整体 `reply`。

## 测试

新增 `tests/regression/test_confirm_message.py`：

| 编号 | 场景 | 期望 |
|---|---|---|
| CM-01 | 只走到画像确认 | 恰好一条 confirm，内容以「已记录」开头 |
| CM-02 | 再走到计划确认 | 两条 confirm，内容互不相同，且第二条含「计划」 |

CM-01 是防回退的：如果图省事把 `_mark_waiting` 的文案全换成 interrupt 的 `message`，画像阶段那条「已记录：…」就没了，用户看不到系统识别出哪些值，这条会挂。

变异验证：把那行改回 `text = reply`，CM-02 红、CM-01 绿，正是预期。复原后两条都绿，后端全量 207 项通过。

## 影响面

| 范围 | 是否受影响 | 说明 |
|---|---|---|
| 接口 | 否 | 响应结构不变 |
| 聊天记录 | 是 | 计划确认阶段那条消息文案变了，历史数据不回溯 |
| 消息条数 | 是 | 同一流程少一条重复记录 |
| 前端 | 否 | 无改动 |
| 其他链路 | 否 | `_finish()` 的回复逻辑没动 |

## 遗留

- 已经产生的重复消息不会自动清理。演示库可以重置，真实数据要另写迁移或手工删。
- 计划阶段现在只存一句阶段提示，没有像画像阶段那样把「草稿标题/任务数」写进正文。这些信息在确认卡片里已经有了，正文再写一遍会更啰嗦，暂不加。
