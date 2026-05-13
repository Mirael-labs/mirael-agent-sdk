"""Data models for the agent layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """
    Configuration for an Agent instance.

    Attributes:
        name: Display name shown in the system prompt
              (e.g. ``"HyperAssist"``).
        protocol_name: Name of the DeFi protocol being supported
                       (e.g. ``"Hyperliquid"``).
        system_instructions: Additional behaviour instructions injected
                             after the base persona paragraph.
        max_rag_results: How many RAG chunks to retrieve per turn.
        max_memory_turns: Maximum user+assistant turn pairs kept in memory.
    """

    name: str = Field(default="Agent")
    protocol_name: str = Field(default="DeFi Protocol")
    system_instructions: str = Field(default="")
    max_rag_results: int = Field(default=5, ge=1, le=20)
    max_memory_turns: int = Field(default=20, ge=1, le=100)


class AgentResponse(BaseModel):
    """
    Full response returned by ``Agent.chat()``.

    Attributes:
        text: Assistant reply text.
        input_tokens: Tokens consumed in the request.
        output_tokens: Tokens in the completion.
        cache_read_tokens: Tokens served from prompt cache (Anthropic).
        rag_chunks_used: Number of RAG chunks injected into the prompt.
        had_chain_context: Whether live on-chain data was included.
    """

    text: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = Field(default=0)
    rag_chunks_used: int = Field(default=0)
    had_chain_context: bool = Field(default=False)
