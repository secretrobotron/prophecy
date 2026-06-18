#!/usr/bin/env python3
"""
Unit tests for the Prompts class.

This module tests the Prompts class functionality including initialization,
data access, template population, and line folding.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from prophecy.prompts import Prompts


class TestPrompts:
    """Test class for the Prompts functionality."""

    @pytest.fixture
    def temp_data_folder(self):
        """Create a temporary data folder with test data/prompts/{prompts.tsv,template.txt}."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir()
            prompts_dir = data_dir / "prompts"
            prompts_dir.mkdir()

            # Create test prompts.tsv with actual tab characters
            with open(prompts_dir / "prompts.tsv", "w", encoding="utf-8") as f:
                f.write("id\tcategory\ttopic\tprompt\n")
                f.write(
                    "1\tBabylonian\tGeopolitical Danger\tThere is an upcoming significant man-made destruction\n"
                )
                f.write(
                    "2\tPersian\tCyrus the Great\tA messenger of Yahweh entered a city in peace\n"
                )
                f.write(
                    "3\tHellenistic\tHellenistic Neighbors\tThe Hebrews live near foreign neighbors\n"
                )
                f.write("4\tBabylonian\tGeopolitical Danger\tThere is a great disaster\n")

            # Create test template.txt
            template_content = """Question 1: The fragment originates in the $category category.

Question 2: The fragment pertains to the topic: "$topic".

Question 3: The following statement applies to the fragment: "$prompt"

Below is the text fragment:

$text"""

            with open(prompts_dir / "template.txt", "w", encoding="utf-8") as f:
                f.write(template_content)

            yield str(data_dir)

    def test_init_with_data_folder(self, temp_data_folder):
        """Test Prompts initialization with explicit data folder."""
        prompts = Prompts(temp_data_folder)
        assert prompts.data_folder == Path(temp_data_folder)
        assert prompts.get_prompt_count() == 4

    def test_init_with_env_var(self, temp_data_folder):
        """Test Prompts initialization with environment variable."""
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": temp_data_folder}):
            prompts = Prompts()
            assert prompts.data_folder == Path(temp_data_folder)

    def test_init_with_default_data_folder(self):
        """Test Prompts initialization with default data folder."""
        with patch.dict(os.environ, {}, clear=True):
            # Should default to 'data' - test depends on whether data folder exists
            try:
                prompts = Prompts()
                # If this succeeds, data folder exists and has valid files
                assert prompts.data_folder == Path("data")
                assert isinstance(prompts.get_prompt_count(), int)
            except FileNotFoundError:
                # This is also acceptable if no data folder exists
                pass

    def test_init_nonexistent_folder(self):
        """Test Prompts initialization with non-existent data folder."""
        with pytest.raises(FileNotFoundError, match="Data folder not found"):
            Prompts("/nonexistent/path")

    def test_init_no_prompt_files(self, temp_data_folder):
        """When the prompts folder has no prompts*.tsv files at all,
        construction fails fast — the pipeline has nothing to do."""
        prompts_dir = Path(temp_data_folder) / "prompts"
        for f in prompts_dir.glob("prompts*.tsv"):
            f.unlink()
        with pytest.raises(FileNotFoundError, match="No prompts\\*.tsv files found"):
            Prompts(temp_data_folder)

    def test_init_missing_template_file(self, temp_data_folder):
        """Test Prompts initialization with missing template.txt."""
        os.remove(Path(temp_data_folder) / "prompts" / "template.txt")
        with pytest.raises(FileNotFoundError, match="Template file not found"):
            Prompts(temp_data_folder)

    def test_init_empty_prompts_file(self, temp_data_folder):
        """Test Prompts initialization with empty prompts.tsv."""
        # Write only header
        with open(Path(temp_data_folder) / "prompts" / "prompts.tsv", "w") as f:
            f.write("id\tcategory\ttopic\tprompt\n")

        with pytest.raises(ValueError, match="No prompts data found"):
            Prompts(temp_data_folder)

    def test_get_prompts(self, temp_data_folder):
        """Test getting all prompts."""
        prompts = Prompts(temp_data_folder)
        all_prompts = prompts.get_prompts()

        assert isinstance(all_prompts, list)
        assert len(all_prompts) == 4

        # Check structure of first prompt
        first_prompt = all_prompts[0]
        assert "id" in first_prompt
        assert "category" in first_prompt
        assert "topic" in first_prompt
        assert "prompt" in first_prompt
        assert first_prompt["id"] == "1"
        assert first_prompt["category"] == "Babylonian"
        assert first_prompt["topic"] == "Geopolitical Danger"

        # Test that it returns a copy (modifications don't affect original)
        all_prompts[0]["id"] = "modified"
        new_all_prompts = prompts.get_prompts()
        assert new_all_prompts[0]["id"] == "1"

    def test_get_prompt_by_id_valid(self, temp_data_folder):
        """Test getting a specific prompt by valid ID."""
        prompts = Prompts(temp_data_folder)

        prompt = prompts.get_prompt_by_id("2")
        assert prompt["id"] == "2"
        assert prompt["category"] == "Persian"
        assert prompt["topic"] == "Cyrus the Great"
        assert prompt["prompt"] == "A messenger of Yahweh entered a city in peace"

        # Test with numeric ID
        prompt = prompts.get_prompt_by_id(3)
        assert prompt["id"] == "3"

    def test_get_prompt_by_id_invalid(self, temp_data_folder):
        """Test getting a prompt by invalid ID."""
        prompts = Prompts(temp_data_folder)

        with pytest.raises(ValueError, match="Prompt ID '999' not found"):
            prompts.get_prompt_by_id("999")

    def test_get_prompts_by_category(self, temp_data_folder):
        """Test getting prompts filtered by category."""
        prompts = Prompts(temp_data_folder)

        babylonian_prompts = prompts.get_prompts_by_category("Babylonian")
        assert len(babylonian_prompts) == 2
        for prompt in babylonian_prompts:
            assert prompt["category"] == "Babylonian"

        persian_prompts = prompts.get_prompts_by_category("Persian")
        assert len(persian_prompts) == 1
        assert persian_prompts[0]["id"] == "2"

        # Test non-existent category
        empty_prompts = prompts.get_prompts_by_category("NonExistent")
        assert len(empty_prompts) == 0

    def test_get_prompts_by_topic(self, temp_data_folder):
        """Test getting prompts filtered by topic."""
        prompts = Prompts(temp_data_folder)

        geo_danger_prompts = prompts.get_prompts_by_topic("Geopolitical Danger")
        assert len(geo_danger_prompts) == 2
        for prompt in geo_danger_prompts:
            assert prompt["topic"] == "Geopolitical Danger"

        cyrus_prompts = prompts.get_prompts_by_topic("Cyrus the Great")
        assert len(cyrus_prompts) == 1
        assert cyrus_prompts[0]["id"] == "2"

    def test_get_categories(self, temp_data_folder):
        """Test getting unique categories."""
        prompts = Prompts(temp_data_folder)
        categories = prompts.get_categories()

        assert isinstance(categories, list)
        assert set(categories) == {"Babylonian", "Persian", "Hellenistic"}
        assert categories == sorted(categories)  # Should be sorted

    def test_get_topics(self, temp_data_folder):
        """Test getting unique topics."""
        prompts = Prompts(temp_data_folder)
        topics = prompts.get_topics()

        assert isinstance(topics, list)
        expected_topics = {"Geopolitical Danger", "Cyrus the Great", "Hellenistic Neighbors"}
        assert set(topics) == expected_topics
        assert topics == sorted(topics)  # Should be sorted

    def test_get_template_content(self, temp_data_folder):
        """Test getting template content."""
        prompts = Prompts(temp_data_folder)
        template = prompts.get_template_content()

        assert isinstance(template, str)
        assert "$category" in template
        assert "$topic" in template
        assert "$prompt" in template
        assert "$text" in template

    def test_get_prompt_count(self, temp_data_folder):
        """Test getting prompt count."""
        prompts = Prompts(temp_data_folder)
        assert prompts.get_prompt_count() == 4

    def test_fold_lines_short_lines(self, temp_data_folder):
        """Test line folding with lines shorter than limit."""
        prompts = Prompts(temp_data_folder)

        short_text = "Short line\nAnother short line"
        folded = prompts._fold_lines(short_text, width=100)
        assert folded == short_text

    def test_fold_lines_long_lines(self, temp_data_folder):
        """Test line folding with lines longer than limit."""
        prompts = Prompts(temp_data_folder)

        long_line = "This is a very long line that definitely exceeds the specified width and should be wrapped properly without breaking words unnecessarily or incorrectly."
        folded = prompts._fold_lines(long_line, width=50)

        lines = folded.split("\n")
        for line in lines:
            assert len(line) <= 50

        # Should preserve content
        assert long_line.replace(" ", "") in folded.replace(" ", "").replace("\n", "")

    def test_fold_lines_mixed_content(self, temp_data_folder):
        """Test line folding with mixed short and long lines."""
        prompts = Prompts(temp_data_folder)

        mixed_text = """Short line
This is a very long line that should be wrapped because it exceeds the maximum width
Another short line
Another very long line that needs to be wrapped at the appropriate width to ensure proper formatting"""

        folded = prompts._fold_lines(mixed_text, width=50)
        lines = folded.split("\n")

        # Check that all lines are within limit
        for line in lines:
            assert len(line) <= 50

        # Check that short lines are preserved
        assert "Short line" in lines
        assert "Another short line" in lines

    def test_populate_template_valid_inputs(self, temp_data_folder):
        """Test template population with valid inputs."""
        prompts = Prompts(temp_data_folder)

        # Create mock story object
        mock_story = Mock()
        mock_story.title = "Test Story"
        mock_story.book = "Genesis"
        mock_story.verses = ["1:1-1:3"]

        prompt_record = {
            "id": "1",
            "category": "Babylonian",
            "topic": "Geopolitical Danger",
            "prompt": "There is an upcoming significant destruction",
        }

        text = "In the beginning God created the heaven and the earth."

        result = prompts.populate_template(prompt_record, mock_story, text)

        assert isinstance(result, str)
        assert "Babylonian" in result
        assert "Geopolitical Danger" in result
        # Check for the prompt text, accounting for potential line folding
        assert "There is an upcoming significant destruction" in result.replace("\n", " ")
        assert text in result

        # Check that lines are properly folded
        lines = result.split("\n")
        for line in lines:
            assert len(line) <= 100

    def test_populate_template_missing_prompt_keys(self, temp_data_folder):
        """Test template population with missing prompt record keys."""
        prompts = Prompts(temp_data_folder)

        mock_story = Mock()
        mock_story.title = "Test Story"
        mock_story.book = "Genesis"
        mock_story.verses = ["1:1-1:3"]

        # Missing 'prompt' key
        incomplete_prompt = {"id": "1", "category": "Babylonian", "topic": "Geopolitical Danger"}

        with pytest.raises(ValueError, match="Prompt record missing required keys"):
            prompts.populate_template(incomplete_prompt, mock_story, "text")

    def test_populate_template_missing_story_attributes(self, temp_data_folder):
        """Test template population with missing story object attributes."""
        prompts = Prompts(temp_data_folder)

        # Story missing 'verses' attribute
        incomplete_story = Mock()
        incomplete_story.title = "Test Story"
        incomplete_story.book = "Genesis"
        # Missing verses attribute

        prompt_record = {
            "id": "1",
            "category": "Babylonian",
            "topic": "Geopolitical Danger",
            "prompt": "There is an upcoming significant destruction",
        }

        with pytest.raises(AttributeError, match="Story object missing required attribute"):
            prompts.populate_template(prompt_record, incomplete_story, "text")

    def test_populate_template_line_folding(self, temp_data_folder):
        """Test that template population includes proper line folding."""
        prompts = Prompts(temp_data_folder)

        mock_story = Mock()
        mock_story.title = "Test Story"
        mock_story.book = "Genesis"
        mock_story.verses = ["1:1-1:3"]

        prompt_record = {
            "id": "1",
            "category": "Babylonian",
            "topic": "Geopolitical Danger",
            "prompt": "There is an upcoming significant man-made, natural or supernatural destruction by Yahweh that affects the general public and causes great devastation across the land",
        }

        # Long text that should trigger line folding
        long_text = "This is a very long biblical text that exceeds the normal line length and should be properly wrapped to ensure readability and proper formatting when displayed or printed in various contexts and applications."

        result = prompts.populate_template(prompt_record, mock_story, long_text)

        # Check that all lines are within the 100 character limit
        lines = result.split("\n")
        for line in lines:
            assert len(line) <= 100, f"Line too long ({len(line)} chars): {line}"

    def test_repr(self, temp_data_folder):
        """Test Prompts __repr__ method."""
        prompts = Prompts(temp_data_folder)

        repr_str = repr(prompts)
        assert "Prompts(" in repr_str
        assert f"data_folder='{temp_data_folder}'" in repr_str
        assert "prompt_count=4" in repr_str


