"""
E2E tests: Qdrant Cloud connection and vector operations.

Tests the full upsert → search round-trip against the real Qdrant Cloud instance.
Requires MIRAEL_QDRANT_URL and MIRAEL_QDRANT_API_KEY in .env.
"""

from __future__ import annotations

import contextlib
import time

import pytest

from mirael.knowledge.models import Chunk
from mirael.knowledge.vector_store import QdrantVectorStore

_TEST_COLLECTION = "mirael_e2e_test"
_DIM = 1024


@pytest.fixture()
async def e2e_store(settings):
    store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        collection=_TEST_COLLECTION,
        vector_dim=_DIM,
    )
    await store.ensure_collection()
    yield store
    with contextlib.suppress(Exception):
        await store.delete_collection()


@pytest.mark.e2e
class TestQdrantE2E:
    async def test_connection_and_collection_creation(self, settings):
        """Verify Qdrant Cloud is reachable and collections can be created."""
        store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            collection=_TEST_COLLECTION,
            vector_dim=_DIM,
        )
        # Should not raise
        await store.ensure_collection()
        # Idempotent
        await store.ensure_collection()

    async def test_upsert_and_retrieve(self, e2e_store):
        """Upsert a chunk and verify it can be retrieved by semantic search."""
        chunk = Chunk(
            document_id="e2e-doc-1",
            text="Hyperliquid perpetual futures use funding rates to anchor prices.",
            source_url="https://test.hyperliquid.xyz",
            section_title="Funding",
            chunk_index=0,
        )
        # Use a simple random vector (not semantically meaningful, just testing plumbing)
        import random

        vector = [random.uniform(-1, 1) for _ in range(_DIM)]
        # Normalize
        norm = sum(x**2 for x in vector) ** 0.5
        vector = [x / norm for x in vector]

        await e2e_store.upsert([chunk], [vector])
        results = await e2e_store.search(vector, top_k=1)

        assert len(results) == 1
        assert results[0].chunk.text == chunk.text
        assert results[0].score > 0.99

    async def test_upsert_latency(self, e2e_store):
        """Upsert 10 chunks and verify round-trip latency is acceptable."""
        import random

        chunks = [
            Chunk(
                document_id="perf-doc",
                text=f"Test chunk number {i} for performance testing.",
                source_url="https://test.com",
                section_title="Perf",
                chunk_index=i,
            )
            for i in range(10)
        ]
        vectors = []
        for _ in chunks:
            v = [random.uniform(-1, 1) for _ in range(_DIM)]
            norm = sum(x**2 for x in v) ** 0.5
            vectors.append([x / norm for x in v])

        t0 = time.monotonic()
        await e2e_store.upsert(chunks, vectors)
        elapsed = time.monotonic() - t0

        # 10 chunks to Qdrant Cloud should complete in under 10 seconds
        assert elapsed < 10.0, f"Upsert took {elapsed:.2f}s — too slow"

    async def test_search_returns_top_k(self, e2e_store):
        """Verify top_k parameter is respected."""
        import random

        vector = [random.uniform(-1, 1) for _ in range(_DIM)]
        norm = sum(x**2 for x in vector) ** 0.5
        vector = [x / norm for x in vector]

        results = await e2e_store.search(vector, top_k=3)
        assert len(results) <= 3
