"""
Prophecy: Python toolkit for biblical text analysis and story extraction.

A Python package for programmatic access to biblical texts organized by stories
rather than just chapters and verses.
"""

from .bible import Bible
from .stories import Stories, Story
from .prompts import Prompts

__version__ = "0.1.0"
__all__ = ["Bible", "Stories", "Story", "Prompts"]

# Conditionally import AI providers (requires openai/anthropic dependency)
try:
    from .ai_providers import (
        AIProvider,
        ChatGPTProvider,
        ClaudeProvider,
        AIProviderFactory,
        AIProviderError,
    )

    __all__.extend(
        ["AIProvider", "ChatGPTProvider", "ClaudeProvider", "AIProviderFactory", "AIProviderError"]
    )
except ImportError:
    # AI providers not available (missing openai/anthropic dependency)
    pass
