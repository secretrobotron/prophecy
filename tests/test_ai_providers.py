"""
Unit tests for the AI Providers module.

Tests the abstract base class, ChatGPT implementation, and factory pattern.
"""

import os
from unittest.mock import Mock, patch

import anthropic
import openai
import pytest

from prophecy.ai_providers import (
    AIProvider,
    AIProviderError,
    AIProviderFactory,
    ChatGPTProvider,
    ClaudeProvider,
)


class MockAIProvider(AIProvider):
    """Mock AI provider for testing the abstract base class."""

    def __init__(self, api_key=None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.call_count = 0

    def post_prompt(self, prompt: str, **kwargs) -> str:
        self.call_count += 1
        return f"Mock response to: {prompt[:50]}..."

    def validate_configuration(self) -> bool:
        return self.api_key is not None


class TestAIProvider:
    """Test the abstract AIProvider base class."""

    def test_init_with_api_key(self):
        """Test AIProvider initialization with API key."""
        provider = MockAIProvider(api_key="test_key", custom_param="value")
        assert provider.api_key == "test_key"
        assert provider.config["custom_param"] == "value"

    def test_init_without_api_key(self):
        """Test AIProvider initialization without API key."""
        provider = MockAIProvider()
        assert provider.api_key is None
        assert provider.config == {}

    def test_get_provider_name(self):
        """Test getting provider name."""
        provider = MockAIProvider()
        assert provider.get_provider_name() == "MockAIProvider"

    def test_abstract_methods_implemented(self):
        """Test that concrete implementation implements abstract methods."""
        provider = MockAIProvider(api_key="test")

        # Should not raise NotImplementedError
        response = provider.post_prompt("test prompt")
        assert response.startswith("Mock response to:")

        is_valid = provider.validate_configuration()
        assert is_valid is True

    def test_cannot_instantiate_abstract_class(self):
        """Test that AIProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AIProvider()


class TestChatGPTProvider:
    """Test the ChatGPT provider implementation."""

    def test_init_with_api_key(self):
        """Test ChatGPT provider initialization with API key."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            provider = ChatGPTProvider(api_key="test_key")
            assert provider.api_key == "test_key"
            assert provider.model == ChatGPTProvider.DEFAULT_MODEL
            assert provider.max_tokens == ChatGPTProvider.DEFAULT_MAX_TOKENS
            assert provider.temperature == ChatGPTProvider.DEFAULT_TEMPERATURE
            mock_openai.assert_called_once_with(api_key="test_key")

    def test_init_with_env_var(self):
        """Test ChatGPT provider initialization with environment variable."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env_key"}):
            with patch("prophecy.ai_providers.OpenAI") as mock_openai:
                provider = ChatGPTProvider()
                assert provider.api_key == "env_key"
                mock_openai.assert_called_once_with(api_key="env_key")

    def test_init_no_api_key(self):
        """Test ChatGPT provider initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AIProviderError, match="OpenAI API key not provided"):
                ChatGPTProvider()

    def test_init_with_custom_params(self):
        """Test ChatGPT provider initialization with custom parameters."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = ChatGPTProvider(
                api_key="test_key", model="gpt-4", max_tokens=2000, temperature=0.5
            )
            assert provider.model == "gpt-4"
            assert provider.max_tokens == 2000
            assert provider.temperature == 0.5

    def test_init_openai_client_failure(self):
        """Test ChatGPT provider initialization fails when OpenAI client creation fails."""
        with patch("prophecy.ai_providers.OpenAI", side_effect=Exception("Client creation failed")):
            with pytest.raises(AIProviderError, match="Failed to initialize OpenAI client"):
                ChatGPTProvider(api_key="test_key")

    def test_post_prompt_success(self):
        """Test successful prompt posting."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            # Setup mock response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test response from ChatGPT"

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            provider = ChatGPTProvider(api_key="test_key")
            response = provider.post_prompt("Test prompt")

            assert response == "Test response from ChatGPT"
            mock_client.chat.completions.create.assert_called_once()

            # Check the call arguments
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["model"] == ChatGPTProvider.DEFAULT_MODEL
            assert call_args[1]["messages"][0]["role"] == "user"
            assert call_args[1]["messages"][0]["content"] == "Test prompt"

    def test_post_prompt_with_system_message(self):
        """Test prompt posting with system message."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Response with system context"

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            provider = ChatGPTProvider(api_key="test_key")
            response = provider.post_prompt(
                "Test prompt", system_message="You are a helpful assistant."
            )

            assert response == "Response with system context"

            # Check messages include system message
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are a helpful assistant."
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "Test prompt"

    def test_post_prompt_with_overrides(self):
        """Test prompt posting with parameter overrides."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Override response"

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            provider = ChatGPTProvider(api_key="test_key")
            response = provider.post_prompt(
                "Test prompt", model="gpt-4", max_tokens=500, temperature=0.2
            )

            assert response == "Override response"

            # Check overridden parameters
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["model"] == "gpt-4"
            assert call_args[1]["max_tokens"] == 500
            assert call_args[1]["temperature"] == 0.2

    def test_post_prompt_empty_prompt(self):
        """Test that empty prompt raises error."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = ChatGPTProvider(api_key="test_key")

            with pytest.raises(AIProviderError, match="Prompt cannot be empty"):
                provider.post_prompt("")

            with pytest.raises(AIProviderError, match="Prompt cannot be empty"):
                provider.post_prompt("   ")

    def test_post_prompt_authentication_error(self):
        """Test handling of authentication errors."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            mock_client = Mock()
            # Mock the APIError properly
            mock_response = Mock()
            mock_response.status_code = 401

            auth_error = openai.AuthenticationError(
                message="Invalid API key",
                response=mock_response,
                body={"error": {"message": "Invalid API key"}},
            )
            mock_client.chat.completions.create.side_effect = auth_error
            mock_openai.return_value = mock_client

            provider = ChatGPTProvider(api_key="invalid_key")

            with pytest.raises(AIProviderError, match="Invalid OpenAI API key"):
                provider.post_prompt("Test prompt")

    def test_post_prompt_rate_limit_error(self):
        """Test handling of rate limit errors."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            mock_client = Mock()
            # Mock the RateLimitError properly
            mock_response = Mock()
            mock_response.status_code = 429

            rate_error = openai.RateLimitError(
                message="Rate limit exceeded",
                response=mock_response,
                body={"error": {"message": "Rate limit exceeded"}},
            )
            mock_client.chat.completions.create.side_effect = rate_error
            mock_openai.return_value = mock_client

            provider = ChatGPTProvider(api_key="test_key")

            with pytest.raises(AIProviderError, match="OpenAI API rate limit exceeded"):
                provider.post_prompt("Test prompt")

    def test_post_prompt_api_error(self):
        """Test handling of general API errors."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            mock_client = Mock()
            # Mock the APIError properly
            mock_request = Mock()
            mock_response = Mock()
            mock_response.status_code = 500

            api_error = openai.APIError(
                message="API error", request=mock_request, body={"error": {"message": "API error"}}
            )
            mock_client.chat.completions.create.side_effect = api_error
            mock_openai.return_value = mock_client

            provider = ChatGPTProvider(api_key="test_key")

            with pytest.raises(AIProviderError, match="OpenAI API error"):
                provider.post_prompt("Test prompt")

    def test_post_prompt_unexpected_error(self):
        """Test handling of unexpected errors."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = ValueError("Unexpected error")
            mock_openai.return_value = mock_client

            provider = ChatGPTProvider(api_key="test_key")

            with pytest.raises(
                AIProviderError, match="Unexpected error communicating with ChatGPT"
            ):
                provider.post_prompt("Test prompt")

    def test_validate_configuration_valid(self):
        """Test configuration validation with valid parameters."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = ChatGPTProvider(api_key="test_key")
            assert provider.validate_configuration() is True

    def test_validate_configuration_no_api_key(self):
        """Test configuration validation fails without API key."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = ChatGPTProvider(api_key="test_key")
            provider.api_key = None
            assert provider.validate_configuration() is False

    def test_validate_configuration_no_model(self):
        """Test configuration validation fails without model."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = ChatGPTProvider(api_key="test_key")
            provider.model = None
            assert provider.validate_configuration() is False

    def test_validate_configuration_invalid_max_tokens(self):
        """Test configuration validation fails with invalid max_tokens."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = ChatGPTProvider(api_key="test_key")
            provider.max_tokens = 0
            assert provider.validate_configuration() is False

            provider.max_tokens = -1
            assert provider.validate_configuration() is False

            provider.max_tokens = "invalid"
            assert provider.validate_configuration() is False

    def test_validate_configuration_invalid_temperature(self):
        """Test configuration validation fails with invalid temperature."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = ChatGPTProvider(api_key="test_key")
            provider.temperature = -0.1
            assert provider.validate_configuration() is False

            provider.temperature = 2.1
            assert provider.validate_configuration() is False

            provider.temperature = "invalid"
            assert provider.validate_configuration() is False

    def test_list_available_models_success(self):
        """Test successful model listing."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            # Setup mock models response
            mock_model1 = Mock()
            mock_model1.id = "gpt-3.5-turbo"
            mock_model2 = Mock()
            mock_model2.id = "gpt-4"
            mock_model3 = Mock()
            mock_model3.id = "text-davinci-003"  # Non-GPT model

            mock_models = Mock()
            mock_models.data = [mock_model1, mock_model2, mock_model3]

            mock_client = Mock()
            mock_client.models.list.return_value = mock_models
            mock_openai.return_value = mock_client

            provider = ChatGPTProvider(api_key="test_key")
            models = provider.list_available_models()

            # Should only return GPT models, sorted
            assert models == ["gpt-3.5-turbo", "gpt-4"]

    def test_list_available_models_error(self):
        """Test model listing with API error."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.models.list.side_effect = Exception("API error")
            mock_openai.return_value = mock_client

            provider = ChatGPTProvider(api_key="test_key")

            with pytest.raises(AIProviderError, match="Failed to retrieve available models"):
                provider.list_available_models()


