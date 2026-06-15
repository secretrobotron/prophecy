"""Tests for the RunPod Serverless AIProvider implementation.

All HTTP traffic is mocked through the OpenAI client constructor so the
suite runs offline. Environment-variable behavior is exercised via
``patch.dict(os.environ, ...)`` instead of touching the real shell.
"""

import os
from unittest.mock import Mock, patch

import openai
import pytest

from prophecy.providers import (
    AIProviderError,
    AIProviderFactory,
    RunPodServerlessProvider,
)

# All tests mock at the shared base where OpenAI is actually imported,
# so the patch point doesn't drift when providers are refactored.
OPENAI_PATCH = "prophecy.providers._openai_compat.OpenAI"


class TestRunPodConstruction:
    def test_init_derives_base_url_from_endpoint_id(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            provider = RunPodServerlessProvider(
                api_key="rpa_test",
                endpoint_id="abc123",
            )
            assert provider.endpoint_id == "abc123"
            assert provider.base_url == ("https://api.runpod.ai/v2/abc123/openai/v1")
            mock_openai.assert_called_once()
            kw = mock_openai.call_args.kwargs
            assert kw["base_url"] == "https://api.runpod.ai/v2/abc123/openai/v1"
            assert kw["api_key"] == "rpa_test"
            # Cold-start-aware default timeout flows through to the client.
            assert kw["timeout"] == RunPodServerlessProvider.DEFAULT_TIMEOUT

    def test_explicit_base_url_overrides_endpoint_id(self):
        """Useful for custom RunPod domains or pointing at sibling services."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            RunPodServerlessProvider(
                api_key="k",
                endpoint_id="ignored",
                base_url="https://my-custom-domain.example/v1",
            )
            kw = mock_openai.call_args.kwargs
            assert kw["base_url"] == "https://my-custom-domain.example/v1"

    def test_endpoint_id_from_env(self):
        with (
            patch.dict(
                os.environ,
                {"RUNPOD_ENDPOINT_ID": "from-env"},
                clear=True,
            ),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            provider = RunPodServerlessProvider(api_key="k")
            assert provider.endpoint_id == "from-env"
            assert (
                mock_openai.call_args.kwargs["base_url"]
                == "https://api.runpod.ai/v2/from-env/openai/v1"
            )

    def test_api_key_from_env(self):
        with (
            patch.dict(
                os.environ,
                {"RUNPOD_API_KEY": "rpa_env_secret"},
                clear=True,
            ),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            RunPodServerlessProvider(endpoint_id="abc")
            assert mock_openai.call_args.kwargs["api_key"] == "rpa_env_secret"

    def test_missing_endpoint_id_raises(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH),
            pytest.raises(AIProviderError, match="requires an endpoint_id"),
        ):
            RunPodServerlessProvider(api_key="k")

    def test_missing_api_key_raises(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH),
            pytest.raises(AIProviderError, match="requires an API key"),
        ):
            RunPodServerlessProvider(endpoint_id="abc")

    def test_default_model_is_qwen_14b(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH),
        ):
            p = RunPodServerlessProvider(api_key="k", endpoint_id="x")
            assert p.model == "Qwen/Qwen2.5-14B-Instruct"

    def test_timeout_can_be_overridden(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            RunPodServerlessProvider(api_key="k", endpoint_id="x", timeout=60)
            assert mock_openai.call_args.kwargs["timeout"] == 60


class TestRunPodPostPrompt:
    def _provider(self, mock_openai):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"answer":true,"reason":"x","certainty":80}'
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        return (
            RunPodServerlessProvider(api_key="k", endpoint_id="abc"),
            mock_client,
        )

    def test_success_pins_json_format(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            provider, mock_client = self._provider(mock_openai)
            response = provider.post_prompt("Test prompt")
            assert response.startswith("{")
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == "Qwen/Qwen2.5-14B-Instruct"
            assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_connection_error_hints_at_cold_start(self):
        """The single most likely failure mode after idle — surface it
        as a clear hint instead of a raw APIConnectionError."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = openai.APIConnectionError(
                request=Mock()
            )
            mock_openai.return_value = mock_client
            provider = RunPodServerlessProvider(api_key="k", endpoint_id="abc")
            with pytest.raises(AIProviderError, match="cold start"):
                provider.post_prompt("Test")

    def test_not_found_hints_at_model_loaded(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = openai.NotFoundError(
                message="model not found",
                response=Mock(status_code=404, headers={}),
                body=None,
            )
            mock_openai.return_value = mock_client
            provider = RunPodServerlessProvider(api_key="k", endpoint_id="abc", model="ghost-model")
            with pytest.raises(AIProviderError, match="not loaded"):
                provider.post_prompt("Test")


class TestRunPodEngineId:
    def test_engine_id_includes_model(self):
        """engine_id is part of the cache key, so swapping models must
        invalidate cached answers — even across providers."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH),
        ):
            p7 = RunPodServerlessProvider(
                api_key="k", endpoint_id="x", model="Qwen/Qwen2.5-7B-Instruct"
            )
            p14 = RunPodServerlessProvider(
                api_key="k", endpoint_id="x", model="Qwen/Qwen2.5-14B-Instruct"
            )
            assert p7.engine_id == "runpod:Qwen/Qwen2.5-7B-Instruct"
            assert p14.engine_id == "runpod:Qwen/Qwen2.5-14B-Instruct"
            assert p7.engine_id != p14.engine_id


class TestRunPodFactoryRegistration:
    def test_resolves_via_factory(self):
        with (
            patch.dict(os.environ, {"RUNPOD_API_KEY": "k"}, clear=True),
            patch(OPENAI_PATCH),
        ):
            for name in (
                "runpod",
                "runpod-serverless",
                "RunPod",
                "RUNPOD-SERVERLESS",
            ):
                p = AIProviderFactory.create_provider(name, endpoint_id="abc")
                assert isinstance(p, RunPodServerlessProvider), name

    def test_factory_passes_settings_through(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            AIProviderFactory.create_provider(
                "runpod",
                api_key="k",
                endpoint_id="abc",
                model="custom-model",
                timeout=30,
            )
            kw = mock_openai.call_args.kwargs
            assert kw["base_url"] == "https://api.runpod.ai/v2/abc/openai/v1"
            assert kw["api_key"] == "k"
            assert kw["timeout"] == 30
