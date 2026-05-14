"""E2E test configuration — loads real settings from .env, bypassing test overrides."""

from __future__ import annotations

import pytest


@pytest.fixture()
def settings(monkeypatch: pytest.MonkeyPatch):
    """
    Load real MiraelSettings from .env for E2E tests.

    The global conftest autouse fixture overrides several env vars for unit
    tests (e.g. MIRAEL_QDRANT_URL=http://localhost:6333). We undo those here
    so E2E tests connect to the real services defined in .env.
    """
    # Remove unit-test overrides so pydantic-settings reads from .env
    for key in [
        "MIRAEL_QDRANT_URL",
        "MIRAEL_QDRANT_API_KEY",
        "MIRAEL_ANTHROPIC_API_KEY",
        "MIRAEL_OPENAI_API_KEY",
        "MIRAEL_ENVIRONMENT",
        "MIRAEL_LOG_LEVEL",
        "MIRAEL_EMBEDDING_PROVIDER",
    ]:
        monkeypatch.delenv(key, raising=False)

    from mirael.config import load_settings
    from mirael.logging import configure_logging

    s = load_settings()
    configure_logging(level="WARNING", environment=s.environment)
    return s
