# Prophecy Examples

This directory contains demonstration scripts showing how to use the Prophecy project's Python API for biblical text analysis and story extraction.

## Available Examples

### 1. `bible_api_demo.py`
Comprehensive demonstration of the Bible API functionality.

**Features demonstrated:**
- Initializing the Bible class
- Extracting text using verse ranges (e.g., `"1:1-2:7"`)
- Multiple verse range extraction
- Dictionary-format verse specification
- Loading stories from `stories.yml`
- Getting book information and statistics
- Environment variable configuration

**Usage:**
```bash
python examples/bible_api_demo.py
```

**Sample output:**
- Creation story extraction (980 words)
- Psalm 23 in full
- The Great Flood narrative (2000+ words)
- Book information (chapter counts)

### 2. `ai_provider_demo.py`
Demonstrates AI-powered biblical text analysis using various AI providers.

**Features demonstrated:**
- Integration with OpenAI ChatGPT
- Sentiment analysis of biblical texts
- AI provider factory pattern
- Error handling for AI interactions
- Analysis of specific biblical passages

**Requirements:**
- OpenAI API key (set as `OPENAI_API_KEY` environment variable)
- Valid AI provider configuration

**Usage:**
```bash
export OPENAI_API_KEY="your-api-key-here"
python examples/ai_provider_demo.py
```

### 3. `prompts_usage_demo.py`
Shows how to use the structured prompts system for biblical text analysis.

**Features demonstrated:**
- Loading prompts from `data/prompts.tsv`
- Filtering prompts by period and topic
- Applying prompts to biblical texts
- Structured analysis workflows

**Usage:**
```bash
python examples/prompts_usage_demo.py
```

## Getting Started

### Prerequisites
1. **Install dependencies:**
   ```bash
   pip install pyyaml openai requests pandas
   ```
   Or use the conda environment:
   ```bash
   conda env create -f environment.yml
   conda activate prophecy
   ```

2. **Verify installation:**
   ```bash
   python examples/bible_api_demo.py
   ```

### Running from Different Directories
All examples are designed to run from the repository root:
```bash
# From repository root
python examples/bible_api_demo.py

# Or with explicit path
cd /path/to/prophecy
python examples/bible_api_demo.py
```

## Example Use Cases

### Academic Research
```python
# Extract complete biblical narratives for analysis
from prophecy.bible import Bible
import yaml

bible = Bible('data')
with open('data/stories.yml') as f:
    stories = yaml.safe_load(f)

# Get the complete creation narrative
creation = stories['The Creation']
text = bible.get_text(creation['book'], {'range': creation['verses'][0]})
```

### Sentiment Analysis
```python
# Analyze emotional content of biblical passages
from prophecy.prompts import Prompts
from prophecy.ai_providers import ChatGPTProvider

prompts = Prompts('data/prompts.tsv')
ai = ChatGPTProvider()

# Get sentiment analysis prompts
sentiment_prompts = prompts.get_prompts_by_topic('sentiment')
```

### Text Mining
```python
# Extract texts for computational analysis
bible = Bible('data')

# Get all psalms of praise for thematic analysis
psalm_texts = []
for i in range(1, 151):  # Psalms 1-150
    try:
        text = bible.get_text('Psalms', {'range': f'{i}:1-{i}:999'})
        psalm_texts.append(text)
    except:
        continue  # Handle psalms with fewer verses
```

## Development and Testing

### Adding New Examples
1. Create a new Python file in the `examples/` directory
2. Follow the existing pattern:
   - Add proper imports and path setup
   - Include comprehensive error handling
   - Provide clear output and explanations
   - Test with the actual data

2. Update this README with documentation for the new example

### Error Handling
All examples include robust error handling for common issues:
- Missing data files
- Invalid verse references
- API key configuration problems
- File permission issues

### Testing Examples
```bash
# Test all examples
for script in examples/*.py; do
    echo "Testing $script"
    python "$script"
done
```

## Troubleshooting

### Common Issues

**"Book file not found" error:**
Ensure you have the Hebrew Bible data files in the `data/hebrew/` directory.

**"No module named 'prophecy'" error:**
```bash
# Run from repository root directory
cd /path/to/prophecy
python examples/bible_api_demo.py
```

**AI provider errors:**
```bash
# Set up OpenAI API key
export OPENAI_API_KEY="your-key-here"
```

**Import errors:**
```bash
# Install required dependencies
pip install pyyaml openai requests pandas
```

## Integration Examples

These examples can be integrated into larger projects:
- **Academic research**: Text corpus preparation and analysis
- **Digital humanities**: Biblical language pattern analysis
- **Educational tools**: Interactive biblical study applications
- **Content analysis**: Sentiment and thematic analysis workflows

For more advanced usage, see the main API documentation in `prophecy/README.md`.