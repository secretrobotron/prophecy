#!/usr/bin/env python3
"""
Prophecy command-line interface.

This module provides a CLI for extracting biblical stories and prompts.
"""

import argparse
import hashlib
import json
import logging
import random
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


# NATO phonetic alphabet — short, distinctive codenames for parallel workers
# so log lines from concurrent threads stay visually distinguishable.
_WORKER_NAME_POOL = (
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
    "mike",
    "november",
    "oscar",
    "papa",
    "quebec",
    "romeo",
    "sierra",
    "tango",
    "uniform",
    "victor",
    "whiskey",
    "xray",
    "yankee",
    "zulu",
)


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


def select_stories(stories_obj: Stories, stories_arg: str, books: list[str] | None) -> list[str]:
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
    category: str | list[str] | None,
    topic: str | list[str] | None,
) -> list[dict[str, str]]:
    """
    Resolve the user's prompt selection from --prompt / --category / --topic.

    --prompt is mutually exclusive with --category/--topic when it isn't "all".
    --category and --topic narrow by intersection (any-of within each).
    """
    if prompt_arg != "all" and (category or topic):
        raise ValueError(
            "--prompt cannot be combined with --category or --topic. "
            "Use --prompt for a single ID, or --category/--topic to select a group."
        )

    if category or topic:
        category_list = [category] if isinstance(category, str) else (category or [])
        topic_list = [topic] if isinstance(topic, str) else (topic or [])

        # Case-insensitive normalization against the prompts.tsv vocabulary.
        available_categories = prompts_obj.get_categories()
        available_topics = prompts_obj.get_topics()
        category_list = [
            normalize_known(p, available_categories, "Category") for p in category_list
        ]
        topic_list = [normalize_known(t, available_topics, "Topic") for t in topic_list]

        selected = prompts_obj.filter(
            category=category_list or None,
            topic=topic_list or None,
        )
        if not selected:
            raise ValueError(
                f"No prompts match category={category_list or None!r} topic={topic_list or None!r}"
            )
        return selected

    return validate_prompt_arg(prompts_obj, prompt_arg)


