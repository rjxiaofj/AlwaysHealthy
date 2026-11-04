from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.tools.knowledge_base.retriever import Evidence, _parse_document

log = get_logger(__name__)


class VectorRetriever:
    """BGE-M3 + Chroma 检索通道。建索引与查询必须使用同一模型，模型变更时重建 collection。"""

    collection_name = "medical_knowledge"

    def __init__(self, directory: Path | None = None):
        settings = get_settings()
        import chromadb
        from sentence_transformers import SentenceTransformer

        self.directory = directory or Path(settings.knowledge_dir)
        self.model = SentenceTransformer(settings.bge_model_path)
        self.client = chromadb.PersistentClient(path=settings.chroma_dir)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )
        if self.collection.count() == 0:
            self._index()

    def _encode(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def _index(self) -> None:
        chunks: list[Evidence] = []
        for path in sorted(self.directory.glob("*.md")):
            chunks.extend(_parse_document(path))
        if not chunks:
            return
        self.collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=self._encode([chunk.content for chunk in chunks]),
            documents=[chunk.content for chunk in chunks],
            metadatas=[
                {
                    "source_id": chunk.source_id,
                    "title": chunk.title,
                    "version": chunk.version,
                    "dimension": chunk.dimension,
                    "chapter": chunk.chapter,
                }
                for chunk in chunks
            ],
        )
        log.info("chroma indexed chunks=%s", len(chunks))

    @property
    def size(self) -> int:
        return self.collection.count()

    async def search(self, query: str, dimension: str | None = None, top_k: int = 5) -> list[Evidence]:
        where: dict[str, Any] | None = None
        if dimension:
            where = {"dimension": {"$in": [dimension, "common"]}}
        result = self.collection.query(
            query_embeddings=self._encode([query]),
            n_results=top_k,
            where=where,
        )
        evidences: list[Evidence] = []
        for index, chunk_id in enumerate(result["ids"][0]):
            meta = result["metadatas"][0][index]
            distance = result["distances"][0][index] if result.get("distances") else 0.0
            evidences.append(
                Evidence(
                    source_id=meta["source_id"],
                    chunk_id=chunk_id,
                    title=meta["title"],
                    version=meta.get("version", ""),
                    page=meta.get("page"),
                    dimension=meta["dimension"],
                    chapter=meta.get("chapter", ""),
                    content=result["documents"][0][index],
                    score=round(1 - float(distance), 4),
                )
            )
        return evidences
