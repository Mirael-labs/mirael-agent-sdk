# Mirael Agent SDK — Arbitrum Buildathon Submission

**Category:** AI Agentic  
**Repo:** https://github.com/Mirael-labs/mirael-agent-sdk  
**Builder:** Mael De La Hoz · Mirael Labs · Bucaramanga, Colombia

---

## The Problem

DeFi protocols on Arbitrum have a support crisis that scales with their success.
A protocol with 100K Discord members faces 300-500 repetitive questions every
day:

- *"Why is my health factor dropping on Aave?"*
- *"Why am I paying so much funding on Hyperliquid?"*
- *"What's my liquidation price?"*

Manual support teams burn $5,000-15,000/month on repetitive tickets. Generic AI
chatbots fail because they can't see the user's actual wallet. The user wants to
know about **their** positions — not a textbook explanation.

---

## The Solution

**Mirael Agent SDK** — an open-source Python SDK that deploys a 24/7 AI support
agent for any DeFi protocol in hours. The agent does two things no generic
chatbot can do:

**1. Reads the protocol's documentation via RAG**  
Ingests the protocol's docs, whitepapers, and guides into a vector store
(Qdrant). Answers are grounded in real documentation — zero hallucinations.

**2. Reads the user's real on-chain positions**  
Connects to Arbitrum (Aave V3) and Hyperliquid L1 to fetch live positions,
health factor, funding rates, and liquidation prices — personalized to the
user's actual wallet.

The result: when a user asks *"am I at risk of liquidation?"*, the agent
responds with their actual numbers, not generic advice.

> *"Your health factor is 1.42. WETH collateral at $8,200, USDC debt at $4,100.  
> If ETH drops 22% you'll hit liquidation. Reduce USDC debt by ~$800  
> to reach a safe 1.7 health factor."*

---

## Arbitrum Integration

The `AaveV3Reader` reads directly from **Aave V3 on Arbitrum mainnet**:

```python
# Pool: 0x794a61358D6845594F94dc1DB02A252b5b4814aD (Arbitrum)
async with AaveV3Reader() as reader:
    balance = await reader.get_user_balance("0xWALLET")
    # → health_factor: 1.42, collateral: $8,200, debt: $4,100

    positions = await reader.get_user_positions("0xWALLET")
    # → [{"asset": "WETH", "type": "supply", "balance_usd": 8200, "apy": 0.024}]

    market = await reader.get_market_info("USDC")
    # → variable_borrow_apy: 8.3%, utilization: 0.84
```

The `/monitor` command starts proactive monitoring — the bot DMs the user
**before** liquidation, not after:

```
/monitor 0xYOUR_WALLET

→ Bot: ⚠️ Warning: Your health factor dropped to 1.38.
        WETH price fell 8%. Consider adding $600 USDC collateral.
```

**Arbitrum roadmap:**  
Aave V3 is live today. GMX and Vertex readers are next — the `OnchainReader`
Protocol makes each new integration a 2-4 hour implementation.

---

## Technical Stack

| Layer | Technology |
|---|---|
| LLM | `claude-sonnet-4-5` with prompt caching (~60% cost reduction) |
| Embeddings | `BAAI/bge-large-en-v1.5` — local, free, no API key |
| Vector store | Qdrant Cloud (free tier sufficient) |
| Chains | Hyperliquid L1 + Arbitrum (Aave V3) |
| Channels | Discord (slash commands) + Telegram |
| Only required API key | Anthropic |

---

## Business Model

**Phase 1 — Services (now → Q3 2026)**

| | Price |
|---|---|
| Setup & integration | $10,000 - $15,000 one-time |
| Monthly retainer | $2,000 - $3,000/month |

The setup covers: doc ingestion, agent configuration, Discord/Telegram deploy,
testing, and team handoff. Unit economics: ~90% gross margin.

**Target: 3 clients by September → $7,500 MRR**

**Phase 2 — SaaS (Q4 2026)**

Self-serve tiers: $299/mo (Starter) → $799/mo (Growth) → $1,999/mo (Scale).

**Projected MRR trajectory:**
- Sep 2026: $7,500 (3 services clients)
- Dec 2026: $15,000 (5 services + early SaaS)
- Jun 2027: $42,500 (5 services + 50 SaaS)

**ICP:** DeFi protocols on Arbitrum + Hyperliquid, 10-50 person teams, 100K+
users, $5K-15K/month budget for community tooling.

---

## Why This Wins

**The moat is on-chain context.** Any team can build a chatbot with Claude.
Nobody else has the full pipeline: RAG + live wallet data + multi-chain readers
+ Discord/Telegram + proactive alerts — all in one open-source SDK that deploys
in hours.

**The market is validated.** Aave, GMX, Hyperliquid, and 200+ protocols on
Arbitrum pay $5K-15K/month for human support teams. Mirael replaces 70-80% of
that workload at 10% of the cost.

**LATAM angle.** Mirael Labs is based in Bucaramanga, Colombia — first
DeFi AI tooling company targeting the Spanish-speaking crypto market (Colombia,
Mexico, Argentina, Ecuador = millions of DeFi users underserved by English-only
tools).

---

## Grant Usage ($20K)

| Allocation | Amount |
|---|---|
| Infrastructure (3 months: Anthropic API + Qdrant + VPS) | $2,000 |
| Go-to-market: outreach to 50 Arbitrum protocols | $1,000 |
| Travel: ETH México + LABITCONF Argentina | $3,000 |
| Development: GMX + Vertex readers for Arbitrum | $4,000 |
| Analytics dashboard (unlocks SaaS Growth tier) | $5,000 |
| Founder runway (3 months to close first clients) | $5,000 |

**Expected outcome:** 3 paying clients + GMX/Vertex live + SaaS beta by end of
grant period.

---

## Traction & Quality

- **193 unit tests** · **19 E2E tests** against real Anthropic API
- **17 integration tests** against Qdrant Cloud + Hyperliquid mainnet
- mypy strict · ruff 0 violations · bandit 0 security issues
- Discord bot live: `Mirael Agent#9925`
- GitHub: https://github.com/Mirael-labs/mirael-agent-sdk

---

## Quick Start

```bash
git clone https://github.com/Mirael-labs/mirael-agent-sdk
uv sync --all-extras
cp .env.example .env  # set MIRAEL_ANTHROPIC_API_KEY
uv run python examples/hyperliquid_demo/ingest_docs.py
uv run python examples/discord_demo/bot.py
# → /ask why is my health factor dropping?
```

---

*Mirael Labs · Bucaramanga, Colombia · github.com/Mirael-labs*