def build_concatenated_prompt(
    prompt_records: list[dict[str, str]],
    category: str | list[str] | None,
    topic: str | list[str] | None,
) -> dict[str, str]:
    """
    Bundle a list of prompts into a single synthetic prompt record.

    The combined statement is rendered as a numbered list so the LLM can see
    each sub-claim. The synthetic id is ``concat:<category>:<topic>`` (using
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

    category_label = _label(category, "category")
    topic_label = _label(topic, "topic")

    body_lines = [f"{i + 1}. {p['prompt']}" for i, p in enumerate(prompt_records)]
    combined = "All of the following statements apply:\n" + "\n".join(body_lines)

    return {
        "id": f"concat:{category_label}:{topic_label}",
        "category": category_label,
        "topic": topic_label,
        "prompt": combined,
        "_concatenated_ids": ",".join(p["id"] for p in prompt_records),
    }


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract biblical stories, populate prompts, and get AI responses. "
            "See 'query' to aggregate cached results, 'label' to derive "
            "per-story labels, and 'export' to assemble a static bundle for "
            "the web viewer."
        ),
        epilog=(
            "Subcommands:\n"
            "  query    Aggregate cached prompt results "
            "(see 'python -m prophecy query --help')\n"
            "  label    Derive per-story labels from cached results "
            "(see 'python -m prophecy label --help')\n"
            "  export   Assemble a static bundle of cached results for the viewer "
            "(see 'python -m prophecy export --help')\n"
            "  prune    Delete cached result files by engine filter "
            "(see 'python -m prophecy prune --help')\n\n"
            "Examples:\n"
            "  python -m prophecy --category Politics --topic Populism --book Exodus\n"
            "  python -m prophecy --book Exodus,Genesis --prompt 152\n"
            "  python -m prophecy --topic Populism,Elitism --concatenate\n"
            "  python -m prophecy query --category Politics --book Exodus\n"
            "  python -m prophecy label --exclude-category Test\n"
            "  python -m prophecy prune --engine unknown --dry-run\n"
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
        "--category",
        action="append",
        default=None,
        help=(
            "Select prompts by category (e.g. 'Politics'). Repeatable or comma-separated "
            "for multiple (e.g. --category Politics --category Persian, or --category Politics,Persian). "
            "Cannot combine with a specific --prompt."
        ),
    )

    parser.add_argument(
        "--topic",
        action="append",
        default=None,
        help=(
            "Select prompts by topic (e.g. 'Populism'). Repeatable or comma-separated. "
            "Use with --category to narrow further. Cannot combine with a specific --prompt."
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
        "--stories-file",
        default=None,
        help=(
            "Name (or path) of the stories YAML file inside the data folder "
            "(default: stories.yml). Overrides PROPHECY_STORIES_FILE and the "
            "stories_file entry in prophecy.toml. Use an absolute path to "
            "load a file outside the data folder."
        ),
    )

    parser.add_argument(
        "--api-key", help="API key for AI services (overrides OPENAI_API_KEY environment variable)"
    )

    parser.add_argument(
        "--ai-provider",
        default=None,
        choices=[
            "chatgpt",
            "openai",
            "claude",
            "anthropic",
            "claude-cli",
            "local-claude",
            "ollama",
            "local",
            "runpod",
            "runpod-serverless",
        ],
        help=(
            "AI provider to use. Falls back to the `ai_provider` setting in "
            "prophecy.toml (default chatgpt if unset). "
            '"claude-cli"/"local-claude" shells out to the `claude` CLI; '
            '"ollama"/"local" hits a local Ollama daemon (no API key); '
            '"runpod"/"runpod-serverless" hits a RunPod Serverless vLLM '
            "endpoint (needs RUNPOD_API_KEY + endpoint_id)."
        ),
    )

    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Override the provider's model for this run (e.g. "
            "'qwen2.5:14b-instruct' for ollama, 'Qwen/Qwen2.5-14B-Instruct' "
            "for runpod, 'gpt-4o-mini' for chatgpt). Per-provider defaults "
            "can also be set under [providers.<name>] in prophecy.toml."
        ),
    )

    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "Override the provider's base URL for this run. Useful for "
            "pointing ollama at a non-default daemon, or runpod at a "
            "custom domain. For RunPod, prefer --endpoint-id which builds "
            "the URL for you."
        ),
    )

    parser.add_argument(
        "--endpoint-id",
        default=None,
        help=(
            "RunPod Serverless endpoint ID. Combined with the standard "
            "https://api.runpod.ai/v2/<id>/openai/v1 template to form the "
            "base URL. Can also be set as [providers.runpod] endpoint_id in "
            "prophecy.toml or via RUNPOD_ENDPOINT_ID."
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
        default=None,
        help=(
            "Run that many AI-provider requests in parallel. Overrides "
            "PROPHECY_WORKERS and the workers entry in prophecy.toml (default: 3). "
            "Each worker is an independent provider call so prompts can't "
            "cross-contaminate; cache reads/writes are file-per-call so they "
            "don't collide. Dry-run is always serial."
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
        stories = Stories(
            data_folder=settings.data_folder,
            stories_file=settings.stories_file,
        )
        prompts = Prompts(data_folder=settings.data_folder)
        bible = Bible(data_folder=settings.data_folder)
        return stories, prompts, bible
    except FileNotFoundError as e:
        logger.error(f"{e}")
        logger.error(
            f"Please ensure the data folder contains {settings.stories_folder}/{settings.stories_file}, "
            f"{settings.prompts_folder}/prompts.tsv, and bible data"
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
            parse_multi_value(getattr(args, "category", None)),
            parse_multi_value(getattr(args, "topic", None)),
        )
    except ValueError as e:
        logger.error(f"{e}")
        sys.exit(1)

    return story_titles, prompt_list


def initialize_ai_provider(args, settings: Settings, logger: logging.Logger):
    """Initialize AI provider if not in dry-run mode.

    Resolution order, highest precedence first:
        --ai-provider CLI flag           >  settings.ai_provider  >  "chatgpt"
        --model / --base-url / --endpoint-id
                                         >  [providers.<name>] in toml  >  provider default
        --api-key                        >  provider's own env-var fallback

    Falling through means a user can pin their provider + model in
    prophecy.toml once and stop passing them on every invocation.
    """
    if args.dry_run:
        return None

    if not AI_PROVIDERS_AVAILABLE:
        logger.error("AI providers not available. Install 'openai' package or use --dry-run")
        sys.exit(1)

    provider_name = args.ai_provider or settings.ai_provider
    factory_kwargs = settings.provider_config(provider_name)

    if args.api_key:
        factory_kwargs["api_key"] = args.api_key
    if args.model:
        factory_kwargs["model"] = args.model
    if args.base_url:
        factory_kwargs["base_url"] = args.base_url
    if args.endpoint_id:
        factory_kwargs["endpoint_id"] = args.endpoint_id

    try:
        ai_provider = AIProviderFactory.create_provider(
            provider_name,
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
                "Set the appropriate API key env var (OPENAI_API_KEY, "
                "ANTHROPIC_API_KEY, RUNPOD_API_KEY) or pass --api-key"
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


def calculate_template_checksum(populated_template: str, engine_id: str | None = None) -> str:
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
        # ai_provider is required outside dry-run mode; the entry point only
        # threads None through when is_dry_run=True (which is the if-branch).
        assert ai_provider is not None, "ai_provider must be set when is_dry_run is False"
        engine_id = ai_provider.engine_id

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
            parse_multi_value(getattr(args, "category", None)),
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
    effective_provider = args.ai_provider or settings.ai_provider
    logger.info(f"Mode: {'Dry run' if args.dry_run else f'AI Provider: {effective_provider}'}")

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
    # Settings already validated workers >= 1; CLI default of None means
    # "use whatever Settings resolved (CLI flag → env → toml → 3)".
    workers = settings.workers
    # Dry-run prints multi-line blocks per item; threading them just interleaves
    # garbage. Force serial for dry-run.
    if args.dry_run:
        workers = 1

    # Pre-pick a distinct codename per worker so log lines from concurrent
    # threads are visually distinguishable. If workers > pool size (26),
    # suffix duplicates with -2, -3, ... so names stay unique.
    if workers > 1:
        if workers <= len(_WORKER_NAME_POOL):
            worker_names = random.sample(_WORKER_NAME_POOL, workers)
        else:
            pool_size = len(_WORKER_NAME_POOL)
            shuffled = random.sample(_WORKER_NAME_POOL, pool_size)
            worker_names = [
                shuffled[i % pool_size]
                if i < pool_size
                else f"{shuffled[i % pool_size]}-{i // pool_size + 1}"
                for i in range(workers)
            ]
        logger.info(f"Parallel mode: {workers} workers ({', '.join(worker_names)})")
    else:
        worker_names = []

    completed = 0
    completed_lock = threading.Lock()

    # Each thread claims one name on first use and keeps it for the run.
    name_iter = iter(worker_names)
    name_lock = threading.Lock()
    thread_local = threading.local()

    def _worker_name() -> str:
        name = getattr(thread_local, "name", None)
        if name is None:
            with name_lock:
                name = next(name_iter, "worker")
            thread_local.name = name
        return name

    def run_one(idx_item):
        idx, (story, prompt_record, biblical_text) = idx_item
        name = _worker_name()
        logger.info(
            f"[{name}] start [{idx + 1}/{total}]: "
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
        return name

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
                name = "?"
                try:
                    name = fut.result()
                except Exception as e:
                    logger.error(f"Worker error on combination #{idx + 1}: {e}")
                with completed_lock:
                    completed += 1
                    logger.info(
                        f"[{name}] done [{completed}/{total}]: "
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
        "--stories-file",
        default=None,
        help=(
            "Stories YAML file inside the data folder (default: stories.yml). "
            "Overrides PROPHECY_STORIES_FILE and prophecy.toml."
        ),
    )
    parser.add_argument(
        "--category",
        action="append",
        default=None,
        help="Filter results by prompt category. Repeatable or comma-separated.",
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


def _load_cached_results(cache_folder: Path, logger: logging.Logger) -> list[dict[str, Any]]:
    """Read every *.json file in the cache folder. Skip unreadable/non-result files.

    Each loaded record carries an extra ``_cache_id`` field set to the file
    stem (the MD5 hash used as the cache key). Downstream callers can surface
    it so users can navigate back to the source file on disk.
    """
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
        data["_cache_id"] = path.stem
        results.append(data)
    return results


def _resolve_prompt_meta(
    prompt_id: str, prompt_meta: dict[str, tuple[str, str]]
) -> tuple[str, str]:
    """Look up (category, topic) for a prompt id. Falls back for synthetic concat:* ids."""
    if prompt_id in prompt_meta:
        return prompt_meta[prompt_id]
    if prompt_id.startswith("concat:"):
        parts = prompt_id.split(":", 2)
        category = parts[1] if len(parts) > 1 and parts[1] else "concat"
        topic = parts[2] if len(parts) > 2 and parts[2] else "concat"
        return category, topic
    return "unknown", "unknown"


def _format_table(rows: list[dict[str, Any]]) -> str:
    """Render summary rows as a column-aligned text table."""
    if not rows:
        return "(no results)"

    columns = [
        ("story", "Story"),
        ("book", "Book"),
        ("category", "Category"),
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

    rendered = [{key: fmt(key, row[key]) for key, _ in columns} for row in rows]
    widths = {key: max(len(header), *(len(r[key]) for r in rendered)) for key, header in columns}
    header_line = "  ".join(header.ljust(widths[key]) for key, header in columns)
    sep_line = "  ".join("-" * widths[key] for key, _ in columns)
    body_lines = ["  ".join(r[key].ljust(widths[key]) for key, _ in columns) for r in rendered]
    return "\n".join([header_line, sep_line, *body_lines])


def query_command(argv: list[str]) -> int:
    """Entry point for `python -m prophecy query [...]`."""
    parser = _create_query_parser()
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbosity)

    try:
        settings = Settings.load(
            data_folder=args.data,
            cache_folder=args.cache_folder,
            stories_file=args.stories_file,
        )
        prompts = Prompts(data_folder=settings.data_folder)
        stories = Stories(
            data_folder=settings.data_folder,
            stories_file=settings.stories_file,
        )
    except FileNotFoundError as e:
        logger.error(f"{e}")
        return 1

    prompt_meta = {p["id"]: (p["category"], p["topic"]) for p in prompts.get_prompts()}
    story_book = {title: stories.get_story(title).book for title in stories.titles}

    cache_folder = settings.resolve_cache_folder()
    raw_results = _load_cached_results(cache_folder, logger)
    logger.info(f"Loaded {len(raw_results)} cached results from {cache_folder}")

    category_filter = parse_multi_value(args.category)
    topic_filter = parse_multi_value(args.topic)
    engine_filter = parse_multi_value(args.engine)

    # Case-insensitive normalization for category/topic/book/story. Engine ids
    # stay case-sensitive (they're identifiers like "chatgpt:gpt-4").
    try:
        if category_filter:
            category_filter = [
                normalize_known(p, prompts.get_categories(), "Category") for p in category_filter
            ]
        if topic_filter:
            topic_filter = [normalize_known(t, prompts.get_topics(), "Topic") for t in topic_filter]
        book_arg = args.book
        story_arg = args.story
        if book_arg:
            book_arg = normalize_known(book_arg, sorted(set(story_book.values())), "Book")
        if story_arg:
            story_arg = normalize_known(story_arg, list(story_book.keys()), "Story")
    except ValueError as e:
        logger.error(f"{e}")
        return 1

    # Aggregate by (story, category, topic, engine) — engine in the key so per-engine
    # answers stay separable. Pre-engine cached files surface as engine="unknown".
    agg: dict[tuple[str, str, str, str, str], dict[str, float]] = {}
    for r in raw_results:
        story_title = str(r["story"])
        prompt_id = str(r["prompt"])
        category, topic = _resolve_prompt_meta(prompt_id, prompt_meta)
        book = story_book.get(story_title, "unknown")
        certainty = r.get("certainty", 0) or 0
        engine = str(r.get("engine") or "unknown")

        if category_filter and category not in category_filter:
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

        key = (story_title, book, category, topic, engine)
        bucket = agg.setdefault(key, {"hits": 0, "total": 0, "cert_sum": 0.0})
        bucket["total"] += 1
        if r.get("answer"):
            bucket["hits"] += 1
        bucket["cert_sum"] += certainty

    summary = []
    for (story_title, book, category, topic, engine), bucket in agg.items():
        total = bucket["total"]
        summary.append(
            {
                "story": story_title,
                "book": book,
                "category": category,
                "topic": topic,
                "engine": engine,
                "hits": int(bucket["hits"]),
                "total": int(total),
                "hit_rate": (bucket["hits"] / total) if total else 0.0,
                "avg_certainty": (bucket["cert_sum"] / total) if total else 0.0,
            }
        )

    summary.sort(key=lambda r: (-r["hit_rate"], r["story"], r["category"], r["topic"], r["engine"]))

    if args.format == "json":
        print(json.dumps(summary, indent=2))
    elif args.format == "tsv":
        print("story\tbook\tcategory\ttopic\tengine\thits\ttotal\thit_rate\tavg_certainty")
        for row in summary:
            print(
                f"{row['story']}\t{row['book']}\t{row['category']}\t{row['topic']}\t{row['engine']}\t"
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
        "--stories-file",
        default=None,
        help=(
            "Stories YAML file inside the data folder (default: stories.yml). "
            "Overrides PROPHECY_STORIES_FILE and prophecy.toml."
        ),
    )
    parser.add_argument(
        "--out",
        default=None,
        help=(
            "Output folder for the static bundle. Overrides PROPHECY_EXPORT_OUT_FOLDER "
            "and the export_out_folder entry in prophecy.toml (default: dist/data)."
        ),
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
                                     book/category/topic so the viewer can
                                     filter without joining.
    """
    import datetime

    parser = _create_export_parser()
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbosity)

    try:
        settings = Settings.load(
            data_folder=args.data,
            cache_folder=args.cache_folder,
            stories_file=args.stories_file,
            export_out_folder=args.out,
        )
        prompts = Prompts(data_folder=settings.data_folder)
        stories = Stories(
            data_folder=settings.data_folder,
            stories_file=settings.stories_file,
        )
        # Bible is optional for the export — if the corpus isn't available
        # the bundle still ships, just without resolved story text.
        try:
            bible: Bible | None = Bible(data_folder=settings.data_folder)
        except FileNotFoundError:
            bible = None
            logger.info("No Bible corpus found in data folder — stories.json will omit text")
    except FileNotFoundError as e:
        logger.error(f"{e}")
        return 1

    out_root = settings.export_out_folder
    out_results = out_root / "results"
    out_root.mkdir(parents=True, exist_ok=True)
    out_results.mkdir(parents=True, exist_ok=True)

    prompt_meta = {p["id"]: (p["category"], p["topic"]) for p in prompts.get_prompts()}
    story_book = {title: stories.get_story(title).book for title in stories.titles}

    cache_folder = settings.resolve_cache_folder()
    raw_results = _load_cached_results(cache_folder, logger)
    logger.info(f"Loaded {len(raw_results)} cached results from {cache_folder}")

    # Group enriched rows by book. Cached results for stories that aren't in
    # the active stories YAML (e.g. left over from a previous catalog) are
    # silently dropped so the viewer's universe matches the YAML.
    by_book: dict[str, list[dict[str, Any]]] = {}
    facets_engines: set[str] = set()
    facets_categories: set[str] = set()
    facets_topics: set[str] = set()
    facets_stories: set[str] = set()
    result_count_by_prompt: dict[str, int] = {}
    known_stories = set(stories.titles)
    dropped_unknown = 0

    for r in raw_results:
        story_title = str(r.get("story", ""))
        if story_title not in known_stories:
            dropped_unknown += 1
            continue
        prompt_id = str(r.get("prompt", ""))
        category, topic = _resolve_prompt_meta(prompt_id, prompt_meta)
        book = story_book.get(story_title, "unknown")
        engine = str(r.get("engine") or "unknown")

        enriched = {
            "story": story_title,
            "book": book,
            "prompt": prompt_id,
            "category": category,
            "topic": topic,
            "engine": engine,
            "answer": bool(r.get("answer", False)),
            "certainty": int(r.get("certainty", 0) or 0),
            "reason": r.get("reason", ""),
        }
        by_book.setdefault(book, []).append(enriched)
        facets_engines.add(engine)
        facets_categories.add(category)
        facets_topics.add(topic)
        if story_title:
            facets_stories.add(story_title)
        if prompt_id:
            result_count_by_prompt[prompt_id] = result_count_by_prompt.get(prompt_id, 0) + 1

    if dropped_unknown:
        logger.info(
            f"Dropped {dropped_unknown} cached results for stories not in "
            f"{settings.stories_folder}/{settings.stories_file}"
        )

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
                "categories": sorted({r["category"] for r in rows}),
                "topics": sorted({r["topic"] for r in rows}),
            }
        )
        logger.debug(f"Wrote {len(rows)} rows to {shard_path}")

    # Write prompts.json (the full TSV as a JSON array).
    prompts_json_path = out_root / "prompts.json"
    with open(prompts_json_path, "w", encoding="utf-8") as f:
        json.dump(prompts.get_prompts(), f, separators=(",", ":"))

    # Write stories.json (title -> {book, verses, sources?, text?}). ``sources``
    # is optional in the YAML and is emitted only when present. ``text`` is the
    # resolved biblical text for the verse ranges, populated when a Bible
    # corpus is available so the viewer can show the full passage inline.
    stories_json_path = out_root / "stories.json"
    stories_payload: dict[str, dict[str, Any]] = {}
    text_failures = 0
    for title in stories.titles:
        story = stories.get_story(title)
        entry: dict[str, Any] = {"book": story.book, "verses": story.verses}
        if story.sources:
            entry["sources"] = story.sources
        if bible is not None:
            try:
                entry["text"] = bible.get_text(story.book, *story.to_bible_parts())
            except Exception as e:
                text_failures += 1
                logger.debug(f"Could not resolve text for {title}: {e}")
        stories_payload[title] = entry
    with open(stories_json_path, "w", encoding="utf-8") as f:
        json.dump(stories_payload, f, separators=(",", ":"))
    if bible is not None and text_failures:
        logger.warning(f"stories.json: {text_failures} stories without resolved text")

    # If labels.json exists alongside the data folder, copy it into the bundle
    # so the viewer can read it as a sibling of prompts.json / stories.json.
    labels_src = Path(settings.data_folder) / "labels.json"
    labels_included = False
    if labels_src.exists():
        labels_dst = out_root / "labels.json"
        with open(labels_src, encoding="utf-8") as fsrc:
            labels_data = json.load(fsrc)
        with open(labels_dst, "w", encoding="utf-8") as fdst:
            json.dump(labels_data, fdst, separators=(",", ":"))
        labels_included = True
        logger.info(f"Bundled labels.json ({labels_data.get('label_count', '?')} entries)")
    else:
        logger.info("No data/labels.json found — viewer Labels tab will be empty")

    # Write the manifest.
    manifest_files = {
        "prompts": "prompts.json",
        "stories": "stories.json",
        "results_dir": "results/",
    }
    if labels_included:
        manifest_files["labels"] = "labels.json"

    manifest = {
        "generated_at": datetime.datetime.now(datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "total_results": sum(s["row_count"] for s in shards),
        "books": [s["book"] for s in shards],
        "stories": sorted(facets_stories),
        "engines": sorted(facets_engines),
        "categories": sorted(facets_categories),
        "topics": sorted(facets_topics),
        "used_prompt_ids": sorted(result_count_by_prompt.keys()),
        "result_count_by_prompt": dict(sorted(result_count_by_prompt.items())),
        "shards": shards,
        "files": manifest_files,
    }
    with open(out_root / "index.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(
        f"Exported {manifest['total_results']} results across {len(shards)} book shards "
        f"to {out_root}"
    )
    return 0


def _create_label_parser() -> argparse.ArgumentParser:
    """Argparse parser for the 'label' subcommand."""
    parser = argparse.ArgumentParser(
        description=(
            "Compute per-story labels from cached results. A label is a "
            "(category, topic) pair from prompts.tsv; a story carries a label "
            "if at least one prompt in that group came back true. Writes a "
            "single JSON file the viewer (or any other tool) can read."
        ),
        prog="python -m prophecy label",
    )
    parser.add_argument("--data", help="Path to data folder (overrides PROPHECY_DATA_FOLDER)")
    parser.add_argument("--cache-folder", help="Path to cache folder (defaults to data/results)")
    parser.add_argument(
        "--stories-file",
        default=None,
        help=(
            "Stories YAML file inside the data folder (default: stories.yml). "
            "Overrides PROPHECY_STORIES_FILE and prophecy.toml."
        ),
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: <data>/labels.json)",
    )
    parser.add_argument(
        "--book",
        action="append",
        default=None,
        help="Restrict to stories in these books. Repeatable or comma-separated.",
    )
    parser.add_argument(
        "--engine",
        action="append",
        default=None,
        help="Restrict to these engines. Repeatable or comma-separated.",
    )
    parser.add_argument(
        "--exclude-category",
        action="append",
        default=None,
        help=(
            "Skip these categories at generation time (e.g. 'Test' for the "
            "placeholder category). Repeatable or comma-separated, case-insensitive."
        ),
    )
    parser.add_argument(
        "--verbosity",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging verbosity (default: INFO)",
    )
    return parser


