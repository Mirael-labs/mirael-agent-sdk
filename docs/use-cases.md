# Use Cases — Mirael Agent SDK

Three validated use cases for the Buildathon submission.

---

## Use Case 1: Hyperliquid 24/7 Support Bot

**Protocol type:** Perpetual futures DEX (Hyperliquid)
**Channel:** Discord + Telegram
**Value:** Replace slow manual support with instant AI answers grounded in protocol docs.

### What it does
- Answers questions about funding rates, liquidation mechanics, margin types, order types
- Shows the user's live positions with PnL, health factor, and liquidation distance
- Fires risk alerts when health factor drops below threshold

### Example interaction (Discord)

```
User: /ask why is my SOL position costing me so much in funding?

Bot: Your SOL-PERP long (size: 150 SOL) is paying funding because the perpetual
     is trading above oracle — bullish premium.

     Current rate: +0.031%/hr (+271% annualised)
     Estimated daily cost: ~$48 at current mark price ($102.40)

     At this rate, holding 30 days costs ~$1,440 in funding alone.
     Consider reducing size or switching to a lower-funding asset.

     📚 2 doc chunks used · 1,240 tokens
```

### Setup (5 minutes)

```bash
# 1. Ingest docs once
uv run python examples/hyperliquid_demo/ingest_docs.py

# 2. Set env vars
MIRAEL_DISCORD_BOT_TOKEN=your-token
MIRAEL_HL_WALLET_ADDRESS=0x...

# 3. Run
uv run python examples/discord_demo/bot.py
```

---

## Use Case 2: Aave V3 Arbitrum Risk Monitor

**Protocol type:** Lending protocol (Aave V3 on Arbitrum)
**Channel:** Telegram
**Value:** Proactive health-factor monitoring with AI-generated risk explanations.

### What it does
- Reads user's Aave positions (supplies + variable borrows) from Arbitrum mainnet
- Computes effective health factor, LTV, available borrow capacity
- Answers questions about borrow rates, liquidation thresholds, and risk management

### Example interaction (Telegram)

```
/health 0x742d35Cc6634C0532925a3b844Bc454e4438f44e

Bot: ⚠️ Health Factor: 1.42 — Moderate Risk

     Collateral:  WETH $8,200  (80% LTV)
     Debt:        USDC $4,100
     Liquidation: health < 1.0

     You're 29% above liquidation. If WETH drops ~22%
     from current price ($2,050), you'll be at risk.

     Recommended: reduce USDC debt by ~$800 to reach
     health factor > 1.7 (safe zone).
```

### Setup

```bash
MIRAEL_TELEGRAM_BOT_TOKEN=your-token
MIRAEL_ARBITRUM_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY

uv run python examples/telegram_demo/bot.py
```

---

## Use Case 3: Multi-Protocol DeFi Copilot (Combined)

**Protocols:** Hyperliquid perpetuals + Aave V3 Arbitrum
**Channel:** Discord (primary) + Telegram (mobile)
**Value:** One agent handles both CEX-like perpetuals and lending protocol context.

### What it does
- Unified interface: users ask about Hyperliquid perps OR Aave positions
- Agent detects intent and routes to appropriate chain reader
- Cross-protocol risk view: if funding is high AND borrow rates are high, agent surfaces this

### Architecture

```
User (Discord / Telegram)
    │
    ▼
DiscordChannelAdapter / TelegramChannelAdapter
    │
    ▼
Agent (claude-sonnet-4-5)
    ├── RAG → Qdrant (Hyperliquid + Aave docs)
    ├── HyperliquidReader → perpetual positions
    └── AaveV3Reader → lending positions
```

### Deploy both bots simultaneously

```bash
# Terminal 1 — Discord
MIRAEL_DISCORD_BOT_TOKEN=... uv run python examples/discord_demo/bot.py

# Terminal 2 — Telegram
MIRAEL_TELEGRAM_BOT_TOKEN=... uv run python examples/telegram_demo/bot.py
```

---

## Technical differentiators

| Feature | Mirael Agent SDK | Generic chatbot |
|---|---|---|
| Live on-chain position context | ✅ real-time | ❌ no |
| RAG over protocol docs | ✅ semantic search | ❌ static prompts |
| Multi-chain (HL + Arbitrum) | ✅ pluggable readers | ❌ no |
| Open-source + self-hostable | ✅ MIT | ❌ vendor lock-in |
| Type-safe, tested SDK | ✅ mypy strict, 88% cov | ❌ no |
| Claude with prompt caching | ✅ ~60% token savings | varies |
