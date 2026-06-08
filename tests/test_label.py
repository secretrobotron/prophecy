"""
Tests for the `label` subcommand — per-story (category, topic) aggregation.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prophecy.__main__ import label_command


@pytest.fixture
def data_folder():
    """Small data fixture: 3 prompts spanning two (category, topic) groups."""
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "data"
        data.mkdir()
        (data / "prompts").mkdir()
        (data / "stories").mkdir()

        (data / "prompts" / "prompts.tsv").write_text(
            "id\tcategory\ttopic\tprompt\n"
            "1\tPolitics\tPopulism\tThe people lead\n"
            "2\tPolitics\tPopulism\tThe leader is humble\n"
            "3\tPolitics\tElitism\tThe leaders rage at the people\n"
            "4\tBabylonian\tGeo\tThere is destruction\n",
            encoding="utf-8",
        )
        (data / "prompts" / "template.txt").write_text('"$prompt"\n"$text"\n', encoding="utf-8")
        (data / "stories" / "stories.yml").write_text(
            "Sample Story:\n  book: Genesis\n  verses: ['1:1']\n"
            "Exodus Story:\n  book: Exodus\n  verses: ['1:1']\n",
            encoding="utf-8",
        )
        (data / "index.json").write_text("{}", encoding="utf-8")

        cache = data / "results"
        cache.mkdir()
        results = [
            # Sample Story / Populism: 2 hits / 2 total
            {
                "answer": True,
                "certainty": 90,
                "story": "Sample Story",
                "prompt": "1",
                "engine": "chatgpt:gpt-4",
            },
            {
                "answer": True,
                "certainty": 80,
                "story": "Sample Story",
                "prompt": "2",
                "engine": "chatgpt:gpt-4",
            },
            # Sample Story / Elitism: 0 hits / 1 total — should be dropped
            {
                "answer": False,
                "certainty": 60,
                "story": "Sample Story",
                "prompt": "3",
                "engine": "chatgpt:gpt-4",
            },
            # Sample Story / Geo: 1 hit / 1 total
            {
                "answer": True,
                "certainty": 70,
                "story": "Sample Story",
                "prompt": "4",
                "engine": "chatgpt:gpt-4",
            },
            # Exodus Story / Populism: 1 hit / 2 total
            {
                "answer": True,
                "certainty": 95,
                "story": "Exodus Story",
                "prompt": "1",
                "engine": "chatgpt:gpt-4",
            },
            {
                "answer": False,
                "certainty": 50,
                "story": "Exodus Story",
                "prompt": "2",
                "engine": "chatgpt:gpt-4",
            },
            # Different engine on Sample Story / Populism: 1 hit / 1 total
            {
                "answer": True,
                "certainty": 85,
                "story": "Sample Story",
                "prompt": "1",
                "engine": "claude:haiku",
            },
            # Synthetic concat: id — must be skipped
            {
                "answer": True,
                "certainty": 88,
                "story": "Sample Story",
                "prompt": "concat:Politics:Populism",
                "engine": "chatgpt:gpt-4",
            },
            # Orphan id — must be skipped
            {
                "answer": True,
                "certainty": 88,
                "story": "Sample Story",
                "prompt": "999",
                "engine": "chatgpt:gpt-4",
            },
        ]
        for i, r in enumerate(results):
            (cache / f"r{i}.json").write_text(json.dumps(r), encoding="utf-8")

        yield data


def _read_labels(out_path: Path) -> list[dict]:
    return json.loads(out_path.read_text())["labels"]


def test_label_emits_zero_hit_groups_with_attributed_false(data_folder):
    """Zero-hit groups are kept so the viewer can offer a non-attributed view,
    but each entry carries an `attributed` flag so consumers can filter them."""
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--verbosity", "WARNING"])
    assert rc == 0

    labels = _read_labels(out)
    by_key = {(e["story"], e["engine"], e["category"], e["topic"]): e for e in labels}
    elitism = by_key[("Sample Story", "chatgpt:gpt-4", "Politics", "Elitism")]
    assert elitism["hits"] == 0
    assert elitism["attributed"] is False
    # And hit groups remain marked attributed.
    populism = by_key[("Sample Story", "chatgpt:gpt-4", "Politics", "Populism")]
    assert populism["hits"] > 0
    assert populism["attributed"] is True


def test_label_groups_by_story_engine_category_topic(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--verbosity", "WARNING"])
    assert rc == 0

    labels = _read_labels(out)
    by_key = {(e["story"], e["engine"], e["category"], e["topic"]): e for e in labels}

    # Sample Story / chatgpt / Politics / Populism: 2 hits / 2 total
    e = by_key[("Sample Story", "chatgpt:gpt-4", "Politics", "Populism")]
    assert e["hits"] == 2
    assert e["total"] == 2
    assert e["avg_certainty"] == 85.0

    # Sample Story / claude:haiku / Politics / Populism: 1 hit / 1 total (separate engine)
    e2 = by_key[("Sample Story", "claude:haiku", "Politics", "Populism")]
    assert e2["hits"] == 1
    assert e2["total"] == 1

    # Exodus Story / chatgpt / Politics / Populism: 1 hit / 2 total
    e3 = by_key[("Exodus Story", "chatgpt:gpt-4", "Politics", "Populism")]
    assert e3["hits"] == 1
    assert e3["total"] == 2


def test_label_skips_concat_and_orphan_ids(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--verbosity", "WARNING"])
    assert rc == 0

    labels = _read_labels(out)
    # No entry should reference the synthetic concat id or the orphan 999.
    all_prompt_ids = {p["id"] for entry in labels for p in entry["prompts"]}
    assert "concat:Politics:Populism" not in all_prompt_ids
    assert "999" not in all_prompt_ids


def test_label_inlines_prompt_text_and_sorts_true_first(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--verbosity", "WARNING"])
    assert rc == 0

    labels = _read_labels(out)
    populism = next(e for e in labels if e["story"] == "Exodus Story" and e["topic"] == "Populism")
    # Order: true first (certainty 95), then false (certainty 50).
    assert populism["prompts"][0]["answer"] is True
    assert populism["prompts"][0]["certainty"] == 95
    assert populism["prompts"][0]["prompt"] == "The people lead"
    assert populism["prompts"][1]["answer"] is False


def test_label_book_filter(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--book", "Genesis", "--verbosity", "WARNING"])
    assert rc == 0

    labels = _read_labels(out)
    assert all(e["book"] == "Genesis" for e in labels)
    assert any(e["story"] == "Sample Story" for e in labels)
    assert not any(e["story"] == "Exodus Story" for e in labels)


def test_label_book_filter_case_insensitive(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--book", "genesis", "--verbosity", "WARNING"])
    assert rc == 0
    labels = _read_labels(out)
    assert all(e["book"] == "Genesis" for e in labels)


def test_label_exclude_category(data_folder):
    """--exclude-category Politics should drop both Populism and Elitism entries."""
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(
            [
                "--out",
                str(out),
                "--exclude-category",
                "Politics",
                "--verbosity",
                "WARNING",
            ]
        )
    assert rc == 0

    labels = _read_labels(out)
    categories = {e["category"] for e in labels}
    assert "Politics" not in categories
    # Babylonian/Geo should still appear
    assert any(e["category"] == "Babylonian" for e in labels)


def test_label_exclude_category_case_insensitive(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(
            [
                "--out",
                str(out),
                "--exclude-category",
                "politics",
                "--verbosity",
                "WARNING",
            ]
        )
    assert rc == 0
    categories = {e["category"] for e in _read_labels(out)}
    assert "Politics" not in categories


def test_label_exclude_category_unknown_errors(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(
            [
                "--out",
                str(out),
                "--exclude-category",
                "Imaginary",
                "--verbosity",
                "WARNING",
            ]
        )
    assert rc == 1


def test_label_engine_filter(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(
            ["--out", str(out), "--engine", "claude:haiku", "--verbosity", "WARNING"]
        )
    assert rc == 0

    labels = _read_labels(out)
    assert all(e["engine"] == "claude:haiku" for e in labels)
    assert len(labels) == 1
    assert labels[0]["story"] == "Sample Story"


def test_label_drops_results_for_unknown_stories(data_folder):
    """Cached results whose story isn't in the YAML never become labels."""
    orphan = data_folder / "results" / "ghost.json"
    orphan.write_text(
        json.dumps(
            {
                "answer": True,
                "certainty": 90,
                "story": "Ghost Story",
                "prompt": "1",
                "engine": "chatgpt:gpt-4",
            }
        )
    )

    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--verbosity", "WARNING"])
    assert rc == 0

    labels = _read_labels(out)
    assert all(entry["story"] != "Ghost Story" for entry in labels)


