#!/usr/bin/env python3
"""
Unit tests for the Bible class.

This module tests the Bible class functionality including initialization,
text extraction, and proper formatting.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from prophecy.bible import Bible


class TestBible:
    """Test class for the Bible functionality."""

    @pytest.fixture
    def temp_data_folder(self):
        """Create a temporary data folder with test data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir()
            bible_dir = data_dir / "bible-kjv"
            bible_dir.mkdir()

            # Create test index.json
            index_data = {
                "Genesis": "data/bible-kjv/Genesis.json",
                "Matthew": "data/bible-kjv/Matthew.json",
            }
            with open(data_dir / "index.json", "w") as f:
                json.dump(index_data, f)

            # Create test Genesis.json
            genesis_data = {
                "book": "Genesis",
                "chapters": [
                    {
                        "chapter": "1",
                        "verses": [
                            {
                                "verse": "1",
                                "text": "In the beginning God created the heaven and the earth.",
                            },
                            {
                                "verse": "2",
                                "text": "And the earth was without form, and void; and darkness was upon the face of the deep.",
                            },
                            {
                                "verse": "3",
                                "text": "And God said, Let there be light: and there was light.",
                            },
                        ],
                    },
                    {
                        "chapter": "2",
                        "verses": [
                            {
                                "verse": "1",
                                "text": "Thus the heavens and the earth were finished, and all the host of them.",
                            },
                            {
                                "verse": "2",
                                "text": "And on the seventh day God ended his work which he had made.",
                            },
                        ],
                    },
                ],
            }
            with open(bible_dir / "Genesis.json", "w") as f:
                json.dump(genesis_data, f)

            # Create test Matthew.json
            matthew_data = {
                "book": "Matthew",
                "chapters": [
                    {
                        "chapter": "1",
                        "verses": [
                            {
                                "verse": "1",
                                "text": "The book of the generation of Jesus Christ, the son of David, the son of Abraham.",
                            },
                            {
                                "verse": "2",
                                "text": "Abraham begat Isaac; and Isaac begat Jacob; and Jacob begat Judas and his brethren.",
                            },
                        ],
                    }
                ],
            }
            with open(bible_dir / "Matthew.json", "w") as f:
                json.dump(matthew_data, f)

            yield str(data_dir)

    def test_init_with_data_folder(self, temp_data_folder):
        """Test Bible initialization with explicit data folder."""
        bible = Bible(temp_data_folder)
        assert bible.data_folder == Path(temp_data_folder)
        assert len(bible.index) == 2
        assert "Genesis" in bible.index
        assert "Matthew" in bible.index

    def test_init_with_env_var(self, temp_data_folder):
        """Test Bible initialization with environment variable."""
        with patch.dict(os.environ, {"PROPHECY_DATA_FOLDER": temp_data_folder}):
            bible = Bible()
            assert bible.data_folder == Path(temp_data_folder)

    def test_init_with_default_data_folder(self):
        """Test Bible initialization with default data folder."""
        with patch.dict(os.environ, {}, clear=True):
            # Should default to 'data' - test depends on whether data folder exists
            try:
                bible = Bible()
                # If this succeeds, data folder exists and has valid index
                assert bible.data_folder == Path("data")
            except FileNotFoundError:
                # This is also acceptable if no data folder exists
                pass

    def test_init_nonexistent_folder(self):
        """Test Bible initialization with non-existent data folder."""
        with pytest.raises(FileNotFoundError, match="Data folder not found"):
            Bible("/nonexistent/path")

    def test_init_missing_index(self, temp_data_folder):
        """Test Bible initialization with missing index.json."""
        os.remove(Path(temp_data_folder) / "index.json")
        with pytest.raises(FileNotFoundError, match="Index file not found"):
            Bible(temp_data_folder)

    def test_get_available_books(self, temp_data_folder):
        """Test getting list of available books."""
        bible = Bible(temp_data_folder)
        books = bible.get_available_books()
        assert books == ["Genesis", "Matthew"]

    def test_get_book_info(self, temp_data_folder):
        """Test getting book information."""
        bible = Bible(temp_data_folder)
        info = bible.get_book_info("Genesis")
        assert info["title"] == "Genesis"
        assert info["chapter_count"] == 2
        assert info["file_path"] == "data/bible-kjv/Genesis.json"

    def test_get_book_info_invalid_book(self, temp_data_folder):
        """Test getting info for invalid book."""
        bible = Bible(temp_data_folder)
        with pytest.raises(ValueError, match="Book 'InvalidBook' not found"):
            bible.get_book_info("InvalidBook")

    def test_parse_verse_range_valid(self, temp_data_folder):
        """Test parsing valid verse ranges."""
        bible = Bible(temp_data_folder)

        # Test normal range
        start, end = bible._parse_verse_range("1:1-1:3")
        assert start == (1, 1)
        assert end == (1, 3)

        # Test cross-chapter range
        start, end = bible._parse_verse_range("1:2-2:1")
        assert start == (1, 2)
        assert end == (2, 1)

    def test_parse_verse_range_invalid(self, temp_data_folder):
        """Test parsing invalid verse ranges."""
        bible = Bible(temp_data_folder)

        invalid_ranges = [
            "1:1",  # Missing end
            "1:1-2",  # Missing verse in end
            "invalid",  # Completely invalid
            "1:1-2:",  # Missing end verse
            "",  # Empty string
            "1:1 - 2:2",  # Spaces in wrong places
        ]

        for invalid_range in invalid_ranges:
            with pytest.raises(ValueError, match="Invalid verse range format"):
                bible._parse_verse_range(invalid_range)

    def test_get_text_single_verse(self, temp_data_folder):
        """Test extracting text for a single verse."""
        bible = Bible(temp_data_folder)
        text = bible.get_text("Genesis", {"range": "1:1-1:1"})
        assert text == "In the beginning God created the heaven and the earth."

    def test_get_text_multiple_verses_same_chapter(self, temp_data_folder):
        """Test extracting text for multiple verses in the same chapter."""
        bible = Bible(temp_data_folder)
        text = bible.get_text("Genesis", {"range": "1:1-1:2"})
        expected = (
            "In the beginning God created the heaven and the earth. "
            "And the earth was without form, and void; and darkness was upon the face of the deep."
        )
        assert text == expected

    def test_get_text_cross_chapter(self, temp_data_folder):
        """Test extracting text across chapters."""
        bible = Bible(temp_data_folder)
        text = bible.get_text("Genesis", {"range": "1:3-2:1"})
        expected = (
            "And God said, Let there be light: and there was light. "
            "Thus the heavens and the earth were finished, and all the host of them."
        )
        assert text == expected

    def test_get_text_dict_format(self, temp_data_folder):
        """Test extracting text using dictionary format."""
        bible = Bible(temp_data_folder)
        text = bible.get_text(
            "Genesis", {"start_chapter": 1, "start_verse": 1, "end_chapter": 1, "end_verse": 2}
        )
        expected = (
            "In the beginning God created the heaven and the earth. "
            "And the earth was without form, and void; and darkness was upon the face of the deep."
        )
        assert text == expected

    def test_get_text_multiple_parts(self, temp_data_folder):
        """Test extracting text from multiple parts."""
        bible = Bible(temp_data_folder)
        text = bible.get_text("Genesis", {"range": "1:1-1:1"}, {"range": "2:1-2:1"})
        expected = (
            "In the beginning God created the heaven and the earth. "
            "Thus the heavens and the earth were finished, and all the host of them."
        )
        assert text == expected

    def test_get_text_invalid_book(self, temp_data_folder):
        """Test extracting text from invalid book."""
        bible = Bible(temp_data_folder)
        with pytest.raises(ValueError, match="Book 'InvalidBook' not found"):
            bible.get_text("InvalidBook", {"range": "1:1-1:1"})

    def test_get_text_invalid_range_order(self, temp_data_folder):
        """Test extracting text with invalid range order."""
        bible = Bible(temp_data_folder)
        with pytest.raises(ValueError, match="Invalid range"):
            bible.get_text("Genesis", {"range": "2:1-1:1"})

    def test_get_text_no_parts(self, temp_data_folder):
        """Test extracting text with no parts specified."""
        bible = Bible(temp_data_folder)
        with pytest.raises(ValueError, match="At least one part must be specified"):
            bible.get_text("Genesis")

    def test_get_text_invalid_part_format(self, temp_data_folder):
        """Test extracting text with invalid part format."""
        bible = Bible(temp_data_folder)

        # Test non-dict part
        with pytest.raises(ValueError, match="Each part must be a dictionary"):
            bible.get_text("Genesis", "invalid")  # pyright: ignore[reportArgumentType]

        # Test missing keys
        with pytest.raises(ValueError, match="Each part must contain either"):
            bible.get_text("Genesis", {"start_chapter": 1})

    def test_get_text_nonexistent_verses(self, temp_data_folder):
        """Test extracting text from non-existent verses."""
        bible = Bible(temp_data_folder)
        with pytest.raises(ValueError, match="No verses found in range"):
            bible.get_text("Genesis", {"range": "10:1-10:2"})

    def test_ensure_proper_spacing(self, temp_data_folder):
        """Test proper spacing functionality."""
        bible = Bible(temp_data_folder)

        # Test period spacing
        text = "First sentence.Second sentence."
        corrected = bible._ensure_proper_spacing(text)
        assert corrected == "First sentence. Second sentence."

        # Test multiple spaces
        text = "First   sentence.  Second sentence."
        corrected = bible._ensure_proper_spacing(text)
        assert corrected == "First sentence. Second sentence."

        # Test already correct spacing
        text = "First sentence. Second sentence."
        corrected = bible._ensure_proper_spacing(text)
        assert corrected == "First sentence. Second sentence."

    def test_book_caching(self, temp_data_folder):
        """Test that books are cached after first load."""
        bible = Bible(temp_data_folder)

        # First load
        text1 = bible.get_text("Genesis", {"range": "1:1-1:1"})
        assert "Genesis" in bible._book_cache

        # Second load should use cache
        text2 = bible.get_text("Genesis", {"range": "1:1-1:1"})
        assert text1 == text2

    def test_load_book_missing_file(self, temp_data_folder):
        """Test loading a book with missing file."""
        bible = Bible(temp_data_folder)

        # Add entry to index but remove the file
        bible.index["MissingBook"] = "data/bible-kjv/MissingBook.json"

        with pytest.raises(FileNotFoundError, match="Book file not found"):
            bible._load_book("MissingBook")

    def test_extract_text_from_range_edge_cases(self, temp_data_folder):
        """Test edge cases in text extraction."""
        bible = Bible(temp_data_folder)
        book_data = bible._load_book("Genesis")

        # Test same verse range
        text = bible._extract_text_from_range(book_data, (1, 1), (1, 1))
        assert text == "In the beginning God created the heaven and the earth."

        # Test last verse in chapter
        text = bible._extract_text_from_range(book_data, (1, 3), (1, 3))
        assert text == "And God said, Let there be light: and there was light."


