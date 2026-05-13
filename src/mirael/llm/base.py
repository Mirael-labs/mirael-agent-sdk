"""
LLM provider Protocol — structural interface for all LLM backends.

Using ``runtime_checkable`` Protocol (structural subtyping) means
concrete implementations do not need to inherit from this class.
The agent layer depends only on this interface, never on ``AnthropicLLM``
directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from mirael.llm.models import ChatMessage, LLMResponse


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface every LLM backend must satisfy."""

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str = "",
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Single-turn completion.

        Args:
            messages: Conversation history (user/assistant turns).
            system: Optional system prompt injected before messages.
            max_tokens: Override default max_tokens for this call.

        Returns:
            LLMResponse with text and token usage.

        Raises:
            LLMError: On API failure.
            RateLimitError: On 429 after retries exhausted.
            AuthenticationError: On 401 invalid key.
        """
        ...

    def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str = "",
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """
        Streaming completion — yields text chunks as they arrive.

        Args:
            messages: Conversation history.
            system: Optional system prompt.
            max_tokens: Override default max_tokens.

        Returns:
            AsyncIterator yielding string chunks.
        """
        ...
