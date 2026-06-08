"""
Tests for the `prune` subcommand — delete cached result files by engine
and/or by recomputed content hash.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prophecy.__main__ import calculate_template_checksum, prune_command
from prophecy.bible import Bible
from prophecy.prompts import Prompts
from prophecy.stories import Stories


@pytest.fixture
def data_folder():
    """Cache folder with a mix of engines + a malformed file."""
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "data"
        data.mkdir()
        (data / "prompts").mkdir()
        (data / "stories").mkdir()
        # Settings needs these files to load, even if prune doesn't read them.
        (data / "prompts" / "prompts.tsv").write_text(
            "id\tcategory\ttopic\tprompt\n1\tCat\tTopic\ttext\n", encoding="utf-8"
        )
        (data / "prompts" / "template.txt").write_text("$prompt\n$text", encoding="utf-8")
        (data / "stories" / "stories.yml").write_text(
            "X:\n  book: Genesis\n  verses: ['1:1']\n", encoding="utf-8"
        )
        (data / "index.json").write_text("{}", encoding="utf-8")

        cache = data / "results"
        cache.mkdir()

        # Three flavors of "unknown":
        # explicit unknown, null, missing-field-entirely
        (cache / "u_explicit.json").write_text(
            json.dumps({"answer": True, "story": "X", "prompt": "1", "engine": "unknown"})
        )
        (cache / "u_null.json").write_text(
            json.dumps({"answer": True, "story": "X", "prompt": "1", "engine": None})
        )
        (cache / "u_missing.json").write_text(
            json.dumps({"answer": True, "story": "X", "prompt": "1"})
        )
        # Real engines
        (cache / "chatgpt.json").write_text(
            json.dumps({"answer": True, "story": "X", "prompt": "1", "engine": "chatgpt:gpt-4"})
        )
        (cache / "claude.json").write_text(
            json.dumps({"answer": True, "story": "X", "prompt": "1", "engine": "claude-cli:haiku"})
        )
        # Malformed JSON
        (cache / "bad.json").write_text("not valid json {")

        yield data


def _cache_files(data_folder: Path) -> set[str]:
    return {p.name for p in (data_folder / "results").iterdir()}


def test_prune_unknown_catches_explicit_null_and_missing(data_folder):
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--engine", "unknown", "--verbosity", "WARNING"])
    assert rc == 0

    remaining = _cache_files(data_folder)
    assert "u_explicit.json" not in remaining
    assert "u_null.json" not in remaining
    assert "u_missing.json" not in remaining
    # Real engines untouched
    assert "chatgpt.json" in remaining
    assert "claude.json" in remaining
    # Malformed file is left alone (skipped, not deleted)
    assert "bad.json" in remaining


def test_prune_specific_engine(data_folder):
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--engine", "chatgpt:gpt-4", "--verbosity", "WARNING"])
    assert rc == 0
    remaining = _cache_files(data_folder)
    assert "chatgpt.json" not in remaining
    # Unknown-flavored ones untouched (we didn't ask for unknown)
    assert "u_explicit.json" in remaining
    assert "u_null.json" in remaining
    assert "u_missing.json" in remaining


def test_prune_multiple_engines_comma_sep(data_folder):
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--engine", "chatgpt:gpt-4,claude-cli:haiku", "--verbosity", "WARNING"])
    assert rc == 0
    remaining = _cache_files(data_folder)
    assert "chatgpt.json" not in remaining
    assert "claude.json" not in remaining


def test_prune_dry_run_keeps_files(data_folder):
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--engine", "unknown", "--dry-run", "--verbosity", "WARNING"])
    assert rc == 0
    remaining = _cache_files(data_folder)
    # Everything still there
    assert "u_explicit.json" in remaining
    assert "u_null.json" in remaining
    assert "u_missing.json" in remaining


def test_prune_engine_is_required(data_folder):
    # With neither --engine nor --by-hash, the command refuses to run so
    # "delete everything" isn't a default.
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        with pytest.raises(SystemExit):
            prune_command(["--verbosity", "WARNING"])


def test_prune_missing_cache_folder():
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "data"
        data.mkdir()
        (data / "prompts").mkdir()
        (data / "stories").mkdir()
        (data / "prompts" / "prompts.tsv").write_text(
            "id\tcategory\ttopic\tprompt\n1\tCat\tTopic\ttext\n", encoding="utf-8"
        )
        (data / "prompts" / "template.txt").write_text("$prompt\n$text", encoding="utf-8")
        (data / "stories" / "stories.yml").write_text(
            "X:\n  book: Genesis\n  verses: ['1:1']\n", encoding="utf-8"
        )
        (data / "index.json").write_text("{}", encoding="utf-8")
        # No data/results/ folder

        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data)}, clear=False):
            rc = prune_command(["--engine", "unknown", "--verbosity", "WARNING"])
        assert rc == 1


# ----- --by-hash mode -----

ENGINE = "claude-cli:haiku"


def _expected_hash(data_folder: Path, prompt_id: str, story_title: str, engine: str) -> str:
    """Compute what the cache filename stem *should* be under current data —
    same code path the production prune --by-hash uses, so the test fixture
    matches whatever the implementation considers fresh."""
    prompts = Prompts(data_folder=str(data_folder))
    stories = Stories(data_folder=str(data_folder))
    bible = Bible(data_folder=str(data_folder))
    prompt_record = prompts.get_prompt_by_id(prompt_id)
    story = stories.get_story(story_title)
    try:
        text = bible.get_text(story.book, *story.to_bible_parts())
    except Exception:
        text = f"[Biblical text not available for {story.book}]"
    populated = prompts.populate_template(prompt_record, story, text)
    return calculate_template_checksum(populated, engine)


def test_by_hash_keeps_fresh(data_folder):
    # Cache file written under the *current* content hash should be kept.
    stem = _expected_hash(data_folder, "1", "X", ENGINE)
    (data_folder / "results" / f"{stem}.json").write_text(
        json.dumps({"answer": True, "story": "X", "prompt": "1", "engine": ENGINE})
    )
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--by-hash", "--verbosity", "WARNING"])
    assert rc == 0
    assert f"{stem}.json" in _cache_files(data_folder)


def test_by_hash_deletes_stale_content(data_folder):
    # A file whose stem doesn't match the recomputed hash represents a result
    # for a prompt or story whose text has since changed.
    bogus = "deadbeef" * 4  # 32 hex chars
    (data_folder / "results" / f"{bogus}.json").write_text(
        json.dumps({"answer": True, "story": "X", "prompt": "1", "engine": ENGINE})
    )
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--by-hash", "--verbosity", "WARNING"])
    assert rc == 0
    assert f"{bogus}.json" not in _cache_files(data_folder)


def test_by_hash_deletes_orphan_prompt_id(data_folder):
    # Cache file references a prompt id that's no longer in prompts.tsv.
    bogus = "a" * 32
    (data_folder / "results" / f"{bogus}.json").write_text(
        json.dumps({"answer": True, "story": "X", "prompt": "gone-99", "engine": ENGINE})
    )
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--by-hash", "--verbosity", "WARNING"])
    assert rc == 0
    assert f"{bogus}.json" not in _cache_files(data_folder)


def test_by_hash_deletes_orphan_story(data_folder):
    # Cache file references a story title that's no longer in stories.yml.
    bogus = "b" * 32
    (data_folder / "results" / f"{bogus}.json").write_text(
        json.dumps({"answer": True, "story": "Gone", "prompt": "1", "engine": ENGINE})
    )
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--by-hash", "--verbosity", "WARNING"])
    assert rc == 0
    assert f"{bogus}.json" not in _cache_files(data_folder)


def test_by_hash_preserves_concat_ids(data_folder):
    # Synthetic concat:* ids represent bundled prompts; we can't recompute
    # their hash from the cache record alone, so we leave them alone.
    stem = "c" * 32
    (data_folder / "results" / f"{stem}.json").write_text(
        json.dumps(
            {"answer": True, "story": "X", "prompt": "concat:Politics:Elitism", "engine": ENGINE}
        )
    )
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--by-hash", "--verbosity", "WARNING"])
    assert rc == 0
    assert f"{stem}.json" in _cache_files(data_folder)


def test_by_hash_scoped_by_engine(data_folder):
    # Combined --engine + --by-hash: only hash-check files matching the
    # engine filter. Files for other engines stay untouched even if stale.
    bogus = "e" * 32
    (data_folder / "results" / f"{bogus}.json").write_text(
        json.dumps({"answer": True, "story": "X", "prompt": "1", "engine": "chatgpt:gpt-4"})
    )
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--by-hash", "--engine", "claude-cli:haiku", "--verbosity", "WARNING"])
    assert rc == 0
    # chatgpt file stays even though stale, because it was outside the scope.
    assert f"{bogus}.json" in _cache_files(data_folder)


def test_by_hash_dry_run_keeps_files(data_folder):
    bogus = "f" * 32
    (data_folder / "results" / f"{bogus}.json").write_text(
        json.dumps({"answer": True, "story": "X", "prompt": "1", "engine": ENGINE})
    )
    with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
        rc = prune_command(["--by-hash", "--dry-run", "--verbosity", "WARNING"])
    assert rc == 0
    assert f"{bogus}.json" in _cache_files(data_folder)
