"""
In-memory sliding-window conversation memory.

Keeps the last ``max_turns`` user/assistant pairs so the LLM maintains
context across multi-turn conversations without growing the context
window unboundedly.
"""

from __future__ import annotations

from mirael.llm.models import ChatMessage


class InMemoryConversationMemory:
    """
    Stores a fixed-window list of ``ChatMessage`` objects.

    The window is maintained as a flat list of alternating user/assistant
    messages.  When the window is full, the *oldest* pair is dropped first,
    always preserving message-pair integrity (no orphaned roles).

    Args:
        max_turns: Maximum number of user+assistant pairs to retain.
                   A turn is one user message and one assistant reply.
    """

    def __init__(self, max_turns: int = 20) -> None:
        if max_turns < 1:
            raise ValueError(f"max_turns must be >= 1, got {max_turns}")
        self._max_turns = max_turns
        self._messages: list[ChatMessage] = []

    # ── Mutation ──────────────────────────────────────────────────────────────

    def add_user(self, content: str) -> None:
        """Append a user message and trim if necessary."""
        self._messages.append(ChatMessage(role="user", content=content))
        self._trim()

    def add_assistant(self, content: str) -> None:
        """Append an assistant message and trim if necessary."""
        self._messages.append(ChatMessage(role="assistant", content=content))
        self._trim()

    def clear(self) -> None:
        """Remove all messages from memory."""
        self._messages.clear()

    # ── Accessors ─────────────────────────────────────────────────────────────

    def get_messages(self) -> list[ChatMessage]:
        """
        Return a shallow copy of the current message list.

        Returns a copy so callers cannot mutate internal state.
        """
        return list(self._messages)

    @property
    def turn_count(self) -> int:
        """Number of complete user+assistant pairs stored."""
        return len(self._messages) // 2

    @property
    def message_count(self) -> int:
        """Raw number of messages (may be odd during a streaming turn)."""
        return len(self._messages)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _trim(self) -> None:
        """
        Drop the oldest pair when the window exceeds ``max_turns``.

        Always removes messages in pairs (user + assistant) to keep
        the conversation structurally valid.
        """
        max_messages = self._max_turns * 2
        while len(self._messages) > max_messages:
            # Drop the oldest pair (index 0 and 1)
            self._messages = self._messages[2:]
