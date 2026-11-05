from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeSource, utcnow


async def all_sources(session: AsyncSession) -> list[KnowledgeSource]:
    rows = await session.scalars(select(KnowledgeSource).order_by(KnowledgeSource.source_id))
    return list(rows)


async def upsert(session: AsyncSession, source_id: str, payload: dict[str, Any]) -> bool:
    """按 source_id 幂等写入。checksum 没变就不动行，返回值表示这次是否真的改了库。"""
    row = await session.get(KnowledgeSource, source_id)
    if row is None:
        session.add(KnowledgeSource(source_id=source_id, import_date=utcnow(), **payload))
        return True
    if row.checksum == payload["checksum"]:
        return False
    for field, value in payload.items():
        setattr(row, field, value)
    row.import_date = utcnow()
    return True


def as_dict(row: KnowledgeSource) -> dict[str, Any]:
    return {
        "source_id": row.source_id,
        "title": row.title,
        "issuing_org": row.issuing_org,
        "document_type": row.document_type,
        "version": row.version,
        "publish_date": row.publish_date.isoformat() if isinstance(row.publish_date, date) else None,
        "effective_status": row.effective_status,
        "applicable_population": row.applicable_population,
        "dimensions": row.dimensions or [],
        "original_url": row.original_url,
        "import_date": row.import_date,
    }
