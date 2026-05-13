"""
Anthropic ``claude-sonnet-4-5`` LLM provider.

Features:
- Prompt caching via ``cache_control: ephemeral`` on system prompts
- Automatic retry with exponential back-off on 429 / 529 / connection errors
- Structured logging of token usage and latency
- Maps Anthropic SDK exceptions → Mirael typed exceptions
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from mirael.exceptions import AuthenticationError, ContextLengthError, LLMError, RateLimitError
from mirael.llm.models import ChatMessage, LLMResponse
from mirael.logging import get_logger

_log = get_logger(__name__)

_RETRY_EXCEPTIONS = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)
_MAX_RETRIES = 5
_BASE_WAIT = 2.0
_MAX_WAIT = 60.0


def _build_system_blocks(system: str, cache: bool) -> list[dict[str, Any]]:
    """Return Anthropic system block list, optionally with prompt-cache header."""
    if not system:
        return []
    block: dict[str, Any] = {"type": "text", "text": system}
    if cache:
        block["cache_control"] = {"type": "ephemeral"}
    return [block]


def _to_api_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": m.role, "content": m.content} for m in messages]


class AnthropicLLM:
    """
    Anthropic LLM backend satisfying the ``LLMProvider`` Protocol.

    Args:
        api_key: Anthropic secret key.
        model: Model identifier (default ``claude-sonnet-4-5``).
        max_tokens: Default max completion tokens.
        cache_system_prompt: Enable prompt caching on system blocks.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-sonnet-4-5",
        max_tokens: int = 4096,
        cache_system_prompt: bool = True,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._cache = cache_system_prompt

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _call_with_retry(self, **kwargs: Any) -> anthropic.types.Message:  # noqa: ANN401
        """
        Call ``messages.create`` with exponential back-off retry.

        Retries on: RateLimitError, APIConnectionError, InternalServerError.
        Raises immediately on: AuthenticationError, other 4xx.
        """
        import asyncio

        last_exc: BaseException = RuntimeError("no attempts made")
        for attempt in range(_MAX_RETRIES):
            try:
                return await self._client.messages.create(**kwargs)  # type: ignore[no-any-return]
            except _RETRY_EXCEPTIONS as exc:
                wait = min(_BASE_WAIT * (2**attempt), _MAX_WAIT)
                _log.warning(
                    "llm_retry",
                    attempt=attempt + 1,
                    max_retries=_MAX_RETRIES,
                    wait_seconds=wait,
                    error=str(exc),
                )
                last_exc = exc
                await asyncio.sleep(wait)
            except anthropic.AuthenticationError as exc:
                raise AuthenticationError(str(exc)) from exc
            except anthropic.BadRequestError as exc:
                if "context_length" in str(exc).lower() or "too long" in str(exc).lower():
                    raise ContextLengthError(str(exc)) from exc
                raise LLMError(str(exc), code="LLM_BAD_REQUEST") from exc
            except anthropic.APIStatusError as exc:
                raise LLMError(
                    f"Anthropic API error {exc.status_code}: {exc.message}",
                    code="LLM_API_ERROR",
                ) from exc

        raise RateLimitError(
            f"Rate limited after {_MAX_RETRIES} attempts: {last_exc}",
            code="LLM_RATE_LIMIT",
        )

    # ── Public API ────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str = "",
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Single-turn completion with optional system prompt caching."""
        t0 = time.monotonic()
        system_blocks = _build_system_blocks(system, self._cache)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "messages": _to_api_messages(messages),
        }
        if system_blocks:
            kwargs["system"] = system_blocks

        response = await self._call_with_retry(**kwargs)

        text = next(
            (block.text for block in response.content if hasattr(block, "text")),
            "",
        )
        usage = response.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0

        _log.info(
            "llm_chat_complete",
            model=self._model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read,
            latency_ms=round((time.monotonic() - t0) * 1000),
        )

        return LLMResponse(
            text=text,
            model=response.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )

    async def _stream_generator(
        self,
        messages: list[ChatMessage],
        system: str,
        max_tokens: int | None,
    ) -> AsyncIterator[str]:
        """Async generator that yields text chunks from the streaming API."""
        system_blocks = _build_system_blocks(system, self._cache)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "messages": _to_api_messages(messages),
        }
        if system_blocks:
            kwargs["system"] = system_blocks

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str = "",
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Streaming completion — returns an async iterator of text chunks."""
        return self._stream_generator(messages, system, max_tokens)


def create_from_settings(settings: Any) -> AnthropicLLM:  # noqa: ANN401
    """
    Factory: build an ``AnthropicLLM`` from a ``MiraelSettings`` instance.

    Avoids importing ``MiraelSettings`` directly to prevent circular imports.
    """
    return AnthropicLLM(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
    )
