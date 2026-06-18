"""
Prompts class for the Prophecy project.

This module provides the Prompts class for accessing prompts data and populating
templates using the Template system.
"""

import csv
import logging
import textwrap
from pathlib import Path
from string import Template
from typing import Any

from .settings import Settings

logger = logging.getLogger(__name__)


class Prompts:
    """
    A class for accessing prompts data and populating templates.

    This class encapsulates access to the prompts.tsv data and provides methods
    for reading prompts and populating templates with prompts and Story objects.
    """

    def __init__(
        self,
        data_folder: str | Path | None = None,
        prompts_folder: str | Path | None = None,
    ):
        """
        Initialize the Prompts class.

        Args:
            data_folder: Path to the data folder. If None, falls back to
                ``Settings.load()``.
            prompts_folder: Subfolder under ``data_folder`` containing one
                or more ``prompts*.tsv`` files plus ``template.txt``.
                Default ``prompts``. If None, falls back to
                ``Settings.load().prompts_folder``.

        Contributors can keep topical prompt sets in their own files
        (e.g. ``prompts.politics.tsv``, ``prompts.persian.tsv``). All
        ``prompts*.tsv`` files in the folder are merged on load — IDs
        must be globally unique across the set. At least one file with
        at least one data row is required.
        """
        settings = Settings.load(
            data_folder=data_folder,
            prompts_folder=prompts_folder,
        )
        self.data_folder = settings.data_folder
        self.prompts_folder = settings.resolve_prompts_folder()

        if not self.data_folder.exists():
            raise FileNotFoundError(f"Data folder not found: {self.data_folder}")
        if not self.prompts_folder.exists():
            raise FileNotFoundError(f"Prompts folder not found: {self.prompts_folder}")

        self.prompts_paths: list[Path] = self._discover_prompt_files()
        if not self.prompts_paths:
            raise FileNotFoundError(f"No prompts*.tsv files found in {self.prompts_folder}")
        # Backwards-compat alias: callers that used to read .prompts_path
        # (the singular "main" file) get the first discovered file. New
        # code should iterate .prompts_paths instead.
        self.prompts_path = self.prompts_paths[0]

        # Load the template.txt file
        self.template_path = self.prompts_folder / "template.txt"
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template file not found: {self.template_path}")

        # Load prompts data. Rows are TSV dicts: id/category/topic/prompt are
        # always strings; the optional ``weight`` field is ``int`` when the
        # TSV provides a value or ``None`` when blank/missing. Typed as
        # ``Any`` here so the union doesn't cascade through every accessor.
        self._prompts_data: list[dict[str, Any]] = []
        self._load_prompts()

        # Load template
        with open(self.template_path, encoding="utf-8") as f:
            self._template_content = f.read()

    def _discover_prompt_files(self) -> list[Path]:
        """Return every ``prompts*.tsv`` in the folder, sorted by name.

        Sort key is the filename so the ID-uniqueness check fires
        deterministically and error messages stay reproducible. The bare
        ``prompts.tsv`` (no infix) naturally sorts before any
        ``prompts.<name>.tsv`` because '.' < any letter.
        """
        return sorted(self.prompts_folder.glob("prompts*.tsv"))

    def _load_prompts(self):
        """Load and merge prompts data from every discovered TSV, enforcing global ID uniqueness.

        The optional ``weight`` column is parsed if present. A blank cell or
        a missing column resolves to ``None`` (no explicit weight). Resolution
        from ``None`` to an effective numeric weight happens in
        :meth:`get_effective_weights`, where the per-topic policy lives.
        """
        merged: list[dict[str, Any]] = []
        id_origin: dict[str, Path] = {}
        for path in self.prompts_paths:
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                rows = list(reader)
            for row in rows:
                prompt_id = row.get("id", "")
                if prompt_id in id_origin:
                    raise ValueError(
                        f"Duplicate prompt id '{prompt_id}' in {path} "
                        f"(already defined in {id_origin[prompt_id]})"
                    )
                id_origin[prompt_id] = path
                raw_weight = (row.get("weight") or "").strip()
                if raw_weight == "":
                    parsed_weight: int | None = None
                else:
                    try:
                        parsed_weight = int(raw_weight)
                    except ValueError as e:
                        raise ValueError(
                            f"Invalid weight '{raw_weight}' for prompt id "
                            f"'{prompt_id}' in {path}: must be an integer or blank"
                        ) from e
                    if parsed_weight < 0:
                        raise ValueError(
                            f"Negative weight {parsed_weight} for prompt id "
                            f"'{prompt_id}' in {path}: weights must be >= 0"
                        )
                row["weight"] = parsed_weight
                merged.append(row)

        if not merged:
            raise ValueError(
                f"No prompts data found in {', '.join(str(p) for p in self.prompts_paths)}"
            )
        self._prompts_data = merged
        self._warn_partial_weight_topics()

    def _warn_partial_weight_topics(self) -> None:
        """Log one WARN block per topic that has weights on *some* but not all prompts.

        Mixed topics get a weighted rate, but prompts without an explicit weight
        contribute nothing (effective weight 0) — surface them so a missing weight
        doesn't quietly drop the prompt from the score.
        """
        from collections import defaultdict

        by_topic: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for p in self._prompts_data:
            by_topic[(p.get("category", ""), p.get("topic", ""))].append(p)

        for (category, topic), prompts in by_topic.items():
            weighted = [p for p in prompts if p.get("weight") is not None]
            unweighted = [p for p in prompts if p.get("weight") is None]
            if not weighted or not unweighted:
                continue  # fully weighted or fully unweighted — both are clean
            listing = "\n".join(
                f"    {p.get('id', '?'):>8}  {p.get('prompt', '')}" for p in unweighted
            )
            logger.warning(
                f"Topic {category!r}/{topic!r} has weights but "
                f"{len(unweighted)} of {len(prompts)} prompts are unweighted "
                f"(will contribute weight=0 to the weighted score):\n{listing}"
            )

    def get_effective_weights(self) -> dict[str, float]:
        """Resolve each prompt id to its effective numeric weight.

        Per-topic policy:
          * Topic has zero explicit weights → uniform ``1.0`` for every prompt
            in that topic (fully-unweighted fallback; identical to plain
            counting).
          * Topic has at least one explicit weight → prompts without an
            explicit weight resolve to ``0.0`` (they don't contribute to the
            weighted score). :meth:`_warn_partial_weight_topics` already
            warned about these at load time.
        """
        from collections import defaultdict

        by_topic: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for p in self._prompts_data:
            by_topic[(p.get("category", ""), p.get("topic", ""))].append(p)

        out: dict[str, float] = {}
        for prompts in by_topic.values():
            any_weighted = any(p.get("weight") is not None for p in prompts)
            for p in prompts:
                w = p.get("weight")
                if w is None:
                    out[p["id"]] = 0.0 if any_weighted else 1.0
                else:
                    out[p["id"]] = float(w)
        return out

    def get_prompts(self) -> list[dict[str, str]]:
        """
        Get all prompts data.

        Returns:
            List of dictionaries, each containing 'id', 'category', 'topic', 'prompt' keys
        """
        return [prompt.copy() for prompt in self._prompts_data]

    def get_prompt_by_id(self, prompt_id: str | int) -> dict[str, str]:
        """
        Get a specific prompt by its ID.

        Args:
            prompt_id: The ID of the prompt to retrieve. Accepts ``str`` or
                ``int`` — int values are stringified before lookup.

        Returns:
            Dictionary containing 'id', 'category', 'topic', 'prompt' keys

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

    def get_prompts_by_category(self, category: str) -> list[dict[str, str]]:
        """
        Get all prompts for a specific category.

        Args:
            category: The category to filter by (e.g., 'Babylonian', 'Persian', 'Hellenistic')

        Returns:
            List of prompt dictionaries matching the category
        """
        return [prompt.copy() for prompt in self._prompts_data if prompt["category"] == category]

    def get_prompts_by_topic(self, topic: str) -> list[dict[str, str]]:
        """
        Get all prompts for a specific topic.

        Args:
            topic: The topic to filter by

        Returns:
            List of prompt dictionaries matching the topic
        """
        return [prompt.copy() for prompt in self._prompts_data if prompt["topic"] == topic]

    def filter(
        self,
        category: str | list[str] | None = None,
        topic: str | list[str] | None = None,
    ) -> list[dict[str, str]]:
        """
        Get prompts narrowed by category and/or topic.

        Args:
            category: If set, keep only prompts whose category matches. May be a
                single string or a list of strings (any-of match).
            topic: If set, keep only prompts whose topic matches. Same shape
                rules as ``category``.

        Returns:
            List of prompt dictionaries matching the filters (intersection
            across category and topic, any-of within each filter).
            With no filters set, returns all prompts.
        """
        results = [prompt.copy() for prompt in self._prompts_data]
        if category is not None:
            category_set = {category} if isinstance(category, str) else set(category)
            results = [p for p in results if p["category"] in category_set]
        if topic is not None:
            topic_set = {topic} if isinstance(topic, str) else set(topic)
            results = [p for p in results if p["topic"] in topic_set]
        return results

    def get_categories(self) -> list[str]:
        """
        Get all unique categories in the prompts data.

        Returns:
            Sorted list of unique categories
        """
        categories = set(prompt["category"] for prompt in self._prompts_data)
        return sorted(categories)

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
            prompt_record: Dictionary containing prompt data with 'id', 'category', 'topic', 'prompt' keys
            story_object: Story object with title, book, and verses properties
            text: The biblical text content

        Returns:
            Interpolated and line-folded text

        Raises:
            ValueError: If prompt_record is missing required keys
            AttributeError: If story_object is missing required attributes
        """
        # Validate prompt_record
        required_keys = {"id", "category", "topic", "prompt"}
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
            "category": prompt_record["category"],
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
