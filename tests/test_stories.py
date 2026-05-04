#!/usr/bin/env python3
"""
Unit tests for the Stories class.

This module tests the Stories class functionality including initialization,
story access, and integration with the Bible class.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from prophecy.stories import Stories, Story


class TestStories:
    """Test class for the Stories functionality."""

    @pytest.fixture
    def temp_data_folder(self):
        """Create a temporary data folder with test stories.yml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir()

            # Create test stories.yml
            stories_data = {
                "The Creation": {"book": "Genesis", "verses": ["1:1-2:7"]},
                "Adam and Eve": {"book": "Genesis", "verses": ["2:8-3:24"]},
                "Complex Story": {"book": "Genesis", "verses": ["1:1-1:3", "2:1-2:3"]},
            }

            with open(data_dir / "stories.yml", "w") as f:
                yaml.dump(stories_data, f, default_flow_style=False)

            yield str(data_dir)

    def test_init_with_data_folder(self, temp_data_folder):
        """Test Stories initialization with explicit data folder."""
        stories = Stories(temp_data_folder)
        assert stories.data_folder == Path(temp_data_folder)
        assert len(stories.titles) == 3
        assert "The Creation" in stories.titles
        assert "Adam and Eve" in stories.titles
        assert "Complex Story" in stories.titles

    def test_init_with_env_var(self, temp_data_folder):
        """Test Stories initialization with environment variable."""
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": temp_data_folder}):
            stories = Stories()
            assert stories.data_folder == Path(temp_data_folder)

    def test_init_with_default_data_folder(self):
        """Test Stories initialization with default data folder."""
        with patch.dict(os.environ, {}, clear=True):
            # Should default to 'data' - test depends on whether data folder exists
            try:
                stories = Stories()
                # If this succeeds, data folder exists and has valid stories.yml
                assert stories.data_folder == Path("data")
                assert isinstance(stories.titles, list)
            except FileNotFoundError:
                # This is also acceptable if no data folder exists
                pass

    def test_init_nonexistent_folder(self):
        """Test Stories initialization with non-existent data folder."""
        with pytest.raises(FileNotFoundError, match="Data folder not found"):
            Stories("/nonexistent/path")

    def test_init_missing_stories_file(self, temp_data_folder):
        """Test Stories initialization with missing stories.yml."""
        os.remove(Path(temp_data_folder) / "stories.yml")
        with pytest.raises(FileNotFoundError, match="Stories file not found"):
            Stories(temp_data_folder)

    def test_init_invalid_yaml_format(self, temp_data_folder):
        """Test Stories initialization with invalid YAML format."""
        stories_path = Path(temp_data_folder) / "stories.yml"

        # Write invalid YAML (list instead of dict at root)
        with open(stories_path, "w") as f:
            yaml.dump(["invalid", "format"], f)

        with pytest.raises(ValueError, match="Invalid stories.yml format"):
            Stories(temp_data_folder)

    def test_titles_property(self, temp_data_folder):
        """Test the titles property returns sorted list."""
        stories = Stories(temp_data_folder)
        titles = stories.titles
        assert isinstance(titles, list)
        assert len(titles) == 3
        assert titles == sorted(titles)  # Should be sorted
        assert "Adam and Eve" in titles
        assert "Complex Story" in titles
        assert "The Creation" in titles

    def test_get_story_valid(self, temp_data_folder):
        """Test getting a valid story."""
        stories = Stories(temp_data_folder)
        story = stories.get_story("The Creation")

        assert isinstance(story, Story)
        assert story.title == "The Creation"
        assert story.book == "Genesis"
        assert story.verses == ["1:1-2:7"]

    def test_get_story_invalid(self, temp_data_folder):
        """Test getting an invalid story."""
        stories = Stories(temp_data_folder)

        with pytest.raises(ValueError, match="Story 'Nonexistent' not found"):
            stories.get_story("Nonexistent")

    def test_get_story_complex_verses(self, temp_data_folder):
        """Test getting a story with multiple verse ranges."""
        stories = Stories(temp_data_folder)
        story = stories.get_story("Complex Story")

        assert story.title == "Complex Story"
        assert story.book == "Genesis"
        assert story.verses == ["1:1-1:3", "2:1-2:3"]


