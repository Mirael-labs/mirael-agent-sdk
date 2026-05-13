# Hyperliquid Co-Pilot Demo

End-to-end demo: a terminal REPL that answers questions about
Hyperliquid using documentation RAG **and** live on-chain position data.

## Prerequisites

1. Python 3.12+, `uv` installed
2. Docker (for Qdrant)
3. API keys: Anthropic + OpenAI
4. A Hyperliquid wallet address (mainnet or testnet)

## Setup

```bash
# From repo root
cp .env.example .env
# Fill in MIRAEL_ANTHROPIC_API_KEY and MIRAEL_OPENAI_API_KEY at minimum

uv sync --all-extras
docker compose up -d qdrant
```

## Step 1 — Ingest documentation

```bash
uv run python examples/hyperliquid_demo/ingest_docs.py
```

Output:
```
  ✓ Fetched: Hyperliquid Python SDK
Ingesting 7 documents into collection mirael_docs...
⠋ Embedding and upserting...
✓ Done. Ingested 142 chunks from 7 documents.
```

This step embeds 6 built-in concept documents (funding, liquidation, margin,
order types, fees, protocol overview) plus the live SDK README from GitHub.
Re-running is safe — existing chunks are overwritten.

## Step 2 — Start the chat

```bash
uv run python examples/hyperliquid_demo/chat.py 0xYOUR_WALLET_ADDRESS
```

### Example session

```
╭─────────────────────────────────────────────╮
│  Hyperliquid Co-Pilot                        │
│  AI assistant with live on-chain context     │
│  Commands: /reset · /quit                    │
╰─────────────────────────────────────────────╯
  Wallet: 0xabc123...

You: Why am I paying funding on my BTC position?

─────────────── HyperAssist ────────────────────

Your BTC-PERP long position (0.5 BTC) is paying funding because the
perpetual price is trading **above** the oracle price, indicating bullish
sentiment. Longs pay shorts when this premium exists.

**Current position:**
- Size: 0.5 BTC long
- Funding rate: +0.012% per hour (**+105.1% annualised**)
- Estimated daily cost: ~$42 at current mark price ($70,000)

**Why it matters:** At this rate, holding for 30 days would cost ~$1,260
in funding alone, regardless of price movement.

─────────────────────────────────────────────────

You: what happens if my health drops below 20?

─────────────── HyperAssist ────────────────────

When a position's health factor drops below **20/100**, it means your
liquidation price is within **10%** of the current mark price — a
critical zone.

At that point:
1. **Partial liquidation** may trigger automatically to bring your
   account back above maintenance margin.
2. If the price continues against you, the entire position can be closed.
3. You receive the **remaining equity** after liquidation fees.

**Your current health: 72** — you're well within safe territory.
Liquidation distance: ~28% from current mark price.

─────────────────────────────────────────────────
```

## Commands

| Command | Description |
|---|---|
| `/reset` | Clear conversation memory (start fresh) |
| `/quit` | Exit the REPL |
| Ctrl-C | Emergency exit |

## Configuration

| Env var | Effect |
|---|---|
| `MIRAEL_HL_NETWORK=testnet` | Use testnet instead of mainnet |
| `MIRAEL_LLM_MODEL=claude-opus-4-5` | Use a different Claude model |
| `MIRAEL_QDRANT_COLLECTION=my_docs` | Use a custom collection |
