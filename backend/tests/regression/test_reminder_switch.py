import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core.timeutil import business_today
from app.db.models import Notification, User
from tests.helpers import activate_plan, today_task_id


@pytest.fixture(autouse=True)
def _freeze_to_late_evening(monkeypatch):
    """把「现在」钉在 23:59，晚于所有任务的 scheduled_time。

    提醒按任务设定时间判断要不要催，早上跑测试时晚间任务会被跳过，导致「今日任务数
    等于提醒数」这类断言飘。固定到深夜让所有任务都算已到点，语义与本文件的历史断言一致。
    """
    from app.services import reminder_service

    late = datetime(2026, 11, 5, 23, 59, tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(reminder_service, "business_now", lambda: late)
    yield


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
    today = business_today().isoformat()
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


async def test_checkin_marks_only_its_own_reminder_read(client) -> None:
    headers, _ = await fresh_user(client, "chk")
    plan = await activate_plan(client, headers)
    today = business_today().isoformat()
    today_tasks = [item for item in plan["tasks"] if item["scheduled_date"] == today]
    assert len(today_tasks) > 1

    assert len(await task_due_reminders(client, headers)) == len(today_tasks)

    done = today_task_id(plan)
    response = await client.post(f"/api/v1/tasks/{done}/checkins", json={"status": "completed"}, headers=headers)
    assert response.status_code == 200, response.text

    # 访问提醒列表时 sync 会把已完成任务的待完成提醒标已读
    items = (await client.get("/api/v1/reminders", headers=headers)).json()["data"]
    by_task = {item["related_object_id"]: item for item in items if item["notification_type"] == "task_due"}
    assert by_task[done]["read_at"] is not None
    for task in today_tasks:
        if task["id"] != done:
            assert by_task[task["id"]]["read_at"] is None

    again = (await client.get("/api/v1/reminders", headers=headers)).json()["data"]
    again_row = next(item for item in again if item["related_object_id"] == done)
    assert again_row["read_at"] == by_task[done]["read_at"]


async def test_sync_does_not_touch_other_user_reminder(client, session) -> None:
    headers, _ = await fresh_user(client, "chk")
    plan = await activate_plan(client, headers)

    _, other_username = await fresh_user(client, "oth")
    other_id = await session.scalar(select(User.id).where(User.username == other_username))
    session.add(
        Notification(
            user_id=other_id,
            notification_type="task_due",
            title="他人提醒",
            content="不该被本用户的同步动到",
            dedup_key="task_due:other:manual",
        )
    )
    await session.commit()

    await client.post(f"/api/v1/tasks/{today_task_id(plan)}/checkins", json={"status": "completed"}, headers=headers)
    await client.get("/api/v1/reminders", headers=headers)

    row = await session.scalar(select(Notification).where(Notification.dedup_key == "task_due:other:manual"))
    assert row.read_at is None


async def test_parallel_reminder_requests_stay_clean(client) -> None:
    headers, _ = await fresh_user(client, "par")
    plan = await activate_plan(client, headers)
    today = business_today().isoformat()
    today_tasks = [item for item in plan["tasks"] if item["scheduled_date"] == today]

    first, second = await asyncio.gather(
        client.get("/api/v1/reminders", headers=headers),
        client.get("/api/v1/reminders", headers=headers),
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    task_due = [item for item in first.json()["data"] if item["notification_type"] == "task_due"]
    assert len(task_due) == len(today_tasks)
