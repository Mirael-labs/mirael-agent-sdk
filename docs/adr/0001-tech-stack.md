# ADR-0001: Tech Stack Selection

**Date:** 2026-05-12
**Status:** Accepted

## Context

We need to choose the foundational tech stack for the Mirael Agent SDK. The SDK must be:
- Easy to self-host (no mandatory cloud lock-in)
- Suitable for real-time financial data
- Type-safe and testable
- Deployable on Railway with minimal ops overhead

## Decision

### LLM: Anthropic `claude-sonnet-4-5`

**Rationale:** Best-in-class instruction following; native tool use and streaming; prompt caching reduces costs ~60% on repeated context (docs chunks); hosted API eliminates GPU ops.

**Alternatives considered:** OpenAI GPT-4o (rejected — lower instruction accuracy on financial domain), Mistral self-hosted (rejected — GPU ops complexity out of scope).

### Embeddings: OpenAI `text-embedding-3-large`

**Rationale:** 3072-dim vectors with state-of-the-art MTEB retrieval scores; matryoshka truncation allows dimension reduction if needed; proven in financial text retrieval.

**Alternatives considered:** `BAAI/bge-large-en-v1.5` (good open-source option but requires hosting; added infra complexity at SDK stage).

### Vector Store: Qdrant

**Rationale:** Native async Python client; payload filtering for metadata-aware retrieval; free self-hosted via Docker; Qdrant Cloud available for managed deployment; HNSW index with tunable parameters.

**Alternatives considered:** Pinecone (managed but $70/month minimum, no self-hosted), Chroma (simpler but lacks production-grade filtering).

### HTTP: `httpx` + `tenacity`

**Rationale:** Native async, HTTP/2 support, clean API. `tenacity` gives declarative retry with exponential backoff — critical for LLM and chain RPC calls.

**Alternatives considered:** `aiohttp` (more complex API, no HTTP/2).

### Config: Pydantic v2 + `pydantic-settings`

**Rationale:** Fail-fast validation at startup prevents misconfigured deployments; `SecretStr` prevents secrets from appearing in logs or tracebacks; full type annotations.

### Logging: `structlog`

**Rationale:** JSON-structured logs in production integrate directly with Railway/Datadog log aggregators; console renderer in development is human-readable; context binding via contextvars is thread/async safe.

### CLI: `typer` + `rich`

**Rationale:** Automatic help generation from Python type hints; `rich` integration for beautiful terminal output; no boilerplate compared to argparse/click.

## Consequences

- SDK requires Python 3.12+ (no legacy support)
- Two external API keys required at minimum (Anthropic + OpenAI); users can swap embedding provider in Phase 3+
- Qdrant must be running before any RAG operations (clear error via `ConfigurationError` if not reachable)
