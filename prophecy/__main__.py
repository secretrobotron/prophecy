#!/usr/bin/env python3
"""
Prophecy command-line interface.

This module provides a CLI for extracting biblical stories and prompts.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from .bible import Bible
from .prompts import Prompts

# Import modules directly to avoid dependency issues
from .stories import Stories

# Try to import AI providers (optional if openai not available)
try:
    from .ai_providers import AIProviderError, AIProviderFactory

    AI_PROVIDERS_AVAILABLE = True
except ImportError:
    AI_PROVIDERS_AVAILABLE = False


def validate_story_arg(stories_obj: Stories, stories_arg: str) -> list[str]:
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
    if stories_arg == "all":
        return stories_obj.titles
    else:
        # Validate the story exists
        if stories_arg not in stories_obj.titles:
            available = ", ".join(stories_obj.titles[:10])
            if len(stories_obj.titles) > 10:
                available += f", ... ({len(stories_obj.titles)} total)"
            raise ValueError(f"Story '{stories_arg}' not found. Available stories: {available}")
        return [stories_arg]


def validate_prompt_arg(prompts_obj: Prompts, prompt_arg: str) -> list[dict[str, str]]:
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
    if prompt_arg == "all":
        return prompts_obj.get_prompts()
    else:
        # Validate the prompt ID exists and get the prompt
        prompt = prompts_obj.get_prompt_by_id(prompt_arg)
        return [prompt]


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract biblical stories, populate prompts, and get AI responses",
        prog="python -m prophecy",
    )

    parser.add_argument(
        "--stories",
        default="all",
        help='Story to extract: either a specific story title or "all" (default: all)',
    )

    parser.add_argument(
        "--prompt",
        default="all",
        help='Prompt to use: either a specific prompt ID or "all" (default: all)',
    )

    parser.add_argument(
        "--data", help="Path to data folder (overrides PROPHECY_DATA_FOLDER environment variable)"
    )

    parser.add_argument(
        "--api-key", help="API key for AI services (overrides OPENAI_API_KEY environment variable)"
    )

    parser.add_argument(
        "--ai-provider",
        default="chatgpt",
        choices=["chatgpt", "openai"],
        help="AI provider to use (default: chatgpt)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show populated templates without sending to AI provider",
    )

    parser.add_argument(
        "--verbosity",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging verbosity level (default: INFO)",
    )

    parser.add_argument(
        "--cache-folder",
        help="Path to cache folder (defaults to results folder inside data folder)",
    )

    return parser


def setup_logging(verbosity_level: str) -> logging.Logger:
    """Set up logging to stderr with specified verbosity level."""
    logger = logging.getLogger("prophecy")
    logger.setLevel(getattr(logging, verbosity_level.upper()))

    # Remove any existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create handler that writes to stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, verbosity_level.upper()))

    # Create formatter
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def setup_environment(args) -> None:
    """Set up environment variables from command line arguments."""
    if args.data:
        os.environ["PROPHECY_DATA_FOLDER"] = args.data

    if args.api_key:
        os.environ["OPENAI_API_KEY"] = args.api_key


def initialize_components(data_folder: str | None, logger: logging.Logger):
    """Initialize Stories, Prompts, and Bible components."""
    try:
        # Resolve the data folder path using the same logic as the individual classes
        if data_folder is None:
            resolved_data_folder = os.getenv("PROPHECY_DATA_FOLDER", "data")
        else:
            resolved_data_folder = data_folder

        stories = Stories(data_folder=data_folder)
        prompts = Prompts(data_folder=data_folder)
        bible = Bible(data_folder=data_folder)
        return stories, prompts, bible, resolved_data_folder
    except FileNotFoundError as e:
        logger.error(f"{e}")
        logger.error(
            "Please ensure the data folder contains stories.yml, prompts.tsv, and bible data"
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error initializing data: {e}")
        sys.exit(1)


def validate_inputs(stories, prompts, args, logger: logging.Logger):
    """Validate story and prompt arguments, return lists of items to process."""
    try:
        story_titles = validate_story_arg(stories, args.stories)
    except ValueError as e:
        logger.error(f"{e}")
        sys.exit(1)

    try:
        prompt_list = validate_prompt_arg(prompts, args.prompt)
    except ValueError as e:
        logger.error(f"{e}")
        sys.exit(1)

    return story_titles, prompt_list


def initialize_ai_provider(args, logger: logging.Logger):
    """Initialize AI provider if not in dry-run mode."""
    if args.dry_run:
        return None

    if not AI_PROVIDERS_AVAILABLE:
        logger.error("AI providers not available. Install 'openai' package or use --dry-run")
        sys.exit(1)

    try:
        ai_provider = AIProviderFactory.create_provider(
            args.ai_provider, api_key=args.api_key or os.getenv("OPENAI_API_KEY")
        )

        if not ai_provider.validate_configuration():
            logger.error("AI provider configuration is invalid")
            sys.exit(1)

        return ai_provider

    except (ValueError, AIProviderError) as e:
        logger.error(f"Failed to initialize AI provider: {e}")
        if "API key" in str(e):
            logger.error("Make sure to set OPENAI_API_KEY environment variable or use --api-key")
        sys.exit(1)


def get_biblical_text(bible, story, logger: logging.Logger):
    """Get biblical text for a story, with fallback for missing data."""
    try:
        return bible.get_text(story.book, *story.to_bible_parts())
    except Exception as e:
        logger.warning(f"Could not get biblical text for {story.title}: {e}")
        return f"[Biblical text not available for {story.book}]"


def get_cache_folder(data_folder: str, args, logger: logging.Logger) -> Path:
    """Get the cache folder path, creating it if it doesn't exist."""
    if args.cache_folder:
        cache_folder = Path(args.cache_folder)
    else:
        # Default to results folder inside data folder
        cache_folder = Path(data_folder) / "results"

    # Create cache folder if it doesn't exist
    try:
        cache_folder.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Using cache folder: {cache_folder}")
        return cache_folder
    except Exception as e:
        logger.error(f"Failed to create cache folder {cache_folder}: {e}")
        sys.exit(1)


