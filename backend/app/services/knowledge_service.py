import hashlib
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories import knowledge as knowledge_repo
from app.tools.knowledge_base.retriever import read_metadata

log = get_logger(__name__)


def _as_date(value: Any) -> date | None:
    return value if isinstance(value, date) else None


async def sync_sources(session: AsyncSession) -> int:
    """把 knowledge 目录的元数据头同步成台账。启动时调用，按 source_id 幂等。

    台账只描述资料的出处与适用人群，正文仍从文件读。文件改了 checksum 才更新，
    这样 import_date 能反映最后一次实际改动的时间，而不是每次启动都刷新。
    """
    directory = Path(get_settings().knowledge_dir)
    if not directory.exists():
        return 0

    changed = 0
    for path in sorted(directory.glob("*.md")):
        meta = read_metadata(path)
        payload = {
            "title": meta.get("title") or path.stem,
            "issuing_org": meta.get("issuing_org") or "未标注",
            "document_type": meta.get("document_type") or "guideline",
            "version": str(meta.get("version", "")),
            "publish_date": _as_date(meta.get("publish_date")),
            "effective_status": meta.get("effective_status") or "active",
            "applicable_population": meta.get("applicable_population") or "adult",
            "dimensions": meta.get("dimensions") or [],
            "original_url": meta.get("original_url"),
            "checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        if await knowledge_repo.upsert(session, meta["source_id"], payload):
            changed += 1

    await session.commit()
    if changed:
        log.info("knowledge sources synced changed=%s", changed)
    return changed


async def list_sources(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await knowledge_repo.all_sources(session)
    return [knowledge_repo.as_dict(row) for row in rows]
