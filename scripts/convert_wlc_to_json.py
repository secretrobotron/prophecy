#!/usr/bin/env python3
"""
Convert the Westminster Leningrad Codex (wlc.txt) to JSON format.

This script reads the Hebrew Bible text from data/wlc.txt and converts it to
JSON files, one per book, in the data/hebrew/ directory.

Input format (tab-separated):
    Book chapter:verse.word    word_id    hebrew_word

Output format:
    {
        "book": "Genesis",
        "chapters": [
            {
                "chapter": "1",
                "verses": [
                    {
                        "verse": "1",
                        "text": "בְּרֵאשִׁית בָּרָא אֱלֹהִים..."
                    }
                ]
            }
        ]
    }
"""

import json
import os
from collections import defaultdict


# Mapping from abbreviations in wlc.txt to full book names
BOOK_NAME_MAPPING = {
    "Gen": "Genesis",
    "Exod": "Exodus",
    "Lev": "Leviticus",
    "Num": "Numbers",
    "Deut": "Deuteronomy",
    "Josh": "Joshua",
    "Judg": "Judges",
    "Ruth": "Ruth",
    "1Sam": "1 Samuel",
    "2Sam": "2 Samuel",
    "1Kgs": "1 Kings",
    "2Kgs": "2 Kings",
    "1Chr": "1 Chronicles",
    "2Chr": "2 Chronicles",
    "Ezra": "Ezra",
    "Neh": "Nehemiah",
    "Esth": "Esther",
    "Job": "Job",
    "Ps": "Psalms",
    "Prov": "Proverbs",
    "Eccl": "Ecclesiastes",
    "Song": "Song of Solomon",
    "Isa": "Isaiah",
    "Jer": "Jeremiah",
    "Lam": "Lamentations",
    "Ezek": "Ezekiel",
    "Dan": "Daniel",
    "Hos": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obad": "Obadiah",
    "Jonah": "Jonah",
    "Mic": "Micah",
    "Nah": "Nahum",
    "Hab": "Habakkuk",
    "Zeph": "Zephaniah",
    "Hag": "Haggai",
    "Zech": "Zechariah",
    "Mal": "Malachi",
}


def parse_wlc_file(input_file):
    """
    Parse the wlc.txt file and organize it by book, chapter, and verse.

    Returns:
        dict: Nested dictionary structure {book: {chapter: {verse: [words]}}}
    """
    # Structure: book -> chapter -> verse -> list of words
    books = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Parse the line: "Book chapter:verse.word    word_id    hebrew_word"
            parts = line.split("\t")
            if len(parts) < 3:
                continue

            reference = parts[0]  # e.g., "Gen 1:1.1"
            hebrew_word = parts[2]  # e.g., "בְּ/רֵאשִׁ֖ית"

            # Remove slashes from the Hebrew word
            hebrew_word = hebrew_word.replace("/", "")

            # Parse the reference
            ref_parts = reference.split()
            if len(ref_parts) < 2:
                continue

            book_abbrev = ref_parts[0]  # e.g., "Gen"
            location = ref_parts[1]  # e.g., "1:1.1"

            # Parse chapter:verse.word
            chapter_verse = location.split(".")
            if len(chapter_verse) < 2:
                continue

            chapter_verse_parts = chapter_verse[0].split(":")
            if len(chapter_verse_parts) < 2:
                continue

            chapter = chapter_verse_parts[0]
            verse = chapter_verse_parts[1]

            # Add the word to the structure
            books[book_abbrev][chapter][verse].append(hebrew_word)

    return books


def convert_to_json_structure(books):
    """
    Convert the nested dictionary structure to the required JSON format.

    Args:
        books: dict with structure {book: {chapter: {verse: [words]}}}

    Returns:
        dict: JSON structures keyed by book abbreviation
    """
    json_books = {}

    for book_abbrev, chapters in books.items():
        # Get the full book name
        full_name = BOOK_NAME_MAPPING.get(book_abbrev, book_abbrev)

        # Build chapters array
        chapters_array = []
        for chapter_num in sorted(chapters.keys(), key=int):
            verses = chapters[chapter_num]

            # Build verses array
            verses_array = []
            for verse_num in sorted(verses.keys(), key=int):
                words = verses[verse_num]
                text = " ".join(words)

                verses_array.append({"verse": verse_num, "text": text})

            chapters_array.append({"chapter": chapter_num, "verses": verses_array})

        # Create the final structure
        json_books[book_abbrev] = {"book": full_name, "chapters": chapters_array}

    return json_books


def write_json_files(json_books, output_dir):
    """
    Write each book to a separate JSON file.

    Args:
        json_books: dict with JSON structures keyed by book abbreviation
        output_dir: directory to write the JSON files
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    for book_abbrev, book_data in json_books.items():
        # Use full book name without spaces for filename
        full_name = book_data["book"].replace(" ", "")
        output_file = os.path.join(output_dir, f"{full_name}.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(book_data, f, ensure_ascii=False, indent=2)

        print(f"Written: {output_file}")


def main():
    """Main function to convert wlc.txt to JSON files."""
    # Define paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(base_dir, "data", "wlc.txt")
    output_dir = os.path.join(base_dir, "data", "hebrew")

    print(f"Reading from: {input_file}")
    print(f"Writing to: {output_dir}")

    # Parse the input file
    print("Parsing wlc.txt...")
    books = parse_wlc_file(input_file)

    # Convert to JSON structure
    print("Converting to JSON structure...")
    json_books = convert_to_json_structure(books)

    # Write JSON files
    print("Writing JSON files...")
    write_json_files(json_books, output_dir)

    print(f"\nConversion complete! {len(json_books)} books processed.")


if __name__ == "__main__":
    main()