def label_command(argv: list[str]) -> int:
    """
    Entry point for `python -m prophecy label [...]`.

    Walks the result cache, joins with prompts.tsv for category/topic/text,
    and writes a flat JSON list of label entries — one per (story, engine,
    category, topic) group that has at least one hit.
    """
    import datetime

    parser = _create_label_parser()
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbosity)

    try:
        settings = Settings.load(
            data_folder=args.data,
            cache_folder=args.cache_folder,
            stories_file=args.stories_file,
        )
        prompts = Prompts(data_folder=settings.data_folder)
        stories = Stories(
            data_folder=settings.data_folder,
            stories_file=settings.stories_file,
        )
    except FileNotFoundError as e:
        logger.error(f"{e}")
        return 1

    # category/topic AND the prompt text — viewer wants to render the
    # statement inline so it doesn't have to join against prompts.json.
    prompt_meta = {
        p["id"]: {"category": p["category"], "topic": p["topic"], "prompt": p["prompt"]}
        for p in prompts.get_prompts()
    }
    story_book = {title: stories.get_story(title).book for title in stories.titles}
    available_books = sorted(set(story_book.values()))

    book_filter = parse_multi_value(args.book)
    engine_filter = parse_multi_value(args.engine)
    exclude_categories_raw = parse_multi_value(args.exclude_category)
    try:
        if book_filter:
            book_filter = [normalize_known(b, available_books, "Book") for b in book_filter]
        # Case-insensitive normalisation against the prompts.tsv vocabulary.
        exclude_categories: set[str] = set()
        if exclude_categories_raw:
            for cat in exclude_categories_raw:
                exclude_categories.add(normalize_known(cat, prompts.get_categories(), "Category"))
    except ValueError as e:
        logger.error(f"{e}")
        return 1

    cache_folder = settings.resolve_cache_folder()
    raw_results = _load_cached_results(cache_folder, logger)
    logger.info(f"Loaded {len(raw_results)} cached results from {cache_folder}")

    # Stories outside the active YAML are dropped — matches the export's
    # behavior so the bundle and the labels share the same universe.
    known_stories = set(stories.titles)
    dropped_unknown = 0

    # group key -> aggregated bucket
    groups: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    for r in raw_results:
        prompt_id = str(r.get("prompt", ""))
        # Concat:* synthetic ids represent a single combined LLM call, not
        # individual statements; they don't fit the per-prompt scoring model.
        if prompt_id.startswith("concat:"):
            continue

        meta = prompt_meta.get(prompt_id)
        if meta is None:
            # Orphan result (prompt id no longer in prompts.tsv). Skip rather
            # than fabricate a label.
            continue
        if meta["category"] in exclude_categories:
            continue

        story_title = str(r.get("story", ""))
        if not story_title:
            continue
        if story_title not in known_stories:
            dropped_unknown += 1
            continue
        book = story_book.get(story_title, "unknown")
        engine = str(r.get("engine") or "unknown")

        if book_filter and book not in book_filter:
            continue
        if engine_filter and engine not in engine_filter:
            continue

        key = (story_title, book, engine, meta["category"], meta["topic"])
        bucket = groups.setdefault(
            key,
            {
                "story": story_title,
                "book": book,
                "engine": engine,
                "category": meta["category"],
                "topic": meta["topic"],
                "hits": 0,
                "total": 0,
                "cert_sum": 0,
                "prompts": [],
            },
        )
        answer = bool(r.get("answer", False))
        certainty = int(r.get("certainty", 0) or 0)
        bucket["total"] += 1
        if answer:
            bucket["hits"] += 1
        bucket["cert_sum"] += certainty
        # Pull the cache id (last 8 chars are enough to navigate by — the full
        # stem stays in the cache filename) and the rationale text so the
        # viewer can show provenance + reasoning without re-reading the cache.
        cache_id = str(r.get("_cache_id", ""))
        bucket["prompts"].append(
            {
                "id": prompt_id,
                "answer": answer,
                "certainty": certainty,
                "prompt": meta["prompt"],
                "cache_id": cache_id,
                "reason": str(r.get("reason", "")),
            }
        )

    # Emit every group, including those with zero hits. The viewer hides the
    # zero-hit ("not attributed") ones by default; surfacing them here lets
    # users opt-in without re-running label.
    label_entries = []
    for bucket in groups.values():
        total = bucket["total"]
        # Sort prompts inside the group: true answers first, then by certainty desc.
        bucket["prompts"].sort(key=lambda p: (not p["answer"], -p["certainty"]))
        label_entries.append(
            {
                "story": bucket["story"],
                "book": bucket["book"],
                "engine": bucket["engine"],
                "category": bucket["category"],
                "topic": bucket["topic"],
                "hits": bucket["hits"],
                "total": total,
                "attributed": bucket["hits"] > 0,
                "avg_certainty": round(bucket["cert_sum"] / total, 1) if total else 0.0,
                "prompts": bucket["prompts"],
            }
        )

    # Deterministic order so the file diffs cleanly across runs.
    label_entries.sort(
        key=lambda r: (r["book"], r["story"], r["category"], r["topic"], r["engine"])
    )

    out_path = Path(args.out) if args.out else Path(settings.data_folder) / "labels.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.datetime.now(datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "label_count": len(label_entries),
        "labels": label_entries,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))

    distinct_stories = len({(e["story"], e["engine"]) for e in label_entries})
    attributed = sum(1 for e in label_entries if e["attributed"])
    logger.info(
        f"Wrote {len(label_entries)} label entries ({attributed} attributed, "
        f"{len(label_entries) - attributed} non-attributed) across "
        f"{distinct_stories} (story, engine) pairs to {out_path}"
    )
    if dropped_unknown:
        logger.info(
            f"Dropped {dropped_unknown} cached results for stories not in "
            f"{settings.stories_folder}/{settings.stories_file}"
        )
    return 0


