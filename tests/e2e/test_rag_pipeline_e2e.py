"""
E2E tests: full RAG pipeline against real services.

Tests: local embedding model → Qdrant Cloud upsert → semantic retrieval.
No LLM API calls — only embeddings + vector store.
"""

from __future__ import annotations

import contextlib
import time

import pytest

from mirael.knowledge.embeddings import create_from_settings
from mirael.knowledge.ingest import IngestPipeline, SemanticChunker
from mirael.knowledge.models import Document
from mirael.knowledge.retriever import Retriever
from mirael.knowledge.vector_store import QdrantVectorStore

_E2E_COLLECTION = "mirael_rag_e2e"


@pytest.fixture()
async def rag_setup(settings):
    """Set up a real ingest pipeline and retriever for E2E tests."""
    embeddings = create_from_settings(settings)
    store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        collection=_E2E_COLLECTION,
        vector_dim=settings.embedding_dimensions,
    )
    chunker = SemanticChunker(chunk_size=100, overlap=15)
    pipeline = IngestPipeline(
        chunker=chunker, embeddings=embeddings, vector_store=store, batch_size=20
    )
    retriever = Retriever(embeddings=embeddings, vector_store=store)

    # Ingest 2 test documents
    docs = [
        Document(
            url="https://test.mirael.xyz/funding",
            title="Funding Rates",
            content=(
                "Funding rates on Hyperliquid are periodic payments between long and short positions. "
                "When the perpetual price is above oracle, longs pay shorts. "
                "The funding rate is settled every hour. "
                "High positive funding means the market is bullish and longs are paying a premium. "
                "Traders should monitor funding costs as they can significantly erode profits over time. "
                "A 0.01% hourly rate annualises to approximately 87.6% per year."
            ),
        ),
        Document(
            url="https://test.mirael.xyz/liquidation",
            title="Liquidation",
            content=(
                "Liquidation occurs when account equity falls below maintenance margin. "
                "The health factor measures distance from liquidation — keep it above 1.5. "
                "Hyperliquid uses partial liquidation to preserve as much user equity as possible. "
                "Adding margin or reducing position size can prevent liquidation. "
                "The liquidation price depends on entry price, leverage, and current margin."
            ),
        ),
    ]

    await pipeline.ingest(docs)
    yield retriever, store

    with contextlib.suppress(Exception):
        await store.delete_collection()


@pytest.mark.e2e
class TestRAGPipelineE2E:
    async def test_semantic_retrieval_funding(self, rag_setup):
        """Query about funding should return the funding rate document."""
        retriever, _ = rag_setup
        results = await retriever.retrieve("what are funding rates and how do they work?", top_k=3)

        assert len(results) > 0
        # The most relevant result should mention funding
        top_text = results[0].chunk.text.lower()
        assert any(word in top_text for word in ["funding", "payment", "longs", "shorts"])

    async def test_semantic_retrieval_liquidation(self, rag_setup):
        """Query about liquidation should return liquidation document."""
        retriever, _ = rag_setup
        results = await retriever.retrieve("how does liquidation work?", top_k=3)

        assert len(results) > 0
        top_text = results[0].chunk.text.lower()
        assert any(word in top_text for word in ["liquidat", "margin", "health"])

    async def test_retrieval_scores_are_positive(self, rag_setup):
        """All retrieval scores should be positive (cosine similarity)."""
        retriever, _ = rag_setup
        results = await retriever.retrieve("DeFi trading", top_k=5)

        for r in results:
            assert r.score > 0.0

    async def test_format_context_produces_markdown(self, rag_setup):
        """format_context should produce valid markdown with source URLs."""
        retriever, _ = rag_setup
        results = await retriever.retrieve("funding rates", top_k=2)
        context = Retriever.format_context(results)

        assert "## Relevant documentation" in context
        assert "test.mirael.xyz" in context

    async def test_retrieval_latency(self, rag_setup):
        """Semantic retrieval should complete under 5 seconds."""
        retriever, _ = rag_setup
        t0 = time.monotonic()
        await retriever.retrieve("what is funding rate?", top_k=3)
        elapsed = time.monotonic() - t0

        assert elapsed < 5.0, f"Retrieval took {elapsed:.2f}s"

    async def test_empty_query_does_not_crash(self, rag_setup):
        """Empty query should return results without crashing."""
        retriever, _ = rag_setup
        results = await retriever.retrieve("", top_k=3)
        # May return results or empty — just shouldn't crash
        assert isinstance(results, list)
