"""
Tests for prophecy.settings.Settings — the layered config dataclass.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from prophecy.settings import Settings


class TestSettingsDefaults:
    def test_dataclass_defaults(self):
        s = Settings()
        assert s.data_folder == Path("data")
        assert s.cache_folder is None
        assert s.stories_file == Path("stories.yml")
        assert s.export_out_folder == Path("dist/data")
        assert s.workers == 3

    def test_resolve_cache_folder_default(self):
        s = Settings(data_folder=Path("/tmp/foo"))
        assert s.resolve_cache_folder() == Path("/tmp/foo/results")

    def test_resolve_cache_folder_explicit(self):
        s = Settings(data_folder=Path("/tmp/foo"), cache_folder=Path("/var/cache/x"))
        assert s.resolve_cache_folder() == Path("/var/cache/x")

    def test_str_to_path_coercion(self):
        """Constructor strings are coerced to Path so callers don't have to wrap them."""
        s = Settings(
            data_folder="some/dir",  # type: ignore[arg-type]
            cache_folder="cache/dir",  # type: ignore[arg-type]
            stories_file="alt.yml",  # type: ignore[arg-type]
        )
        assert s.data_folder == Path("some/dir")
        assert s.cache_folder == Path("cache/dir")
        assert s.stories_file == Path("alt.yml")

    def test_resolve_stories_path_relative(self):
        s = Settings(data_folder=Path("/tmp/foo"))
        assert s.resolve_stories_path() == Path("/tmp/foo/stories/stories.yml")

    def test_resolve_stories_path_absolute(self):
        s = Settings(
            data_folder=Path("/tmp/foo"),
            stories_file=Path("/var/data/custom.yml"),
        )
        # Absolute stories_file short-circuits both folders.
        assert s.resolve_stories_path() == Path("/var/data/custom.yml")

    def test_resolve_stories_path_custom_folder(self):
        s = Settings(
            data_folder=Path("/tmp/foo"),
            stories_folder=Path("catalogs"),
        )
        assert s.resolve_stories_path() == Path("/tmp/foo/catalogs/stories.yml")

    def test_resolve_stories_folder_absolute(self):
        s = Settings(
            data_folder=Path("/tmp/foo"),
            stories_folder=Path("/srv/stories"),
        )
        assert s.resolve_stories_folder() == Path("/srv/stories")
        assert s.resolve_stories_path() == Path("/srv/stories/stories.yml")

    def test_resolve_prompts_folder_relative(self):
        s = Settings(data_folder=Path("/tmp/foo"))
        assert s.resolve_prompts_folder() == Path("/tmp/foo/prompts")

    def test_resolve_prompts_folder_absolute(self):
        s = Settings(data_folder=Path("/tmp/foo"), prompts_folder=Path("/srv/prompts"))
        assert s.resolve_prompts_folder() == Path("/srv/prompts")

    def test_export_out_folder_coerces_string(self):
        s = Settings(export_out_folder="viewer/data")  # type: ignore[arg-type]
        assert s.export_out_folder == Path("viewer/data")


