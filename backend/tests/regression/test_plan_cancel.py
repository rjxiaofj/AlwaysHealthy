from datetime import date, timedelta
from uuid import UUID

from app.db.models import HealthPlan
from tests.helpers import activate_plan, today_task_id


async def test_cancel_active_plan(client, auth) -> None:
    plan = await activate_plan(client, auth)

    response = await client.post(f"/api/v1/plans/{plan['id']}/cancel", headers=auth)
    assert response.status_code == 200, response.text

    detail = (await client.get(f"/api/v1/plans/{plan['id']}", headers=auth)).json()["data"]
    assert detail["status"] == "cancelled"


async def test_cancelled_plan_rejects_checkin(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = today_task_id(plan)
    await client.post(f"/api/v1/plans/{plan['id']}/cancel", headers=auth)

    response = await client.post(f"/api/v1/tasks/{task_id}/checkins", json={"status": "completed"}, headers=auth)
    assert response.status_code == 409
    assert "不能打卡" in response.json()["message"]


async def test_cancel_completed_plan_rejected(client, auth, session) -> None:
    plan = await activate_plan(client, auth)

    row = await session.get(HealthPlan, UUID(plan["id"]))
    row.start_date = date.today() - timedelta(days=14)
    row.end_date = date.today() - timedelta(days=1)
    await session.commit()

    # 结束日期已过，列表会把计划置为 completed
    await client.get("/api/v1/plans", headers=auth)

    response = await client.post(f"/api/v1/plans/{plan['id']}/cancel", headers=auth)
    assert response.status_code == 409
    assert "已结束" in response.json()["message"]


async def test_cancel_other_user_plan_not_found(client, auth) -> None:
    plan = await activate_plan(client, auth)

    other = await client.post("/api/v1/auth/register", json={"username": "cancelother", "password": "demo12345"})
    other_headers = {"Authorization": f"Bearer {other.json()['data']['access_token']}"}

    response = await client.post(f"/api/v1/plans/{plan['id']}/cancel", headers=other_headers)
    assert response.status_code == 404
