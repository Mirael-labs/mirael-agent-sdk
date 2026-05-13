# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 1: project bootstrap, DevOps toolchain, core config/logging/exceptions modules
- Phase 2: AnthropicLLM (retry, caching, streaming), OpenAIEmbeddings, QdrantVectorStore, SemanticChunker, IngestPipeline, Retriever — 79 unit tests
- Phase 3: Agent class (RAG + chain + LLM orchestration, graceful degradation, streaming), InMemoryConversationMemory, AgentConfig/AgentResponse, build_system_prompt — 43 unit tests
- Phase 4: HyperliquidReader (httpx + tenacity retry, all 5 OnchainReader methods, Pydantic models) — 22 unit tests + 8 integration tests
- Phase 5: working terminal demo (ingest_docs.py + streaming chat REPL), ADR-0002 (agent orchestration decisions), updated README with demo walkthrough and coverage

## [0.1.0] - 2026-05-12

### Added
- Initial project scaffold
- `pyproject.toml` with full dependency set and tool configuration (ruff, mypy, pytest, bandit)
- `.pre-commit-config.yaml` with ruff, mypy, bandit, pip-audit hooks
- GitHub Actions CI workflow (lint + types + tests + security)
- Docker Compose for local Qdrant instance
- Railway deployment config
- `config.py`: Pydantic Settings with fail-fast validation
- `logging.py`: structlog with JSON (prod) / console (dev) renderers
- `exceptions.py`: typed error hierarchy (`MiraelError`, `ConfigurationError`, `LLMError`, etc.)
- Architecture documentation with Mermaid diagram
- ADR-0001: tech stack decision record
