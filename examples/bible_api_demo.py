#!/usr/bin/env python3
"""
Example demonstrating the new Bible API.

This script shows how to use the Bible class to extract biblical texts
based on verse ranges, similar to how stories are defined in stories.yml.
"""

import sys
import os
from pathlib import Path

# Add the prophecy package to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prophecy.bible import Bible


def main():
    """Demonstrate the Bible API functionality."""

    print("=== Bible API Demonstration ===\n")

    try:
        # Initialize Bible with default data folder
        bible = Bible("data")
        print("✓ Bible initialized successfully")

        # Show available books
        books = bible.get_available_books()
        print(f"✓ Found {len(books)} books in the Bible")
        print(f"First 10 books: {', '.join(books[:10])}")

        print("\n=== Example 1: The Creation Story ===")
        # Extract the creation story (Genesis 1:1-2:7)
        creation_text = bible.get_text("Genesis", {"range": "1:1-2:7"})
        print(f"Creation story ({len(creation_text.split())} words):")
        print(creation_text[:200] + "..." if len(creation_text) > 200 else creation_text)

        print("\n=== Example 2: Multiple Verse Ranges ===")
        # Extract text from multiple parts (like complex stories)
        multi_text = bible.get_text(
            "Genesis",
            {"range": "1:1-1:3"},  # Beginning of creation
            {"range": "1:26-1:28"},
        )  # Creation of man
        print("Creation highlights:")
        print(multi_text)

        print("\n=== Example 3: Using Dictionary Format ===")
        # Alternative format for specifying ranges
        psalm23 = bible.get_text(
            "Psalms", {"start_chapter": 23, "start_verse": 1, "end_chapter": 23, "end_verse": 6}
        )
        print("Psalm 23:")
        print(psalm23)

        print("\n=== Example 4: Story from stories.yml ===")
        # Extract a story that's defined in stories.yml
        # Noah's ark story
        flood_text = bible.get_text("Genesis", {"range": "6:5-9:17"})
        print(f"The Great Flood story ({len(flood_text.split())} words):")
        print(flood_text[:300] + "..." if len(flood_text) > 300 else flood_text)

        print("\n=== Example 5: Book Information ===")
        # Get information about a book
        genesis_info = bible.get_book_info("Genesis")
        print(f"Genesis has {genesis_info['chapter_count']} chapters")

        psalms_info = bible.get_book_info("Psalms")
        print(f"Psalms has {psalms_info['chapter_count']} chapters")

        print("\n=== Environment Variable Example ===")
        # Show how to use environment variable
        print(f"Current data folder: {bible.data_folder}")
        print("To use a different data folder, set PROPHECY_DATA_FOLDER environment variable")

        print("\n✓ All examples completed successfully!")

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Make sure you're running this from the prophecy repository root")
        print("and that the data folder exists with the Bible files.")
        return 1

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
