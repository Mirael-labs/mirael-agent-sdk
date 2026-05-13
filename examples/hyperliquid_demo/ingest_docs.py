#!/usr/bin/env python3
"""
Ingest Hyperliquid documentation into Qdrant.

Combines embedded core-concept documents (always available) with
live GitHub sources (fetched if reachable).  Safe to re-run: existing
chunks are overwritten via Qdrant upsert.

Usage::

    uv run python examples/hyperliquid_demo/ingest_docs.py [--collection NAME]
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
app = typer.Typer(add_completion=False)

# ── Embedded documentation ────────────────────────────────────────────────────
# Curated excerpts so the demo works without any external network access
# beyond Qdrant + OpenAI (for embeddings).

_EMBEDDED_DOCS: list[tuple[str, str, str]] = [
    # (url, title, content)
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding",
        "Funding Rates",
        """
# Funding Rates on Hyperliquid

## What is funding?
Funding is a periodic payment exchanged between long and short positions in
perpetual futures.  It keeps the perpetual price (mark price) anchored to the
spot price (oracle price).

## Direction
- **Positive funding rate**: Longs pay shorts. This happens when the perpetual
  trades above the oracle — bulls are willing to pay a premium.
- **Negative funding rate**: Shorts pay longs. The perpetual trades below oracle.

## Frequency
Hyperliquid settles funding every **1 hour** (3 times per day by convention used
in annualisation).  A position open for 24 hours experiences 24 funding payments.

## Formula
```
funding_payment = position_notional × funding_rate
position_notional = abs(position_size) × mark_price
```

## Cost estimation
To estimate your daily funding cost:
```
daily_cost_usd = abs(size) × mark_price × funding_rate × 24
```

## Why funding matters
A 0.01% hourly rate annualises to ~87.6%.  Holding large leveraged longs through
a high-funding environment can erode profits quickly even if the price moves in
your favour.

## Impact on health factor
The Mirael Co-Pilot's health factor calculation penalises positions where the
estimated 24h funding burn exceeds $100.
""",
    ),
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations",
        "Liquidation Mechanics",
        """
# Liquidation Mechanics

## Overview
When your account's equity falls below the **maintenance margin** requirement,
the system liquidates your positions to protect the protocol.

## Liquidation price
The liquidation price is the mark price at which your position would be
forcibly closed.  For a long position:
```
liquidation_price ≈ entry_price × (1 - 1/leverage + maintenance_margin_rate)
```

## Health factor
Mirael computes a health factor from 0–100 for each position:
- **>60** — healthy, no action needed
- **30–60** — watch closely
- **<20** — critical, consider reducing exposure

The factor is penalised when:
- Liquidation distance < 20% of current mark price (–20 pts)
- Liquidation distance < 10% (–40 pts instead)
- Margin utilisation > 80% (–20 pts)
- 24h funding burn > $100 (–10 pts)

## Partial liquidation
Hyperliquid uses partial liquidation where possible to preserve the account.
Only enough of the position is closed to bring the account back above maintenance.

## Cross vs Isolated margin
- **Cross margin**: all available balance backs all positions.  Higher
  risk of full liquidation but more efficient capital use.
- **Isolated margin**: a fixed USD amount is allocated to a position.
  Losses are capped at the isolated margin; the rest of the account is safe.
""",
    ),
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/overview/what-is-hyperliquid",
        "What is Hyperliquid",
        """
# What is Hyperliquid?

Hyperliquid is a high-performance Layer 1 blockchain purpose-built for trading.
It runs its own order-book-based perpetual futures exchange natively on-chain.

## Key characteristics
- **On-chain order book**: every order, cancellation, and trade is a blockchain
  transaction — fully transparent and verifiable.
- **Sub-second finality**: the custom consensus layer (HyperBFT) achieves
  ~0.2s block times and ~0.9s finality.
- **USDC settlement**: all positions and PnL are denominated in USDC.
- **No gas fees**: trading is free; the protocol captures value through fees
  on notional volume.

## Supported assets
Hyperliquid offers 100+ perpetual pairs including BTC, ETH, SOL, ARB, AVAX,
and many others with up to 50× leverage depending on the asset.

## HLP (Hyperliquid Liquidity Provider)
HLP is a protocol-owned vault that market-makes on Hyperliquid.  Users can
deposit into HLP to earn a share of the trading fees.

## Account model
Each EVM-compatible wallet address has a single cross-margin account.
Isolated-margin positions are tracked separately per asset.
""",
    ),
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margin",
        "Margin and Leverage",
        """
# Margin and Leverage

## Initial vs Maintenance Margin
- **Initial margin** = position_notional / leverage
  Required upfront to open a position.
- **Maintenance margin** = a smaller fraction of notional
  Below this, liquidation is triggered.

## Leverage limits
Maximum leverage varies by asset:
- BTC, ETH: up to 50×
- Most altcoins: 20× or less
- Smaller assets may be limited to 5–10×

## Cross margin account
The default mode.  All your USDC balance backs all your positions.
Example: $10,000 balance, two positions using $2,000 margin each.
If one position loses $6,000 (exceeding its $2,000 initial), the other
position's margin cushions it — until total equity hits maintenance.

