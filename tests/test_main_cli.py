#!/usr/bin/env python3
"""
Tests for the main CLI functionality, especially edge cases around argument handling.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add the prophecy module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prophecy.__main__ import (
    create_argument_parser,
    get_cache_folder,
    initialize_components,
)
from prophecy.settings import Settings


class TestMainCLI:
    """Test class for main CLI functionality."""

    def test_initialize_components_with_default_settings(self):
        """initialize_components builds Stories/Prompts/Bible from defaults."""
        logger = logging.getLogger("test")
        settings = Settings()  # default data_folder = Path("data")

        stories, prompts, bible = initialize_components(settings, logger)

        assert stories is not None
        assert prompts is not None
        assert bible is not None

    def test_initialize_components_with_explicit_data_folder(self):
        """initialize_components honors an explicit data_folder on Settings."""
        logger = logging.getLogger("test")
        settings = Settings(data_folder=Path("data"))

        stories, prompts, bible = initialize_components(settings, logger)

        assert stories is not None
        assert prompts is not None
        assert bible is not None

    def test_get_cache_folder_default_resolves_to_data_results(self):
        """When cache_folder isn't set, it lands at data_folder/results."""
        logger = logging.getLogger("test")

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(data_folder=Path(temp_dir))

            cache_folder = get_cache_folder(settings, logger)
            expected = Path(temp_dir) / "results"

            assert cache_folder == expected
            assert cache_folder.exists()

    def test_get_cache_folder_explicit_override(self):
        """An explicit cache_folder on Settings wins over the default."""
        logger = logging.getLogger("test")

        with tempfile.TemporaryDirectory() as temp_dir:
            explicit = Path(temp_dir) / "elsewhere"
            settings = Settings(data_folder=Path(temp_dir), cache_folder=explicit)

            cache_folder = get_cache_folder(settings, logger)

            assert cache_folder == explicit
            assert cache_folder.exists()

    def test_cli_argument_parsing_no_data(self):
        """args.data is None when --data isn't passed; CLI flags parse cleanly."""
        test_argv = ["prophecy", "--stories", "The Creation", "--prompt", "1"]

        with patch.object(sys, "argv", test_argv):
            parser = create_argument_parser()
            args = parser.parse_args()

            assert args.data is None
            assert args.stories == "The Creation"
            assert args.prompt == "1"

    def test_settings_load_from_env_var(self):
        """Settings.load picks up PROPHECY_DATA_FOLDER from the environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = Path(temp_dir) / "test_data"
            data_path.mkdir()
            (data_path / "stories.yml").write_text(
                'test_story:\n  book: Genesis\n  verses: ["1:1"]'
            )
            (data_path / "prompts.tsv").write_text(
                "id\tprompt\tperiod\ttopic\n1\ttest prompt\ttest\ttest"
            )
            (data_path / "template.txt").write_text("Test template")
            (data_path / "index.json").write_text("{}")

            with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_path)}, clear=False):
                settings = Settings.load()
                assert settings.data_folder == data_path


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
