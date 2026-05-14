"""
E2E tests: full Agent pipeline with real Anthropic API.

Tests the complete flow:
  user question → RAG retrieval (Qdrant) → LLM call (Claude) → response

These tests consume real API tokens (~$0.01-0.05 per run).
Run sparingly: pytest tests/e2e/test_agent_e2e.py -m e2e --no-cov
"""

from __future__ import annotations

import time

import pytest

from mirael.agent.base import Agent
from mirael.agent.models import AgentConfig
from mirael.knowledge.embeddings import create_from_settings
from mirael.knowledge.retriever import Retriever
from mirael.knowledge.vector_store import QdrantVectorStore
from mirael.llm.anthropic import AnthropicLLM


@pytest.fixture()
def agent(settings):
    """Build a real Agent backed by Anthropic + Qdrant Cloud."""
    llm = AnthropicLLM(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.llm_model,
        max_tokens=512,  # keep short for tests → cheaper
    )
    embeddings = create_from_settings(settings)
    store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        collection=settings.qdrant_collection,
        vector_dim=settings.embedding_dimensions,
    )
    retriever = Retriever(embeddings=embeddings, vector_store=store)
    config = AgentConfig(
        name="TestAssistant",
        protocol_name="Hyperliquid",
        system_instructions="Keep answers short and concise. 2-3 sentences max.",
        max_rag_results=3,
        max_memory_turns=5,
    )
    return Agent(llm=llm, retriever=retriever, config=config)


@pytest.mark.e2e
class TestAgentRealLLM:
    async def test_basic_question_returns_response(self, agent: Agent) -> None:
        """The agent should respond to any question without crashing."""
        response = await agent.chat("What is Hyperliquid?")

        assert response.text
        assert len(response.text) > 20
        assert response.input_tokens > 0
        assert response.output_tokens > 0

    async def test_funding_rate_question_mentions_funding(self, agent: Agent) -> None:
        """Asking about funding should yield a response mentioning funding concepts."""
        response = await agent.chat("Explain funding rates briefly.")

        text_lower = response.text.lower()
        assert any(w in text_lower for w in ["funding", "rate", "payment", "long", "short"])

    async def test_rag_chunks_are_used(self, agent: Agent) -> None:
        """The agent should use RAG context (rag_chunks_used > 0) for relevant queries."""
        response = await agent.chat("What happens during liquidation on Hyperliquid?")

        assert response.rag_chunks_used > 0, (
            f"Expected RAG chunks to be used, got {response.rag_chunks_used}"
        )

    async def test_response_latency_under_30s(self, agent: Agent) -> None:
        """A simple question should complete in under 30 seconds end-to-end."""
        t0 = time.monotonic()
        response = await agent.chat("What is a perpetual future?")
        elapsed = time.monotonic() - t0

        assert response.text
        assert elapsed < 30.0, f"Response took {elapsed:.1f}s — too slow"

    async def test_multi_turn_memory_preserved(self, agent: Agent) -> None:
        """The agent should remember context across turns."""
        await agent.chat("My name is Mael and I trade on Hyperliquid.")
        response = await agent.chat("What platform did I say I trade on?")

        # Claude should recall Hyperliquid from the previous turn
        assert "hyperliquid" in response.text.lower()

    async def test_reset_clears_context(self, agent: Agent) -> None:
        """After reset, previous conversation context is gone."""
        await agent.chat("Remember the number 42.")
        agent.reset_memory()

        await agent.chat("What number did I ask you to remember?")
        # Claude should not know — context was cleared
        assert agent._memory.turn_count == 1  # only the latest turn


@pytest.mark.e2e
class TestStreamingAgent:
    async def test_stream_yields_chunks(self, agent: Agent) -> None:
        """stream_chat should yield multiple text chunks."""
        chunks = [c async for c in agent.stream_chat("What is Hyperliquid in one sentence?")]

        assert len(chunks) > 0
        full_text = "".join(chunks)
        assert len(full_text) > 10

    async def test_stream_complete_response_matches_content(self, agent: Agent) -> None:
        """Streamed and assembled text should be coherent."""
        chunks = [c async for c in agent.stream_chat("Define funding rate in one sentence.")]

        full = "".join(chunks)
        assert len(full) > 20
        # Should mention funding somewhere
        assert "funding" in full.lower() or "rate" in full.lower()

    async def test_stream_updates_memory(self, agent: Agent) -> None:
        """Streaming should update conversation memory when done."""
        assert agent._memory.turn_count == 0
        async for _ in agent.stream_chat("Hello"):
            pass
        assert agent._memory.turn_count == 1


@pytest.mark.e2e
class TestAgentWithChainContext:
    async def test_agent_works_without_chain_reader(self, agent: Agent) -> None:
        """Agent without a chain reader should still answer general questions."""
        assert agent._chain is None  # no chain reader configured
        response = await agent.chat("What is health factor in Aave?", wallet=None)

        assert response.text
        assert response.had_chain_context is False

    async def test_agent_graceful_with_bad_wallet(self, agent: Agent) -> None:
        """Agent with an invalid wallet should degrade gracefully, not crash."""
        # No chain reader configured → wallet is ignored
        response = await agent.chat(
            "What are my positions?",
            wallet="0x0000000000000000000000000000000000000000",
        )
        assert response.text
        assert isinstance(response.had_chain_context, bool)
