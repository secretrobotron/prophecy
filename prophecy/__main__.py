#!/usr/bin/env python3
"""
Prophecy command-line interface.

This module provides a CLI for extracting biblical stories and prompts.
"""

import argparse
import hashlib
import json
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .bible import Bible
from .prompts import Prompts
from .settings import Settings
from .stories import Stories

# Try to import AI providers (optional if openai not available)
try:
    from .providers import AIProviderError, AIProviderFactory

    AI_PROVIDERS_AVAILABLE = True
except ImportError:
    AI_PROVIDERS_AVAILABLE = False


def validate_story_arg(stories_obj: Stories, stories_arg: str) -> list[str]:
    """
    Validate and return list of story titles based on argument.

    Args:
        stories_obj: Stories instance
        stories_arg: Either 'all' or a specific story title (case-insensitive)

    Returns:
        List of story titles to process

    Raises:
        ValueError: If story title is not found
    """
    if stories_arg == "all":
        return stories_obj.titles
    canonical = normalize_known(stories_arg, stories_obj.titles, "Story")
    return [canonical]


def select_stories(
    stories_obj: Stories, stories_arg: str, books: list[str] | None
) -> list[str]:
    """
    Resolve the user's story selection from --stories and --book.

    --book is repeatable / comma-separated; each value narrows the story set
    to stories from that book. --stories ``all`` (the default) combined with
    --book runs every story in those books. An explicit story title combined
    with --book is allowed only if the story belongs to one of the books.
    """
    if not books:
        return validate_story_arg(stories_obj, stories_arg)

    # Build the story → book lookup once.
    story_book = {title: stories_obj.get_story(title).book for title in stories_obj.titles}
    available_books = sorted(set(story_book.values()))

    # Case-insensitive book normalization.
    canonical_books = [normalize_known(b, available_books, "Book") for b in books]

    book_set = set(canonical_books)
    by_book = [title for title, b in story_book.items() if b in book_set]

    if stories_arg == "all":
        return sorted(by_book)

    # Explicit --stories together with --book: must overlap. Normalize the
    # story title against the known set first, so casing differences don't
    # masquerade as "not in book".
    canonical_story = normalize_known(stories_arg, list(story_book.keys()), "Story")
    if story_book[canonical_story] not in book_set:
        raise ValueError(
            f"Story '{canonical_story}' is in book '{story_book[canonical_story]}', "
            f"which isn't in --book {sorted(book_set)!r}"
        )
    return [canonical_story]


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


def normalize_known(value: str, known: list[str] | set[str], kind: str) -> str:
    """
    Case-insensitive lookup of ``value`` against ``known``. Returns the
    canonical-cased entry from ``known``, so downstream string equality stays
    strict.

    Raises ValueError with a helpful "Available: …" suffix on miss.
    """
    lookup = {k.lower(): k for k in known}
    canonical = lookup.get(value.lower())
    if canonical is not None:
        return canonical
    available = sorted(lookup.values())
    sample = ", ".join(available[:10])
    if len(available) > 10:
        sample += f", ... ({len(available)} total)"
    raise ValueError(f"{kind} '{value}' not found. Available: {sample}")


def parse_multi_value(raw_values: list[str] | None) -> list[str] | None:
    """
    Normalize a multi-value CLI argument.

    Accepts the argparse output of ``action="append"`` (a list of strings, or
    None when the flag was never passed) and splits each entry on commas so
    that ``--topic A,B --topic C`` becomes ``["A", "B", "C"]``.

    Returns None when no real values were supplied.
    """
    if not raw_values:
        return None
    expanded: list[str] = []
    for raw in raw_values:
        for part in raw.split(","):
            part = part.strip()
            if part:
                expanded.append(part)
    return expanded or None


