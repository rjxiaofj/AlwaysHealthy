import uuid
from datetime import date

from sqlalchemy import delete, select

from app.db.models import Notification, User
from tests.helpers import activate_plan


async def fresh_user(client, prefix: str) -> tuple[dict[str, str], str]:
    username = f"{prefix}{uuid.uuid4().hex[:8]}"
    response = await client.post("/api/v1/auth/register", json={"username": username, "password": "demo12345"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}, username


async def task_due_reminders(client, headers) -> list[dict]:
    items = (await client.get("/api/v1/reminders", headers=headers)).json()["data"]
    return [item for item in items if item["notification_type"] == "task_due"]


async def clear_task_due(session, username: str) -> None:
    # 提醒只在访问时生成，已生成的行不会随开关删除，清掉才能看出下一次生成的结果
    user_id = await session.scalar(select(User.id).where(User.username == username))
    await session.execute(
        delete(Notification).where(Notification.user_id == user_id, Notification.notification_type == "task_due")
    )
    await session.commit()


async def test_task_reminder_follows_switch(client, session) -> None:
    headers, username = await fresh_user(client, "rem")
    plan = await activate_plan(client, headers)
    today = date.today().isoformat()
    today_tasks = [item for item in plan["tasks"] if item["scheduled_date"] == today]
    assert today_tasks
    assert all(item["reminder_enabled"] for item in today_tasks)

    assert len(await task_due_reminders(client, headers)) == len(today_tasks)

    for task in today_tasks:
        response = await client.patch(f"/api/v1/tasks/{task['id']}", json={"reminder_enabled": False}, headers=headers)
        assert response.status_code == 200, response.text

    await clear_task_due(session, username)
    assert await task_due_reminders(client, headers) == []

    keep = today_tasks[0]["id"]
    await client.patch(f"/api/v1/tasks/{keep}", json={"reminder_enabled": True}, headers=headers)
    await clear_task_due(session, username)
    regenerated = await task_due_reminders(client, headers)
    assert len(regenerated) == 1
    assert regenerated[0]["related_object_id"] == keep


async def test_patch_task_rejects_bad_time(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = plan["tasks"][0]["id"]

    response = await client.patch(f"/api/v1/tasks/{task_id}", json={"scheduled_time": "25:00"}, headers=auth)
    assert response.status_code == 422


async def test_patch_task_sets_time(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = plan["tasks"][0]["id"]

    response = await client.patch(f"/api/v1/tasks/{task_id}", json={"scheduled_time": "08:30"}, headers=auth)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["scheduled_time"] == "08:30"
