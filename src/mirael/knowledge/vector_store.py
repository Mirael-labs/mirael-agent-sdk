"""
Qdrant async vector store client.

Wraps ``qdrant_client.AsyncQdrantClient`` with typed interfaces,
collection lifecycle management, and Mirael exception mapping.
"""

from __future__ import annotations

import uuid
from typing import Any

from mirael.exceptions import VectorStoreError
from mirael.knowledge.models import Chunk, SearchResult
from mirael.logging import get_logger

_log = get_logger(__name__)


class QdrantVectorStore:
    """
    Async Qdrant vector store with automatic collection setup.

    Args:
        url: Qdrant server URL (e.g. ``http://localhost:6333``).
        api_key: Qdrant Cloud API key (``None`` for local).
        collection: Collection name to use for upsert/search.
        vector_dim: Embedding dimension (must match your embedding model).
    """

    def __init__(
        self,
        url: str,
        api_key: str | None,
        collection: str,
        vector_dim: int = 3072,
    ) -> None:
        try:
            from qdrant_client import AsyncQdrantClient

            self._client: Any = AsyncQdrantClient(url=url, api_key=api_key)
        except ImportError as exc:
            raise VectorStoreError(
                "qdrant-client not installed. Run: uv add qdrant-client",
                code="KB_VECTOR_STORE_IMPORT",
            ) from exc
        self._collection = collection
        self._dim = vector_dim

    async def ensure_collection(self) -> None:
        """
        Create the Qdrant collection if it does not already exist.

        Safe to call multiple times (idempotent).

        Raises:
            VectorStoreError: On connection or creation failure.
        """
        try:
            from qdrant_client.models import Distance, VectorParams

            existing = [
                c.name
                for c in (await self._client.get_collections()).collections
            ]
            if self._collection not in existing:
                await self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=self._dim, distance=Distance.COSINE
                    ),
                )
                _log.info(
                    "qdrant_collection_created",
                    collection=self._collection,
                    dim=self._dim,
                )
            else:
                _log.debug(
                    "qdrant_collection_exists", collection=self._collection
                )
        except Exception as exc:
            raise VectorStoreError(
                f"Failed to ensure collection '{self._collection}': {exc}"
            ) from exc

    async def upsert(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:
        """
        Upsert chunks and their vectors into Qdrant.

        Args:
            chunks: List of ``Chunk`` objects (provides payload).
            vectors: Parallel list of float vectors; must match len(chunks).

        Raises:
            ValueError: If ``len(chunks) != len(vectors)``.
            VectorStoreError: On Qdrant write failure.
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) and vectors ({len(vectors)}) must have equal length"
            )
        if not chunks:
            return

        try:
            from qdrant_client.models import PointStruct

            points = [
                PointStruct(
                    id=abs(hash(chunk.id)) % (2**63),
                    vector=vec,
                    payload={
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "text": chunk.text,
                        "source_url": chunk.source_url,
                        "section_title": chunk.section_title,
                        "chunk_index": chunk.chunk_index,
                    },
                )
                for chunk, vec in zip(chunks, vectors, strict=True)
            ]
            await self._client.upsert(
                collection_name=self._collection, points=points
            )
            _log.info(
                "qdrant_upserted", collection=self._collection, count=len(chunks)
            )
        except Exception as exc:
            raise VectorStoreError(f"Upsert failed: {exc}") from exc

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        """
        Search for the top-k most similar chunks.

        Args:
            query_vector: Embedded query vector.
            top_k: Number of results to return.
            filter_metadata: Optional exact-match payload filters
                             (e.g. ``{"source_url": "https://..."}``)

        Returns:
            List of ``SearchResult`` ordered by descending similarity score.

        Raises:
            VectorStoreError: On Qdrant query failure.
        """
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            qdrant_filter: Any = None
            if filter_metadata:
                qdrant_filter = Filter(
                    must=[
                        FieldCondition(key=k, match=MatchValue(value=v))
                        for k, v in filter_metadata.items()
                    ]
                )

            hits = await self._client.search(
                collection_name=self._collection,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreError(f"Search failed: {exc}") from exc

        results: list[SearchResult] = []
        for hit in hits:
            payload = hit.payload or {}
            chunk = Chunk(
                id=payload.get("chunk_id", str(uuid.uuid4())),
                document_id=payload.get("document_id", ""),
                text=payload.get("text", ""),
                source_url=payload.get("source_url", ""),
                section_title=payload.get("section_title", ""),
                chunk_index=int(payload.get("chunk_index", 0)),
            )
            results.append(
                SearchResult(
                    chunk=chunk,
                    score=float(hit.score),
                    point_id=str(hit.id),
                )
            )
        return results

    async def delete_collection(self) -> None:
        """
        Delete the collection entirely.

        Primarily used in tests to clean up after integration runs.
        """
        try:
            await self._client.delete_collection(self._collection)
            _log.info("qdrant_collection_deleted", collection=self._collection)
        except Exception as exc:
            raise VectorStoreError(f"Delete collection failed: {exc}") from exc


def create_from_settings(settings: Any) -> QdrantVectorStore:  # noqa: ANN401
    """Factory: build ``QdrantVectorStore`` from a ``MiraelSettings`` instance."""
    return QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=(
            settings.qdrant_api_key.get_secret_value()
            if settings.qdrant_api_key
            else None
        ),
        collection=settings.qdrant_collection,
        vector_dim=settings.embedding_dimensions,
    )
