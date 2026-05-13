"""
OpenAI ``text-embedding-3-large`` embedding wrapper.

Supports batch encoding with automatic chunking to stay under the
OpenAI 2048-input-per-request limit. Raises ``EmbeddingError`` on
any API failure so callers need not import the openai package.
"""

from __future__ import annotations

import time
from typing import Any

from mirael.exceptions import AuthenticationError, EmbeddingError
from mirael.logging import get_logger

_log = get_logger(__name__)

_MAX_BATCH = 256  # well under OpenAI's 2048 limit; keeps latency predictable


class OpenAIEmbeddings:
    """
    Async wrapper around ``openai.AsyncOpenAI`` for text embeddings.

    Args:
        api_key: OpenAI secret key.
        model: Embedding model identifier.
        dimensions: Output vector dimensions (matryoshka truncation).
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "text-embedding-3-large",
        dimensions: int = 3072,
    ) -> None:
        try:
            from openai import AsyncOpenAI  # deferred to avoid startup penalty

            self._client: Any = AsyncOpenAI(api_key=api_key)
        except ImportError as exc:
            raise EmbeddingError(
                "openai package not installed. Run: uv add openai",
                code="KB_EMBEDDING_IMPORT",
            ) from exc
        self._model = model
        self._dimensions = dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts, automatically batching if needed.

        Args:
            texts: Input strings to embed.

        Returns:
            List of float vectors, one per input text.

        Raises:
            EmbeddingError: On API or import failure.
            AuthenticationError: On invalid API key.
        """
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), _MAX_BATCH):
            batch = texts[i : i + _MAX_BATCH]
            all_vectors.extend(await self._embed_batch(batch))
        return all_vectors

    async def embed_query(self, text: str) -> list[float]:
        """
        Embed a single query string.

        Equivalent to ``embed_texts([text])[0]`` but more ergonomic.
        """
        vectors = await self.embed_texts([text])
        return vectors[0]

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        import openai

        t0 = time.monotonic()
        try:
            response = await self._client.embeddings.create(
                input=texts,
                model=self._model,
                dimensions=self._dimensions,
            )
        except openai.AuthenticationError as exc:
            raise AuthenticationError(str(exc)) from exc
        except openai.RateLimitError as exc:
            raise EmbeddingError(
                f"OpenAI rate limit: {exc}", code="KB_EMBEDDING_RATE_LIMIT"
            ) from exc
        except openai.OpenAIError as exc:
            raise EmbeddingError(str(exc)) from exc

        _log.debug(
            "embeddings_batch",
            count=len(texts),
            model=self._model,
            tokens=response.usage.total_tokens,
            latency_ms=round((time.monotonic() - t0) * 1000),
        )

        return [item.embedding for item in response.data]


def create_from_settings(settings: Any) -> OpenAIEmbeddings:  # noqa: ANN401
    """Factory: build ``OpenAIEmbeddings`` from a ``MiraelSettings`` instance."""
    return OpenAIEmbeddings(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )
