#!/usr/bin/env python3
"""
Ingest Aave V3 + Arbitrum documentation into Qdrant.

Run this before starting the Arbitrum demo bot.

Usage::

    uv run python examples/arbitrum_aave_demo/ingest_aave_docs.py
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
app = typer.Typer(add_completion=False)

_AAVE_DOCS: list[tuple[str, str, str]] = [
    (
        "https://docs.aave.com/overview",
        "Aave Protocol Overview",
        """
# Aave Protocol — Complete Overview

Aave is a decentralized, open-source liquidity protocol on Arbitrum and other chains.
Users can supply assets to earn yield, borrow against collateral, or access flash loans.

## Core mechanics
- Supply: deposit assets -> receive aTokens -> earn supply APY automatically
- Borrow: lock collateral -> borrow up to LTV limit -> pay variable or stable APY
- Health Factor: (collateral x liq_threshold) / debt — must stay above 1.0

## Arbitrum deployment
Aave V3 on Arbitrum offers the same features with:
- Lower gas fees (Arbitrum L2 reduces costs 10-100x)
- Fast finality (~0.25s block time)
- Same security as Ethereum (fraud proofs)

Popular Arbitrum markets: WETH, USDC, USDT, WBTC, ARB, wstETH, DAI

## Interest rates
- Supply APY: earned by suppliers, paid by borrowers
- Variable borrow APY: fluctuates with utilization
- Stable borrow APY: fixed at borrowing time (higher, predictable)

Rates increase sharply above optimal utilization (typically 80%) to incentivize repayment.

## Risk management
Health factor below 1.0 triggers liquidation.
Liquidators repay up to 50% of debt and receive collateral + liquidation bonus (5-15%).
Always maintain health factor above 1.5 for safety.
""",
    ),
    (
        "https://docs.aave.com/arbitrum-specifics",
        "Aave on Arbitrum — Key Info",
        """
# Aave V3 on Arbitrum — Specific Information

## Contract addresses
- Pool: 0x794a61358D6845594F94dc1DB02A252b5b4814aD
- PoolAddressesProvider: 0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb
- AaveOracle: 0xb56c2F0B653B2e0b10C9b928C8580Ac5Df02C7C7
- UiPoolDataProvider: 0x5c5228aC8BC1528482514aF3e27E692495148717

## Supported assets and parameters
| Asset   | LTV  | Liq Threshold | Supply APY* | Borrow APY* |
|---------|------|---------------|-------------|-------------|
| WETH    | 80%  | 82.5%         | 1-3%        | 2-5%        |
| WBTC    | 73%  | 78%           | 0.5-2%      | 1-4%        |
| USDC    | 77%  | 80%           | 3-8%        | 4-10%       |
| USDT    | 76%  | 78%           | 3-8%        | 4-10%       |
| ARB     | 56%  | 61%           | 1-5%        | 2-8%        |
| wstETH  | 75%  | 78%           | 0.5-2%      | 1-3%        |
| DAI     | 75%  | 80%           | 3-7%        | 4-9%        |

*APYs are variable and change with utilization

## E-Mode on Arbitrum
Stablecoin E-Mode: USDC/USDT/DAI with 97% LTV vs each other
ETH E-Mode: stETH/wstETH with up to 90% LTV vs WETH

## Common strategies on Arbitrum Aave
1. Yield farming: supply stablecoins -> earn 5-10% APY
2. Leverage: supply ETH -> borrow USDC -> buy more ETH (loop)
3. Hedging: supply BTC -> borrow stablecoins -> hedge exposure
4. Flash loans: atomic arbitrage and liquidations in one transaction

## Monitoring your position
Use the health factor to gauge risk at all times.
The Mirael Agent monitors your health factor and sends alerts before liquidation.
""",
    ),
]


async def _run_ingest(collection: str) -> None:
    from mirael.config import load_settings
    from mirael.knowledge.embeddings import create_from_settings
    from mirael.knowledge.ingest import IngestPipeline, SemanticChunker
    from mirael.knowledge.models import Document
    from mirael.knowledge.vector_store import QdrantVectorStore
    from mirael.logging import configure_logging

    settings = load_settings()
    configure_logging(level="WARNING", environment=settings.environment)

    embeddings = create_from_settings(settings)
    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        collection=collection,
        vector_dim=settings.embedding_dimensions,
    )
    chunker = SemanticChunker(chunk_size=300, overlap=40)
    pipeline = IngestPipeline(
        chunker=chunker,
        embeddings=embeddings,
        vector_store=vector_store,
        batch_size=50,
    )

    documents = [Document(url=u, title=t, content=c.strip()) for u, t, c in _AAVE_DOCS]

    console.print(
        f"\n[bold]Ingesting {len(documents)} Aave docs into [cyan]{collection}[/cyan]...[/bold]"
    )

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Embedding and upserting...", total=None)
        total = await pipeline.ingest(documents)
        progress.update(task, completed=True)

    console.print(f"\n[bold green]Done.[/bold green] {total} chunks ingested.")


@app.command()
def main(
    collection: str = typer.Option("mirael_docs", "--collection", "-c"),
) -> None:
    """Ingest Aave V3 + Arbitrum documentation into Qdrant."""
    asyncio.run(_run_ingest(collection))


if __name__ == "__main__":
    app()
