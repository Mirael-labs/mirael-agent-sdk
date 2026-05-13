"""CLI entrypoint — ``mirael`` command."""

from __future__ import annotations

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
    source: str = typer.Argument(..., help="URL or local path to ingest"),
    collection: str = typer.Option("mirael_docs", help="Qdrant collection name"),
) -> None:
    """Ingest documents into the vector store."""
    # TODO(phase-2): implement
    typer.echo(f"[stub] Would ingest {source!r} into collection {collection!r}")


@app.command()
def chat(
    wallet: str = typer.Option(..., help="Hyperliquid wallet address"),
) -> None:
    """Start an interactive chat session with the agent."""
    # TODO(phase-5): implement
    typer.echo(f"[stub] Would start chat for wallet {wallet!r}")


if __name__ == "__main__":
    app()
