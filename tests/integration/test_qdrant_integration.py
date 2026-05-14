"""
Integration tests against a real Qdrant instance.

Requires Qdrant running on localhost:6333.
Run with: pytest tests/integration/ -m integration

These tests are excluded from the default test run and only execute
when the `integration` marker is explicitly requested or in CI
(which spins up a Qdrant service container).
"""

from __future__ import annotations

import contextlib
import uuid

import pytest

from mirael.knowledge.models import Chunk
from mirael.knowledge.vector_store import QdrantVectorStore


@pytest.fixture()
def collection_name() -> str:
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
async def store(collection_name: str) -> QdrantVectorStore:  # type: ignore[misc]
    s = QdrantVectorStore(
        url="http://localhost:6333",
        api_key=None,
        collection=collection_name,
        vector_dim=4,
    )
    yield s  # type: ignore[misc]
    with contextlib.suppress(Exception):
        await s.delete_collection()


@pytest.mark.integration
class TestQdrantIntegration:
    async def test_ensure_collection_creates_and_is_idempotent(
        self, store: QdrantVectorStore
    ) -> None:
        await store.ensure_collection()
        # Second call should not raise
        await store.ensure_collection()

    async def test_upsert_and_search_round_trip(self, store: QdrantVectorStore) -> None:
        await store.ensure_collection()

        chunk = Chunk(
            document_id="doc-1",
            text="Hyperliquid uses a proof-of-stake consensus mechanism.",
            source_url="https://hyperliquid.xyz/docs",
            section_title="Architecture",
            chunk_index=0,
        )
        vector = [0.1, 0.9, 0.2, 0.8]  # arbitrary 4-dim vector

        await store.upsert([chunk], [vector])
        results = await store.search(vector, top_k=1)

        assert len(results) == 1
        assert results[0].chunk.text == chunk.text
        assert results[0].score > 0.99  # same vector → near-perfect cosine similarity

    async def test_search_returns_empty_on_empty_collection(self, store: QdrantVectorStore) -> None:
        await store.ensure_collection()
        results = await store.search([0.1, 0.2, 0.3, 0.4], top_k=5)
        assert results == []

    async def test_upsert_multiple_chunks_and_top_k(self, store: QdrantVectorStore) -> None:
        await store.ensure_collection()

        chunks = [
            Chunk(
                document_id="d",
                text=f"document chunk {i}",
                source_url="https://test.com",
                section_title="Test",
                chunk_index=i,
            )
            for i in range(5)
        ]
        vectors = [[float(i), float(i + 1), float(i + 2), float(i + 3)] for i in range(5)]
        await store.upsert(chunks, vectors)
        results = await store.search([0.0, 1.0, 2.0, 3.0], top_k=3)
        assert len(results) == 3
