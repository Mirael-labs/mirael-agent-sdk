"""
Document ingestion pipeline: chunk → embed → store.

``SemanticChunker`` splits documents using recursive word-boundary
splitting with configurable overlap. ``IngestPipeline`` wires the
chunker, embedder, and vector store into a single ``ingest()`` call.
"""

from __future__ import annotations

import re

from mirael.exceptions import IngestError
from mirael.knowledge.embeddings import EmbeddingProvider
from mirael.knowledge.models import Chunk, Document
from mirael.knowledge.vector_store import QdrantVectorStore
from mirael.logging import get_logger

_log = get_logger(__name__)

_SENTENCE_ENDINGS = re.compile(r"(?<=[.!?])\s+")


class SemanticChunker:
    """
    Splits documents into overlapping word-boundary chunks.

    Args:
        chunk_size: Target chunk size in words.
        overlap: Number of words shared between consecutive chunks.
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 64) -> None:
        if overlap >= chunk_size:
            raise ValueError(f"overlap ({overlap}) must be < chunk_size ({chunk_size})")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk_document(self, doc: Document) -> list[Chunk]:
        """
        Split a document into overlapping word-boundary chunks.

        The section title is inferred from the first heading found
        in each chunk (``## Title``) or falls back to the document title.

        Args:
            doc: Source document.

        Returns:
            Ordered list of ``Chunk`` objects (may be empty for blank docs).
        """
        # Split preserving original lines so heading detection works correctly.
        lines = doc.content.splitlines(keepends=True)
        # Build a flat word list while tracking which original line each word came from.
        all_words: list[str] = []
        word_line_idx: list[int] = []
        for line_idx, line in enumerate(lines):
            for word in line.split():
                all_words.append(word)
                word_line_idx.append(line_idx)

        if not all_words:
            return []

        chunks: list[Chunk] = []
        start = 0
        idx = 0

        while start < len(all_words):
            end = min(start + self._chunk_size, len(all_words))
            chunk_text = " ".join(all_words[start:end])

            # Reconstruct the raw text slice for heading detection.
            first_line = word_line_idx[start]
            last_line = word_line_idx[end - 1]
            raw_slice = "".join(lines[first_line : last_line + 1])
            title = self._extract_section_title(raw_slice) or doc.title

            chunks.append(
                Chunk(
                    document_id=doc.id,
                    text=chunk_text,
                    source_url=doc.url,
                    section_title=title,
                    chunk_index=idx,
                )
            )
            idx += 1
            if end == len(all_words):
                break
            start += self._chunk_size - self._overlap

        return chunks

    @staticmethod
    def _extract_section_title(text: str) -> str | None:
        """Return the first markdown heading found in ``text``, or None."""
        for line in text.splitlines():
            stripped = line.lstrip("#").strip()
            if stripped and line.startswith("#"):
                return stripped
        return None


class IngestPipeline:
    """
    Orchestrates the full ingestion flow for a list of documents.

    Flow: documents → chunker → embedder → vector store upsert

    Args:
        chunker: ``SemanticChunker`` instance.
        embeddings: ``EmbeddingProvider`` instance.
        vector_store: ``QdrantVectorStore`` instance.
        batch_size: Max chunks per embedding API call.
    """

    def __init__(
        self,
        chunker: SemanticChunker,
        embeddings: EmbeddingProvider,
        vector_store: QdrantVectorStore,
        batch_size: int = 100,
    ) -> None:
        self._chunker = chunker
        self._embeddings = embeddings
        self._store = vector_store
        self._batch_size = batch_size

    async def ingest(self, documents: list[Document]) -> int:
        """
        Ingest a list of documents.

        Ensures the collection exists, chunks all documents, embeds in
        batches, and upserts into Qdrant.

        Args:
            documents: Source documents to ingest.

        Returns:
            Total number of chunks written to the vector store.

        Raises:
            IngestError: On chunking, embedding, or upsert failure.
        """
        try:
            await self._store.ensure_collection()
        except Exception as exc:
            raise IngestError(f"Collection setup failed: {exc}") from exc

        all_chunks: list[Chunk] = []
        for doc in documents:
            chunks = self._chunker.chunk_document(doc)
            all_chunks.extend(chunks)
            _log.debug("chunked_document", url=doc.url, chunks=len(chunks))

        if not all_chunks:
            _log.info("ingest_no_chunks", doc_count=len(documents))
            return 0

        total_written = 0
        for i in range(0, len(all_chunks), self._batch_size):
            batch = all_chunks[i : i + self._batch_size]
            try:
                vectors = await self._embeddings.embed_texts(
                    [c.text for c in batch]
                )
                await self._store.upsert(batch, vectors)
                total_written += len(batch)
                _log.info(
                    "ingest_batch_complete",
                    batch=i // self._batch_size + 1,
                    chunks=len(batch),
                    total_so_far=total_written,
                )
            except Exception as exc:
                raise IngestError(
                    f"Ingest failed at batch {i // self._batch_size + 1}: {exc}"
                ) from exc

        _log.info(
            "ingest_complete",
            documents=len(documents),
            total_chunks=total_written,
        )
        return total_written
