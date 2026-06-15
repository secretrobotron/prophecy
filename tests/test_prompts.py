#!/usr/bin/env python3
"""
Test module to verify the structure and content of data/prompts*.tsv.

The Prompts class loads ``prompts.tsv`` plus any auxiliary
``prompts.<name>.tsv`` files in the same folder, so these tests apply the
same structural checks to every TSV in that set and additionally verify
that IDs are globally unique across the union.

Requirements being tested:
1. Each file must be tab-separated data with exactly four columns
2. Headers must be 'id', 'category', 'topic', and 'prompt'
3. ID values must be unique within each file and across the full set
"""

import csv
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "data"
PROMPTS_DIR = DATA_DIR / "prompts"
PROMPT_FILES = sorted(PROMPTS_DIR.glob("prompts*.tsv"))
PROMPT_FILE_IDS = [p.name for p in PROMPT_FILES]


def _read_rows(path: Path) -> list[list[str]]:
    with open(path, encoding="utf-8") as f:
        return [row for row in csv.reader(f, delimiter="\t")]


@pytest.fixture(scope="module")
def prompt_files() -> list[Path]:
    # No filename is mandatory — any prompts*.tsv counts — but at least
    # one file with some data must exist or the pipeline has nothing to do.
    assert PROMPT_FILES, f"No prompts*.tsv files found under {PROMPTS_DIR}"
    return PROMPT_FILES


@pytest.mark.parametrize("prompts_file", PROMPT_FILES, ids=PROMPT_FILE_IDS)
class TestPromptsFileStructure:
    """Structural checks applied to every prompts*.tsv file in data/."""

    def test_file_exists(self, prompts_file):
        assert prompts_file.exists(), f"{prompts_file} should exist"

    def test_file_is_tab_separated_with_four_columns(self, prompts_file):
        rows = _read_rows(prompts_file)
        assert rows, f"{prompts_file} should not be empty"
        for i, row in enumerate(rows):
            assert len(row) == 4, (
                f"{prompts_file.name} row {i + 1} has {len(row)} columns, expected 4. "
                f"Row content: {row}"
            )

    def test_headers_are_correct(self, prompts_file):
        rows = _read_rows(prompts_file)
        expected = ["id", "category", "topic", "prompt"]
        assert rows[0] == expected, (
            f"{prompts_file.name} headers should be {expected}, found {rows[0]}"
        )

    def test_id_values_unique_within_file(self, prompts_file):
        rows = _read_rows(prompts_file)
        data_rows = [r for r in rows[1:] if r]
        ids = [r[0] for r in data_rows]
        unique = set(ids)
        if len(ids) != len(unique):
            seen, dupes = set(), set()
            for value in ids:
                if value in seen:
                    dupes.add(value)
                seen.add(value)
            pytest.fail(f"{prompts_file.name}: duplicate ID values: {sorted(dupes)}")

    def test_no_empty_cells(self, prompts_file):
        rows = _read_rows(prompts_file)
        for i, row in enumerate(rows[1:], start=2):
            if not row:
                continue
            for col_name, cell in zip(["id", "category", "topic", "prompt"], row, strict=False):
                assert cell and cell.strip(), (
                    f"{prompts_file.name} row {i}, column '{col_name}' is empty"
                )

    def test_tab_separation_consistency(self, prompts_file):
        with open(prompts_file, encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                stripped = line.rstrip("\n")
                if not stripped.strip():
                    continue
                tab_count = stripped.count("\t")
                assert tab_count == 3, (
                    f"{prompts_file.name} line {i} has {tab_count} tabs, expected 3. "
                    f"Line content: '{stripped[:100]}...'"
                )


class TestPromptsGlobal:
    """Checks that span the full set of prompts*.tsv files."""

    def test_at_least_one_data_row_total(self, prompt_files):
        total = 0
        for path in prompt_files:
            rows = _read_rows(path)
            total += sum(1 for r in rows[1:] if r and any(cell.strip() for cell in r))
        assert total >= 1, "There must be at least one data row across all prompt files"

    def test_ids_globally_unique(self, prompt_files):
        origin: dict[str, Path] = {}
        collisions: list[tuple[str, Path, Path]] = []
        for path in prompt_files:
            rows = _read_rows(path)
            for row in rows[1:]:
                if not row:
                    continue
                prompt_id = row[0]
                if prompt_id in origin:
                    collisions.append((prompt_id, origin[prompt_id], path))
                else:
                    origin[prompt_id] = path
        if collisions:
            details = ", ".join(
                f"'{pid}' in both {a.name} and {b.name}" for pid, a, b in collisions
            )
            pytest.fail(f"Duplicate IDs across prompt files: {details}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
