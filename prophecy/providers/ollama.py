"""
Ollama (local) implementation of the AIProvider interface.

Ollama exposes an OpenAI-compatible REST endpoint at ``/v1``, so the
implementation reuses the shared ``OpenAICompatProvider`` base — the
only Ollama-specific bits are the default model, the placeholder API
key the OpenAI client requires (Ollama ignores it), and the user-facing
error hints.

The default model is ``qwen2.5:7b-instruct`` — Qwen's multilingual
holds up against Hebrew passages better than other open models at the
same parameter count, which matters because the prompt template asks
the model to judge a Hebrew-Masoretic fragment against an English
statement.
"""

from ._openai_compat import OpenAICompatProvider


class OllamaProvider(OpenAICompatProvider):
    """AIProvider backed by a local Ollama daemon."""

    NAME = "ollama"
    DEFAULT_MODEL = "qwen2.5:7b-instruct"
    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    # Ollama ignores the API key but the OpenAI client refuses an empty
    # string. Caller-supplied keys still win in case someone fronts Ollama
    # behind a reverse proxy that does enforce auth.
    DEFAULT_API_KEY_PLACEHOLDER = "ollama"

    def _connection_hint(self, exc: Exception) -> str:
        return f"Could not reach Ollama at {self.base_url} — is the daemon running?"

    def _not_found_hint(self, model: str, exc: Exception) -> str:
        return f"Ollama returned 404 for model {model!r} — have you `ollama pull {model}`?"
