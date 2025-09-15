# Prophecy Data Directory

This directory contains the core data files used by the Prophecy project for biblical text analysis and story extraction.

## Contents

### Bible Text Data
- **`bible-kjv/`** - Git submodule containing King James Version Bible in JSON format
  - Source: [aruljohn/Bible-kjv](https://github.com/aruljohn/Bible-kjv)
  - Contains individual JSON files for each biblical book
  - Format: Structured by books, chapters, and verses
  - Example: `Genesis.json`, `Exodus.json`, etc.

### Index and Configuration
- **`index.json`** - Maps biblical book names to their corresponding JSON file paths
  - Used by the Python API to locate Bible text files
  - Contains 39 Hebrew Bible books from the Tanakh
  - Format: `{"BookName": "data/bible-kjv/BookName.json"}`

### Story Definitions
- **`stories.yml`** - YAML file defining 72+ major biblical narratives
  - Maps story titles to their biblical references
  - Includes book name and verse ranges for each story
  - Format: Standard biblical citation (e.g., `1:1-2:7` for Chapter 1, verse 1 through Chapter 2, verse 7)
  - Source: Curated from [biblestories.org](https://biblestories.org/)
  - Coverage: Major Hebrew Bible narratives from Genesis through minor prophets

### Analysis Prompts
- **`prompts.tsv`** - Tab-separated file containing sentiment analysis prompts
  - Contains prompts organized by historical period and topic
  - Used for AI-powered biblical text analysis
  - Format: Four columns - `id`, `period`, `topic`, `prompt`
  - Source: [Curated prompt collection](https://docs.google.com/spreadsheets/d/14xjsF39o8T6dVA0DCRL9hz_tPHRQv4rVb8MAeP52GLQ/)

### Template
- **`template.txt`** - Text template for prompt formatting and AI interactions

## Data Structure Example

### Story Definition Format (stories.yml)
```yaml
The Creation:
  book: Genesis
  verses:
    - 1:1-2:7

The Great Flood:
  book: Genesis
  verses:
    - 6:5-9:17
```

### Bible JSON Format
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

## Usage

These data files are used by:
- **Bible API** (`prophecy.bible.Bible`) - Programmatic access to biblical texts
- **Stories module** (`prophecy.stories`) - Story-based text extraction
- **Prompts module** (`prophecy.prompts`) - Sentiment analysis workflows
- **Example scripts** - Demonstrations and testing

## Setup

1. **Initialize the Bible submodule**:
   ```bash
   git submodule init
   git submodule update
   ```

2. **Verify data integrity**:
   ```bash
   python -m pytest tests/test_stories_structure.py tests/test_prompts.py
   ```

## Data Sources and Attribution

- **Bible Text**: King James Version courtesy of [aruljohn/Bible-kjv](https://github.com/aruljohn/Bible-kjv)
- **Story Boundaries**: Based on traditional biblical scholarship and [biblestories.org](https://biblestories.org/)
- **Analysis Prompts**: Curated collection for sentiment analysis research

## Contributing

When adding new stories or modifying existing ones:
1. Follow the existing YAML format in `stories.yml`
2. Use standard biblical citation format for verse ranges
3. Verify all referenced verses exist in the corresponding Bible JSON files
4. Run tests to ensure data integrity: `python -m pytest tests/`