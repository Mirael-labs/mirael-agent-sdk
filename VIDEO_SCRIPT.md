# Video Demo Script — Mirael Agent SDK
## Arbitrum Buildathon Submission

**Target duration:** 2:30 - 3:00 minutes  
**Format:** Screen recording + voiceover  
**Tool:** OBS / Loom / any screen recorder

---

## Pre-recording setup (do this BEFORE hitting record)

1. Open **VS Code** with the `mirael-agent-sdk` folder open
2. Open **Discord** in the browser, go to "El servidor de Mael De La Hoz" → #general
3. Have a **terminal** ready with the SDK folder open
4. Run the ingest script so Qdrant already has docs:
   ```bash
   cd mirael-agent-sdk
   uv run python examples/hyperliquid_demo/ingest_docs.py
   ```
5. Start the Discord bot:
   ```bash
   uv run python examples/discord_demo/bot.py
   ```
6. Have `console.anthropic.com` open in a tab (to show the API key usage)

---

## Script

### [0:00 - 0:20] Hook

> "DeFi protocols have thousands of users asking the same questions in Discord every day. *Why is my health factor dropping? Am I about to get liquidated? Why am I paying so much in funding?*"

> "Manual support doesn't scale. Generic AI chatbots give generic answers. Neither can look at the user's actual wallet."

> "This is Mirael Agent SDK — open-source, built on Arbitrum."

---

### [0:20 - 0:45] Show the architecture (VS Code / diagram)

*Show the architecture diagram from README.md or draw it quickly*

> "The SDK does two things. First, it reads the protocol's documentation using RAG — semantic search over ingested docs. Second, it connects to the blockchain and reads the user's actual positions in real time."

> "On Arbitrum, it reads from Aave V3 — health factor, collateral, debt, liquidation prices. On Hyperliquid, it reads perpetual positions and funding rates."

> "Only one API key required: Anthropic. Everything else — embeddings, vector store — runs locally or on free tiers."

---

### [0:45 - 1:30] Live Discord demo

*Switch to Discord in the browser*

**Command 1 — general question:**

Type in Discord:
```
/ask what is the funding rate on Hyperliquid and why does it matter?
```

*Wait for response (5-10 seconds)*

> "The agent retrieves relevant chunks from the ingested documentation and gives a precise, grounded answer — not a hallucination."

**Command 2 — positions (if you have a HL wallet with positions, use it; otherwise use a demo):**

```
/positions 0x65bf83b7B8B3370bf2Dc59cdF95BfE221d064Fc2
```

> "Now it connects to Hyperliquid mainnet and reads the wallet's actual positions."

**Command 3 — health/risk (Aave angle):**

```
/ask how does Aave V3 on Arbitrum calculate liquidation? what should I watch?
```

*Wait for response*

> "This is RAG in action — the answer is grounded in actual Aave documentation ingested earlier."

**Command 4 — the killer feature:**

```
/monitor 0x65bf83b7B8B3370bf2Dc59cdF95BfE221d064Fc2
```

> "This starts proactive monitoring. If the health factor drops below 1.5, the bot DMs the user directly — before liquidation happens. No generic chatbot does this."

---

### [1:30 - 2:00] Show the code (VS Code)

*Open `src/mirael/chains/evm.py` — scroll to `get_user_balance`*

> "The Aave V3 reader connects directly to the Arbitrum mainnet contract at `0x794a61...` — the official Aave V3 Pool. It reads health factor, collateral, debt, and liquidation threshold in real time."

*Open `src/mirael/agent/base.py` — show the `chat` method*

> "The agent is modular. Any protocol can plug in their own chain reader, their own docs, their own Discord server. The `OnchainReader` Protocol makes adding GMX, Vertex, or Camelot readers a 2-hour implementation."

---

### [2:00 - 2:20] Business model + closing

*Show the README or SUBMISSION.md*

> "The business model is services-first — $10-15K setup plus $2-3K per month. The target: DeFi protocols on Arbitrum with 100K+ users who need 24/7 AI support."

> "The SDK is MIT licensed, open-source, and live on GitHub right now. The $20K grant from Arbitrum accelerates reaching our first three paying clients and expanding the Arbitrum-native integrations."

> "Mirael Agent SDK — built in Bucaramanga, Colombia, for DeFi protocols on Arbitrum."

---

## Recording tips

- Use a **dark theme** everywhere (VS Code dark, Discord dark, terminal dark) — looks better on video
- Zoom in when showing code (`Ctrl +` in VS Code)
- Pause briefly after each Discord response so viewers can read it
- If the bot takes > 15 seconds to respond, cut in editing
- Add captions/subtitles in post if possible — many watch without sound

## Thumbnail suggestion

Dark background, Liquid Glass style:  
`Mirael Agent SDK` in white bold  
`AI agents for DeFi on Arbitrum` in cyan  
Small logos: Anthropic + Arbitrum + Qdrant

---

*Total estimated recording time including setup: 45 minutes*
