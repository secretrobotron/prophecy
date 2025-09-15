# Prophecy Python API

The Prophecy Python package provides programmatic access to biblical texts with a focus on story-based extraction rather than just chapter and verse access. The package includes multiple APIs for different use cases: Bible text access, story management, AI-powered analysis, and sentiment analysis prompts.

## Installation

The package is included in this repository. To use it, ensure dependencies are installed:

```bash
pip install pyyaml openai requests pandas
# OR use conda environment
conda env create -f environment.yml
conda activate prophecy
```

## Quick Start

```python
from prophecy import Bible, Stories, ChatGPTProvider

# Initialize Bible API
bible = Bible()

# Extract text from Genesis creation story
creation_text = bible.get_text('Genesis', {'range': '1:1-2:7'})

# Use Stories API for easier story access
stories = Stories()
story = stories.get_story('The Creation')
print(f"Story: {story.title}")
print(f"Book: {story.book}")
print(f"Verses: {story.verses}")

# Get story text directly
story_text = stories.get_story_text('The Creation')

# AI-powered analysis (requires OpenAI API key)
ai = ChatGPTProvider()
analysis = ai.analyze_text(creation_text, "Analyze the literary themes")
```

## API Reference

### Bible Class

The core API for accessing biblical texts by book and verse ranges.

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

### Stories Class

High-level API for accessing biblical stories defined in `stories.yml`.

#### Constructor

```python
Stories(data_folder=None)
```

**Parameters:**
- `data_folder` (str, optional): Path to the data folder. Defaults to `'data'`.

#### Methods

##### get_story(story_title)

Get a Story object for the specified story.

**Parameters:**
- `story_title` (str): The title of the story (e.g., 'The Creation')

**Returns:**
- `Story`: Story object with title, book, and verses properties

##### get_story_text(story_title)

Get the complete text for a story.

**Parameters:**
- `story_title` (str): The title of the story

**Returns:**
- `str`: Complete story text

##### get_available_stories()

Get a list of all available story titles.

**Returns:**
- `List[str]`: List of story titles

### Story Class

Represents a single biblical story.

#### Properties

- `title` (str): The story title
- `book` (str): The biblical book containing the story
- `verses` (List[str]): List of verse ranges for the story

### AI Provider Classes

Support for AI-powered biblical text analysis.

#### ChatGPTProvider

```python
from prophecy import ChatGPTProvider

# Initialize (requires OPENAI_API_KEY environment variable)
ai = ChatGPTProvider()

# Analyze text
result = ai.analyze_text(text, prompt)
```

#### AIProviderFactory

Factory for creating AI provider instances:

```python
from prophecy import AIProviderFactory

provider = AIProviderFactory.create_provider('chatgpt')
```

### Prompts Class

Access to sentiment analysis prompts from `prompts.tsv`.

```python
from prophecy.prompts import Prompts

prompts = Prompts()
sentiment_prompts = prompts.get_prompts_by_topic('sentiment')
```

## Usage Examples

### Basic Bible Text Extraction

```python
from prophecy import Bible

bible = Bible()

# Single verse
verse = bible.get_text('Genesis', {'range': '1:1-1:1'})
print(verse)  # "In the beginning God created the heaven and the earth."

# Multiple verses in one range
creation = bible.get_text('Genesis', {'range': '1:1-1:5'})

# Cross-chapter range
text = bible.get_text('Genesis', {'range': '1:31-2:3'})

# Multiple separate ranges
highlights = bible.get_text('Genesis', 
                           {'range': '1:1-1:3'},    # Creation beginning
                           {'range': '1:26-1:28'})  # Creation of man

# Dictionary format for verse specification
psalm23 = bible.get_text('Psalms', {
    'start_chapter': 23,
    'start_verse': 1,
    'end_chapter': 23,
    'end_verse': 6
})
```

### Story-Based Access