class TestStory:
    """Test class for the Story functionality."""

    def test_init_valid_story_data(self):
        """Test Story initialization with valid data."""
        story_data = {"book": "Genesis", "verses": ["1:1-2:7"]}
        story = Story("Test Story", story_data)

        assert story.title == "Test Story"
        assert story.book == "Genesis"
        assert story.verses == ["1:1-2:7"]

    def test_init_missing_book_field(self):
        """Test Story initialization with missing book field."""
        story_data = {"verses": ["1:1-2:7"]}
        with pytest.raises(ValueError, match="Story 'Test' missing 'book' field"):
            Story("Test", story_data)

    def test_init_missing_verses_field(self):
        """Test Story initialization with missing verses field."""
        story_data = {"book": "Genesis"}
        with pytest.raises(ValueError, match="Story 'Test' missing 'verses' field"):
            Story("Test", story_data)

    def test_init_non_dict_data(self):
        """Test Story initialization with non-dictionary data."""
        with pytest.raises(ValueError, match="Story data for 'Test' must be a dictionary"):
            Story("Test", "invalid")  # pyright: ignore[reportArgumentType]

    def test_init_non_list_verses(self):
        """Test Story initialization with non-list verses."""
        story_data = {
            "book": "Genesis",
            "verses": "1:1-2:7",  # Should be a list
        }
        with pytest.raises(ValueError, match="Story 'Test' verses field must be a list"):
            Story("Test", story_data)

    def test_properties(self):
        """Test Story properties."""
        story_data = {"book": "Genesis", "verses": ["1:1-2:7", "3:1-3:5"]}
        story = Story("Test Story", story_data)

        # Test properties
        assert story.title == "Test Story"
        assert story.book == "Genesis"
        assert story.verses == ["1:1-2:7", "3:1-3:5"]

        # Test that verses property returns a copy
        verses_copy = story.verses
        verses_copy.append("4:1-4:5")
        assert story.verses == ["1:1-2:7", "3:1-3:5"]  # Original unchanged

    def test_to_bible_parts_single_range(self):
        """Test converting story to Bible parts format with single range."""
        story_data = {"book": "Genesis", "verses": ["1:1-2:7"]}
        story = Story("Test Story", story_data)

        parts = story.to_bible_parts()
        expected = [{"range": "1:1-2:7"}]
        assert parts == expected

    def test_to_bible_parts_multiple_ranges(self):
        """Test converting story to Bible parts format with multiple ranges."""
        story_data = {"book": "Genesis", "verses": ["1:1-1:3", "2:1-2:3", "3:1-3:5"]}
        story = Story("Test Story", story_data)

        parts = story.to_bible_parts()
        expected = [{"range": "1:1-1:3"}, {"range": "2:1-2:3"}, {"range": "3:1-3:5"}]
        assert parts == expected

    def test_repr(self):
        """Test Story __repr__ method."""
        story_data = {"book": "Genesis", "verses": ["1:1-2:7", "3:1-3:5"]}
        story = Story("Test Story", story_data)

        repr_str = repr(story)
        assert "Story(" in repr_str
        assert "title='Test Story'" in repr_str
        assert "book='Genesis'" in repr_str
        assert "verse_count=2" in repr_str

    def test_str(self):
        """Test Story __str__ method."""
        story_data = {"book": "Genesis", "verses": ["1:1-2:7", "3:1-3:5"]}
        story = Story("Test Story", story_data)

        str_repr = str(story)
        assert str_repr == "Test Story (Genesis 1:1-2:7, 3:1-3:5)"


class TestStoriesIntegration:
    """Integration tests using real data."""

    def test_with_real_data(self):
        """Test Stories class with real repository data."""
        # This test will only run if we're in the actual repository with data
        try:
            stories = Stories("data")

            # Test basic functionality
            titles = stories.titles
            assert len(titles) > 0
            assert isinstance(titles[0], str)

            # Test getting a story (use first available)
            first_title = titles[0]
            story = stories.get_story(first_title)
            assert isinstance(story, Story)
            assert story.title == first_title
            assert isinstance(story.book, str)
            assert isinstance(story.verses, list)
            assert len(story.verses) > 0

            # Test Bible parts conversion
            bible_parts = story.to_bible_parts()
            assert isinstance(bible_parts, list)
            assert len(bible_parts) == len(story.verses)

            for part in bible_parts:
                assert isinstance(part, dict)
                assert "range" in part
                assert isinstance(part["range"], str)
                # Should match verse range format
                assert ":" in part["range"]
                assert "-" in part["range"]

        except FileNotFoundError:
            # Skip if running without real data
            pytest.skip("Real data not available for integration test")

    def test_stories_bible_compatibility(self):
        """Test that Stories class works with Bible class."""
        try:
            from prophecy.bible import Bible

            stories = Stories("data")
            bible = Bible("data")

            # Get a story
            titles = stories.titles
            if not titles:
                pytest.skip("No stories available")

            story = stories.get_story(titles[0])

            # Try to get text using Bible
            bible_parts = story.to_bible_parts()
            text = bible.get_text(story.book, *bible_parts)

            # Should return some text
            assert isinstance(text, str)
            assert len(text) > 0

        except FileNotFoundError:
            pytest.skip("Real data not available for integration test")
        except ImportError:
            pytest.skip("Bible class not available")


class TestStoriesYmlValidation:
    """Additional validation tests for stories.yml structure."""

    def test_real_stories_yml_structure(self):
        """Test that real stories.yml has expected structure."""
        try:
            stories = Stories("data")

            # All stories should have valid structure
            for title in stories.titles:
                story = stories.get_story(title)

                # Should have valid properties
                assert isinstance(story.title, str)
                assert len(story.title) > 0
                assert isinstance(story.book, str)
                assert len(story.book) > 0
                assert isinstance(story.verses, list)
                assert len(story.verses) > 0

                # All verses should be strings with valid format
                for verse_range in story.verses:
                    assert isinstance(verse_range, str)
                    assert ":" in verse_range
                    assert "-" in verse_range
                    # Should match pattern chapter:verse-chapter:verse
                    parts = verse_range.split("-")
                    assert len(parts) == 2
                    for part in parts:
                        assert ":" in part
                        chapter, verse = part.split(":")
                        assert chapter.isdigit()
                        assert verse.isdigit()

        except FileNotFoundError:
            pytest.skip("Real data not available for validation test")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