class TestPromptsIntegration:
    """Integration tests using real data."""

    def test_with_real_data(self):
        """Test Prompts class with real repository data."""
        # This test will only run if we're in the actual repository with data
        try:
            prompts = Prompts("data")

            # Test basic functionality
            count = prompts.get_prompt_count()
            assert count > 0

            categories = prompts.get_categories()
            assert len(categories) > 0
            assert all(isinstance(p, str) for p in categories)

            topics = prompts.get_topics()
            assert len(topics) > 0
            assert all(isinstance(t, str) for t in topics)

            # Test getting prompts
            all_prompts = prompts.get_prompts()
            assert len(all_prompts) == count

            if all_prompts:
                first_prompt = all_prompts[0]
                assert "id" in first_prompt
                assert "category" in first_prompt
                assert "topic" in first_prompt
                assert "prompt" in first_prompt

            # Test template content
            template = prompts.get_template_content()
            assert isinstance(template, str)
            assert len(template) > 0

        except FileNotFoundError:
            # Skip if running without real data
            pytest.skip("Real data not available for integration test")

    def test_prompts_stories_bible_integration(self):
        """Test that Prompts class works with Stories and Bible classes."""
        try:
            from prophecy.bible import Bible
            from prophecy.stories import Stories

            prompts = Prompts("data")
            stories = Stories("data")
            bible = Bible("data")

            # Get test data
            all_prompts = prompts.get_prompts()
            if not all_prompts:
                pytest.skip("No prompts available")

            story_titles = stories.titles
            if not story_titles:
                pytest.skip("No stories available")

            # Test integration
            prompt = all_prompts[0]
            story = stories.get_story(story_titles[0])

            # Get some biblical text (truncated for testing)
            bible_parts = story.to_bible_parts()
            text = bible.get_text(story.book, *bible_parts)
            text = text[:500]  # Truncate for testing

            # Test template population
            result = prompts.populate_template(prompt, story, text)

            # Should return properly formatted text
            assert isinstance(result, str)
            assert len(result) > 0

            # Should contain the key elements
            # XXX the category and topic are not needed in the result, they're for downstream analysis
            # assert prompt['category'] in result
            # assert prompt['topic'] in result
            # Check for the prompt text, accounting for potential line folding
            assert prompt["prompt"] in result.replace("\n", " ")
            # Check for the text, accounting for potential line folding
            assert " ".join(text.split()) in " ".join(result.split())

            # Should have proper line folding
            lines = result.split("\n")
            for line in lines:
                assert len(line) <= 100

        except FileNotFoundError:
            pytest.skip("Real data not available for integration test")
        except ImportError:
            pytest.skip("Required classes not available")

    def test_real_data_structure_validation(self):
        """Test that real prompts.tsv has expected structure."""
        try:
            prompts = Prompts("data")

            # All prompts should have valid structure
            all_prompts = prompts.get_prompts()
            assert len(all_prompts) > 0

            for prompt in all_prompts:
                # Should have required keys
                assert "id" in prompt
                assert "category" in prompt
                assert "topic" in prompt
                assert "prompt" in prompt

                # Values should be non-empty strings
                assert isinstance(prompt["id"], str)
                assert len(prompt["id"].strip()) > 0
                assert isinstance(prompt["category"], str)
                assert len(prompt["category"].strip()) > 0
                assert isinstance(prompt["topic"], str)
                assert len(prompt["topic"].strip()) > 0
                assert isinstance(prompt["prompt"], str)
                assert len(prompt["prompt"].strip()) > 0

            # IDs should be unique
            ids = [p["id"] for p in all_prompts]
            assert len(ids) == len(set(ids)), "Duplicate IDs found"

            # Should have reasonable data
            categories = prompts.get_categories()
            assert len(categories) >= 1

            topics = prompts.get_topics()
            assert len(topics) >= 1

        except FileNotFoundError:
            pytest.skip("Real data not available for validation test")


