from datetime import date, timedelta
from uuid import UUID

from app.db.models import HealthPlan
from tests.helpers import activate_plan, today_task_id


async def shift(client, headers, plan_id, start_date, reason=None):
    payload = {"start_date": start_date.isoformat()}
    if reason is not None:
        payload["reason"] = reason
    return await client.post(f"/api/v1/plans/{plan_id}/shift", json=payload, headers=headers)


async def test_shift_moves_plan_and_tasks(client, auth) -> None:
    plan = await activate_plan(client, auth)
    old_start = date.fromisoformat(plan["start_date"])
    old_end = date.fromisoformat(plan["end_date"])
    new_start = old_start + timedelta(days=3)

    response = await shift(client, auth, plan["id"], new_start, "出差推迟")
    assert response.status_code == 200, response.text

    data = response.json()["data"]
    assert data["start_date"] == new_start.isoformat()
    assert data["end_date"] == (old_end + timedelta(days=3)).isoformat()

    dates = {item["scheduled_date"] for item in data["tasks"]}
    assert min(dates) == new_start.isoformat()
    assert max(dates) <= data["end_date"]


async def test_shift_keeps_task_count_and_supersedes_old_version(client, auth) -> None:
    plan = await activate_plan(client, auth)
    old_version_id = plan["current_version_id"]
    task_titles = sorted(item["title"] for item in plan["tasks"])

    new_start = date.fromisoformat(plan["start_date"]) + timedelta(days=2)
    data = (await shift(client, auth, plan["id"], new_start)).json()["data"]

    assert sorted(item["title"] for item in data["tasks"]) == task_titles
    assert data["current_version_id"] != old_version_id

    status_by_id = {item["id"]: item["status"] for item in data["versions"]}
    assert status_by_id[old_version_id] == "superseded"
    assert status_by_id[data["current_version_id"]] == "active"


async def test_shift_rejects_past_date(client, auth) -> None:
    plan = await activate_plan(client, auth)
    response = await shift(client, auth, plan["id"], date.today() - timedelta(days=1))
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_HEALTH_DATA"


async def test_shift_rejects_same_date(client, auth) -> None:
    plan = await activate_plan(client, auth)
    response = await shift(client, auth, plan["id"], date.fromisoformat(plan["start_date"]))
    assert response.status_code == 422


async def test_shift_rejects_started_plan(client, auth, session) -> None:
    plan = await activate_plan(client, auth)

    row = await session.get(HealthPlan, UUID(plan["id"]))
    row.start_date = date.today() - timedelta(days=2)
    await session.commit()

    response = await shift(client, auth, plan["id"], date.today() + timedelta(days=5))
    assert response.status_code == 409
    assert "已经开始" in response.json()["message"]


async def test_shift_rejects_version_with_checkins(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = today_task_id(plan)

    checkin = await client.post(
        f"/api/v1/tasks/{task_id}/checkins",
        json={"status": "completed"},
        headers=auth,
    )
    assert checkin.status_code == 200, checkin.text

    response = await shift(client, auth, plan["id"], date.fromisoformat(plan["start_date"]) + timedelta(days=1))
    assert response.status_code == 409
    assert "打卡" in response.json()["message"]


async def test_shift_other_user_plan_not_found(client, auth) -> None:
    plan = await activate_plan(client, auth)

    other = await client.post("/api/v1/auth/register", json={"username": "shifttaker", "password": "demo12345"})
    other_headers = {"Authorization": f"Bearer {other.json()['data']['access_token']}"}

    response = await shift(client, other_headers, plan["id"], date.today() + timedelta(days=3))
    assert response.status_code == 404
