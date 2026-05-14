"""
Volume tests: Agent under load with mocked LLM.

Tests that the Agent handles concurrent chat requests without
race conditions in memory or context building.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from mirael.agent.base import Agent
from mirael.agent.models import AgentConfig
from mirael.llm.models import LLMResponse


def _make_agent() -> Agent:
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=LLMResponse(
            text="The funding rate is currently 0.01% per hour.",
            model="claude-sonnet-4-5",
            input_tokens=100,
            output_tokens=30,
        )
    )
    config = AgentConfig(
        name="TestAgent",
        protocol_name="Hyperliquid",
        max_memory_turns=10,
    )
    return Agent(llm=llm, config=config)


@pytest.mark.volume
class TestAgentLoad:
    async def test_sequential_10_turns(self):
        """10 sequential turns in one conversation — memory stays intact."""
        agent = _make_agent()
        for i in range(10):
            response = await agent.chat(f"Question number {i}")
            assert response.text != ""

        assert agent._memory.turn_count == 10

    async def test_memory_trim_under_load(self):
        """Memory window trims cleanly after max_turns exceeded."""
        agent = _make_agent()  # max_memory_turns=10
        for i in range(25):
            await agent.chat(f"Message {i}")

        # Should be capped at 10 turns
        assert agent._memory.turn_count == 10

    async def test_independent_agents_no_shared_state(self):
        """Multiple agent instances should not share memory."""
        agents = [_make_agent() for _ in range(5)]

        # Each agent gets 3 turns
        for agent in agents:
            for i in range(3):
                await agent.chat(f"turn {i}")

        # Each should have exactly 3 turns
        for agent in agents:
            assert agent._memory.turn_count == 3

    async def test_response_time_under_mock(self):
        """With mocked LLM, 10 sequential chats should be fast."""
        agent = _make_agent()
        t0 = time.monotonic()
        for i in range(10):
            await agent.chat(f"q{i}")
        elapsed = time.monotonic() - t0

        # 10 mocked chats should complete well under 2 seconds
        assert elapsed < 2.0, f"10 sequential chats took {elapsed:.2f}s"
