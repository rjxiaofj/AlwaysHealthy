from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import EmergencyEvent, User


async def test_emergency_events_are_listed_newest_first(client, auth, session) -> None:
    user_id = await session.scalar(select(User.id).where(User.username == auth["username"]))
    session.add(
        EmergencyEvent(
            user_id=user_id,
            trigger_reason="胸痛",
            matched_rules=[{"rule_id": "emergency_chest_pain", "label": "胸痛或胸部压榨感"}],
            urgency="紧急",
            triggered_at=datetime.now() - timedelta(days=1),
        )
    )
    session.add(
        EmergencyEvent(
            user_id=user_id,
            trigger_reason="严重呼吸困难",
            matched_rules=[{"rule_id": "emergency_dyspnea", "label": "严重呼吸困难"}],
            urgency="紧急",
        )
    )
    await session.commit()

    response = await client.get("/api/v1/profiles/me/emergency-events", headers=auth)
    assert response.status_code == 200, response.text

    rows = response.json()["data"]
    assert len(rows) == 2
    assert rows[0]["trigger_reason"] == "严重呼吸困难"
    assert rows[1]["trigger_reason"] == "胸痛"
    assert rows[1]["matched_rules"][0]["rule_id"] == "emergency_chest_pain"


async def test_emergency_events_isolated_between_users(client, auth, session) -> None:
    user_id = await session.scalar(select(User.id).where(User.username == auth["username"]))
    session.add(EmergencyEvent(user_id=user_id, trigger_reason="胸痛", matched_rules=[], urgency="紧急"))
    await session.commit()

    other = await client.post("/api/v1/auth/register", json={"username": "emergother", "password": "demo12345"})
    other_headers = {"Authorization": f"Bearer {other.json()['data']['access_token']}"}

    response = await client.get("/api/v1/profiles/me/emergency-events", headers=other_headers)
    assert response.status_code == 200
    assert response.json()["data"] == []