def _create_prune_parser() -> argparse.ArgumentParser:
    """Argparse parser for the 'prune' subcommand."""
    parser = argparse.ArgumentParser(
        description=(
            "Delete cached result JSON files. Two orthogonal modes: --engine "
            "deletes by stored engine field (clears legacy 'unknown'-engine "
            "entries); --by-hash recomputes each file's expected MD5 from "
            "current prompts.tsv + stories + Bible and deletes mismatches "
            "(invalidates stale results after editing prompts). Pass at "
            "least one of --engine or --by-hash so 'delete everything' "
            "isn't a default."
        ),
        prog="python -m prophecy prune",
    )
    parser.add_argument("--data", help="Path to data folder (overrides PROPHECY_DATA_FOLDER)")
    parser.add_argument("--cache-folder", help="Path to cache folder (defaults to data/results)")
    parser.add_argument(
        "--engine",
        action="append",
        default=None,
        help=(
            "Delete cache files whose engine field matches one of these "
            "values. Repeatable or comma-separated. Use 'unknown' to catch "
            "files that have engine='unknown' OR no engine field at all. "
            "With --by-hash, restricts the hash check to these engines."
        ),
    )
    parser.add_argument(
        "--by-hash",
        action="store_true",
        help=(
            "Delete cache files whose stored (story, prompt id, engine) no "
            "longer hashes to the cache filename. Catches results left over "
            "after prompts.tsv or stories.yml changed. Synthetic concat:* "
            "ids are preserved (can't recompute their bundle)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List which files would be deleted, but don't actually delete them.",
    )
    parser.add_argument(
        "--verbosity",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging verbosity (default: INFO)",
    )
    return parser


def prune_command(argv: list[str]) -> int:
    """Entry point for `python -m prophecy prune [...]`."""
    parser = _create_prune_parser()
    args = parser.parse_args(argv)
    logger = setup_logging(args.verbosity)

    if not args.by_hash and not args.engine:
        parser.error("Pass --engine or --by-hash (or both).")

    settings = Settings.load(data_folder=args.data, cache_folder=args.cache_folder)
    cache_folder = settings.resolve_cache_folder()
    if not cache_folder.exists():
        logger.error(f"Cache folder does not exist: {cache_folder}")
        return 1

    engine_filter = set(parse_multi_value(args.engine) or [])
    catch_unknown = "unknown" in engine_filter

    # --by-hash needs the current TSV + stories + bible so it can recompute
    # what each cache file *should* hash to under today's data. Loaded once,
    # biblical text memoized per story (cache folders typically have many
    # entries per story).
    prompts_obj = None
    stories_obj = None
    bible_text_cache: dict[str, str | None] = {}
    prompts_by_id: dict[str, dict[str, str]] = {}
    if args.by_hash:
        stories_obj, prompts_obj, bible_obj = initialize_components(settings, logger)
        prompts_by_id = {p["id"]: p for p in prompts_obj.get_prompts()}

        def _biblical_text(story_title: str) -> str | None:
            if story_title in bible_text_cache:
                return bible_text_cache[story_title]
            try:
                story = stories_obj.get_story(story_title)
            except Exception:
                bible_text_cache[story_title] = None
                return None
            text = get_biblical_text(bible_obj, story, logger)
            bible_text_cache[story_title] = text
            return text

    deleted = 0
    skipped = 0
    inspected = 0
    kept_fresh = 0
    for path in sorted(cache_folder.glob("*.json")):
        inspected += 1
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.debug(f"Skipping unreadable cache file {path}: {e}")
            skipped += 1
            continue
        if not isinstance(data, dict):
            skipped += 1
            continue

        engine = data.get("engine")
        engine_str = str(engine) if engine is not None else None
        is_unknown = engine_str is None or engine_str == "unknown"

        # --engine alone gates the deletion; with --by-hash it scopes which
        # files get hash-checked (non-matching files are left alone).
        if engine_filter:
            engine_matches = (catch_unknown and is_unknown) or (
                engine_str is not None and engine_str in engine_filter
            )
            if not engine_matches:
                continue

        reason: str | None = None
        if args.by_hash:
            # prompts_obj/stories_obj are populated whenever args.by_hash is
            # set (initialized above); the assert tells the type checker.
            assert prompts_obj is not None and stories_obj is not None
            prompt_id = str(data.get("prompt", ""))
            story_title = str(data.get("story", ""))
            if prompt_id.startswith("concat:"):
                # Synthetic concat ids can't be recomputed without knowing the
                # exact prompt bundle that produced them. Preserve.
                continue
            if not prompt_id:
                reason = "missing prompt id"
            elif prompt_id not in prompts_by_id:
                reason = f"orphan prompt id {prompt_id!r}"
            else:
                text = _biblical_text(story_title)
                if text is None:
                    reason = f"orphan story {story_title!r}"
                else:
                    try:
                        populated = prompts_obj.populate_template(
                            prompts_by_id[prompt_id],
                            stories_obj.get_story(story_title),
                            text,
                        )
                        expected = calculate_template_checksum(populated, engine_str)
                    except Exception as e:
                        reason = f"recompute failed: {e}"
                    else:
                        if expected != path.stem:
                            reason = (
                                f"hash mismatch (have {path.stem[:8]}…, expected {expected[:8]}…)"
                            )
            if reason is None:
                kept_fresh += 1
                continue
        else:
            reason = f"engine match ({engine_str!r})"

        if args.dry_run:
            logger.info(f"Would delete: {path.name} — {reason}")
        else:
            path.unlink()
            logger.debug(f"Deleted: {path.name} — {reason}")
        deleted += 1

    verb = "Would delete" if args.dry_run else "Deleted"
    suffix = f", {kept_fresh} fresh" if args.by_hash else ""
    logger.info(
        f"{verb} {deleted} of {inspected} files in {cache_folder} "
        f"(skipped {skipped} unreadable{suffix})"
    )
    return 0


def main():
    """Main CLI entry point."""
    # Dispatch subcommands without touching the run pipeline.
    argv = sys.argv[1:]
    if argv and argv[0] == "query":
        sys.exit(query_command(argv[1:]))
    if argv and argv[0] == "export":
        sys.exit(export_command(argv[1:]))
    if argv and argv[0] == "label":
        sys.exit(label_command(argv[1:]))
    if argv and argv[0] == "prune":
        sys.exit(prune_command(argv[1:]))

    parser = create_argument_parser()
    args = parser.parse_args()

    # Set up logging
    logger = setup_logging(args.verbosity)

    try:
        # Build a Settings once from CLI flags + env + ./prophecy.toml,
        # then thread it through the pipeline.
        settings = Settings.load(
            data_folder=args.data,
            cache_folder=args.cache_folder,
            stories_file=args.stories_file,
            workers=args.workers,
            ai_provider=args.ai_provider,
        )

        stories, prompts, bible = initialize_components(settings, logger)
        story_titles, prompt_list = validate_inputs(stories, prompts, args, logger)
        ai_provider = initialize_ai_provider(args, settings, logger)
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
