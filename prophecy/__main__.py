#!/usr/bin/env python3
"""
Prophecy command-line interface.

This module provides a CLI for extracting biblical stories and prompts.
"""

import argparse
import os
import sys
from typing import List, Dict, Any

# Import modules directly to avoid dependency issues
from .stories import Stories
from .prompts import Prompts


def validate_story_arg(stories_obj: Stories, stories_arg: str) -> List[str]:
    """
    Validate and return list of story titles based on argument.
    
    Args:
        stories_obj: Stories instance
        stories_arg: Either 'all' or a specific story title
        
    Returns:
        List of story titles to process
        
    Raises:
        ValueError: If story title is not found
    """
    if stories_arg == 'all':
        return stories_obj.titles
    else:
        # Validate the story exists
        if stories_arg not in stories_obj.titles:
            available = ', '.join(stories_obj.titles[:10])
            if len(stories_obj.titles) > 10:
                available += f', ... ({len(stories_obj.titles)} total)'
            raise ValueError(f"Story '{stories_arg}' not found. Available stories: {available}")
        return [stories_arg]


def validate_prompt_arg(prompts_obj: Prompts, prompt_arg: str) -> List[Dict[str, str]]:
    """
    Validate and return list of prompts based on argument.
    
    Args:
        prompts_obj: Prompts instance
        prompt_arg: Either 'all' or a specific prompt ID
        
    Returns:
        List of prompt dictionaries to process
        
    Raises:
        ValueError: If prompt ID is not found
    """
    if prompt_arg == 'all':
        return prompts_obj.get_prompts()
    else:
        # Validate the prompt ID exists and get the prompt
        prompt = prompts_obj.get_prompt_by_id(prompt_arg)
        return [prompt]


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Extract biblical stories and prompts',
        prog='python -m prophecy'
    )
    
    parser.add_argument(
        '--stories',
        default='all',
        help='Story to extract: either a specific story title or "all" (default: all)'
    )
    
    parser.add_argument(
        '--prompt',
        default='all',
        help='Prompt to use: either a specific prompt ID or "all" (default: all)'
    )
    
    parser.add_argument(
        '--data',
        help='Path to data folder (overrides PROPHECY_DATA_FOLDER environment variable)'
    )
    
    parser.add_argument(
        '--api-key',
        help='API key for AI services (overrides OPENAI_API_KEY environment variable)'
    )
    
    args = parser.parse_args()
    
    try:
        # Set up environment variables if provided
        if args.data:
            os.environ['PROPHECY_DATA_FOLDER'] = args.data
        
        if args.api_key:
            os.environ['OPENAI_API_KEY'] = args.api_key
        
        # Initialize Stories and Prompts
        try:
            stories = Stories(data_folder=args.data)
            prompts = Prompts(data_folder=args.data)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            print("Please ensure the data folder contains stories.yml and prompts.tsv", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error initializing data: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Validate and get stories
        try:
            story_titles = validate_story_arg(stories, args.stories)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Validate and get prompts
        try:
            prompt_list = validate_prompt_arg(prompts, args.prompt)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Extract and output stories and prompts
        print(f"=== Prophecy Extraction ===")
        print(f"Stories: {len(story_titles)}")
        print(f"Prompts: {len(prompt_list)}")
        print()
        
        # Output stories
        print("=== STORIES ===")
        for i, story_title in enumerate(story_titles, 1):
            story = stories.get_story(story_title)
            print(f"{i}. {story}")
            
        print()
        
        # Output prompts
        print("=== PROMPTS ===")
        for i, prompt in enumerate(prompt_list, 1):
            print(f"{i}. ID: {prompt['id']}")
            print(f"   Period: {prompt['period']}")
            print(f"   Topic: {prompt['topic']}")
            print(f"   Prompt: {prompt['prompt']}")
            print()
    
    except KeyboardInterrupt:
        print("\nAborted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()