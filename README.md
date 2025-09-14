# Prophecy: Biblical Text Analysis and Story Extraction

A Python toolkit for analyzing biblical texts, extracting stories, and working with structured biblical data. This project provides programmatic access to the King James Version Bible organized by stories rather than just chapters and verses.

## Overview

The Prophecy project bridges the gap between traditional biblical organization (books, chapters, verses) and narrative structure (stories, themes, characters). It enables researchers, developers, and biblical scholars to work with biblical texts as coherent narratives rather than fragmented verse collections.

## Key Features

- **Story-based Biblical Text Access**: Extract complete biblical narratives spanning multiple chapters
- **Comprehensive Story Index**: 72+ major Old Testament stories with precise verse ranges
- **Structured Data Format**: JSON-based Bible text with chapter/verse organization
- **Testament Indexes**: Separate Old and New Testament book catalogs
- **Flexible Text Extraction**: Retrieve stories by name, book, or custom verse ranges
- **Clean API Design**: Object-oriented Python modules for easy integration

## Project Structure

```
prophecy/
├── data/
│   ├── bible-kjv/          # KJV Bible JSON files (submodule)
│   ├── stories.yml         # Story definitions with verse ranges
│   ├── old_testament.json  # OT book index
│   └── new_testament.json  # NT book index
├── prophecy/               # Python package (planned)
│   ├── bible.py           # Bible text access classes
│   ├── stories.py         # Story extraction and analysis
│   └── utils.py           # Utility functions
├── scripts/               # Development utilities
└── tests/                 # Test suite
```

## Data Sources

- **Bible Text**: King James Version from [aruljohn/Bible-kjv](https://github.com/aruljohn/Bible-kjv)
- **Story Definitions**: Curated collection of major biblical narratives
- **Verse Ranges**: Precisely mapped story boundaries using standard biblical citations
- **Analysis Prompts**: Curated collection of sentiment [prompts](https://docs.google.com/spreadsheets/d/14xjsF39o8T6dVA0DCRL9hz_tPHRQv4rVb8MAeP52GLQ/)

## Use Cases

### Academic Research
- Analyze narrative themes across biblical stories
- Study character development within complete story arcs
- Compare parallel narratives (e.g., different accounts of the same events)

### Digital Humanities
- Text mining and sentiment analysis of biblical narratives
- Computational analysis of biblical language patterns
- Cross-referencing themes and motifs

### Educational Tools
- Create story-based Bible study materials
- Generate thematic reading plans
- Build interactive biblical narrative explorers

### Software Development
- Biblical reference applications
- Devotional and study apps
- API backends for biblical content

## Quick Start

```python
# Load biblical stories
import yaml
with open('data/stories.yml') as f:
    stories = yaml.safe_load(f)

# Access story information
creation_story = stories['The Creation']
print(f"Book: {creation_story['book']}")
print(f"Verses: {creation_story['verses']}")

# Load testament indexes
import json
with open('data/old_testament.json') as f:
    old_testament = json.load(f)

# Get path to Genesis
genesis_path = old_testament['Genesis']
# Returns: "data/bible-kjv/Genesis.json"
```

## Story Coverage

Currently includes 72+ major Old Testament narratives:

- **Genesis**: Creation, Fall, Noah, Abraham, Isaac, Jacob, Joseph
- **Exodus**: Moses, Burning Bush, Ten Plagues, Red Sea, Ten Commandments
- **Historical Books**: Joshua, Judges, Samuel, Kings, Chronicles
- **Wisdom Literature**: Job, selected Psalms narratives
- **Prophets**: Major prophetic narratives from Isaiah, Jeremiah, Ezekiel, Daniel
- **Minor Prophets**: Key stories from Jonah and others

## Verse Range Format

Stories use standard biblical citation format:
- `1:1-2:7` - Chapter 1 verse 1 through Chapter 2 verse 7
- `4:1-4:16` - Chapter 4 verses 1 through 16
- Multiple ranges supported for complex narratives

## Development Status

- ✅ **Data Layer**: Complete Bible text, story definitions, indexes
- ✅ **Story Mapping**: 72+ stories with precise verse ranges
- 🔄 **Python Package**: Object-oriented API in development
- 📋 **Documentation**: API docs and tutorials planned
- 📋 **Testing**: Comprehensive test suite planned
- 📋 **New Testament**: Story mapping for NT narratives planned

## Contributing

Contributions welcome! Areas of need:
- New Testament story definitions
- Additional Old Testament narratives
- Python API development
- Documentation and examples
- Test coverage

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Bible text courtesy of [aruljohn/Bible-kjv](https://github.com/aruljohn/Bible-kjv)
- Story boundaries based on traditional biblical scholarship
- Inspired by narrative approaches to biblical studies
