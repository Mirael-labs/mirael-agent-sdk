# Open Questions

Questions that arose during development. Each has a recommendation so
work can proceed without blocking.

## Q1: OpenAI vs open-source embeddings

**Question:** ADR-0001 chose `text-embedding-3-large` (OpenAI). An earlier
version of this workspace used `BAAI/bge-large-en-v1.5` (self-hosted).
Should the SDK default to OpenAI or allow pluggable embedding providers?

**Options:**
1. OpenAI only (simpler, Phase 1 default) <- **recommended**
2. Protocol-based from day one (more flexible, more Phase 2 work)
3. Start with bge-large self-hosted (no extra API cost)

**Decision made:** Option 1 for Phase 1/2. The `llm/base.py` Protocol
approach makes it trivial to add an `EmbeddingProvider` Protocol in Phase 2
that can wrap either OpenAI or a self-hosted model.

---

## Q2: Single-tenant vs multi-tenant wallet handling

**Question:** Should the SDK treat one wallet per agent instance, or support
multi-wallet queries per session?

**Options:**
1. One wallet per agent instance (simpler DX) <- **recommended**
2. Wallet passed per-query (flexible but complex)

**Decision made:** Option 1. Pass wallet at agent construction time.
Multi-wallet support can be added as a higher-level wrapper in Phase 3+.

---

## Q3: Commitizen commit message format

**Question:** The pre-commit config includes commitizen for conventional
commits. Should the CI enforce this on all branches or only main?

**Decision made:** Enforce on commit-msg hook only (pre-commit). CI does
not re-check commit messages — that's a DX issue, not a CI issue.
