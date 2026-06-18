"""Tests for the hypotheses loader + validator."""

import os
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prophecy.hypotheses import (
    Hypothesis,
    HypothesisError,
    load_all,
    validate_against_facets,
)


def _write(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_load_all_returns_empty_when_folder_missing(tmp_path):
    assert load_all(tmp_path / "nope") == []


def test_load_all_reads_every_yml(tmp_path):
    _write(
        tmp_path / "a.yml",
        """
        id: a
        title: A
        mode: confirm
        slice: {sources: [P]}
        buckets:
          A: {label: Persian, topics: [Return to Zion]}
        """,
    )
    _write(
        tmp_path / "b.yml",
        """
        id: b
        title: B
        mode: compare
        slice: {sources: [E, J], books: [Exodus]}
        buckets:
          A: {label: Populist, topics: [Populism]}
          B: {label: Elitist, topics: [Elitism]}
        """,
    )
    out = load_all(tmp_path)
    assert [h.id for h in out] == ["a", "b"]
    assert out[1].payload["mode"] == "compare"


def test_duplicate_ids_raise(tmp_path):
    _write(
        tmp_path / "x.yml",
        """
        id: dup
        title: X
        mode: confirm
        slice: {}
        buckets: {A: {label: a, topics: [t]}}
        """,
    )
    _write(
        tmp_path / "y.yml",
        """
        id: dup
        title: Y
        mode: confirm
        slice: {}
        buckets: {A: {label: a, topics: [t]}}
        """,
    )
    with pytest.raises(HypothesisError, match="Duplicate hypothesis id 'dup'"):
        load_all(tmp_path)


def test_missing_required_keys(tmp_path):
    _write(tmp_path / "x.yml", "id: x\ntitle: X\n")
    with pytest.raises(HypothesisError, match="missing required keys"):
        Hypothesis.from_yaml(tmp_path / "x.yml")


def test_bad_mode(tmp_path):
    _write(
        tmp_path / "x.yml",
        """
        id: x
        title: X
        mode: refute
        slice: {}
        buckets: {A: {label: a, topics: [t]}}
        """,
    )
    with pytest.raises(HypothesisError, match="'mode' must be one of"):
        Hypothesis.from_yaml(tmp_path / "x.yml")


def test_compare_requires_two_buckets(tmp_path):
    _write(
        tmp_path / "x.yml",
        """
        id: x
        title: X
        mode: compare
        slice: {}
        buckets: {A: {label: a, topics: [t]}}
        """,
    )
    with pytest.raises(HypothesisError, match="compare mode requires buckets A and B"):
        Hypothesis.from_yaml(tmp_path / "x.yml")


def test_confirm_rejects_bucket_b(tmp_path):
    _write(
        tmp_path / "x.yml",
        """
        id: x
        title: X
        mode: confirm
        slice: {}
        buckets:
          A: {label: a, topics: [t]}
          B: {label: b, topics: [u]}
        """,
    )
    with pytest.raises(HypothesisError, match="confirm mode requires only bucket A"):
        Hypothesis.from_yaml(tmp_path / "x.yml")


def test_bucket_topics_must_be_non_empty(tmp_path):
    _write(
        tmp_path / "x.yml",
        """
        id: x
        title: X
        mode: confirm
        slice: {}
        buckets:
          A: {label: a, topics: []}
        """,
    )
    with pytest.raises(HypothesisError, match="needs a non-empty 'topics' list"):
        Hypothesis.from_yaml(tmp_path / "x.yml")


def test_slice_lists_must_be_strings(tmp_path):
    _write(
        tmp_path / "x.yml",
        """
        id: x
        title: X
        mode: confirm
        slice: {sources: [1, 2]}
        buckets:
          A: {label: a, topics: [t]}
        """,
    )
    with pytest.raises(HypothesisError, match="slice.sources must be a list of strings"):
        Hypothesis.from_yaml(tmp_path / "x.yml")


def test_default_scoring_validated(tmp_path):
    _write(
        tmp_path / "x.yml",
        """
        id: x
        title: X
        mode: confirm
        slice: {}
        buckets:
          A: {label: a, topics: [t]}
        default_scoring: nonsense
        """,
    )
    with pytest.raises(HypothesisError, match="default_scoring must be one of"):
        Hypothesis.from_yaml(tmp_path / "x.yml")


def test_validate_against_facets_warns_on_unknown_references(tmp_path):
    _write(
        tmp_path / "x.yml",
        """
        id: x
        title: X
        mode: compare
        slice: {sources: [E, Q], books: [Exodus, Atlantis]}
        buckets:
          A: {label: a, topics: [Populism, MadeUp]}
          B: {label: b, topics: [Elitism]}
        """,
    )
    hyps = load_all(tmp_path)
    warns = validate_against_facets(
        hyps,
        known_topics={"Populism", "Elitism"},
        known_books={"Exodus"},
        known_sources={"E", "J", "P"},
    )
    text = "\n".join(warns)
    assert "topic 'MadeUp'" in text
    assert "slice source 'Q'" in text
    assert "slice book 'Atlantis'" in text
    # Known references must not warn.
    assert "Populism" not in text
    assert "Exodus' not present" not in text


def test_repo_hypotheses_load_cleanly():
    """The repo's authored hypotheses must always parse and structurally validate."""
    repo_root = Path(__file__).resolve().parent.parent
    folder = repo_root / "data" / "hypotheses"
    hyps = load_all(folder)
    # At least the two starter hypotheses live in the repo.
    ids = {h.id for h in hyps}
    assert {"ej-exodus-populist-vs-elitist", "p-return-to-zion-zoroastrian"} <= ids
