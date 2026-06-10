"""
Author/group profiles for the Prophecy project.

A profile is a hand-curated description of what it means for a story to
"look like" the work of a particular person or group — e.g. the Maccabees
were nationalist and populist, so the Maccabees profile lists those two
(category, topic) labels with minimum hit-rate thresholds. A story matches
the profile when every listed label clears its threshold (AND).

Source files live in ``data/profiles/*.yml`` (one profile per file is the
common case; multiple per file is allowed). The loader walks the folder
and merges; duplicate profile names across files are a hard error.

This module is purely the data layer — load, validate, match. The CLI
glue that turns ``labels.json`` + profiles into ``profiles.json`` lives
in ``prophecy.__main__.profile_command``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .settings import Settings


@dataclass(frozen=True)
class ProfileLabel:
    """One label requirement inside a profile.

    ``min_hit_rate`` is stored as a percent (0-100) to match how it is
    written in YAML and how ``avg_certainty`` is expressed elsewhere.
    """

    category: str
    topic: str
    min_hit_rate: float


@dataclass(frozen=True)
class Profile:
    """A named bundle of label requirements."""

    name: str
    description: str
    labels: tuple[ProfileLabel, ...]


@dataclass(frozen=True)
class LabelMatch:
    """Result of evaluating one ProfileLabel against the label entries
    for a single (story, engine) pair."""

    category: str
    topic: str
    min_hit_rate: float
    hit_rate: float
    hits: int
    total: int
    met: bool


@dataclass(frozen=True)
class ProfileMatch:
    """Result of evaluating a full profile against one (story, engine) pair."""

    profile: str
    story: str
    book: str
    engine: str
    matched: bool
    labels: tuple[LabelMatch, ...]


class Profiles:
    """Loads and exposes every profile under ``data/profiles/``.

    Files are read in sorted order so error messages are deterministic.
    Both ``.yml`` and ``.yaml`` extensions are accepted.
    """

    def __init__(
        self,
        data_folder: str | Path | None = None,
        profiles_folder: str | Path | None = None,
    ):
        settings = Settings.load(
            data_folder=data_folder,
            profiles_folder=profiles_folder,
        )
        self.data_folder = settings.data_folder
        self.profiles_folder = settings.resolve_profiles_folder()

        if not self.data_folder.exists():
            raise FileNotFoundError(f"Data folder not found: {self.data_folder}")
        if not self.profiles_folder.exists():
            raise FileNotFoundError(f"Profiles folder not found: {self.profiles_folder}")

        self._profiles: dict[str, Profile] = {}
        # name -> file the profile was first declared in, for error messages.
        origin: dict[str, Path] = {}

        for path in sorted(self.profiles_folder.iterdir()):
            if path.suffix.lower() not in {".yml", ".yaml"}:
                continue
            with open(path, encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if raw is None:
                continue
            if not isinstance(raw, dict):
                raise ValueError(f"Invalid profile file {path}: expected dictionary at root level")
            for name, body in raw.items():
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"Invalid profile name in {path}: {name!r}")
                if name in self._profiles:
                    raise ValueError(
                        f"Duplicate profile {name!r} declared in {path} "
                        f"(first seen in {origin[name]})"
                    )
                self._profiles[name] = _parse_profile(name, body, path)
                origin[name] = path

    @property
    def names(self) -> list[str]:
        """Sorted list of declared profile names."""
        return sorted(self._profiles)

    def get(self, name: str) -> Profile:
        if name not in self._profiles:
            available = ", ".join(self.names) or "(none)"
            raise ValueError(f"Profile {name!r} not found. Available: {available}")
        return self._profiles[name]

    def all(self) -> list[Profile]:
        """Every profile, in name-sorted order."""
        return [self._profiles[n] for n in self.names]


def _parse_profile(name: str, body: object, path: Path) -> Profile:
    if not isinstance(body, dict):
        raise ValueError(f"Profile {name!r} in {path}: body must be a mapping")
    description = body.get("description", "")
    if not isinstance(description, str):
        raise ValueError(f"Profile {name!r} in {path}: description must be a string")
    raw_labels = body.get("labels")
    if not isinstance(raw_labels, list) or not raw_labels:
        raise ValueError(f"Profile {name!r} in {path}: must declare a non-empty 'labels' list")
    labels: list[ProfileLabel] = []
    seen: set[tuple[str, str]] = set()
    for i, entry in enumerate(raw_labels):
        if not isinstance(entry, dict):
            raise ValueError(f"Profile {name!r} in {path}: labels[{i}] must be a mapping")
        try:
            category = entry["category"]
            topic = entry["topic"]
            min_hit_rate = entry["min_hit_rate"]
        except KeyError as e:
            raise ValueError(
                f"Profile {name!r} in {path}: labels[{i}] missing required key {e.args[0]!r}"
            ) from None
        if not isinstance(category, str) or not isinstance(topic, str):
            raise ValueError(
                f"Profile {name!r} in {path}: labels[{i}] category/topic must be strings"
            )
        if not isinstance(min_hit_rate, (int, float)) or isinstance(min_hit_rate, bool):
            raise ValueError(
                f"Profile {name!r} in {path}: labels[{i}] min_hit_rate must be a number"
            )
        if not 0 <= float(min_hit_rate) <= 100:
            raise ValueError(
                f"Profile {name!r} in {path}: labels[{i}] min_hit_rate must be in [0, 100]"
            )
        key = (category, topic)
        if key in seen:
            raise ValueError(f"Profile {name!r} in {path}: duplicate label ({category}, {topic})")
        seen.add(key)
        labels.append(
            ProfileLabel(category=category, topic=topic, min_hit_rate=float(min_hit_rate))
        )
    return Profile(name=name, description=description, labels=tuple(labels))


def match_profile(
    profile: Profile,
    label_entries: list[dict],
) -> tuple[bool, list[LabelMatch]]:
    """Evaluate ``profile`` against the labels for a single (story, engine) pair.

    ``label_entries`` is a list of ``labels.json`` rows already filtered to
    one story+engine. Each profile label is matched against the row with
    the same (category, topic); missing rows count as 0/0 (hit_rate 0).
    Returns ``(matched, per_label_details)`` where ``matched`` is True
    only if every label clears its ``min_hit_rate``.
    """
    by_label = {(e["category"], e["topic"]): e for e in label_entries}
    details: list[LabelMatch] = []
    matched = True
    for plabel in profile.labels:
        row = by_label.get((plabel.category, plabel.topic))
        hits = int(row["hits"]) if row else 0
        total = int(row["total"]) if row else 0
        hit_rate_pct = (hits / total * 100.0) if total else 0.0
        met = hit_rate_pct >= plabel.min_hit_rate
        if not met:
            matched = False
        details.append(
            LabelMatch(
                category=plabel.category,
                topic=plabel.topic,
                min_hit_rate=plabel.min_hit_rate,
                hit_rate=round(hit_rate_pct, 2),
                hits=hits,
                total=total,
                met=met,
            )
        )
    return matched, details
