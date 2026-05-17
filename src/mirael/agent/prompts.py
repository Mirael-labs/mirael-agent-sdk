"""
Parameterised system prompt construction.

Prompts are assembled from a fixed persona section plus dynamic
context blocks (RAG chunks, on-chain data) that change per turn.
Only the static section is eligible for Anthropic prompt caching.
"""

from __future__ import annotations

from typing import Any

from mirael.agent.models import AgentConfig

_BASE_PERSONA_TEMPLATE = """\
You are {name}, the AI support agent for {protocol_name}.

You have two superpowers:
1. You know the {protocol_name} documentation inside-out (retrieved in real time)
2. You can see the user's actual on-chain positions, health factor, and funding costs

Your job: give precise, numbers-first answers. When you have the user's wallet data,
always cite their specific figures (not generic examples). Warn clearly and early
when liquidation risk is elevated.

Be direct. Lead with the most important number. Use markdown for structure.

{extra_instructions}\
"""

_CHAIN_SECTION_TEMPLATE = """\
## Live account state
{content}
"""

_RAG_SECTION_HEADER = "## Relevant documentation\n"


def build_system_prompt(
    config: AgentConfig,
    *,
    chain_context: str = "",
    rag_context: str = "",
) -> str:
    """
    Build a complete system prompt for one agent turn.

    The returned string is passed as the ``system`` argument to
    ``LLMProvider.chat()``.  When Anthropic prompt caching is enabled,
    only the static persona section incurs write cost on subsequent turns.

    Args:
        config: Agent configuration (name, protocol, instructions).
        chain_context: Pre-formatted on-chain account state string.
                       Empty string omits the section.
        rag_context: Pre-formatted RAG chunk context string.
                     Empty string omits the section.

    Returns:
        A complete system prompt string.
    """
    extra = config.system_instructions.strip()
    extra_block = f"\n{extra}\n" if extra else ""

    persona = _BASE_PERSONA_TEMPLATE.format(
        name=config.name,
        protocol_name=config.protocol_name,
        extra_instructions=extra_block,
    ).rstrip()

    sections: list[str] = [persona]

    if chain_context.strip():
        sections.append(_CHAIN_SECTION_TEMPLATE.format(content=chain_context.strip()))

    if rag_context.strip():
        # RAG context already has its own header from Retriever.format_context
        sections.append(rag_context.strip())

    return "\n\n".join(sections)


def format_chain_context(
    balance: dict[str, Any],
    positions: list[dict[str, Any]],
) -> str:
    """
    Format raw on-chain data dicts into a human-readable markdown block.

    Designed to accept the output of ``OnchainReader.get_user_balance()``
    and ``OnchainReader.get_user_positions()``.  Keys are protocol-agnostic
    so this works across different ``OnchainReader`` implementations.

    Args:
        balance: Balance summary dict (e.g. ``{"account_value": "48000"}``).
        positions: List of position dicts.

    Returns:
        Formatted markdown string.
    """
    lines: list[str] = []

    account_value = balance.get("account_value", balance.get("accountValue", "—"))
    free_margin = balance.get("free_margin", balance.get("freeMargin", "—"))
    lines.append(f"- Account value: **${account_value}**")
    lines.append(f"- Free margin: **${free_margin}**")

    if positions:
        lines.append("\n**Open positions:**")
        for p in positions:
            asset = p.get("coin", p.get("asset", "[unknown asset]"))
            size = p.get("szi", p.get("size", "?"))
            pnl = p.get("unrealizedPnl", p.get("unrealized_pnl", "?"))
            liq = p.get("liquidationPx", p.get("liquidation_price"))
            liq_str = f" | liq ${liq}" if liq else ""
            lines.append(f"  - {asset}: size {size} | PnL ${pnl}{liq_str}")
    else:
        lines.append("\n*No open positions.*")

    return "\n".join(lines)
