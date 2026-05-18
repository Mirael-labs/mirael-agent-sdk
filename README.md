# Mirael Agent SDK

[![CI](https://github.com/Mirael-labs/mirael-agent-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mirael-labs/mirael-agent-sdk/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**24/7 AI support agent for DeFi protocols — knows your docs, reads your users' wallets.**

Your community asks the same questions every day. Your team answers them manually.
Mirael deploys an AI agent in your Discord or Telegram in under an hour that answers
protocol questions and reads each user's real on-chain positions in real time.

> *"Why is my health factor dropping?"*
> Bot: **"Your WETH collateral is $8,200, USDC debt $4,100, health factor 1.42.
> If ETH drops 22% you hit liquidation. Reduce debt by ~$800 to reach safe 1.7."**

Unlike generic chatbots, Mirael reads the actual wallet. Users get answers
about *their* positions — not textbook examples.

**Integrates with:** Hyperliquid · Aave V3 on Arbitrum · GMX V2 on Arbitrum · Vertex

---

## For DeFi Protocols

| You pay today | What you get with Mirael |
|---|---|
| $5K-15K/month for human support | AI handles 80% of repetitive tickets |
| Slow, inconsistent answers | Instant, precise, wallet-aware responses |
| Users get liquidated, churn | `/monitor` alerts users *before* liquidation |
| English-only support | Multilingual (Spanish, English, Portuguese) |

**Setup time:** under 1 hour
**Cost:** one-time setup + monthly retainer
**Interested?** DM [@MiraelLabs on Twitter](https://twitter.com/MiraelLabs) or open an issue.

---

## Features

- **RAG over your docs** — ingest any protocol documentation; answers are grounded in your actual content
- **Live on-chain context** — reads Hyperliquid positions, Aave health factor, GMX positions in real time
- **Proactive alerts** — `/monitor` DMs users before liquidation, not after
- **Discord + Telegram** — slash commands, plain text, per-user wallet registry
- **One API key** — only Anthropic required; embeddings run locally (free)
- **Open-source MIT** — self-host or use Mirael managed service

---

## Quick Start (under 10 minutes)

### 1. Install

```bash
git clone https://github.com/Mirael-labs/mirael-agent-sdk
cd mirael-agent-sdk
uv sync --all-extras
```

### 2. Configure

```bash
cp .env.example .env
# Fill in: MIRAEL_ANTHROPIC_API_KEY (required)
#          MIRAEL_QDRANT_URL        (required — use cloud.qdrant.io free tier)
#          MIRAEL_DISCORD_BOT_TOKEN (for Discord bot)
```

### 3. Ingest your protocol docs

```bash
mirael ingest https://your-protocol-docs.io
# or use the built-in Hyperliquid + Aave + GMX docs:
uv run python examples/hyperliquid_demo/ingest_docs.py
```

### 4. Start the bot

```bash
# Discord bot
uv run python examples/discord_demo/bot.py

# Telegram bot
uv run python examples/telegram_demo/bot.py

# Terminal demo (with your wallet)
mirael chat 0xYOUR_WALLET
```

---

## Discord Commands

| Command | What it does |
|---|---|
| `/ask [question]` | Ask anything — RAG answers from your protocol docs |
| `/positions [wallet]` | Show live on-chain positions (Hyperliquid, Aave, GMX) |
| `/health [wallet]` | Health factor + liquidation risk assessment |
| `/monitor [wallet]` | Start DM alerts before liquidation |

---

## Architecture

```
User (Discord / Telegram)
        │
        ▼
ChannelAdapter
        │
        ▼
Agent  (claude-sonnet-4-5 · prompt caching)
        ├── RAG → Qdrant → bge-large-en-v1.5 (local, free)
        ├── HyperliquidReader → Hyperliquid L1 (positions, funding)
        ├── AaveV3Reader → Arbitrum mainnet (health factor, debt)
        └── GMXReader → Arbitrum mainnet (perp positions, OI)
```

Full architecture: [`docs/architecture.md`](docs/architecture.md) · ADRs: [`docs/adr/`](docs/adr/)

---

## SDK Structure

```
src/mirael/
├── chains/       # On-chain readers (Hyperliquid, Aave, GMX, EVM)
├── knowledge/    # RAG: ingest → embed → store → retrieve
├── agent/        # Agent: orchestrates RAG + chain + LLM + memory
├── channels/     # Discord + Telegram adapters
└── llm/          # LLM providers (Anthropic)
```

---

## Quality

- **200 unit tests** · **17 E2E tests** (real Qdrant + Hyperliquid mainnet)
- **19 Agent E2E tests** using real Anthropic API
- mypy strict · ruff 0 violations · bandit 0 security issues
- GitHub Actions CI on every push

---

## Business Model

**Services-first → SaaS**

Setup: $10,000–15,000 one-time · Monthly: $2,000–3,000/month

Self-serve SaaS launching Q4 2026: $299/mo (Starter) · $799/mo (Growth) · $1,999/mo (Scale)

Full model: [`BUSINESS_MODEL.md`](BUSINESS_MODEL.md)

---

## License

MIT — [Mirael Labs](https://github.com/Mirael-labs) · Bucaramanga, Colombia
