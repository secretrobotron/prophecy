"""
Shared base for providers that speak the OpenAI REST API but live elsewhere.

Ollama, vLLM-on-RunPod, and similar self-hosted/serverless inference
services all expose ``/v1/chat/completions`` with the same envelope shape
as OpenAI itself. Rather than duplicate the OpenAI client wiring,
response parsing, and error-to-AIProviderError translation in every
provider, we put it here and let concrete providers customize:

- ``NAME`` / ``DEFAULT_MODEL`` / ``DEFAULT_BASE_URL`` (class attributes)
- ``DEFAULT_API_KEY_PLACEHOLDER`` (e.g. Ollama uses ``"ollama"`` because
  the daemon ignores the key but the OpenAI client refuses empty strings)
- ``resolve_base_url`` (override when the URL is derived — e.g. RunPod
  computes it from an endpoint_id)
- ``_connection_hint`` / ``_not_found_hint`` (override to give users a
  service-specific nudge when something obvious is wrong, like "is the
  daemon running" or "is the endpoint awake")

Concrete providers in this folder: ``OllamaProvider``, ``RunPodServerlessProvider``.
"""

from __future__ import annotations

from typing import Any

import openai
from openai import OpenAI

from .base import AIProvider, AIProviderError, FatalAIProviderError