def calculate_template_checksum(populated_template: str) -> str:
    """Calculate MD5 checksum of the populated template."""
    return hashlib.md5(populated_template.encode("utf-8")).hexdigest()


def get_cached_result(
    cache_folder: Path, checksum: str, logger: logging.Logger
) -> dict[str, Any] | None:
    """Try to get cached result for the given checksum."""
    cache_file = cache_folder / f"{checksum}.json"

    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                cached_result = json.load(f)
            logger.info(f"Found cached result: {cache_file}")
            return cached_result
        except Exception as e:
            logger.warning(f"Failed to read cache file {cache_file}: {e}")

    return None


def save_cached_result(
    cache_folder: Path, checksum: str, result: dict[str, Any], logger: logging.Logger
) -> None:
    """Save result to cache."""
    cache_file = cache_folder / f"{checksum}.json"

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, separators=(",", ":"))
        logger.debug(f"Saved result to cache: {cache_file}")
    except Exception as e:
        logger.warning(f"Failed to save cache file {cache_file}: {e}")


def process_combination(
    prompts,
    story,
    prompt_record,
    biblical_text,
    ai_provider,
    is_dry_run,
    cache_folder,
    logger: logging.Logger,
):
    """Process a single story-prompt combination."""
    # Populate template
    try:
        populated_template = prompts.populate_template(prompt_record, story, biblical_text)
    except Exception as e:
        logger.error(f"Failed to populate template: {e}")
        return False

    if is_dry_run:
        # Just show the populated template (this goes to stdout as before)
        print("=== POPULATED TEMPLATE ===")
        print(populated_template)
        print("=" * 50)
        print()
    else:
        # Calculate checksum for caching
        checksum = calculate_template_checksum(populated_template)
        logger.debug(f"Template checksum: {checksum}")

        # Try to get cached result first
        cached_result = get_cached_result(cache_folder, checksum, logger)

        if cached_result is not None:
            # Use cached result
            print(json.dumps(cached_result, separators=(",", ":")))
        else:
            # Send to AI provider and get response
            try:
                logger.info("Sending to AI provider...")
                ai_response = ai_provider.post_prompt(
                    populated_template,
                    system_message="You are a biblical scholar analyzing ancient texts.",
                )

                # Try to parse the AI response as JSON
                try:
                    response_json = json.loads(ai_response)
                    # Add story title and prompt ID to the JSON
                    response_json["story"] = story.title
                    response_json["prompt"] = prompt_record["id"]

                    # Save to cache
                    save_cached_result(cache_folder, checksum, response_json, logger)

                    # Output as flattened JSON line (to stdout for piping)
                    print(json.dumps(response_json, separators=(",", ":")))

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse AI response as JSON: {e}")
                    logger.debug(f"Raw AI response: {ai_response}")
                    return False
                except Exception as e:
                    logger.error(f"Error processing JSON response: {e}")
                    return False

            except AIProviderError as e:
                logger.error(f"AI provider failed: {e}")
                logger.info("Skipping this combination...")
                return False
            except Exception as e:
                logger.error(f"Unexpected AI error: {e}")
                logger.info("Skipping this combination...")
                return False

    return True


def process_all_combinations(
    stories,
    prompts,
    bible,
    story_titles,
    prompt_list,
    ai_provider,
    args,
    data_folder,
    logger: logging.Logger,
):
    """Process all story-prompt combinations."""
    logger.info("=== Prophecy Processing ===")
    logger.info(f"Stories: {len(story_titles)}")
    logger.info(f"Prompts: {len(prompt_list)}")
    logger.info(f"Mode: {'Dry run' if args.dry_run else f'AI Provider: {args.ai_provider}'}")

    # Get cache folder (only used when not in dry-run mode)
    cache_folder = None
    if not args.dry_run:
        cache_folder = get_cache_folder(data_folder, args, logger)
        logger.info(f"Cache folder: {cache_folder}")

    total_combinations = len(story_titles) * len(prompt_list)
    current_combination = 0

    for story_title in story_titles:
        story = stories.get_story(story_title)
        biblical_text = get_biblical_text(bible, story, logger)

        for prompt_record in prompt_list:
            current_combination += 1

            logger.info(f"--- Combination {current_combination}/{total_combinations} ---")
            logger.info(f"Story: {story.title} ({story.book})")
            logger.info(f"Prompt: #{prompt_record['id']} - {prompt_record['prompt']}")

            process_combination(
                prompts,
                story,
                prompt_record,
                biblical_text,
                ai_provider,
                args.dry_run,
                cache_folder,
                logger,
            )

    logger.info("=== Processing Complete ===")
    logger.info(f"Processed {current_combination} story-prompt combinations")


def main():
    """Main CLI entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Set up logging
    logger = setup_logging(args.verbosity)

    try:
        setup_environment(args)
        stories, prompts, bible, data_folder = initialize_components(args.data, logger)
        story_titles, prompt_list = validate_inputs(stories, prompts, args, logger)
        ai_provider = initialize_ai_provider(args, logger)
        process_all_combinations(
            stories,
            prompts,
            bible,
            story_titles,
            prompt_list,
            ai_provider,
            args,
            data_folder,
            logger,
        )

    except KeyboardInterrupt:
        logger.info("Aborted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
