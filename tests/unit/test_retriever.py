"""Unit tests for Retriever."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mirael.knowledge.embeddings import OpenAIEmbeddings
from mirael.knowledge.models import Chunk, RetrievalResult, SearchResult
from mirael.knowledge.retriever import Retriever
from mirael.knowledge.vector_store import QdrantVectorStore


def _make_search_result(text: str = "doc text", score: float = 0.9) -> SearchResult:
    return SearchResult(
        chunk=Chunk(
            document_id="d1",
            text=text,
            source_url="https://hl.xyz/docs",
            section_title="Intro",
            chunk_index=0,
        ),
        score=score,
        point_id="1",
    )


@pytest.fixture()
def mock_deps() -> tuple[AsyncMock, AsyncMock]:
    emb = AsyncMock(spec=OpenAIEmbeddings)
    emb.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4])
    store = AsyncMock(spec=QdrantVectorStore)
    store.search = AsyncMock(return_value=[])
    return emb, store


class TestRetriever:
    async def test_retrieve_returns_empty_when_no_hits(
        self, mock_deps: tuple[AsyncMock, AsyncMock]
    ) -> None:
        emb, store = mock_deps
        r = Retriever(emb, store)
        results = await r.retrieve("what is funding?")
        assert results == []

    async def test_retrieve_embeds_query(
        self, mock_deps: tuple[AsyncMock, AsyncMock]
    ) -> None:
        emb, store = mock_deps
        r = Retriever(emb, store)
        await r.retrieve("my query")
        emb.embed_query.assert_called_once_with("my query")

    async def test_retrieve_calls_search_with_vector(
        self, mock_deps: tuple[AsyncMock, AsyncMock]
    ) -> None:
        emb, store = mock_deps
        r = Retriever(emb, store)
        await r.retrieve("q", top_k=3)
        store.search.assert_called_once_with(
            [0.1, 0.2, 0.3, 0.4], top_k=3, filter_metadata=None
        )

    async def test_retrieve_maps_to_retrieval_results(
        self, mock_deps: tuple[AsyncMock, AsyncMock]
    ) -> None:
        emb, store = mock_deps
        store.search = AsyncMock(return_value=[_make_search_result()])
        r = Retriever(emb, store)
        results = await r.retrieve("q")
        assert len(results) == 1
        assert isinstance(results[0], RetrievalResult)
        assert results[0].score == pytest.approx(0.9)

    async def test_retrieve_passes_filter_metadata(
        self, mock_deps: tuple[AsyncMock, AsyncMock]
    ) -> None:
        emb, store = mock_deps
        r = Retriever(emb, store)
        await r.retrieve("q", filter_metadata={"source_url": "https://test.com"})
        call_kwargs = store.search.call_args.kwargs
        assert call_kwargs["filter_metadata"] == {"source_url": "https://test.com"}


class TestFormatContext:
    def test_empty_results_returns_empty_string(self) -> None:
        assert Retriever.format_context([]) == ""

    def test_formats_single_result(self) -> None:
        result = RetrievalResult(
            chunk=Chunk(
                document_id="d1",
                text="Funding rates are paid every 8 hours.",
                source_url="https://hl.xyz",
                section_title="Funding",
                chunk_index=0,
            ),
            score=0.95,
        )
        context = Retriever.format_context([result])
        assert "Funding" in context
        assert "Funding rates are paid" in context
        assert "https://hl.xyz" in context

    def test_respects_max_chars(self) -> None:
        results = [
            RetrievalResult(
                chunk=Chunk(
                    document_id="d1",
                    text="x " * 500,
                    source_url="https://test.com",
                    section_title="Big Section",
                    chunk_index=i,
                ),
                score=0.9 - i * 0.01,
            )
            for i in range(20)
        ]
        context = Retriever.format_context(results, max_chars=500)
        assert len(context) <= 600  # some tolerance for header line