class OpenAICompatProvider(AIProvider):
    """Base class for OpenAI-API-compatible providers that aren't OpenAI."""

    # Subclasses override these.
    NAME: str = "openai-compat"
    DEFAULT_MODEL: str = ""
    DEFAULT_BASE_URL: str = ""
    # Set this when the upstream ignores the API key but the OpenAI client
    # still refuses an empty string (Ollama is the canonical example). Leave
    # empty for services that genuinely require a key.
    DEFAULT_API_KEY_PLACEHOLDER: str = ""

    # 500 is plenty for our JSON output ({answer, reason, certainty} — the
    # reason field is typically a 2-3 sentence paragraph ~100 tokens). The
    # reason it's not larger: most self-hosted / serverless OpenAI-compat
    # endpoints run smaller-context models (Qwen 2.5's 32K, Llama 3's 8K)
    # and the prompts include Hebrew Masoretic passages that already eat
    # most of the context window. Leaving max_tokens at OpenAI's 1000
    # default would push long-passage stories over the model's context
    # limit. Users with bigger-context models can override via
    # ``[providers.<name>] max_tokens = ...`` in prophecy.toml.
    DEFAULT_MAX_TOKENS: int = 500
    # Lower than OpenAI's default — judgment tasks shouldn't be creative.
    DEFAULT_TEMPERATURE: float = 0.2
    # None lets the OpenAI client pick its own default (currently 600s).
    # Subclasses can pin this when the service has known cold-start behavior.
    DEFAULT_TIMEOUT: float | None = None

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ):
        super().__init__(api_key, **kwargs)
        self.model = model or self.DEFAULT_MODEL
        self.base_url = self.resolve_base_url(base_url, kwargs)
        self.max_tokens = max_tokens if max_tokens is not None else self.DEFAULT_MAX_TOKENS
        self.temperature = temperature if temperature is not None else self.DEFAULT_TEMPERATURE
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

        effective_key = self.resolve_api_key()

        client_kwargs: dict[str, Any] = {
            "api_key": effective_key,
            "base_url": self.base_url,
        }
        if self.timeout is not None:
            client_kwargs["timeout"] = self.timeout

        try:
            self.client = OpenAI(**client_kwargs)
        except Exception as e:
            raise AIProviderError(
                f"Failed to initialize {self.NAME} client at {self.base_url}: {e}"
            ) from e

    # ---- Hooks for subclasses ----

    def resolve_base_url(self, base_url: str | None, kwargs: dict[str, Any]) -> str:
        """Override when the URL is computed from other config.

        ``kwargs`` is the trailing ``**kwargs`` from ``__init__`` so the
        override can read service-specific fields (e.g. RunPod reads
        ``endpoint_id``). The default just honors an explicit ``base_url``
        or falls back to ``DEFAULT_BASE_URL``.
        """
        return base_url or self.DEFAULT_BASE_URL

    def resolve_api_key(self) -> str:
        """Resolve the API key to send. Defaults: explicit > placeholder.

        Override to read service-specific env vars or to raise a friendly
        AIProviderError when the service genuinely requires a key and
        none was supplied.
        """
        if self.api_key:
            return self.api_key
        if self.DEFAULT_API_KEY_PLACEHOLDER:
            return self.DEFAULT_API_KEY_PLACEHOLDER
        raise AIProviderError(f"{self.NAME} requires an API key but none was provided")

    def _connection_hint(self, exc: Exception) -> str:
        """Override to give the user a service-specific hint when the
        OpenAI client raises APIConnectionError."""
        return f"could not reach {self.NAME} at {self.base_url}"

    def _not_found_hint(self, model: str, exc: Exception) -> str:
        """Override to give the user a hint when the model isn't found."""
        return f"model {model!r} not available at {self.base_url}"

    # ---- AIProvider interface ----

    def post_prompt(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system_message: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise AIProviderError("Prompt cannot be empty")

        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        messages: list[dict[str, str]] = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        # Pipeline expects parseable JSON ({answer, reason, certainty}).
        # Constraining generation server-side removes "almost-JSON" parse
        # failures that would otherwise force a re-run.
        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        request_kwargs.update(kwargs)

        try:
            response = self.client.chat.completions.create(**request_kwargs)
            content = response.choices[0].message.content
            if content is None:
                raise AIProviderError(f"{self.NAME} returned an empty response")
            return content.strip()
        except openai.APIConnectionError as e:
            raise AIProviderError(f"{self._connection_hint(e)} ({e})") from e
        except openai.NotFoundError as e:
            raise AIProviderError(f"{self._not_found_hint(model, e)} ({e})") from e
        except openai.APIError as e:
            # Context-length errors come back as a 400 BadRequestError with
            # 'maximum context length' or 'context_length_exceeded' in the
            # body. Translate to a focused message so the user can see
            # immediately which lever to pull (shorten prompt, bigger
            # model, lower max_tokens) instead of squinting at a 500-line
            # error body.
            msg = str(e)
            lower = msg.lower()
            if "maximum context length" in lower or "context_length_exceeded" in lower:
                raise AIProviderError(
                    f"{self.NAME}: prompt exceeded the model's context "
                    f"window. Lower max_tokens in [providers.{self.NAME}], "
                    f"deploy a larger-context model, or skip the offending "
                    f"story. Server said: {msg}"
                ) from e
            raise AIProviderError(f"{self.NAME} API error: {e}") from e
        except Exception as e:
            raise AIProviderError(f"Unexpected error talking to {self.NAME}: {e}") from e

    def validate_configuration(self) -> bool:
        if not self.model:
            return False
        if not self.base_url:
            return False
        if not isinstance(self.max_tokens, int) or self.max_tokens <= 0:
            return False
        if not isinstance(self.temperature, (int, float)) or not (0.0 <= self.temperature <= 2.0):
            return False
        if self.timeout is not None and (
            not isinstance(self.timeout, (int, float)) or self.timeout <= 0
        ):
            return False
        return True

    def verify_model_available(self) -> list[str]:
        """Ask the endpoint which models it serves; fail fast if ours isn't.

        Hits ``GET /v1/models`` once at startup. If the configured
        ``self.model`` isn't in the returned list, raises
        ``FatalAIProviderError`` with the actual list of available models
        in the message so the user can fix the typo without leaving the
        terminal. This is the cheap way to catch the most common
        misconfiguration (model name mismatch between toml and what's
        deployed) before a multi-thousand-call batch starts hammering
        the endpoint with rejected requests.

        Returns the list of available model IDs from the endpoint on
        success. Re-raises as a non-fatal AIProviderError if the request
        itself fails (network, auth) — the caller can decide to skip the
        check rather than abort.
        """
        try:
            response = self.client.models.list()
        except openai.APIConnectionError as e:
            raise AIProviderError(f"{self._connection_hint(e)} ({e})") from e
        except openai.AuthenticationError as e:
            raise FatalAIProviderError(
                f"{self.NAME} rejected the API key when listing models. "
                f"Check the credential and retry. ({e})"
            ) from e
        except openai.APIError as e:
            raise AIProviderError(f"{self.NAME} API error while listing models: {e}") from e

        available = [m.id for m in response.data]
        if self.model not in available:
            sample = ", ".join(available[:5])
            if len(available) > 5:
                sample += f", … ({len(available)} total)"
            raise FatalAIProviderError(
                f"Model {self.model!r} is not served by the {self.NAME} "
                f"endpoint at {self.base_url}. "
                f"Available model{'s' if len(available) != 1 else ''}: "
                f"{sample if available else '(none reported)'}. "
                f"Fix the model name in [providers.{self.NAME}] or --model "
                f"and retry — every call would otherwise fail the same way."
            )
        return available