class TestSettingsLoad:
    """Settings.load layers TOML → env → kwargs (highest wins)."""

    def test_load_with_no_sources_returns_defaults(self, tmp_path):
        # Point at a non-existent toml file and clear env
        missing = tmp_path / "does-not-exist.toml"
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.load(config_path=missing)
        assert s.data_folder == Path("data")
        assert s.cache_folder is None

    def test_load_reads_toml(self, tmp_path):
        toml_path = tmp_path / "prophecy.toml"
        toml_path.write_text('data_folder = "/srv/data"\ncache_folder = "/srv/cache"\n')
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.load(config_path=toml_path)
        assert s.data_folder == Path("/srv/data")
        assert s.cache_folder == Path("/srv/cache")

    def test_env_overrides_toml(self, tmp_path):
        toml_path = tmp_path / "prophecy.toml"
        toml_path.write_text('data_folder = "/srv/data"\n')
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": "/from/env"}, clear=True):
            s = Settings.load(config_path=toml_path)
        assert s.data_folder == Path("/from/env")

    def test_kwargs_override_env(self, tmp_path):
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": "/from/env"}, clear=True):
            s = Settings.load(config_path=tmp_path / "missing.toml", data_folder="/from/kwarg")
        assert s.data_folder == Path("/from/kwarg")

    def test_kwargs_none_does_not_override(self, tmp_path):
        """Passing data_folder=None (e.g. CLI flag absent) must not stomp on env."""
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": "/from/env"}, clear=True):
            s = Settings.load(config_path=tmp_path / "missing.toml", data_folder=None)
        assert s.data_folder == Path("/from/env")

    def test_unknown_toml_keys_are_ignored(self, tmp_path):
        toml_path = tmp_path / "prophecy.toml"
        toml_path.write_text(
            'data_folder = "/srv/data"\nunknown_key = "ignored"\n[some_other_section]\nfoo = 1\n'
        )
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.load(config_path=toml_path)
        assert s.data_folder == Path("/srv/data")

    def test_default_config_path_is_prophecy_toml(self, tmp_path, monkeypatch):
        """When no config_path is given, the module's DEFAULT_CONFIG_PATH is loaded."""
        import prophecy.settings as settings_mod

        toml = tmp_path / "prophecy.toml"
        toml.write_text('data_folder = "from-default-toml"\n')
        # The conftest autouse fixture redirected DEFAULT_CONFIG_PATH at a
        # nonexistent file; for this test we point it at the toml we just wrote
        # so the no-arg Settings.load() actually sees something.
        monkeypatch.setattr(settings_mod, "DEFAULT_CONFIG_PATH", toml)
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.load()
        assert s.data_folder == Path("from-default-toml")

    def test_export_out_folder_layers(self, tmp_path):
        toml_path = tmp_path / "prophecy.toml"
        toml_path.write_text('export_out_folder = "from-toml/data"\n')

        with patch.dict(os.environ, {}, clear=True):
            s = Settings.load(config_path=toml_path)
        assert s.export_out_folder == Path("from-toml/data")

        with patch.dict(os.environ, {"PROPHECY_EXPORT_OUT_FOLDER": "from-env/data"}, clear=True):
            s = Settings.load(config_path=toml_path)
        assert s.export_out_folder == Path("from-env/data")

        with patch.dict(os.environ, {"PROPHECY_EXPORT_OUT_FOLDER": "from-env/data"}, clear=True):
            s = Settings.load(config_path=toml_path, export_out_folder="from-kwarg/data")
        assert s.export_out_folder == Path("from-kwarg/data")

    def test_workers_layers(self, tmp_path):
        """workers follows TOML → env → kwarg precedence and accepts ints."""
        toml_path = tmp_path / "prophecy.toml"
        toml_path.write_text("workers = 5\n")

        with patch.dict(os.environ, {}, clear=True):
            s = Settings.load(config_path=toml_path)
        assert s.workers == 5

        # Env vars arrive as strings — Settings must coerce.
        with patch.dict(os.environ, {"PROPHECY_WORKERS": "8"}, clear=True):
            s = Settings.load(config_path=toml_path)
        assert s.workers == 8

        with patch.dict(os.environ, {"PROPHECY_WORKERS": "8"}, clear=True):
            s = Settings.load(config_path=toml_path, workers=2)
        assert s.workers == 2

    def test_workers_rejects_invalid_values(self, tmp_path):
        with pytest.raises(ValueError, match="workers must be an integer"):
            with patch.dict(os.environ, {"PROPHECY_WORKERS": "not-a-number"}, clear=True):
                Settings.load(config_path=tmp_path / "missing.toml")

        with pytest.raises(ValueError, match="workers must be >= 1"):
            Settings(workers=0)

    def test_stories_file_layers(self, tmp_path):
        """stories_file follows the same TOML → env → kwarg precedence."""
        toml_path = tmp_path / "prophecy.toml"
        toml_path.write_text('stories_file = "from-toml.yml"\n')

        with patch.dict(os.environ, {}, clear=True):
            s = Settings.load(config_path=toml_path)
        assert s.stories_file == Path("from-toml.yml")

        with patch.dict(os.environ, {"PROPHECY_STORIES_FILE": "from-env.yml"}, clear=True):
            s = Settings.load(config_path=toml_path)
        assert s.stories_file == Path("from-env.yml")

        with patch.dict(os.environ, {"PROPHECY_STORIES_FILE": "from-env.yml"}, clear=True):
            s = Settings.load(config_path=toml_path, stories_file="from-kwarg.yml")
        assert s.stories_file == Path("from-kwarg.yml")
