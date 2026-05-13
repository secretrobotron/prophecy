"""
Tests for --period/--topic prompt selection, --concatenate bundling,
and the `query` subcommand.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prophecy.__main__ import (
    build_concatenated_prompt,
    normalize_known,
    parse_multi_value,
    query_command,
    select_prompts,
    select_stories,
)
from prophecy.prompts import Prompts
from prophecy.stories import Stories


@pytest.fixture
def data_folder():
    """Build a tiny data folder with prompts.tsv, template.txt, stories.yml."""
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "data"
        data.mkdir()

        (data / "prompts.tsv").write_text(
            "id\tperiod\ttopic\tprompt\n"
            "1\tBabylonian\tGeo\tThere is destruction\n"
            "2\tBabylonian\tGeo\tThere is famine\n"
            "3\tPolitics\tPopulism\tThe people make decisions\n"
            "4\tPolitics\tPopulism\tThe leader is humble\n"
            "5\tPolitics\tElitism\tThe leaders rage at the people\n",
            encoding="utf-8",
        )
        (data / "template.txt").write_text('"$prompt"\n\n"$text"\n', encoding="utf-8")
        (data / "stories.yml").write_text(
            "Sample Story:\n  book: Genesis\n  verses: ['1:1']\n"
            "Exodus Story:\n  book: Exodus\n  verses: ['1:1']\n"
            "Another Genesis Story:\n  book: Genesis\n  verses: ['2:1']\n",
            encoding="utf-8",
        )
        (data / "index.json").write_text("{}", encoding="utf-8")
        yield data


class TestSelectPrompts:
    def test_default_all(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        result = select_prompts(prompts, "all", None, None)
        assert len(result) == 5

    def test_period_filter(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        result = select_prompts(prompts, "all", "Politics", None)
        assert len(result) == 3
        assert all(p["period"] == "Politics" for p in result)

    def test_period_and_topic_filter(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        result = select_prompts(prompts, "all", "Politics", "Populism")
        assert len(result) == 2
        assert {p["id"] for p in result} == {"3", "4"}

    def test_topic_only_filter(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        result = select_prompts(prompts, "all", None, "Elitism")
        assert len(result) == 1
        assert result[0]["id"] == "5"

    def test_specific_prompt_id(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        result = select_prompts(prompts, "2", None, None)
        assert len(result) == 1
        assert result[0]["id"] == "2"

    def test_specific_prompt_with_period_rejected(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        with pytest.raises(ValueError, match="cannot be combined"):
            select_prompts(prompts, "1", "Politics", None)

    def test_unknown_period_rejected(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        with pytest.raises(ValueError, match="Period 'Nope' not found"):
            select_prompts(prompts, "all", "Nope", None)

    def test_unknown_topic_rejected(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        with pytest.raises(ValueError, match="Topic 'Nope' not found"):
            select_prompts(prompts, "all", None, "Nope")

    def test_empty_intersection_rejected(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        # Both exist, but never co-occur on the same row
        with pytest.raises(ValueError, match="No prompts match"):
            select_prompts(prompts, "all", "Babylonian", "Populism")

    def test_multiple_topics_via_list(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        result = select_prompts(prompts, "all", None, ["Populism", "Elitism"])
        assert {p["id"] for p in result} == {"3", "4", "5"}

    def test_multiple_periods_via_list(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        result = select_prompts(prompts, "all", ["Politics", "Babylonian"], None)
        assert {p["id"] for p in result} == {"1", "2", "3", "4", "5"}

    def test_unknown_value_in_list_rejected(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        with pytest.raises(ValueError, match="Topic 'Nope' not found"):
            select_prompts(prompts, "all", None, ["Populism", "Nope"])


class TestSelectStories:
    def test_no_book_returns_all(self, data_folder):
        stories = Stories(data_folder=data_folder)
        result = select_stories(stories, "all", None)
        assert set(result) == {"Sample Story", "Exodus Story", "Another Genesis Story"}

    def test_single_book(self, data_folder):
        stories = Stories(data_folder=data_folder)
        result = select_stories(stories, "all", ["Genesis"])
        assert set(result) == {"Sample Story", "Another Genesis Story"}

    def test_multiple_books(self, data_folder):
        stories = Stories(data_folder=data_folder)
        result = select_stories(stories, "all", ["Genesis", "Exodus"])
        assert set(result) == {"Sample Story", "Exodus Story", "Another Genesis Story"}

    def test_unknown_book_rejected(self, data_folder):
        stories = Stories(data_folder=data_folder)
        with pytest.raises(ValueError, match="Book 'Leviticus' not found"):
            select_stories(stories, "all", ["Leviticus"])

    def test_explicit_story_must_be_in_book(self, data_folder):
        stories = Stories(data_folder=data_folder)
        with pytest.raises(ValueError, match="isn't in --book"):
            select_stories(stories, "Exodus Story", ["Genesis"])

    def test_explicit_story_in_book_passes(self, data_folder):
        stories = Stories(data_folder=data_folder)
        result = select_stories(stories, "Exodus Story", ["Exodus"])
        assert result == ["Exodus Story"]

    def test_explicit_story_no_book_filter(self, data_folder):
        stories = Stories(data_folder=data_folder)
        result = select_stories(stories, "Sample Story", None)
        assert result == ["Sample Story"]


class TestNormalizeKnown:
    def test_exact_match(self):
        assert normalize_known("Exodus", ["Exodus", "Genesis"], "Book") == "Exodus"

    def test_lowercase_input(self):
        assert normalize_known("exodus", ["Exodus", "Genesis"], "Book") == "Exodus"

    def test_uppercase_input(self):
        assert normalize_known("EXODUS", ["Exodus", "Genesis"], "Book") == "Exodus"

    def test_mixed_case_input(self):
        assert normalize_known("ExOdUs", ["Exodus", "Genesis"], "Book") == "Exodus"

    def test_unknown_value_raises_with_kind(self):
        with pytest.raises(ValueError, match="Book 'Leviticus' not found"):
            normalize_known("Leviticus", ["Exodus", "Genesis"], "Book")

    def test_unknown_value_includes_available_sample(self):
        with pytest.raises(ValueError, match="Available: Exodus, Genesis"):
            normalize_known("Leviticus", ["Exodus", "Genesis"], "Book")


class TestCaseInsensitiveSelectors:
    def test_select_prompts_period_lowercase(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        result = select_prompts(prompts, "all", "politics", None)
        assert all(p["period"] == "Politics" for p in result)

    def test_select_prompts_topic_uppercase(self, data_folder):
        prompts = Prompts(data_folder=data_folder)
        result = select_prompts(prompts, "all", None, "POPULISM")
        assert all(p["topic"] == "Populism" for p in result)

    def test_select_stories_book_lowercase(self, data_folder):
        stories = Stories(data_folder=data_folder)
        result = select_stories(stories, "all", ["exodus"])
        assert result == ["Exodus Story"]

    def test_select_stories_explicit_story_mixed_case(self, data_folder):
        stories = Stories(data_folder=data_folder)
        result = select_stories(stories, "exodus story", ["exodus"])
        assert result == ["Exodus Story"]


class TestParseMultiValue:
    def test_none_returns_none(self):
        assert parse_multi_value(None) is None

    def test_empty_list_returns_none(self):
        assert parse_multi_value([]) is None

    def test_single_value(self):
        assert parse_multi_value(["Populism"]) == ["Populism"]

    def test_repeated_flag(self):
        assert parse_multi_value(["A", "B"]) == ["A", "B"]

    def test_comma_separated(self):
        assert parse_multi_value(["A,B,C"]) == ["A", "B", "C"]

    def test_mixed_repeat_and_comma(self):
        assert parse_multi_value(["A,B", "C"]) == ["A", "B", "C"]

    def test_whitespace_trimmed(self):
        assert parse_multi_value([" A , B "]) == ["A", "B"]

    def test_empty_segments_skipped(self):
        assert parse_multi_value(["A,,B"]) == ["A", "B"]
        assert parse_multi_value([","]) is None


class TestBuildConcatenatedPrompt:
    def test_synthetic_id_uses_filter_labels(self):
        records = [
            {"id": "3", "period": "Politics", "topic": "Populism", "prompt": "A"},
            {"id": "4", "period": "Politics", "topic": "Populism", "prompt": "B"},
        ]
        combined = build_concatenated_prompt(records, "Politics", "Populism")
        assert combined["id"] == "concat:Politics:Populism"
        assert combined["period"] == "Politics"
        assert combined["topic"] == "Populism"
        assert "1. A" in combined["prompt"]
        assert "2. B" in combined["prompt"]
        assert combined["_concatenated_ids"] == "3,4"

    def test_unset_filters_fall_back_to_uniform_record_metadata(self):
        records = [
            {"id": "1", "period": "Babylonian", "topic": "Geo", "prompt": "X"},
            {"id": "2", "period": "Babylonian", "topic": "Geo", "prompt": "Y"},
        ]
        combined = build_concatenated_prompt(records, None, None)
        assert combined["id"] == "concat:Babylonian:Geo"

    def test_mixed_periods_use_all_label(self):
        records = [
            {"id": "1", "period": "Babylonian", "topic": "Geo", "prompt": "X"},
            {"id": "3", "period": "Politics", "topic": "Populism", "prompt": "Y"},
        ]
        combined = build_concatenated_prompt(records, None, None)
        assert combined["period"] == "all"
        assert combined["topic"] == "all"
        assert combined["id"] == "concat:all:all"

    def test_empty_records_rejected(self):
        with pytest.raises(ValueError, match="empty prompt set"):
            build_concatenated_prompt([], None, None)

    def test_list_topic_joined_with_plus(self):
        records = [
            {"id": "3", "period": "Politics", "topic": "Populism", "prompt": "A"},
            {"id": "5", "period": "Politics", "topic": "Elitism", "prompt": "B"},
        ]
        combined = build_concatenated_prompt(records, "Politics", ["Populism", "Elitism"])
        assert combined["topic"] == "Populism+Elitism"
        assert combined["id"] == "concat:Politics:Populism+Elitism"


class TestQueryCommand:
    def _write_results(self, cache: Path, results: list[dict]):
        cache.mkdir(parents=True, exist_ok=True)
        for i, r in enumerate(results):
            (cache / f"r{i}.json").write_text(json.dumps(r), encoding="utf-8")

    def test_query_aggregates_and_filters(self, data_folder, capsys):
        cache = data_folder / "results"
        self._write_results(
            cache,
            [
                {"answer": True, "certainty": 90, "story": "Sample Story", "prompt": "3"},
                {"answer": True, "certainty": 80, "story": "Sample Story", "prompt": "4"},
                {"answer": False, "certainty": 70, "story": "Sample Story", "prompt": "5"},
                {"answer": True, "certainty": 95, "story": "Sample Story", "prompt": "1"},
            ],
        )

        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--period", "Politics", "--format", "json"])
        assert rc == 0
        out = capsys.readouterr().out
        rows = json.loads(out)

        # Two topics within Politics: Populism (2 hits / 2 total) + Elitism (0 hits / 1 total)
        assert len(rows) == 2
        by_topic = {r["topic"]: r for r in rows}
        assert by_topic["Populism"]["hits"] == 2
        assert by_topic["Populism"]["total"] == 2
        assert by_topic["Populism"]["hit_rate"] == 1.0
        assert by_topic["Elitism"]["hits"] == 0
        assert by_topic["Elitism"]["total"] == 1

    def test_query_min_certainty_filter(self, data_folder, capsys):
        cache = data_folder / "results"
        self._write_results(
            cache,
            [
                {"answer": True, "certainty": 50, "story": "Sample Story", "prompt": "3"},
                {"answer": True, "certainty": 95, "story": "Sample Story", "prompt": "4"},
            ],
        )

        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--min-certainty", "80", "--format", "json"])
        assert rc == 0
        rows = json.loads(capsys.readouterr().out)
        assert len(rows) == 1
        assert rows[0]["hits"] == 1
        assert rows[0]["total"] == 1

    def test_query_book_filter(self, data_folder, capsys):
        cache = data_folder / "results"
        self._write_results(
            cache,
            [
                {"answer": True, "certainty": 90, "story": "Sample Story", "prompt": "3"},
            ],
        )
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--book", "Exodus", "--format", "json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out) == []

    def test_query_concat_synthetic_id(self, data_folder, capsys):
        cache = data_folder / "results"
        self._write_results(
            cache,
            [
                {
                    "answer": True,
                    "certainty": 88,
                    "story": "Sample Story",
                    "prompt": "concat:Politics:Populism",
                }
            ],
        )
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--period", "Politics", "--format", "json"])
        assert rc == 0
        rows = json.loads(capsys.readouterr().out)
        assert len(rows) == 1
        assert rows[0]["period"] == "Politics"
        assert rows[0]["topic"] == "Populism"

    def test_query_multiple_topics(self, data_folder, capsys):
        cache = data_folder / "results"
        self._write_results(
            cache,
            [
                {"answer": True, "certainty": 90, "story": "Sample Story", "prompt": "3"},
                {"answer": False, "certainty": 80, "story": "Sample Story", "prompt": "5"},
                {"answer": True, "certainty": 95, "story": "Sample Story", "prompt": "1"},
            ],
        )
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--topic", "Populism,Elitism", "--format", "json"])
        assert rc == 0
        rows = json.loads(capsys.readouterr().out)
        topics = {r["topic"] for r in rows}
        assert topics == {"Populism", "Elitism"}
        # The Babylonian result (topic "Geo") should be excluded
        assert all(r["topic"] != "Geo" for r in rows)

    def test_query_engine_filter(self, data_folder, capsys):
        cache = data_folder / "results"
        self._write_results(
            cache,
            [
                {
                    "answer": True,
                    "certainty": 90,
                    "story": "Sample Story",
                    "prompt": "3",
                    "engine": "chatgpt:gpt-4",
                },
                {
                    "answer": False,
                    "certainty": 80,
                    "story": "Sample Story",
                    "prompt": "3",
                    "engine": "claude:claude-3-haiku-20240307",
                },
                {"answer": True, "certainty": 70, "story": "Sample Story", "prompt": "3"},
            ],
        )
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--engine", "chatgpt:gpt-4", "--format", "json"])
        assert rc == 0
        rows = json.loads(capsys.readouterr().out)
        assert len(rows) == 1
        assert rows[0]["engine"] == "chatgpt:gpt-4"

    def test_query_groups_by_engine(self, data_folder, capsys):
        cache = data_folder / "results"
        self._write_results(
            cache,
            [
                {
                    "answer": True,
                    "certainty": 90,
                    "story": "Sample Story",
                    "prompt": "3",
                    "engine": "chatgpt:gpt-4",
                },
                {
                    "answer": False,
                    "certainty": 80,
                    "story": "Sample Story",
                    "prompt": "3",
                    "engine": "claude:claude-3-haiku-20240307",
                },
            ],
        )
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--format", "json"])
        assert rc == 0
        rows = json.loads(capsys.readouterr().out)
        # Same (story, period, topic) but two engines → two rows
        engines = {r["engine"] for r in rows}
        assert engines == {"chatgpt:gpt-4", "claude:claude-3-haiku-20240307"}

    def test_query_period_case_insensitive(self, data_folder, capsys):
        cache = data_folder / "results"
        self._write_results(
            cache,
            [
                {"answer": True, "certainty": 90, "story": "Sample Story", "prompt": "3"},
            ],
        )
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--period", "politics", "--format", "json"])
        assert rc == 0
        rows = json.loads(capsys.readouterr().out)
        assert len(rows) == 1
        assert rows[0]["period"] == "Politics"

    def test_query_unknown_book_errors(self, data_folder, capsys):
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--book", "Leviticus", "--format", "json"])
        assert rc == 1

    def test_parallel_workers_all_complete(self, data_folder, capsys, tmp_path):
        # Exercise the ThreadPoolExecutor path end-to-end with a stub provider.
        from unittest.mock import MagicMock

        from prophecy import __main__ as main_mod
        from prophecy.__main__ import process_all_combinations
        from prophecy.bible import Bible
        from prophecy.settings import Settings
        from prophecy.stories import Stories

        prompts = Prompts(data_folder=data_folder)
        stories = Stories(data_folder=data_folder)
        bible = MagicMock(spec=Bible)

        ai_provider = MagicMock()
        ai_provider.engine_id = "stub:1"
        ai_provider.post_prompt.return_value = '{"answer":true,"reason":"stub","certainty":42}'

        args = MagicMock()
        args.dry_run = False
        args.ai_provider = "stub"
        args.workers = 4
        args.concatenate = False
        args.period = None
        args.topic = None

        settings = Settings(data_folder=data_folder, cache_folder=tmp_path / "results")

        # Per-story unique text so the cache key (MD5 of the populated template)
        # differs for every (story, prompt) — matches real biblical text behavior.
        def fake_text(_bible, story, _logger):
            return f"text-for-{story.title}"

        with patch.object(main_mod, "get_biblical_text", side_effect=fake_text):
            process_all_combinations(
                stories,
                prompts,
                bible,
                story_titles=stories.titles,
                prompt_list=prompts.get_prompts(),
                ai_provider=ai_provider,
                args=args,
                settings=settings,
                logger=__import__("logging").getLogger("test"),
            )

        # Every (story, prompt) combo should have produced exactly one cached
        # JSON file. The cache is checksum-keyed and engine-namespaced, so no
        # collisions and no missing items.
        cache_dir = tmp_path / "results"
        cached_files = list(cache_dir.glob("*.json"))
        expected = len(stories.titles) * len(prompts.get_prompts())
        assert len(cached_files) == expected, (
            f"Expected {expected} cached files, got {len(cached_files)}"
        )
        # The provider should have been hit exactly that many times too.
        assert ai_provider.post_prompt.call_count == expected

    def test_query_tsv_format_header_and_rows(self, data_folder, capsys):
        cache = data_folder / "results"
        self._write_results(
            cache,
            [
                {"answer": True, "certainty": 90, "story": "Sample Story", "prompt": "3"},
            ],
        )
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": str(data_folder)}, clear=False):
            rc = query_command(["--format", "tsv"])
        assert rc == 0
        lines = capsys.readouterr().out.strip().split("\n")
        assert lines[0] == (
            "story\tbook\tperiod\ttopic\tengine\thits\ttotal\thit_rate\tavg_certainty"
        )
        assert len(lines) == 2
        assert lines[1].startswith("Sample Story\tGenesis\tPolitics\tPopulism\tunknown\t1\t1\t")
