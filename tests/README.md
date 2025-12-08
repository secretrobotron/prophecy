# Prophecy Tests

This directory contains comprehensive pytest tests to validate the functionality, structure, and content of the prophecy project.

## Test Files

### Core API Tests

#### test_bible.py
Tests for the Bible class API functionality:
- Bible initialization and configuration
- Text extraction from various verse ranges
- Error handling for invalid inputs
- Book information retrieval
- Caching behavior
- Environment variable configuration

#### test_stories.py
Tests for the Stories and Story classes:
- Story loading from YAML files
- Story text extraction
- Story metadata access
- Integration with Bible API

#### test_ai_providers.py
Tests for AI provider integration:
- ChatGPT provider functionality
- AI provider factory pattern
- Error handling for API issues
- Text analysis capabilities
- Configuration management

#### test_prompts_class.py
Tests for the Prompts class:
- Prompts loading from TSV files
- Filtering by topic and period
- Data structure validation
- Integration with AI providers

#### test_create_sources.py
Tests for the `scripts/create_sources.py` functionality:
- **Text cleaning**: Validates removal of special characters and whitespace normalization
- **Regex validation**: Tests the `RANGE_TOKEN` pattern for valid verse ranges
- **Bullet parsing**: Tests extraction of book names, verse ranges, and source tags (J/E/P/D)
- **Range normalization**: Verifies proper space handling, duplicate removal, and format standardization
- **Bible integration**: Tests that parsed ranges work directly with the Bible class
- **Format compatibility**: Validates conversion from terse ranges ("1:1-7") to standard format ("1:1-1:7")
- **Special formatting**: Tests handling of verse suffixes like "4b"
- **Error handling**: Ensures invalid ranges and malformed input are properly handled

### Data Integrity Tests

#### test_stories_structure.py
Comprehensive validation of `data/stories.yml`:
1. **YAML Structure Validation**
   - File loads successfully as valid YAML
   - Story entries have required fields (`book`, `verses`)
   - Story titles are valid strings

2. **Book Reference Validation**
   - All book references exist in `data/index.json`
   - Book names are properly formatted

3. **Verse Format Validation**
   - Verses follow format: `chapter:verse-chapter:verse`
   - All elements are valid integers
   - Verse ranges are logically valid (start ≤ end)

4. **Bible Data Integration**
   - Referenced chapters exist in Bible JSON files
   - Referenced verses exist in specified chapters
   - Data consistency between stories.yml and Bible data

#### test_prompts.py
Validation of `data/prompts.tsv` structure and content:
1. **File Format Validation**
   - File exists and is accessible
   - Proper tab-separated format with four columns
   - Consistent column count across all rows

2. **Header Validation**
   - Headers are exactly: `id`, `period`, `topic`, `prompt`
   - Headers are in correct order

3. **Data Integrity**
   - All ID values are unique
   - No empty cells in required columns
   - Valid data types and formats

4. **Content Validation**
   - Reasonable amount of data
   - Consistent delimiter usage
   - Valid prompt content

## Running Tests

### Run All Tests
```bash
# All tests with verbose output
pytest -v

# All tests with coverage report
pytest --cov=prophecy tests/

# Run tests in parallel (if pytest-xdist is installed)
pytest -n auto
```

### Run Specific Test Categories
```bash
# Core API tests
pytest tests/test_bible.py tests/test_stories.py tests/test_prompts_class.py tests/test_create_sources.py -v

# Data integrity tests
pytest tests/test_stories_structure.py tests/test_prompts.py -v

# AI provider tests (requires API keys)
pytest tests/test_ai_providers.py -v

# Create sources script validation
pytest tests/test_create_sources.py -v
```

### Run Individual Test Files
```bash
# Bible API tests
pytest tests/test_bible.py -v

# Stories structure validation
pytest tests/test_stories_structure.py -v

# Prompts data validation
pytest tests/test_prompts.py -v

# Create sources script tests
pytest tests/test_create_sources.py -v
```

### Run Specific Test Methods
```bash
# Test specific functionality
pytest tests/test_bible.py::TestBible::test_get_text_with_range_string -v

# Test specific data validation
pytest tests/test_stories_structure.py::TestStoriesStructure::test_verses_format_is_valid -v
```

## Test Requirements

The tests require the following Python packages:
- **pytest** - Testing framework
- **pyyaml** - YAML file processing
- **beautifulsoup4** - HTML parsing (for create_sources tests)
- **requests** - HTTP requests (for AI provider and create_sources tests)
- **openai** - AI provider integration (for AI tests)
- **pandas** - Data processing (for prompts tests)

Install all dependencies:
```bash
pip install pytest pyyaml beautifulsoup4 requests openai pandas
# OR use the project environment
conda env create -f environment.yml
conda activate prophecy
```

## Test Configuration

Tests are configured in `setup.cfg`:
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

## Test Coverage Areas

### Data Validation
- ✅ YAML structure and format validation
- ✅ TSV file format and content validation  
- ✅ Bible JSON data integrity
- ✅ Cross-reference validation between data files
- ✅ Verse range format validation
- ✅ Script output validation (create_sources.py)

### API Functionality
- ✅ Bible text extraction with various input formats
- ✅ Story loading and text retrieval
- ✅ Prompts system functionality
- ✅ AI provider integration
- ✅ Error handling and edge cases
- ✅ Script parsing and range normalization

### Integration Testing
- ✅ End-to-end workflows
- ✅ Data consistency across modules
- ✅ Environment configuration
- ✅ File system operations
- ✅ Scripture source assignment validation

## Continuous Integration

Tests are designed to work in CI environments:
- No external dependencies for core tests
- Clear separation of unit and integration tests
- Configurable test environments
- Comprehensive error reporting

## Troubleshooting Tests

### Common Issues

**Missing dependencies:**
```bash
pip install -r requirements.txt
# OR install individual packages as needed
```

**Missing data files:**
Ensure you have the Hebrew Bible data files in the `data/hebrew/` directory.

**AI provider test failures:**
```bash
# Set up API keys for AI tests
export OPENAI_API_KEY="your-key-here"
```

**Permission errors:**
```bash
# Ensure proper file permissions
chmod -R 755 data/
```

## Adding New Tests

### Guidelines for New Tests

1. **Naming Convention**
   - Use descriptive test method names starting with `test_`
   - Group related tests in classes starting with `Test`
   - Use clear, self-documenting names

2. **Test Structure**
   ```python
   def test_specific_functionality_description(self):
       """Test description explaining what is being tested."""
       # Arrange
       setup_code()
       
       # Act
       result = function_under_test()
       
       # Assert
       assert result == expected_value, "Clear error message"
   ```

3. **Error Handling**
   - Test both success and failure cases
   - Verify appropriate exceptions are raised
   - Include clear assertion messages

4. **Data Management**
   - Use fixtures for shared test data
   - Clean up temporary files
   - Use mock data when appropriate

5. **Documentation**
   - Document test purpose and requirements
   - Update this README when adding new test files
   - Include examples of expected behavior

### Example Test Addition

```python
# tests/test_new_feature.py
import pytest
from prophecy.new_feature import NewFeature

class TestNewFeature:
    def test_new_feature_initialization(self):
        """Test that NewFeature initializes correctly."""
        feature = NewFeature()
        assert feature is not None
        assert hasattr(feature, 'expected_attribute')
    
    def test_new_feature_with_invalid_input(self):
        """Test that NewFeature handles invalid input appropriately."""
        with pytest.raises(ValueError, match="Expected error message"):
            NewFeature(invalid_parameter=True)
```