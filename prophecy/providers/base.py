"""
Abstract base class and shared exception type for AI providers.
"""

from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Exception raised for AI provider errors."""

    pass


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    This class defines the interface that all AI providers must implement
    for posting prompts and getting responses.
    """

    def __init__(self, api_key: str | None = None, **kwargs):
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