def select_prompts(
    prompts_obj: Prompts,
    prompt_arg: str,
    period: str | list[str] | None,
    topic: str | list[str] | None,
) -> list[dict[str, str]]:
    """
    Resolve the user's prompt selection from --prompt / --period / --topic.

    --prompt is mutually exclusive with --period/--topic when it isn't "all".
    --period and --topic narrow by intersection (any-of within each).
    """
    if prompt_arg != "all" and (period or topic):
        raise ValueError(
            "--prompt cannot be combined with --period or --topic. "
            "Use --prompt for a single ID, or --period/--topic to select a group."
        )

    if period or topic:
        period_list = [period] if isinstance(period, str) else (period or [])
        topic_list = [topic] if isinstance(topic, str) else (topic or [])

        # Case-insensitive normalization against the prompts.tsv vocabulary.
        available_periods = prompts_obj.get_periods()
        available_topics = prompts_obj.get_topics()
        period_list = [normalize_known(p, available_periods, "Period") for p in period_list]
        topic_list = [normalize_known(t, available_topics, "Topic") for t in topic_list]

        selected = prompts_obj.filter(
            period=period_list or None,
            topic=topic_list or None,
        )
        if not selected:
            raise ValueError(
                f"No prompts match period={period_list or None!r} topic={topic_list or None!r}"
            )
        return selected

    return validate_prompt_arg(prompts_obj, prompt_arg)


def build_concatenated_prompt(
    prompt_records: list[dict[str, str]],
    period: str | list[str] | None,
    topic: str | list[str] | None,
) -> dict[str, str]:
    """
    Bundle a list of prompts into a single synthetic prompt record.

    The combined statement is rendered as a numbered list so the LLM can see
    each sub-claim. The synthetic id is ``concat:<period>:<topic>`` (using
    "all" for any unset selector, joining lists with "+") so cached results
    stay introspectable.
    """
    if not prompt_records:
        raise ValueError("Cannot concatenate an empty prompt set")

    def _label(
        explicit: str | list[str] | None,
        key: str,
    ) -> str:
        if explicit:
            values = [explicit] if isinstance(explicit, str) else list(explicit)
            return "+".join(values)
        # No explicit filter — use the records' shared value if uniform, else "all"
        distinct = {p[key] for p in prompt_records}
        return next(iter(distinct)) if len(distinct) == 1 else "all"

    period_label = _label(period, "period")
    topic_label = _label(topic, "topic")

    body_lines = [f"{i + 1}. {p['prompt']}" for i, p in enumerate(prompt_records)]
    combined = "All of the following statements apply:\n" + "\n".join(body_lines)

    return {
        "id": f"concat:{period_label}:{topic_label}",
        "period": period_label,
        "topic": topic_label,
        "prompt": combined,
        "_concatenated_ids": ",".join(p["id"] for p in prompt_records),
    }


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract biblical stories, populate prompts, and get AI responses. "
            "See 'query' to aggregate cached results, and 'export' to assemble "
            "a static bundle for the web viewer."
        ),
        epilog=(
            "Subcommands:\n"
            "  query    Aggregate cached prompt results "
            "(see 'python -m prophecy query --help')\n"
            "  export   Assemble a static bundle of cached results for the viewer "
            "(see 'python -m prophecy export --help')\n\n"
            "Examples:\n"
            "  python -m prophecy --period Politics --topic Populism --book Exodus\n"
            "  python -m prophecy --book Exodus,Genesis --prompt 152\n"
            "  python -m prophecy --topic Populism,Elitism --concatenate\n"
            "  python -m prophecy query --period Politics --book Exodus\n"
            "  python -m prophecy export --out dist/data"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog="python -m prophecy",
    )

    parser.add_argument(
        "--stories",
        default="all",
        help='Story to extract: either a specific story title or "all" (default: all)',
    )

    parser.add_argument(
        "--book",
        action="append",
        default=None,
        help=(
            "Narrow --stories by biblical book (e.g. 'Exodus'). Repeatable or "
            "comma-separated. Combines with --stories: 'all' runs every story in the "
            "listed books; an explicit story title must belong to one of them."
        ),
    )

    parser.add_argument(
        "--prompt",
        default="all",
        help='Prompt to use: either a specific prompt ID or "all" (default: all)',
    )

    parser.add_argument(
        "--period",
        action="append",
        default=None,
        help=(
            "Select prompts by period (e.g. 'Politics'). Repeatable or comma-separated "
            "for multiple (e.g. --period Politics --period Persian, or --period Politics,Persian). "
            "Cannot combine with a specific --prompt."
        ),
    )

    parser.add_argument(
        "--topic",
        action="append",
        default=None,
        help=(
            "Select prompts by topic (e.g. 'Populism'). Repeatable or comma-separated. "
            "Use with --period to narrow further. Cannot combine with a specific --prompt."
        ),
    )

    parser.add_argument(
        "--concatenate",
        action="store_true",
        help=(
            "Bundle the selected prompts into a single combined statement sent in one "
            "LLM call per story (instead of one call per prompt)."
        ),
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
        choices=["chatgpt", "openai", "claude", "anthropic", "claude-cli", "local-claude"],
        help=(
            'AI provider to use (default: chatgpt). "claude-cli"/"local-claude" '
            "shells out to the `claude` CLI and needs no API key."
        ),
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

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Run that many AI-provider requests in parallel (default: 1). "
            "Cache reads/writes are file-per-call so they don't collide; stdout "
            "stays line-buffered. Useful with --ai-provider claude/chatgpt."
        ),
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


