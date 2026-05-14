#!/usr/bin/env python3
"""
Mirael Agent — Arbitrum / Aave V3 demo.

Shows the Mirael Agent reading live Aave V3 positions on Arbitrum
and answering questions about them.

Prerequisites:
  Set in .env:
    MIRAEL_ANTHROPIC_API_KEY=...
    MIRAEL_OPENAI_API_KEY=...
    MIRAEL_ARBITRUM_RPC_URL=https://arb1.arbitrum.io/rpc   (or Alchemy URL)

Usage:
  uv run python examples/arbitrum_aave_demo/main.py --wallet 0xYOUR_WALLET
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule

console = Console()
app = typer.Typer(add_completion=False)

_BANNER = """[bold cyan]Mirael Agent — Arbitrum / Aave V3[/bold cyan]
AI assistant with live Aave position context on Arbitrum.

[dim]Commands: /reset · /quit[/dim]"""

_QUESTIONS = [
    "What are my current Aave positions?",
    "What is my health factor?",
    "How much can I still borrow?",
    "What is the current USDC borrow rate on Aave?",
    "Am I at risk of liquidation?",
]


async def _run(wallet: str) -> None:
    from mirael.agent.base import Agent
    from mirael.agent.models import AgentConfig
    from mirael.chains.evm import AaveV3Reader
    from mirael.config import load_settings
    from mirael.knowledge.retriever import Retriever
    from mirael.knowledge.vector_store import QdrantVectorStore
    from mirael.llm.anthropic import AnthropicLLM
    from mirael.logging import configure_logging

    settings = load_settings()
    configure_logging(level="WARNING", environment=settings.environment)

    llm = AnthropicLLM(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.llm_model,
    )
    from mirael.knowledge.embeddings import create_from_settings as create_embeddings

    embeddings = create_embeddings(settings)
    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        collection=settings.qdrant_collection,
        vector_dim=settings.embedding_dimensions,
    )
    retriever = Retriever(embeddings=embeddings, vector_store=vector_store)
    chain_reader = AaveV3Reader(rpc_url=settings.arbitrum_rpc_url)

    config = AgentConfig(
        name="AaveAssist",
        protocol_name="Aave V3 on Arbitrum",
        system_instructions=(
            "You are a DeFi risk assistant specialising in Aave V3 on Arbitrum. "
            "Always cite exact USD amounts for positions. "
            "Warn clearly when health factor < 1.5. "
            "Use markdown for formatting."
        ),
    )
    agent = Agent(llm=llm, retriever=retriever, chain_reader=chain_reader, config=config)

    console.print()
    console.print(Panel(_BANNER, border_style="cyan", padding=(0, 2)))
    console.print(f"  Wallet: [dim]{wallet}[/dim]")
    console.print("  Network: [dim]Arbitrum mainnet (Aave V3)[/dim]\n")
    console.print("[dim]Suggested questions:[/dim]")
    for i, q in enumerate(_QUESTIONS, 1):
        console.print(f"  [dim]{i}.[/dim] {q}")
    console.print()

    async with chain_reader:
        while True:
            try:
                raw = Prompt.ask("[bold cyan]You[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                break
            user_input = raw.strip()
            if not user_input:
                continue
            if user_input.lower() in ("/quit", "/exit"):
                break
            if user_input.lower() == "/reset":
                agent.reset_memory()
                console.print("[dim]Memory cleared.[/dim]\n")
                continue

            console.print()
            console.print(Rule("[bold cyan]AaveAssist[/bold cyan]", style="cyan"))

            full: list[str] = []
            try:
                async for chunk in agent.stream_chat(user_input, wallet=wallet):
                    console.print(chunk, end="", highlight=False)
                    full.append(chunk)
            except Exception as exc:
                console.print(f"\n[red]Error:[/red] {exc}")
                continue

            console.print("\n")
            console.print(Markdown("".join(full)))
            console.print()

    console.print("\n[dim]Session ended.[/dim]\n")


@app.command()
def main(
    wallet: str = typer.Argument(..., help="EVM wallet address (0x...)"),
) -> None:
    """Chat with an AI assistant that reads your Aave V3 positions on Arbitrum."""
    asyncio.run(_run(wallet))


if __name__ == "__main__":
    app()
