#!/usr/bin/env python3
"""
Test module to verify the structure of data/stories.yml against requirements.

Requirements being tested:
1. Every top-level entry is the title of a bible story
2. Each story has a 'book' field that must occur in data/index.json
3. Each story has a 'verses' field containing a list
4. Each verses list element follows format: 'chapter:verse-chapter:verse' 
5. All chapters and verses must exist in the specified book's JSON file
"""

import json
import os
import pytest
import re
import yaml
from pathlib import Path


class TestStoriesStructure:
    """Test class for validating data/stories.yml structure."""
    
    @pytest.fixture(scope="class")
    def data_path(self):
        """Get the path to the data directory."""
        return Path(__file__).parent.parent / "data"
    
    @pytest.fixture(scope="class")
    def stories_data(self, data_path):
        """Load the stories.yml file."""
        stories_file = data_path / "stories.yml"
        assert stories_file.exists(), f"stories.yml not found at {stories_file}"
        
        with open(stories_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    @pytest.fixture(scope="class")
    def index(self, data_path):
        """Load the index.json index file."""
        ot_file = data_path / "index.json"
        assert ot_file.exists(), f"index.json not found at {ot_file}"
        
        with open(ot_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @pytest.fixture(scope="class")
    def bible_books_cache(self, data_path, index):
        """Cache bible book data to avoid repeated file reads."""
        cache = {}
        for book_name, book_path in index.items():
            full_path = data_path.parent / book_path
            if full_path.exists():
                with open(full_path, 'r', encoding='utf-8') as f:
                    cache[book_name] = json.load(f)
        return cache
    
    def test_stories_file_loads_successfully(self, stories_data):
        """Test that stories.yml loads without errors."""
        assert stories_data is not None
        assert isinstance(stories_data, dict)
    
    def test_stories_are_top_level_entries(self, stories_data):
        """Test that every top-level entry represents a bible story title."""
        assert len(stories_data) > 0, "No stories found in stories.yml"
        
        # Each top-level key should be a string (story title)
        for story_title in stories_data.keys():
            assert isinstance(story_title, str), f"Story title '{story_title}' is not a string"
            assert len(story_title.strip()) > 0, f"Story title '{story_title}' is empty or whitespace"
    
    def test_each_story_has_required_fields(self, stories_data):
        """Test that each story has required 'book' and 'verses' fields."""
        for story_title, story_data in stories_data.items():
            assert isinstance(story_data, dict), f"Story '{story_title}' data is not a dictionary"
            
            # Check 'book' field exists
            assert 'book' in story_data, f"Story '{story_title}' missing 'book' field"
            assert isinstance(story_data['book'], str), f"Story '{story_title}' book field is not a string"
            assert len(story_data['book'].strip()) > 0, f"Story '{story_title}' has empty book field"
            
            # Check 'verses' field exists and is a list
            assert 'verses' in story_data, f"Story '{story_title}' missing 'verses' field"
            assert isinstance(story_data['verses'], list), f"Story '{story_title}' verses field is not a list"
            assert len(story_data['verses']) > 0, f"Story '{story_title}' has empty verses list"
    
    def test_book_references_exist_in_index(self, stories_data, index):
        """Test that all book references exist in data/index.json."""
        for story_title, story_data in stories_data.items():
            book_name = story_data['book']
            assert book_name in index, \
                f"Story '{story_title}' references book '{book_name}' not found in index.json. " \
                f"Available books: {list(index.keys())}"
    
    def test_verses_format_is_valid(self, stories_data):
        """Test that verses follow the format 'chapter:verse-chapter:verse'."""
        verse_pattern = re.compile(r'^\d+:\d+-\d+:\d+$')
        
        for story_title, story_data in stories_data.items():
            verses = story_data['verses']
            
            for i, verse_range in enumerate(verses):
                assert isinstance(verse_range, str), \
                    f"Story '{story_title}' verse {i} is not a string: {verse_range}"
                
                # Check format matches pattern
                assert verse_pattern.match(verse_range), \
                    f"Story '{story_title}' verse {i} '{verse_range}' does not match format 'chapter:verse-chapter:verse'"
    
    def test_verse_ranges_exist_in_bible_books(self, stories_data, bible_books_cache):
        """Test that all chapter:verse references exist in the actual bible book files."""
        for story_title, story_data in stories_data.items():
            book_name = story_data['book']
            
            # Skip if book data not available (will be caught by other test)
            if book_name not in bible_books_cache:
                continue
            
            book_data = bible_books_cache[book_name]
            verses = story_data['verses']
            
            for verse_range in verses:
                # Parse the verse range (e.g., "1:1-2:7")
                start_ref, end_ref = verse_range.split('-')
                start_chapter, start_verse = map(int, start_ref.split(':'))
                end_chapter, end_verse = map(int, end_ref.split(':'))
                
                # Validate start reference
                self._validate_verse_reference(
                    story_title, book_name, book_data, 
                    start_chapter, start_verse, verse_range, "start"
                )
                
                # Validate end reference
                self._validate_verse_reference(
                    story_title, book_name, book_data, 
                    end_chapter, end_verse, verse_range, "end"
                )
                
                # Validate that start <= end (logically)
                assert (start_chapter < end_chapter) or (start_chapter == end_chapter and start_verse <= end_verse), \
                    f"Story '{story_title}' verse range '{verse_range}' has invalid order (start > end)"
    
    def _validate_verse_reference(self, story_title, book_name, book_data, chapter_num, verse_num, verse_range, position):
        """Helper method to validate a single chapter:verse reference."""
        # Find the chapter
        chapters = book_data.get('chapters', [])
        chapter = None
        for ch in chapters:
            if int(ch['chapter']) == chapter_num:
                chapter = ch
                break
        
        assert chapter is not None, \
            f"Story '{story_title}' ({position} of '{verse_range}'): Chapter {chapter_num} not found in book '{book_name}'. " \
            f"Available chapters: {[int(ch['chapter']) for ch in chapters]}"
        
        # Find the verse
        verses_list = chapter.get('verses', [])
        verse = None
        for v in verses_list:
            if int(v['verse']) == verse_num:
                verse = v
                break
        
        assert verse is not None, \
            f"Story '{story_title}' ({position} of '{verse_range}'): Verse {verse_num} not found in chapter {chapter_num} of book '{book_name}'. " \
            f"Available verses: {[int(v['verse']) for v in verses_list]}"
    
    def test_stories_yaml_format_consistency(self, stories_data):
        """Test additional format consistency requirements."""
        for story_title, story_data in stories_data.items():
            # Ensure no unexpected fields
            expected_fields = {'book', 'verses'}
            actual_fields = set(story_data.keys())
            unexpected = actual_fields - expected_fields
            assert len(unexpected) == 0, \
                f"Story '{story_title}' has unexpected fields: {unexpected}"
    
    def test_comprehensive_stories_coverage(self, stories_data, index):
        """Test that stories reference a reasonable variety of Hebrew Bible books."""
        referenced_books = set()
        for story_data in stories_data.values():
            referenced_books.add(story_data['book'])
        
        # Should reference at least 10 different books (reasonable for bible stories)
        assert len(referenced_books) >= 10, \
            f"Stories only reference {len(referenced_books)} different books. Expected at least 10. " \
            f"Referenced books: {sorted(referenced_books)}"
        
        # All referenced books should be from the Hebrew Bible
        for book in referenced_books:
            assert book in index, \
                f"Referenced book '{book}' not in Hebrew Bible index"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
