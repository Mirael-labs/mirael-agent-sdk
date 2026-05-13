#!/usr/bin/env python3
"""
Hyperliquid Co-Pilot — interactive terminal REPL.

Combines live on-chain position data (read from Hyperliquid mainnet)
with Qdrant RAG retrieval over ingested documentation.

Usage::

    uv run python examples/hyperliquid_demo/chat.py --wallet 0xYOUR_ADDRESS

Commands inside the REPL:
  /reset  — clear conversation memory
  /quit   — exit
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

_BANNER = """[bold cyan]Hyperliquid Co-Pilot[/bold cyan]
AI assistant with live on-chain context and documentation RAG.

[dim]Commands: /reset · /quit · Ctrl-C to exit[/dim]"""

_SUGGESTED_QUESTIONS = [
    "Why am I paying funding on my positions?",
    "How close am I to liquidation?",
    "What is my free margin right now?",
    "Explain how cross-margin liquidation works.",
    "What are the maker/taker fees on Hyperliquid?",
]


async def _run_repl(wallet: str, collection: str) -> None:
    from mirael.agent.base import Agent
    from mirael.agent.models import AgentConfig
    from mirael.chains.hyperliquid import HyperliquidReader
    from mirael.config import load_settings
    from mirael.knowledge.retriever import Retriever
    from mirael.knowledge.vector_store import QdrantVectorStore
    from mirael.llm.anthropic import AnthropicLLM
    from mirael.logging import configure_logging

    settings = load_settings()
    configure_logging(level="WARNING", environment=settings.environment)

    # ── Build components ──────────────────────────────────────────────────────
    llm = AnthropicLLM(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
    )
    from mirael.knowledge.embeddings import create_from_settings as create_embeddings
    embeddings = create_embeddings(settings)
    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=(
            settings.qdrant_api_key.get_secret_value()
            if settings.qdrant_api_key
            else None
        ),
        collection=collection,
        vector_dim=settings.embedding_dimensions,
    )
    retriever = Retriever(embeddings=embeddings, vector_store=vector_store)
    chain_reader = HyperliquidReader(network=settings.hl_network)

    config = AgentConfig(
        name="HyperAssist",
        protocol_name="Hyperliquid",
        system_instructions=(
            "You are a precise, helpful trading assistant. "
            "Always cite specific numbers from the user's positions when available. "
            "When discussing funding rates, mention both the 1h rate and the "
            "annualised equivalent. Keep answers concise but complete. "
            "Use markdown formatting: bold for key numbers, headers for multi-part answers."
        ),
        max_rag_results=5,
        max_memory_turns=15,
    )

    agent = Agent(
        llm=llm,
        retriever=retriever,
        chain_reader=chain_reader,
        config=config,
    )

    # ── Welcome screen ────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(_BANNER, border_style="cyan", padding=(0, 2)))
    console.print(f"  Wallet: [dim]{wallet}[/dim]")
    console.print(f"  Network: [dim]{settings.hl_network}[/dim]")
    console.print()
    console.print("[dim]Suggested questions:[/dim]")
    for i, q in enumerate(_SUGGESTED_QUESTIONS, 1):
        console.print(f"  [dim]{i}.[/dim] {q}")
    console.print()

    # ── REPL loop ─────────────────────────────────────────────────────────────
    async with chain_reader:
        while True:
            try:
                raw = Prompt.ask("[bold cyan]You[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                break

            user_input = raw.strip()
            if not user_input:
                continue

            if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
                break

            if user_input.lower() == "/reset":
                agent.reset_memory()
                console.print("[dim]Conversation memory cleared.[/dim]\n")
                continue

            console.print()
            console.print(Rule("[bold cyan]HyperAssist[/bold cyan]", style="cyan"))

            full_response: list[str] = []
            try:
                async for chunk in agent.stream_chat(user_input, wallet=wallet):
                    console.print(chunk, end="", highlight=False)
                    full_response.append(chunk)
            except Exception as exc:
                console.print(
                    f"\n[bold red]Error:[/bold red] {exc}\n"
                    "[dim]Check your API keys and that Qdrant is running.[/dim]"
                )
                continue

            # Re-render as markdown for better formatting
            text = "".join(full_response)
            console.print("\n")
            console.print(Rule(style="dim"))
            console.print(Markdown(text))
            console.print()

    console.print("\n[dim]Session ended. Goodbye.[/dim]\n")


@app.command()
def main(
    wallet: str = typer.Argument(..., help="Hyperliquid wallet address (0x...)"),
    collection: str = typer.Option(
        "mirael_docs",
        "--collection",
        "-c",
        help="Qdrant collection to use for RAG retrieval.",
    ),
) -> None:
    """Start an interactive Hyperliquid Co-Pilot chat session."""
    asyncio.run(_run_repl(wallet, collection))


if __name__ == "__main__":
    app()
