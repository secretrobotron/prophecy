"""
Project-wide configuration for the Prophecy toolkit.

`Settings` is a small dataclass whose field defaults *are* the defaults.
`Settings.load()` layers, highest precedence first:

    explicit kwargs  >  PROPHECY_* env vars  >  ./prophecy.toml  >  field defaults

API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY) are intentionally *not*
managed here — providers continue to read them from the environment
directly, so secrets never live in TOML files.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("prophecy.toml")
ENV_PREFIX = "PROPHECY_"


@dataclass
class Settings:
    """User-facing configuration for Prophecy."""

    data_folder: Path = Path("data")
    cache_folder: Path | None = None

    def __post_init__(self) -> None:
        # Coerce strings (from TOML or env) to Path so consumers can rely
        # on Path semantics regardless of how Settings was built.
        if isinstance(self.data_folder, str):
            self.data_folder = Path(self.data_folder)
        if isinstance(self.cache_folder, str):
            self.cache_folder = Path(self.cache_folder)

    def resolve_cache_folder(self) -> Path:
        """Cache folder if set explicitly; otherwise ``data_folder / "results"``."""
        if self.cache_folder is not None:
            return self.cache_folder
        return self.data_folder / "results"

    @classmethod
    def load(cls, *, config_path: Path | None = None, **overrides: Any) -> Settings:
        """
        Build a ``Settings`` from layered sources.

        Args:
            config_path: Path to a TOML file. Defaults to ``./prophecy.toml``.
                Missing files are silently ignored.
            **overrides: Explicit values that win over TOML and env vars.
                ``None`` values are treated as "not set" and skipped, so
                callers can pass CLI args through unconditionally:
                ``Settings.load(data_folder=args.data)``.

        Returns:
            A fully-resolved ``Settings`` instance.
        """
        values: dict[str, Any] = {}

        # Layer 1: TOML
        path = config_path if config_path is not None else DEFAULT_CONFIG_PATH
        if path.is_file():
            with path.open("rb") as f:
                toml_data = tomllib.load(f)
            field_names = {f.name for f in fields(cls)}
            for key, value in toml_data.items():
                if key in field_names:
                    values[key] = value

        # Layer 2: env vars (PROPHECY_DATA_FOLDER, PROPHECY_CACHE_FOLDER, …)
        for f in fields(cls):
            env_value = os.environ.get(ENV_PREFIX + f.name.upper())
            if env_value is not None:
                values[f.name] = env_value

        # Layer 3: explicit kwargs (None means "not set")
        values.update({k: v for k, v in overrides.items() if v is not None})

        return cls(**values)
