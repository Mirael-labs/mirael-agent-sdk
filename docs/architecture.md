# Architecture

## System Overview

```mermaid
graph TB
    subgraph Client["Client Layer"]
        CLI["CLI (typer)"]
        DC["Discord Channel"]
        TG["Telegram Channel"]
    end

    subgraph Core["Core Agent"]
        AGT["Agent\norchestrate RAG + LLM + chain"]
        MEM["ConversationMemory\nsliding window"]
        PRO["Prompts\nparameterized templates"]
    end

    subgraph Knowledge["Knowledge Layer"]
        ING["Ingest Pipeline\ncrawl → chunk → embed"]
        EMB["Embeddings\nOpenAI text-embedding-3-large"]
        VS["Vector Store\nQdrant"]
        RET["Retriever\ntop-k semantic search"]
    end

    subgraph Chain["On-chain Layer"]
        HLC["HyperliquidReader\npositions · funding · trades"]
        EVM["EVMReader\n(placeholder)"]
    end

    subgraph LLM["LLM Layer"]
        ANT["AnthropicLLM\nclaude-sonnet-4-5\nwith prompt caching"]
    end

    subgraph Config["Cross-cutting"]
        CFG["Settings\nPydantic v2"]
        LOG["Logging\nstructlog JSON/console"]
        EXC["Exceptions\ntyped hierarchy"]
    end

    CLI --> AGT
    DC  --> AGT
    TG  --> AGT

    AGT --> MEM
    AGT --> PRO
    AGT --> RET
    AGT --> HLC
    AGT --> ANT

    ING --> EMB --> VS
    RET --> VS

    HLC --> EXT_HL["Hyperliquid L1\nREST + WS"]
    ANT --> EXT_ANT["Anthropic API"]
    EMB --> EXT_OAI["OpenAI API"]
```

## Data Flow: User Query

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant R as Retriever
    participant H as HyperliquidReader
    participant L as AnthropicLLM

    U->>A: user message
    A->>R: semantic search(message)
    R-->>A: top-k doc chunks
    A->>H: get_user_positions(wallet)
    H-->>A: live position snapshot
    A->>A: build system prompt<br/>(docs + positions + history)
    A->>L: chat(messages, system)
    L-->>A: streamed response
    A-->>U: response text
```

## Module Dependency Rules

- `config`, `logging`, `exceptions` — no internal dependencies (foundation layer)
- `llm`, `chains` — depend on foundation only
- `knowledge` — depends on `llm` (for embeddings)
- `agent` — depends on `knowledge`, `chains`, `llm`
- `channels`, `cli` — depend on `agent`

**Rule:** lower layers NEVER import from higher layers.
