import os
from pathlib import Path

from sqlalchemy import select

from app.db.models import KnowledgeSource
from app.services import knowledge_service


async def test_sources_are_listed_after_startup(client, auth) -> None:
    response = await client.get("/api/v1/knowledge/sources", headers=auth)
    assert response.status_code == 200, response.text

    rows = response.json()["data"]
    expected = len(list(Path(os.environ["KNOWLEDGE_DIR"]).glob("*.md")))
    assert len(rows) == expected

    hypertension = next(item for item in rows if item["source_id"] == "KB_CN_HYPERTENSION_2024")
    assert hypertension["issuing_org"] == "中国高血压防治指南修订委员会"
    assert hypertension["publish_date"] == "2024-08-01"
    assert hypertension["dimensions"] == ["cardiovascular"]
    assert hypertension["effective_status"] == "active"


async def test_sync_does_not_duplicate_rows(session) -> None:
    first = await knowledge_service.sync_sources(session)
    assert first == 0

    await knowledge_service.sync_sources(session)
    rows = await session.scalars(select(KnowledgeSource))
    expected = len(list(Path(os.environ["KNOWLEDGE_DIR"]).glob("*.md")))
    assert len(list(rows)) == expected


async def test_sources_require_login(client) -> None:
    response = await client.get("/api/v1/knowledge/sources")
    assert response.status_code == 401
