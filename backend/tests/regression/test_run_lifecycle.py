"""workflow_runs 的生命周期收口。

真 Postgres 上验过的事实：checkpointer 按 conversation.thread_id 只存一份断点，
同会话所有 run 共用。由此派生出三条必须守住的边界：

1. 客户端断连时 Starlette 抛 CancelledError / GeneratorExit（都是 BaseException），
   原来只 catch Exception，run 会永远挂在 running；
2. cancelled 是终态，被顶替的旧流迟到的收尾不能把它改回活状态、不能再追加回复；
3. 新一轮开跑要收掉同会话所有活 run，resume 只能被一条请求原子抢到。

这组用例在 sqlite + 内存 checkpointer 上跑，CI 不需要起 Postgres。
"""

import asyncio
from contextlib import suppress
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import Conversation, ConversationMessage, User, WorkflowRun
from app.repositories import chat as chat_repo
from app.services.graph_service import GraphService, RunContext
from tests.helpers import ASSESS_TEXT, collect_events, reach_plan_review


class _HangGraph:
    """吐一个节点后永久挂住，用来模拟用户 abort 时后端还停在某个 LLM 节点。"""

    def __init__(self, yield_first=True):
        self.blocked = asyncio.Event()
        self.yield_first = yield_first

    async def astream(self, *args, **kwargs):
        if self.yield_first:
            yield {"safety": {}}
        self.blocked.set()
        await asyncio.Event().wait()
        yield {}  # pragma: no cover - 取消前不会走到

    async def aget_state(self, config):
        return SimpleNamespace(values={})


def _service_with(graph):
    service = GraphService.__new__(GraphService)
    service.graph = graph
    service.settings = get_settings()
    return service


async def _make_run(session, status="running"):
    user = User(username=f"lc{uuid4().hex[:10]}", password_hash="x")
    session.add(user)
    await session.flush()
    conversation = Conversation(user_id=user.id, thread_id=f"thread-{uuid4().hex}")
    session.add(conversation)
    await session.flush()
    run = WorkflowRun(
        conversation_id=conversation.id,
        thread_id=conversation.thread_id,
        user_id=user.id,
        run_type="message",
        status=status,
    )
    session.add(run)
    await session.commit()
    return conversation, run


