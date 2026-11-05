from uuid import UUID, uuid4

from sqlalchemy import select

from app.db.models import PlanAdjustmentRecord
from tests.helpers import activate_plan, reach_plan_review, register_another


async def adjust_plan(client, headers, plan_id, reason="任务太多，想减到每天两项"):
    response = await client.post(f"/api/v1/plans/{plan_id}/adjust", json={"reason": reason}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]["version_id"]


async def approve_version(client, headers, plan_id, version_id):
    response = await client.post(
        f"/api/v1/plans/{plan_id}/approve", json={"version_id": version_id}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def reject_version(client, headers, plan_id, version_id):
    return await client.post(f"/api/v1/plans/{plan_id}/versions/{version_id}/reject", headers=headers, json={})


async def feedback(client, headers, plan_id, version_id, text):
    return await client.post(
        f"/api/v1/plans/{plan_id}/adjustment-feedback",
        json={"version_id": version_id, "feedback": text},
        headers=headers,
    )


async def test_feedback_after_approved_adjustment(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])
    await approve_version(client, auth, plan["id"], version_id)

    detail = (await client.get(f"/api/v1/plans/{plan['id']}", headers=auth)).json()["data"]
    assert detail["adjustment"]["version_id"] == version_id
    assert detail["adjustment"]["reason"] == "任务太多，想减到每天两项"
    assert detail["adjustment"]["feedback"] is None

    response = await feedback(client, auth, plan["id"], version_id, "更合适了：每天两项能做到")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["feedback"] == "更合适了：每天两项能做到"

    detail = (await client.get(f"/api/v1/plans/{plan['id']}", headers=auth)).json()["data"]
    assert detail["adjustment"]["feedback"] == "更合适了：每天两项能做到"


async def test_feedback_overwrites_same_record(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])
    await approve_version(client, auth, plan["id"], version_id)

    await feedback(client, auth, plan["id"], version_id, "差别不大")
    await feedback(client, auth, plan["id"], version_id, "还是不合适：任务时间太早")

    detail = (await client.get(f"/api/v1/plans/{plan['id']}", headers=auth)).json()["data"]
    assert detail["adjustment"]["feedback"] == "还是不合适：任务时间太早"


async def test_feedback_rejects_unapproved_version(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])

    response = await feedback(client, auth, plan["id"], version_id, "差别不大")
    assert response.status_code == 409
    assert response.json()["code"] == "RESOURCE_CONFLICT"


async def test_feedback_rejects_plain_version(client, auth) -> None:
    plan = await activate_plan(client, auth)
    response = await feedback(client, auth, plan["id"], plan["current_version_id"], "差别不大")
    assert response.status_code == 409


async def test_feedback_rejects_other_users_plan(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])
    await approve_version(client, auth, plan["id"], version_id)

    other = await register_another(client)
    response = await feedback(client, other, plan["id"], version_id, "差别不大")
    assert response.status_code == 404


async def test_feedback_rejects_blank_text(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])
    await approve_version(client, auth, plan["id"], version_id)

    response = await feedback(client, auth, plan["id"], version_id, " ")
    assert response.status_code == 422


async def test_reject_adjustment_keeps_plan_running(client, auth, session) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])

    response = await reject_version(client, auth, plan["id"], version_id)
    assert response.status_code == 200, response.text

    data = response.json()["data"]
    assert data["status"] == "active"
    assert data["current_version_id"] == plan["current_version_id"]
    assert data["adjustment"] is None
    status_by_id = {item["id"]: item["status"] for item in data["versions"]}
    assert status_by_id[version_id] == "cancelled"

    row = await session.scalar(
        select(PlanAdjustmentRecord).where(PlanAdjustmentRecord.new_version_id == UUID(version_id))
    )
    assert row is not None
    assert row.approval_status == "rejected"
    assert row.confirmed_at is not None


async def test_reject_initial_draft_cancels_plan(client, auth) -> None:
    confirm = await reach_plan_review(client, auth)
    response = await reject_version(client, auth, confirm["plan_id"], confirm["plan_version_id"])
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "cancelled"


async def test_reject_twice_returns_conflict(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])
    await reject_version(client, auth, plan["id"], version_id)

    response = await reject_version(client, auth, plan["id"], version_id)
    assert response.status_code == 409


async def test_unknown_plan_returns_404(client, auth) -> None:
    response = await feedback(client, auth, str(uuid4()), str(uuid4()), "差别不大")
    assert response.status_code == 404
