"""
Embedding provider implementations.

Two backends are supported:

``LocalEmbeddings`` (default)
    Uses ``sentence-transformers`` with ``BAAI/bge-large-en-v1.5`` locally.
    No API key required.  Model is downloaded once (~1.3 GB) on first use.

``OpenAIEmbeddings``
    Uses OpenAI ``text-embedding-3-large`` via API.
    Requires ``MIRAEL_OPENAI_API_KEY``.

Switch backend via ``MIRAEL_EMBEDDING_PROVIDER=openai`` (default: ``local``).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Protocol, runtime_checkable

from mirael.exceptions import AuthenticationError, EmbeddingError
from mirael.logging import get_logger

_log = get_logger(__name__)

_MAX_BATCH = 256


# ── Protocol ──────────────────────────────────────────────────────────────────


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Interface satisfied by both LocalEmbeddings and OpenAIEmbeddings."""

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of strings, return one vector per string."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        ...


# ── Local (sentence-transformers) ─────────────────────────────────────────────


class LocalEmbeddings:
    """
    Local embedding model using ``sentence-transformers``.

    Default model: ``BAAI/bge-large-en-v1.5`` (1024-dim, MIT license).
    Downloaded automatically on first use via Hugging Face Hub.

    Args:
        model_name: Any sentence-transformers compatible model name.
        dimensions: Output dimensions (must match the model's native dim).
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-en-v1.5",
        *,
        dimensions: int = 1024,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self._model: Any = None  # lazy-loaded

    def _get_model(self) -> Any:  # noqa: ANN401
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                _log.info("loading_local_embedding_model", model=self._model_name)
                self._model = SentenceTransformer(self._model_name)
                _log.info("local_embedding_model_ready", model=self._model_name)
            except ImportError as exc:
                raise EmbeddingError(
                    "sentence-transformers not installed. Run: uv sync",
                    code="KB_EMBEDDING_IMPORT",
                ) from exc
        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts using the local model."""
        if not texts:
            return []
        t0 = time.monotonic()
        model = self._get_model()
        loop = asyncio.get_event_loop()
        embeddings: list[list[float]] = await loop.run_in_executor(
            None,
            lambda: model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist(),
        )
        _log.debug(
            "local_embeddings_batch",
            count=len(texts),
            latency_ms=round((time.monotonic() - t0) * 1000),
        )
        return embeddings

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        results = await self.embed_texts([text])
        return results[0]


# ── OpenAI ────────────────────────────────────────────────────────────────────


class OpenAIEmbeddings:
    """
    OpenAI ``text-embedding-3-large`` embedding wrapper.

    Requires ``MIRAEL_OPENAI_API_KEY``.
    Only needed if ``MIRAEL_EMBEDDING_PROVIDER=openai``.

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
            from openai import AsyncOpenAI

            self._client: Any = AsyncOpenAI(api_key=api_key)
        except ImportError as exc:
            raise EmbeddingError(
                "openai package not installed. Run: uv add openai",
                code="KB_EMBEDDING_IMPORT",
            ) from exc
        self._model = model
        self._dimensions = dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, auto-batching if needed."""
        if not texts:
            return []
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), _MAX_BATCH):
            all_vectors.extend(await self._embed_batch(texts[i : i + _MAX_BATCH]))
        return all_vectors

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        results = await self.embed_texts([text])
        return results[0]

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
            "openai_embeddings_batch",
            count=len(texts),
            model=self._model,
            tokens=response.usage.total_tokens,
            latency_ms=round((time.monotonic() - t0) * 1000),
        )
        return [item.embedding for item in response.data]


# ── Factory ───────────────────────────────────────────────────────────────────


def create_from_settings(settings: Any) -> EmbeddingProvider:  # noqa: ANN401
    """
    Build the appropriate embedding backend from ``MiraelSettings``.

    Uses ``LocalEmbeddings`` by default.
    Set ``MIRAEL_EMBEDDING_PROVIDER=openai`` to use OpenAI instead.
    """
    provider = getattr(settings, "embedding_provider", "local")
    if provider == "openai":
        if not settings.openai_api_key:
            raise EmbeddingError(
                "MIRAEL_OPENAI_API_KEY is required when MIRAEL_EMBEDDING_PROVIDER=openai",
                code="KB_EMBEDDING_NO_KEY",
            )
        return OpenAIEmbeddings(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    return LocalEmbeddings(
        model_name=settings.local_embedding_model,
        dimensions=settings.embedding_dimensions,
    )
