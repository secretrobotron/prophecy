#!/usr/bin/env python3
"""
Example script showing how to use the Hebrew Bible and New Testament index files.
"""

import json

def load_testament_index(testament_type):
    """Load either 'old' (Hebrew Bible) or 'new' testament index."""
    filename = f"data/{testament_type}_testament.json"
    with open(filename, 'r') as f:
        return json.load(f)

def get_book_data(book_name, testament_index):
    """Get the JSON data for a specific book."""
    if book_name not in testament_index:
        return None
    
    file_path = testament_index[book_name]
    with open(file_path, 'r') as f:
        return json.load(f)

def main():
    """Demonstrate usage of the Bible index files."""
    
    # Load both testaments
    hebrew_bible = load_testament_index('old')
    new_testament = load_testament_index('new')
    
    print("=== Hebrew Bible Books ===")
    for book_name in hebrew_bible:
        print(f"  - {book_name}")
    print(f"Total: {len(hebrew_bible)} books")
    
    print("\n=== New Testament Books ===")
    for book_name in new_testament:
        print(f"  - {book_name}")
    print(f"Total: {len(new_testament)} books")
    
    # Example: Load Genesis data
    print("\n=== Example: Genesis Chapter 1, Verse 1 ===")
    genesis_data = get_book_data('Genesis', hebrew_bible)
    if genesis_data:
        first_verse = genesis_data['chapters'][0]['verses'][0]
        print(f"Book: {genesis_data['book']}")
        print(f"Chapter: {first_verse}")
    
    # Example: Load Matthew data
    print("\n=== Example: Matthew Chapter 1, Verse 1 ===")
    matthew_data = get_book_data('Matthew', new_testament)
    if matthew_data:
        first_verse = matthew_data['chapters'][0]['verses'][0]
        print(f"Book: {matthew_data['book']}")
        print(f"Chapter: {first_verse}")
    
    # Example: Search for a specific book
    print("\n=== Example: Find 'Psalms' ===")
    if 'Psalms' in hebrew_bible:
        print(f"Psalms found in Hebrew Bible: {hebrew_bible['Psalms']}")
        psalms_data = get_book_data('Psalms', hebrew_bible)
        print(f"Psalms has {len(psalms_data['chapters'])} chapters")

if __name__ == "__main__":
    main()
