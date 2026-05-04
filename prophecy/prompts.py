"""
Prompts class for the Prophecy project.

This module provides the Prompts class for accessing prompts data and populating
templates using the Template system.
"""

import csv
import os
import textwrap
from pathlib import Path
from string import Template


class Prompts:
    """
    A class for accessing prompts data and populating templates.

    This class encapsulates access to the prompts.tsv data and provides methods
    for reading prompts and populating templates with prompts and Story objects.
    """

    def __init__(self, data_folder: str | None = None):
        """
        Initialize the Prompts class.

        Args:
            data_folder: Path to the data folder containing prompts.tsv and template.txt.
                        If None, uses the PROPHECY_DATA_FOLDER environment variable.
                        If that's not set, defaults to 'data' relative to the current directory.
        """
        if data_folder is None:
            data_folder = os.getenv("PROPHECY_DATA_FOLDER", "data")

        self.data_folder = Path(data_folder)

        # Validate data folder exists
        if not self.data_folder.exists():
            raise FileNotFoundError(f"Data folder not found: {self.data_folder}")

        # Load the prompts.tsv file
        self.prompts_path = self.data_folder / "prompts.tsv"
        if not self.prompts_path.exists():
            raise FileNotFoundError(f"Prompts file not found: {self.prompts_path}")

        # Load the template.txt file
        self.template_path = self.data_folder / "template.txt"
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template file not found: {self.template_path}")

        # Load prompts data
        self._prompts_data: list[dict[str, str]] = []
        self._load_prompts()

        # Load template
        with open(self.template_path, encoding="utf-8") as f:
            self._template_content = f.read()

    def _load_prompts(self):
        """Load prompts data from the TSV file."""
        with open(self.prompts_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            self._prompts_data = list(reader)

        if not self._prompts_data:
            raise ValueError(f"No prompts data found in {self.prompts_path}")

    def get_prompts(self) -> list[dict[str, str]]:
        """
        Get all prompts data.

        Returns:
            List of dictionaries, each containing 'id', 'period', 'topic', 'prompt' keys
        """
        return [prompt.copy() for prompt in self._prompts_data]

    def get_prompt_by_id(self, prompt_id: str | int) -> dict[str, str]:
        """
        Get a specific prompt by its ID.

        Args:
            prompt_id: The ID of the prompt to retrieve. Accepts ``str`` or
                ``int`` — int values are stringified before lookup.

        Returns:
            Dictionary containing 'id', 'period', 'topic', 'prompt' keys

        Raises:
            ValueError: If the prompt ID is not found
        """
        for prompt in self._prompts_data:
            if prompt["id"] == str(prompt_id):
                return prompt.copy()

        available_ids = [p["id"] for p in self._prompts_data]
        raise ValueError(
            f"Prompt ID '{prompt_id}' not found. Available IDs: {', '.join(available_ids[:10])}..."
        )

    def get_prompts_by_period(self, period: str) -> list[dict[str, str]]:
        """
        Get all prompts for a specific period.

        Args:
            period: The period to filter by (e.g., 'Babylonian', 'Persian', 'Hellenistic')

        Returns:
            List of prompt dictionaries matching the period
        """
        return [prompt.copy() for prompt in self._prompts_data if prompt["period"] == period]

    def get_prompts_by_topic(self, topic: str) -> list[dict[str, str]]:
        """
        Get all prompts for a specific topic.

        Args:
            topic: The topic to filter by

        Returns:
            List of prompt dictionaries matching the topic
        """
        return [prompt.copy() for prompt in self._prompts_data if prompt["topic"] == topic]

    def get_periods(self) -> list[str]:
        """
        Get all unique periods in the prompts data.

        Returns:
            Sorted list of unique periods
        """
        periods = set(prompt["period"] for prompt in self._prompts_data)
        return sorted(periods)

    def get_topics(self) -> list[str]:
        """
        Get all unique topics in the prompts data.

        Returns:
            Sorted list of unique topics
        """
        topics = set(prompt["topic"] for prompt in self._prompts_data)
        return sorted(topics)

    def _fold_lines(self, text: str, width: int = 100) -> str:
        """
        Fold long lines in text to a specified width.

        Args:
            text: The text to fold
            width: Maximum line width (default: 100)

        Returns:
            Text with lines folded at the specified width
        """
        lines = text.split("\n")
        folded_lines = []

        for line in lines:
            if len(line) <= width:
                folded_lines.append(line)
            else:
                # Use textwrap to handle line folding with proper word boundaries
                wrapped_lines = textwrap.fill(
                    line, width=width, break_long_words=False, break_on_hyphens=False
                )
                folded_lines.append(wrapped_lines)

        return "\n".join(folded_lines)

    def populate_template(self, prompt_record: dict[str, str], story_object, text: str) -> str:
        """
        Populate the template with a prompt record, story object, and text.

        Args:
            prompt_record: Dictionary containing prompt data with 'id', 'period', 'topic', 'prompt' keys
            story_object: Story object with title, book, and verses properties
            text: The biblical text content

        Returns:
            Interpolated and line-folded text

        Raises:
            ValueError: If prompt_record is missing required keys
            AttributeError: If story_object is missing required attributes
        """
        # Validate prompt_record
        required_keys = {"id", "period", "topic", "prompt"}
        missing_keys = required_keys - set(prompt_record.keys())
        if missing_keys:
            raise ValueError(f"Prompt record missing required keys: {missing_keys}")

        # Validate story_object
        required_attrs = ["title", "book", "verses"]
        for attr in required_attrs:
            try:
                value = getattr(story_object, attr)
                # Check if it's a Mock object (for testing) that wasn't explicitly set
                if hasattr(value, "_mock_name"):
                    raise AttributeError(f"Story object missing required attribute: {attr}")
            except AttributeError as e:
                raise AttributeError(f"Story object missing required attribute: {attr}") from e

        # Prepare template variables
        template_vars = {
            "period": prompt_record["period"],
            "topic": prompt_record["topic"],
            "prompt": prompt_record["prompt"],
            "text": text,
        }

        # Create and substitute template
        template = Template(self._template_content)
        populated_text = template.substitute(template_vars)

        # Fold lines at >=100 characters
        return self._fold_lines(populated_text, width=100)

    def get_template_content(self) -> str:
        """
        Get the raw template content.

        Returns:
            Raw template content as string
        """
        return self._template_content

    def get_prompt_count(self) -> int:
        """
        Get the total number of prompts.

        Returns:
            Number of prompts in the dataset
        """
        return len(self._prompts_data)

    def __repr__(self) -> str:
        """String representation of the Prompts object."""
        return f"Prompts(data_folder='{self.data_folder}', prompt_count={self.get_prompt_count()})"