```python
from prophecy import Stories

stories = Stories()

# Get story information
story = stories.get_story('The Creation')
print(f"Title: {story.title}")
print(f"Book: {story.book}")
print(f"Verses: {story.verses}")

# Get story text directly
creation_text = stories.get_story_text('The Creation')
flood_text = stories.get_story_text('The Great Flood')

# List all available stories
all_stories = stories.get_available_stories()
print(f"Available stories: {len(all_stories)}")
```

### AI-Powered Analysis

```python
import os
from prophecy import Bible, ChatGPTProvider

# Set up OpenAI API key
os.environ['OPENAI_API_KEY'] = 'your-api-key-here'

bible = Bible()
ai = ChatGPTProvider()

# Extract text and analyze
text = bible.get_text('Genesis', {'range': '1:1-2:7'})
analysis = ai.analyze_text(text, "Analyze the literary themes and tone")
print(analysis)

# Sentiment analysis
sentiment = ai.analyze_text(text, "What is the emotional tone of this passage?")
```

### Prompts System

```python
from prophecy.prompts import Prompts

prompts = Prompts()

# Get prompts by topic
sentiment_prompts = prompts.get_prompts_by_topic('sentiment')
thematic_prompts = prompts.get_prompts_by_topic('theme')

# Get prompts by period
ancient_prompts = prompts.get_prompts_by_period('ancient')

# Use with AI analysis
for prompt_data in sentiment_prompts:
    result = ai.analyze_text(text, prompt_data['prompt'])
    print(f"Analysis using {prompt_data['id']}: {result}")
```

## Features

- **Story-based text extraction**: Extract complete narratives spanning multiple chapters using the Stories API
- **Flexible verse range specification**: Use either range strings or dictionary format
- **Multiple part concatenation**: Combine text from different verse ranges
- **Proper text spacing**: Automatically handles spacing between sentences and parts
- **Book caching**: Efficiently caches loaded books to avoid repeated file reads
- **Environment variable support**: Configure data folder via `PROPHECY_DATA_FOLDER`
- **Comprehensive error handling**: Clear error messages for invalid inputs
- **AI Integration**: Built-in support for OpenAI and other AI providers
- **Sentiment Analysis**: Structured prompts system for biblical text analysis
- **High-level APIs**: Multiple interfaces for different use cases (Bible, Stories, Prompts)

## Data Structure

The package expects the following data structure:

```
data/
├── index.json              # Maps book names to file paths
├── stories.yml             # Story definitions with verse ranges  
├── prompts.tsv             # Sentiment analysis prompts
└── bible-kjv/             # Directory containing Bible book files
    ├── Genesis.json
    ├── Exodus.json
    └── ...
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

### Stories YAML Format
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

## Error Handling

The package provides clear error messages for common issues:

- **Invalid book names**: Lists available books when a book isn't found
- **Invalid verse ranges**: Validates format and verse existence
- **Missing files**: Clear messages when data files are missing
- **Invalid parameters**: Helpful messages for incorrect function calls
- **API key issues**: Clear guidance for AI provider setup

## Examples and Documentation

### Example Scripts
- `examples/bible_api_demo.py` - Comprehensive Bible API demonstration
- `examples/ai_provider_demo.py` - AI-powered analysis examples
- `examples/prompts_usage_demo.py` - Prompts system demonstration

### Additional Documentation
- `data/README.md` - Data structure and sources documentation
- `examples/README.md` - Detailed example script documentation
- `scripts/README.md` - Utility script documentation

## Testing

Run the test suite:

```bash
# All tests
python -m pytest tests/ -v

# Specific test modules
python -m pytest tests/test_bible.py -v
python -m pytest tests/test_stories_structure.py -v
python -m pytest tests/test_prompts.py -v

# AI provider tests (requires API keys)
python -m pytest tests/test_ai_providers.py -v
```

The tests include:
- Unit tests with mock data
- Integration tests with real Bible data
- Data integrity validation
- API functionality verification
- AI provider integration tests