def initialize_components(settings: Settings, logger: logging.Logger):
    """Initialize Stories, Prompts, and Bible components from a Settings."""
    try:
        stories = Stories(data_folder=settings.data_folder)
        prompts = Prompts(data_folder=settings.data_folder)
        bible = Bible(data_folder=settings.data_folder)
        return stories, prompts, bible
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
        story_titles = select_stories(
            stories,
            args.stories,
            parse_multi_value(getattr(args, "book", None)),
        )
    except ValueError as e:
        logger.error(f"{e}")
        sys.exit(1)

    try:
        prompt_list = select_prompts(
            prompts,
            args.prompt,
            parse_multi_value(getattr(args, "period", None)),
            parse_multi_value(getattr(args, "topic", None)),
        )
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

    # Each provider falls back to its own env var when api_key is None,
    # so only override with --api-key when the user explicitly supplied one.
    factory_kwargs = {}
    if args.api_key:
        factory_kwargs["api_key"] = args.api_key

    try:
        ai_provider = AIProviderFactory.create_provider(
            args.ai_provider,
            **factory_kwargs,
        )

        if not ai_provider.validate_configuration():
            logger.error("AI provider configuration is invalid")
            sys.exit(1)

        return ai_provider

    except (ValueError, AIProviderError) as e:
        logger.error(f"Failed to initialize AI provider: {e}")
        if "API key" in str(e):
            logger.error(
                "Set the appropriate API key env var (OPENAI_API_KEY or ANTHROPIC_API_KEY) or pass --api-key"
            )
        sys.exit(1)


def get_biblical_text(bible, story, logger: logging.Logger):
    """Get biblical text for a story, with fallback for missing data."""
    try:
        return bible.get_text(story.book, *story.to_bible_parts())
    except Exception as e:
        logger.warning(f"Could not get biblical text for {story.title}: {e}")
        return f"[Biblical text not available for {story.book}]"


def get_cache_folder(settings: Settings, logger: logging.Logger) -> Path:
    """Resolve the cache folder from settings, creating it if needed."""
    cache_folder = settings.resolve_cache_folder()
    try:
        cache_folder.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Using cache folder: {cache_folder}")
        return cache_folder
    except Exception as e:
        logger.error(f"Failed to create cache folder {cache_folder}: {e}")
        sys.exit(1)


