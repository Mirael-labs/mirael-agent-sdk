"""
E2E tests: Discord bot adapter internals (no real Discord connection needed).

Tests the command handler logic by calling the Agent directly with the
same prompts the Discord slash commands would send.
"""

from __future__ import annotations

import pytest

from mirael.agent.base import Agent
from mirael.agent.models import AgentConfig
from mirael.knowledge.embeddings import create_from_settings
from mirael.knowledge.retriever import Retriever
from mirael.knowledge.vector_store import QdrantVectorStore
from mirael.llm.anthropic import AnthropicLLM
from mirael.monitoring.health_monitor import HealthAlert, HealthMonitor


@pytest.fixture()
def agent(settings):
    llm = AnthropicLLM(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.llm_model,
        max_tokens=256,
    )
    embeddings = create_from_settings(settings)
    store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        collection=settings.qdrant_collection,
        vector_dim=settings.embedding_dimensions,
    )
    config = AgentConfig(
        name="MiraelAgent",
        protocol_name="Hyperliquid",
        system_instructions="Keep answers under 3 sentences.",
        max_rag_results=2,
    )
    return Agent(llm=llm, retriever=Retriever(embeddings=embeddings, vector_store=store), config=config)


@pytest.mark.e2e
class TestDiscordCommandLogic:
    """
    Simulate the logic behind /ask, /positions, /health Discord commands
    by directly calling the Agent the same way the bot handlers do.
    """

    async def test_ask_command_logic(self, agent: Agent) -> None:
        """Simulates /ask what is funding rate?"""
        question = "What is the funding rate?"
        response = await agent.chat(question, wallet=None)

        assert response.text
        assert response.input_tokens > 0

    async def test_positions_command_logic(self, agent: Agent) -> None:
        """Simulates /positions — asks about open positions."""
        response = await agent.chat(
            "Show me my open positions with size, PnL, and liquidation price.",
            wallet=None,
        )
        assert response.text
        # No wallet configured → agent should still respond (just without real data)

    async def test_health_command_logic(self, agent: Agent) -> None:
        """Simulates /health — asks for risk assessment."""
        response = await agent.chat(
            "What is my current health factor and liquidation risk? "
            "Give me a clear risk assessment.",
            wallet=None,
        )
        assert response.text
        text_lower = response.text.lower()
        assert any(w in text_lower for w in ["health", "liquidat", "risk", "position", "wallet"])

    async def test_response_fits_discord_limit(self, agent: Agent) -> None:
        """Discord limit is 2000 chars. Responses should be manageable."""
        response = await agent.chat("Explain Hyperliquid funding rates in detail.")
        # With max_tokens=256, response should be well under 2000 chars
        assert len(response.text) < 2000

    async def test_multiple_users_independent_memory(self, settings) -> None:
        """Each Discord user gets their own Agent instance with independent memory."""
        llm = AnthropicLLM(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
            max_tokens=100,
        )
        embeddings = create_from_settings(settings)
        store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            collection=settings.qdrant_collection,
            vector_dim=settings.embedding_dimensions,
        )
        config = AgentConfig(name="Bot", protocol_name="Hyperliquid", max_rag_results=1)

        # Simulate two different users with separate agent instances
        agent_user1 = Agent(llm=llm, retriever=Retriever(embeddings=embeddings, vector_store=store), config=config)
        agent_user2 = Agent(llm=llm, retriever=Retriever(embeddings=embeddings, vector_store=store), config=config)

        await agent_user1.chat("I have a BTC long position.")
        await agent_user2.chat("I prefer ETH.")

        # Each agent has its own memory
        assert agent_user1._memory.turn_count == 1
        assert agent_user2._memory.turn_count == 1
        # User1's memory doesn't contaminate user2's
        assert agent_user1._memory.get_messages()[0].content != agent_user2._memory.get_messages()[0].content


@pytest.mark.e2e
class TestHealthMonitorLogic:
    """Test HealthMonitor logic with simulated on-chain data."""

    async def test_monitor_fires_critical_alert(self) -> None:
        """HealthMonitor fires critical alert when health factor < 1.2."""
        from unittest.mock import AsyncMock

        alerts_fired: list[HealthAlert] = []

        async def capture_alert(alert: HealthAlert) -> None:
            alerts_fired.append(alert)

        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(return_value={"health_factor": 1.1})
        chain.get_user_positions = AsyncMock(return_value=[])

        monitor = HealthMonitor(chain_reader=chain, check_interval=60, on_alert=capture_alert)
        await monitor._check("0xtest")

        assert len(alerts_fired) == 1
        assert alerts_fired[0].severity == "critical"
        assert "1.1" in alerts_fired[0].message or "CRITICAL" in alerts_fired[0].message.upper()

    async def test_monitor_fires_warning_alert(self) -> None:
        """HealthMonitor fires warning at health factor 1.3 (between 1.2 and 1.5)."""
        from unittest.mock import AsyncMock

        alerts: list[HealthAlert] = []

        async def capture(alert: HealthAlert) -> None:
            alerts.append(alert)

        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(return_value={"health_factor": 1.3})
        chain.get_user_positions = AsyncMock(return_value=[])

        monitor = HealthMonitor(chain_reader=chain, check_interval=60, on_alert=capture)
        await monitor._check("0xtest")

        assert len(alerts) == 1
        assert alerts[0].severity == "warning"

    async def test_monitor_no_alert_when_safe(self) -> None:
        """No alert when health factor > 1.5."""
        from unittest.mock import AsyncMock

        alerts: list[HealthAlert] = []

        async def capture(alert: HealthAlert) -> None:
            alerts.append(alert)

        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(return_value={"health_factor": 2.5})
        chain.get_user_positions = AsyncMock(return_value=[])

        monitor = HealthMonitor(chain_reader=chain, check_interval=60, on_alert=capture)
        await monitor._check("0xtest")

        assert len(alerts) == 0
