from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select

from app.core.timeutil import business_today
from app.db.models import HealthPlan, PlanTask, TrackingSummary
from tests.helpers import activate_plan, today_task_id


async def shift_cycle(session, plan) -> None:
    """把计划整体前移 13 天，任务日期跟着走，周期结束日仍是今天。"""
    row = await session.get(HealthPlan, UUID(plan["id"]))
    row.start_date = business_today() - timedelta(days=13)
    row.end_date = business_today()
    tasks = await session.scalars(select(PlanTask).where(PlanTask.plan_version_id == UUID(plan["current_version_id"])))
    for task in tasks:
        task.scheduled_date = task.scheduled_date - timedelta(days=13)
    await session.commit()


async def close_cycle(client, session, plan, headers) -> None:
    row = await session.get(HealthPlan, UUID(plan["id"]))
    row.end_date = business_today() - timedelta(days=1)
    await session.commit()
    # 列表会触发 close_expired，把过了结束日的 active 计划置为 completed
    await client.get("/api/v1/plans", headers=headers)


async def prepare_finished_cycle(client, session, plan, headers) -> str:
    task_id = today_task_id(plan)
    await shift_cycle(session, plan)
    checkin = await client.post(
        f"/api/v1/tasks/{task_id}/checkins",
        json={"status": "completed", "checkin_date": (business_today() - timedelta(days=1)).isoformat()},
        headers=headers,
    )
    assert checkin.status_code == 200, checkin.text
    await close_cycle(client, session, plan, headers)
    return task_id


async def test_report_requires_finished_cycle(client, auth) -> None:
    plan = await activate_plan(client, auth)

    response = await client.post(f"/api/v1/plans/{plan['id']}/report", headers=auth)
    assert response.status_code == 409
    assert "才结束" in response.json()["message"]


async def test_report_generated_after_cycle_end(client, auth, session) -> None:
    plan = await activate_plan(client, auth)
    await prepare_finished_cycle(client, session, plan, auth)

    response = await client.post(f"/api/v1/plans/{plan['id']}/report", headers=auth)
    assert response.status_code == 200, response.text

    data = response.json()["data"]
    assert data["report_type"] == "tracking"
    assert "阶段跟踪报告" in data["title"]
    headings = [section["heading"] for section in data["content"]["sections"]]
    assert "计划执行情况" in headings
    assert "健康指标变化" in headings

    summary = await session.scalar(
        select(TrackingSummary).where(TrackingSummary.plan_id == UUID(plan["id"]))
    )
    assert summary is not None
    assert float(summary.completion_rate) > 0
    assert summary.period_end == business_today() - timedelta(days=1)

    export = await client.get(f"/api/v1/reports/{data['id']}/export", headers=auth)
    assert export.status_code == 200
    assert "阶段跟踪报告" in export.text
    assert "任务完成率" in export.text

    printed = await client.get(f"/api/v1/reports/{data['id']}/print", headers=auth)
    assert printed.status_code == 200
    assert printed.headers["content-type"].startswith("text/html")
    assert "<!DOCTYPE html>" in printed.text
    assert "阶段跟踪报告" in printed.text


async def test_report_is_idempotent(client, auth, session) -> None:
    plan = await activate_plan(client, auth)
    await prepare_finished_cycle(client, session, plan, auth)

    first = await client.post(f"/api/v1/plans/{plan['id']}/report", headers=auth)
    second = await client.post(f"/api/v1/plans/{plan['id']}/report", headers=auth)
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]

    rows = await session.scalars(select(TrackingSummary).where(TrackingSummary.plan_id == UUID(plan["id"])))
    assert len(list(rows)) == 1


async def test_report_rejects_cancelled_plan(client, auth) -> None:
    plan = await activate_plan(client, auth)
    cancel = await client.post(f"/api/v1/plans/{plan['id']}/cancel", headers=auth)
    assert cancel.status_code == 200

    response = await client.post(f"/api/v1/plans/{plan['id']}/report", headers=auth)
    assert response.status_code == 409
    assert "不能生成周期报告" in response.json()["message"]


async def test_report_other_user_plan_not_found(client, auth) -> None:
    plan = await activate_plan(client, auth)

    other = await client.post("/api/v1/auth/register", json={"username": "reportother", "password": "demo12345"})
    other_headers = {"Authorization": f"Bearer {other.json()['data']['access_token']}"}

    response = await client.post(f"/api/v1/plans/{plan['id']}/report", headers=other_headers)
    assert response.status_code == 404
