"""
Claude (Anthropic API) implementation of the AIProvider interface.
"""

import os

import anthropic

from .base import AIProvider, AIProviderError


class ClaudeProvider(AIProvider):
    """
    Claude implementation of the AIProvider interface.

    This class provides integration with Anthropic's Claude API.
    """

    NAME = "claude"
    DEFAULT_MODEL = "claude-3-haiku-20240307"
    DEFAULT_MAX_TOKENS = 1000
    DEFAULT_TEMPERATURE = 0.7

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        **kwargs,
    ):
        """
        Initialize the Claude provider.

        Args:
            api_key: Anthropic API key. If None, looks for ANTHROPIC_API_KEY environment variable.
            model: Claude model to use (default: claude-3-haiku-20240307)
            max_tokens: Maximum tokens in response (default: 1000)
            temperature: Response creativity (0.0-1.0, default: 0.7)
            **kwargs: Additional Anthropic API parameters
        """
        super().__init__(api_key, **kwargs)

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        if self.api_key is None:
            self.api_key = os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise AIProviderError(
                "Anthropic API key not provided and ANTHROPIC_API_KEY environment variable not set"
            )

        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except Exception as e:
            raise AIProviderError(f"Failed to initialize Anthropic client: {str(e)}") from e

    def post_prompt(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system_message: str | None = None,
        **kwargs,
    ) -> str:
        """
        Post a prompt to Claude and get a response.

        Args:
            prompt: The text prompt to send to Claude
            model: Override default model for this request
            max_tokens: Override default max_tokens for this request
            temperature: Override default temperature for this request
            system_message: Optional system message to set context
            **kwargs: Additional Anthropic API parameters

        Returns:
            Response text from Claude

        Raises:
            AIProviderError: If there's an error communicating with Claude
        """
        if not prompt or not prompt.strip():
            raise AIProviderError("Prompt cannot be empty")

        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        messages = [{"role": "user", "content": prompt}]

        try:
            api_params = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs,
            }

            if system_message:
                api_params["system"] = system_message

            response = self.client.messages.create(**api_params)

            return response.content[0].text.strip()

        except anthropic.AuthenticationError as e:
            raise AIProviderError("Invalid Anthropic API key") from e
        except anthropic.RateLimitError as e:
            raise AIProviderError("Anthropic API rate limit exceeded") from e
        except anthropic.APIError as e:
            raise AIProviderError(f"Anthropic API error: {str(e)}") from e
        except Exception as e:
            raise AIProviderError(f"Unexpected error communicating with Claude: {str(e)}") from e

    def validate_configuration(self) -> bool:
        """
        Validate that the Claude provider is properly configured.

        Returns:
            True if configuration is valid, False otherwise
        """
        if not self.api_key:
            return False

        if not self.model:
            return False

        if not isinstance(self.max_tokens, int) or self.max_tokens <= 0:
            return False

        if not isinstance(self.temperature, (int, float)) or not (0.0 <= self.temperature <= 1.0):
            return False

        return True

    def list_available_models(self) -> list[str]:
        """
        Get list of known Claude models.

        Returns:
            List of model names available for this API key

        Raises:
            AIProviderError: If there's an error accessing the API
        """
        try:
            claude_models = [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-sonnet-20240620",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ]
            return sorted(claude_models)
        except Exception as e:
            raise AIProviderError(f"Failed to retrieve available models: {str(e)}") from e
