"""Unit tests for QdrantVectorStore."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mirael.knowledge.models import Chunk
from mirael.knowledge.vector_store import QdrantVectorStore


def _make_chunk(idx: int = 0) -> Chunk:
    return Chunk(
        document_id="doc-1",
        text=f"chunk text {idx}",
        source_url="https://test.com",
        section_title="Test Section",
        chunk_index=idx,
    )


@pytest.fixture()
def mock_qdrant_client() -> MagicMock:
    with patch("qdrant_client.AsyncQdrantClient") as mock_cls:
        instance = AsyncMock()
        mock_cls.return_value = instance
        # Default: collection does not exist
        instance.get_collections.return_value = MagicMock(collections=[])
        instance.create_collection = AsyncMock()
        instance.upsert = AsyncMock()
        instance.search.return_value = []
        instance.delete_collection = AsyncMock()
        yield instance


class TestEnsureCollection:
    async def test_creates_when_missing(self, mock_qdrant_client: MagicMock) -> None:
        store = QdrantVectorStore("http://localhost:6333", None, "test", 4)
        await store.ensure_collection()
        mock_qdrant_client.create_collection.assert_called_once()

    async def test_skips_when_exists(self, mock_qdrant_client: MagicMock) -> None:
        existing = MagicMock()
        existing.name = "my_col"
        mock_qdrant_client.get_collections.return_value = MagicMock(
            collections=[existing]
        )
        store = QdrantVectorStore("http://localhost:6333", None, "my_col", 4)
        await store.ensure_collection()
        mock_qdrant_client.create_collection.assert_not_called()


class TestUpsert:
    async def test_upserts_points(self, mock_qdrant_client: MagicMock) -> None:
        store = QdrantVectorStore("http://localhost:6333", None, "test", 4)
        chunks = [_make_chunk(0), _make_chunk(1)]
        vectors = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]
        await store.upsert(chunks, vectors)
        mock_qdrant_client.upsert.assert_called_once()

    async def test_empty_upsert_is_noop(self, mock_qdrant_client: MagicMock) -> None:
        store = QdrantVectorStore("http://localhost:6333", None, "test", 4)
        await store.upsert([], [])
        mock_qdrant_client.upsert.assert_not_called()

    async def test_mismatched_lengths_raise(self, mock_qdrant_client: MagicMock) -> None:
        store = QdrantVectorStore("http://localhost:6333", None, "test", 4)
        with pytest.raises(ValueError, match="equal length"):
            await store.upsert([_make_chunk()], [[0.1], [0.2]])


class TestSearch:
    async def test_returns_empty_on_no_hits(self, mock_qdrant_client: MagicMock) -> None:
        store = QdrantVectorStore("http://localhost:6333", None, "test", 4)
        results = await store.search([0.1, 0.2, 0.3, 0.4])
        assert results == []

    async def test_maps_hits_to_search_result(self, mock_qdrant_client: MagicMock) -> None:
        hit = MagicMock()
        hit.score = 0.95
        hit.id = 12345
        hit.payload = {
            "chunk_id": "c-1",
            "document_id": "d-1",
            "text": "some text",
            "source_url": "https://test.com",
            "section_title": "Intro",
            "chunk_index": 0,
        }
        mock_qdrant_client.search.return_value = [hit]
        store = QdrantVectorStore("http://localhost:6333", None, "test", 4)
        results = await store.search([0.1, 0.2, 0.3, 0.4])
        assert len(results) == 1
        assert results[0].score == pytest.approx(0.95)
        assert results[0].chunk.text == "some text"
