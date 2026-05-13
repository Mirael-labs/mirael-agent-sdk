"""Unit tests for AnthropicLLM."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from mirael.exceptions import AuthenticationError, LLMError
from mirael.llm.anthropic import AnthropicLLM
from mirael.llm.models import ChatMessage, LLMResponse


def _make_response(
    text: str = "Hello!", input_tokens: int = 10, output_tokens: int = 5
) -> MagicMock:
    response = MagicMock()
    block = MagicMock()
    block.text = text
    response.content = [block]
    response.stop_reason = "end_turn"
    response.model = "claude-sonnet-4-5"
    response.usage = MagicMock()
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    response.usage.cache_read_input_tokens = 0
    response.usage.cache_creation_input_tokens = 0
    return response


@pytest.fixture()
def mock_async_anthropic() -> MagicMock:
    with patch("anthropic.AsyncAnthropic") as mock_cls:
        instance = AsyncMock()
        mock_cls.return_value = instance
        instance.messages.create = AsyncMock(return_value=_make_response())
        yield instance


class TestAnthropicLLMChat:
    async def test_returns_llm_response(self, mock_async_anthropic: MagicMock) -> None:
        llm = AnthropicLLM(api_key="sk-test")
        result = await llm.chat([ChatMessage(role="user", content="Hi")])
        assert isinstance(result, LLMResponse)
        assert result.text == "Hello!"
        assert result.input_tokens == 10
        assert result.output_tokens == 5

    async def test_total_tokens_property(self, mock_async_anthropic: MagicMock) -> None:
        llm = AnthropicLLM(api_key="sk-test")
        result = await llm.chat([ChatMessage(role="user", content="Hi")])
        assert result.total_tokens == 15

    async def test_system_prompt_included(self, mock_async_anthropic: MagicMock) -> None:
        llm = AnthropicLLM(api_key="sk-test")
        await llm.chat([ChatMessage(role="user", content="Hi")], system="You are helpful.")
        call_kwargs = mock_async_anthropic.messages.create.call_args.kwargs
        assert "system" in call_kwargs
        assert call_kwargs["system"][0]["text"] == "You are helpful."

    async def test_cache_control_on_system(self, mock_async_anthropic: MagicMock) -> None:
        llm = AnthropicLLM(api_key="sk-test", cache_system_prompt=True)
        await llm.chat([ChatMessage(role="user", content="Hi")], system="sys")
        call_kwargs = mock_async_anthropic.messages.create.call_args.kwargs
        assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}

    async def test_no_cache_when_disabled(self, mock_async_anthropic: MagicMock) -> None:
        llm = AnthropicLLM(api_key="sk-test", cache_system_prompt=False)
        await llm.chat([ChatMessage(role="user", content="Hi")], system="sys")
        call_kwargs = mock_async_anthropic.messages.create.call_args.kwargs
        assert "cache_control" not in call_kwargs["system"][0]

    async def test_no_system_key_when_empty(self, mock_async_anthropic: MagicMock) -> None:
        llm = AnthropicLLM(api_key="sk-test")
        await llm.chat([ChatMessage(role="user", content="Hi")])
        call_kwargs = mock_async_anthropic.messages.create.call_args.kwargs
        assert "system" not in call_kwargs

    async def test_auth_error_converted(self) -> None:
        import anthropic

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            instance = AsyncMock()
            mock_cls.return_value = instance
            instance.messages.create.side_effect = anthropic.AuthenticationError(
                message="Invalid key", response=MagicMock(status_code=401), body={}
            )
            llm = AnthropicLLM(api_key="bad-key")
            with pytest.raises(AuthenticationError):
                await llm.chat([ChatMessage(role="user", content="Hi")])

    async def test_api_status_error_converted(self) -> None:
        import anthropic

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            instance = AsyncMock()
            mock_cls.return_value = instance
            err = anthropic.APIStatusError(
                message="Server error",
                response=MagicMock(status_code=500),
                body={},
            )
            instance.messages.create.side_effect = err
            llm = AnthropicLLM(api_key="sk-test")
            with pytest.raises(LLMError):
                await llm.chat([ChatMessage(role="user", content="Hi")])


class TestAnthropicLLMStream:
    def test_stream_returns_async_iterator(self) -> None:
        with patch("anthropic.AsyncAnthropic"):
            llm = AnthropicLLM(api_key="sk-test")
            result = llm.stream_chat([ChatMessage(role="user", content="Hi")])
            assert hasattr(result, "__aiter__")


class TestChatMessageModel:
    def test_valid_user_message(self) -> None:
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"

    def test_valid_assistant_message(self) -> None:
        msg = ChatMessage(role="assistant", content="world")
        assert msg.role == "assistant"

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatMessage(role="system", content="oops")  # type: ignore[arg-type]
