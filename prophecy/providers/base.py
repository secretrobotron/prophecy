"""
Abstract base class and shared exception type for AI providers.
"""

from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Exception raised for AI provider errors.

    The default semantics are *recoverable* — the calling pipeline catches
    these per-call and continues processing the next item, so a single
    transient hiccup doesn't kill an N-thousand-call batch. For failures
    that mean every subsequent call would fail the same way (wrong model
    name, bad auth, endpoint gone), raise ``FatalAIProviderError`` instead
    so the worker pool aborts immediately.
    """

    pass


class FatalAIProviderError(AIProviderError):
    """Provider failure that every subsequent call would hit the same way.

    Raised for things like "the configured model isn't loaded on the
    endpoint" or "the API key is unauthorized" — situations where
    continuing would just burn through compute generating identical
    errors. Callers in the batch pipeline catch this distinctly from
    plain ``AIProviderError`` and abort the run with a clear message.
    """

    pass


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    This class defines the interface that all AI providers must implement
    for posting prompts and getting responses.
    """

    # Stable short identifier used in cache JSON and cache keys.
    # Subclasses must override.
    NAME: str = "abstract"

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

    @property
    def engine_id(self) -> str:
        """
        Stable, hashable identifier for this provider+model.

        Used both as a tag on cached results (so downstream queries can
        distinguish answers from different engines) and as an input to the
        cache key (so identical prompts sent to different engines don't
        collide).

        Default format is ``"<NAME>:<model>"`` when the provider has a
        ``model`` attribute, otherwise just ``NAME``. Subclasses can
        override if they need a richer identifier.
        """
        model = getattr(self, "model", None)
        if model:
            return f"{self.NAME}:{model}"
        return self.NAME
