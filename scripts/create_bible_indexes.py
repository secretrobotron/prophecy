#!/usr/bin/env python3
"""
Script to create Hebrew Bible and New Testament index files for the Bible KJV submodule.
"""

import json
import os

def normalize_book_name_to_filename(book_name):
    """Convert book name from Books.json to the actual JSON filename format."""
    # Handle special cases
    replacements = {
        ' ': '',  # Remove spaces
        'Song of Solomon': 'SongofSolomon'
    }
    
    filename = book_name
    for old, new in replacements.items():
        if old == book_name:  # Exact match for special cases
            filename = new
        else:  # General replacements
            filename = filename.replace(old, new)
    
    return f"{filename}.json"

def create_bible_indexes():
    """Create Hebrew Bible index file."""
    
    # Read the Books.json file
    with open('data/bible-kjv/Books.json', 'r') as f:
        books = json.load(f)
    
    # Based on biblical canon, first 39 books are Hebrew Bible, last 27 are New Testament
    hebrew_bible_books = books[:39]  # Genesis through Malachi
    new_testament_books = books[39:]  # Matthew through Revelation
    
    # Create Hebrew Bible index
    hebrew_bible_index = {}
    for book_name in hebrew_bible_books:
        filename = normalize_book_name_to_filename(book_name)
        file_path = f"data/bible-kjv/{filename}"
        
        # Verify the file exists
        if os.path.exists(file_path):
            hebrew_bible_index[book_name] = file_path
        else:
            print(f"Warning: File not found for {book_name}: {file_path}")
    
    # Create New Testament index
    new_testament_index = {}
    for book_name in new_testament_books:
        filename = normalize_book_name_to_filename(book_name)
        file_path = f"data/bible-kjv/{filename}"
        
        # Verify the file exists
        if os.path.exists(file_path):
            new_testament_index[book_name] = file_path
        else:
            print(f"Warning: File not found for {book_name}: {file_path}")
    
    # Write Hebrew Bible index to index.json (replaces old_testament.json)
    with open('data/index.json', 'w') as f:
        json.dump(hebrew_bible_index, f, indent=2)
    print(f"Created data/index.json with {len(hebrew_bible_index)} books")
    
    # Write New Testament index - REMOVED as requested
    # with open('data/new_testament.json', 'w') as f:
    #     json.dump(new_testament_index, f, indent=2)
    # print(f"Created data/new_testament.json with {len(new_testament_index)} books")
    
    # Print summary
    print("\nHebrew Bible books:")
    for book in hebrew_bible_books:
        print(f"  - {book}")
    
    print("\nNew Testament books:")
    for book in new_testament_books:
        print(f"  - {book}")

if __name__ == "__main__":
    create_bible_indexes()