def test_label_default_output_path(data_folder):
    # No --out: should write to <data>/labels.json
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--verbosity", "WARNING"])
    assert rc == 0
    assert (data_folder / "labels.json").exists()


def test_label_unknown_book_errors(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--book", "Leviticus", "--verbosity", "WARNING"])
    assert rc == 1


def test_label_deterministic_ordering(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--verbosity", "WARNING"])
        assert rc == 0
        first = out.read_text()

        # Run again — should produce the same labels list (only generated_at differs).
        rc = label_command(["--out", str(out), "--verbosity", "WARNING"])
        assert rc == 0
        second = out.read_text()

    first_labels = json.loads(first)["labels"]
    second_labels = json.loads(second)["labels"]
    assert first_labels == second_labels


def test_label_payload_shape(data_folder):
    out = data_folder / "labels.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = label_command(["--out", str(out), "--verbosity", "WARNING"])
    assert rc == 0

    payload = json.loads(out.read_text())
    assert "generated_at" in payload
    assert "label_count" in payload
    assert "labels" in payload
    assert payload["label_count"] == len(payload["labels"])
    # Every label entry has the documented keys.
    for entry in payload["labels"]:
        assert {
            "story",
            "book",
            "engine",
            "category",
            "topic",
            "hits",
            "total",
            "attributed",
            "avg_certainty",
            "prompts",
        } <= set(entry.keys())
        assert entry["attributed"] == (entry["hits"] > 0)
        for p in entry["prompts"]:
            # cache_id is the MD5-stem the cache file is keyed by; reason is
            # the rationale text the LLM returned. Both feed the viewer.
            assert {"id", "answer", "certainty", "prompt", "cache_id", "reason"} <= set(p.keys())
            # Cache id should look like a 32-hex MD5 (the fixture's filenames
            # are non-hex like "r0" etc — exact value depends on fixture, just
            # confirm it's a string).
            assert isinstance(p["cache_id"], str)
