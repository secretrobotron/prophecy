"""Tests for the Profiles loader/matcher and the `profile` subcommand."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prophecy.__main__ import profile_command
from prophecy.profiles import Profile, Profiles, match_profile


@pytest.fixture
def data_folder():
    """Data folder with two profile files and a small labels.json."""
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "data"
        data.mkdir()
        profiles_dir = data / "profiles"
        profiles_dir.mkdir()

        (profiles_dir / "maccabees.yml").write_text(
            "Maccabees:\n"
            "  description: Nationalist + populist\n"
            "  labels:\n"
            "    - { category: Politics, topic: Nationalism, min_hit_rate: 30 }\n"
            "    - { category: Politics, topic: Populism,    min_hit_rate: 30 }\n",
            encoding="utf-8",
        )
        (profiles_dir / "priests.yaml").write_text(
            "Priests:\n"
            "  description: Priestly\n"
            "  labels:\n"
            "    - { category: Politics, topic: Priestly, min_hit_rate: 50 }\n",
            encoding="utf-8",
        )

        labels_payload = {
            "generated_at": "2026-06-10T00:00:00Z",
            "label_count": 6,
            "labels": [
                # Story A on engine X: clears both Maccabees labels.
                {
                    "story": "Story A",
                    "book": "Genesis",
                    "engine": "X",
                    "category": "Politics",
                    "topic": "Nationalism",
                    "hits": 4,
                    "total": 10,
                    "attributed": True,
                    "avg_certainty": 90.0,
                },
                {
                    "story": "Story A",
                    "book": "Genesis",
                    "engine": "X",
                    "category": "Politics",
                    "topic": "Populism",
                    "hits": 3,
                    "total": 10,
                    "attributed": True,
                    "avg_certainty": 80.0,
                },
                {
                    "story": "Story A",
                    "book": "Genesis",
                    "engine": "X",
                    "category": "Politics",
                    "topic": "Priestly",
                    "hits": 0,
                    "total": 5,
                    "attributed": False,
                    "avg_certainty": 50.0,
                },
                # Story B on engine X: only one of the two Maccabees labels meets threshold.
                {
                    "story": "Story B",
                    "book": "Exodus",
                    "engine": "X",
                    "category": "Politics",
                    "topic": "Nationalism",
                    "hits": 4,
                    "total": 10,
                    "attributed": True,
                    "avg_certainty": 80.0,
                },
                {
                    "story": "Story B",
                    "book": "Exodus",
                    "engine": "X",
                    "category": "Politics",
                    "topic": "Populism",
                    "hits": 1,
                    "total": 10,
                    "attributed": True,
                    "avg_certainty": 60.0,
                },
                # Story B on engine X: clears Priests.
                {
                    "story": "Story B",
                    "book": "Exodus",
                    "engine": "X",
                    "category": "Politics",
                    "topic": "Priestly",
                    "hits": 6,
                    "total": 10,
                    "attributed": True,
                    "avg_certainty": 70.0,
                },
            ],
        }
        (data / "labels.json").write_text(json.dumps(labels_payload), encoding="utf-8")
        yield data


def test_profiles_loads_multiple_files(data_folder):
    profiles = Profiles(data_folder=data_folder)
    assert profiles.names == ["Maccabees", "Priests"]
    mac = profiles.get("Maccabees")
    assert isinstance(mac, Profile)
    assert len(mac.labels) == 2
    assert {(label.category, label.topic) for label in mac.labels} == {
        ("Politics", "Nationalism"),
        ("Politics", "Populism"),
    }


def test_profiles_duplicate_name_across_files_errors(tmp_path):
    data = tmp_path / "data"
    profiles_dir = data / "profiles"
    profiles_dir.mkdir(parents=True)
    body = "Foo:\n  description: x\n  labels:\n    - { category: A, topic: B, min_hit_rate: 10 }\n"
    (profiles_dir / "a.yml").write_text(body, encoding="utf-8")
    (profiles_dir / "b.yml").write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate profile 'Foo'"):
        Profiles(data_folder=data)


def test_profiles_rejects_out_of_range_threshold(tmp_path):
    data = tmp_path / "data"
    profiles_dir = data / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "bad.yml").write_text(
        "Bad:\n  description: x\n  labels:\n    - { category: A, topic: B, min_hit_rate: 150 }\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be in \\[0, 100\\]"):
        Profiles(data_folder=data)


def test_profiles_rejects_empty_labels(tmp_path):
    data = tmp_path / "data"
    profiles_dir = data / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "bad.yml").write_text(
        "Bad:\n  description: x\n  labels: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-empty 'labels'"):
        Profiles(data_folder=data)


def test_match_profile_and_semantics(data_folder):
    profiles = Profiles(data_folder=data_folder)
    mac = profiles.get("Maccabees")

    # Story A clears both — matched.
    story_a = [
        {"category": "Politics", "topic": "Nationalism", "hits": 4, "total": 10},
        {"category": "Politics", "topic": "Populism", "hits": 3, "total": 10},
    ]
    matched, details = match_profile(mac, story_a)
    assert matched is True
    assert all(d.met for d in details)
    rates = {(d.category, d.topic): d.hit_rate for d in details}
    assert rates == {("Politics", "Nationalism"): 40.0, ("Politics", "Populism"): 30.0}

    # Story B fails Populism (10% < 30%) — overall not matched.
    story_b = [
        {"category": "Politics", "topic": "Nationalism", "hits": 4, "total": 10},
        {"category": "Politics", "topic": "Populism", "hits": 1, "total": 10},
    ]
    matched, details = match_profile(mac, story_b)
    assert matched is False
    by_topic = {d.topic: d for d in details}
    assert by_topic["Nationalism"].met is True
    assert by_topic["Populism"].met is False


def test_match_profile_missing_label_counts_as_zero(data_folder):
    """If labels.json has no row for a profile's (category, topic),
    we score it 0/0 (hit_rate 0) and the threshold fails."""
    profiles = Profiles(data_folder=data_folder)
    mac = profiles.get("Maccabees")
    matched, details = match_profile(mac, [])
    assert matched is False
    assert all(d.hits == 0 and d.total == 0 and d.hit_rate == 0.0 for d in details)


def test_profile_command_writes_profiles_json(data_folder):
    out = data_folder / "profiles.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = profile_command(["--out", str(out), "--verbosity", "WARNING"])
    assert rc == 0
    payload = json.loads(out.read_text())
    assert payload["profile_count"] == 2
    assert {p["name"] for p in payload["profiles"]} == {"Maccabees", "Priests"}

    by_key = {(m["profile"], m["story"], m["engine"]): m for m in payload["matches"]}
    # Story A matches Maccabees, Story B does not.
    assert by_key[("Maccabees", "Story A", "X")]["matched"] is True
    assert by_key[("Maccabees", "Story B", "X")]["matched"] is False
    # Story B matches Priests, Story A does not.
    assert by_key[("Priests", "Story B", "X")]["matched"] is True
    assert by_key[("Priests", "Story A", "X")]["matched"] is False


def test_profile_command_matched_only(data_folder):
    out = data_folder / "profiles.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = profile_command(["--out", str(out), "--matched-only", "--verbosity", "WARNING"])
    assert rc == 0
    payload = json.loads(out.read_text())
    assert all(m["matched"] for m in payload["matches"])
    keys = {(m["profile"], m["story"]) for m in payload["matches"]}
    assert keys == {("Maccabees", "Story A"), ("Priests", "Story B")}


def test_profile_command_missing_labels_file_errors(tmp_path, caplog):
    data = tmp_path / "data"
    profiles_dir = data / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "x.yml").write_text(
        "X:\n  description: x\n  labels:\n    - { category: A, topic: B, min_hit_rate: 10 }\n",
        encoding="utf-8",
    )
    out = data / "profiles.json"
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data)}, clear=False):
        rc = profile_command(["--out", str(out), "--verbosity", "ERROR"])
    assert rc == 1
