"""Unit tests for the exception hierarchy."""

from __future__ import annotations

import pytest

from mirael.exceptions import (
    AuthenticationError,
    ChainConnectionError,
    ChainDataError,
    ChainError,
    ConfigurationError,
    ContextLengthError,
    EmbeddingError,
    IngestError,
    KnowledgeBaseError,
    LLMError,
    MiraelError,
    RateLimitError,
    VectorStoreError,
)


class TestMiraelError:
    def test_default_code(self) -> None:
        err = MiraelError("something failed")
        assert err.code == "MIRAEL_ERROR"
        assert err.message == "something failed"

    def test_custom_code(self) -> None:
        err = MiraelError("oops", code="CUSTOM_CODE")
        assert err.code == "CUSTOM_CODE"

    def test_str_includes_code(self) -> None:
        err = MiraelError("boom", code="TEST_CODE")
        assert "[TEST_CODE]" in str(err)
        assert "boom" in str(err)

    def test_repr(self) -> None:
        err = MiraelError("boom", code="X")
        assert "MiraelError" in repr(err)

    def test_is_exception(self) -> None:
        with pytest.raises(MiraelError):
            raise MiraelError("test")


class TestInheritanceHierarchy:
    def test_config_is_mirael(self) -> None:
        assert issubclass(ConfigurationError, MiraelError)

    def test_llm_is_mirael(self) -> None:
        assert issubclass(LLMError, MiraelError)

    def test_rate_limit_is_llm(self) -> None:
        assert issubclass(RateLimitError, LLMError)
        assert issubclass(RateLimitError, MiraelError)

    def test_context_length_is_llm(self) -> None:
        assert issubclass(ContextLengthError, LLMError)

    def test_kb_is_mirael(self) -> None:
        assert issubclass(KnowledgeBaseError, MiraelError)

    def test_embedding_is_kb(self) -> None:
        assert issubclass(EmbeddingError, KnowledgeBaseError)

    def test_vector_store_is_kb(self) -> None:
        assert issubclass(VectorStoreError, KnowledgeBaseError)

    def test_ingest_is_kb(self) -> None:
        assert issubclass(IngestError, KnowledgeBaseError)

    def test_chain_is_mirael(self) -> None:
        assert issubclass(ChainError, MiraelError)

    def test_chain_connection_is_chain(self) -> None:
        assert issubclass(ChainConnectionError, ChainError)

    def test_chain_data_is_chain(self) -> None:
        assert issubclass(ChainDataError, ChainError)

    def test_auth_is_mirael(self) -> None:
        assert issubclass(AuthenticationError, MiraelError)

    def test_catch_all_with_base(self) -> None:
        """All subtypes can be caught with base MiraelError."""
        errors = [
            ConfigurationError("cfg"),
            LLMError("llm"),
            RateLimitError("rl"),
            KnowledgeBaseError("kb"),
            ChainError("chain"),
            AuthenticationError("auth"),
        ]
        for err in errors:
            with pytest.raises(MiraelError):
                raise err


class TestRateLimitError:
    def test_retry_after_default_none(self) -> None:
        err = RateLimitError("too many requests")
        assert err.retry_after is None

    def test_retry_after_set(self) -> None:
        err = RateLimitError("slow down", retry_after=30.0)
        assert err.retry_after == 30.0

    def test_default_code(self) -> None:
        assert RateLimitError("x").code == "LLM_RATE_LIMIT"
