#!/usr/bin/env python3
"""
Mirael Agent — Telegram Bot demo.

Prerequisites:
  1. uv add 'python-telegram-bot>=20.7'
  2. Set in .env:
       MIRAEL_ANTHROPIC_API_KEY=...
       MIRAEL_OPENAI_API_KEY=...
       MIRAEL_TELEGRAM_BOT_TOKEN=...
       MIRAEL_HL_WALLET_ADDRESS=...  (or use /setwallet in chat)

Usage:
  uv run python examples/telegram_demo/bot.py
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    from mirael.agent.base import Agent
    from mirael.agent.models import AgentConfig
    from mirael.chains.hyperliquid import HyperliquidReader
    from mirael.channels.telegram import create_adapter_from_settings
    from mirael.config import load_settings
    from mirael.knowledge.retriever import Retriever
    from mirael.knowledge.vector_store import QdrantVectorStore
    from mirael.llm.anthropic import AnthropicLLM
    from mirael.logging import configure_logging

    settings = load_settings()
    configure_logging(level=settings.log_level, environment=settings.environment)

    llm = AnthropicLLM(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.llm_model,
    )
    from mirael.knowledge.embeddings import create_from_settings as create_embeddings
    embeddings = create_embeddings(settings)
    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        collection=settings.qdrant_collection,
        vector_dim=settings.embedding_dimensions,
    )
    retriever = Retriever(embeddings=embeddings, vector_store=vector_store)
    chain_reader = HyperliquidReader(network=settings.hl_network)

    config = AgentConfig(
        name="MiraelBot",
        protocol_name="Hyperliquid",
        system_instructions=(
            "You are a precise DeFi assistant. "
            "Keep answers concise for Telegram. "
            "Use plain text or minimal Markdown."
        ),
    )

    agent = Agent(
        llm=llm,
        retriever=retriever,
        chain_reader=chain_reader,
        config=config,
    )

    async with chain_reader:
        adapter = create_adapter_from_settings(settings, agent)
        await adapter.start()


if __name__ == "__main__":
    asyncio.run(main())
