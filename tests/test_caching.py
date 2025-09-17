#!/usr/bin/env python3
"""
Tests for the caching functionality in __main__.py.
"""

import json
import tempfile
import pytest
import logging
from pathlib import Path
from unittest.mock import Mock, patch

import sys
import os

# Add the prophecy module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from prophecy.__main__ import (
    calculate_template_checksum,
    get_cached_result,
    save_cached_result,
    get_cache_folder,
    process_combination
)


class TestCaching:
    """Test class for caching functionality."""
    
    def test_checksum_calculation_deterministic(self):
        """Test that checksum calculation is deterministic."""
        template = "This is a test template with content"
        checksum1 = calculate_template_checksum(template)
        checksum2 = calculate_template_checksum(template)
        
        assert checksum1 == checksum2
        assert len(checksum1) == 32  # MD5 hex string length
        assert isinstance(checksum1, str)
    
    def test_checksum_calculation_different_inputs(self):
        """Test that different templates produce different checksums."""
        template1 = "This is template one"
        template2 = "This is template two"
        
        checksum1 = calculate_template_checksum(template1)
        checksum2 = calculate_template_checksum(template2)
        
        assert checksum1 != checksum2
    
    def test_cache_miss(self):
        """Test cache miss scenario."""
        logger = logging.getLogger('test')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_folder = Path(temp_dir)
            checksum = "nonexistent123"
            
            result = get_cached_result(cache_folder, checksum, logger)
            assert result is None
    
    def test_cache_save_and_hit(self):
        """Test cache save and subsequent hit."""
        logger = logging.getLogger('test')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_folder = Path(temp_dir)
            checksum = "test123abc"
            test_result = {
                "answer": True,
                "reason": "Test reason",
                "certainty": 95,
                "story": "Test Story",
                "prompt": "1"
            }
            
            # Save to cache
            save_cached_result(cache_folder, checksum, test_result, logger)
            
            # Verify file exists
            cache_file = cache_folder / f"{checksum}.json"
            assert cache_file.exists()
            
            # Retrieve from cache
            cached_result = get_cached_result(cache_folder, checksum, logger)
            assert cached_result is not None
            assert cached_result == test_result
    
    def test_cache_invalid_json(self):
        """Test handling of corrupted cache files."""
        logger = logging.getLogger('test')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_folder = Path(temp_dir)
            checksum = "corrupted123"
            cache_file = cache_folder / f"{checksum}.json"
            
            # Create corrupted cache file
            with open(cache_file, 'w') as f:
                f.write("invalid json content {")
            
            # Should return None for corrupted file
            result = get_cached_result(cache_folder, checksum, logger)
            assert result is None
    
    def test_get_cache_folder_default(self):
        """Test default cache folder creation."""
        logger = logging.getLogger('test')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock args without cache_folder
            args = Mock()
            args.cache_folder = None
            
            cache_folder = get_cache_folder(temp_dir, args, logger)
            expected_path = Path(temp_dir) / "results"
            
            assert cache_folder == expected_path
            assert cache_folder.exists()
    
    def test_get_cache_folder_custom(self):
        """Test custom cache folder path."""
        logger = logging.getLogger('test')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_cache = Path(temp_dir) / "custom_cache"
            
            # Mock args with custom cache_folder
            args = Mock()
            args.cache_folder = str(custom_cache)
            
            cache_folder = get_cache_folder("/some/data/folder", args, logger)
            
            assert cache_folder == custom_cache
            assert cache_folder.exists()


if __name__ == "__main__":
    test_instance = TestCaching()
    test_instance.test_checksum_calculation_deterministic()
    test_instance.test_checksum_calculation_different_inputs()
    test_instance.test_cache_miss()
    test_instance.test_cache_save_and_hit()
    test_instance.test_cache_invalid_json()
    test_instance.test_get_cache_folder_default()
    test_instance.test_get_cache_folder_custom()
    print("All caching tests passed!")