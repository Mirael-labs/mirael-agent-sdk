# ADR-0002: Agent Orchestration Design

**Date:** 2026-05-12
**Status:** Accepted

## Context

The Agent class must combine three data sources (knowledge base, on-chain
state, conversation history) into a single prompt for the LLM.  Key design
questions:

1. How to assemble the system prompt without blocking on sequential fetches.
2. How to handle partial failures (e.g. Qdrant down, chain node unreachable).
3. How much history to retain and when to trim.
4. How to keep the module dependency graph clean.

## Decisions

### 1. Concurrent context gathering via `asyncio.gather`

RAG retrieval and on-chain data fetching run concurrently:
```python
rag_task   = asyncio.create_task(self._get_rag_context(user_message))
chain_task = asyncio.create_task(self._get_chain_context(wallet))
rag_results, chain_ctx = await asyncio.gather(rag_task, chain_task)
```

**Rationale:** On a typical query, RAG retrieval takes ~200–400ms (embedding
call + Qdrant search) and chain fetching takes ~150–300ms (two HTTP requests).
Sequential would take ~700ms worst-case; concurrent takes ~400ms — a 40%
latency reduction with no added complexity.

**Alternative considered:** Sequential fetch.  Rejected: unnecessary latency.

### 2. Graceful degradation on context failures

Non-`MiraelError` exceptions in `_get_rag_context` and `_get_chain_context`
are caught, logged as warnings, and replaced with empty context:

```python
except MiraelError:
    raise            # propagate SDK errors (e.g. auth failure)
except Exception:
    return []        # degrade gracefully (e.g. Qdrant temporarily down)
```

**Rationale:** A Qdrant outage should not prevent a user from getting a
response about their positions.  The LLM can still answer from its training
knowledge without RAG context.  `MiraelError` subtypes (e.g.
`AuthenticationError`) are re-raised because they indicate a configuration
problem that the user must fix.

**Alternative considered:** Fail the entire turn on any context error.
Rejected: too fragile for a real-time trading assistant.

### 3. Sliding-window memory (pair-safe trim)

Memory keeps the last `max_turns` user+assistant pairs.  Trimming removes
complete pairs from the front:

```python
while len(self._messages) > max_messages:
    self._messages = self._messages[2:]  # drop oldest pair
```

**Rationale:** Removing individual messages (not pairs) could produce a
conversation starting with an assistant message, which some LLMs handle
poorly.  Pair-safe trim preserves structural validity.

**Alternative considered:** Token-count-based truncation.  Rejected for
Phase 3: requires an accurate tokeniser (tiktoken or equivalent); adds a
dependency; turn-count trimming is good enough for typical conversations.
Can be revisited in a future phase.

### 4. Protocol-based dependency injection

`Agent.__init__` accepts `LLMProvider`, `Retriever`, and `OnchainReader`
interfaces — not concrete classes:

```python
def __init__(
    self,
    llm: LLMProvider,
    *,
    retriever: Retriever | None = None,
    chain_reader: OnchainReader | None = None,
    ...
)
```

**Rationale:** Callers can inject mocks in tests without patching.  A future
`GeminiLLM` or `EVMReader` requires zero changes to `Agent`.  The dependency
graph rule (agent layer never imports llm/chains implementations directly)
is enforced structurally.

### 5. Separate `AgentConfig` from constructor kwargs

Agent behaviour (persona, limits) is encapsulated in a `Pydantic` model
rather than scattered as constructor parameters:

```python
config = AgentConfig(
    name="HyperAssist",
    protocol_name="Hyperliquid",
    system_instructions="...",
    max_rag_results=5,
    max_memory_turns=15,
)
agent = Agent(llm=llm, config=config)
```

**Rationale:** `AgentConfig` is serialisable and storable (e.g. per-tenant
config in a database).  Adding a new config field does not break existing
callers who don't pass it.

## Consequences

- `Agent` has no opinions about which LLM, store, or chain is used.
- All unit tests can inject `AsyncMock` objects without patching imports.
- Context failures produce degraded but functional responses.
- Memory is bounded; long conversations drop old context from the front.
