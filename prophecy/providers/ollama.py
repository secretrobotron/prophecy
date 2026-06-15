"""
Ollama (local) implementation of the AIProvider interface.

Ollama exposes an OpenAI-compatible REST endpoint at ``/v1``, so the
cleanest implementation reuses the official ``openai`` client with an
``api_key`` of "ollama" (Ollama ignores the value but the client
requires a non-empty string) and a ``base_url`` pointing at the local
daemon. This keeps response-parsing, retries, and streaming uniform
with ``ChatGPTProvider``.

The default model is ``qwen2.5:7b-instruct`` — Qwen's multilingual
holds up against Hebrew passages better than other open models at the
same parameter count, which matters because the prompt template asks
the model to judge a Hebrew-Masoretic fragment against an English
statement.
"""

import openai
from openai import OpenAI

from .base import AIProvider, AIProviderError


class OllamaProvider(AIProvider):
    """AIProvider backed by a local Ollama daemon."""

    NAME = "ollama"
    DEFAULT_MODEL = "qwen2.5:7b-instruct"
    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MAX_TOKENS = 1000
    # Lower than the OpenAI default — we want deterministic-ish judgments,
    # not creative paraphrase. The Hebrew judgment task isn't aided by warmth.
    DEFAULT_TEMPERATURE = 0.2

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        **kwargs,
    ):
        super().__init__(api_key, **kwargs)
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Ollama ignores the key but the OpenAI client refuses an empty
        # string. Caller-supplied keys win in case someone fronts Ollama
        # behind a reverse proxy that does enforce auth.
        effective_key = self.api_key or "ollama"
        try:
            self.client = OpenAI(api_key=effective_key, base_url=self.base_url)
        except Exception as e:
            raise AIProviderError(
                f"Failed to initialize Ollama client at {self.base_url}: {e}"
            ) from e

    def post_prompt(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system_message: str | None = None,
        **kwargs,
    ) -> str:
        if not prompt or not prompt.strip():
            raise AIProviderError("Prompt cannot be empty")

        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        # The pipeline expects the model's reply to be parseable JSON
        # ({answer, reason, certainty}). Asking the server to constrain
        # generation removes "almost-JSON" parse failures that would
        # otherwise force a re-run.
        request_kwargs: dict = {
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
                raise AIProviderError("Ollama returned an empty response")
            return content.strip()
        except openai.APIConnectionError as e:
            raise AIProviderError(
                f"Could not reach Ollama at {self.base_url} — is the daemon running? ({e})"
            ) from e
        except openai.NotFoundError as e:
            raise AIProviderError(
                f"Ollama returned 404 for model {model!r} — have you `ollama pull {model}`? ({e})"
            ) from e
        except openai.APIError as e:
            raise AIProviderError(f"Ollama API error: {e}") from e
        except Exception as e:
            raise AIProviderError(f"Unexpected error talking to Ollama: {e}") from e

    def validate_configuration(self) -> bool:
        if not self.model:
            return False
        if not self.base_url:
            return False
        if not isinstance(self.max_tokens, int) or self.max_tokens <= 0:
            return False
        if not isinstance(self.temperature, (int, float)) or not (0.0 <= self.temperature <= 2.0):
            return False
        return True
