# Mirael Agent SDK

Open-source Python SDK for deploying AI customer support agents with on-chain context.

Give any DeFi protocol a conversational agent that understands their docs **and** can read a user's live wallet state from the chain — powered by Claude, Qdrant, and Hyperliquid.

## Features

- **RAG pipeline** — ingest protocol docs, semantic chunking, OpenAI embeddings, Qdrant retrieval
- **On-chain context** — read Hyperliquid positions, balances, trades, and funding rates in real time
- **Anthropic LLM** — `claude-sonnet-4-5` with prompt caching, streaming, and retry logic
- **Channel-ready** — pluggable interface for Discord, Telegram, or custom channels
- **Type-safe** — mypy strict, Pydantic v2 models throughout
- **Observable** — structured logging via structlog, metric hooks ready

## Demo

```bash
# 1. Start Qdrant + install deps
docker compose up -d qdrant
uv sync --all-extras

# 2. Ingest Hyperliquid docs
uv run python examples/hyperliquid_demo/ingest_docs.py

# 3. Chat with live on-chain context
uv run python examples/hyperliquid_demo/chat.py 0xYOUR_WALLET
```

```
You: Why am I paying funding on my BTC position?

HyperAssist: Your BTC-PERP long (0.5 BTC) is paying funding because the
perpetual price is above the oracle. Current rate: +0.012%/hr
(+105% annualised). Estimated daily cost: ~$42.

You: How close am I to liquidation?
HyperAssist: Your health factor is 72/100. Liquidation distance: 28%.
No immediate risk — but the funding burn is the bigger concern right now.
```

See [`examples/hyperliquid_demo/README.md`](examples/hyperliquid_demo/README.md) for the full walkthrough.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (recommended) or pip
- Docker (for local Qdrant)

## 10-minute setup

### 1. Clone and install

```bash
git clone https://github.com/your-org/mirael-agent-sdk
cd mirael-agent-sdk
uv sync --all-extras
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set MIRAEL_ANTHROPIC_API_KEY and MIRAEL_OPENAI_API_KEY
```

### 3. Start Qdrant

```bash
docker compose up -d qdrant
```

### 4. Run the Hyperliquid demo

```bash
uv run python examples/hyperliquid_demo/ingest_docs.py
uv run python examples/hyperliquid_demo/chat.py 0xYOUR_ADDRESS
```

## Development

```bash
uv sync --all-extras
uv run pre-commit install

# Quality gates
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/
uv run pytest
uv run bandit -r src/
uv run pip-audit
```

## Project structure

```
src/mirael/
├── config.py          # Pydantic Settings — all config in one place
├── logging.py         # structlog JSON/console renderer
├── exceptions.py      # Typed error hierarchy
├── cli.py             # typer CLI entrypoint (mirael version|ingest|chat)
├── chains/            # On-chain data readers (Protocol-based)
│   ├── base.py        # OnchainReader Protocol
│   ├── hyperliquid.py # HyperliquidReader — httpx + tenacity
│   └── models.py      # PositionSummary, BalanceSummary, …
├── knowledge/         # RAG: ingest → embed → store → retrieve
│   ├── models.py      # Document, Chunk, RetrievalResult
│   ├── embeddings.py  # OpenAI text-embedding-3-large
│   ├── vector_store.py# Qdrant async client
│   ├── ingest.py      # SemanticChunker + IngestPipeline
│   └── retriever.py   # Retriever (embed query → top-k chunks)
├── agent/             # Agent orchestration
│   ├── base.py        # Agent: RAG + chain + LLM + memory
│   ├── memory.py      # InMemoryConversationMemory (sliding window)
│   ├── prompts.py     # build_system_prompt, format_chain_context
│   └── models.py      # AgentConfig, AgentResponse
├── channels/          # Output channels (Discord, Telegram — interfaces)
└── llm/               # LLM provider wrappers
    ├── base.py        # LLMProvider Protocol
    ├── anthropic.py   # AnthropicLLM — claude-sonnet-4-5
    └── models.py      # ChatMessage, LLMResponse

examples/
└── hyperliquid_demo/
    ├── ingest_docs.py # Step 1: embed HL docs into Qdrant
    ├── chat.py        # Step 2: interactive REPL with streaming
    └── README.md      # Full walkthrough with example output

docs/
├── architecture.md    # System diagram (Mermaid)
└── adr/
    ├── 0001-tech-stack.md        # Why Anthropic / OpenAI / Qdrant / structlog
    └── 0002-agent-orchestration.md # Concurrent context, graceful degradation, memory
```

## Architecture decisions

See [`docs/adr/`](docs/adr/) for recorded design decisions:
- [ADR-0001](docs/adr/0001-tech-stack.md) — Tech stack selection
- [ADR-0002](docs/adr/0002-agent-orchestration.md) — Agent orchestration design

## Coverage

```
pytest --cov=src/mirael --cov-report=term-missing
```

Current unit test coverage: **88%** across 155 tests.
Integration tests (Qdrant + Hyperliquid mainnet) live in `tests/integration/`
and are marked `@pytest.mark.integration`.

## License

MIT
