# Arbitrum Open House London Buildathon — Submission

**Project:** Mirael Agent SDK  
**Category:** AI Agentic  
**Repo:** https://github.com/Mirael-labs/mirael-agent-sdk  
**Team:** Mael De La Hoz — solo founder, Mirael Labs (Bucaramanga, Colombia)

---

## The Problem

DeFi protocols have thousands of users asking the same questions in Discord and Telegram every day:

- *"Why is my health factor dropping?"*
- *"Am I about to get liquidated on Aave?"*
- *"Why am I paying so much in funding on Hyperliquid?"*

Manual support is slow, expensive, and doesn't scale. Generic AI chatbots give generic answers. Neither can look at the user's actual wallet and give a precise, real-time answer.

---

## The Solution

**Mirael Agent SDK** — an open-source Python SDK that lets any DeFi protocol deploy an AI customer support agent in minutes. The agent does two things no generic chatbot can do:

1. **Reads the protocol's own docs** — via RAG (semantic search over ingested documentation). Answers are grounded in the protocol's actual mechanics, not hallucinated.

2. **Reads the user's real on-chain positions** — connects to Arbitrum (Aave V3) and Hyperliquid to fetch live positions, health factor, funding rates, and liquidation prices.

The result: when a user asks *"am I at risk of liquidation?"*, the agent responds with their actual numbers — not a generic explanation.

---

## Arbitrum Integration

The SDK's `AaveV3Reader` connects directly to **Aave V3 on Arbitrum mainnet** via Web3.py:

- Contract: `Pool` at `0x794a61358D6845594F94dc1DB02A252b5b4814aD` (Arbitrum)
- Reads: `getUserAccountData()` → health factor, collateral, debt, LTV
- Reads: reserve positions (WETH, USDC, ARB, USDT, wstETH…)
- Calculates: liquidation distance, available borrow capacity

```python
async with AaveV3Reader() as reader:
    balance = await reader.get_user_balance("0xYOUR_WALLET")
    # {"health_factor": 1.82, "total_collateral_usd": 8200, "total_debt_usd": 4100}
    
    positions = await reader.get_user_positions("0xYOUR_WALLET")
    # [{"asset": "WETH", "position_type": "supply", "balance_usd": 8200, "apy": 0.024}]
```

The agent uses this live context to answer risk questions with precision:

> *"Your health factor is 1.42. WETH collateral at $8,200, USDC debt at $4,100. If ETH drops ~22% you'll hit liquidation. Reduce your USDC debt by ~$800 to reach a safe 1.7 health factor."*

---

## Technical Architecture

```
User (Discord / Telegram)
        │
        ▼
ChannelAdapter  —  /ask, /positions, /health, /monitor
        │
        ▼
Agent  (claude-sonnet-4-5, Anthropic)
        ├── RAG retriever → Qdrant → bge-large-en-v1.5 (local, free)
        ├── HyperliquidReader → Hyperliquid L1 REST API
        └── AaveV3Reader → Arbitrum mainnet (Aave V3)
```

**Stack:**
- LLM: `claude-sonnet-4-5` with prompt caching (~60% token cost reduction)
- Embeddings: `BAAI/bge-large-en-v1.5` — local, no API key needed
- Vector store: Qdrant Cloud (free tier sufficient for any protocol)
- Chains: Hyperliquid L1 + Arbitrum (Aave V3)
- Channels: Discord (slash commands) + Telegram (commands + plain text)
- Only 1 API key required to run: Anthropic

**Key features:**
- `/monitor` — proactive DM alerts when health factor < 1.5 (before liquidation)
- Multi-wallet: each Discord user gets their own wallet and memory
- Graceful degradation: if chain is unreachable, agent answers from docs only
- Open-source (MIT) — protocols self-host or use Mirael managed service

---

## Business Model

**Services-first → SaaS:**

1. **Setup** ($10-15K): Mirael configures the agent for the protocol, ingests their docs, deploys to their Discord/Telegram
2. **Monthly** ($2-3K/month): maintenance, doc updates, support
3. **Later**: productized SaaS with self-serve onboarding

**ICP:** DeFi protocols on Arbitrum + Hyperliquid, 10-50 person teams, 100K+ users.

The $20K grant accelerates reaching the first 3 paying clients and building the Arbitrum-native multi-protocol features.

---

## Code Quality

- **193 unit tests** · 88% coverage
- **17 E2E tests** against real services (Qdrant Cloud + Hyperliquid mainnet)
- **mypy strict** · ruff 0 violations · bandit 0 issues
- GitHub Actions CI on every push

---

## Demo

```bash
git clone https://github.com/Mirael-labs/mirael-agent-sdk
cd mirael-agent-sdk
uv sync --all-extras
cp .env.example .env  # add MIRAEL_ANTHROPIC_API_KEY
docker compose up -d qdrant
uv run python examples/hyperliquid_demo/ingest_docs.py
uv run python examples/discord_demo/bot.py
```

Then in Discord: `/ask why is my Aave health factor dropping?`

---

## Why Arbitrum

Arbitrum hosts the most active DeFi ecosystem after Ethereum mainnet:
- Aave V3 (largest lending protocol) — our primary integration
- GMX, Vertex, Camelot, Pendle — next integrations on the roadmap
- Fast finality + low gas = better UX for real-time position monitoring

The `AaveV3Reader` is production-ready against Arbitrum mainnet today. GMX and Vertex readers are next on the roadmap (the `OnchainReader` Protocol makes adding new chains a ~2h implementation).

---

*Built by Mael De La Hoz · Mirael Labs · Bucaramanga, Colombia*  
*github.com/Mirael-labs · mirael-agent-sdk*
