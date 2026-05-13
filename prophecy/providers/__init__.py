"""
AI provider package for Prophecy.

Public surface:
- AIProvider — abstract base
- AIProviderError — exception type
- ChatGPTProvider, ClaudeProvider, ClaudeCLIProvider — concrete providers
- AIProviderFactory — builds providers by name
"""

from .base import AIProvider, AIProviderError
from .chatgpt import ChatGPTProvider
from .claude_api import ClaudeProvider
from .claude_cli import ClaudeCLIProvider


class AIProviderFactory:
    """
    Factory class for creating AI provider instances.

    Names are matched case-insensitively. Aliases are intentional and stable.
    """

    _providers = {
        "chatgpt": ChatGPTProvider,
        "openai": ChatGPTProvider,
        "claude": ClaudeProvider,
        "anthropic": ClaudeProvider,
        "claude-cli": ClaudeCLIProvider,
        "local-claude": ClaudeCLIProvider,
    }

    @classmethod
    def create_provider(cls, provider_name: str, **kwargs) -> AIProvider:
        """
        Create an AI provider instance by name.

        Args:
            provider_name: Name of the provider (e.g. 'chatgpt', 'claude-cli').
            **kwargs: Configuration parameters passed to the provider's __init__.

        Returns:
            Configured AI provider instance.

        Raises:
            ValueError: If provider_name is not registered.
            AIProviderError: If provider initialization fails.
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
            raise AIProviderError(f"Failed to create {provider_name} provider: {str(e)}") from e

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """List of registered provider names (including aliases)."""
        return list(cls._providers.keys())

    @classmethod
    def register_provider(cls, name: str, provider_class: type) -> None:
        """
        Register a new AI provider class.

        Raises:
            TypeError: If provider_class doesn't inherit from AIProvider.
        """
        if not issubclass(provider_class, AIProvider):
            raise TypeError("Provider class must inherit from AIProvider")

        cls._providers[name.lower()] = provider_class


__all__ = [
    "AIProvider",
    "AIProviderError",
    "AIProviderFactory",
    "ChatGPTProvider",
    "ClaudeProvider",
    "ClaudeCLIProvider",
]
