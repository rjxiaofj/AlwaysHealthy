"""确认卡片与 workflow_runs 状态的一致性守卫。

真 Postgres 上验过的事实：LangGraph 的 checkpointer 按 conversation.thread_id
只存一份断点，同会话所有 run 共用；`_fail` 只写 workflow_runs，图仍停在 interrupt。
于是旧确认卡片可能把新一轮的断点当成旧 run 继续，旧 run 又被改回 running。
这组用例在 sqlite + InMemorySaver 上守住同样的规则，CI 不需要起 Postgres。
"""

from uuid import UUID, uuid4

from app.db.models import WorkflowRun
from tests.helpers import (
    ASSESS_TEXT,
    collect_events,
    patch_profile,
    reach_plan_review,
    start_assessment,
)


def _errors(events):
    return [data for name, data in events if name == "run_error"]


async def _resume(client, headers, run_id, **extra):
    body = {"approval_type": "profile", "decision": "approve", **extra}
    return await collect_events(client, "POST", f"/api/v1/runs/{run_id}/resume/stream", headers, body)


async def _pending_run(client, auth, session):
    await patch_profile(client, auth)
    confirm = await start_assessment(client, auth)
    run = await session.get(WorkflowRun, UUID(confirm["run_id"]))
    assert run.status == "waiting_user"
    return confirm, run


async def test_new_message_cancels_stale_confirmation(client, auth, session) -> None:
    confirm, run = await _pending_run(client, auth, session)

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{run.conversation_id}/messages/stream",
        auth,
        {"content": ASSESS_TEXT},
    )
    assert events

    await session.refresh(run)
    # 旧 run 不能再挂着「待确认」，否则卡片还能点、状态永远不收口
    assert run.status == "cancelled"
    assert run.completed_at is not None

    errors = _errors(await _resume(client, auth, confirm["run_id"]))
    assert errors and errors[0]["code"] == "RUN_NOT_RESUMABLE"
    assert "过期" in errors[0]["message"]


async def test_resume_missing_run_reports_error(client, auth) -> None:
    # 之前这里是裸 return，前端收到一条空 SSE 流：转圈停了却什么也没说
    errors = _errors(await _resume(client, auth, str(uuid4())))
    assert errors and errors[0]["code"] == "RUN_NOT_FOUND"


async def test_failed_run_cannot_be_resurrected(client, auth, session) -> None:
    confirm, run = await _pending_run(client, auth, session)
    run.status = "failed"
    run.error_code = "WORKFLOW_TIMEOUT"
    await session.commit()

    errors = _errors(await _resume(client, auth, confirm["run_id"]))

    assert errors and errors[0]["code"] == "RUN_NOT_RESUMABLE"
    await session.refresh(run)
    # 守卫不能顺手把状态改回 running，failed 要留作审计
    assert run.status == "failed"
    assert run.error_code == "WORKFLOW_TIMEOUT"


async def test_waiting_user_run_still_resumes(client, auth, session) -> None:
    confirm, run = await _pending_run(client, auth, session)

    events = await _resume(client, auth, confirm["run_id"])

    # 画像确认放行后应停在计划确认，不能因为加了守卫把正常链路也挡掉
    assert any(name == "confirmation_required" for name, _ in events)
    await session.refresh(run)
    assert run.status == "waiting_user"


async def test_expiry_is_scoped_to_one_conversation(client, auth, session) -> None:
    _, run_a = await _pending_run(client, auth, session)
    confirm_b, run_b = await _pending_run(client, auth, session)
    assert run_a.conversation_id != run_b.conversation_id

    await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{run_a.conversation_id}/messages/stream",
        auth,
        {"content": ASSESS_TEXT},
    )

    await session.refresh(run_a)
    await session.refresh(run_b)
    assert run_a.status == "cancelled"
    assert run_b.status == "waiting_user"
    # 另一条会话的卡片仍应能正常恢复
    events = await _resume(client, auth, confirm_b["run_id"])
    assert any(name == "confirmation_required" for name, _ in events)


async def test_plan_approve_without_version_reports_error(client, auth) -> None:
    plan_confirm = await reach_plan_review(client, auth)

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{plan_confirm['run_id']}/resume/stream",
        auth,
        {"approval_type": "plan", "decision": "approve"},
    )

    errors = _errors(events)
    assert errors and errors[0]["code"] == "RUN_NOT_RESUMABLE"
