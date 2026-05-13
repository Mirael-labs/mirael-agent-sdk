# Mirael Agent SDK

[![CI](https://github.com/Mirael-labs/mirael-agent-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mirael-labs/mirael-agent-sdk/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Open-source Python SDK for deploying AI customer support agents with live on-chain context.

Give any DeFi protocol a 24/7 AI assistant that **understands their docs** and **reads the user's real positions from the chain** — deployable to Discord and Telegram in minutes.

> Built for the [Arbitrum Open House London Buildathon](https://arbitrum.foundation) · AI Agentic category

---

## What it does

```
User in Discord: /ask why is my health factor dropping?

Agent: Your Aave V3 position on Arbitrum shows a health factor of 1.42.
       WETH collateral ($8,200) vs USDC debt ($4,100).
       If WETH drops 22% you hit liquidation.
       Reduce USDC debt by ~$800 to reach a safe 1.7 health factor.
```

- **RAG over protocol docs** — semantic search (Qdrant + OpenAI embeddings) over Hyperliquid and Aave documentation
- **Live on-chain context** — reads positions, health factors, funding rates, and borrow APYs in real time
- **Discord + Telegram bots** — slash commands, plain-text chat, per-user wallet registry
- **Multi-chain** — Hyperliquid perpetuals (L1) + Aave V3 on Arbitrum, same agent interface
- **Powered by Claude** — `claude-sonnet-4-5` with prompt caching (~60% token cost reduction on repeated context)
- **Open-source SDK** — MIT licensed, self-hostable, pluggable architecture

---

## Supported chains

| Chain | Reader | Use case |
|---|---|---|
| Hyperliquid L1 | `HyperliquidReader` | Perpetual futures positions, funding rates, PnL |
| Arbitrum (Aave V3) | `AaveV3Reader` | Lending positions, health factor, borrow APYs |
| Any EVM *(planned)* | `EVMReader` | Generic ERC-20 balances, protocol adapters |

---

## Quick start (5 minutes)

### Prerequisites
- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- Docker (for local Qdrant)
- Anthropic API key + OpenAI API key

### 1. Install

```bash
git clone https://github.com/Mirael-labs/mirael-agent-sdk
cd mirael-agent-sdk
uv sync --all-extras
```

### 2. Configure

```bash
cp .env.example .env
# Fill in at minimum:
#   MIRAEL_ANTHROPIC_API_KEY
#   MIRAEL_OPENAI_API_KEY
#   MIRAEL_DISCORD_BOT_TOKEN  (or TELEGRAM)
```

### 3. Start Qdrant + ingest docs

```bash
docker compose up -d qdrant
uv run python examples/hyperliquid_demo/ingest_docs.py
```

### 4. Run your bot

```bash
# Discord
uv run python examples/discord_demo/bot.py

# Telegram
uv run python examples/telegram_demo/bot.py

# Terminal REPL (Hyperliquid)
uv run python examples/hyperliquid_demo/chat.py 0xYOUR_WALLET

# Terminal REPL (Aave / Arbitrum)
uv run python examples/arbitrum_aave_demo/main.py 0xYOUR_WALLET
```

---

## Use cases

See [`docs/use-cases.md`](docs/use-cases.md) for full walkthroughs:

1. **Hyperliquid 24/7 support bot** — Discord bot answering perp trading questions with live position context
2. **Aave V3 risk monitor** — Telegram bot showing health factor and liquidation risk on Arbitrum
3. **Multi-protocol copilot** — unified agent across Hyperliquid + Aave V3

---

## Architecture

```
User (Discord / Telegram / Terminal)
    │
    ▼
ChannelAdapter  ─────────────────────────────────────────────────┐
    │                                                             │
    ▼                                                             │
Agent (claude-sonnet-4-5)                                         │
    ├── RAG → Retriever → Qdrant → OpenAI embeddings             │
    ├── HyperliquidReader → REST + WebSocket (Hyperliquid L1)    │
    └── AaveV3Reader → JSON-RPC (Arbitrum mainnet)               │
                                                                  │
IngestPipeline (one-time setup) ─────────────────────────────────┘
    └── docs → SemanticChunker → OpenAIEmbeddings → Qdrant
```

Full diagram: [`docs/architecture.md`](docs/architecture.md)

Architecture decisions: [`docs/adr/`](docs/adr/)

---

## SDK structure

```
src/mirael/
├── config.py          # Pydantic Settings — all config, MIRAEL_* env vars
├── exceptions.py      # Typed error hierarchy
├── logging.py         # structlog JSON/console
├── chains/
│   ├── base.py        # OnchainReader Protocol
│   ├── hyperliquid.py # HyperliquidReader — REST + tenacity retry
│   └── evm.py         # AaveV3Reader — Aave V3 on Arbitrum via web3
├── knowledge/
│   ├── embeddings.py  # OpenAI text-embedding-3-large
│   ├── vector_store.py# Qdrant async client
│   ├── ingest.py      # SemanticChunker + IngestPipeline
│   └── retriever.py   # top-k semantic retrieval
├── agent/
│   ├── base.py        # Agent — concurrent RAG + chain + LLM
│   ├── memory.py      # InMemoryConversationMemory (sliding window)
│   └── prompts.py     # parameterised system prompt builder
├── channels/
│   ├── base.py        # ChannelAdapter Protocol
│   ├── discord.py     # Discord bot (slash commands)
│   └── telegram.py    # Telegram bot (/commands + plain text)
└── llm/
    ├── base.py        # LLMProvider Protocol
    └── anthropic.py   # AnthropicLLM — claude-sonnet-4-5 + prompt cache
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `MIRAEL_ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `MIRAEL_OPENAI_API_KEY` | ✅ | Embeddings API key |
| `MIRAEL_QDRANT_URL` | ✅ | Qdrant URL (default: `http://localhost:6333`) |
| `MIRAEL_HL_WALLET_ADDRESS` | For HL demo | Hyperliquid wallet |
| `MIRAEL_ARBITRUM_RPC_URL` | For Aave demo | Arbitrum RPC (default: public endpoint) |
| `MIRAEL_DISCORD_BOT_TOKEN` | For Discord bot | From discord.com/developers |
| `MIRAEL_TELEGRAM_BOT_TOKEN` | For Telegram bot | From @BotFather |

Full reference: [`.env.example`](.env.example)

---

## Development

```bash
uv sync --all-extras
uv run pre-commit install

uv run ruff check .          # lint
uv run mypy --strict src/    # types
uv run pytest                # 151 tests · 88% coverage
uv run bandit -r src/        # security
```

---

## License

MIT — [Mirael Labs](https://github.com/Mirael-labs)
