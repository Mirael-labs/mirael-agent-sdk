"""
Structured logging via structlog.

Produces JSON logs in staging/production (Railway-compatible) and
human-readable colored output in development. Context can be bound
per-request via ``mirael.logging.bind_context()``.

Usage::

    from mirael.logging import get_logger
    log = get_logger(__name__)
    log.info("event_happened", key="value")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(
    level: str = "INFO",
    environment: str = "development",
) -> None:
    """
    Configure structlog and stdlib logging.

    Call once at application startup before any log statements.

    Args:
        level: Log level string (DEBUG/INFO/WARNING/ERROR).
        environment: Runtime environment — controls renderer choice.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if environment == "development":
        renderer: Any = structlog.dev.ConsoleRenderer(colors=True)
    else:
        shared_processors.append(structlog.processors.dict_tracebacks)
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "openai", "anthropic", "qdrant_client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return a bound structlog logger for the given module name.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A structlog BoundLogger instance.
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def bind_context(**kwargs: Any) -> None:  # noqa: ANN401
    """
    Bind key-value pairs to the current async/thread context.

    Bound values appear in all subsequent log calls within the same
    contextvars context (e.g. within a single request handler).

    Args:
        **kwargs: Arbitrary key-value pairs to bind.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all context-bound log variables for the current context."""
    structlog.contextvars.clear_contextvars()
