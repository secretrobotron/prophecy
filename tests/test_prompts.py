#!/usr/bin/env python3
"""
Test module to verify the structure and content of data/prompts*.tsv.

The Prompts class loads ``prompts.tsv`` plus any auxiliary
``prompts.<name>.tsv`` files in the same folder, so these tests apply the
same structural checks to every TSV in that set and additionally verify
that IDs are globally unique across the union.

Requirements being tested:
1. Each file must be tab-separated data with four or five columns
   (the optional fifth column is ``weight``)
2. Headers must start with 'id', 'category', 'topic', 'prompt' and may
   include a trailing 'weight'
3. ID values must be unique within each file and across the full set
4. ``id``/``category``/``topic``/``prompt`` cells must be non-empty;
   ``weight`` may be blank (means: no explicit weight)
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

    def test_file_is_tab_separated_with_expected_columns(self, prompts_file):
        rows = _read_rows(prompts_file)
        assert rows, f"{prompts_file} should not be empty"
        header_cols = len(rows[0])
        assert header_cols in (4, 5), (
            f"{prompts_file.name} header has {header_cols} columns, expected 4 or 5. "
            f"Row content: {rows[0]}"
        )
        for i, row in enumerate(rows):
            assert len(row) == header_cols, (
                f"{prompts_file.name} row {i + 1} has {len(row)} columns, "
                f"expected {header_cols} (to match the header). Row content: {row}"
            )

    def test_headers_are_correct(self, prompts_file):
        rows = _read_rows(prompts_file)
        required = ["id", "category", "topic", "prompt"]
        # Required columns first, optional 'weight' column allowed at the end.
        assert rows[0][: len(required)] == required, (
            f"{prompts_file.name} headers must start with {required}, found {rows[0]}"
        )
        extras = rows[0][len(required) :]
        assert extras in ([], ["weight"]), (
            f"{prompts_file.name} unexpected trailing headers: {extras} "
            f"(only optional 'weight' is allowed)"
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

    def test_required_cells_non_empty(self, prompts_file):
        """``weight`` may be blank but the other four columns must be filled."""
        rows = _read_rows(prompts_file)
        required = ["id", "category", "topic", "prompt"]
        for i, row in enumerate(rows[1:], start=2):
            if not row:
                continue
            for col_name, cell in zip(required, row[: len(required)], strict=False):
                assert cell and cell.strip(), (
                    f"{prompts_file.name} row {i}, column '{col_name}' is empty"
                )

    def test_tab_separation_consistency(self, prompts_file):
        rows = _read_rows(prompts_file)
        expected_tabs = len(rows[0]) - 1  # tab count matches the header width
        with open(prompts_file, encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                stripped = line.rstrip("\n")
                if not stripped.strip():
                    continue
                tab_count = stripped.count("\t")
                assert tab_count == expected_tabs, (
                    f"{prompts_file.name} line {i} has {tab_count} tabs, "
                    f"expected {expected_tabs}. Line content: '{stripped[:100]}...'"
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
