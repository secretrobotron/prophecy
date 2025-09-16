# AI Provider System

The Prophecy AI Provider system enables integration with various AI services for analyzing biblical texts and generating insights. The system is designed with extensibility in mind, allowing easy addition of new AI providers through a factory pattern.

## Key Components

### 1. Abstract Base Class (`AIProvider`)
Defines the interface that all AI providers must implement:
- `post_prompt(prompt, **kwargs)` - Send prompt to AI and get response
- `validate_configuration()` - Check if provider is properly configured
- `get_provider_name()` - Get the name of the provider

### 2. ChatGPT Implementation (`ChatGPTProvider`)
Concrete implementation for OpenAI's ChatGPT API:
- Full ChatGPT API integration with configurable parameters
- Support for GPT-3.5-turbo, GPT-4, and other models
- Configurable temperature, max_tokens, and other parameters
- Robust error handling for API failures
- Support for system messages and conversation context

### 3. Claude Implementation (`ClaudeProvider`)
Concrete implementation for Anthropic's Claude API:
- Full Claude API integration with configurable parameters
- Support for Claude 3 Haiku, Sonnet, and Opus models
- Configurable temperature, max_tokens, and other parameters
- Robust error handling for API failures
- Support for system messages and conversation context

### 4. Factory Pattern (`AIProviderFactory`)
Centralized factory for creating AI provider instances:
- `create_provider(name, **kwargs)` - Create provider by name
- `get_available_providers()` - List available providers
- `register_provider(name, class)` - Add new provider types

## Basic Usage

```python
from prophecy import AIProviderFactory, AIProviderError

# Create a ChatGPT provider
ai_provider = AIProviderFactory.create_provider(
    'chatgpt',
    api_key='your_openai_api_key',
    model='gpt-3.5-turbo',
    temperature=0.7,
    max_tokens=1000
)

# Create a Claude provider
claude_provider = AIProviderFactory.create_provider(
    'claude',
    api_key='your_anthropic_api_key',
    model='claude-3-haiku-20240307',
    temperature=0.7,
    max_tokens=1000
)

# Send a prompt
response = ai_provider.post_prompt(
    "Analyze this biblical text for themes of hope...",
    system_message="You are a biblical scholar."
)

print(response)
```

## Integration with Prophecy Components

```python
from prophecy import Prompts, Stories, Bible, AIProviderFactory

# Initialize components
prompts = Prompts()
stories = Stories()
bible = Bible()
ai_provider = AIProviderFactory.create_provider('chatgpt', api_key='...')

# Get a story and prompt
story = stories.get_story('The Creation')
prompt_data = prompts.get_prompt_by_id('1')
biblical_text = bible.get_text(story.book, *story.to_bible_parts())

# Create populated template
populated_template = prompts.populate_template(prompt_data, story, biblical_text)

# Analyze with AI
analysis = ai_provider.post_prompt(populated_template)
```

## Available Providers

- `chatgpt` or `openai` - OpenAI ChatGPT integration
- `claude` or `anthropic` - Anthropic Claude integration

## Configuration

### ChatGPT Provider
- `api_key` - OpenAI API key (or set `OPENAI_API_KEY` environment variable)
- `model` - GPT model to use (default: 'gpt-3.5-turbo')
- `max_tokens` - Maximum response length (default: 1000)
- `temperature` - Response creativity 0.0-2.0 (default: 0.7)

### Claude Provider
- `api_key` - Anthropic API key (or set `ANTHROPIC_API_KEY` environment variable)
- `model` - Claude model to use (default: 'claude-3-haiku-20240307')
- `max_tokens` - Maximum response length (default: 1000)
- `temperature` - Response creativity 0.0-1.0 (default: 0.7)

### Environment Variables
- `OPENAI_API_KEY` - Your OpenAI API key
- `ANTHROPIC_API_KEY` - Your Anthropic API key

## Error Handling

The system provides robust error handling:
- `AIProviderError` - Base exception for AI provider errors
- Authentication errors for invalid API keys
- Rate limit handling
- Network and API error handling

## Extending the System

Add new AI providers by implementing the `AIProvider` interface:

```python
from prophecy.ai_providers import AIProvider, AIProviderFactory

class MyCustomProvider(AIProvider):
    def post_prompt(self, prompt: str, **kwargs) -> str:
        # Your implementation here
        return "Response from custom AI"
    
    def validate_configuration(self) -> bool:
        # Validate your configuration
        return True

# Register the new provider
AIProviderFactory.register_provider('custom', MyCustomProvider)

# Use it
provider = AIProviderFactory.create_provider('custom')
```

## Examples

See `examples/ai_provider_demo.py` for a comprehensive demonstration of:
- Basic AI provider usage
- Integration with Prophecy components
- Error handling
- Extensibility examples

## Testing

Run the AI provider tests:
```bash
python -m pytest tests/test_ai_providers.py -v
```

The test suite includes:
- Unit tests for all provider functionality
- Mock-based testing for external dependencies
- Integration tests
- Error condition testing
- Factory pattern testing