# 📜 Prophecy: LLM-based content analysis of the TeNaKh

A Python toolkit for analyzing biblical texts, extracting stories, and working with structured biblical data. This project provides programmatic access to the Bible organized by stories rather than just chapters and verses.

## Overview

The Prophecy project bridges the gap between traditional biblical organization (books, chapters, verses) and narrative structure (stories, themes, characters). It enables researchers, developers, and biblical scholars to work with biblical texts as coherent narratives rather than fragmented verse collections.

## Key Features

- **Story-based Biblical Text Access**: Extract complete biblical narratives spanning multiple chapters
- **Comprehensive Story Index**: 72+ major Hebrew Bible stories with precise verse ranges
- **Structured Data Format**: JSON-based Bible text with chapter/verse organization
- **Book Indexes**: Index of Hebrew Bible books from the Hebrew Masoretic text
- **Flexible Text Extraction**: Retrieve stories by name, book, or custom verse ranges
- **Clean Python API**: Object-oriented modules for easy integration
- **AI Integration**: Built-in support for OpenAI and other AI providers for text analysis
- **Sentiment Analysis**: Curated prompts for biblical text sentiment analysis
- **Comprehensive Testing**: Full test suite ensuring data integrity and API reliability

## Project Structure

```
prophecy/
├── data/
│   ├── hebrew/                   # Hebrew Masoretic text JSON files
│   ├── stories.yml               # Story definitions with verse ranges
│   ├── prompts.tsv               # Sentiment analysis prompts
│   ├── index.json                # Hebrew Bible book index
│   └── template.txt              # AI prompt template
├── prophecy/                     # Python package
│   ├── __init__.py               # Package initialization
│   ├── __main__.py               # `python -m prophecy` CLI entry point
│   ├── bible.py                  # Bible text access classes
│   ├── stories.py                # Story extraction and analysis
│   ├── prompts.py                # Prompts management
│   ├── settings.py               # Layered config (defaults / TOML / env)
│   └── ai_providers.py           # AI integration (OpenAI, Anthropic, …)
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

- **Bible Text**: Hebrew Masoretic text from [Westminster Leningrad Codex](https://github.com/openscriptures/morphhb)
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

Clone the repository:

```bash
git clone https://github.com/rvosa/prophecy.git
cd prophecy
```

Pick one of three install paths — all of them install the same dependency
graph from `pyproject.toml`:

### With [uv](https://github.com/astral-sh/uv) (recommended)

```bash
uv sync --extra dev
```

This creates a `.venv`, installs the package in editable mode, and pulls
in the dev tooling (pytest, ruff, pyright). All commands below can be run
with `uv run <cmd>`.

### With conda

```bash
conda env create -f environment.yml
conda activate prophecy
```

### With plain pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

`prophecy.settings.Settings` is a small dataclass that resolves config
from layered sources, highest precedence first:

```
explicit kwargs  >  PROPHECY_* env vars  >  ./prophecy.toml  >  defaults
```

For a one-off override, just export an env var:

```bash
export PROPHECY_DATA_FOLDER=/path/to/data
python -m prophecy --dry-run
```

For project-local config, create `prophecy.toml` in the repo root
(it's gitignored):

```toml
data_folder = "data"
cache_folder = "results"
```

API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) are deliberately *not*
managed by `Settings` — providers read them from the environment so
secrets don't end up in TOML files.

## Quick Start

```python
from prophecy import Bible, Stories

# Bible text by book + verse range
bible = Bible()
creation = bible.get_text("Genesis", {"range": "1:1-2:7"})
print(f"Creation story: {len(creation.split())} words")

# Or via the higher-level Stories API
stories = Stories()
flood = stories.get_story("The Great Flood")
flood_text = bible.get_text(flood.book, *flood.to_bible_parts())

# AI-powered analysis (requires OPENAI_API_KEY)
from prophecy import ChatGPTProvider
ai = ChatGPTProvider()
analysis = ai.post_prompt(
    f"Analyze the tone and themes:\n\n{creation}",
    system_message="You are a biblical scholar.",
)
```

To run the full story × prompt × LLM pipeline, use the CLI:

```bash
# Dry run — prints the populated template, no API calls
uv run python -m prophecy --stories "The Creation" --prompt 1 --dry-run

# Real run — caches results in data/results/<md5>.json
uv run python -m prophecy --stories "The Creation" --prompt 1
```

## Story Coverage

Currently includes 72+ major Hebrew Bible narratives:

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

1. **Fork and clone the repository.**
2. **Set up the dev environment** (see the install paths above —
   `uv sync --extra dev` is the fastest).
3. **Run the test, lint, and typecheck pipeline locally before
   pushing:**
   ```bash
   uv run pytest          # 194 tests
   uv run ruff check      # linter
   uv run ruff format     # auto-formatter
   uv run pyright         # type checker
   ```
4. **Verify the demo scripts still work:**
   ```bash
   uv run python examples/bible_api_demo.py
   ```

CI runs three jobs on every push and PR to `main`:

- `test-conda` — original miniconda flow (preserved for the project's
  conda users).
- `test-uv` — same dependency graph via uv, fast feedback on PRs.
- `lint` — `ruff check`, `ruff format --check`, and `pyright`.

See individual README files in `data/`, `examples/`, `scripts/`, and `tests/` directories for specific contribution guidelines.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Bible text from the Westminster Leningrad Codex via [Open Scriptures Hebrew Bible](https://github.com/openscriptures/morphhb)
- Story boundaries based on traditional biblical scholarship
- Inspired by narrative approaches to biblical studies
