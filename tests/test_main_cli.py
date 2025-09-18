#!/usr/bin/env python3
"""
Tests for the main CLI functionality, especially edge cases around argument handling.
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock, patch

# Add the prophecy module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from prophecy.__main__ import (
    initialize_components,
    get_cache_folder,
    create_argument_parser,
    setup_logging,
    setup_environment
)


class TestMainCLI:
    """Test class for main CLI functionality."""
    
    def test_initialize_components_with_none_data_folder(self):
        """Test that initialize_components handles None data_folder correctly."""
        logger = logging.getLogger('test')
        
        # This should not raise an exception and should resolve data_folder
        stories, prompts, bible, data_folder = initialize_components(None, logger)
        
        # Should resolve to default value
        assert data_folder == 'data'
        assert stories is not None
        assert prompts is not None
        assert bible is not None
    
    def test_initialize_components_with_explicit_data_folder(self):
        """Test that initialize_components preserves explicit data_folder."""
        logger = logging.getLogger('test')
        
        explicit_path = 'data'
        stories, prompts, bible, data_folder = initialize_components(explicit_path, logger)
        
        # Should preserve the explicit value
        assert data_folder == explicit_path
        assert stories is not None
        assert prompts is not None
        assert bible is not None
    
    def test_get_cache_folder_no_type_error(self):
        """Test that get_cache_folder doesn't raise TypeError when given resolved path."""
        logger = logging.getLogger('test')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            args = Mock()
            args.cache_folder = None
            
            # This should not raise TypeError - this was the original bug
            cache_folder = get_cache_folder(temp_dir, args, logger)
            expected_path = Path(temp_dir) / "results"
            
            assert cache_folder == expected_path
            assert cache_folder.exists()
    
    def test_cli_argument_parsing_no_data(self):
        """Test CLI argument parsing when --data is not provided."""
        # Mock sys.argv to simulate no --data argument
        test_argv = ['prophecy', '--stories', 'The Creation', '--prompt', '1']
        
        with patch.object(sys, 'argv', test_argv):
            parser = create_argument_parser()
            args = parser.parse_args()
            
            # args.data should be None when not provided
            assert args.data is None
            assert args.stories == 'The Creation'
            assert args.prompt == '1'
    
    def test_end_to_end_no_data_argument_flow(self):
        """Test the complete flow that previously caused TypeError."""
        test_argv = ['prophecy', '--stories', 'The Creation', '--prompt', '1']
        
        with patch.object(sys, 'argv', test_argv):
            parser = create_argument_parser()
            args = parser.parse_args()
            logger = setup_logging('ERROR')  # Reduce log noise
            
            # This sequence previously caused TypeError at get_cache_folder
            setup_environment(args)
            stories, prompts, bible, data_folder = initialize_components(args.data, logger)
            
            # Simulate the non-dry-run path that calls get_cache_folder
            args.cache_folder = None
            cache_folder = get_cache_folder(data_folder, args, logger)
            
            # Should succeed without TypeError
            assert data_folder == 'data'
            assert cache_folder == Path('data') / 'results'
    
    def test_data_folder_resolution_with_env_var(self):
        """Test data folder resolution with environment variable."""
        logger = logging.getLogger('test')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a minimal data structure
            data_path = Path(temp_dir) / 'test_data'
            data_path.mkdir()
            
            # Create required files for the test
            (data_path / 'stories.yml').write_text('test_story:\n  book: Genesis\n  verses: ["1:1"]')
            (data_path / 'prompts.tsv').write_text('id\tprompt\tperiod\ttopic\n1\ttest prompt\ttest\ttest')
            (data_path / 'template.txt').write_text('Test template')
            (data_path / 'index.json').write_text('{}')
            
            # Test with environment variable
            with patch.dict(os.environ, {'PROPHECY_DATA_FOLDER': str(data_path)}):
                stories, prompts, bible, data_folder = initialize_components(None, logger)
                assert data_folder == str(data_path)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, '-v'])