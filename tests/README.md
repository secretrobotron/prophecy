# Prophecy Tests

This directory contains pytest tests to validate the structure and content of the prophecy project data files.

## Test Files

### test_stories_structure.py

Comprehensive tests for validating the structure of `data/stories.yml` according to the project requirements:

1. **Story Structure Validation**
   - Every top-level entry is a bible story title
   - Each story contains required fields: `book` and `verses`

2. **Book Reference Validation**
   - All book references exist in `data/old_testament.json`
   - Book names are properly formatted strings

3. **Verse Format Validation**
   - Verses follow the format: `chapter:verse-chapter:verse`
   - All elements are integers
   - Verse ranges are logically valid (start ≤ end)

4. **Bible Data Validation**
   - All referenced chapters exist in the corresponding bible book files
   - All referenced verses exist in the specified chapters
   - Data integrity between stories.yml and bible JSON files

## Running Tests

### Run all tests:
```bash
pytest
```

### Run with verbose output:
```bash
pytest -v
```

### Run specific test file:
```bash
pytest tests/test_stories_structure.py
```

### Run specific test method:
```bash
pytest tests/test_stories_structure.py::TestStoriesStructure::test_verses_format_is_valid
```

## Test Requirements

The tests require the following Python packages:
- pytest
- pyyaml

These should be installed automatically when running the tests for the first time.

## Test Coverage

The tests verify that:
- `data/stories.yml` has the correct YAML structure
- Story titles are valid strings
- Each story references a valid Old Testament book
- Verse ranges use the correct format and reference valid bible passages
- The bible book JSON files contain the referenced chapters and verses
- Stories cover a reasonable variety of Old Testament books (at least 10)

## Adding New Tests

When adding new tests, follow these guidelines:
- Use descriptive test method names starting with `test_`
- Add appropriate assertions with helpful error messages
- Use fixtures for loading data to avoid repeated file I/O
- Document any new requirements or validation rules