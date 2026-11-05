from datetime import date, timedelta

from tests.helpers import activate_plan, today_task_id


async def patch_date(client, headers, task_id, scheduled_date):
    return await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"scheduled_date": scheduled_date.isoformat()},
        headers=headers,
    )


async def test_reschedule_moves_task(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = today_task_id(plan)
    target = date.today() + timedelta(days=1)

    response = await patch_date(client, auth, task_id, target)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["scheduled_date"] == target.isoformat()

    detail = (await client.get(f"/api/v1/plans/{plan['id']}", headers=auth)).json()["data"]
    moved = next(item for item in detail["tasks"] if item["id"] == task_id)
    assert moved["scheduled_date"] == target.isoformat()


async def test_reschedule_same_date_is_noop(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = today_task_id(plan)

    response = await patch_date(client, auth, task_id, date.today())
    assert response.status_code == 200
    assert response.json()["data"]["scheduled_date"] == date.today().isoformat()


async def test_reschedule_rejects_past_date(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = today_task_id(plan)

    response = await patch_date(client, auth, task_id, date.today() - timedelta(days=1))
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_HEALTH_DATA"


async def test_reschedule_rejects_outside_plan_range(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = today_task_id(plan)
    beyond = date.fromisoformat(plan["end_date"]) + timedelta(days=1)

    response = await patch_date(client, auth, task_id, beyond)
    assert response.status_code == 422
    assert "周期" in response.json()["message"]


async def test_reschedule_rejects_task_with_checkin(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = today_task_id(plan)

    checkin = await client.post(f"/api/v1/tasks/{task_id}/checkins", json={"status": "completed"}, headers=auth)
    assert checkin.status_code == 200, checkin.text

    response = await patch_date(client, auth, task_id, date.today() + timedelta(days=1))
    assert response.status_code == 409
    assert "打卡" in response.json()["message"]


async def test_reschedule_rejects_task_of_old_version(client, auth) -> None:
    plan = await activate_plan(client, auth)
    old_task_id = today_task_id(plan)

    shifted = await client.post(
        f"/api/v1/plans/{plan['id']}/shift",
        json={"start_date": (date.today() + timedelta(days=2)).isoformat()},
        headers=auth,
    )
    assert shifted.status_code == 200, shifted.text

    response = await patch_date(client, auth, old_task_id, date.today() + timedelta(days=3))
    assert response.status_code == 409
    assert "旧版本" in response.json()["message"]


async def test_reschedule_other_user_task_not_found(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = today_task_id(plan)

    other = await client.post("/api/v1/auth/register", json={"username": "taskmover", "password": "demo12345"})
    other_headers = {"Authorization": f"Bearer {other.json()['data']['access_token']}"}

    response = await patch_date(client, other_headers, task_id, date.today() + timedelta(days=1))
    assert response.status_code == 404