async def _message_count(session, conversation_id):
    # 测试库是全量用例共用的，别用无条件 count：别的用例留下的消息会混进来
    return await session.scalar(
        select(func.count())
        .select_from(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
    )


# ---------- 1. 断连收口 ----------


async def test_disconnect_closes_running_run(session) -> None:
    conversation, run = await _make_run(session)
    graph = _HangGraph()
    service = _service_with(graph)
    ctx = RunContext(run_id=run.id, conversation=conversation)

    async def drive():
        async for _ in service._stream({}, ctx, resume=False, budget=60):
            pass

    task = asyncio.create_task(drive())
    await asyncio.wait_for(graph.blocked.wait(), 2)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    await session.refresh(run)
    assert run.status == "cancelled"
    assert run.error_code == "CLIENT_DISCONNECTED"
    assert run.completed_at is not None


async def test_generator_close_closes_running_run(session) -> None:
    """生成器被 aclose（而不是 task.cancel）时抛的是 GeneratorExit，也要收口。"""
    conversation, run = await _make_run(session)
    service = _service_with(_HangGraph())
    ctx = RunContext(run_id=run.id, conversation=conversation)

    stream = service._stream({}, ctx, resume=False, budget=60)
    first = await stream.__anext__()
    assert first[0] == "node_progress"
    await stream.aclose()

    await session.refresh(run)
    assert run.status == "cancelled"
    assert run.error_code == "CLIENT_DISCONNECTED"


async def test_workflow_timeout_is_not_mistaken_for_disconnect(session) -> None:
    """asyncio.timeout 内部也用 CancelledError，新增的取消分支不能把超时吞掉。"""
    conversation, run = await _make_run(session)
    service = _service_with(_HangGraph(yield_first=False))
    ctx = RunContext(run_id=run.id, conversation=conversation)

    events = [event async for event in service._stream({}, ctx, resume=False, budget=0.01)]

    assert any(name == "run_error" and data["code"] == "WORKFLOW_TIMEOUT" for name, data in events)
    await session.refresh(run)
    assert run.status == "failed"
    assert run.error_code == "WORKFLOW_TIMEOUT"


# ---------- 2. cancelled 是终态 ----------


async def test_cancelled_survives_late_finish(session) -> None:
    conversation, run = await _make_run(session, status="cancelled")
    service = _service_with(_HangGraph())

    await service._finish(
        RunContext(run_id=run.id, conversation=conversation),
        {"workflow_status": "completed"},
        "迟到的回复",
    )

    await session.refresh(run)
    assert run.status == "cancelled"
    assert await _message_count(session, conversation.id) == 0


async def test_cancelled_survives_late_fail_and_waiting(session) -> None:
    first_conv, first_run = await _make_run(session, status="cancelled")
    second_conv, second_run = await _make_run(session, status="cancelled")
    service = _service_with(_HangGraph())

    await service._fail(RunContext(run_id=first_run.id, conversation=first_conv), "超时")
    await service._mark_waiting(
        RunContext(run_id=second_run.id, conversation=second_conv),
        {"current_stage": "review_profile"},
        "迟到的确认卡片",
    )

    await session.refresh(first_run)
    await session.refresh(second_run)
    assert first_run.status == "cancelled"
    assert second_run.status == "cancelled"
    # 确认卡片和失败兜底都不能再往会话里写消息
    assert await _message_count(session, first_conv.id) == 0
    assert await _message_count(session, second_conv.id) == 0


async def test_late_waiting_cannot_revive_superseded_run(session) -> None:
    """旧 run 还在 running 时用户发了新消息，它随后走到 interrupt 也不能复活。"""
    conversation, run = await _make_run(session)
    service = _service_with(_HangGraph())

    affected = await chat_repo.cancel_live_runs(session, conversation.id)
    await session.commit()
    assert affected == 1

    await service._mark_waiting(
        RunContext(run_id=run.id, conversation=conversation),
        {"current_stage": "review_profile"},
        "旧流的确认卡片",
    )

    await session.refresh(run)
    assert run.status == "cancelled"
    assert run.error_code == "SUPERSEDED"
    assert await _message_count(session, conversation.id) == 0


# ---------- 3. 新一轮收口与 resume 原子抢占 ----------


async def test_new_message_cancels_running_run(client, auth, session) -> None:
    created = (await client.post("/api/v1/conversations", headers=auth, json={})).json()["data"]
    conversation_id = UUID(created["id"])
    user_id = await session.scalar(select(User.id).where(User.username == auth["username"]))
    stale = WorkflowRun(
        conversation_id=conversation_id,
        thread_id=created["thread_id"],
        user_id=user_id,
        status="running",
    )
    session.add(stale)
    await session.commit()

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        auth,
        {"content": ASSESS_TEXT},
    )
    assert any(name == "run_started" for name, _ in events)

    await session.refresh(stale)
    assert stale.status == "cancelled"
    assert stale.error_code == "SUPERSEDED"
    # 新一轮自己不能被收掉
    fresh = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.conversation_id == conversation_id,
            WorkflowRun.id != stale.id,
        )
    )
    assert fresh is not None and fresh.status != "cancelled"


async def test_claim_resume_is_single_use(session) -> None:
    """同一张确认卡片只能被抢占一次，这是 CAS 的最小语义。"""
    _, run = await _make_run(session, status="waiting_user")

    assert await chat_repo.claim_resume(session, run.id) is True
    await session.commit()
    assert await chat_repo.claim_resume(session, run.id) is False
    await session.commit()

    await session.refresh(run)
    assert run.status == "running"


async def test_resume_lost_race_reports_error(client, auth, session, monkeypatch) -> None:
    async def _never_claim(*args, **kwargs):
        return False

    # 先把卡片造出来再打桩：reach_plan_review 自己也要走一次 resume
    plan_confirm = await reach_plan_review(client, auth)
    run_id = plan_confirm["run_id"]
    monkeypatch.setattr("app.repositories.chat.claim_resume", _never_claim)

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{run_id}/resume/stream",
        auth,
        {"approval_type": "profile", "decision": "approve"},
    )

    errors = [data for name, data in events if name == "run_error"]
    assert errors and errors[0]["code"] == "RUN_NOT_RESUMABLE"
    assert "已被处理" in errors[0]["message"]
    # 抢不到不能顺手把状态改坏，得留给真正抢到的那条
    run = await session.get(WorkflowRun, UUID(run_id))
    assert run.status == "waiting_user"


async def test_resume_precheck_failure_does_not_leave_orphan(client, auth, session) -> None:
    """抢占已落库但计划版本失效时，要把 run 收口，不能留一条没人跑的 running。"""
    plan_confirm = await reach_plan_review(client, auth)
    run_id = plan_confirm["run_id"]

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{run_id}/resume/stream",
        auth,
        {
            "approval_type": "plan",
            "decision": "approve",
            "business_id": plan_confirm["plan_id"],
            "version_id": str(uuid4()),
        },
    )

    assert any(name == "run_error" for name, _ in events)
    run = await session.get(WorkflowRun, UUID(run_id))
    await session.refresh(run)
    assert run.status == "cancelled"
    assert run.error_code == "RESUME_PRECHECK_FAILED"