class TestClaudeProvider:
    """Test the Claude provider implementation."""

    def test_init_with_api_key(self):
        """Test Claude provider initialization with API key."""
        with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
            provider = ClaudeProvider(api_key="test_key")
            assert provider.api_key == "test_key"
            assert provider.model == ClaudeProvider.DEFAULT_MODEL
            assert provider.max_tokens == ClaudeProvider.DEFAULT_MAX_TOKENS
            assert provider.temperature == ClaudeProvider.DEFAULT_TEMPERATURE
            mock_anthropic.assert_called_once_with(api_key="test_key")

    def test_init_with_env_var(self):
        """Test Claude provider initialization with environment variable."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env_key"}):
            with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
                provider = ClaudeProvider()
                assert provider.api_key == "env_key"
                mock_anthropic.assert_called_once_with(api_key="env_key")

    def test_init_no_api_key(self):
        """Test Claude provider initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AIProviderError, match="Anthropic API key not provided"):
                ClaudeProvider()

    def test_init_with_custom_params(self):
        """Test Claude provider initialization with custom parameters."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = ClaudeProvider(
                api_key="test_key", model="claude-3-opus-20240229", max_tokens=2000, temperature=0.5
            )
            assert provider.model == "claude-3-opus-20240229"
            assert provider.max_tokens == 2000
            assert provider.temperature == 0.5

    def test_init_anthropic_client_failure(self):
        """Test Claude provider initialization fails when Anthropic client creation fails."""
        with patch(
            "prophecy.ai_providers.anthropic.Anthropic",
            side_effect=Exception("Client creation failed"),
        ):
            with pytest.raises(AIProviderError, match="Failed to initialize Anthropic client"):
                ClaudeProvider(api_key="test_key")

    def test_post_prompt_success(self):
        """Test successful prompt posting."""
        with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
            # Setup mock response
            mock_response = Mock()
            mock_response.content = [Mock()]
            mock_response.content[0].text = "Test response from Claude"

            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="test_key")
            response = provider.post_prompt("Test prompt")

            assert response == "Test response from Claude"
            mock_client.messages.create.assert_called_once()

            # Check the call arguments
            call_args = mock_client.messages.create.call_args
            assert call_args[1]["model"] == ClaudeProvider.DEFAULT_MODEL
            assert call_args[1]["messages"][0]["role"] == "user"
            assert call_args[1]["messages"][0]["content"] == "Test prompt"

    def test_post_prompt_with_system_message(self):
        """Test prompt posting with system message."""
        with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
            mock_response = Mock()
            mock_response.content = [Mock()]
            mock_response.content[0].text = "Response with system context"

            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="test_key")
            response = provider.post_prompt(
                "Test prompt", system_message="You are a helpful assistant."
            )

            assert response == "Response with system context"

            # Check system message parameter
            call_args = mock_client.messages.create.call_args
            assert call_args[1]["system"] == "You are a helpful assistant."
            assert call_args[1]["messages"][0]["role"] == "user"
            assert call_args[1]["messages"][0]["content"] == "Test prompt"

    def test_post_prompt_with_overrides(self):
        """Test prompt posting with parameter overrides."""
        with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
            mock_response = Mock()
            mock_response.content = [Mock()]
            mock_response.content[0].text = "Override response"

            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="test_key")
            response = provider.post_prompt(
                "Test prompt", model="claude-3-opus-20240229", max_tokens=500, temperature=0.2
            )

            assert response == "Override response"

            # Check overridden parameters
            call_args = mock_client.messages.create.call_args
            assert call_args[1]["model"] == "claude-3-opus-20240229"
            assert call_args[1]["max_tokens"] == 500
            assert call_args[1]["temperature"] == 0.2

    def test_post_prompt_empty_prompt(self):
        """Test that empty prompt raises error."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = ClaudeProvider(api_key="test_key")

            with pytest.raises(AIProviderError, match="Prompt cannot be empty"):
                provider.post_prompt("")

            with pytest.raises(AIProviderError, match="Prompt cannot be empty"):
                provider.post_prompt("   ")

    def test_post_prompt_authentication_error(self):
        """Test handling of authentication errors."""
        with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            # Mock the authentication error
            auth_error = anthropic.AuthenticationError("Invalid API key", response=Mock(), body={})
            mock_client.messages.create.side_effect = auth_error
            mock_anthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="invalid_key")

            with pytest.raises(AIProviderError, match="Invalid Anthropic API key"):
                provider.post_prompt("Test prompt")

    def test_post_prompt_rate_limit_error(self):
        """Test handling of rate limit errors."""
        with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            # Mock the rate limit error
            rate_error = anthropic.RateLimitError("Rate limit exceeded", response=Mock(), body={})
            mock_client.messages.create.side_effect = rate_error
            mock_anthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="test_key")

            with pytest.raises(AIProviderError, match="Anthropic API rate limit exceeded"):
                provider.post_prompt("Test prompt")

    def test_post_prompt_api_error(self):
        """Test handling of general API errors."""
        with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            # Mock the API error
            api_error = anthropic.APIError("API error", request=Mock(), body={})
            mock_client.messages.create.side_effect = api_error
            mock_anthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="test_key")

            with pytest.raises(AIProviderError, match="Anthropic API error"):
                provider.post_prompt("Test prompt")

    def test_post_prompt_unexpected_error(self):
        """Test handling of unexpected errors."""
        with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.side_effect = ValueError("Unexpected error")
            mock_anthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="test_key")

            with pytest.raises(AIProviderError, match="Unexpected error communicating with Claude"):
                provider.post_prompt("Test prompt")

    def test_validate_configuration_valid(self):
        """Test configuration validation with valid parameters."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = ClaudeProvider(api_key="test_key")
            assert provider.validate_configuration() is True

    def test_validate_configuration_no_api_key(self):
        """Test configuration validation fails without API key."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = ClaudeProvider(api_key="test_key")
            provider.api_key = None
            assert provider.validate_configuration() is False

    def test_validate_configuration_no_model(self):
        """Test configuration validation fails without model."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = ClaudeProvider(api_key="test_key")
            provider.model = None
            assert provider.validate_configuration() is False

    def test_validate_configuration_invalid_max_tokens(self):
        """Test configuration validation fails with invalid max_tokens."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = ClaudeProvider(api_key="test_key")
            provider.max_tokens = 0
            assert provider.validate_configuration() is False

            provider.max_tokens = -1
            assert provider.validate_configuration() is False

            provider.max_tokens = "invalid"
            assert provider.validate_configuration() is False

    def test_validate_configuration_invalid_temperature(self):
        """Test configuration validation fails with invalid temperature."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = ClaudeProvider(api_key="test_key")
            provider.temperature = -0.1
            assert provider.validate_configuration() is False

            provider.temperature = 1.1
            assert provider.validate_configuration() is False

            provider.temperature = "invalid"
            assert provider.validate_configuration() is False

    def test_list_available_models_success(self):
        """Test successful model listing."""
        with patch("prophecy.ai_providers.anthropic.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="test_key")
            models = provider.list_available_models()

            # Should return known Claude models, sorted
            expected_models = [
                "claude-3-5-haiku-20241022",
                "claude-3-5-sonnet-20240620",
                "claude-3-5-sonnet-20241022",
                "claude-3-haiku-20240307",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
            ]
            assert models == expected_models

    def test_get_provider_name(self):
        """Test getting provider name."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = ClaudeProvider(api_key="test_key")
            assert provider.get_provider_name() == "ClaudeProvider"


