# Prophecy Scripts

This directory contains utility scripts for setting up, maintaining, and working with the Prophecy project data and infrastructure.

## Available Scripts

### 1. `create_bible_indexes.py`
Creates index files for organizing biblical text data by testament.

**Purpose:**
- Generates `old_testament.json` and `new_testament.json` index files
- Maps book names to their corresponding JSON file paths
- Handles filename normalization (e.g., "Song of Solomon" → "SongofSolomon.json")
- Validates book availability in the Bible data submodule

**Usage:**
```bash
python scripts/create_bible_indexes.py
```

**Generated files:**
- `data/old_testament.json` - Index of Hebrew Bible books
- `data/new_testament.json` - Index of New Testament books

**Dependencies:**
- Requires `data/bible-kjv/Books.json` (from the Bible submodule)
- Python standard library only

### 2. `example_usage.py`
Provides quick usage examples and validation of the project setup.

**Purpose:**
- Tests basic Bible API functionality
- Demonstrates story loading and text extraction
- Validates data integrity
- Serves as a quick setup verification script

**Usage:**
```bash
python scripts/example_usage.py
```

**Features:**
- Loads and displays available biblical books
- Extracts sample text from Genesis
- Shows story definitions from `stories.yml`
- Provides troubleshooting output

## Setup and Prerequisites

### Before Running Scripts

1. **Initialize the Bible data submodule:**
   ```bash
   git submodule init
   git submodule update
   ```

2. **Install Python dependencies:**
   ```bash
   pip install pyyaml
   ```
   Or use the conda environment:
   ```bash
   conda env create -f environment.yml
   conda activate prophecy
   ```

3. **Run from repository root:**
   ```bash
   # Correct usage
   python scripts/create_bible_indexes.py
   
   # Not from scripts directory
   cd scripts && python create_bible_indexes.py  # This may fail
   ```

## Script Details

### create_bible_indexes.py

**Function Overview:**
```python
def normalize_book_name_to_filename(book_name):
    """Convert book name from Books.json to actual JSON filename format."""
    
def create_bible_indexes():
    """Create Hebrew Bible and New Testament index files."""
```

**Process:**
1. Reads `data/bible-kjv/Books.json` to get official book list
2. Separates books into Hebrew Bible and New Testament
3. Normalizes book names to match actual JSON filenames
4. Creates index files with path mappings
5. Validates file existence

**Output Example:**
```json
{
  "Genesis": "data/bible-kjv/Genesis.json",
  "Exodus": "data/bible-kjv/Exodus.json",
  "Leviticus": "data/bible-kjv/Leviticus.json"
}
```

### example_usage.py

**Function Overview:**
- Demonstrates basic library usage
- Tests data file accessibility
- Provides example output for verification

**Typical Output:**
- List of available books
- Sample biblical text extraction
- Story definition examples
- Error messages if setup is incomplete

## Development and Maintenance

### Adding New Scripts

When adding new utility scripts to this directory:

1. **Follow the naming pattern**: Use descriptive, lowercase names with underscores
2. **Include proper documentation**: Add function docstrings and file headers
3. **Handle errors gracefully**: Provide clear error messages for common issues
4. **Test from repository root**: Ensure scripts work when run from the main directory
5. **Update this README**: Add documentation for new scripts

### Common Script Pattern
```python
#!/usr/bin/env python3
"""
Brief description of script purpose.
"""

import sys
import os
from pathlib import Path

def main():
    """Main script function."""
    try:
        # Script logic here
        pass
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Troubleshooting

### Common Issues

**"No such file or directory" errors:**
- Ensure you're running from the repository root
- Check that the Bible submodule is initialized: `git submodule status`
- Verify file paths in error messages

**"Books.json not found":**
```bash
# Initialize and update the Bible data submodule
git submodule init
git submodule update
cd data/bible-kjv && ls -la Books.json
```

**Python import errors:**
```bash
# Ensure you're in the repository root
pwd  # Should show .../prophecy
python scripts/script_name.py
```

**Permission denied:**
```bash
# Make scripts executable if needed
chmod +x scripts/*.py
```

## Integration with Project Workflow

These scripts are typically used in the following scenarios:

### Initial Setup
```bash
# 1. Clone repository
git clone <repository-url>
cd prophecy

# 2. Initialize submodules
git submodule init
git submodule update

# 3. Create indexes
python scripts/create_bible_indexes.py

# 4. Verify setup
python scripts/example_usage.py
```

### Data Updates
When the Bible data submodule is updated:
```bash
git submodule update --remote
python scripts/create_bible_indexes.py  # Regenerate indexes
python -m pytest tests/  # Verify data integrity
```

### Development Workflow
- Use `example_usage.py` for quick functionality testing
- Run `create_bible_indexes.py` after any changes to book organization
- Scripts can be integrated into CI/CD pipelines for automated testing

## Advanced Usage

### Customizing Index Creation
The `create_bible_indexes.py` script can be modified to:
- Include additional metadata in index files
- Create custom book groupings
- Generate different file formats (CSV, YAML, etc.)
- Filter books by specific criteria

### Batch Processing
Scripts can be combined for batch operations:
```bash
# Setup and validation workflow
python scripts/create_bible_indexes.py && \
python scripts/example_usage.py && \
python -m pytest tests/
```