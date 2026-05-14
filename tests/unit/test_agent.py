"""Unit tests for the Agent class."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from mirael.agent.base import Agent
from mirael.agent.models import AgentConfig, AgentResponse
from mirael.exceptions import LLMError
from mirael.knowledge.models import Chunk, RetrievalResult
from mirael.knowledge.retriever import Retriever
from mirael.llm.models import LLMResponse


def _make_llm_response(text: str = "Hi there!") -> LLMResponse:
    return LLMResponse(
        text=text,
        model="claude-sonnet-4-5",
        input_tokens=50,
        output_tokens=10,
        cache_read_tokens=5,
    )


def _make_retrieval_result(text: str = "doc chunk") -> RetrievalResult:
    return RetrievalResult(
        chunk=Chunk(
            document_id="d1",
            text=text,
            source_url="https://hl.xyz",
            section_title="Docs",
            chunk_index=0,
        ),
        score=0.9,
    )


@pytest.fixture()
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value=_make_llm_response())
    return llm


@pytest.fixture()
def mock_retriever() -> AsyncMock:
    retriever = AsyncMock(spec=Retriever)
    retriever.retrieve = AsyncMock(return_value=[_make_retrieval_result()])
    return retriever


class TestAgentChat:
    async def test_returns_agent_response(self, mock_llm: AsyncMock) -> None:
        agent = Agent(llm=mock_llm)
        result = await agent.chat("hello")
        assert isinstance(result, AgentResponse)
        assert result.text == "Hi there!"

    async def test_calls_llm_with_messages(self, mock_llm: AsyncMock) -> None:
        agent = Agent(llm=mock_llm)
        await agent.chat("my question")
        mock_llm.chat.assert_called_once()
        call_args = mock_llm.chat.call_args
        messages = call_args.args[0]
        assert messages[-1].content == "my question"
        assert messages[-1].role == "user"

    async def test_stores_turn_in_memory(self, mock_llm: AsyncMock) -> None:
        agent = Agent(llm=mock_llm)
        await agent.chat("q1")
        assert agent._memory.turn_count == 1

    async def test_memory_persists_across_turns(self, mock_llm: AsyncMock) -> None:
        agent = Agent(llm=mock_llm)
        await agent.chat("q1")
        await agent.chat("q2")
        # LLM should see both turns on the second call.
        # On the second call: q1, a1 (from first turn) + q2 (added before call) = 3 messages.
        # a2 is only added after the LLM responds.
        second_call_messages = mock_llm.chat.call_args.args[0]
        assert len(second_call_messages) == 3
        assert any(m.content == "q1" for m in second_call_messages)

    async def test_without_retriever_no_rag(self, mock_llm: AsyncMock) -> None:
        agent = Agent(llm=mock_llm)
        result = await agent.chat("q")
        assert result.rag_chunks_used == 0

    async def test_with_retriever_uses_rag(
        self, mock_llm: AsyncMock, mock_retriever: AsyncMock
    ) -> None:
        agent = Agent(llm=mock_llm, retriever=mock_retriever)
        result = await agent.chat("q")
        mock_retriever.retrieve.assert_called_once()
        assert result.rag_chunks_used == 1

    async def test_system_prompt_passed_to_llm(self, mock_llm: AsyncMock) -> None:
        config = AgentConfig(name="TestBot", protocol_name="MyProtocol")
        agent = Agent(llm=mock_llm, config=config)
        await agent.chat("hello")
        call_kwargs = mock_llm.chat.call_args.kwargs
        assert "TestBot" in call_kwargs["system"]
        assert "MyProtocol" in call_kwargs["system"]

    async def test_token_usage_in_response(self, mock_llm: AsyncMock) -> None:
        agent = Agent(llm=mock_llm)
        result = await agent.chat("q")
        assert result.input_tokens == 50
        assert result.output_tokens == 10
        assert result.cache_read_tokens == 5

    async def test_llm_error_propagates(self) -> None:
        llm = AsyncMock()
        llm.chat = AsyncMock(side_effect=LLMError("API down"))
        agent = Agent(llm=llm)
        with pytest.raises(LLMError):
            await agent.chat("q")

    async def test_with_chain_reader_fetches_context(self, mock_llm: AsyncMock) -> None:
        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(return_value={"account_value": "50000"})
        chain.get_user_positions = AsyncMock(return_value=[])
        agent = Agent(llm=mock_llm, chain_reader=chain)
        result = await agent.chat("q", wallet="0xabc")
        assert result.had_chain_context is True
        chain.get_user_balance.assert_called_once_with("0xabc")

    async def test_no_wallet_skips_chain(self, mock_llm: AsyncMock) -> None:
        chain = AsyncMock()
        agent = Agent(llm=mock_llm, chain_reader=chain)
        result = await agent.chat("q", wallet=None)
        assert result.had_chain_context is False
        chain.get_user_balance.assert_not_called()

    async def test_chain_failure_is_graceful(self, mock_llm: AsyncMock) -> None:
        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(side_effect=Exception("network"))
        chain.get_user_positions = AsyncMock(side_effect=Exception("network"))
        agent = Agent(llm=mock_llm, chain_reader=chain)
        result = await agent.chat("q", wallet="0xabc")
        # Should still return a response, just without chain context
        assert isinstance(result, AgentResponse)
        assert result.had_chain_context is False

    async def test_rag_failure_is_graceful(self, mock_llm: AsyncMock) -> None:
        retriever = AsyncMock(spec=Retriever)
        retriever.retrieve = AsyncMock(side_effect=Exception("qdrant down"))
        agent = Agent(llm=mock_llm, retriever=retriever)
        result = await agent.chat("q")
        assert result.rag_chunks_used == 0


class TestAgentStreamChat:
    def test_stream_chat_returns_async_iterator(self, mock_llm: AsyncMock) -> None:
        async def _gen() -> AsyncIterator[str]:
            yield "hello"
            yield " world"

        mock_llm.stream_chat = MagicMock(return_value=_gen())
        agent = Agent(llm=mock_llm)
        result = agent.stream_chat("q")
        assert hasattr(result, "__aiter__")


class TestAgentReset:
    async def test_reset_clears_memory(self, mock_llm: AsyncMock) -> None:
        agent = Agent(llm=mock_llm)
        await agent.chat("q1")
        assert agent._memory.turn_count == 1
        agent.reset_memory()
        assert agent._memory.turn_count == 0

    async def test_after_reset_starts_fresh(self, mock_llm: AsyncMock) -> None:
        agent = Agent(llm=mock_llm)
        await agent.chat("q1")
        agent.reset_memory()
        await agent.chat("q2")
        messages = mock_llm.chat.call_args.args[0]
        # Should only have q2, not q1
        assert not any(m.content == "q1" for m in messages)


class TestAgentConfig:
    def test_default_config(self, mock_llm: AsyncMock) -> None:
        agent = Agent(llm=mock_llm)
        assert agent.config.name == "Agent"
        assert agent.config.protocol_name == "DeFi Protocol"

    def test_custom_config(self, mock_llm: AsyncMock) -> None:
        config = AgentConfig(name="MyBot", protocol_name="MyChain")
        agent = Agent(llm=mock_llm, config=config)
        assert agent.config.name == "MyBot"

    def test_config_max_turns_passed_to_memory(self) -> None:
        llm = AsyncMock()
        config = AgentConfig(max_memory_turns=5)
        agent = Agent(llm=llm, config=config)
        assert agent._memory._max_turns == 5
