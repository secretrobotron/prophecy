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
    FatalAIProviderError,
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

    def test_context_length_exceeded_message_is_focused(self):
        """Hebrew Masoretic passages can be many thousands of tokens; the
        server's 400 body is huge and buries the actual problem. Our
        translator surfaces the 'context window' phrase and points at
        the right config knob so the user can fix it in seconds."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            mock_client = Mock()
            server_body = (
                "Error during inference: This model's maximum context "
                "length is 32768 tokens. However, you requested 1000 output "
                "tokens and your prompt contains at least 31769 input tokens"
            )
            mock_client.chat.completions.create.side_effect = openai.BadRequestError(
                message=server_body,
                response=Mock(status_code=400, headers={}),
                body=None,
            )
            mock_openai.return_value = mock_client
            provider = RunPodServerlessProvider(api_key="k", endpoint_id="abc")
            with pytest.raises(AIProviderError, match="context window") as exc:
                provider.post_prompt("Test")
            assert "max_tokens" in str(exc.value)
            # Original server message is preserved for diagnostics.
            assert "32768" in str(exc.value)


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


class TestRunPodFromTomlConfig:
    """End-to-end: Settings reads [providers.runpod] from prophecy.toml and
    the values (including api_key) reach the OpenAI client unmodified."""

    def test_api_key_flows_from_toml_via_settings(self, tmp_path):
        from prophecy.settings import Settings

        toml = tmp_path / "prophecy.toml"
        toml.write_text(
            'ai_provider = "runpod"\n'
            "[providers.runpod]\n"
            'api_key = "rpa_from_toml"\n'
            'endpoint_id = "abc-from-toml"\n'
            'model = "Qwen/Qwen2.5-7B-Instruct"\n'
            "timeout = 120\n",
            encoding="utf-8",
        )
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            settings = Settings.load(config_path=toml)
            # Mirror what initialize_ai_provider does in __main__.py — the
            # factory consumes provider_config(name) directly.
            kwargs = settings.provider_config(settings.ai_provider)
            AIProviderFactory.create_provider(settings.ai_provider, **kwargs)
        kw = mock_openai.call_args.kwargs
        assert kw["api_key"] == "rpa_from_toml"
        assert kw["base_url"] == "https://api.runpod.ai/v2/abc-from-toml/openai/v1"
        assert kw["timeout"] == 120


class TestVerifyModelAvailable:
    """The /v1/models pre-flight check that catches name mismatches
    before a batch run starts wasting compute on rejected calls.
    Lives on the shared OpenAICompatProvider base so it covers ollama too,
    but the motivating bug was a RunPod deploy serving a different model
    than the toml specified."""

    def _models_response(self, model_ids):
        """Build a mock matching the openai SDK's Page[Model] shape."""
        return Mock(data=[Mock(id=mid) for mid in model_ids])

    def test_success_returns_available_models(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            mock_client = Mock()
            mock_client.models.list.return_value = self._models_response(
                ["Qwen/Qwen2.5-14B-Instruct", "other/model"]
            )
            mock_openai.return_value = mock_client
            p = RunPodServerlessProvider(
                api_key="k",
                endpoint_id="abc",
                model="Qwen/Qwen2.5-14B-Instruct",
            )
            available = p.verify_model_available()
            assert "Qwen/Qwen2.5-14B-Instruct" in available

    def test_missing_model_raises_fatal_with_actual_list(self):
        """The exact failure mode that hid behind RunPod's 500 in
        production — endpoint serves 'qwen/qwen2.5-7b-instruct' while
        config asks for 'Qwen/Qwen2.5-14B-Instruct'. Error must surface
        the served name so the user can fix immediately."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            mock_client = Mock()
            mock_client.models.list.return_value = self._models_response(
                ["qwen/qwen2.5-7b-instruct"]
            )
            mock_openai.return_value = mock_client
            p = RunPodServerlessProvider(
                api_key="k",
                endpoint_id="abc",
                model="Qwen/Qwen2.5-14B-Instruct",
            )
            with pytest.raises(FatalAIProviderError) as exc:
                p.verify_model_available()
            assert "Qwen/Qwen2.5-14B-Instruct" in str(exc.value)
            assert "qwen/qwen2.5-7b-instruct" in str(exc.value)

    def test_truncates_long_model_list(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            many = [f"served-model-{i}" for i in range(12)]
            mock_client = Mock()
            mock_client.models.list.return_value = self._models_response(many)
            mock_openai.return_value = mock_client
            p = RunPodServerlessProvider(api_key="k", endpoint_id="abc", model="not-served")
            with pytest.raises(FatalAIProviderError) as exc:
                p.verify_model_available()
            # Show first few, plus a "N total" hint so the user knows the
            # list was clipped rather than being only 5 entries long.
            assert "12 total" in str(exc.value)

    def test_connection_error_is_non_fatal(self):
        """Network blip while *checking* shouldn't kill the run — let the
        caller decide. Real per-call retries cover the same surface."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            mock_client = Mock()
            mock_client.models.list.side_effect = openai.APIConnectionError(request=Mock())
            mock_openai.return_value = mock_client
            p = RunPodServerlessProvider(api_key="k", endpoint_id="abc")
            with pytest.raises(AIProviderError) as exc:
                p.verify_model_available()
            assert not isinstance(exc.value, FatalAIProviderError)

    def test_authentication_error_is_fatal(self):
        """Bad API key affects every subsequent call, not just the check —
        fatal so the user fixes the credential before paying for retries."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):
            mock_client = Mock()
            mock_client.models.list.side_effect = openai.AuthenticationError(
                message="bad key",
                response=Mock(status_code=401, headers={}),
                body=None,
            )
            mock_openai.return_value = mock_client
            p = RunPodServerlessProvider(api_key="k", endpoint_id="abc")
            with pytest.raises(FatalAIProviderError):
                p.verify_model_available()

    def test_factory_propagates_fatal_unwrapped(self):
        """The factory normally wraps construction exceptions in a generic
        AIProviderError. The fatal subclass must pass through so callers
        can distinguish it; otherwise the pipeline keeps retrying."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(OPENAI_PATCH) as mock_openai,
        ):

            class _BadInit(RunPodServerlessProvider):
                def __init__(self, *a, **kw):
                    raise FatalAIProviderError("bad")

            AIProviderFactory.register_provider("test-fatal", _BadInit)
            mock_openai.return_value = Mock()
            with pytest.raises(FatalAIProviderError):
                AIProviderFactory.create_provider("test-fatal", api_key="k", endpoint_id="x")
