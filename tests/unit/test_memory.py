"""Unit tests for InMemoryConversationMemory."""

from __future__ import annotations

import pytest

from mirael.agent.memory import InMemoryConversationMemory
from mirael.llm.models import ChatMessage


class TestInMemoryConversationMemory:
    def test_starts_empty(self) -> None:
        mem = InMemoryConversationMemory()
        assert mem.get_messages() == []
        assert mem.turn_count == 0
        assert mem.message_count == 0

    def test_add_user_stores_message(self) -> None:
        mem = InMemoryConversationMemory()
        mem.add_user("hello")
        msgs = mem.get_messages()
        assert len(msgs) == 1
        assert msgs[0].role == "user"
        assert msgs[0].content == "hello"

    def test_add_assistant_stores_message(self) -> None:
        mem = InMemoryConversationMemory()
        mem.add_user("hi")
        mem.add_assistant("hello there")
        msgs = mem.get_messages()
        assert msgs[1].role == "assistant"
        assert msgs[1].content == "hello there"

    def test_turn_count_increments_per_pair(self) -> None:
        mem = InMemoryConversationMemory()
        assert mem.turn_count == 0
        mem.add_user("q1")
        mem.add_assistant("a1")
        assert mem.turn_count == 1
        mem.add_user("q2")
        mem.add_assistant("a2")
        assert mem.turn_count == 2

    def test_get_messages_returns_copy(self) -> None:
        mem = InMemoryConversationMemory()
        mem.add_user("hello")
        copy = mem.get_messages()
        copy.append(ChatMessage(role="assistant", content="extra"))
        # Original should be unchanged
        assert mem.message_count == 1

    def test_clear_empties_all_messages(self) -> None:
        mem = InMemoryConversationMemory()
        mem.add_user("q")
        mem.add_assistant("a")
        mem.clear()
        assert mem.get_messages() == []
        assert mem.turn_count == 0

    def test_trim_at_max_turns(self) -> None:
        mem = InMemoryConversationMemory(max_turns=2)
        mem.add_user("q1")
        mem.add_assistant("a1")
        mem.add_user("q2")
        mem.add_assistant("a2")
        # Adding a 3rd pair should drop the 1st
        mem.add_user("q3")
        mem.add_assistant("a3")
        msgs = mem.get_messages()
        assert len(msgs) == 4  # 2 pairs
        assert msgs[0].content == "q2"
        assert msgs[1].content == "a2"
        assert msgs[2].content == "q3"
        assert msgs[3].content == "a3"

    def test_trim_preserves_pair_integrity(self) -> None:
        mem = InMemoryConversationMemory(max_turns=1)
        mem.add_user("old_q")
        mem.add_assistant("old_a")
        mem.add_user("new_q")
        mem.add_assistant("new_a")
        msgs = mem.get_messages()
        # Only the newest pair should remain
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"

    def test_max_turns_one_is_valid(self) -> None:
        mem = InMemoryConversationMemory(max_turns=1)
        mem.add_user("a")
        mem.add_assistant("b")
        assert mem.turn_count == 1

    def test_max_turns_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="max_turns"):
            InMemoryConversationMemory(max_turns=0)

    def test_message_count_odd_during_streaming(self) -> None:
        mem = InMemoryConversationMemory()
        mem.add_user("question")
        assert mem.message_count == 1
        assert mem.turn_count == 0  # incomplete pair

    def test_large_window_no_trim(self) -> None:
        mem = InMemoryConversationMemory(max_turns=10)
        for i in range(10):
            mem.add_user(f"q{i}")
            mem.add_assistant(f"a{i}")
        assert mem.turn_count == 10
        assert mem.message_count == 20
