from sqlalchemy import select

from app.db.models import SecurityAuditLog
from tests.helpers import activate_plan


async def request_reassessment(client, headers, reason: str):
    return await client.post("/api/v1/tracking/reassessment", json={"reason": reason}, headers=headers)


async def test_reassessment_requires_reason(client, auth) -> None:
    plan = await activate_plan(client, auth)
    assert plan["id"]

    response = await request_reassessment(client, auth, "x")
    assert response.status_code == 422


async def test_reassessment_writes_audit_row(client, auth, session) -> None:
    await activate_plan(client, auth)

    response = await request_reassessment(client, auth, "一个周期做完了，想看看指标有没有变化")
    assert response.status_code == 200, response.text

    row = await session.scalar(
        select(SecurityAuditLog).where(SecurityAuditLog.action == "reassessment_request")
    )
    assert row is not None
    assert row.resource_type == "health_profile"
    # result 列是 varchar(16)，写长文本在 Postgres 上会直接报 value too long
    assert row.result == "requested"
    assert len(row.result) <= 16


async def test_reassessment_requires_login(client) -> None:
    response = await client.post("/api/v1/tracking/reassessment", json={"reason": "周期结束重新评估"})
    assert response.status_code == 401
