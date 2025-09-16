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
from .bible import Bible

# Try to import AI providers (optional if openai not available)
try:
    from .ai_providers import AIProviderFactory, AIProviderError
    AI_PROVIDERS_AVAILABLE = True
except ImportError:
    AI_PROVIDERS_AVAILABLE = False


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


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description='Extract biblical stories, populate prompts, and get AI responses',
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
    
    parser.add_argument(
        '--ai-provider',
        default='chatgpt',
        choices=['chatgpt', 'openai'],
        help='AI provider to use (default: chatgpt)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show populated templates without sending to AI provider'
    )
    
    return parser


def setup_environment(args) -> None:
    """Set up environment variables from command line arguments."""
    if args.data:
        os.environ['PROPHECY_DATA_FOLDER'] = args.data
    
    if args.api_key:
        os.environ['OPENAI_API_KEY'] = args.api_key


def initialize_components(data_folder: str):
    """Initialize Stories, Prompts, and Bible components."""
    try:
        stories = Stories(data_folder=data_folder)
        prompts = Prompts(data_folder=data_folder)
        bible = Bible(data_folder=data_folder)
        return stories, prompts, bible
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Please ensure the data folder contains stories.yml, prompts.tsv, and bible data", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing data: {e}", file=sys.stderr)
        sys.exit(1)


def validate_inputs(stories, prompts, args):
    """Validate story and prompt arguments, return lists of items to process."""
    try:
        story_titles = validate_story_arg(stories, args.stories)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        prompt_list = validate_prompt_arg(prompts, args.prompt)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    return story_titles, prompt_list


def initialize_ai_provider(args):
    """Initialize AI provider if not in dry-run mode."""
    if args.dry_run:
        return None
    
    if not AI_PROVIDERS_AVAILABLE:
        print("Error: AI providers not available. Install 'openai' package or use --dry-run", file=sys.stderr)
        sys.exit(1)
    
    try:
        ai_provider = AIProviderFactory.create_provider(
            args.ai_provider,
            api_key=args.api_key or os.getenv('OPENAI_API_KEY')
        )
        
        if not ai_provider.validate_configuration():
            print("Error: AI provider configuration is invalid", file=sys.stderr)
            sys.exit(1)
        
        return ai_provider
        
    except (ValueError, AIProviderError) as e:
        print(f"Error: Failed to initialize AI provider: {e}", file=sys.stderr)
        if "API key" in str(e):
            print("Make sure to set OPENAI_API_KEY environment variable or use --api-key", file=sys.stderr)
        sys.exit(1)


def get_biblical_text(bible, story):
    """Get biblical text for a story, with fallback for missing data."""
    try:
        return bible.get_text(story.book, *story.to_bible_parts())
    except Exception as e:
        print(f"Warning: Could not get biblical text for {story.title}: {e}", file=sys.stderr)
        return f"[Biblical text not available for {story.book}]"


def process_combination(prompts, story, prompt_record, biblical_text, ai_provider, is_dry_run):
    """Process a single story-prompt combination."""
    # Populate template
    try:
        populated_template = prompts.populate_template(prompt_record, story, biblical_text)
    except Exception as e:
        print(f"Error: Failed to populate template: {e}", file=sys.stderr)
        return False
    
    if is_dry_run:
        # Just show the populated template
        print("=== POPULATED TEMPLATE ===")
        print(populated_template)
        print("=" * 50)
        print()
    else:
        # Send to AI provider and get response
        try:
            print("Sending to AI provider...")
            ai_response = ai_provider.post_prompt(
                populated_template,
                system_message="You are a biblical scholar analyzing ancient texts."
            )
            
            print("=== AI RESPONSE ===")
            print(ai_response)
            print("=" * 50)
            print()
            
        except AIProviderError as e:
            print(f"Error: AI provider failed: {e}", file=sys.stderr)
            print("Skipping this combination...", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error: Unexpected AI error: {e}", file=sys.stderr)
            print("Skipping this combination...", file=sys.stderr)
            return False
    
    return True


def process_all_combinations(stories, prompts, bible, story_titles, prompt_list, ai_provider, args):
    """Process all story-prompt combinations."""
    print(f"=== Prophecy Processing ===")
    print(f"Stories: {len(story_titles)}")
    print(f"Prompts: {len(prompt_list)}")
    print(f"Mode: {'Dry run' if args.dry_run else f'AI Provider: {args.ai_provider}'}")
    print()
    
    total_combinations = len(story_titles) * len(prompt_list)
    current_combination = 0
    
    for story_title in story_titles:
        story = stories.get_story(story_title)
        biblical_text = get_biblical_text(bible, story)
        
        for prompt_record in prompt_list:
            current_combination += 1
            
            print(f"--- Combination {current_combination}/{total_combinations} ---")
            print(f"Story: {story.title} ({story.book})")
            print(f"Prompt: #{prompt_record['id']} - {prompt_record['prompt']}")
            print()
            
            process_combination(prompts, story, prompt_record, biblical_text, ai_provider, args.dry_run)
    
    print(f"=== Processing Complete ===")
    print(f"Processed {current_combination} story-prompt combinations")


def main():
    """Main CLI entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    try:
        setup_environment(args)
        stories, prompts, bible = initialize_components(args.data)
        story_titles, prompt_list = validate_inputs(stories, prompts, args)
        ai_provider = initialize_ai_provider(args)
        process_all_combinations(stories, prompts, bible, story_titles, prompt_list, ai_provider, args)
    
    except KeyboardInterrupt:
        print("\nAborted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()