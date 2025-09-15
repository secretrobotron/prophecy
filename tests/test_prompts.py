#!/usr/bin/env python3
"""
Test module to verify the structure and content of data/prompts.tsv.

Requirements being tested:
1. File must be tab-separated data with exactly four columns
2. Headers should be 'id', 'period', 'topic', and 'prompt'
3. Values in the 'id' column should be unique within the file
"""

import csv
import os
import pytest
from pathlib import Path


class TestPromptsStructure:
    """Test class for validating data/prompts.tsv structure."""
    
    @pytest.fixture(scope="class")
    def data_path(self):
        """Get the path to the data directory."""
        return Path(__file__).parent.parent / "data"
    
    @pytest.fixture(scope="class")
    def prompts_file(self, data_path):
        """Get the path to the prompts.tsv file."""
        prompts_file = data_path / "prompts.tsv"
        assert prompts_file.exists(), f"prompts.tsv not found at {prompts_file}"
        return prompts_file
    
    @pytest.fixture(scope="class")
    def prompts_data(self, prompts_file):
        """Load the prompts.tsv file as a list of rows."""
        rows = []
        with open(prompts_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                rows.append(row)
        return rows
    
    def test_prompts_file_exists(self, prompts_file):
        """Test that prompts.tsv file exists."""
        assert prompts_file.exists(), "prompts.tsv file should exist in data directory"
    
    def test_file_is_tab_separated_with_four_columns(self, prompts_data):
        """Test that the file is tab-separated and has exactly four columns in every row."""
        assert len(prompts_data) > 0, "File should not be empty"
        
        for i, row in enumerate(prompts_data):
            assert len(row) == 4, \
                f"Row {i+1} has {len(row)} columns, expected exactly 4. Row content: {row}"
    
    def test_headers_are_correct(self, prompts_data):
        """Test that the file has the correct headers: id, period, topic, prompt."""
        assert len(prompts_data) > 0, "File should not be empty"
        
        expected_headers = ['id', 'period', 'topic', 'prompt']
        actual_headers = prompts_data[0]
        
        assert actual_headers == expected_headers, \
            f"Headers should be {expected_headers}, but found {actual_headers}"
    
    def test_id_values_are_unique(self, prompts_data):
        """Test that all values in the 'id' column are unique."""
        assert len(prompts_data) > 1, "File should have at least header + data rows"
        
        # Skip header row (index 0)
        data_rows = prompts_data[1:]
        
        # Extract all id values (first column)
        id_values = [row[0] for row in data_rows if row]  # Skip empty rows
        
        # Check for uniqueness
        unique_ids = set(id_values)
        
        assert len(id_values) == len(unique_ids), \
            f"Found {len(id_values)} IDs but only {len(unique_ids)} unique values. " \
            f"Duplicate IDs detected."
        
        # Additional check: find and report duplicates if any
        if len(id_values) != len(unique_ids):
            seen = set()
            duplicates = set()
            for id_val in id_values:
                if id_val in seen:
                    duplicates.add(id_val)
                seen.add(id_val)
            
            pytest.fail(f"Duplicate ID values found: {sorted(duplicates)}")
    
    def test_no_empty_cells_in_required_columns(self, prompts_data):
        """Test that there are no empty cells in any of the four required columns."""
        assert len(prompts_data) > 1, "File should have at least header + data rows"
        
        # Skip header row (index 0)
        data_rows = prompts_data[1:]
        
        for i, row in enumerate(data_rows):
            if not row:  # Skip completely empty rows
                continue
            
            row_num = i + 2  # +2 because we skipped header and 0-indexed
            
            # Check each column is non-empty
            for col_idx, (col_name, cell_value) in enumerate(zip(['id', 'period', 'topic', 'prompt'], row)):
                assert cell_value and cell_value.strip(), \
                    f"Row {row_num}, column '{col_name}' (index {col_idx}) is empty or whitespace-only"
    
    def test_id_values_are_valid_format(self, prompts_data):
        """Test that ID values follow a reasonable format (non-empty strings)."""
        assert len(prompts_data) > 1, "File should have at least header + data rows"
        
        # Skip header row (index 0)
        data_rows = prompts_data[1:]
        
        for i, row in enumerate(data_rows):
            if not row:  # Skip completely empty rows
                continue
            
            row_num = i + 2  # +2 because we skipped header and 0-indexed
            id_value = row[0]
            
            # ID should be a non-empty string
            assert isinstance(id_value, str), \
                f"Row {row_num}: ID value should be a string, got {type(id_value)}: {id_value}"
            
            assert id_value.strip(), \
                f"Row {row_num}: ID value should not be empty or whitespace-only: '{id_value}'"
    
    def test_file_has_reasonable_amount_of_data(self, prompts_data):
        """Test that the file contains a reasonable amount of data (at least some rows)."""
        # Should have header + at least 1 data row
        assert len(prompts_data) >= 2, \
            f"File should have at least header + 1 data row, found {len(prompts_data)} rows total"
        
        # Count non-empty data rows
        data_rows = [row for row in prompts_data[1:] if row and any(cell.strip() for cell in row)]
        
        assert len(data_rows) >= 1, \
            "File should have at least 1 non-empty data row"
    
    def test_tab_separation_consistency(self, prompts_file):
        """Test that the file uses consistent tab separation (no mixed delimiters)."""
        with open(prompts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        assert len(non_empty_lines) > 0, "File should have at least one non-empty line"
        
        for i, line in enumerate(non_empty_lines):
            line_num = i + 1
            
            # Check that tabs are present (for separation)
            tab_count = line.count('\t')
            
            # Should have exactly 3 tabs for 4 columns
            assert tab_count == 3, \
                f"Line {line_num} should have exactly 3 tabs for 4 columns, found {tab_count} tabs. " \
                f"Line content: '{line[:100]}...'"
            
            # Check that other common delimiters are not being used as primary separators
            # (they might exist within cell content, but not as primary separators)
            if ',' in line and '\t' in line:
                # If both exist, tabs should be the primary delimiter
                parts_by_tab = line.split('\t')
                parts_by_comma = line.split(',')
                
                # Tab separation should give us exactly 4 parts
                assert len(parts_by_tab) == 4, \
                    f"Line {line_num}: Tab separation should give 4 columns, got {len(parts_by_tab)}"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])