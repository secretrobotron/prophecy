# Unit Tests for create_sources.py

This document describes the unit tests created to verify that the output of `scripts/create_sources.py` consists of valid ranges in the KJV Bible.

## Test Overview

The tests are organized into two main test classes:

### TestCreateSources
Tests the core functionality of the `create_sources.py` script:

- **Text cleaning**: Validates the `clean_text()` function properly removes special characters and normalizes whitespace
- **Regex validation**: Tests the `RANGE_TOKEN` regex pattern matches valid verse ranges and rejects invalid ones
- **Bullet parsing**: Tests the `parse_bullet()` function correctly extracts book names, verse ranges, and source tags
- **Range normalization**: Verifies that ranges are properly normalized (spaces around hyphens, duplicate removal)
- **Commentary handling**: Tests parsing of ranges embedded in commentary text
- **Book mapping**: Validates the abbreviation-to-full-name mapping for Pentateuch books

### TestCreateSourcesWithBible
Tests that parsed ranges are valid in the actual KJV Bible data:

- **Range conversion**: Tests conversion from create_sources format (e.g., "1:1-31") to Bible class format (e.g., "1:1-1:31")
- **Bible accessibility**: Verifies all Pentateuch books are accessible via the Bible class
- **Range validation**: Tests that parsed ranges can be successfully retrieved from the Bible
- **Edge cases**: Tests single verses, cross-chapter ranges, and error handling
- **Special formatting**: Tests handling of verse suffixes like "4b"
- **Comprehensive workflow**: End-to-end testing from parsing to Bible validation

## Key Features

### Range Format Compatibility
The tests handle the difference between create_sources range formats and Bible class expectations:
- create_sources allows abbreviated ranges like "1:1-31" (same chapter)
- Bible class requires full format like "1:1-1:31"
- Tests include a conversion function to bridge this gap

### Realistic Testing
- Uses mock HTML responses to test the full extraction workflow
- Tests with actual Pentateuch books (Genesis, Exodus, Leviticus, Numbers, Deuteronomy)
- Validates that extracted ranges produce meaningful biblical text content

### Error Handling
- Tests invalid book names, non-existent chapters/verses
- Validates proper exception handling for malformed ranges
- Tests resilience to commentary text that might interfere with parsing

## Running the Tests

```bash
# Run all create_sources tests
python -m pytest tests/test_create_sources.py -v

# Run specific test class
python -m pytest tests/test_create_sources.py::TestCreateSources -v
python -m pytest tests/test_create_sources.py::TestCreateSourcesWithBible -v

# Run with coverage
python -m pytest tests/test_create_sources.py --cov=scripts.create_sources
```

## Test Coverage

The tests cover:
- ✅ Text cleaning and normalization
- ✅ Regular expression pattern matching
- ✅ Bullet point parsing and range extraction
- ✅ Book name mapping and validation
- ✅ Range format conversion for Bible class compatibility
- ✅ Integration with actual KJV Bible data
- ✅ Error handling for invalid input
- ✅ Special verse formatting (suffixes like "4b")
- ✅ End-to-end workflow validation

## Dependencies

The tests require:
- `pytest` for test framework
- `prophecy.bible.Bible` class for KJV data access
- `beautifulsoup4` for HTML parsing (mocked in tests)
- `requests` library (mocked in tests)

## Notes

- Tests are designed to work with the existing repository structure
- Bible data is accessed from the `data/bible-kjv/` submodule
- Mock tests simulate network requests to avoid external dependencies
- Tests validate both parsing accuracy and biblical content correctness