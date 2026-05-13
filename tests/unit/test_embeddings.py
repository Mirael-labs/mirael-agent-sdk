"""Unit tests for OpenAIEmbeddings."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mirael.exceptions import AuthenticationError, EmbeddingError
from mirael.knowledge.embeddings import OpenAIEmbeddings


def _make_openai_response(n: int = 1, dim: int = 4) -> MagicMock:
    response = MagicMock()
    response.data = [MagicMock(embedding=[0.1] * dim) for _ in range(n)]
    response.usage = MagicMock(total_tokens=10 * n)
    return response


@pytest.fixture()
def mock_openai_client() -> MagicMock:
    with patch("openai.AsyncOpenAI") as mock_cls:
        instance = AsyncMock()
        mock_cls.return_value = instance
        # Return as many embeddings as there are input texts
        async def _create_side_effect(**kwargs: object) -> MagicMock:
            texts = kwargs.get("input", [])
            n = len(texts) if isinstance(texts, list) else 1
            return _make_openai_response(n)
        instance.embeddings.create = AsyncMock(side_effect=_create_side_effect)
        yield instance


class TestOpenAIEmbeddings:
    async def test_embed_texts_returns_vectors(self, mock_openai_client: MagicMock) -> None:
        emb = OpenAIEmbeddings(api_key="sk-test")
        vectors = await emb.embed_texts(["hello", "world"])
        # Two texts → one batch call with 2 items
        assert len(vectors) == 2

    async def test_embed_empty_list(self, mock_openai_client: MagicMock) -> None:
        emb = OpenAIEmbeddings(api_key="sk-test")
        result = await emb.embed_texts([])
        assert result == []
        mock_openai_client.embeddings.create.assert_not_called()

    async def test_embed_query_returns_single_vector(self, mock_openai_client: MagicMock) -> None:
        mock_openai_client.embeddings.create = AsyncMock(
            return_value=_make_openai_response(1, dim=3072)
        )
        emb = OpenAIEmbeddings(api_key="sk-test")
        vector = await emb.embed_query("what is funding?")
        assert len(vector) == 3072

    async def test_auth_error_converted(self) -> None:
        import openai

        with patch("openai.AsyncOpenAI") as mock_cls:
            instance = AsyncMock()
            mock_cls.return_value = instance
            instance.embeddings.create.side_effect = openai.AuthenticationError(
                message="bad key", response=MagicMock(status_code=401), body={}
            )
            emb = OpenAIEmbeddings(api_key="bad")
            with pytest.raises(AuthenticationError):
                await emb.embed_texts(["test"])

    async def test_rate_limit_converted(self) -> None:
        import openai

        with patch("openai.AsyncOpenAI") as mock_cls:
            instance = AsyncMock()
            mock_cls.return_value = instance
            instance.embeddings.create.side_effect = openai.RateLimitError(
                message="429", response=MagicMock(status_code=429), body={}
            )
            emb = OpenAIEmbeddings(api_key="sk-test")
            with pytest.raises(EmbeddingError) as exc:
                await emb.embed_texts(["test"])
            assert exc.value.code == "KB_EMBEDDING_RATE_LIMIT"
