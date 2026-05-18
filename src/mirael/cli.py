"""CLI entrypoint — ``mirael`` command."""

from __future__ import annotations

import asyncio

import typer

app = typer.Typer(
    name="mirael",
    help="Mirael Agent SDK — deploy AI agents with on-chain context.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the SDK version."""
    from mirael import __version__

    typer.echo(f"mirael-agent-sdk v{__version__}")


@app.command()
def ingest(
    source: str = typer.Argument(
        ...,
        help="URL or local file path to ingest (markdown/text)",
    ),
    title: str = typer.Option("", "--title", "-t", help="Document title (optional)"),
    collection: str = typer.Option(
        "mirael_docs", "--collection", "-c", help="Qdrant collection name"
    ),
) -> None:
    """
    Ingest a document URL or file into the vector store.

    Examples:

      mirael ingest https://docs.yourprotocol.io/overview

      mirael ingest ./whitepaper.md --title "Protocol Whitepaper"
    """

    async def _run() -> None:
        import httpx
        from rich.console import Console
        from rich.progress import Progress, SpinnerColumn, TextColumn

        from mirael.config import load_settings
        from mirael.knowledge.embeddings import create_from_settings
        from mirael.knowledge.ingest import IngestPipeline, SemanticChunker
        from mirael.knowledge.models import Document
        from mirael.knowledge.vector_store import QdrantVectorStore
        from mirael.logging import configure_logging

        console = Console()
        settings = load_settings()
        configure_logging(level="WARNING", environment=settings.environment)

        # Fetch content
        if source.startswith("http"):
            console.print(f"Fetching [cyan]{source}[/cyan]...")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(source)
                resp.raise_for_status()
                content = resp.text
            doc_title = title or source.split("/")[-1] or "Document"
        else:
            from pathlib import Path

            path = Path(source)
            if not path.exists():
                console.print(f"[red]File not found:[/red] {source}")
                raise typer.Exit(1)
            content = path.read_text(encoding="utf-8")
            doc_title = title or path.stem

        doc = Document(url=source, title=doc_title, content=content)
        embeddings = create_from_settings(settings)
        store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            collection=collection,
            vector_dim=settings.embedding_dimensions,
        )
        chunker = SemanticChunker(chunk_size=300, overlap=40)
        pipeline = IngestPipeline(chunker=chunker, embeddings=embeddings, vector_store=store)

        col_desc = TextColumn("[progress.description]{task.description}")
        with Progress(SpinnerColumn(), col_desc, console=console) as p:
            task = p.add_task(f"Ingesting '{doc_title}'...", total=None)
            total = await pipeline.ingest([doc])
            p.update(task, description=f"Done — {total} chunks ingested", completed=True)

        console.print(
            f"\n[green]Done.[/green] '{doc_title}' → {total} chunks in '{collection}'"
        )

    asyncio.run(_run())


@app.command()
def chat(
    wallet: str = typer.Argument(
        "",
        help="Wallet address for on-chain context (optional)",
    ),
    collection: str = typer.Option(
        "mirael_docs", "--collection", "-c", help="Qdrant collection for RAG"
    ),
    protocol: str = typer.Option(
        "Hyperliquid", "--protocol", "-p", help="Protocol name shown in agent persona"
    ),
) -> None:
    """
    Start an interactive chat session with the Mirael Agent.

    The agent uses RAG over ingested docs and optionally reads
    on-chain positions for the provided wallet address.

    Examples:

      mirael chat

      mirael chat 0xYOUR_WALLET

      mirael chat 0xYOUR_WALLET --protocol "Aave"
    """

    async def _run() -> None:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.prompt import Prompt
        from rich.rule import Rule

        from mirael.agent.base import Agent
        from mirael.agent.models import AgentConfig
        from mirael.chains.hyperliquid import HyperliquidReader
        from mirael.config import load_settings
        from mirael.knowledge.embeddings import create_from_settings
        from mirael.knowledge.retriever import Retriever
        from mirael.knowledge.vector_store import QdrantVectorStore
        from mirael.llm.anthropic import AnthropicLLM
        from mirael.logging import configure_logging

        console = Console()
        settings = load_settings()
        configure_logging(level="WARNING", environment=settings.environment)

        # Build agent
        llm = AnthropicLLM(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
        )
        embeddings = create_from_settings(settings)
        store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            collection=collection,
            vector_dim=settings.embedding_dimensions,
        )
        retriever = Retriever(embeddings=embeddings, vector_store=store)
        chain_reader = HyperliquidReader(network=settings.hl_network)

        config = AgentConfig(
            name="Mirael",
            protocol_name=protocol,
            system_instructions=(
                "Keep answers precise and concise. "
                "Lead with numbers when you have wallet data. "
                "Use markdown formatting."
            ),
            max_rag_results=5,
        )
        agent = Agent(llm=llm, retriever=retriever, chain_reader=chain_reader, config=config)

        # Welcome
        console.print()
        wallet_display = (
            f"[dim]{wallet[:8]}...{wallet[-4:]}[/dim]" if wallet else "[dim]no wallet[/dim]"
        )
        console.print(Panel(
            f"[bold cyan]Mirael Agent[/bold cyan] · {protocol}\n"
            f"Wallet: {wallet_display} · Collection: [dim]{collection}[/dim]\n"
            "[dim]/reset to clear memory · /quit to exit[/dim]",
            border_style="cyan",
            padding=(0, 2),
        ))
        console.print()

        async with chain_reader:
            while True:
                try:
                    raw = Prompt.ask("[bold cyan]You[/bold cyan] [dim](/reset · /quit)[/dim]")
                except (KeyboardInterrupt, EOFError):
                    break

                user_input = raw.strip()
                if not user_input:
                    continue
                if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
                    break
                if user_input.lower() == "/reset":
                    agent.reset_memory()
                    console.print("[dim]Memory cleared.[/dim]\n")
                    continue

                console.print()
                console.print(Rule("[bold cyan]Mirael[/bold cyan]", style="cyan"))

                full_response: list[str] = []
                try:
                    async for chunk in agent.stream_chat(
                        user_input,
                        wallet=wallet if wallet else None,
                    ):
                        console.print(chunk, end="", highlight=False)
                        full_response.append(chunk)
                except Exception as exc:
                    err_type = type(exc).__name__
                    console.print(f"\n[red]{err_type}:[/red] {exc}")
                    if "Connection" in err_type or "connect" in str(exc).lower():
                        console.print("[dim]  → Check that Qdrant is running[/dim]")
                    elif "Authentication" in err_type or "401" in str(exc):
                        console.print("[dim]  → Check MIRAEL_ANTHROPIC_API_KEY in .env[/dim]")
                    continue

                text = "".join(full_response)
                console.print("\n")
                console.print(Markdown(text))
                console.print()

        console.print("\n[dim]Session ended.[/dim]\n")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