def calculate_template_checksum(
    populated_template: str, engine_id: str | None = None
) -> str:
    """
    Calculate MD5 checksum of the populated template, optionally namespaced
    by an engine identifier so identical prompts sent to different engines
    don't collide in the cache.

    Pre-existing cached files (computed before engine namespacing) remain
    readable by the query subcommand — they just won't be hit on re-run
    when an engine is specified.
    """
    if engine_id:
        payload = f"{engine_id}\n{populated_template}"
    else:
        payload = populated_template
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def get_cached_result(
    cache_folder: Path, checksum: str, logger: logging.Logger
) -> dict[str, Any] | None:
    """Try to get cached result for the given checksum."""
    cache_file = cache_folder / f"{checksum}.json"

    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                cached_result = json.load(f)
            logger.debug(f"Found cached result: {cache_file}")
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
        # Engine id namespaces the cache so per-engine answers don't collide.
        engine_id = ai_provider.engine_id if ai_provider is not None else None

        # Calculate checksum for caching
        checksum = calculate_template_checksum(populated_template, engine_id)
        logger.debug(f"Template checksum: {checksum} (engine={engine_id})")

        # Try to get cached result first
        cached_result = get_cached_result(cache_folder, checksum, logger)

        if cached_result is not None:
            # Cached: log the answer at DEBUG so default output stays quiet.
            logger.debug(json.dumps(cached_result, separators=(",", ":")))
        else:
            # Send to AI provider and get response
            try:
                logger.debug("Sending to AI provider...")
                ai_response = ai_provider.post_prompt(
                    populated_template,
                    system_message="You are a biblical scholar analyzing ancient texts.",
                )

                # Try to parse the AI response as JSON
                try:
                    response_json = json.loads(ai_response)
                    # Add story title, prompt ID, and engine id to the JSON
                    response_json["story"] = story.title
                    response_json["prompt"] = prompt_record["id"]
                    response_json["engine"] = engine_id

                    # Save to cache (this is the durable artifact; use
                    # `prophecy query` to read results back).
                    save_cached_result(cache_folder, checksum, response_json, logger)

                    # Log the answer at DEBUG only — default runs stay quiet.
                    logger.debug(json.dumps(response_json, separators=(",", ":")))

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse AI response as JSON: {e}")
                    logger.debug(f"Raw AI response: {ai_response}")
                    return False
                except Exception as e:
                    logger.error(f"Error processing JSON response: {e}")
                    return False

            except AIProviderError as e:
                logger.error(f"AI provider failed: {e}")
                logger.debug("Skipping this combination...")
                return False
            except Exception as e:
                logger.error(f"Unexpected AI error: {e}")
                logger.debug("Skipping this combination...")
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
    settings: Settings,
    logger: logging.Logger,
):
    """Process all story-prompt combinations."""
    concatenate = getattr(args, "concatenate", False)

    # If --concatenate, collapse the prompt list into a single synthetic record per story.
    effective_prompts: list[dict[str, str]]
    if concatenate:
        combined = build_concatenated_prompt(
            prompt_list,
            parse_multi_value(getattr(args, "period", None)),
            parse_multi_value(getattr(args, "topic", None)),
        )
        effective_prompts = [combined]
        logger.info(
            f"Concatenating {len(prompt_list)} prompts into synthetic id {combined['id']!r}"
        )
    else:
        effective_prompts = prompt_list

    logger.info("=== Prophecy Processing ===")
    logger.info(f"Stories: {len(story_titles)}")
    logger.info(f"Prompts: {len(effective_prompts)}")
    logger.info(f"Mode: {'Dry run' if args.dry_run else f'AI Provider: {args.ai_provider}'}")

    # Get cache folder (only used when not in dry-run mode)
    cache_folder = None
    if not args.dry_run:
        cache_folder = get_cache_folder(settings, logger)
        logger.info(f"Cache folder: {cache_folder}")

    # Build the (story, prompt) work list up front — text fetch is cheap and
    # we want it done deterministically before any threads kick off.
    work_items: list[tuple[Any, dict[str, str], str]] = []
    for story_title in story_titles:
        story = stories.get_story(story_title)
        biblical_text = get_biblical_text(bible, story, logger)
        for prompt_record in effective_prompts:
            work_items.append((story, prompt_record, biblical_text))

    total = len(work_items)
    workers = max(1, int(getattr(args, "workers", 1) or 1))
    # Dry-run prints multi-line blocks per item; threading them just interleaves
    # garbage. Force serial for dry-run.
    if args.dry_run:
        workers = 1

    if workers > 1:
        logger.info(f"Parallel mode: {workers} workers")

    completed = 0
    completed_lock = threading.Lock()

    def run_one(idx_item):
        idx, (story, prompt_record, biblical_text) = idx_item
        return idx, process_combination(
            prompts,
            story,
            prompt_record,
            biblical_text,
            ai_provider,
            args.dry_run,
            cache_folder,
            logger,
        )

    if workers == 1:
        for story, prompt_record, biblical_text in work_items:
            completed += 1
            logger.info(
                f"Combination {completed}/{total}: "
                f"{story.title} ({story.book}) / #{prompt_record['id']}"
            )
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
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(run_one, (idx, item)): (idx, item)
                for idx, item in enumerate(work_items)
            }
            for fut in as_completed(futures):
                idx, item = futures[fut]
                story, prompt_record, _ = item
                try:
                    fut.result()
                except Exception as e:
                    logger.error(f"Worker error on combination #{idx + 1}: {e}")
                with completed_lock:
                    completed += 1
                    logger.info(
                        f"--- Combination {completed}/{total}: "
                        f"{story.title} ({story.book}) / #{prompt_record['id']}"
                    )

    logger.info("=== Processing Complete ===")
    logger.info(f"Processed {completed} story-prompt combinations")


