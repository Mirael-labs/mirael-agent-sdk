"""Shared pytest fixtures for the Mirael Agent SDK test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Inject minimal required environment variables for all tests.

    This prevents real API calls and satisfies ``MiraelSettings`` validation.
    """
    monkeypatch.setenv("MIRAEL_ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("MIRAEL_OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("MIRAEL_EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("MIRAEL_ENVIRONMENT", "development")
    monkeypatch.setenv("MIRAEL_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MIRAEL_QDRANT_URL", "http://localhost:6333")
