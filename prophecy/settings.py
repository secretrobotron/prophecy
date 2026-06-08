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
    # Curated input lives in topical subfolders so the data root stays
    # uncluttered: data/stories/*.yml and data/prompts/{prompts*.tsv,template.txt}.
    stories_folder: Path = Path("stories")
    stories_file: Path = Path("stories.yml")
    prompts_folder: Path = Path("prompts")
    # Where `prophecy export` writes its static bundle by default. Independent
    # of data_folder because the export is consumed by the viewer / a static
    # site, not by the pipeline itself.
    export_out_folder: Path = Path("dist/data")
    # Default to a small pool: AI calls are independent (no cross-prompt
    # contamination) and the per-call cost is dominated by network/subprocess
    # latency, so a handful of parallel workers buys a lot of wall-clock back.
    workers: int = 3

    def __post_init__(self) -> None:
        # Coerce strings (from TOML or env) to Path so consumers can rely
        # on Path semantics regardless of how Settings was built.
        if isinstance(self.data_folder, str):
            self.data_folder = Path(self.data_folder)
        if isinstance(self.cache_folder, str):
            self.cache_folder = Path(self.cache_folder)
        if isinstance(self.stories_folder, str):
            self.stories_folder = Path(self.stories_folder)
        if isinstance(self.stories_file, str):
            self.stories_file = Path(self.stories_file)
        if isinstance(self.prompts_folder, str):
            self.prompts_folder = Path(self.prompts_folder)
        if isinstance(self.export_out_folder, str):
            self.export_out_folder = Path(self.export_out_folder)
        # Env vars arrive as strings; TOML/kwarg ints come through untouched.
        if isinstance(self.workers, str):
            try:
                self.workers = int(self.workers)
            except ValueError as e:
                raise ValueError(f"workers must be an integer, got {self.workers!r}") from e
        if self.workers < 1:
            raise ValueError(f"workers must be >= 1, got {self.workers}")

    def resolve_cache_folder(self) -> Path:
        """Cache folder if set explicitly; otherwise ``data_folder / "results"``."""
        if self.cache_folder is not None:
            return self.cache_folder
        return self.data_folder / "results"

    def resolve_stories_folder(self) -> Path:
        """Stories folder resolved against ``data_folder`` if relative."""
        if self.stories_folder.is_absolute():
            return self.stories_folder
        return self.data_folder / self.stories_folder

    def resolve_stories_path(self) -> Path:
        """
        Stories file resolved against the stories folder.

        Absolute ``stories_file`` short-circuits both folders so a one-off
        catalog outside the data tree still works.
        """
        if self.stories_file.is_absolute():
            return self.stories_file
        return self.resolve_stories_folder() / self.stories_file

    def resolve_prompts_folder(self) -> Path:
        """Prompts folder resolved against ``data_folder`` if relative."""
        if self.prompts_folder.is_absolute():
            return self.prompts_folder
        return self.data_folder / self.prompts_folder

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
