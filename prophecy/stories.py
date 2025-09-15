"""
Stories class for the Prophecy project.

This module provides the Stories class for accessing biblical stories from the stories.yml data.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Union


class Stories:
    """
    A class for accessing biblical stories from the stories.yml data.
    
    This class encapsulates access to the stories data and provides properties
    for extracting story information including title, book, and verse ranges.
    """
    
    def __init__(self, data_folder: Optional[str] = None):
        """
        Initialize the Stories class.
        
        Args:
            data_folder: Path to the data folder containing stories.yml.
                        If None, uses the PROPHECY_DATA_FOLDER environment variable.
                        If that's not set, defaults to 'data' relative to the current directory.
        """
        if data_folder is None:
            data_folder = os.getenv('PROPHECY_DATA_FOLDER', 'data')
        
        self.data_folder = Path(data_folder)
        
        # Validate data folder exists
        if not self.data_folder.exists():
            raise FileNotFoundError(f"Data folder not found: {self.data_folder}")
        
        # Load the stories.yml file
        self.stories_path = self.data_folder / 'stories.yml'
        if not self.stories_path.exists():
            raise FileNotFoundError(f"Stories file not found: {self.stories_path}")
        
        with open(self.stories_path, 'r', encoding='utf-8') as f:
            self._stories_data = yaml.safe_load(f)
        
        if not isinstance(self._stories_data, dict):
            raise ValueError(f"Invalid stories.yml format: expected dictionary at root level")
    
    @property
    def titles(self) -> List[str]:
        """
        Get a list of all story titles.
        
        Returns:
            Sorted list of story titles
        """
        return sorted(self._stories_data.keys())
    
    def get_story(self, title: str) -> 'Story':
        """
        Get a Story object for the specified title.
        
        Args:
            title: The title of the story
        
        Returns:
            Story object
        
        Raises:
            ValueError: If the story title is not found
        """
        if title not in self._stories_data:
            available_titles = ', '.join(self.titles)
            raise ValueError(f"Story '{title}' not found. Available stories: {available_titles}")
        
        story_data = self._stories_data[title]
        return Story(title, story_data)


class Story:
    """
    Represents a single biblical story with its metadata.
    
    This class provides access to individual story properties including
    title, book, and verse ranges.
    """
    
    def __init__(self, title: str, story_data: Dict):
        """
        Initialize a Story object.
        
        Args:
            title: The title of the story
            story_data: Dictionary containing 'book' and 'verses' keys
        
        Raises:
            ValueError: If story_data is missing required fields
        """
        if not isinstance(story_data, dict):
            raise ValueError(f"Story data for '{title}' must be a dictionary")
        
        if 'book' not in story_data:
            raise ValueError(f"Story '{title}' missing 'book' field")
        
        if 'verses' not in story_data:
            raise ValueError(f"Story '{title}' missing 'verses' field")
        
        if not isinstance(story_data['verses'], list):
            raise ValueError(f"Story '{title}' verses field must be a list")
        
        self._title = title
        self._book = story_data['book']
        self._verses = story_data['verses']
    
    @property
    def title(self) -> str:
        """Get the story title."""
        return self._title
    
    @property
    def book(self) -> str:
        """Get the book name for this story."""
        return self._book
    
    @property
    def verses(self) -> List[str]:
        """Get the list of verse ranges for this story."""
        return self._verses.copy()  # Return a copy to prevent modification
    
    def to_bible_parts(self) -> List[Dict[str, str]]:
        """
        Convert the story's verse ranges to Bible.get_text() compatible format.
        
        Returns:
            List of dictionaries with 'range' keys suitable for Bible.get_text()
        
        Example:
            >>> story = Story("The Creation", {"book": "Genesis", "verses": ["1:1-2:7"]})
            >>> story.to_bible_parts()
            [{'range': '1:1-2:7'}]
        """
        return [{'range': verse_range} for verse_range in self._verses]
    
    def __repr__(self) -> str:
        """String representation of the story."""
        return f"Story(title='{self._title}', book='{self._book}', verse_count={len(self._verses)})"
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        verses_str = ', '.join(self._verses)
        return f"{self._title} ({self._book} {verses_str})"