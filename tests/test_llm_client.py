"""Tests for LLMClient — unified Anthropic/OpenAI wrapper."""
import json
import os
from unittest.mock import MagicMock, patch
from agent.config import get_llm_client, LLMClient


class TestGetLLMClient:
    """Test the factory function that creates the right client type."""

    @patch("agent.config.anthropic.Anthropic")
    def test_anthropic_without_base_url(self, mock_anthropic):
        """When ANTHROPIC_BASE_URL is not set, creates Anthropic client."""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "sk-test-key",
        }, clear=True):
            os.environ.pop("ANTHROPIC_BASE_URL", None)
            os.environ.pop("LLM_PROVIDER", None)
            client = get_llm_client()
            assert client.provider == "anthropic"

    @patch("agent.config.openai.OpenAI")
    def test_openai_with_explicit_provider(self, mock_openai):
        """When LLM_PROVIDER=openai, creates OpenAI client even without base_url."""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "sk-test-key",
            "LLM_PROVIDER": "openai",
        }, clear=True):
            client = get_llm_client()
            assert client.provider == "openai"

    @patch("agent.config.openai.OpenAI")
    def test_openai_with_custom_base_url(self, mock_openai):
        """When ANTHROPIC_BASE_URL is set to non-anthropic host, auto-detects OpenAI."""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "sk-test-key",
            "ANTHROPIC_BASE_URL": "https://router.shengsuanyun.com/api/v1",
        }, clear=True):
            os.environ.pop("LLM_PROVIDER", None)
            client = get_llm_client()
            assert client.provider == "openai"

    @patch("agent.config.anthropic.Anthropic")
    def test_anthropic_with_official_base_url(self, mock_anthropic):
        """When base_url is api.anthropic.com, stays as Anthropic."""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "sk-test-key",
            "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
        }, clear=True):
            os.environ.pop("LLM_PROVIDER", None)
            client = get_llm_client()
            assert client.provider == "anthropic"


class TestLLMClientCreateMessage:
    """Test unified create_message interface for both providers."""

    @patch("agent.config.anthropic.Anthropic")
    @patch("agent.config.MODEL_ID", "claude-sonnet-4-6")
    def test_anthropic_create_message(self, mock_anthropic_class):
        """Anthropic provider delegates to anthropic SDK with cache_control preserved."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response text")]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}, clear=True):
            os.environ.pop("ANTHROPIC_BASE_URL", None)
            os.environ.pop("LLM_PROVIDER", None)
            client = get_llm_client()

        system_blocks = [
            {"type": "text", "text": "Base prompt", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "Task prompt", "cache_control": {"type": "ephemeral"}},
        ]
        result = client.create_message(
            system_prompts=system_blocks,
            user_content="user input",
            max_tokens=2048,
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["max_tokens"] == 2048
        assert call_kwargs["messages"] == [{"role": "user", "content": "user input"}]
        assert call_kwargs["system"] == system_blocks
        assert result == "response text"

    @patch("agent.config.openai.OpenAI")
    @patch("agent.config.MODEL_ID", "claude-sonnet-4-6")
    def test_openai_create_message(self, mock_openai_class):
        """OpenAI provider delegates to openai SDK with proper format translation."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="openai response"))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "sk-test-key",
            "LLM_PROVIDER": "openai",
        }, clear=True):
            client = get_llm_client()

        system_blocks = [
            {"type": "text", "text": "Base prompt", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "Task prompt", "cache_control": {"type": "ephemeral"}},
        ]
        result = client.create_message(
            system_prompts=system_blocks,
            user_content="user input",
            max_tokens=2048,
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["max_completion_tokens"] == 2048
        messages = call_kwargs["messages"]
        assert len(messages) == 3
        assert messages[0] == {"role": "system", "content": "Base prompt"}
        assert messages[1] == {"role": "system", "content": "Task prompt"}
        assert messages[2] == {"role": "user", "content": "user input"}
        for msg in messages:
            assert "cache_control" not in msg
        assert result == "openai response"

    @patch("agent.config.openai.OpenAI")
    @patch("agent.config.MODEL_ID", "deepseek/deepseek-v4-flash")
    def test_openai_uses_model_id_from_env(self, mock_openai_class):
        """OpenAI provider reads MODEL_ID from module-level config."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="ok"))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "sk-test-key",
            "LLM_PROVIDER": "openai",
        }, clear=True):
            client = get_llm_client()

        client.create_message(
            system_prompts=[{"type": "text", "text": "prompt"}],
            user_content="hi",
            max_tokens=512,
        )
        assert mock_client.chat.completions.create.call_args.kwargs["model"] == "deepseek/deepseek-v4-flash"

    @patch("agent.config.anthropic.Anthropic")
    @patch("agent.config.MODEL_ID", "claude-sonnet-4-6")
    def test_no_cache_control_key_in_system(self, mock_anthropic_class):
        """System prompts without cache_control work fine with Anthropic."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}, clear=True):
            os.environ.pop("ANTHROPIC_BASE_URL", None)
            os.environ.pop("LLM_PROVIDER", None)
            client = get_llm_client()

        client.create_message(
            system_prompts=[{"type": "text", "text": "simple prompt"}],
            user_content="hi",
            max_tokens=100,
        )
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == [{"type": "text", "text": "simple prompt"}]


def test_create_message_logs_trace(tmp_path):
    """create_message writes a trace entry when logger is initialized."""
    from agent.logger import init_logs

    init_logs(tmp_path)

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}, clear=True):
        os.environ.pop("ANTHROPIC_BASE_URL", None)
        os.environ.pop("LLM_PROVIDER", None)

        with patch("agent.config.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="traced response")]
            mock_client.messages.create.return_value = mock_response

            client = get_llm_client()
            client.create_message(
                system_prompts=[{"type": "text", "text": "test prompt"}],
                user_content="test input",
                max_tokens=100,
                node_name="test_node",
            )

    trace_content = (tmp_path / "trace.log").read_text()
    assert "test_node" in trace_content
    assert "traced response" in trace_content
    entry = json.loads(trace_content.strip().split("\n")[0])
    assert entry["node"] == "test_node"
    assert entry["provider"] == "anthropic"
