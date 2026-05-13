"""
Tests for the engine_id property on AI providers and engine-aware cache keys.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prophecy.__main__ import calculate_template_checksum


class _FakeProvider:
    """Stand-in for an AIProvider, just for engine_id semantics."""

    def __init__(self, name: str, model: str | None = None):
        self.NAME = name
        if model is not None:
            self.model = model

    @property
    def engine_id(self) -> str:
        model = getattr(self, "model", None)
        return f"{self.NAME}:{model}" if model else self.NAME


class TestEngineIdProperty:
    def test_chatgpt_default_engine_id(self):
        from prophecy.providers.chatgpt import ChatGPTProvider

        # Skip API key validation by setting one
        os.environ.setdefault("OPENAI_API_KEY", "test-key")
        p = ChatGPTProvider(api_key="test-key", model="gpt-4")
        assert p.engine_id == "chatgpt:gpt-4"

    def test_claude_default_engine_id(self):
        from prophecy.providers.claude_api import ClaudeProvider

        p = ClaudeProvider(api_key="test-key", model="claude-3-haiku-20240307")
        assert p.engine_id == "claude:claude-3-haiku-20240307"

    def test_claude_cli_engine_id(self):
        from prophecy.providers.claude_cli import ClaudeCLIProvider

        p = ClaudeCLIProvider(model="haiku")
        assert p.engine_id == "claude-cli:haiku"


class TestCacheKeyEngineNamespacing:
    def test_same_prompt_different_engines_collide_without_namespacing(self):
        # Backwards-compat: omitting engine_id reproduces the pre-engine hash.
        prompt = "Some populated template"
        a = calculate_template_checksum(prompt)
        b = calculate_template_checksum(prompt)
        assert a == b

    def test_same_prompt_different_engines_produce_different_hashes(self):
        prompt = "Some populated template"
        a = calculate_template_checksum(prompt, "chatgpt:gpt-4")
        b = calculate_template_checksum(prompt, "claude:claude-3-haiku-20240307")
        assert a != b

    def test_engine_none_matches_legacy_hash(self):
        prompt = "Some populated template"
        legacy = calculate_template_checksum(prompt)
        explicit_none = calculate_template_checksum(prompt, None)
        assert legacy == explicit_none

    def test_same_engine_same_prompt_is_stable(self):
        prompt = "Some populated template"
        a = calculate_template_checksum(prompt, "chatgpt:gpt-4")
        b = calculate_template_checksum(prompt, "chatgpt:gpt-4")
        assert a == b
