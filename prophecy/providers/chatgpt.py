"""
ChatGPT (OpenAI) implementation of the AIProvider interface.
"""

import os

import openai
from openai import OpenAI

from .base import AIProvider, AIProviderError


class ChatGPTProvider(AIProvider):
    """
    ChatGPT implementation of the AIProvider interface.

    This class provides integration with OpenAI's ChatGPT API.
    """

    NAME = "chatgpt"
    DEFAULT_MODEL = "gpt-3.5-turbo"
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
        Initialize the ChatGPT provider.

        Args:
            api_key: OpenAI API key. If None, looks for OPENAI_API_KEY environment variable.
            model: GPT model to use (default: gpt-3.5-turbo)
            max_tokens: Maximum tokens in response (default: 1000)
            temperature: Response creativity (0.0-2.0, default: 0.7)
            **kwargs: Additional OpenAI API parameters
        """
        super().__init__(api_key, **kwargs)

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        if self.api_key is None:
            self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise AIProviderError(
                "OpenAI API key not provided and OPENAI_API_KEY environment variable not set"
            )

        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            raise AIProviderError(f"Failed to initialize OpenAI client: {str(e)}") from e

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
        Post a prompt to ChatGPT and get a response.

        Args:
            prompt: The text prompt to send to ChatGPT
            model: Override default model for this request
            max_tokens: Override default max_tokens for this request
            temperature: Override default temperature for this request
            system_message: Optional system message to set context
            **kwargs: Additional OpenAI API parameters

        Returns:
            Response text from ChatGPT

        Raises:
            AIProviderError: If there's an error communicating with ChatGPT
        """
        if not prompt or not prompt.strip():
            raise AIProviderError("Prompt cannot be empty")

        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

            return response.choices[0].message.content.strip()

        except openai.AuthenticationError as e:
            raise AIProviderError("Invalid OpenAI API key") from e
        except openai.RateLimitError as e:
            raise AIProviderError("OpenAI API rate limit exceeded") from e
        except openai.APIError as e:
            raise AIProviderError(f"OpenAI API error: {str(e)}") from e
        except Exception as e:
            raise AIProviderError(f"Unexpected error communicating with ChatGPT: {str(e)}") from e

    def validate_configuration(self) -> bool:
        """
        Validate that the ChatGPT provider is properly configured.

        Returns:
            True if configuration is valid, False otherwise
        """
        if not self.api_key:
            return False

        if not self.model:
            return False

        if not isinstance(self.max_tokens, int) or self.max_tokens <= 0:
            return False

        if not isinstance(self.temperature, (int, float)) or not (0.0 <= self.temperature <= 2.0):
            return False

        return True

    def list_available_models(self) -> list[str]:
        """
        Get list of available GPT models.

        Returns:
            List of model names available for this API key

        Raises:
            AIProviderError: If there's an error accessing the API
        """
        try:
            models = self.client.models.list()
            gpt_models = [model.id for model in models.data if "gpt" in model.id.lower()]
            return sorted(gpt_models)
        except Exception as e:
            raise AIProviderError(f"Failed to retrieve available models: {str(e)}") from e