def _create_query_parser() -> argparse.ArgumentParser:
    """Argparse parser for the 'query' subcommand."""
    parser = argparse.ArgumentParser(
        description="Aggregate cached prompt results across stories.",
        prog="python -m prophecy query",
    )
    parser.add_argument("--data", help="Path to data folder (overrides PROPHECY_DATA_FOLDER)")
    parser.add_argument("--cache-folder", help="Path to cache folder (defaults to data/results)")
    parser.add_argument(
        "--period",
        action="append",
        default=None,
        help="Filter results by prompt period. Repeatable or comma-separated.",
    )
    parser.add_argument(
        "--topic",
        action="append",
        default=None,
        help="Filter results by prompt topic. Repeatable or comma-separated.",
    )
    parser.add_argument("--book", default=None, help="Filter results by biblical book")
    parser.add_argument("--story", default=None, help="Filter results by story title")
    parser.add_argument(
        "--engine",
        action="append",
        default=None,
        help=(
            "Filter results by engine id (e.g. 'chatgpt:gpt-3.5-turbo'). "
            "Repeatable or comma-separated. Use 'unknown' to match pre-engine cached results."
        ),
    )
    parser.add_argument(
        "--min-certainty",
        type=int,
        default=0,
        help="Drop results with certainty below this threshold (0-100, default 0)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "tsv", "json"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--verbosity",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging verbosity (default: WARNING; lower than 'run' to keep stdout clean)",
    )
    return parser


