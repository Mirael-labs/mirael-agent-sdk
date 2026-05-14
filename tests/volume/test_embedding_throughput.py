"""
Volume tests: local embedding model throughput.

Measures how many texts can be embedded per second using
the local BAAI/bge-large-en-v1.5 model.
"""

from __future__ import annotations

import time

import pytest

from mirael.knowledge.embeddings import LocalEmbeddings

# CPU-realistic thresholds (no GPU, includes cold-start model load on first call)
# Cold start: ~15-20s model load + ~0.5s encode
# Warm: ~0.5-2s per text on CPU
MAX_COLD_START_SECONDS = 30.0
MIN_WARM_TEXTS_PER_SECOND = 1.0  # conservative: 1 text/s on CPU after model loaded


@pytest.fixture(scope="module")
def warm_embeddings():
    """Pre-warm the model once per test module to avoid cold-start in latency tests."""
    import asyncio

    emb = LocalEmbeddings()
    asyncio.get_event_loop().run_until_complete(emb.embed_texts(["warm up"]))
    return emb


@pytest.mark.volume
class TestEmbeddingThroughput:
    async def test_single_text_cold_start(self):
        """Single text including cold model load should complete under 30 seconds on CPU."""
        emb = LocalEmbeddings()  # fresh instance — cold start
        t0 = time.monotonic()
        vectors = await emb.embed_texts(["What is the funding rate on Hyperliquid?"])
        elapsed = time.monotonic() - t0

        assert len(vectors) == 1
        assert len(vectors[0]) == 1024
        print(f"\n  Cold-start embed: {elapsed:.2f}s (model load + encode)")
        assert elapsed < MAX_COLD_START_SECONDS, f"Cold start took {elapsed:.2f}s"

    async def test_batch_10_texts(self, warm_embeddings):
        """Batch of 10 texts (warm model) should meet minimum throughput."""
        texts = [f"What happens when the health factor drops below 1.{i}?" for i in range(10)]
        t0 = time.monotonic()
        vectors = await warm_embeddings.embed_texts(texts)
        elapsed = time.monotonic() - t0

        assert len(vectors) == 10
        throughput = 10 / elapsed
        print(f"\n  Warm batch-10 throughput: {throughput:.2f} texts/s ({elapsed:.2f}s)")
        assert throughput >= MIN_WARM_TEXTS_PER_SECOND, (
            f"Throughput {throughput:.1f} texts/s below minimum {MIN_WARM_TEXTS_PER_SECOND}"
        )

    async def test_batch_50_texts(self, warm_embeddings):
        """Batch of 50 texts — measures sustained throughput on warm model."""
        texts = [
            f"DeFi protocol description number {i} explaining perpetual futures." for i in range(50)
        ]

        t0 = time.monotonic()
        vectors = await warm_embeddings.embed_texts(texts)
        elapsed = time.monotonic() - t0

        assert len(vectors) == 50
        throughput = 50 / elapsed
        print(
            f"\n  Embedding throughput (50 texts): {throughput:.1f} texts/s ({elapsed:.2f}s total)"
        )

    async def test_vector_dimensions_consistent(self, warm_embeddings):
        """All vectors must have exactly 1024 dimensions."""
        emb = warm_embeddings
        texts = ["short", "a medium length sentence about DeFi", "a" * 200]
        vectors = await emb.embed_texts(texts)

        assert all(len(v) == 1024 for v in vectors)

    async def test_vectors_are_normalized(self, warm_embeddings):
        """bge-large-en-v1.5 with normalize_embeddings=True should return unit vectors."""
        import math

        vectors = await warm_embeddings.embed_texts(["test normalization"])
        norm = math.sqrt(sum(x**2 for x in vectors[0]))
        assert abs(norm - 1.0) < 0.01, f"Vector norm {norm:.4f} is not ~1.0"
