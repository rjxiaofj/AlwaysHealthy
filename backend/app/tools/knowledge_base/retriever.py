import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings

CJK = re.compile(r"[\u4e00-\u9fa5]")
ASCII_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Evidence:
    source_id: str
    chunk_id: str
    title: str
    version: str
    page: int | None
    dimension: str
    chapter: str
    content: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "chunk_id": self.chunk_id,
            "title": self.title,
            "version": self.version,
            "page": self.page,
            "dimension": self.dimension,
            "chapter": self.chapter,
            "content": self.content,
        }


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = ASCII_WORD.findall(lowered)
    chars = CJK.findall(lowered)
    for i in range(len(chars) - 1):
        tokens.append(chars[i] + chars[i + 1])
    tokens.extend(chars)
    return tokens


def load_document(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"{path.name} 缺少元数据头")
    _, meta_block, body = raw.split("---", 2)
    meta = yaml.safe_load(meta_block) or {}
    if not meta.get("source_id"):
        raise ValueError(f"{path.name} 缺少 source_id")
    return meta, body


def read_metadata(path: Path) -> dict[str, Any]:
    return load_document(path)[0]


def _parse_document(path: Path) -> list[Evidence]:
    meta, body = load_document(path)

    chunks: list[Evidence] = []
    sections = re.split(r"\n##\s+", "\n" + body.strip())
    for index, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        lines = section.splitlines()
        chapter = lines[0].strip() if len(lines) > 1 else "概述"
        content = "\n".join(lines[1:]).strip() if len(lines) > 1 else section
        if len(content) < 20:
            continue
        chunks.append(
            Evidence(
                source_id=meta["source_id"],
                chunk_id=f"{meta['source_id']}#{index}",
                title=meta.get("title", path.stem),
                version=str(meta.get("version", "")),
                page=meta.get("page"),
                dimension=(meta.get("dimensions") or ["common"])[0],
                chapter=chapter,
                content=content,
            )
        )
    return chunks


class KeywordRetriever:
    """BGE-M3 未就绪时的检索通道。与向量通道分开建索引，避免混用不同向量化方式。"""

    def __init__(self, directory: Path | None = None):
        settings = get_settings()
        self.directory = directory or Path(settings.knowledge_dir)
        self._chunks: list[Evidence] = []
        self._df: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if not self.directory.exists():
            return
        for path in sorted(self.directory.glob("*.md")):
            self._chunks.extend(_parse_document(path))
        for chunk in self._chunks:
            for token in set(tokenize(chunk.content + chunk.chapter)):
                self._df[token] = self._df.get(token, 0) + 1

    @property
    def size(self) -> int:
        return len(self._chunks)

    def _idf(self, token: str) -> float:
        total = max(len(self._chunks), 1)
        return math.log((total + 1) / (self._df.get(token, 0) + 1)) + 1.0

    async def search(self, query: str, dimension: str | None = None, top_k: int = 5) -> list[Evidence]:
        tokens = [t for t in set(tokenize(query)) if len(t) > 1]
        if not tokens or not self._chunks:
            return []

        scored: list[Evidence] = []
        for chunk in self._chunks:
            if dimension and chunk.dimension not in (dimension, "common"):
                continue
            haystack = set(tokenize(chunk.chapter + chunk.content))
            hit = [t for t in tokens if t in haystack]
            if not hit:
                continue
            raw_score = sum(self._idf(t) for t in hit) / math.sqrt(len(haystack) + 1)
            if dimension and chunk.dimension == dimension:
                raw_score *= 1.15
            scored.append(
                Evidence(
                    source_id=chunk.source_id,
                    chunk_id=chunk.chunk_id,
                    title=chunk.title,
                    version=chunk.version,
                    page=chunk.page,
                    dimension=chunk.dimension,
                    chapter=chunk.chapter,
                    content=chunk.content,
                    score=round(raw_score, 4),
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]


_retriever: KeywordRetriever | None = None


def get_retriever() -> KeywordRetriever:
    global _retriever
    if _retriever is None:
        settings = get_settings()
        if settings.embedding_backend == "bge":
            from app.integrations.chroma_client import VectorRetriever

            _retriever = VectorRetriever()
        else:
            _retriever = KeywordRetriever()
    return _retriever