def _load_cached_results(
    cache_folder: Path, logger: logging.Logger
) -> list[dict[str, Any]]:
    """Read every *.json file in the cache folder. Skip unreadable/non-result files."""
    if not cache_folder.exists():
        logger.warning(f"Cache folder does not exist: {cache_folder}")
        return []

    results = []
    for path in sorted(cache_folder.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.debug(f"Skipping unreadable cache file {path}: {e}")
            continue
        if not isinstance(data, dict) or "story" not in data or "prompt" not in data:
            logger.debug(f"Skipping non-result file {path}")
            continue
        results.append(data)
    return results


def _resolve_prompt_meta(prompt_id: str, prompt_meta: dict[str, tuple[str, str]]) -> tuple[str, str]:
    """Look up (period, topic) for a prompt id. Falls back for synthetic concat:* ids."""
    if prompt_id in prompt_meta:
        return prompt_meta[prompt_id]
    if prompt_id.startswith("concat:"):
        parts = prompt_id.split(":", 2)
        period = parts[1] if len(parts) > 1 and parts[1] else "concat"
        topic = parts[2] if len(parts) > 2 and parts[2] else "concat"
        return period, topic
    return "unknown", "unknown"


def _format_table(rows: list[dict[str, Any]]) -> str:
    """Render summary rows as a column-aligned text table."""
    if not rows:
        return "(no results)"

    columns = [
        ("story", "Story"),
        ("book", "Book"),
        ("period", "Period"),
        ("topic", "Topic"),
        ("engine", "Engine"),
        ("hits", "Hits"),
        ("total", "Total"),
        ("hit_rate", "Hit%"),
        ("avg_certainty", "AvgCert"),
    ]

    def fmt(key: str, value: Any) -> str:
        if key == "hit_rate":
            return f"{value * 100:.0f}%"
        if key == "avg_certainty":
            return f"{value:.0f}"
        return str(value)

    rendered = [
        {key: fmt(key, row[key]) for key, _ in columns}
        for row in rows
    ]
    widths = {
        key: max(len(header), *(len(r[key]) for r in rendered))
        for key, header in columns
    }
    header_line = "  ".join(header.ljust(widths[key]) for key, header in columns)
    sep_line = "  ".join("-" * widths[key] for key, _ in columns)
    body_lines = [
        "  ".join(r[key].ljust(widths[key]) for key, _ in columns) for r in rendered
    ]
    return "\n".join([header_line, sep_line, *body_lines])


def query_command(argv: list[str]) -> int:
    """Entry point for `python -m prophecy query [...]`."""
    parser = _create_query_parser()
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbosity)

    try:
        settings = Settings.load(data_folder=args.data, cache_folder=args.cache_folder)
        prompts = Prompts(data_folder=settings.data_folder)
        stories = Stories(data_folder=settings.data_folder)
    except FileNotFoundError as e:
        logger.error(f"{e}")
        return 1

    prompt_meta = {p["id"]: (p["period"], p["topic"]) for p in prompts.get_prompts()}
    story_book = {title: stories.get_story(title).book for title in stories.titles}

    cache_folder = settings.resolve_cache_folder()
    raw_results = _load_cached_results(cache_folder, logger)
    logger.info(f"Loaded {len(raw_results)} cached results from {cache_folder}")

    period_filter = parse_multi_value(args.period)
    topic_filter = parse_multi_value(args.topic)
    engine_filter = parse_multi_value(args.engine)

    # Case-insensitive normalization for period/topic/book/story. Engine ids
    # stay case-sensitive (they're identifiers like "chatgpt:gpt-4").
    try:
        if period_filter:
            period_filter = [
                normalize_known(p, prompts.get_periods(), "Period") for p in period_filter
            ]
        if topic_filter:
            topic_filter = [
                normalize_known(t, prompts.get_topics(), "Topic") for t in topic_filter
            ]
        book_arg = args.book
        story_arg = args.story
        if book_arg:
            book_arg = normalize_known(book_arg, sorted(set(story_book.values())), "Book")
        if story_arg:
            story_arg = normalize_known(story_arg, list(story_book.keys()), "Story")
    except ValueError as e:
        logger.error(f"{e}")
        return 1

    # Aggregate by (story, period, topic, engine) — engine in the key so per-engine
    # answers stay separable. Pre-engine cached files surface as engine="unknown".
    agg: dict[tuple[str, str, str, str, str], dict[str, float]] = {}
    for r in raw_results:
        story_title = str(r["story"])
        prompt_id = str(r["prompt"])
        period, topic = _resolve_prompt_meta(prompt_id, prompt_meta)
        book = story_book.get(story_title, "unknown")
        certainty = r.get("certainty", 0) or 0
        engine = str(r.get("engine") or "unknown")

        if period_filter and period not in period_filter:
            continue
        if topic_filter and topic not in topic_filter:
            continue
        if book_arg and book != book_arg:
            continue
        if story_arg and story_title != story_arg:
            continue
        if engine_filter and engine not in engine_filter:
            continue
        if certainty < args.min_certainty:
            continue

        key = (story_title, book, period, topic, engine)
        bucket = agg.setdefault(
            key, {"hits": 0, "total": 0, "cert_sum": 0.0}
        )
        bucket["total"] += 1
        if r.get("answer"):
            bucket["hits"] += 1
        bucket["cert_sum"] += certainty

    summary = []
    for (story_title, book, period, topic, engine), bucket in agg.items():
        total = bucket["total"]
        summary.append(
            {
                "story": story_title,
                "book": book,
                "period": period,
                "topic": topic,
                "engine": engine,
                "hits": int(bucket["hits"]),
                "total": int(total),
                "hit_rate": (bucket["hits"] / total) if total else 0.0,
                "avg_certainty": (bucket["cert_sum"] / total) if total else 0.0,
            }
        )

    summary.sort(
        key=lambda r: (-r["hit_rate"], r["story"], r["period"], r["topic"], r["engine"])
    )

    if args.format == "json":
        print(json.dumps(summary, indent=2))
    elif args.format == "tsv":
        print(
            "story\tbook\tperiod\ttopic\tengine\thits\ttotal\thit_rate\tavg_certainty"
        )
        for row in summary:
            print(
                f"{row['story']}\t{row['book']}\t{row['period']}\t{row['topic']}\t{row['engine']}\t"
                f"{row['hits']}\t{row['total']}\t{row['hit_rate']:.4f}\t{row['avg_certainty']:.2f}"
            )
    else:
        print(_format_table(summary))

    return 0


