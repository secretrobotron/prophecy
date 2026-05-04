"""
Prophecy: Python toolkit for biblical text analysis and story extraction.

A Python package for programmatic access to biblical texts organized by stories
rather than just chapters and verses.
"""

from .bible import Bible
from .prompts import Prompts
from .stories import Stories, Story

__version__ = "0.1.0"
__all__ = ["Bible", "Stories", "Story", "Prompts"]

# Conditionally import AI providers (requires openai/anthropic dependency).
# The names are re-exported via __all__ — `noqa: F401` quiets ruff's
# unused-import check, which doesn't see the conditional __all__.extend.
try:
    from .ai_providers import (
        AIProvider,  # noqa: F401
        AIProviderError,  # noqa: F401
        AIProviderFactory,  # noqa: F401
        ChatGPTProvider,  # noqa: F401
        ClaudeProvider,  # noqa: F401
    )

    __all__.extend(
        ["AIProvider", "ChatGPTProvider", "ClaudeProvider", "AIProviderFactory", "AIProviderError"]
    )
except ImportError:
    # AI providers not available (missing openai/anthropic dependency)
    pass
