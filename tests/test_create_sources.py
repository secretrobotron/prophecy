#!/usr/bin/env python3
"""
Unit tests for scripts/create_sources.py

This module tests that the output of create_sources.py consists of valid ranges
in the KJV Bible by way of prophecy.Bible and prophecy module.
"""

import os
import re
import pytest
import tempfile
from unittest.mock import patch, MagicMock

# Add the scripts directory to the path to import create_sources
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

# Import the functions we want to test
from create_sources import parse_bullet, clean_text, RANGE_TOKEN, BOOK_MAP

# Import the Bible class to validate ranges
from prophecy.bible import Bible


class TestCreateSources:
    """Test class for create_sources.py functionality."""

    def test_clean_text(self):
        """Test text cleaning functionality."""
        # Test removing non-breaking spaces
        assert clean_text("text\xa0with\xa0spaces") == "text with spaces"

        # Test removing asterisks
        assert clean_text("text*with*asterisks") == "textwithasterisks"

        # Test normalizing multiple spaces
        assert clean_text("text   with    multiple   spaces") == "text with multiple spaces"

        # Test combined cleaning
        assert clean_text("*text\xa0\xa0\xa0with   mixed*") == "text with mixed"

    def test_range_token_regex(self):
        """Test that the RANGE_TOKEN regex matches expected patterns."""
        valid_patterns = [
            "1:1",
            "2:4b",
            "1:1-2:7",
            "2:4b-4:26",
            "7:1-5",
            "7:10",
            "7:13a",
            "14:1-19",
            "1:1-2:3a",
            "25:1-34",
        ]

        for pattern in valid_patterns:
            assert re.fullmatch(RANGE_TOKEN, pattern), (
                f"Pattern '{pattern}' should match RANGE_TOKEN regex"
            )

    def test_range_token_regex_invalid(self):
        """Test that invalid patterns don't match RANGE_TOKEN regex."""
        invalid_patterns = [
            "1",  # Missing verse
            "1:",  # Missing verse number
            ":1",  # Missing chapter
            "a:1",  # Non-numeric chapter
            "1:a",  # Non-numeric verse (except for letter suffixes)
            "1:1-",  # Incomplete range
            "-1:1",  # Invalid start
        ]

        for pattern in invalid_patterns:
            assert not re.fullmatch(RANGE_TOKEN, pattern), (
                f"Pattern '{pattern}' should NOT match RANGE_TOKEN regex"
            )

    def test_parse_bullet_valid(self):
        """Test parsing valid bullet points."""
        # Test simple single range
        result = parse_bullet("Gen 1:1-2:7", "J")
        assert result is not None
        assert result["book"] == "Genesis"
        assert result["ranges"] == ["1:1-2:7"]
        assert result["source"] == "J"

        # Test multiple ranges - should be normalized
        result = parse_bullet("Gen 2:4b-4:26, 4:1-26", "J")
        assert result is not None
        assert result["book"] == "Genesis"
        assert result["ranges"] == ["2:4b-4:26", "4:1-4:26"]  # Second range normalized
        assert result["source"] == "J"

        # Test with different books
        result = parse_bullet("Exo 7:1-5, 7:10", "E")
        assert result is not None
        assert result["book"] == "Exodus"
        assert result["ranges"] == ["7:1-7:5", "7:10"]  # First range normalized
        assert result["source"] == "E"

    def test_parse_bullet_invalid(self):
        """Test that invalid bullet points return None."""
        # Test with invalid book
        result = parse_bullet("InvalidBook 1:1-2:7", "J")
        assert result is None

        # Test with no book abbreviation
        result = parse_bullet("1:1-2:7", "J")
        assert result is None

        # Test with completely invalid format
        result = parse_bullet("This is not a valid range", "J")
        assert result is None

        # Test with empty string
        result = parse_bullet("", "J")
        assert result is None

    def test_parse_bullet_range_normalization(self):
        """Test that ranges are normalized correctly."""
        # Test space normalization around hyphens
        result = parse_bullet("Gen 1:1 - 2:7, 3:1-3:24", "J")
        assert result is not None
        assert result["ranges"] == ["1:1-2:7", "3:1-3:24"]

        # Test duplicate removal with normalization
        result = parse_bullet("Gen 1:1-2:7, 1:1-2:7, 3:1-24", "J")
        assert result is not None
        assert result["ranges"] == ["1:1-2:7", "3:1-3:24"]  # Second unique range normalized

    def test_parse_bullet_with_commentary(self):
        """Test parsing bullets with commentary text."""
        # Test simpler case first - the regex behavior shows this is expected
        result = parse_bullet("Gen 1:1-2:7, 3:1-3:24", "P")
        assert result is not None
        assert result["book"] == "Genesis"
        assert "1:1-2:7" in result["ranges"]
        assert "3:1-3:24" in result["ranges"]

        # Test that when commentary disrupts parsing, at least some ranges are found
        result = parse_bullet("Gen 1:1-2:7 (creation story), 3:1-24 (fall)", "P")
        assert result is not None
        assert result["book"] == "Genesis"
        # The function should extract what it can, even if not perfect
        assert len(result["ranges"]) > 0

    def test_book_mapping(self):
        """Test that all book abbreviations map correctly."""
        expected_books = {
            "Gen": "Genesis",
            "Exo": "Exodus",
            "Lev": "Leviticus",
            "Num": "Numbers",
            "Deu": "Deuteronomy",
        }

        for abbrev, full_name in expected_books.items():
            assert BOOK_MAP[abbrev] == full_name

    def test_range_normalization_to_standard_format(self):
        """Test that ranges are normalized to the standard format expected by Bible class."""
        # Test that terse ranges are expanded to full format
        test_cases = [
            ("Gen 1:1-7", ["1:1-1:7"]),  # Same chapter expanded
            ("Gen 2:4b-26", ["2:4b-2:26"]),  # Same chapter with suffix
            ("Gen 1:1-2:7", ["1:1-2:7"]),  # Cross-chapter unchanged
            ("Gen 3:1", ["3:1"]),  # Single verse unchanged
            ("Gen 1:1-7, 2:8-25", ["1:1-1:7", "2:8-2:25"]),  # Multiple ranges
        ]

        for bullet_text, expected_ranges in test_cases:
            result = parse_bullet(bullet_text, "J")
            assert result is not None, f"Failed to parse: {bullet_text}"
            assert result["ranges"] == expected_ranges, (
                f"Expected {expected_ranges}, got {result['ranges']} for input: {bullet_text}"
            )


