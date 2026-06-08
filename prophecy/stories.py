"""
Stories class for the Prophecy project.

This module provides the Stories class for accessing biblical stories from a
stories YAML file (``data/stories/stories.yml`` by default; configurable via
Settings).
"""

import re
from pathlib import Path

import yaml

from .settings import Settings


class _StoriesYamlLoader(yaml.SafeLoader):
    """SafeLoader without YAML 1.1's sexagesimal int resolver.

    PyYAML defaults to YAML 1.1, which interprets unquoted ``N:N`` scalars as
    base-60 integers (so ``- 1:7`` silently becomes ``67``). Our verse refs
    are always ``chapter:verse[-chapter:verse]`` strings, never sexagesimal
    numbers, so we strip that branch from the int resolver and leave the rest
    of safe-loader behavior untouched.
    """


# A standard YAML-1.2-style int resolver: binary, octal, decimal, hex — no
# sexagesimal branch.
_NON_SEXAGESIMAL_INT_RE = re.compile(
    r"""^(?:
        [-+]?0b[0-1_]+
        | [-+]?0[0-7_]+
        | [-+]?(?:0 | [1-9][0-9_]*)
        | [-+]?0x[0-9a-fA-F_]+
    )$""",
    re.VERBOSE,
)


def _install_non_sexagesimal_int_resolver() -> None:
    """Replace the inherited int resolvers on _StoriesYamlLoader with sexagesimal-free ones.

    Implicit resolvers are class-level dicts keyed by leading character. We
    copy SafeLoader's table once (so we don't mutate the parent), drop every
    ``tag:yaml.org,2002:int`` entry, and register the replacement for the
    same set of leading characters PyYAML registers ints under.
    """
    _StoriesYamlLoader.yaml_implicit_resolvers = {
        key: [(tag, regex) for tag, regex in resolvers if tag != "tag:yaml.org,2002:int"]
        for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    _StoriesYamlLoader.add_implicit_resolver(
        "tag:yaml.org,2002:int", _NON_SEXAGESIMAL_INT_RE, list("-+0123456789")
    )


_install_non_sexagesimal_int_resolver()


class Stories:
    """
    A class for accessing biblical stories from a stories YAML file.

    Files live in ``data/stories/`` by default (configurable via
    ``Settings.stories_folder``). The active catalog is normally
    ``stories.yml``, but the filename is overridable via
    ``Settings.stories_file`` or ``Stories(stories_file=...)`` so callers can
    swap in alternative catalogs like ``stories-according-to-source.yml``.
    """

    def __init__(
        self,
        data_folder: str | Path | None = None,
        stories_file: str | Path | None = None,
        stories_folder: str | Path | None = None,
    ):
        """
        Initialize the Stories class.

        Args:
            data_folder: Path to the data folder. If None, falls back to
                ``Settings.load()``.
            stories_file: Name of the stories YAML file. Resolved against
                ``stories_folder`` if relative, used as-is if absolute.
                If None, falls back to ``Settings.load().stories_file``.
            stories_folder: Subfolder under ``data_folder`` holding the
                stories YAML files (default ``stories``). If None, falls
                back to ``Settings.load().stories_folder``.
        """
        # Route everything through Settings.load so resolution rules stay in
        # one place and explicit kwargs continue to win over env / toml.
        settings = Settings.load(
            data_folder=data_folder,
            stories_file=stories_file,
            stories_folder=stories_folder,
        )
        self.data_folder = settings.data_folder
        self.stories_folder = settings.resolve_stories_folder()
        self.stories_path = settings.resolve_stories_path()

        if not self.data_folder.exists():
            raise FileNotFoundError(f"Data folder not found: {self.data_folder}")

        if not self.stories_path.exists():
            raise FileNotFoundError(f"Stories file not found: {self.stories_path}")

        with open(self.stories_path, encoding="utf-8") as f:
            self._stories_data = yaml.load(f, Loader=_StoriesYamlLoader)

        if not isinstance(self._stories_data, dict):
            raise ValueError(
                f"Invalid stories file format ({self.stories_path}): "
                "expected dictionary at root level"
            )

    @property
    def titles(self) -> list[str]:
        """
        Get a list of all story titles.

        Returns:
            Sorted list of story titles
        """
        return sorted(self._stories_data.keys())

    def get_story(self, title: str) -> "Story":
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
            available_titles = ", ".join(self.titles)
            raise ValueError(f"Story '{title}' not found. Available stories: {available_titles}")

        story_data = self._stories_data[title]
        return Story(title, story_data)


class Story:
    """
    Represents a single biblical story with its metadata.

    Stories always carry a title, book, and verse ranges. They may also
    carry an optional ``sources`` list — currently free-form strings used
    for cataloging (e.g. documentary-hypothesis source markers like "E",
    "P", "J"); the schema is expected to harden over time.
    """

    def __init__(self, title: str, story_data: dict):
        """
        Initialize a Story object.

        Args:
            title: The title of the story
            story_data: Dictionary containing 'book' and 'verses' keys,
                and an optional 'sources' key (list of strings).

        Raises:
            ValueError: If story_data is missing required fields
        """
        if not isinstance(story_data, dict):
            raise ValueError(f"Story data for '{title}' must be a dictionary")

        if "book" not in story_data:
            raise ValueError(f"Story '{title}' missing 'book' field")

        if "verses" not in story_data:
            raise ValueError(f"Story '{title}' missing 'verses' field")

        if not isinstance(story_data["verses"], list):
            raise ValueError(f"Story '{title}' verses field must be a list")

        sources = story_data.get("sources", [])
        if not isinstance(sources, list):
            raise ValueError(f"Story '{title}' sources field must be a list")
        for s in sources:
            if not isinstance(s, str):
                raise ValueError(f"Story '{title}' sources entries must be strings")

        self._title = title
        self._book = story_data["book"]
        self._verses = story_data["verses"]
        self._sources: list[str] = list(sources)

    @property
    def title(self) -> str:
        """Get the story title."""
        return self._title

    @property
    def book(self) -> str:
        """Get the book name for this story."""
        return self._book

    @property
    def verses(self) -> list[str]:
        """Get the list of verse ranges for this story."""
        return self._verses.copy()  # Return a copy to prevent modification

    @property
    def sources(self) -> list[str]:
        """Optional source tags for this story (empty list if none declared)."""
        return self._sources.copy()

    def to_bible_parts(self) -> list[dict[str, str]]:
        """
        Convert the story's verse ranges to Bible.get_text() compatible format.

        Returns:
            List of dictionaries with 'range' keys suitable for Bible.get_text()

        Example:
            >>> story = Story("The Creation", {"book": "Genesis", "verses": ["1:1-2:7"]})
            >>> story.to_bible_parts()
            [{'range': '1:1-2:7'}]
        """
        return [{"range": verse_range} for verse_range in self._verses]

    def __repr__(self) -> str:
        """String representation of the story."""
        return f"Story(title='{self._title}', book='{self._book}', verse_count={len(self._verses)})"

    def __str__(self) -> str:
        """Human-readable string representation."""
        verses_str = ", ".join(self._verses)
        return f"{self._title} ({self._book} {verses_str})"
