"""
Local Claude CLI implementation of the AIProvider interface.

Calls the `claude` CLI as a subprocess in non-interactive `--print` mode.
Useful for development/research because it reuses whichever authentication
the user already has configured for the CLI (OAuth, keychain, or
ANTHROPIC_API_KEY) — no API key argument is required from the caller.
"""

import json
import shutil
import subprocess

from .base import AIProvider, AIProviderError


def _strip_outer_code_fence(text: str) -> str:
    """
    Strip a single outer markdown code fence if the entire response is wrapped
    in one. `claude --print` tends to fence structured output (e.g. ```json
    ... ```) even when the prompt asks for raw JSON.
    """
    if not text.startswith("```"):
        return text
    first_newline = text.find("\n")
    if first_newline == -1:
        return text
    if not text.rstrip().endswith("```"):
        return text
    inner = text[first_newline + 1 :].rstrip()
    if inner.endswith("```"):
        inner = inner[:-3].rstrip()
    return inner


class ClaudeCLIProvider(AIProvider):
    """
    Claude provider that shells out to the `claude` CLI in --print mode.

    The prompt is delivered on stdin (so it is not subject to argv length
    limits) and the response is parsed from `--output-format json`, which
    returns an envelope with a `result` field containing the assistant text.
    """

    DEFAULT_MODEL = "haiku"
    DEFAULT_BINARY = "claude"
    DEFAULT_TIMEOUT = 300

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        binary: str = DEFAULT_BINARY,
        timeout: int = DEFAULT_TIMEOUT,
        **kwargs,
    ):
        """
        Initialize the local Claude CLI provider.

        Args:
            api_key: Ignored. Present for interface compatibility — the CLI
                handles authentication itself.
            model: Model alias or full id passed to `claude --model`
                (default: "haiku"). Aliases like "sonnet" / "opus" also work.
            binary: Path or name of the claude CLI executable.
            timeout: Per-call timeout in seconds.
        """
        super().__init__(api_key, **kwargs)

        self.model = model
        self.binary = binary
        self.timeout = timeout

    def _resolve_binary(self) -> str:
        resolved = shutil.which(self.binary)
        if resolved is None:
            raise AIProviderError(
                f"Claude CLI binary '{self.binary}' not found on PATH. "
                "Install Claude Code or pass binary='/path/to/claude'."
            )
        return resolved

    def post_prompt(
        self,
        prompt: str,
        model: str | None = None,
        system_message: str | None = None,
        timeout: int | None = None,
        **kwargs,
    ) -> str:
        """
        Send the prompt to the local `claude` CLI and return the text result.

        Args:
            prompt: The user prompt.
            model: Override the default model for this call.
            system_message: Optional system prompt (mapped to --system-prompt).
            timeout: Override the default per-call timeout (seconds).

        Returns:
            The assistant text response.

        Raises:
            AIProviderError: If the CLI is missing, times out, exits non-zero,
                returns malformed JSON, or reports an error in its envelope.
        """
        if not prompt or not prompt.strip():
            raise AIProviderError("Prompt cannot be empty")

        binary = self._resolve_binary()
        model = model or self.model
        timeout = timeout if timeout is not None else self.timeout

        cmd = [
            binary,
            "--print",
            "--output-format",
            "json",
            "--model",
            model,
        ]
        if system_message:
            cmd.extend(["--system-prompt", system_message])

        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise AIProviderError(f"Claude CLI timed out after {timeout}s") from e
        except FileNotFoundError as e:
            raise AIProviderError(f"Failed to launch Claude CLI: {e}") from e

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise AIProviderError(
                f"Claude CLI exited with code {completed.returncode}: {stderr or '<no stderr>'}"
            )

        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError as e:
            raise AIProviderError(f"Could not parse Claude CLI JSON output: {e}") from e

        if envelope.get("is_error"):
            detail = envelope.get("result") or envelope.get("api_error_status") or "unknown error"
            raise AIProviderError(f"Claude CLI reported an error: {detail}")

        result = envelope.get("result")
        if not isinstance(result, str):
            raise AIProviderError("Claude CLI envelope missing string 'result' field")

        return _strip_outer_code_fence(result.strip())

    def validate_configuration(self) -> bool:
        """
        True iff the CLI binary is locatable and the model alias is non-empty.
        """
        if not self.model:
            return False
        try:
            self._resolve_binary()
        except AIProviderError:
            return False
        return True

    def list_available_models(self) -> list[str]:
        """
        Return the model aliases the CLI accepts. (The CLI also accepts full
        model ids; these are just convenient shortcuts.)
        """
        return ["haiku", "sonnet", "opus"]