## Isolated margin
You allocate a specific USDC amount to a position.  Maximum loss = allocated
amount.  This is safer for high-risk speculative trades.

## Margin utilisation
```
margin_utilisation = total_margin_used / account_equity
```
Above 80% utilisation, the health factor is penalised.

## Free margin
The amount available to open new positions or withdraw:
```
free_margin = account_value - total_margin_used
```
""",
    ),
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/order-types",
        "Order Types",
        """
# Order Types on Hyperliquid

## Limit orders
Execute only at the specified price or better.
- **Good-til-cancelled (GTC)**: stays in the book until filled or cancelled.
- **Post-only**: only accepted if it rests in the book (never takes liquidity).
- **Immediate-or-cancel (IOC)**: fills immediately at the price or better,
  cancels any unfilled portion.

## Market orders
Execute immediately at the best available price.  May incur slippage in
low-liquidity conditions.

## Stop orders
- **Stop market**: triggers a market order when the mark price reaches the stop.
- **Stop limit**: triggers a limit order when the mark price reaches the stop.
- **Take profit**: mirrors stop orders but for profit-taking.

## Reduce-only
Any order marked reduce-only will only decrease an existing position.
It is automatically cancelled if no matching position exists.

## TP/SL on positions
Hyperliquid supports attaching take-profit and stop-loss directly to a position
entry rather than managing them as separate orders.
""",
    ),
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees",
        "Trading Fees",
        """
# Trading Fees

## Maker / Taker model
Hyperliquid uses a maker-taker fee structure:
- **Maker** (adds liquidity via resting limit orders): lower fee, typically
  0.01% of notional or even rebates at high volumes.
- **Taker** (removes liquidity via market or aggressive limit orders):
  typically 0.035–0.05% of notional.

## Fee tiers
Volume-based tiers reduce fees for active traders.  Tiers reset monthly based
on the prior 30-day notional volume.

## Where fees go
A portion of fees goes to HLP vault participants; the remainder is protocol
revenue.

## Impact on PnL
For a $100,000 notional trade at 0.035% taker fee:
```
fee = $100,000 × 0.00035 = $35
```
High-frequency traders must factor fees into their strategy edge.
""",
    ),
]

_GITHUB_SOURCES: list[tuple[str, str]] = [
    (
        "https://raw.githubusercontent.com/hyperliquid-dex/hyperliquid-python-sdk/master/README.md",
        "Hyperliquid Python SDK",
    ),
]


# ── Main ingestion logic ───────────────────────────────────────────────────────


async def _run_ingest(collection: str) -> None:
    from mirael.config import load_settings
    from mirael.knowledge.ingest import IngestPipeline, SemanticChunker
    from mirael.knowledge.models import Document
    from mirael.knowledge.vector_store import QdrantVectorStore
    from mirael.logging import configure_logging

    settings = load_settings()
    configure_logging(level="WARNING", environment=settings.environment)

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
    chunker = SemanticChunker(chunk_size=400, overlap=50)
    pipeline = IngestPipeline(
        chunker=chunker,
        embeddings=embeddings,
        vector_store=vector_store,
        batch_size=50,
    )

    documents: list[Document] = []

    # 1. Embedded docs (always available)
    for url, title, content in _EMBEDDED_DOCS:
        documents.append(Document(url=url, title=title, content=content.strip()))

    # 2. Live GitHub sources (best-effort)
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as http:
        for url, title in _GITHUB_SOURCES:
            try:
                resp = await http.get(url)
                if resp.status_code == 200:
                    documents.append(
                        Document(url=url, title=title, content=resp.text)
                    )
                    console.print(f"  [green]✓[/green] Fetched: {title}")
                else:
                    console.print(
                        f"  [yellow]⚠[/yellow] Skipped {title} (HTTP {resp.status_code})"
                    )
            except Exception as exc:
                console.print(
                    f"  [yellow]⚠[/yellow] Skipped {title}: {exc}"
                )

    console.print(
        f"\n[bold]Ingesting {len(documents)} documents into "
        f"collection [cyan]{collection}[/cyan]...[/bold]"
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Embedding and upserting...", total=None)
        total_chunks = await pipeline.ingest(documents)
        progress.update(task, completed=True)

    console.print(
        f"\n[bold green]✓ Done.[/bold green] "
        f"Ingested [cyan]{total_chunks}[/cyan] chunks from "
        f"[cyan]{len(documents)}[/cyan] documents."
    )
    console.print(
        "\nRun the chat demo next:\n"
        "  [bold]uv run python examples/hyperliquid_demo/chat.py --wallet 0xYOUR_ADDRESS[/bold]"
    )


@app.command()
def main(
    collection: str = typer.Option(
        "mirael_docs",
        "--collection",
        "-c",
        help="Qdrant collection name to write into.",
    ),
) -> None:
    """Ingest Hyperliquid documentation into Qdrant for RAG retrieval."""
    asyncio.run(_run_ingest(collection))


if __name__ == "__main__":
    app()
