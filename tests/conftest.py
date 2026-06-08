"""
Test-wide fixtures.

When pytest runs from the repo root, ``Settings.load()`` would otherwise pick
up the project's own ``prophecy.toml`` and apply its overrides (e.g. switching
the active stories catalog) inside every test's temp-data fixture. That makes
tests pass or fail based on the developer's local config — exactly the kind
of action-at-a-distance we don't want.

The autouse fixture below redirects the default TOML lookup to a path inside
a per-test ``tmp_path`` so it's guaranteed not to exist. Tests that want to
exercise TOML loading still pass ``config_path=`` explicitly and are
unaffected.
"""

import pytest

import prophecy.settings as settings_mod


@pytest.fixture(autouse=True)
def isolate_prophecy_config(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_mod, "DEFAULT_CONFIG_PATH", tmp_path / "no-config.toml")
