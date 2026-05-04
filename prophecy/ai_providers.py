"""
AI Provider system for the Prophecy project.

This module provides an abstract base class for AI providers and concrete implementations
for different AI services like ChatGPT, with a factory pattern for instantiation.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import os
import openai
from openai import OpenAI
import anthropic


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    This class defines the interface that all AI providers must implement
    for posting prompts and getting responses.
    """

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the AI provider.

        Args:
            api_key: API key for the AI service. If None, will look for environment variable.
            **kwargs: Additional configuration parameters specific to the provider.
        """
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    def post_prompt(self, prompt: str, **kwargs) -> str:
        """
        Post a prompt to the AI service and get a response.

        Args:
            prompt: The text prompt to send to the AI
            **kwargs: Additional parameters specific to the provider

        Returns:
            Response text from the AI service

        Raises:
            AIProviderError: If there's an error communicating with the AI service
        """
        pass

    @abstractmethod
    def validate_configuration(self) -> bool:
        """
        Validate that the provider is properly configured.

        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    def get_provider_name(self) -> str:
        """
        Get the name of this AI provider.

        Returns:
            String name of the provider
        """
        return self.__class__.__name__


class AIProviderError(Exception):
    """Exception raised for AI provider errors."""

    pass


class ChatGPTProvider(AIProvider):
    """
    ChatGPT implementation of the AIProvider interface.

    This class provides integration with OpenAI's ChatGPT API.
    """

    DEFAULT_MODEL = "gpt-3.5-turbo"
    DEFAULT_MAX_TOKENS = 1000
    DEFAULT_TEMPERATURE = 0.7

    def __init__(
        self,
        api_key: Optional[str] = None,
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

        # Get API key from environment if not provided
        if self.api_key is None:
            self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise AIProviderError(
                "OpenAI API key not provided and OPENAI_API_KEY environment variable not set"
            )

        # Initialize OpenAI client
        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            raise AIProviderError(f"Failed to initialize OpenAI client: {str(e)}")

    def post_prompt(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_message: Optional[str] = None,
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

        # Use instance defaults if parameters not provided
        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        # Prepare messages
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

        except openai.AuthenticationError:
            raise AIProviderError("Invalid OpenAI API key")
        except openai.RateLimitError:
            raise AIProviderError("OpenAI API rate limit exceeded")
        except openai.APIError as e:
            raise AIProviderError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            raise AIProviderError(f"Unexpected error communicating with ChatGPT: {str(e)}")

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

    def list_available_models(self) -> List[str]:
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
            raise AIProviderError(f"Failed to retrieve available models: {str(e)}")


class ClaudeProvider(AIProvider):
    """
    Claude implementation of the AIProvider interface.

    This class provides integration with Anthropic's Claude API.
    """

    DEFAULT_MODEL = "claude-3-haiku-20240307"
    DEFAULT_MAX_TOKENS = 1000
    DEFAULT_TEMPERATURE = 0.7

    def __init__(
        self,
        api_key: Optional[str] = None,
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

        # Get API key from environment if not provided
        if self.api_key is None:
            self.api_key = os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise AIProviderError(
                "Anthropic API key not provided and ANTHROPIC_API_KEY environment variable not set"
            )

        # Initialize Anthropic client
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except Exception as e:
            raise AIProviderError(f"Failed to initialize Anthropic client: {str(e)}")

    def post_prompt(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_message: Optional[str] = None,
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

        # Use instance defaults if parameters not provided
        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        # Prepare messages
        messages = [{"role": "user", "content": prompt}]

        try:
            # Build API call parameters
            api_params = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs,
            }

            # Add system message if provided
            if system_message:
                api_params["system"] = system_message

            response = self.client.messages.create(**api_params)

            return response.content[0].text.strip()

        except anthropic.AuthenticationError:
            raise AIProviderError("Invalid Anthropic API key")
        except anthropic.RateLimitError:
            raise AIProviderError("Anthropic API rate limit exceeded")
        except anthropic.APIError as e:
            raise AIProviderError(f"Anthropic API error: {str(e)}")
        except Exception as e:
            raise AIProviderError(f"Unexpected error communicating with Claude: {str(e)}")

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

    def list_available_models(self) -> List[str]:
        """
        Get list of available Claude models.

        Returns:
            List of model names available for this API key

        Raises:
            AIProviderError: If there's an error accessing the API
        """
        try:
            # Anthropic doesn't have a public models API endpoint like OpenAI,
            # so we return the known models as of the current API version
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
            raise AIProviderError(f"Failed to retrieve available models: {str(e)}")


class AIProviderFactory:
    """
    Factory class for creating AI provider instances.

    This factory allows for easy instantiation of different AI providers
    and can be extended to support additional providers in the future.
    """

    _providers = {
        "chatgpt": ChatGPTProvider,
        "openai": ChatGPTProvider,  # Alias for ChatGPT
        "claude": ClaudeProvider,
        "anthropic": ClaudeProvider,  # Alias for Claude
    }

    @classmethod
    def create_provider(cls, provider_name: str, **kwargs) -> AIProvider:
        """
        Create an AI provider instance.

        Args:
            provider_name: Name of the provider ('chatgpt', 'openai')
            **kwargs: Configuration parameters for the provider

        Returns:
            Configured AI provider instance

        Raises:
            ValueError: If provider_name is not supported
            AIProviderError: If provider initialization fails
        """
        provider_name = provider_name.lower()

        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unsupported AI provider: {provider_name}. Available providers: {available}"
            )

        provider_class = cls._providers[provider_name]

        try:
            return provider_class(**kwargs)
        except Exception as e:
            raise AIProviderError(f"Failed to create {provider_name} provider: {str(e)}")

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of available provider names.

        Returns:
            List of supported provider names
        """
        return list(cls._providers.keys())

    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """
        Register a new AI provider class.

        Args:
            name: Name to register the provider under
            provider_class: Provider class that inherits from AIProvider

        Raises:
            TypeError: If provider_class doesn't inherit from AIProvider
        """
        if not issubclass(provider_class, AIProvider):
            raise TypeError("Provider class must inherit from AIProvider")

        cls._providers[name.lower()] = provider_class