class TestAIProviderFactory:
    """Test the AI provider factory."""

    def test_create_claude_provider(self):
        """Test creating Claude provider through factory."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = AIProviderFactory.create_provider("claude", api_key="test_key")
            assert isinstance(provider, ClaudeProvider)
            assert provider.api_key == "test_key"

    def test_create_anthropic_provider_alias(self):
        """Test creating provider using 'anthropic' alias."""
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            provider = AIProviderFactory.create_provider("anthropic", api_key="test_key")
            assert isinstance(provider, ClaudeProvider)

    def test_create_chatgpt_provider(self):
        """Test creating ChatGPT provider through factory."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = AIProviderFactory.create_provider("chatgpt", api_key="test_key")
            assert isinstance(provider, ChatGPTProvider)
            assert provider.api_key == "test_key"

    def test_create_openai_provider_alias(self):
        """Test creating provider using 'openai' alias."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = AIProviderFactory.create_provider("openai", api_key="test_key")
            assert isinstance(provider, ChatGPTProvider)

    def test_create_provider_case_insensitive(self):
        """Test that provider creation is case insensitive."""
        with patch("prophecy.ai_providers.OpenAI"):
            provider = AIProviderFactory.create_provider("CHATGPT", api_key="test_key")
            assert isinstance(provider, ChatGPTProvider)

    def test_create_unsupported_provider(self):
        """Test creating unsupported provider raises error."""
        with pytest.raises(ValueError, match="Unsupported AI provider: unsupported"):
            AIProviderFactory.create_provider("unsupported")

    def test_create_provider_initialization_failure(self):
        """Test that provider initialization failure is handled."""
        with patch("prophecy.ai_providers.OpenAI", side_effect=Exception("Init failed")):
            with pytest.raises(AIProviderError, match="Failed to create chatgpt provider"):
                AIProviderFactory.create_provider("chatgpt", api_key="test_key")

    def test_get_available_providers(self):
        """Test getting list of available providers."""
        providers = AIProviderFactory.get_available_providers()
        assert "chatgpt" in providers
        assert "openai" in providers
        assert "claude" in providers
        assert "anthropic" in providers
        assert len(providers) >= 4

    def test_register_new_provider(self):
        """Test registering a new provider."""
        original_providers = AIProviderFactory._providers.copy()

        try:
            AIProviderFactory.register_provider("mock", MockAIProvider)
            assert "mock" in AIProviderFactory.get_available_providers()

            # Test creating the registered provider
            provider = AIProviderFactory.create_provider("mock", api_key="test")
            assert isinstance(provider, MockAIProvider)

        finally:
            # Restore original providers
            AIProviderFactory._providers = original_providers

    def test_register_invalid_provider(self):
        """Test that registering invalid provider raises error."""

        class InvalidProvider:
            pass

        with pytest.raises(TypeError, match="Provider class must inherit from AIProvider"):
            AIProviderFactory.register_provider("invalid", InvalidProvider)


class TestAIProviderError:
    """Test the AIProviderError exception."""

    def test_error_creation(self):
        """Test creating AIProviderError."""
        error = AIProviderError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_error_inheritance(self):
        """Test that AIProviderError inherits from Exception."""
        error = AIProviderError("Test")
        assert isinstance(error, Exception)


class TestIntegration:
    """Integration tests for the AI provider system."""

    def test_end_to_end_workflow(self):
        """Test complete workflow from factory to response."""
        with patch("prophecy.ai_providers.OpenAI") as mock_openai:
            # Setup mock response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Integration test response"

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            # Create provider through factory
            provider = AIProviderFactory.create_provider(
                "chatgpt", api_key="test_key", model="gpt-4", temperature=0.5
            )

            # Validate configuration
            assert provider.validate_configuration() is True

            # Post prompt and get response
            response = provider.post_prompt(
                "Test integration prompt", system_message="You are a test assistant"
            )

            assert response == "Integration test response"
            assert provider.get_provider_name() == "ChatGPTProvider"

    def test_multiple_providers_same_interface(self):
        """Test that different providers follow the same interface."""
        # Mock provider
        mock_provider = MockAIProvider(api_key="test")

        # ChatGPT provider (mocked)
        with patch("prophecy.ai_providers.OpenAI"):
            chatgpt_provider = ChatGPTProvider(api_key="test")

        # Claude provider (mocked)
        with patch("prophecy.ai_providers.anthropic.Anthropic"):
            claude_provider = ClaudeProvider(api_key="test")

        # All should implement the same interface
        for provider in [mock_provider, chatgpt_provider, claude_provider]:
            assert hasattr(provider, "post_prompt")
            assert hasattr(provider, "validate_configuration")
            assert hasattr(provider, "get_provider_name")
            assert callable(provider.post_prompt)
            assert callable(provider.validate_configuration)
            assert callable(provider.get_provider_name)
