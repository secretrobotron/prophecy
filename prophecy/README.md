# Prophecy Python API

The Prophecy Python package provides programmatic access to biblical texts with a focus on story-based extraction rather than just chapter and verse access.

## Installation

The package is included in this repository. To use it, ensure the `prophecy` directory is in your Python path or install it locally.

## Quick Start

```python
from prophecy.bible import Bible

# Initialize with default data folder
bible = Bible()

# Or specify a custom data folder
bible = Bible('/path/to/data')

# Extract text from Genesis creation story
creation_text = bible.get_text('Genesis', {'range': '1:1-2:7'})
print(creation_text)

# Extract multiple parts
text = bible.get_text('Genesis', 
                     {'range': '1:1-1:3'},      # Creation beginning
                     {'range': '1:26-1:28'})    # Creation of man

# Alternative dictionary format
psalm23 = bible.get_text('Psalms', {
    'start_chapter': 23,
    'start_verse': 1,
    'end_chapter': 23,
    'end_verse': 6
})
```

## API Reference

### Bible Class

#### Constructor

```python
Bible(data_folder=None)
```

**Parameters:**
- `data_folder` (str, optional): Path to the data folder containing `index.json` and Bible files. If `None`, uses the `PROPHECY_DATA_FOLDER` environment variable, or defaults to `'data'`.

**Raises:**
- `FileNotFoundError`: If the data folder or index file doesn't exist.

#### Methods

##### get_text(book_title, *parts)

Extract text from the specified book and verse ranges.

**Parameters:**
- `book_title` (str): The name of the book (e.g., 'Genesis', 'Matthew')
- `*parts`: Variable number of dictionaries specifying verse ranges

**Part Dictionary Format:**

Option 1 - Range string:
```python
{'range': 'start_chapter:start_verse-end_chapter:end_verse'}
```

Option 2 - Individual fields:
```python
{
    'start_chapter': int,
    'start_verse': int,
    'end_chapter': int,
    'end_verse': int
}
```

**Returns:**
- `str`: Concatenated text from all parts with proper spacing

**Example:**
```python
# Single verse
text = bible.get_text('Genesis', {'range': '1:1-1:1'})

# Multiple verses
text = bible.get_text('Genesis', {'range': '1:1-1:5'})

# Cross-chapter range
text = bible.get_text('Genesis', {'range': '1:31-2:3'})

# Multiple parts
text = bible.get_text('Genesis', 
                     {'range': '1:1-1:3'},
                     {'range': '2:1-2:3'})

# Dictionary format
text = bible.get_text('Genesis', {
    'start_chapter': 1,
    'start_verse': 1,
    'end_chapter': 1,
    'end_verse': 5
})
```

##### get_available_books()

Get a list of all available book titles.

**Returns:**
- `List[str]`: Sorted list of book titles

##### get_book_info(book_title)

Get information about a specific book.

**Parameters:**
- `book_title` (str): The name of the book

**Returns:**
- `Dict`: Book information including title, chapter count, and file path

## Data Structure

The Bible class expects the following data structure:

```
data/
├── index.json              # Maps book names to file paths
└── bible-kjv/             # Directory containing Bible book files
    ├── Genesis.json
    ├── Exodus.json
    └── ...
```

Each book file contains:
```json
{
  "book": "Genesis",
  "chapters": [
    {
      "chapter": "1",
      "verses": [
        {
          "verse": "1",
          "text": "In the beginning God created the heaven and the earth."
        }
      ]
    }
  ]
}
```

## Features

- **Story-based text extraction**: Extract complete narratives spanning multiple chapters
- **Flexible verse range specification**: Use either range strings or dictionary format
- **Multiple part concatenation**: Combine text from different verse ranges
- **Proper text spacing**: Automatically handles spacing between sentences and parts
- **Book caching**: Efficiently caches loaded books to avoid repeated file reads
- **Environment variable support**: Configure data folder via `PROPHECY_DATA_FOLDER`
- **Comprehensive error handling**: Clear error messages for invalid inputs

## Error Handling

The Bible class provides clear error messages for common issues:

- **Invalid book names**: Lists available books when a book isn't found
- **Invalid verse ranges**: Validates format and verse existence
- **Missing files**: Clear messages when data files are missing
- **Invalid parameters**: Helpful messages for incorrect function calls

## Examples

See `examples/bible_api_demo.py` for a comprehensive demonstration of all features.

## Testing

Run the test suite:

```bash
python -m pytest tests/test_bible.py -v
```

The tests include both unit tests with mock data and integration tests with real Bible data.