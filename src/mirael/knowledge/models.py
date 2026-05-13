"""Shared data models for the knowledge / RAG layer."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


def _new_id() -> str:
    return str(uuid.uuid4())


class Document(BaseModel):
    """
    A source document to be ingested into the knowledge base.

    Attributes:
        id: Auto-generated UUID string.
        url: Canonical URL or file path of the source.
        title: Human-readable title (used in retrieval context).
        content: Full raw text content.
        metadata: Arbitrary key-value pairs for filtering.
    """

    id: str = Field(default_factory=_new_id)
    url: str
    title: str
    content: str
    metadata: dict[str, str] = Field(default_factory=dict)


class Chunk(BaseModel):
    """
    A text chunk derived from a ``Document``.

    Attributes:
        id: Auto-generated UUID string (used as Qdrant point ID).
        document_id: ID of the parent ``Document``.
        text: Chunk text content.
        source_url: URL of the source document.
        section_title: Title or heading of the containing section.
        chunk_index: Zero-based position within the document.
    """

    id: str = Field(default_factory=_new_id)
    document_id: str
    text: str
    source_url: str
    section_title: str
    chunk_index: int


class SearchResult(BaseModel):
    """A single Qdrant search hit, including the retrieved chunk."""

    chunk: Chunk
    score: float
    point_id: str


class RetrievalResult(BaseModel):
    """Top-level retrieval result returned to the agent."""

    chunk: Chunk
    score: float
