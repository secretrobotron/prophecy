"""
Prophecy: Python toolkit for biblical text analysis and story extraction.

A Python package for programmatic access to biblical texts organized by stories
rather than just chapters and verses.
"""

from .bible import Bible
from .stories import Stories, Story

__version__ = "0.1.0"
__all__ = ["Bible", "Stories", "Story"]