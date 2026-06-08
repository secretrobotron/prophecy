"""
Tests for the `export` subcommand — sharded JSONL bundle + manifest.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prophecy.__main__ import export_command


@pytest.fixture
def data_folder():
    """Small data fixture with two books to exercise sharding."""
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "data"
        data.mkdir()
        (data / "prompts").mkdir()
        (data / "stories").mkdir()

        (data / "prompts" / "prompts.tsv").write_text(
            "id\tcategory\ttopic\tprompt\n"
            "1\tPolitics\tPopulism\tThe people lead\n"
            "2\tPolitics\tElitism\tThe elite rule\n"
            "3\tBabylonian\tGeo\tThere is destruction\n",
            encoding="utf-8",
        )
        (data / "prompts" / "template.txt").write_text('"$prompt"\n"$text"\n', encoding="utf-8")
        (data / "stories" / "stories.yml").write_text(
            "The Creation:\n  book: Genesis\n  verses: ['1:1']\n"
            "The Exodus:\n  book: Exodus\n  verses: ['1:1']\n",
            encoding="utf-8",
        )
        (data / "index.json").write_text("{}", encoding="utf-8")

        cache = data / "results"
        cache.mkdir()
        results = [
            {
                "answer": True,
                "certainty": 90,
                "story": "The Creation",
                "prompt": "1",
                "engine": "chatgpt:gpt-4",
                "reason": "yes",
            },
            {
                "answer": False,
                "certainty": 60,
                "story": "The Creation",
                "prompt": "2",
                "engine": "chatgpt:gpt-4",
                "reason": "no",
            },
            {
                "answer": True,
                "certainty": 80,
                "story": "The Exodus",
                "prompt": "1",
                "engine": "claude:haiku",
                "reason": "yes",
            },
            {
                "answer": True,
                "certainty": 85,
                "story": "The Exodus",
                "prompt": "3",
                "reason": "destruction",
            },  # legacy: no engine
        ]
        for i, r in enumerate(results):
            (cache / f"r{i}.json").write_text(json.dumps(r), encoding="utf-8")

        yield data


def test_export_writes_manifest_and_shards(data_folder):
    with tempfile.TemporaryDirectory() as out_tmp:
        out_dir = Path(out_tmp) / "dist" / "data"

        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = export_command(["--out", str(out_dir), "--verbosity", "WARNING"])
        assert rc == 0

        # Manifest
        manifest = json.loads((out_dir / "index.json").read_text())
        assert manifest["total_results"] == 4
        assert set(manifest["books"]) == {"Genesis", "Exodus"}
        assert "chatgpt:gpt-4" in manifest["engines"]
        assert "claude:haiku" in manifest["engines"]
        assert "unknown" in manifest["engines"]  # legacy row
        assert "Politics" in manifest["categories"]
        assert "Populism" in manifest["topics"]
        assert manifest["files"]["prompts"] == "prompts.json"
        # Stories facet: only stories that have at least one result
        assert set(manifest["stories"]) == {"The Creation", "The Exodus"}
        # used_prompt_ids: only the prompt ids that show up in cached results
        assert set(manifest["used_prompt_ids"]) == {"1", "2", "3"}
        # result_count_by_prompt: how many results per prompt id
        assert manifest["result_count_by_prompt"] == {"1": 2, "2": 1, "3": 1}

        # Shard files
        genesis_shard = out_dir / "results" / "Genesis.jsonl"
        exodus_shard = out_dir / "results" / "Exodus.jsonl"
        assert genesis_shard.exists()
        assert exodus_shard.exists()

        genesis_rows = [json.loads(line) for line in genesis_shard.read_text().splitlines() if line]
        assert len(genesis_rows) == 2
        assert all(r["book"] == "Genesis" for r in genesis_rows)
        # Enrichment: category/topic resolved from prompt id
        assert any(r["category"] == "Politics" and r["topic"] == "Populism" for r in genesis_rows)

        exodus_rows = [json.loads(line) for line in exodus_shard.read_text().splitlines() if line]
        assert len(exodus_rows) == 2
        # Legacy row gets engine="unknown"
        assert any(r["engine"] == "unknown" for r in exodus_rows)

        # prompts.json
        prompts_payload = json.loads((out_dir / "prompts.json").read_text())
        assert isinstance(prompts_payload, list)
        assert len(prompts_payload) == 3
        assert all({"id", "category", "topic", "prompt"} <= set(p.keys()) for p in prompts_payload)

        # stories.json
        stories_payload = json.loads((out_dir / "stories.json").read_text())
        assert set(stories_payload.keys()) == {"The Creation", "The Exodus"}
        assert stories_payload["The Exodus"]["book"] == "Exodus"


def test_export_shard_per_book_inventory(data_folder):
    with tempfile.TemporaryDirectory() as out_tmp:
        out_dir = Path(out_tmp) / "dist"

        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = export_command(["--out", str(out_dir), "--verbosity", "WARNING"])
        assert rc == 0

        manifest = json.loads((out_dir / "index.json").read_text())
        shards_by_book = {s["book"]: s for s in manifest["shards"]}
        assert shards_by_book["Genesis"]["row_count"] == 2
        assert shards_by_book["Exodus"]["row_count"] == 2
        assert shards_by_book["Genesis"]["stories"] == ["The Creation"]
        assert "claude:haiku" in shards_by_book["Exodus"]["engines"]
        assert "unknown" in shards_by_book["Exodus"]["engines"]


def test_export_empty_cache_writes_empty_manifest(data_folder):
    # Wipe the cache folder
    for f in (data_folder / "results").iterdir():
        f.unlink()

    with tempfile.TemporaryDirectory() as out_tmp:
        out_dir = Path(out_tmp) / "dist"
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = export_command(["--out", str(out_dir), "--verbosity", "WARNING"])
        assert rc == 0

        manifest = json.loads((out_dir / "index.json").read_text())
        assert manifest["total_results"] == 0
        assert manifest["shards"] == []
        assert manifest["books"] == []


def test_export_picks_up_labels_json(data_folder):
    """If data/labels.json exists, it's copied into the bundle and listed in
    the manifest under files.labels."""
    labels_src = data_folder / "labels.json"
    labels_src.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-01T00:00:00Z",
                "label_count": 1,
                "labels": [
                    {
                        "story": "The Creation",
                        "book": "Genesis",
                        "engine": "chatgpt:gpt-4",
                        "category": "Politics",
                        "topic": "Populism",
                        "hits": 1,
                        "total": 1,
                        "avg_certainty": 90.0,
                        "prompts": [{"id": "1", "answer": True, "certainty": 90, "prompt": "test"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with tempfile.TemporaryDirectory() as out_tmp:
        out_dir = Path(out_tmp) / "dist"
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = export_command(["--out", str(out_dir), "--verbosity", "WARNING"])
        assert rc == 0

        bundled = out_dir / "labels.json"
        assert bundled.exists()
        assert json.loads(bundled.read_text())["label_count"] == 1

        manifest = json.loads((out_dir / "index.json").read_text())
        assert manifest["files"]["labels"] == "labels.json"


def test_export_without_labels_json_omits_from_manifest(data_folder):
    """Without data/labels.json, export still succeeds and files.labels is absent."""
    with tempfile.TemporaryDirectory() as out_tmp:
        out_dir = Path(out_tmp) / "dist"
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = export_command(["--out", str(out_dir), "--verbosity", "WARNING"])
        assert rc == 0

        assert not (out_dir / "labels.json").exists()
        manifest = json.loads((out_dir / "index.json").read_text())
        assert "labels" not in manifest["files"]


def test_export_stories_json_includes_sources(data_folder):
    """stories.json emits the ``sources`` array only for stories that declare it."""
    # Rewrite stories.yml so one story has sources, the other doesn't.
    (data_folder / "stories" / "stories.yml").write_text(
        "The Creation:\n  book: Genesis\n  verses: ['1:1']\n"
        "The Exodus:\n  book: Exodus\n  verses: ['1:1']\n  sources: ['E', 'P']\n",
        encoding="utf-8",
    )

    with tempfile.TemporaryDirectory() as out_tmp:
        out_dir = Path(out_tmp) / "dist"
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = export_command(["--out", str(out_dir), "--verbosity", "WARNING"])
        assert rc == 0

        stories_payload = json.loads((out_dir / "stories.json").read_text())
        assert stories_payload["The Exodus"]["sources"] == ["E", "P"]
        # Stories without sources stay byte-identical to the legacy shape.
        assert "sources" not in stories_payload["The Creation"]


def test_export_drops_results_for_unknown_stories(data_folder):
    """Cached results whose story isn't in the YAML are dropped from the bundle."""
    # The fixture's stories.yml knows about "The Creation" and "The Exodus".
    # Add a cache file for a story that isn't there.
    orphan = data_folder / "results" / "orphan.json"
    orphan.write_text(
        json.dumps(
            {
                "answer": True,
                "certainty": 75,
                "story": "Ghost Story",
                "prompt": "1",
                "engine": "chatgpt:gpt-4",
            }
        )
    )

    with tempfile.TemporaryDirectory() as out_tmp:
        out_dir = Path(out_tmp) / "dist"
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = export_command(["--out", str(out_dir), "--verbosity", "WARNING"])
        assert rc == 0

        manifest = json.loads((out_dir / "index.json").read_text())
        # Manifest only mentions stories that exist in the YAML.
        assert "Ghost Story" not in manifest["stories"]
        # Pre-existing fixture has 4 results across the two known stories; the
        # orphan must not inflate the count.
        assert manifest["total_results"] == 4
        # And no shard for an unknown story's book either.
        assert all(s["book"] != "unknown" for s in manifest["shards"])


def test_export_stories_file_flag_picks_alternate_yaml(data_folder):
    """--stories-file selects an alternate YAML file in the data folder."""
    (data_folder / "stories" / "stories-alt.yml").write_text(
        "Only Story:\n  book: Genesis\n  verses: ['1:1']\n  sources: ['Alt']\n",
        encoding="utf-8",
    )

    with tempfile.TemporaryDirectory() as out_tmp:
        out_dir = Path(out_tmp) / "dist"
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = export_command(
                [
                    "--out",
                    str(out_dir),
                    "--stories-file",
                    "stories-alt.yml",
                    "--verbosity",
                    "WARNING",
                ]
            )
        assert rc == 0

        stories_payload = json.loads((out_dir / "stories.json").read_text())
        assert set(stories_payload.keys()) == {"Only Story"}
        assert stories_payload["Only Story"]["sources"] == ["Alt"]