class TestBibleIntegration:
    """Integration tests using real data."""

    def test_with_real_data(self):
        """Test Bible class with real repository data."""
        # This test will only run if we're in the actual repository with data
        try:
            bible = Bible("data")

            # Test basic functionality
            books = bible.get_available_books()
            assert "Genesis" in books

            # Test getting actual text
            text = bible.get_text("Genesis", {"range": "1:1-1:3"})
            assert "בְּרֵאשִׁ֖ית" in text
            assert "בָּרָ֣א אֱלֹהִ֑ים" in text

            # Test book info
            info = bible.get_book_info("Genesis")
            assert info["title"] == "Genesis"
            assert info["chapter_count"] > 0

        except FileNotFoundError:
            # Skip if running without real data
            pytest.skip("Real data not available for integration test")

    def test_story_like_usage(self):
        """Test usage pattern similar to stories.yml."""
        try:
            bible = Bible("data")

            # Test creation story (Genesis 1:1-2:7)
            creation_text = bible.get_text("Genesis", {"range": "1:1-2:7"})
            assert "בְּרֵאשִׁ֖ית" in creation_text
            assert len(creation_text) > 100  # Should be substantial text

            # Test multiple parts (like complex stories)
            if "Matthew" in bible.get_available_books():
                text = bible.get_text("Matthew", {"range": "1:1-1:5"}, {"range": "1:18-1:20"})
                assert len(text.split(" ")) > 20  # Should be multiple sentences

        except FileNotFoundError:
            pytest.skip("Real data not available for integration test")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