class TestWeightColumn:
    """Tests for the optional ``weight`` column.

    Weight semantics:
      * Missing column or blank cell → no explicit weight (``None`` on the row).
      * Topic with zero explicit weights → uniform 1.0 for every prompt.
      * Topic with any explicit weight → blanks resolve to 0.0 (don't
        contribute), and a load-time warning lists the affected prompts.
    """

    @staticmethod
    def _write(prompts_dir: Path, name: str, content: str) -> None:
        with open(prompts_dir / name, "w", encoding="utf-8") as f:
            f.write(content)
        if not (prompts_dir / "template.txt").exists():
            with open(prompts_dir / "template.txt", "w", encoding="utf-8") as f:
                f.write("$prompt\n$text\n")

    @pytest.fixture
    def make_tsv(self, tmp_path):
        """Factory: scaffold a data folder whose prompts.tsv has caller-supplied rows."""

        def _make(rows_tsv: str, with_weight_col: bool = True) -> Path:
            data = tmp_path / "data"
            prompts_dir = data / "prompts"
            prompts_dir.mkdir(parents=True)
            header = (
                "id\tcategory\ttopic\tprompt\tweight\n"
                if with_weight_col
                else "id\tcategory\ttopic\tprompt\n"
            )
            self._write(prompts_dir, "prompts.tsv", header + rows_tsv)
            return data

        return _make

    def test_missing_weight_column_loads_as_none(self, make_tsv):
        """Legacy 4-column TSVs (no weight column at all) load fine; weights default to None."""
        data = make_tsv(
            "1\tCat\tTopicA\tA prompt\n2\tCat\tTopicA\tAnother\n",
            with_weight_col=False,
        )
        prompts = Prompts(str(data))
        weights = [p.get("weight") for p in prompts.get_prompts()]
        assert weights == [None, None]
        # Effective weights fall back to uniform 1.0 (fully-unweighted topic).
        eff = prompts.get_effective_weights()
        assert eff == {"1": 1.0, "2": 1.0}

    def test_explicit_weights_parse_as_ints(self, make_tsv):
        data = make_tsv(
            "1\tCat\tTopicA\tA prompt\t3\n2\tCat\tTopicA\tAnother\t5\n3\tCat\tTopicA\tThird\t1\n"
        )
        prompts = Prompts(str(data))
        rows = {p["id"]: p for p in prompts.get_prompts()}
        assert rows["1"]["weight"] == 3
        assert rows["2"]["weight"] == 5
        assert rows["3"]["weight"] == 1
        eff = prompts.get_effective_weights()
        assert eff == {"1": 3.0, "2": 5.0, "3": 1.0}

    def test_partial_weight_topic_zeroes_blanks_and_warns(self, make_tsv, caplog):
        """Mixing weighted + unweighted prompts in one topic: blanks → 0,
        and the loader warns so the silent-drop is visible."""
        data = make_tsv(
            "1\tCat\tT\tWeighted A\t3\n"
            "2\tCat\tT\tBlank B\t\n"
            "3\tCat\tT\tWeighted C\t2\n"
            "4\tCat\tT\tBlank D\t\n"
        )
        with caplog.at_level("WARNING", logger="prophecy.prompts"):
            prompts = Prompts(str(data))
        eff = prompts.get_effective_weights()
        assert eff == {"1": 3.0, "2": 0.0, "3": 2.0, "4": 0.0}
        # One warning per partial-weight topic; lists every zero-weighted id.
        assert any("'Cat'/'T'" in rec.message for rec in caplog.records)
        warn_text = "\n".join(rec.message for rec in caplog.records)
        assert "Blank B" in warn_text and "Blank D" in warn_text
        # Fully-weighted prompts are not listed as "missing" in the warning.
        assert "Weighted A" not in warn_text and "Weighted C" not in warn_text

    def test_fully_unweighted_topic_does_not_warn(self, make_tsv, caplog):
        data = make_tsv("1\tCat\tT\tA\t\n2\tCat\tT\tB\t\n")
        with caplog.at_level("WARNING", logger="prophecy.prompts"):
            Prompts(str(data))
        assert not any("weights but" in rec.message for rec in caplog.records)

    def test_fully_weighted_topic_does_not_warn(self, make_tsv, caplog):
        data = make_tsv("1\tCat\tT\tA\t1\n2\tCat\tT\tB\t2\n")
        with caplog.at_level("WARNING", logger="prophecy.prompts"):
            Prompts(str(data))
        assert not any("weights but" in rec.message for rec in caplog.records)

    def test_invalid_weight_raises(self, make_tsv):
        data = make_tsv("1\tCat\tT\tA\tnot-a-number\n")
        with pytest.raises(ValueError, match="Invalid weight"):
            Prompts(str(data))

    def test_negative_weight_raises(self, make_tsv):
        data = make_tsv("1\tCat\tT\tA\t-1\n")
        with pytest.raises(ValueError, match="Negative weight"):
            Prompts(str(data))

    def test_weight_zero_is_legal_and_means_no_contribution(self, make_tsv):
        """``weight=0`` is explicit "ignore me" — distinct from a blank cell only in
        that it doesn't trigger the partial-weight warning."""
        data = make_tsv("1\tCat\tT\tA\t0\n2\tCat\tT\tB\t5\n")
        prompts = Prompts(str(data))
        eff = prompts.get_effective_weights()
        assert eff == {"1": 0.0, "2": 5.0}

    def test_per_topic_policy_is_independent(self, make_tsv):
        """One topic being weighted shouldn't force another topic into weighted mode."""
        data = make_tsv(
            "1\tCat\tWeighted\tA\t3\n"
            "2\tCat\tWeighted\tB\t1\n"
            "3\tCat\tUnweighted\tC\t\n"
            "4\tCat\tUnweighted\tD\t\n"
        )
        prompts = Prompts(str(data))
        eff = prompts.get_effective_weights()
        # "Weighted" topic uses its explicit values; "Unweighted" gets uniform 1.0.
        assert eff == {"1": 3.0, "2": 1.0, "3": 1.0, "4": 1.0}


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
