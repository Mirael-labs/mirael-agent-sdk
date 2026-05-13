"""Unit tests for structured logging setup."""

from __future__ import annotations

import logging

from mirael.logging import bind_context, clear_context, configure_logging, get_logger


class TestConfigureLogging:
    def test_configure_development_does_not_raise(self) -> None:
        configure_logging(level="INFO", environment="development")

    def test_configure_production_does_not_raise(self) -> None:
        configure_logging(level="WARNING", environment="production")

    def test_log_level_applied(self) -> None:
        configure_logging(level="DEBUG", environment="development")
        assert logging.getLogger().level == logging.DEBUG

    def test_configure_info_level(self) -> None:
        configure_logging(level="INFO", environment="development")
        assert logging.getLogger().level == logging.INFO


class TestGetLogger:
    def test_returns_bound_logger(self) -> None:
        configure_logging()
        logger = get_logger("test.module")
        assert logger is not None

    def test_logger_has_info_method(self) -> None:
        configure_logging()
        logger = get_logger("test.module")
        assert callable(getattr(logger, "info", None))


class TestContextBinding:
    def test_bind_and_clear(self) -> None:
        configure_logging()
        bind_context(request_id="abc-123", user="alice")
        # Should not raise
        clear_context()

    def test_clear_without_prior_bind(self) -> None:
        # Should be idempotent
        clear_context()
        clear_context()
