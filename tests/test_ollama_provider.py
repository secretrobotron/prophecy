"""Tests for the Ollama AIProvider implementation.

All HTTP traffic is mocked through the same patch point ChatGPT tests use
(``OpenAI`` constructor), so these run offline.
"""

from unittest.mock import Mock, patch

import openai
import pytest

from prophecy.providers import (
    AIProviderError,
    AIProviderFactory,
    OllamaProvider,
)


class TestOllamaProvider:
    def test_init_with_defaults(self):
        with patch("prophecy.providers._openai_compat.OpenAI") as mock_openai:
            provider = OllamaProvider()
            assert provider.model == OllamaProvider.DEFAULT_MODEL
            assert provider.base_url == OllamaProvider.DEFAULT_BASE_URL
            assert provider.max_tokens == OllamaProvider.DEFAULT_MAX_TOKENS
            assert provider.temperature == OllamaProvider.DEFAULT_TEMPERATURE
            # The constructor should pass the placeholder "ollama" key when
            # caller didn't supply one — the OpenAI client refuses empties.
            mock_openai.assert_called_once_with(
                api_key="ollama", base_url=OllamaProvider.DEFAULT_BASE_URL
            )

    def test_init_with_custom_model_and_base_url(self):
        with patch("prophecy.providers._openai_compat.OpenAI") as mock_openai:
            provider = OllamaProvider(
                model="qwen2.5:14b-instruct",
                base_url="http://192.168.1.50:11434/v1",
            )
            assert provider.model == "qwen2.5:14b-instruct"
            assert provider.base_url == "http://192.168.1.50:11434/v1"
            mock_openai.assert_called_once_with(
                api_key="ollama", base_url="http://192.168.1.50:11434/v1"
            )

    def test_init_with_explicit_api_key_overrides_placeholder(self):
        with patch("prophecy.providers._openai_compat.OpenAI") as mock_openai:
            OllamaProvider(api_key="secret-via-proxy")
            mock_openai.assert_called_once_with(
                api_key="secret-via-proxy", base_url=OllamaProvider.DEFAULT_BASE_URL
            )

    def test_post_prompt_success_requests_json_format(self):
        """The Ollama call should pin response_format=json_object so the
        prompt template's 'pure and valid JSON' contract is enforced
        server-side instead of relying on the model behaving."""
        with patch("prophecy.providers._openai_compat.OpenAI") as mock_openai:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = '{"answer":true,"reason":"x","certainty":80}'
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            provider = OllamaProvider()
            response = provider.post_prompt("Test prompt")

            assert response == '{"answer":true,"reason":"x","certainty":80}'
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == OllamaProvider.DEFAULT_MODEL
            assert call_kwargs["response_format"] == {"type": "json_object"}
            assert call_kwargs["messages"][0]["role"] == "user"

    def test_post_prompt_with_system_message(self):
        with patch("prophecy.providers._openai_compat.OpenAI") as mock_openai:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "ok"
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            provider = OllamaProvider()
            provider.post_prompt("Test", system_message="Be terse")
            msgs = mock_client.chat.completions.create.call_args.kwargs["messages"]
            assert msgs[0] == {"role": "system", "content": "Be terse"}
            assert msgs[1] == {"role": "user", "content": "Test"}

    def test_post_prompt_empty_raises(self):
        with patch("prophecy.providers._openai_compat.OpenAI"):
            provider = OllamaProvider()
            with pytest.raises(AIProviderError, match="Prompt cannot be empty"):
                provider.post_prompt("")

    def test_post_prompt_connection_error_hints_at_daemon(self):
        """When the daemon isn't running, surface a clear message instead
        of a raw APIConnectionError — this is the single most common
        first-run failure for local users."""
        with patch("prophecy.providers._openai_compat.OpenAI") as mock_openai:
            mock_client = Mock()
            # APIConnectionError requires a Request kwarg in newer openai
            # versions; construct it the safe way through its protocol.
            err = openai.APIConnectionError(request=Mock())
            mock_client.chat.completions.create.side_effect = err
            mock_openai.return_value = mock_client

            provider = OllamaProvider()
            with pytest.raises(AIProviderError, match="is the daemon running"):
                provider.post_prompt("Test")

    def test_post_prompt_not_found_hints_at_pull(self):
        with patch("prophecy.providers._openai_compat.OpenAI") as mock_openai:
            mock_client = Mock()
            err = openai.NotFoundError(
                message="model not found",
                response=Mock(status_code=404, headers={}),
                body=None,
            )
            mock_client.chat.completions.create.side_effect = err
            mock_openai.return_value = mock_client

            provider = OllamaProvider(model="not-a-real-model")
            with pytest.raises(AIProviderError, match="ollama pull not-a-real-model"):
                provider.post_prompt("Test")

    def test_engine_id_includes_model(self):
        """engine_id is used as part of the cache key; it must change when
        the model changes so swapping qwen 7b → 14b doesn't reuse old
        cached answers."""
        with patch("prophecy.providers._openai_compat.OpenAI"):
            p7 = OllamaProvider(model="qwen2.5:7b-instruct")
            p14 = OllamaProvider(model="qwen2.5:14b-instruct")
            assert p7.engine_id == "ollama:qwen2.5:7b-instruct"
            assert p14.engine_id == "ollama:qwen2.5:14b-instruct"
            assert p7.engine_id != p14.engine_id

    def test_validate_configuration(self):
        with patch("prophecy.providers._openai_compat.OpenAI"):
            assert OllamaProvider().validate_configuration() is True


class TestFactoryRegistration:
    def test_ollama_resolves_via_factory(self):
        with patch("prophecy.providers._openai_compat.OpenAI"):
            for name in ("ollama", "local", "Ollama", "LOCAL"):
                p = AIProviderFactory.create_provider(name)
                assert isinstance(p, OllamaProvider), name

    def test_factory_passes_through_model_and_base_url(self):
        with patch("prophecy.providers._openai_compat.OpenAI") as mock_openai:
            AIProviderFactory.create_provider(
                "ollama",
                model="qwen2.5:14b-instruct",
                base_url="http://otherhost:11434/v1",
            )
            mock_openai.assert_called_once_with(
                api_key="ollama", base_url="http://otherhost:11434/v1"
            )
