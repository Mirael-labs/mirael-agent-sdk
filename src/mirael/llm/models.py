"""Shared data models for the LLM layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single turn in a conversation."""

    role: Literal["user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    """Structured response from an LLM provider."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = Field(default=0)
    cache_write_tokens: int = Field(default=0)

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed (input + output)."""
        return self.input_tokens + self.output_tokens

    @property
    def cached_tokens(self) -> int:
        """Tokens served from prompt cache (zero cost on Anthropic)."""
        return self.cache_read_tokens
