from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.llm_client import LLMClient


@dataclass
class GraphDeps:
    session_factory: async_sessionmaker[AsyncSession]
    retriever: Any
    llm: LLMClient
    use_llm: bool = False
