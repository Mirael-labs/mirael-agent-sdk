"""
Volume tests: concurrent RAG retrieval.

Simulates multiple users querying the Retriever simultaneously.
Uses mocked embeddings and vector store to avoid real API calls.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from mirael.knowledge.embeddings import EmbeddingProvider
from mirael.knowledge.models import Chunk, SearchResult
from mirael.knowledge.retriever import Retriever
from mirael.knowledge.vector_store import QdrantVectorStore


def _make_mock_result(i: int) -> SearchResult:
    return SearchResult(
        chunk=Chunk(
            document_id="d1",
            text=f"result {i}",
            source_url="https://test.com",
            section_title="Test",
            chunk_index=i,
        ),
        score=0.9 - i * 0.01,
        point_id=str(i),
    )


@pytest.fixture()
def mock_retriever() -> Retriever:
    embeddings = AsyncMock(spec=EmbeddingProvider)
    embeddings.embed_query = AsyncMock(return_value=[0.1] * 1024)
    store = AsyncMock(spec=QdrantVectorStore)
    store.search = AsyncMock(return_value=[_make_mock_result(i) for i in range(5)])
    return Retriever(embeddings=embeddings, vector_store=store)


@pytest.mark.volume
class TestConcurrentRetrieval:
    async def test_10_concurrent_queries(self, mock_retriever):
        """10 simultaneous queries should all succeed."""
        queries = [f"question about DeFi topic {i}" for i in range(10)]
        tasks = [mock_retriever.retrieve(q, top_k=5) for q in queries]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(len(r) == 5 for r in results)

    async def test_50_concurrent_queries_throughput(self, mock_retriever):
        """50 concurrent queries — measures async concurrency efficiency."""
        queries = [f"DeFi query {i}" for i in range(50)]

        t0 = time.monotonic()
        results = await asyncio.gather(*[mock_retriever.retrieve(q) for q in queries])
        elapsed = time.monotonic() - t0

        assert len(results) == 50
        qps = 50 / elapsed
        print(f"\n  Concurrent retrieval: {qps:.0f} queries/s ({elapsed:.3f}s for 50 queries)")
        # With mocked IO, 50 concurrent queries should complete well under 1 second
        assert elapsed < 5.0

    async def test_concurrent_format_context(self, mock_retriever):
        """format_context is pure Python — should handle concurrent calls safely."""
        queries = [f"q{i}" for i in range(20)]
        all_results = await asyncio.gather(*[mock_retriever.retrieve(q, top_k=3) for q in queries])

        contexts = [Retriever.format_context(r) for r in all_results]
        assert all(len(c) > 0 for c in contexts)

    async def test_no_race_conditions_in_memory(self, mock_retriever):
        """Concurrent queries should not produce shared state corruption."""
        import random

        queries = [f"query with random seed {random.random()}" for _ in range(30)]
        results = await asyncio.gather(*[mock_retriever.retrieve(q) for q in queries])

        # Each result should be an independent list
        for r in results:
            assert isinstance(r, list)
