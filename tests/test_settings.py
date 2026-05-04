"""
Tests for prophecy.settings.Settings — the layered config dataclass.
"""

import os
from pathlib import Path
from unittest.mock import patch

from prophecy.settings import Settings


class TestSettingsDefaults:
    def test_dataclass_defaults(self):
        s = Settings()
        assert s.data_folder == Path("data")
        assert s.cache_folder is None

    def test_resolve_cache_folder_default(self):
        s = Settings(data_folder=Path("/tmp/foo"))
        assert s.resolve_cache_folder() == Path("/tmp/foo/results")

    def test_resolve_cache_folder_explicit(self):
        s = Settings(data_folder=Path("/tmp/foo"), cache_folder=Path("/var/cache/x"))
        assert s.resolve_cache_folder() == Path("/var/cache/x")

    def test_str_to_path_coercion(self):
        """Constructor strings are coerced to Path so callers don't have to wrap them."""
        s = Settings(data_folder="some/dir", cache_folder="cache/dir")  # type: ignore[arg-type]
        assert s.data_folder == Path("some/dir")
        assert s.cache_folder == Path("cache/dir")


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
        """When no config_path is given, ./prophecy.toml in the cwd is loaded."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "prophecy.toml").write_text('data_folder = "from-default-toml"\n')
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.load()
        assert s.data_folder == Path("from-default-toml")
