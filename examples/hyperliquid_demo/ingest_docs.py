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
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/perpetuals-101",
        "Perpetual Futures 101",
        """
# Perpetual Futures on Hyperliquid

## What are perpetual futures?
Perpetual futures (perps) are derivative contracts that let you speculate on asset
prices with leverage without an expiry date. Unlike traditional futures, perps never
settle — you hold them as long as you want and pay/receive funding.

## Key concepts

### Mark price vs index price
- **Mark price**: the fair value used for liquidations and PnL calculation.
  Derived from the order book mid price with a dampening mechanism.
- **Index price** (oracle): the spot price from external price feeds.
  Used to anchor the perpetual to reality via funding.
- **Premium**: mark price minus index price. Positive = perp is expensive vs spot.

### Leverage
Leverage amplifies both gains and losses:
```
position_notional = size x mark_price
initial_margin    = position_notional / leverage
```
A 10x leveraged $10,000 position requires $1,000 margin.

### PnL calculation
For a long position:
```
unrealized_pnl = size x (mark_price - entry_price)
```
For a short position:
```
unrealized_pnl = size x (entry_price - mark_price)
```

### Cross vs isolated margin
- **Cross**: all account equity backs all positions. More efficient, higher risk.
- **Isolated**: fixed margin per position. Losses capped at allocated amount.

## Hyperliquid-specific features
- Sub-second finality on all trades
- No gas fees on orders
- On-chain order book — every trade is verifiable
- USDC settlement — all profits and losses in USDC
- Up to 50x leverage on BTC and ETH
""",
    ),
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/portfolio-management",
        "Portfolio and Risk Management",
        """
# Portfolio and Risk Management on Hyperliquid

## Account value
Your total equity including unrealized PnL from all positions.
```
account_value = USDC_balance + sum(unrealized_pnl for all positions)
```

## Free margin
Capital available to open new positions or withdraw:
```
free_margin = account_value - total_margin_used
```
When free_margin < 0, you cannot open new positions.

## Portfolio margin utilization
```
margin_utilization = total_margin_used / account_value
```
Exceeding 80% is risky — any adverse price movement could trigger liquidation.

## Risk management best practices
1. Never use more than 5-10x leverage on volatile assets
2. Keep margin utilization below 50% to absorb volatility
3. Monitor funding rates — high positive funding erodes long positions daily
4. Set stop-losses on all positions
5. Diversify across multiple assets to reduce correlated liquidation risk

## Correlation risk
If BTC and ETH both drop simultaneously, cross-margin accounts face compounding losses.
Consider position sizing to account for correlation between assets.

## Position sizing formula
A conservative position size based on risk per trade:
```
risk_per_trade = account_value x risk_pct  # e.g. 1-2%
position_size  = risk_per_trade / abs(entry_price - stop_loss_price)
```
""",
    ),
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/architecture/hype",
        "HYPE Token and HLP",
        """
# HYPE Token and Hyperliquid Ecosystem

## HYPE token
HYPE is the native token of the Hyperliquid L1 blockchain.

### Use cases
- Staking for validator participation in consensus (HyperBFT)
- Fee discounts on trading
- Governance (planned)
- Collateral for certain protocol features

## HLP — Hyperliquid Liquidity Provider
HLP is a protocol-owned vault that acts as the market maker on Hyperliquid.

### How it works
- HLP takes the other side of trades when no other liquidity exists
- It earns spread from market making and a portion of trading fees
- Users can deposit USDC into HLP to earn yield

### HLP yield
Yield comes from:
1. Trading fees (maker rebates)
2. Funding payments received when HLP holds short positions during bull markets
3. Spread income from market making

### Risks of HLP
- HLP can lose money if large price moves occur against its positions
- Returns are variable and can be negative in volatile markets
- No guaranteed yield — it depends on market conditions

## Vaults
Beyond HLP, any user can create a vault — a shared trading account where
followers can copy trades by depositing funds. Vault leaders earn a
performance fee (typically 10% of profits).
""",
    ),
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/api-trading",
        "API Trading and Bots",
        """
# API Trading on Hyperliquid

## Authentication
Hyperliquid uses wallet-based authentication. Your Ethereum private key signs
all trade orders. No API key/secret required — just a wallet.

## Key API endpoints
All requests go to: https://api.hyperliquid.xyz

### Info endpoint (read-only, no auth needed)
POST /info

Request types:
- clearinghouseState: get user positions and margin summary
- openOrders: get user's open orders
- userFills: get trade history
- allMids: get all mid prices
- metaAndAssetCtxs: get all market data including funding rates
- fundingHistory: get historical funding rate for an asset

### Exchange endpoint (write, requires signature)
POST /exchange

Actions: place orders, cancel orders, modify orders, transfer funds

## Rate limits
- Info endpoints: 1200 requests/minute per IP
- Exchange endpoints: 600 requests/minute per wallet

## WebSocket
Real-time data via WSS: wss://api.hyperliquid.xyz/ws

Subscription types:
- allMids: all mid prices (every ~0.5s)
- userEvents: fills, orders, liquidations for your wallet
- orderUpdates: order book changes
- activeAssetData: per-asset data for a user

## Common trading patterns

### Place a limit order
```python
from hyperliquid.exchange import Exchange
exchange = Exchange(wallet, base_url)
exchange.order("BTC", True, 0.1, 65000, {"limit": {"tif": "Gtc"}})
```

### Check positions
```python
from hyperliquid.info import Info
info = Info(base_url)
state = info.user_state(wallet_address)
positions = state["assetPositions"]
```
""",
    ),
    (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations-deep-dive",
        "Liquidation Deep Dive",
        """
# Liquidation Mechanics — Deep Dive

## When does liquidation happen?
Liquidation triggers when your account equity falls below the
**maintenance margin** requirement across all positions.

For cross-margin accounts:
```
maintenance_margin = sum(position_notional x maintenance_margin_rate)
liquidation_trigger = account_equity < maintenance_margin
```

Maintenance margin rates by leverage:
- 1-3x: 1% of notional
- 3-5x: 2% of notional
- 5-10x: 2.5% of notional
- 10-20x: 3% of notional
- 20-50x: 5% of notional

## Liquidation price formula
For a long position with cross margin:

```
liq_price ~= entry_price x (1 - (equity/notional) + maintenance_rate)
```

For a short position:
```
liq_price ~= entry_price x (1 + (equity/notional) - maintenance_rate)
```

## What happens during liquidation
1. Hyperliquid's liquidation engine takes over the position
2. The engine closes as much as needed to restore margin above maintenance
3. Any remaining equity is returned to the user
4. A liquidation fee (~0.05% of notional) is deducted

## Partial liquidation
Hyperliquid uses partial liquidation to preserve as much of the account as possible.
Only the minimum amount is liquidated to bring the account back to a safe margin level.

## Bankruptcy price
If the mark price moves beyond the liquidation price before the engine can act,
the position reaches bankruptcy. The insurance fund covers losses in this case.
HLP and the insurance fund protect the protocol from bad debt.

## How to avoid liquidation
1. Use the health factor indicator — stay above 1.5 health factor
2. Add margin before it becomes critical
3. Reduce position size (partial close)
4. Place a stop-loss order to auto-close before liquidation
5. Monitor funding — it erodes equity continuously

## Warning signs
- Health factor below 2.0: watch closely
- Health factor below 1.5: consider reducing exposure
- Health factor below 1.2: urgent action needed
- Health factor below 1.0: liquidation imminent
""",
    ),
    (
        "https://docs.aave.com/developers/getting-started/readme",
        "Aave V3 Overview",
        """
# Aave V3 Protocol Overview

## What is Aave?
Aave is a decentralized lending protocol where users can:
- **Supply** assets to earn interest (supply APY)
- **Borrow** assets by posting collateral (borrow APY)
- **Flash loan** assets with zero collateral (single-transaction)

Aave V3 is deployed on Arbitrum, Ethereum, Optimism, Polygon, and more.

## Key concepts

### Supply (deposit)
When you supply assets, you receive aTokens (e.g. supply USDC -> receive aUSDC).
aTokens automatically accrue interest — your balance increases every block.

### Borrow
You can borrow up to your **borrowing power** (based on collateral LTV).
Two borrow modes:
- **Variable rate**: fluctuates with market demand (most common)
- **Stable rate**: locked rate at time of borrow (higher, but predictable)

### Health Factor
The health factor represents the safety of your loan:
```
health_factor = (collateral_value x liquidation_threshold) / total_debt_value
```
- **> 1.0**: account is safe
- **< 1.0**: account can be liquidated
- **< 1.5**: getting risky — reduce exposure
- **~1.0**: liquidation imminent

### LTV (Loan-to-Value)
The maximum amount you can borrow against your collateral:
```
max_borrow_usd = collateral_usd x LTV
```
Example: WETH has 80% LTV — $10,000 WETH lets you borrow up to $8,000.

### Liquidation threshold
Higher than LTV — the point at which liquidation can begin:
- WETH: LTV 80%, Liquidation threshold 82.5%
- USDC: LTV 77%, Liquidation threshold 80%
- ARB: LTV 56%, Liquidation threshold 61%

## Aave V3 on Arbitrum
Contract addresses (Arbitrum mainnet):
- Pool: 0x794a61358D6845594F94dc1DB02A252b5b4814aD
- Pool Addresses Provider: 0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb

Popular markets on Arbitrum: WETH, WBTC, USDC, USDT, ARB, DAI, wstETH
""",
    ),
    (
        "https://docs.aave.com/risk/asset-risk/risk-parameters",
        "Aave Risk Parameters",
        """
# Aave V3 Risk Parameters — Arbitrum

## Supply and borrow caps
Each asset has supply and borrow caps to limit protocol exposure:
- Supply cap: max total amount that can be supplied
- Borrow cap: max total amount that can be borrowed
Caps prevent over-concentration in any single asset.

## Interest rate model
Aave uses a kinked interest rate model:
- Below optimal utilization: low, stable rates
- Above optimal utilization: rates increase sharply to rebalance supply/demand

Utilization rate = total_borrowed / total_supplied

At 100% utilization, borrow rates can reach 100%+ APY.

## Reserve factor
A percentage of interest paid by borrowers goes to the Aave treasury:
- Typically 10-20% depending on the asset
- The rest goes to suppliers as yield

## E-Mode (Efficiency Mode)
E-Mode allows higher LTVs for correlated assets (e.g. ETH and stETH):
- Stablecoin E-Mode: USDC/USDT/DAI can reach 97% LTV vs each other
- ETH E-Mode: stETH/rETH can reach 90% LTV vs WETH

## Isolation mode
New or riskier assets may launch in isolation mode:
- Can only be used as collateral for stablecoins
- Debt ceiling limits total borrowing against isolated assets

## How to minimize liquidation risk on Aave
1. Maintain health factor above 1.5 at all times
2. Use stable borrow rates for long-term positions
3. Watch oracle prices — liquidations use oracle, not market prices
4. Borrow stablecoins against volatile collateral carefully
5. Set up monitoring alerts (this is what Mirael Agent does for you)
""",
    ),
    (
        "https://gmx-docs.io/docs/trading/v2/overview",
        "GMX V2 Trading Overview",
        """
# GMX V2 — Perpetual Trading on Arbitrum

## What is GMX?
GMX is a decentralized perpetual exchange on Arbitrum (and Avalanche).
GMX V2 introduced isolated markets, improved capital efficiency, and
a new price impact mechanism.

## Key concepts

### Markets
Each GMX V2 market has a long token, short token, and index token.
Example: BTC/USD market uses WBTC (long), USDC (short), and BTC index price.
Markets are isolated — losses in one don't affect others.

### Leverage
GMX V2 supports up to 100× leverage on major pairs (BTC, ETH).
Most traders use 2-10× for safer risk management.

### Funding & Borrowing fees
GMX V2 uses **borrowing fees** (not traditional funding):
- Paid by position holders to liquidity providers (GLV/GM pool)
- Calculated per hour based on pool utilization
- Formula: `hourly_rate = (reserved_usd / pool_value) × factor`
- Higher utilization = higher borrowing cost

### Price impact
Large trades move the price against the trader:
- Reduces spread when balancing long/short OI
- Increases spread when imbalancing the market

### Liquidation
Position is liquidated when:
```
remaining_collateral < maintenance_margin
maintenance_margin = position_size × maintenance_margin_factor
```
Liquidation keeper closes the position, returns remaining collateral minus fees.

## GLV and GM liquidity pools
- **GM pools**: single-market liquidity (e.g. BTC-USDC GM)
- **GLV vaults**: diversified across multiple GM pools
- LPs earn borrowing fees + price impact fees
- LPs risk: losses when traders profit ("delta exposure")

## Key Arbitrum contracts
- DataStore: 0xFD70de6b91282D8017aA4E741e9Ae325CAb992d
- ExchangeRouter: 0x7452c558d45f8afC8c83dAe62C3f8A5BE19c71f
- Reader: 0xf60becbba223EEA9495Da3f606753867eC10d139
""",
    ),
    (
        "https://gmx-docs.io/docs/trading/v2/risk-management",
        "GMX V2 Risk Management",
        """
# GMX V2 Risk Management

## Health factor equivalent
GMX V2 does not use a single health factor like Aave.
Instead, monitor:
- **Collateral ratio** = collateral_usd / position_size_usd
- Liquidation triggers when collateral covers < maintenance margin

## Safe leverage guidelines
| Leverage | Risk Level | Notes |
|----------|-----------|-------|
| 1-3x | Low | Safe for volatile assets |
| 3-10x | Medium | Watch borrowing fees daily |
| 10-50x | High | Requires active monitoring |
| 50-100x | Extreme | High liquidation risk |

## Borrowing fee estimation
Daily borrowing cost ≈ position_size × hourly_rate × 24

Example: $10,000 position at 0.01%/hr = $24/day

## How to reduce liquidation risk
1. Add collateral before reaching maintenance margin
2. Reduce position size (partial close)
3. Monitor open interest imbalance — higher OI on your side = higher fees
4. Use stop-loss orders to auto-close before liquidation

## Key difference from Aave
- Aave: health factor across all positions
- GMX V2: each position is isolated, independent liquidation threshold
""",
    ),
    (
        "https://vertex-protocol.gitbook.io/docs/getting-started/overview",
        "Vertex Protocol Overview",
        """
# Vertex Protocol — Arbitrum DEX

## What is Vertex?
Vertex is a DEX on Arbitrum combining spot trading, perpetual futures,
and money market in one unified interface. It uses a hybrid architecture:
off-chain order matching + on-chain settlement.

## Products
- **Spot**: trade tokens at spot prices with limit/market orders
- **Perps**: perpetual futures with up to 20x leverage
- **Money market**: earn yield by supplying assets, borrow against collateral

## Unified margin account
All positions share a single cross-margin account:
- Spot holdings count as collateral for perp positions
- More capital efficient than isolated systems
- One health factor across all products

## Sequencer + on-chain settlement
- Orders matched off-chain by the Vertex sequencer (fast, low latency)
- Settlement and custody always on-chain (Arbitrum)
- Cannot be frontrun or censored at settlement level

## Key risk metrics
- **Health score**: weighted sum of all positions and collateral
- **Initial margin**: required to open a position
- **Maintenance margin**: below this triggers liquidation
- **Max leverage**: up to 20x on major pairs

## Arbitrum native
Vertex was built natively on Arbitrum:
- Benefits from Arbitrum's low fees and fast finality
- Integrates with Arbitrum native tokens (ARB, USDC, WETH, WBTC)
- Part of the Arbitrum DeFi ecosystem alongside Aave, GMX, Camelot
""",
    ),
    (
        "https://docs.arbitrum.io/for-users/getting-started",
        "Arbitrum DeFi Ecosystem",
        """
# Arbitrum DeFi Ecosystem Overview

## What is Arbitrum?
Arbitrum is an Ethereum Layer 2 using Optimistic Rollup technology.
It offers 10-100x lower gas costs than Ethereum mainnet with
~0.25 second block times and Ethereum-grade security.

## Key DeFi protocols on Arbitrum

### Lending
- **Aave V3**: largest lending protocol, supports WETH/USDC/WBTC/ARB/wstETH
- **Radiant**: cross-chain lending with Arbitrum focus

### Perpetual DEX
- **GMX V2**: largest perp DEX on Arbitrum, isolated markets, up to 100x
- **Vertex**: unified spot+perps+money market, up to 20x
- **Gains Network**: synthetic perps, up to 150x leverage (high risk)
- **Hyperliquid**: separate L1 (not Arbitrum) but closely related ecosystem

### DEX / Liquidity
- **Camelot**: native Arbitrum DEX with V3-style concentrated liquidity
- **Uniswap V3**: largest DEX, deep WETH/USDC liquidity

### Yield
- **Pendle**: yield tokenization — split any yield-bearing asset into PT+YT
- **Convex on Arbitrum**: boosted Curve yields

## ARB token
- Native governance token of Arbitrum
- Used for voting in Arbitrum DAO
- Airdropped to early users in March 2023
- Available as collateral on Aave V3 Arbitrum (56% LTV)

## Gas costs on Arbitrum
- Typical transaction: $0.01-0.10
- Complex DeFi interaction: $0.10-1.00
- vs Ethereum mainnet: 10-100x cheaper

## Bridging assets to Arbitrum
- **Official bridge**: bridge.arbitrum.io (slow, ~7 days withdrawal)
- **Fast bridges**: Stargate, Hop, Across (minutes, small fee)
""",
    ),
]

_GITHUB_SOURCES: list[tuple[str, str]] = [
    (
        "https://raw.githubusercontent.com/hyperliquid-dex/hyperliquid-python-sdk/master/README.md",
        "Hyperliquid Python SDK",
    ),
    (
        "https://raw.githubusercontent.com/hyperliquid-dex/hyperliquid-python-sdk/master/hyperliquid/info.py",
        "Hyperliquid Info API",
    ),
    (
        "https://raw.githubusercontent.com/hyperliquid-dex/hyperliquid-python-sdk/master/hyperliquid/exchange.py",
        "Hyperliquid Exchange API",
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
        api_key=(settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None),
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
                    documents.append(Document(url=url, title=title, content=resp.text))
                    console.print(f"  [green]✓[/green] Fetched: {title}")
                else:
                    console.print(f"  [yellow]⚠[/yellow] Skipped {title} (HTTP {resp.status_code})")
            except Exception as exc:
                console.print(f"  [yellow]⚠[/yellow] Skipped {title}: {exc}")

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
