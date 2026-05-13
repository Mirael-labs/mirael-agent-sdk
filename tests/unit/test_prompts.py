"""Unit tests for agent prompt builders."""

from __future__ import annotations

from mirael.agent.models import AgentConfig
from mirael.agent.prompts import build_system_prompt, format_chain_context


class TestBuildSystemPrompt:
    def test_includes_agent_name(self) -> None:
        config = AgentConfig(name="HyperBot")
        prompt = build_system_prompt(config)
        assert "HyperBot" in prompt

    def test_includes_protocol_name(self) -> None:
        config = AgentConfig(protocol_name="Hyperliquid")
        prompt = build_system_prompt(config)
        assert "Hyperliquid" in prompt

    def test_includes_extra_instructions(self) -> None:
        config = AgentConfig(system_instructions="Always cite sources.")
        prompt = build_system_prompt(config)
        assert "Always cite sources." in prompt

    def test_no_extra_instructions_is_clean(self) -> None:
        config = AgentConfig()
        prompt = build_system_prompt(config)
        # Should not have extra blank lines from empty instructions
        assert "\n\n\n" not in prompt

    def test_chain_context_included_when_provided(self) -> None:
        config = AgentConfig()
        prompt = build_system_prompt(config, chain_context="Account value: $50,000")
        assert "Account value: $50,000" in prompt
        assert "Live account state" in prompt

    def test_chain_context_omitted_when_empty(self) -> None:
        config = AgentConfig()
        prompt = build_system_prompt(config, chain_context="")
        assert "Live account state" not in prompt

    def test_rag_context_included_when_provided(self) -> None:
        config = AgentConfig()
        rag = "## Relevant documentation\nFunding rates are..."
        prompt = build_system_prompt(config, rag_context=rag)
        assert "Funding rates are" in prompt

    def test_rag_context_omitted_when_empty(self) -> None:
        config = AgentConfig()
        prompt = build_system_prompt(config, rag_context="")
        assert "Relevant documentation" not in prompt

    def test_whitespace_only_chain_context_omitted(self) -> None:
        config = AgentConfig()
        prompt = build_system_prompt(config, chain_context="   \n  ")
        assert "Live account state" not in prompt

    def test_returns_non_empty_string(self) -> None:
        assert len(build_system_prompt(AgentConfig())) > 50


class TestFormatChainContext:
    def test_includes_account_value(self) -> None:
        result = format_chain_context({"account_value": "48000"}, [])
        assert "48000" in result

    def test_no_positions_shows_placeholder(self) -> None:
        result = format_chain_context({"account_value": "0"}, [])
        assert "No open positions" in result

    def test_positions_listed(self) -> None:
        positions = [
            {"coin": "BTC", "szi": "0.5", "unrealizedPnl": "200"},
            {"coin": "ETH", "szi": "-1.0", "unrealizedPnl": "-50"},
        ]
        result = format_chain_context({"account_value": "10000"}, positions)
        assert "BTC" in result
        assert "ETH" in result
        assert "0.5" in result

    def test_liq_price_shown_when_present(self) -> None:
        positions = [
            {
                "coin": "SOL",
                "szi": "10",
                "unrealizedPnl": "100",
                "liquidationPx": "120.5",
            }
        ]
        result = format_chain_context({}, positions)
        assert "120.5" in result

    def test_accepts_alternative_key_names(self) -> None:
        result = format_chain_context({"accountValue": "9999"}, [])
        assert "9999" in result
