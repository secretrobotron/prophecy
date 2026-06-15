"""
RunPod Serverless implementation of the AIProvider interface.

RunPod's serverless vLLM workers expose an OpenAI-compatible REST surface
at ``https://api.runpod.ai/v2/<endpoint_id>/openai/v1``, so the actual
wire protocol is identical to Ollama / ChatGPT. This provider exists for
two reasons:

1. The base URL is derived from a per-user ``endpoint_id`` rather than
   being fixed, so we accept it as first-class config instead of asking
   users to type the whole URL.
2. RunPod workers spin down after idle. The first request after sleep
   triggers a cold start that can take 30-60s (10-15s with FlashBoot
   cache), so the default request timeout is bumped and error messages
   explain why a hang is plausible rather than indicating a real failure.

The API key is read from ``RUNPOD_API_KEY`` by default — never put it in
``prophecy.toml`` if the file is committed. CLI ``--api-key`` and the
explicit ``api_key`` constructor argument still work for ad-hoc use.

Default model is ``Qwen/Qwen2.5-14B-Instruct`` — same family as the
local Ollama default but the HF-style model ID that vLLM expects.
"""

from __future__ import annotations

import os
from typing import Any

from ._openai_compat import OpenAICompatProvider
from .base import AIProviderError


class RunPodServerlessProvider(OpenAICompatProvider):
    """AIProvider backed by a RunPod Serverless vLLM endpoint."""

    NAME = "runpod"
    DEFAULT_MODEL = "Qwen/Qwen2.5-14B-Instruct"
    # No default base URL — each user has their own endpoint_id. The
    # resolve_base_url override constructs the full URL from that.
    DEFAULT_BASE_URL = ""
    # 180s headroom for cold starts. Concrete inference is still typically
    # a couple of seconds; this just keeps us from giving up during the
    # initial worker boot. Override via [providers.runpod] timeout = N.
    DEFAULT_TIMEOUT: float | None = 180.0

    BASE_URL_TEMPLATE = "https://api.runpod.ai/v2/{endpoint_id}/openai/v1"
    API_KEY_ENV_VAR = "RUNPOD_API_KEY"
    ENDPOINT_ID_ENV_VAR = "RUNPOD_ENDPOINT_ID"

    def __init__(
        self,
        api_key: str | None = None,
        endpoint_id: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ):
        # Resolve endpoint_id from env if not passed — must happen before
        # super().__init__ because resolve_base_url reads it via kwargs.
        # Pass it through kwargs so OpenAICompatProvider.resolve_base_url
        # can see it without us needing to subclass __init__ further.
        self.endpoint_id = endpoint_id or os.getenv(self.ENDPOINT_ID_ENV_VAR)
        kwargs["endpoint_id"] = self.endpoint_id
        super().__init__(api_key=api_key, base_url=base_url, **kwargs)

    def resolve_base_url(self, base_url: str | None, kwargs: dict[str, Any]) -> str:
        # An explicit base_url wins — useful for custom RunPod domains or
        # the OpenAI-compat endpoints from sibling services.
        if base_url:
            return base_url
        endpoint_id = kwargs.get("endpoint_id") or self.endpoint_id
        if endpoint_id:
            return self.BASE_URL_TEMPLATE.format(endpoint_id=endpoint_id)
        raise AIProviderError(
            "RunPod Serverless requires an endpoint_id (or an explicit base_url). "
            "Set [providers.runpod] endpoint_id in prophecy.toml, "
            "pass --endpoint-id, or export RUNPOD_ENDPOINT_ID."
        )

    def resolve_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        env_key = os.getenv(self.API_KEY_ENV_VAR)
        if env_key:
            return env_key
        raise AIProviderError(
            "RunPod Serverless requires an API key. "
            f"Export {self.API_KEY_ENV_VAR} (preferred — it's a secret) "
            "or pass --api-key. As a last resort you can put api_key under "
            "[providers.runpod] in prophecy.toml, but never commit that file."
        )

    def _connection_hint(self, exc: Exception) -> str:
        return (
            f"Could not reach RunPod endpoint at {self.base_url}. "
            f"After idle, cold start can take 30-60s — if this happens on "
            f"first request after a quiet period, try again. If it persists, "
            f"check that endpoint_id is correct and the worker is healthy."
        )

    def _not_found_hint(self, model: str, exc: Exception) -> str:
        return (
            f"Model {model!r} not loaded on the RunPod endpoint. "
            f"vLLM workers serve one model per endpoint — check the "
            f"endpoint's MODEL_NAME environment variable, and use the "
            f"HuggingFace ID (e.g. 'Qwen/Qwen2.5-14B-Instruct')."
        )