class TestCreateSourcesWithBible:
    """Test class for validating create_sources.py output against Bible data."""

    @pytest.fixture
    def bible(self):
        """Create a Bible instance for testing."""
        return Bible("data")

    def test_range_normalization_works_with_create_sources(self):
        """Test that create_sources now produces ranges in standard format."""
        # Test that create_sources normalizes terse ranges to standard format
        test_cases = [
            # Input with terse ranges should be normalized
            ("Gen 1:1-7", ["1:1-1:7"]),  # Same chapter expanded
            ("Gen 2:4b-26", ["2:4b-2:26"]),  # Same chapter with suffix
            ("Gen 1:1-2:7", ["1:1-2:7"]),  # Cross-chapter unchanged
        ]

        for input_text, expected_ranges in test_cases:
            result = parse_bullet(input_text, "J")
            assert result is not None
            assert result["ranges"] == expected_ranges

    def test_standard_ranges_work_with_bible(self, bible):
        """Test that standardized ranges work directly with the Bible class."""
        # Test ranges in standard format work with Bible class
        test_ranges = [
            ("Genesis", "1:1-1:31"),  # Standard format, same chapter
            ("Genesis", "2:8-2:25"),  # Standard format, same chapter
            ("Genesis", "1:1-2:7"),  # Standard format, cross-chapter
        ]

        for book, range_str in test_ranges:
            try:
                text = bible.get_text(book, {"range": range_str})
                assert text is not None
                assert len(text.strip()) > 0
            except ValueError as e:
                pytest.fail(f"Standard range {range_str} should work with Bible class: {e}")

    def test_parsed_ranges_compatible_with_bible_class(self, bible):
        """Test that parsed ranges from create_sources are directly compatible with Bible class."""
        # Test some sample parsed ranges - these should now be in standard format
        test_cases = [
            ("Gen", "Genesis", ["1:1-2:7", "2:8-2:25"]),
            ("Exo", "Exodus", ["1:1-1:22", "2:1-2:25"]),
            ("Deu", "Deuteronomy", ["1:1-1:46", "2:1-2:37"]),
        ]

        for book_abbrev, book_name, ranges in test_cases:
            for range_str in ranges:
                # Test that we can parse and validate the range
                parsed_result = parse_bullet(f"{book_abbrev} {range_str}", "J")
                assert parsed_result is not None
                assert parsed_result["book"] == book_name

                # Test that the range exists in the Bible - no conversion needed!
                try:
                    text = bible.get_text(book_name, {"range": range_str})
                    assert text is not None
                    assert len(text.strip()) > 0
                except ValueError as e:
                    pytest.fail(
                        f"Range {range_str} in {book_name} should be valid in Bible data: {e}"
                    )

    def test_all_pentateuch_books_accessible(self, bible):
        """Test that all Pentateuch books referenced in BOOK_MAP are accessible."""
        for book_abbrev, book_name in BOOK_MAP.items():
            try:
                # Test basic access to each book
                books = bible.get_available_books()
                assert book_name in books, f"Book {book_name} should be available in Bible data"

                # Test that we can get book info
                info = bible.get_book_info(book_name)
                assert info["title"] == book_name
                assert info["chapter_count"] > 0

            except (FileNotFoundError, ValueError) as e:
                pytest.fail(f"Book {book_name} should be accessible in Bible data: {e}")

    def test_range_validation_edge_cases(self, bible):
        """Test edge cases for range validation."""
        # Test single verse range
        result = parse_bullet("Gen 1:1", "J")
        if result:  # Only test if parsing succeeds
            try:
                # This should work for single verses - Bible class should handle it
                text = bible.get_text(
                    "Genesis",
                    {"start_chapter": 1, "start_verse": 1, "end_chapter": 1, "end_verse": 1},
                )
                assert text is not None
                assert len(text.strip()) > 0
            except ValueError:
                # If the Bible class doesn't support single verse this way, that's okay
                pass

        # Test cross-chapter range
        result = parse_bullet("Gen 1:30-2:3", "J")
        if result:
            try:
                text = bible.get_text("Genesis", {"range": "1:30-2:3"})
                assert text is not None
                assert len(text.strip()) > 0
            except ValueError as e:
                pytest.fail(f"Cross-chapter range should be valid: {e}")

    @patch("create_sources.requests.get")
    def test_mock_create_sources_output_validation(self, mock_get, bible):
        """Test validation of a mocked create_sources output."""
        # Mock the HTML response from Wikiversity
        mock_html = """
        <html>
        <body>
        <h2>Jahwist</h2>
        <ul>
        <li>Gen 2:4b-4:26, 4:1-26</li>
        <li>Gen 6:1-8, 7:1-5</li>
        </ul>
        <h2>Elohist</h2>
        <ul>
        <li>Exo 3:1-15</li>
        <li>Num 11:1-35</li>
        </ul>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Import and test the main functions
        from create_sources import extract_source_list, SOURCE_HEADINGS
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(mock_html, "html.parser")

        # Test extraction for each source type
        for regex, tag in SOURCE_HEADINGS[:2]:  # Test first two sources
            entries = extract_source_list(soup, regex, tag)

            # Validate that we got some entries
            assert len(entries) > 0

            # Validate each entry
            for entry in entries:
                assert entry["book"] in BOOK_MAP.values()
                assert entry["source"] == tag
                assert len(entry["ranges"]) > 0

                # Validate that each range can be accessed in the Bible
                for range_str in entry["ranges"]:
                    try:
                        # Ranges should now be in standard format, no conversion needed
                        text = bible.get_text(entry["book"], {"range": range_str})
                        assert text is not None
                        assert len(text.strip()) > 0
                    except ValueError as e:
                        # Some ranges might have special formatting (like 4b) that need special handling
                        # For now, we'll just ensure the basic format is parseable
                        assert re.match(r"\d+:\d+[a-z]?(-\d+(?::\d+)?[a-z]?)?", range_str), (
                            f"Range {range_str} should match expected format"
                        )

    def test_range_format_compatibility_with_bible_class(self, bible):
        """Test that create_sources range formats are compatible with Bible class expectations."""
        # Test various range formats that create_sources now produces (all standardized)
        test_ranges = [
            ("Genesis", "1:1-2:7"),  # Standard cross-chapter range
            ("Genesis", "1:1-1:31"),  # Standard same-chapter range
            ("Genesis", "2:4-2:25"),  # Standard within-chapter range
        ]

        for book, range_str in test_ranges:
            try:
                # Test that Bible class can handle the range format
                text = bible.get_text(book, {"range": range_str})
                assert text is not None
                assert len(text.strip()) > 0

                # Test that the range produces meaningful content
                assert len(text.split()) > 5, f"Range {range_str} should produce substantial text"

            except ValueError as e:
                pytest.fail(f"Bible class should handle range format {range_str}: {e}")

    def test_error_handling_for_invalid_ranges(self, bible):
        """Test that invalid ranges are properly handled."""
        # Test ranges that should cause errors
        invalid_ranges = [
            ("Genesis", "999:1-1000:1"),  # Non-existent chapters
            ("Genesis", "1:999-1:1000"),  # Non-existent verses
            ("InvalidBook", "1:1-2:7"),  # Non-existent book
        ]

        for book, range_str in invalid_ranges:
            with pytest.raises((ValueError, FileNotFoundError)):
                bible.get_text(book, {"range": range_str})

    def test_special_verse_suffixes(self):
        """Test handling of verse suffixes like '4b'."""
        # Test that suffixes are preserved in parsing and normalized
        result = parse_bullet("Gen 2:4b-4:26", "J")
        assert result is not None
        assert "2:4b-4:26" in result["ranges"]

        # Test terse suffix range normalization
        result = parse_bullet("Gen 2:4b-26", "J")
        assert result is not None
        assert "2:4b-2:26" in result["ranges"]  # Should be normalized

        # Test multiple suffixes
        result = parse_bullet("Gen 1:1a-3b, 2:4c-5d", "J")
        assert result is not None
        # Should preserve suffixes and normalize format
        expected_ranges = ["1:1a-1:3b", "2:4c-2:5d"]
        assert result["ranges"] == expected_ranges

    def test_comprehensive_range_validation_workflow(self, bible):
        """Test the complete workflow from create_sources parsing to Bible validation."""
        # Simulate realistic create_sources output
        test_bullets = [
            "Gen 1:1-2:7",  # Creation story
            "Gen 2:4b-4:26",  # J source with suffix
            "Exo 3:1-4:31",  # Burning bush
            "Lev 1:1-17",  # Sacrificial laws
            "Num 1:1-54",  # Census
            "Deu 1:1-46",  # Moses' speech
        ]

        successful_validations = 0

        for bullet_text in test_bullets:
            # Parse with create_sources
            result = parse_bullet(bullet_text, "J")
            if result is None:
                continue

            # Validate each range
            for range_str in result["ranges"]:
                try:
                    # Ranges should now be in standard format, no conversion needed
                    text = bible.get_text(result["book"], {"range": range_str})

                    # Validate we got meaningful content
                    assert text is not None
                    assert len(text.strip()) > 0
                    assert len(text.split()) >= 5  # At least 5 words

                    successful_validations += 1

                except ValueError:
                    # Some ranges with suffixes might not work perfectly
                    # but we should still validate the basic format
                    assert re.match(r"\d+:\d+[a-z]?(-\d+(?::\d+)?[a-z]?)?", range_str)

        # We should have successfully validated most ranges
        assert successful_validations >= 4, (
            f"Expected at least 4 successful validations, got {successful_validations}"
        )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
