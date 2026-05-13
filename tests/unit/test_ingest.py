"""Unit tests for SemanticChunker and IngestPipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mirael.exceptions import IngestError
from mirael.knowledge.embeddings import OpenAIEmbeddings
from mirael.knowledge.ingest import IngestPipeline, SemanticChunker
from mirael.knowledge.models import Document
from mirael.knowledge.vector_store import QdrantVectorStore


def _doc(content: str, title: str = "Test Doc") -> Document:
    return Document(url="https://test.com/doc", title=title, content=content)


class TestSemanticChunker:
    def test_single_chunk_for_short_doc(self) -> None:
        chunker = SemanticChunker(chunk_size=100, overlap=10)
        doc = _doc("word " * 50)
        chunks = chunker.chunk_document(doc)
        assert len(chunks) == 1

    def test_multiple_chunks_for_long_doc(self) -> None:
        chunker = SemanticChunker(chunk_size=10, overlap=2)
        doc = _doc("word " * 50)
        chunks = chunker.chunk_document(doc)
        assert len(chunks) > 1

    def test_chunk_indices_sequential(self) -> None:
        chunker = SemanticChunker(chunk_size=10, overlap=2)
        doc = _doc("word " * 50)
        chunks = chunker.chunk_document(doc)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_inherits_document_id(self) -> None:
        chunker = SemanticChunker(chunk_size=100, overlap=10)
        doc = _doc("hello world " * 20)
        chunks = chunker.chunk_document(doc)
        assert all(c.document_id == doc.id for c in chunks)

    def test_chunk_inherits_source_url(self) -> None:
        chunker = SemanticChunker(chunk_size=100, overlap=10)
        doc = _doc("hello " * 20)
        chunks = chunker.chunk_document(doc)
        assert all(c.source_url == doc.url for c in chunks)

    def test_empty_document_returns_no_chunks(self) -> None:
        chunker = SemanticChunker()
        assert chunker.chunk_document(_doc("")) == []

    def test_whitespace_only_returns_no_chunks(self) -> None:
        chunker = SemanticChunker()
        assert chunker.chunk_document(_doc("   \n\t  ")) == []

    def test_overlap_larger_than_chunk_raises(self) -> None:
        with pytest.raises(ValueError, match="overlap"):
            SemanticChunker(chunk_size=10, overlap=10)

    def test_section_title_extracted_from_markdown_heading(self) -> None:
        chunker = SemanticChunker(chunk_size=100, overlap=10)
        doc = _doc("## Funding Rates\nFunding is paid every 8 hours " * 5)
        chunks = chunker.chunk_document(doc)
        assert chunks[0].section_title == "Funding Rates"

    def test_falls_back_to_doc_title(self) -> None:
        chunker = SemanticChunker(chunk_size=100, overlap=10)
        doc = _doc("no headings here " * 10, title="My Document")
        chunks = chunker.chunk_document(doc)
        assert chunks[0].section_title == "My Document"

    def test_overlap_creates_shared_words(self) -> None:
        chunker = SemanticChunker(chunk_size=5, overlap=2)
        words = ["a", "b", "c", "d", "e", "f", "g"]
        doc = _doc(" ".join(words))
        chunks = chunker.chunk_document(doc)
        if len(chunks) > 1:
            last_of_first = chunks[0].text.split()[-2:]
            first_of_second = chunks[1].text.split()[:2]
            assert last_of_first == first_of_second


class TestIngestPipeline:
    def _make_pipeline(self) -> tuple[IngestPipeline, AsyncMock, AsyncMock]:
        mock_emb = AsyncMock(spec=OpenAIEmbeddings)
        mock_store = AsyncMock(spec=QdrantVectorStore)
        mock_store.ensure_collection = AsyncMock()
        mock_store.upsert = AsyncMock()
        # embed_texts returns one vector per text
        mock_emb.embed_texts = AsyncMock(
            side_effect=lambda texts: [[0.1] * 4 for _ in texts]
        )
        chunker = SemanticChunker(chunk_size=10, overlap=2)
        pipeline = IngestPipeline(chunker, mock_emb, mock_store, batch_size=50)
        return pipeline, mock_emb, mock_store

    async def test_ingest_returns_chunk_count(self) -> None:
        pipeline, _, _ = self._make_pipeline()
        docs = [_doc("word " * 50), _doc("sentence " * 30)]
        count = await pipeline.ingest(docs)
        assert count > 0

    async def test_ingest_empty_list_returns_zero(self) -> None:
        pipeline, mock_emb, _ = self._make_pipeline()
        count = await pipeline.ingest([])
        assert count == 0
        mock_emb.embed_texts.assert_not_called()

    async def test_ensure_collection_called(self) -> None:
        pipeline, _, mock_store = self._make_pipeline()
        await pipeline.ingest([_doc("content " * 20)])
        mock_store.ensure_collection.assert_called_once()

    async def test_upsert_called_with_vectors(self) -> None:
        pipeline, _, mock_store = self._make_pipeline()
        await pipeline.ingest([_doc("content " * 20)])
        mock_store.upsert.assert_called()

    async def test_embed_failure_raises_ingest_error(self) -> None:
        pipeline, mock_emb, _ = self._make_pipeline()
        mock_emb.embed_texts.side_effect = Exception("network error")
        with pytest.raises(IngestError):
            await pipeline.ingest([_doc("content " * 20)])
