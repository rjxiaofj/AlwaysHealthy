"""知情同意记录。

授权与撤回都留痕，不覆盖旧记录：历史授权状态是后续争议时唯一的凭据。
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConsentRecord
from app.schemas.chat import ConsentIn

CONSENT_LABELS = {
    "health_data": "健康数据处理",
    "ai_analysis": "AI 辅助分析",
}


async def record(session: AsyncSession, user_id: UUID, payload: ConsentIn) -> ConsentRecord:
    now = datetime.now(UTC)
    row = ConsentRecord(
        user_id=user_id,
        consent_type=payload.consent_type,
        policy_version=payload.policy_version,
        consent_status="granted" if payload.granted else "revoked",
        consented_at=now,
        revoked_at=None if payload.granted else now,
    )
    session.add(row)
    await session.commit()
    return row


async def list_records(session: AsyncSession, user_id: UUID) -> list[dict[str, Any]]:
    rows = await session.scalars(
        select(ConsentRecord).where(ConsentRecord.user_id == user_id).order_by(ConsentRecord.consented_at.desc())
    )
    return [
        {
            "id": row.id,
            "consent_type": row.consent_type,
            "label": CONSENT_LABELS.get(row.consent_type, row.consent_type),
            "policy_version": row.policy_version,
            "consent_status": row.consent_status,
            "consented_at": row.consented_at,
            "revoked_at": row.revoked_at,
        }
        for row in rows
    ]