def _create_export_parser() -> argparse.ArgumentParser:
    """Argparse parser for the 'export' subcommand."""
    parser = argparse.ArgumentParser(
        description=(
            "Export cached results into a static, browser-consumable bundle "
            "(sharded JSONL by book + manifest)."
        ),
        prog="python -m prophecy export",
    )
    parser.add_argument("--data", help="Path to data folder (overrides PROPHECY_DATA_FOLDER)")
    parser.add_argument("--cache-folder", help="Path to cache folder (defaults to data/results)")
    parser.add_argument(
        "--out",
        default="dist/data",
        help="Output folder for the static bundle (default: dist/data)",
    )
    parser.add_argument(
        "--verbosity",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging verbosity (default: INFO)",
    )
    return parser


def _shard_key_for(book: str) -> str:
    """Filesystem-safe shard filename for a book."""
    safe = book.replace("/", "_").replace(" ", "_")
    return f"{safe}.jsonl"


def export_command(argv: list[str]) -> int:
    """
    Entry point for `python -m prophecy export [...]`.

    Writes:
      <out>/index.json     -- manifest with shard inventory and facets
      <out>/prompts.json   -- prompts.tsv converted to JSON
      <out>/stories.json   -- stories.yml converted to JSON
      <out>/results/<Book>.jsonl  -- one shard per book, enriched with
                                     book/period/topic so the viewer can
                                     filter without joining.
    """
    import datetime

    parser = _create_export_parser()
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbosity)

    try:
        settings = Settings.load(data_folder=args.data, cache_folder=args.cache_folder)
        prompts = Prompts(data_folder=settings.data_folder)
        stories = Stories(data_folder=settings.data_folder)
    except FileNotFoundError as e:
        logger.error(f"{e}")
        return 1

    out_root = Path(args.out)
    out_results = out_root / "results"
    out_root.mkdir(parents=True, exist_ok=True)
    out_results.mkdir(parents=True, exist_ok=True)

    prompt_meta = {p["id"]: (p["period"], p["topic"]) for p in prompts.get_prompts()}
    story_book = {title: stories.get_story(title).book for title in stories.titles}

    cache_folder = settings.resolve_cache_folder()
    raw_results = _load_cached_results(cache_folder, logger)
    logger.info(f"Loaded {len(raw_results)} cached results from {cache_folder}")

    # Group enriched rows by book.
    by_book: dict[str, list[dict[str, Any]]] = {}
    facets_engines: set[str] = set()
    facets_periods: set[str] = set()
    facets_topics: set[str] = set()
    facets_stories: set[str] = set()
    result_count_by_prompt: dict[str, int] = {}

    for r in raw_results:
        story_title = str(r.get("story", ""))
        prompt_id = str(r.get("prompt", ""))
        period, topic = _resolve_prompt_meta(prompt_id, prompt_meta)
        book = story_book.get(story_title, "unknown")
        engine = str(r.get("engine") or "unknown")

        enriched = {
            "story": story_title,
            "book": book,
            "prompt": prompt_id,
            "period": period,
            "topic": topic,
            "engine": engine,
            "answer": bool(r.get("answer", False)),
            "certainty": int(r.get("certainty", 0) or 0),
            "reason": r.get("reason", ""),
        }
        by_book.setdefault(book, []).append(enriched)
        facets_engines.add(engine)
        facets_periods.add(period)
        facets_topics.add(topic)
        if story_title:
            facets_stories.add(story_title)
        if prompt_id:
            result_count_by_prompt[prompt_id] = result_count_by_prompt.get(prompt_id, 0) + 1

    # Write shards.
    shards = []
    for book in sorted(by_book.keys()):
        rows = by_book[book]
        # Deterministic ordering inside a shard.
        rows.sort(key=lambda x: (x["story"], x["prompt"], x["engine"]))

        shard_file = _shard_key_for(book)
        shard_path = out_results / shard_file
        with open(shard_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":")))
                f.write("\n")

        shards.append(
            {
                "book": book,
                "file": f"results/{shard_file}",
                "row_count": len(rows),
                "stories": sorted({r["story"] for r in rows}),
                "engines": sorted({r["engine"] for r in rows}),
                "periods": sorted({r["period"] for r in rows}),
                "topics": sorted({r["topic"] for r in rows}),
            }
        )
        logger.debug(f"Wrote {len(rows)} rows to {shard_path}")

    # Write prompts.json (the full TSV as a JSON array).
    prompts_json_path = out_root / "prompts.json"
    with open(prompts_json_path, "w", encoding="utf-8") as f:
        json.dump(prompts.get_prompts(), f, separators=(",", ":"))

    # Write stories.json (title -> {book, verses}).
    stories_json_path = out_root / "stories.json"
    stories_payload = {
        title: {"book": stories.get_story(title).book, "verses": stories.get_story(title).verses}
        for title in stories.titles
    }
    with open(stories_json_path, "w", encoding="utf-8") as f:
        json.dump(stories_payload, f, separators=(",", ":"))

    # Write the manifest.
    manifest = {
        "generated_at": datetime.datetime.now(datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "total_results": sum(s["row_count"] for s in shards),
        "books": [s["book"] for s in shards],
        "stories": sorted(facets_stories),
        "engines": sorted(facets_engines),
        "periods": sorted(facets_periods),
        "topics": sorted(facets_topics),
        "used_prompt_ids": sorted(result_count_by_prompt.keys()),
        "result_count_by_prompt": dict(sorted(result_count_by_prompt.items())),
        "shards": shards,
        "files": {
            "prompts": "prompts.json",
            "stories": "stories.json",
            "results_dir": "results/",
        },
    }
    with open(out_root / "index.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(
        f"Exported {manifest['total_results']} results across {len(shards)} book shards "
        f"to {out_root}"
    )
    return 0


def main():
    """Main CLI entry point."""
    # Dispatch the 'query' or 'export' subcommands without touching the run pipeline.
    argv = sys.argv[1:]
    if argv and argv[0] == "query":
        sys.exit(query_command(argv[1:]))
    if argv and argv[0] == "export":
        sys.exit(export_command(argv[1:]))

    parser = create_argument_parser()
    args = parser.parse_args()

    # Set up logging
    logger = setup_logging(args.verbosity)

    try:
        # Build a Settings once from CLI flags + env + ./prophecy.toml,
        # then thread it through the pipeline.
        settings = Settings.load(data_folder=args.data, cache_folder=args.cache_folder)

        stories, prompts, bible = initialize_components(settings, logger)
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
            settings,
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
