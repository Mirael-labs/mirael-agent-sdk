"""
Semantic retriever — converts a natural-language query into top-k chunks.

Usage::

    retriever = Retriever(embeddings=emb, vector_store=store)
    results = await retriever.retrieve("what is the funding rate?", top_k=5)
    context = retriever.format_context(results)
"""

from __future__ import annotations

from mirael.knowledge.embeddings import EmbeddingProvider
from mirael.knowledge.models import RetrievalResult, SearchResult
from mirael.knowledge.vector_store import QdrantVectorStore
from mirael.logging import get_logger

_log = get_logger(__name__)


class Retriever:
    """
    Top-k semantic retriever over the Qdrant vector store.

    Args:
        embeddings: Embedding model used to encode queries.
        vector_store: Qdrant store to search against.
    """

    def __init__(
        self,
        embeddings: EmbeddingProvider,
        vector_store: QdrantVectorStore,
    ) -> None:
        self._embeddings = embeddings
        self._store = vector_store

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: dict[str, str] | None = None,
    ) -> list[RetrievalResult]:
        """
        Embed ``query`` and return the top-k most relevant chunks.

        Args:
            query: Natural-language question or search string.
            top_k: Maximum number of results.
            filter_metadata: Optional payload filters forwarded to Qdrant.

        Returns:
            List of ``RetrievalResult`` ordered by descending similarity.
        """
        query_vector = await self._embeddings.embed_query(query)
        hits: list[SearchResult] = await self._store.search(
            query_vector, top_k=top_k, filter_metadata=filter_metadata
        )
        results = [RetrievalResult(chunk=h.chunk, score=h.score) for h in hits]
        _log.debug("retrieved", query=query[:80], top_k=top_k, hits=len(results))
        return results

    @staticmethod
    def format_context(results: list[RetrievalResult], max_chars: int = 4000) -> str:
        """
        Format retrieval results as a context block for injection into a prompt.

        Args:
            results: Retrieved results, ordered by score.
            max_chars: Hard character limit on the returned string
                       (truncates gracefully at chunk boundaries).

        Returns:
            Markdown-formatted context string, or empty string if no results.
        """
        if not results:
            return ""

        lines: list[str] = ["## Relevant documentation\n"]
        total = len(lines[0])

        for r in results:
            header = f"### {r.chunk.section_title} — {r.chunk.source_url}\n"
            body = r.chunk.text + "\n\n"
            entry = header + body
            if total + len(entry) > max_chars:
                break
            lines.append(entry)
            total += len(entry)

        return "".join(lines)
