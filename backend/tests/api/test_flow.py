import json
import uuid
from datetime import date

ASSESS_TEXT = (
    "我今年39岁，男，身高175，体重88公斤，血压150/95，"
    "每周运动1天，久坐9小时，睡眠6小时，口味重，吸烟"
)


async def collect_events(client, method, url, headers=None, payload=None):
    events = []
    current = None
    async with client.stream(method, url, headers=headers, json=payload) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                current = line[7:]
            elif line.startswith("data: ") and current:
                events.append((current, json.loads(line[6:])))
                current = None
    return events


async def prepare_profile(client, headers):
    response = await client.patch(
        "/api/v1/profiles/me",
        headers=headers,
        json={"birth_date": "1986-05-01", "sex": "male", "height_cm": 175, "weight_kg": 88},
    )
    assert response.status_code == 200


async def new_conversation(client, headers):
    response = await client.post("/api/v1/conversations", headers=headers, json={})
    return response.json()["data"]["id"]


async def test_assessment_flow_reaches_report(client, auth):
    await prepare_profile(client, auth)
    conversation_id = await new_conversation(client, auth)

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        auth,
        {"content": ASSESS_TEXT},
    )
    names = [name for name, _ in events]
    assert "confirmation_required" in names
    profile_confirm = next(data for name, data in events if name == "confirmation_required")
    assert profile_confirm["approval_type"] == "profile"
    assert profile_confirm["summary"]["systolic_bp"] == 150

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{profile_confirm['run_id']}/resume/stream",
        auth,
        {"approval_type": "profile", "decision": "approve"},
    )
    plan_confirm = next(data for name, data in events if name == "confirmation_required")
    assert plan_confirm["approval_type"] == "plan"
    assert plan_confirm["plan_id"]

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{plan_confirm['run_id']}/resume/stream",
        auth,
        {
            "approval_type": "plan",
            "decision": "approve",
            "business_id": plan_confirm["plan_id"],
            "version_id": plan_confirm["plan_version_id"],
        },
    )
    assert "run_completed" in [name for name, _ in events]

    assessment = await client.get("/api/v1/assessments/latest", headers=auth)
    data = assessment.json()["data"]
    assert data["overall_level"] in ("中", "高")
    assert len(data["dimensions"]) == 5
    assert data["dimensions"][0]["evidence_sources"]

    plans = await client.get("/api/v1/plans", headers=auth)
    assert plans.json()["data"][0]["status"] == "active"

    reports = await client.get("/api/v1/reports", headers=auth)
    assert reports.json()["data"][0]["report_type"] == "assessment"


async def test_emergency_message_skips_normal_flow(client, auth):
    conversation_id = await new_conversation(client, auth)
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        auth,
        {"content": "现在突然胸痛，喘不上气"},
    )
    names = [name for name, _ in events]
    assert "confirmation_required" not in names
    reply = next(data["content"] for name, data in events if name == "token")
    assert "120" in reply
    assert "急诊" in reply


async def test_plan_isolation_between_users(client, auth):
    await prepare_profile(client, auth)
    conversation_id = await new_conversation(client, auth)
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        auth,
        {"content": ASSESS_TEXT},
    )
    confirm = next(data for name, data in events if name == "confirmation_required")
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{confirm['run_id']}/resume/stream",
        auth,
        {"approval_type": "profile", "decision": "approve"},
    )
    plan_confirm = next(data for name, data in events if name == "confirmation_required")

    other = await client.post(
        "/api/v1/auth/register",
        json={"username": f"u{uuid.uuid4().hex[:10]}", "password": "demo12345"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['data']['access_token']}"}
    response = await client.get(f"/api/v1/plans/{plan_confirm['plan_id']}", headers=other_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"


async def test_checkin_is_idempotent(client, auth):
    await prepare_profile(client, auth)
    conversation_id = await new_conversation(client, auth)
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        auth,
        {"content": ASSESS_TEXT},
    )
    confirm = next(data for name, data in events if name == "confirmation_required")
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{confirm['run_id']}/resume/stream",
        auth,
        {"approval_type": "profile", "decision": "approve"},
    )
    plan_confirm = next(data for name, data in events if name == "confirmation_required")
    await client.post(
        f"/api/v1/plans/{plan_confirm['plan_id']}/approve",
        headers=auth,
        json={"version_id": plan_confirm["plan_version_id"]},
    )

    detail = await client.get(f"/api/v1/plans/{plan_confirm['plan_id']}", headers=auth)
    today_tasks = [item for item in detail.json()["data"]["tasks"] if item["scheduled_date"] == date.today().isoformat()]
    task_id = today_tasks[0]["id"]

    first = await client.post(
        f"/api/v1/tasks/{task_id}/checkins",
        headers=auth,
        json={"status": "completed", "feedback": "已完成"},
    )
    second = await client.post(
        f"/api/v1/tasks/{task_id}/checkins",
        headers=auth,
        json={"status": "partial"},
    )
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert second.json()["data"]["status"] == "partial"


async def test_metric_value_out_of_range_rejected(client, auth):
    response = await client.post(
        "/api/v1/tracking/metrics",
        headers=auth,
        json={"metric_code": "systolic_bp", "value": 400, "measured_at": "2026-01-01T08:00:00Z"},
    )
    assert response.status_code == 422

    ok_response = await client.post(
        "/api/v1/tracking/metrics",
        headers=auth,
        json={"metric_code": "systolic_bp", "value": 126, "measured_at": "2026-01-01T08:00:00Z"},
    )
    assert ok_response.status_code == 200


async def test_reminders_generated_for_today_tasks(client, auth):
    await prepare_profile(client, auth)
    conversation_id = await new_conversation(client, auth)
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        auth,
        {"content": ASSESS_TEXT},
    )
    confirm = next(data for name, data in events if name == "confirmation_required")
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{confirm['run_id']}/resume/stream",
        auth,
        {"approval_type": "profile", "decision": "approve"},
    )
    plan_confirm = next(data for name, data in events if name == "confirmation_required")
    await client.post(
        f"/api/v1/plans/{plan_confirm['plan_id']}/approve",
        headers=auth,
        json={"version_id": plan_confirm["plan_version_id"]},
    )

    response = await client.get("/api/v1/reminders", headers=auth)
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 1
