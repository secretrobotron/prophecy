"""
Hypotheses loader for the Prophecy project.

Hypotheses are pre-baked analytic frames the viewer presents as a gallery:
each one names a corpus slice (by source tag and/or book), a set of label
"buckets" (single bucket for confirmatory, two for comparative), and a
short thesis. The viewer renders them with per-engine verdicts and
drill-through to the underlying prompts.

Files live in ``data/hypotheses/*.yml`` by default. Each file is one
hypothesis. The loader validates structural shape; semantic validation
(do referenced topics/sources/books exist in the labelled corpus?) is
done by callers that have that context (e.g. the export command).
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

_VALID_MODES = {"compare", "confirm"}
_VALID_SCORING = {"weighted", "hit", "coverage"}


class HypothesisError(ValueError):
    """Raised when a hypothesis YAML is malformed or references unknown facets."""


class Hypothesis:
    """A single validated hypothesis."""

    def __init__(self, payload: dict[str, Any], source_path: Path | None = None):
        self._payload = payload
        self.source_path = source_path

    @property
    def id(self) -> str:
        return self._payload["id"]

    @property
    def payload(self) -> dict[str, Any]:
        return self._payload

    @staticmethod
    def from_yaml(path: Path) -> "Hypothesis":
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict):
            raise HypothesisError(f"{path}: expected mapping at root, got {type(raw).__name__}")
        _validate_shape(raw, path)
        return Hypothesis(raw, source_path=path)


def load_all(folder: Path) -> list[Hypothesis]:
    """Load every ``*.yml`` file in ``folder`` (non-recursive). Empty list if absent.

    IDs must be unique across the folder; duplicates raise ``HypothesisError``
    naming both source files so the conflict is obvious.
    """
    if not folder.exists():
        return []
    out: list[Hypothesis] = []
    seen: dict[str, Path] = {}
    for path in sorted(folder.glob("*.yml")):
        h = Hypothesis.from_yaml(path)
        if h.id in seen:
            raise HypothesisError(
                f"Duplicate hypothesis id '{h.id}' in {path} (also in {seen[h.id]})"
            )
        seen[h.id] = path
        out.append(h)
    return out


def validate_against_facets(
    hypotheses: Iterable[Hypothesis],
    *,
    known_topics: set[str],
    known_books: set[str],
    known_sources: set[str],
) -> list[str]:
    """Cross-check each hypothesis against the facets the labelled corpus actually has.

    Returns a list of warning strings — one per unresolved reference. Does
    not raise: the bundle still ships, but the caller can log so the user
    sees why a bucket may be empty in the viewer.
    """
    warnings: list[str] = []
    for h in hypotheses:
        for topic in _collect_topics(h.payload):
            if topic not in known_topics:
                warnings.append(f"{h.id}: topic '{topic}' not present in labelled corpus")
        slice_ = h.payload.get("slice") or {}
        for book in slice_.get("books") or []:
            if book not in known_books:
                warnings.append(f"{h.id}: slice book '{book}' not present in labelled corpus")
        for src in slice_.get("sources") or []:
            if src not in known_sources:
                warnings.append(f"{h.id}: slice source '{src}' not present in any story's sources")
    return warnings


def _validate_shape(raw: dict[str, Any], path: Path) -> None:
    required = {"id", "title", "mode", "slice", "buckets"}
    missing = required - raw.keys()
    if missing:
        raise HypothesisError(f"{path}: missing required keys: {sorted(missing)}")

    if not isinstance(raw["id"], str) or not raw["id"]:
        raise HypothesisError(f"{path}: 'id' must be a non-empty string")
    if not isinstance(raw["title"], str) or not raw["title"]:
        raise HypothesisError(f"{path}: 'title' must be a non-empty string")
    if raw["mode"] not in _VALID_MODES:
        raise HypothesisError(
            f"{path}: 'mode' must be one of {sorted(_VALID_MODES)}, got {raw['mode']!r}"
        )

    slice_ = raw["slice"]
    if not isinstance(slice_, dict):
        raise HypothesisError(f"{path}: 'slice' must be a mapping")
    for key in ("sources", "books"):
        if key in slice_ and not _is_string_list(slice_[key]):
            raise HypothesisError(f"{path}: slice.{key} must be a list of strings")

    buckets = raw["buckets"]
    if not isinstance(buckets, dict) or not buckets:
        raise HypothesisError(f"{path}: 'buckets' must be a non-empty mapping")
    if raw["mode"] == "compare" and set(buckets.keys()) != {"A", "B"}:
        raise HypothesisError(
            f"{path}: compare mode requires buckets A and B, got {sorted(buckets.keys())}"
        )
    if raw["mode"] == "confirm" and set(buckets.keys()) != {"A"}:
        raise HypothesisError(
            f"{path}: confirm mode requires only bucket A, got {sorted(buckets.keys())}"
        )
    for name, bucket in buckets.items():
        if not isinstance(bucket, dict):
            raise HypothesisError(f"{path}: bucket {name!r} must be a mapping")
        if not isinstance(bucket.get("label"), str) or not bucket["label"]:
            raise HypothesisError(f"{path}: bucket {name!r} needs a non-empty 'label'")
        topics = bucket.get("topics")
        if not _is_string_list(topics) or not topics:
            raise HypothesisError(f"{path}: bucket {name!r} needs a non-empty 'topics' list")

    scoring = raw.get("default_scoring", "weighted")
    if scoring not in _VALID_SCORING:
        raise HypothesisError(
            f"{path}: default_scoring must be one of {sorted(_VALID_SCORING)}, got {scoring!r}"
        )


def _collect_topics(payload: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    for bucket in (payload.get("buckets") or {}).values():
        for topic in bucket.get("topics") or []:
            topics.append(topic)
    return topics


def _is_string_list(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)
