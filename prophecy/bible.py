"""
Bible text access class for the Prophecy project.

This module provides the Bible class for accessing biblical texts from the KJV data.
"""

import json
import re
from collections.abc import Mapping
from pathlib import Path

from .settings import Settings


class Bible:
    """
    A class for accessing biblical texts from the KJV data.

    This class encapsulates access to the biblical data and provides methods
    for extracting text based on book titles and verse ranges.
    """

    def __init__(self, data_folder: str | Path | None = None):
        """
        Initialize the Bible class.

        Args:
            data_folder: Path to the data folder containing index.json and
                bible files. If None, falls back to ``Settings.load()``,
                which layers prophecy.toml, the PROPHECY_DATA_FOLDER env
                var, and the dataclass default ('data').
        """
        if data_folder is None:
            data_folder = Settings.load().data_folder

        self.data_folder = Path(data_folder)

        # Validate data folder exists
        if not self.data_folder.exists():
            raise FileNotFoundError(f"Data folder not found: {self.data_folder}")

        # Load the index
        self.index_path = self.data_folder / "index.json"
        if not self.index_path.exists():
            raise FileNotFoundError(f"Index file not found: {self.index_path}")

        with open(self.index_path, encoding="utf-8") as f:
            self.index = json.load(f)

        # Cache for loaded books to avoid repeated file reads
        self._book_cache: dict[str, dict] = {}

    def _load_book(self, book_title: str) -> dict:
        """
        Load a book's data from its JSON file.

        Args:
            book_title: The title of the book (e.g., 'Genesis', 'Matthew')

        Returns:
            Dictionary containing the book's data

        Raises:
            ValueError: If the book title is not found in the index
            FileNotFoundError: If the book file doesn't exist
        """
        if book_title in self._book_cache:
            return self._book_cache[book_title]

        if book_title not in self.index:
            available_books = ", ".join(sorted(self.index.keys()))
            raise ValueError(
                f"Book '{book_title}' not found in index. Available books: {available_books}"
            )

        book_path = self.data_folder.parent / self.index[book_title]

        if not book_path.exists():
            raise FileNotFoundError(f"Book file not found: {book_path}")

        with open(book_path, encoding="utf-8") as f:
            book_data = json.load(f)

        self._book_cache[book_title] = book_data
        return book_data

    def _parse_verse_range(self, verse_range: str) -> tuple:
        """
        Parse a verse range string into start and end chapter:verse pairs.

        Args:
            verse_range: String in format "start_chapter:start_verse-end_chapter:end_verse"

        Returns:
            Tuple of ((start_chapter, start_verse), (end_chapter, end_verse))

        Raises:
            ValueError: If the verse range format is invalid
        """
        pattern = r"^(\d+):(\d+)-(\d+):(\d+)$"
        match = re.match(pattern, verse_range.strip())

        if not match:
            raise ValueError(
                f"Invalid verse range format: '{verse_range}'. Expected format: 'chapter:verse-chapter:verse'"
            )

        start_chapter, start_verse, end_chapter, end_verse = match.groups()
        return ((int(start_chapter), int(start_verse)), (int(end_chapter), int(end_verse)))

    def _extract_text_from_range(self, book_data: dict, start: tuple, end: tuple) -> str:
        """
        Extract text from a book within the specified verse range.

        Args:
            book_data: The book's JSON data
            start: Tuple of (start_chapter, start_verse)
            end: Tuple of (end_chapter, end_verse)

        Returns:
            Extracted text as a string

        Raises:
            ValueError: If chapter or verse numbers are invalid
        """
        start_chapter, start_verse = start
        end_chapter, end_verse = end

        # Validate range order
        if (start_chapter > end_chapter) or (
            start_chapter == end_chapter and start_verse > end_verse
        ):
            raise ValueError(
                f"Invalid range: start ({start_chapter}:{start_verse}) must be <= end ({end_chapter}:{end_verse})"
            )

        chapters = book_data.get("chapters", [])
        text_parts = []

        # Find chapters within the range
        for chapter in chapters:
            chapter_num = int(chapter["chapter"])

            if chapter_num < start_chapter or chapter_num > end_chapter:
                continue

            verses = chapter.get("verses", [])

            for verse in verses:
                verse_num = int(verse["verse"])

                # Check if this verse is within our range
                if chapter_num == start_chapter and verse_num < start_verse:
                    continue
                if chapter_num == end_chapter and verse_num > end_verse:
                    continue

                text_parts.append(verse["text"])

        if not text_parts:
            raise ValueError(
                f"No verses found in range {start_chapter}:{start_verse}-{end_chapter}:{end_verse}"
            )

        return " ".join(text_parts)

    def _ensure_proper_spacing(self, text: str) -> str:
        """
        Ensure proper spacing in text, particularly after periods.

        Args:
            text: Input text

        Returns:
            Text with corrected spacing
        """
        # Ensure there's always a space after a period if followed by a letter
        # and ensure there's only one space
        text = re.sub(r"\.([A-Z])", r". \1", text)
        text = re.sub(r"\.\s+", ". ", text)

        # Clean up multiple spaces
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def get_text(self, book_title: str, *parts: Mapping[str, int | str]) -> str:
        """
        Extract text from the specified book and parts.

        Args:
            book_title: The title of the book (e.g., 'Genesis', 'Matthew')
            *parts: Variable number of dictionaries, each containing:
                   - start_chapter: Starting chapter number
                   - start_verse: Starting verse number
                   - end_chapter: Ending chapter number
                   - end_verse: Ending verse number
                   OR
                   - range: String in format "start_chapter:start_verse-end_chapter:end_verse"

        Returns:
            Concatenated text from all parts with proper spacing

        Raises:
            ValueError: If book title is invalid or part format is incorrect
            FileNotFoundError: If book file doesn't exist

        Example:
            >>> bible = Bible()
            >>> text = bible.get_text('Genesis',
            ...                      {'start_chapter': 1, 'start_verse': 1, 'end_chapter': 1, 'end_verse': 3})
            >>> # Or using range format:
            >>> text = bible.get_text('Genesis', {'range': '1:1-1:3'})
        """
        if not parts:
            raise ValueError("At least one part must be specified")

        book_data = self._load_book(book_title)
        text_segments = []

        for part in parts:
            if not isinstance(part, dict):
                raise ValueError("Each part must be a dictionary")

            # Handle range format
            if "range" in part:
                range_value = part["range"]
                if not isinstance(range_value, str):
                    raise ValueError("'range' value must be a string like '1:1-2:7'")
                start, end = self._parse_verse_range(range_value)
            # Handle individual chapter/verse format
            elif all(
                key in part for key in ["start_chapter", "start_verse", "end_chapter", "end_verse"]
            ):
                start = (part["start_chapter"], part["start_verse"])
                end = (part["end_chapter"], part["end_verse"])
            else:
                raise ValueError(
                    "Each part must contain either 'range' or all of "
                    "'start_chapter', 'start_verse', 'end_chapter', 'end_verse'"
                )

            text = self._extract_text_from_range(book_data, start, end)
            text_segments.append(text)

        # Join all segments and ensure proper spacing
        combined_text = " ".join(text_segments)
        return self._ensure_proper_spacing(combined_text)

    def get_available_books(self) -> list[str]:
        """
        Get a list of all available book titles.

        Returns:
            Sorted list of book titles
        """
        return sorted(self.index.keys())

    def get_book_info(self, book_title: str) -> dict:
        """
        Get information about a specific book.

        Args:
            book_title: The title of the book

        Returns:
            Dictionary with book information including chapter count

        Raises:
            ValueError: If book title is not found
        """
        book_data = self._load_book(book_title)

        return {
            "title": book_data.get("book", book_title),
            "chapter_count": len(book_data.get("chapters", [])),
            "file_path": self.index[book_title],
        }
