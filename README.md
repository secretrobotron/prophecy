# Hebrew Bible Text Analysis and Story Extraction

A Python toolkit for analyzing biblical texts, extracting stories, and working with structured biblical data. This project provides programmatic access to the Bible organized by stories rather than just chapters and verses.

## Overview

The Prophecy project bridges the gap between traditional biblical organization (books, chapters, verses) and narrative structure (stories, themes, characters). It enables researchers, developers, and biblical scholars to work with biblical texts as coherent narratives rather than fragmented verse collections.

## Key Features

- **Story-based Biblical Text Access**: Extract complete biblical narratives spanning multiple chapters
- **Comprehensive Story Index**: 72+ major Hebrew Bible stories with precise verse ranges
- **Structured Data Format**: JSON-based Bible text with chapter/verse organization
- **Testament Indexes**: Index of Hebrew Bible books from the KJV translation
- **Flexible Text Extraction**: Retrieve stories by name, book, or custom verse ranges
- **Clean Python API**: Object-oriented modules for easy integration
- **AI Integration**: Built-in support for OpenAI and other AI providers for text analysis
- **Sentiment Analysis**: Curated prompts for biblical text sentiment analysis
- **Comprehensive Testing**: Full test suite ensuring data integrity and API reliability

## Project Structure

```
prophecy/
├── data/
│   ├── bible-kjv/                # KJV Bible JSON files (submodule)
│   ├── stories.yml               # Story definitions with verse ranges
│   ├── prompts.tsv               # Sentiment analysis prompts
│   ├── index.json                # Hebrew Bible book index
│   └── template.txt              # AI prompt template
├── prophecy/                     # Python package
│   ├── __init__.py               # Package initialization
│   ├── bible.py                  # Bible text access classes
│   ├── stories.py                # Story extraction and analysis
│   ├── prompts.py                # Prompts management
│   └── ai_providers.py           # AI integration (OpenAI, etc.)
├── examples/                     # Demonstration scripts
│   ├── bible_api_demo.py         # Bible API usage examples
│   ├── ai_provider_demo.py       # AI analysis examples
│   └── prompts_usage_demo.py     # Prompts system demo
├── scripts/                      # Utility scripts
│   ├── create_bible_indexes.py   # Index generation
│   └── example_usage.py          # Setup verification
└── tests/                        # Test suite
    ├── test_bible.py             # Bible API tests
    ├── test_stories_structure.py # Data integrity tests
    ├── test_prompts.py           # Prompts validation tests
    └── test_*.py                 # Additional test modules
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

### Software Development
- Building biblical study applications
- Creating educational software
- Developing content management systems for religious texts

## Running Examples

The project includes comprehensive example scripts:

```bash
# Test the Bible API
python examples/bible_api_demo.py

# Explore AI-powered analysis (requires OpenAI API key)
export OPENAI_API_KEY="your-key-here"
python examples/ai_provider_demo.py

# Learn about the prompts system
python examples/prompts_usage_demo.py
```

See `examples/README.md` for detailed documentation of all demonstration scripts.

## Installation and Setup

### Prerequisites
```bash
# Clone the repository
git clone https://github.com/rvosa/prophecy.git
cd prophecy

# Initialize Bible data submodule
git submodule init
git submodule update

# Install Python dependencies
pip install pyyaml openai requests pandas
# OR use conda environment
conda env create -f environment.yml
conda activate prophecy
```

### Quick Start

```python
# Import the main Bible API
from prophecy.bible import Bible

# Initialize with default data folder
bible = Bible()

# Extract the Creation story
creation_text = bible.get_text('Genesis', {'range': '1:1-2:7'})
print(f"Creation story: {len(creation_text.split())} words")

# Load stories from YAML
import yaml
with open('data/stories.yml') as f:
    stories = yaml.safe_load(f)

# Extract a complete story
flood_story = stories['The Great Flood']
flood_text = bible.get_text(flood_story['book'], 
                           {'range': flood_story['verses'][0]})

# Use the Stories API for easier access
from prophecy.stories import Stories
story_api = Stories()
story_text = story_api.get_story_text('The Creation')

# AI-powered analysis (requires OpenAI API key)
from prophecy.ai_providers import ChatGPTProvider
ai = ChatGPTProvider()
analysis = ai.analyze_text(creation_text, "Analyze the tone and themes")
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

- ✅ **Data Layer**: Complete Bible text, story definitions, indexes, and prompts
- ✅ **Story Mapping**: 72+ stories with precise verse ranges
- ✅ **Python Package**: Full object-oriented API with Bible, Stories, Prompts, and AI integration
- ✅ **Testing**: Comprehensive test suite for data integrity and API functionality
- ✅ **Examples**: Working demonstration scripts for all major features
- ✅ **AI Integration**: OpenAI and other AI provider support for text analysis
- 📋 **Documentation**: Ongoing improvements and API reference

## Contributing

Contributions welcome! Areas of interest:

### Data Enhancement
- Additional Hebrew Bible narratives for `stories.yml`
- New sentiment analysis prompts for `prompts.tsv`
- Cross-references between stories
- Alternative biblical translations

### Code Development
- Additional AI provider integrations
- Enhanced text analysis features
- Performance optimizations
- API extensions

### Testing and Documentation
- Additional test coverage
- Documentation improvements
- Example scripts and tutorials
- Integration guides

### Getting Started with Development

1. **Fork and clone the repository**
2. **Set up development environment:**
   ```bash
   git submodule init && git submodule update
   pip install -r requirements.txt  # or use environment.yml
   ```
3. **Run tests to ensure everything works:**
   ```bash
   python -m pytest tests/ -v
   ```
4. **Verify examples work:**
   ```bash
   python examples/bible_api_demo.py
   ```

See individual README files in `data/`, `examples/`, `scripts/`, and `tests/` directories for specific contribution guidelines.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Bible text courtesy of [aruljohn/Bible-kjv](https://github.com/aruljohn/Bible-kjv)
- Story boundaries based on traditional biblical scholarship
- Inspired by narrative approaches to biblical studies
