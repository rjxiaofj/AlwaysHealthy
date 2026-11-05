from datetime import datetime, timedelta


async def submit(client, headers, **payload):
    return await client.post("/api/v1/tracking/feedback", json=payload, headers=headers)


async def test_feedback_list_returns_submitted(client, auth) -> None:
    first = await submit(client, auth, mood_status="fair", fatigue_level="medium", physical_feeling="下午有点累")
    assert first.status_code == 200, first.text
    second = await submit(client, auth, mood_status="good", execution_difficulty="时间不够")
    assert second.status_code == 200, second.text

    response = await client.get("/api/v1/tracking/feedback", headers=auth)
    assert response.status_code == 200, response.text

    rows = response.json()["data"]
    assert len(rows) == 2
    # 倒序返回，后提交的在前
    assert rows[0]["id"] == second.json()["data"]["id"]
    assert rows[0]["execution_difficulty"] == "时间不够"
    assert rows[1]["physical_feeling"] == "下午有点累"


async def test_feedback_list_respects_days_window(client, auth, session) -> None:
    from uuid import UUID

    from sqlalchemy import select

    from app.db.models import HealthFeedbackRecord, User

    await submit(client, auth, physical_feeling="今天的感受")
    old = await submit(client, auth, physical_feeling="很久以前")
    assert old.status_code == 200

    user_id = await session.scalar(select(User.id).where(User.username == auth["username"]))
    row = await session.get(HealthFeedbackRecord, UUID(old.json()["data"]["id"]))
    row.recorded_at = datetime.now() - timedelta(days=40)
    await session.commit()

    recent = (await client.get("/api/v1/tracking/feedback?days=7", headers=auth)).json()["data"]
    assert len(recent) == 1
    assert recent[0]["physical_feeling"] == "今天的感受"

    wide = (await client.get("/api/v1/tracking/feedback?days=90", headers=auth)).json()["data"]
    assert len(wide) == 2


async def test_feedback_list_isolated_between_users(client, auth) -> None:
    await submit(client, auth, physical_feeling="只属于我")

    other = await client.post("/api/v1/auth/register", json={"username": "feedother", "password": "demo12345"})
    other_headers = {"Authorization": f"Bearer {other.json()['data']['access_token']}"}

    response = await client.get("/api/v1/tracking/feedback", headers=other_headers)
    assert response.status_code == 200
    assert response.json()["data"] == []
