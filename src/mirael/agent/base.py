"""
Agent: orchestrates RAG retrieval, on-chain context, and LLM completion.

The ``Agent`` class is the main entry point for consumers of the SDK.
It wires together the knowledge retriever, an on-chain reader, and an
LLM provider into a single ``chat()`` / ``stream_chat()`` interface.

All dependencies are injected — the Agent itself has no opinions about
which LLM backend, vector store, or chain is used.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from mirael.agent.memory import InMemoryConversationMemory
from mirael.agent.models import AgentConfig, AgentResponse
from mirael.agent.prompts import build_system_prompt, format_chain_context
from mirael.chains.base import OnchainReader
from mirael.exceptions import MiraelError
from mirael.knowledge.retriever import Retriever
from mirael.llm.base import LLMProvider
from mirael.logging import get_logger

_log = get_logger(__name__)


class Agent:
    """
    Conversational agent combining RAG, on-chain context, and an LLM.

    Args:
        llm: Any object satisfying ``LLMProvider`` Protocol.
        retriever: Optional ``Retriever`` for knowledge-base lookups.
                   If ``None``, no RAG context is injected.
        chain_reader: Optional ``OnchainReader`` for live wallet data.
                      If ``None``, no on-chain context is injected.
        memory: Conversation memory instance.
                Defaults to a fresh ``InMemoryConversationMemory``.
        config: Agent persona and behaviour configuration.

    Example::

        agent = Agent(llm=AnthropicLLM(api_key="..."), config=AgentConfig(
            name="HyperAssist",
            protocol_name="Hyperliquid",
        ))
        reply = await agent.chat("What is the funding rate for BTC?")
    """

    def __init__(
        self,
        llm: LLMProvider,
        *,
        retriever: Retriever | None = None,
        chain_reader: OnchainReader | None = None,
        memory: InMemoryConversationMemory | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._chain = chain_reader
        self._memory = memory or InMemoryConversationMemory(
            max_turns=(config or AgentConfig()).max_memory_turns
        )
        self._config = config or AgentConfig()

    # ── Public API ────────────────────────────────────────────────────────────

    async def chat(
        self,
        user_message: str,
        *,
        wallet: str | None = None,
    ) -> AgentResponse:
        """
        Process one user message and return a complete response.

        Steps:
        1. Retrieve top-k RAG chunks for the user message.
        2. Fetch live on-chain context for ``wallet`` (if provided).
        3. Build the system prompt from persona + context.
        4. Add the user message to memory.
        5. Call the LLM with the full message history.
        6. Store the assistant reply in memory.
        7. Return an ``AgentResponse``.

        Args:
            user_message: The user's input text.
            wallet: Optional wallet address for on-chain context lookup.

        Returns:
            ``AgentResponse`` with text, token usage, and metadata.

        Raises:
            MiraelError: If the LLM call fails after retries.
        """
        rag_results, chain_ctx = await self._gather_context(user_message, wallet)

        rag_context = Retriever.format_context(rag_results) if rag_results else ""
        system = build_system_prompt(
            self._config,
            chain_context=chain_ctx,
            rag_context=rag_context,
        )

        self._memory.add_user(user_message)
        messages = self._memory.get_messages()

        _log.info(
            "agent_chat",
            turns=self._memory.turn_count,
            rag_chunks=len(rag_results),
            has_chain=bool(chain_ctx),
        )

        llm_response = await self._llm.chat(messages, system=system)
        self._memory.add_assistant(llm_response.text)

        return AgentResponse(
            text=llm_response.text,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            cache_read_tokens=llm_response.cache_read_tokens,
            rag_chunks_used=len(rag_results),
            had_chain_context=bool(chain_ctx),
        )

    def stream_chat(
        self,
        user_message: str,
        *,
        wallet: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Process one user message with streaming token output.

        Yields text chunks as they arrive from the LLM.  Memory is updated
        with the complete response once streaming is finished.

        Args:
            user_message: The user's input text.
            wallet: Optional wallet address for on-chain context lookup.

        Returns:
            AsyncIterator that yields ``str`` chunks.
        """
        return self._stream_generator(user_message, wallet)

    def reset_memory(self) -> None:
        """Clear conversation history."""
        self._memory.clear()

    @property
    def config(self) -> AgentConfig:
        """Read-only access to the agent configuration."""
        return self._config

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _gather_context(
        self,
        user_message: str,
        wallet: str | None,
    ) -> tuple[list[Any], str]:
        """Concurrently fetch RAG chunks and on-chain data."""
        rag_task = asyncio.create_task(self._get_rag_context(user_message))
        chain_task = asyncio.create_task(self._get_chain_context(wallet))
        rag_results, chain_ctx = await asyncio.gather(rag_task, chain_task)
        return rag_results, chain_ctx

    async def _get_rag_context(self, query: str) -> list[Any]:
        if not self._retriever:
            return []
        try:
            return await self._retriever.retrieve(
                query, top_k=self._config.max_rag_results
            )
        except MiraelError:
            raise
        except Exception as exc:
            _log.warning("rag_context_failed", error=str(exc))
            return []

    async def _get_chain_context(self, wallet: str | None) -> str:
        if not self._chain or not wallet:
            return ""
        try:
            balance, positions = await _gather_chain_data(self._chain, wallet)
            return format_chain_context(balance, positions)
        except Exception as exc:
            _log.warning("chain_context_failed", wallet=wallet, error=str(exc))
            return ""

    async def _stream_generator(
        self,
        user_message: str,
        wallet: str | None,
    ) -> AsyncIterator[str]:
        rag_results, chain_ctx = await self._gather_context(user_message, wallet)
        rag_context = Retriever.format_context(rag_results) if rag_results else ""
        system = build_system_prompt(
            self._config,
            chain_context=chain_ctx,
            rag_context=rag_context,
        )
        self._memory.add_user(user_message)

        full_text = ""
        async for chunk in self._llm.stream_chat(
            self._memory.get_messages(), system=system
        ):
            full_text += chunk
            yield chunk

        self._memory.add_assistant(full_text)


async def _gather_chain_data(
    reader: OnchainReader,
    wallet: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Concurrently fetch balance and positions."""
    balance_task = asyncio.create_task(reader.get_user_balance(wallet))
    positions_task = asyncio.create_task(reader.get_user_positions(wallet))
    balance, positions = await asyncio.gather(balance_task, positions_task)
    return balance, positions
