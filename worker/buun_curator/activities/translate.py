"""
Translate Activities for Temporal.

Activities for entry translation operations.
"""

import asyncio
from typing import Any

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    GetEntriesForTranslationInput,
    GetEntriesForTranslationOutput,
    SaveTranslationsInput,
    SaveTranslationsOutput,
)
from buun_curator.services.api import APIClient

logger = get_logger(__name__)


def _html_to_markdown(html: str) -> str:
    """
    Convert HTML to clean Markdown using Crawl4AI's markdown generator.

    Uses the same PruningContentFilter and excluded_tags as ContentFetcher
    to produce clean, content-focused Markdown.

    Parameters
    ----------
    html : str
        HTML content.

    Returns
    -------
    str
        Clean Markdown content.
    """
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    if not html or not html.strip():
        return ""

    try:
        # Use PruningContentFilter with same settings as ContentFetcher hybrid mode
        content_filter = PruningContentFilter(
            threshold=0.3,
            threshold_type="dynamic",
            min_word_threshold=None,  # type: ignore[arg-type]
        )

        generator = DefaultMarkdownGenerator(
            content_filter=content_filter,
            options={
                "body_width": 0,  # No line wrapping
                "ignore_images": True,  # Skip image references for translation
            },
        )

        result = generator.generate_markdown(
            input_html=html,
            citations=False,
        )

        # Use filtered (fit_markdown) if available and substantial,
        # otherwise fall back to raw_markdown
        filtered = result.fit_markdown or ""
        raw = result.raw_markdown or ""

        if len(filtered) >= 100:
            return filtered.strip()
        return raw.strip()

    except Exception as e:
        logger.warning(
            f"Failed to convert HTML to Markdown: {e}",
            error_type=type(e).__name__,
        )
        return ""


def _get_content_for_translation(entry: dict) -> tuple[str, bool]:
    """
    Get content for translation from an entry.

    Uses the same logic as the frontend ContentViewer:
    1. If feedContent is >= 1000 chars, use feedContent (HTML)
    2. If filteredContent exists, use filteredContent (Markdown)
    3. If fullContent exists, use fullContent (Markdown)
    4. Fall back to feedContent (HTML)

    Parameters
    ----------
    entry : dict
        Entry data from API.

    Returns
    -------
    tuple[str, bool]
        Content suitable for translation and is_html flag.
        is_html=True means content is HTML (feedContent).
        is_html=False means content is Markdown (filteredContent/fullContent).
    """
    feed_content = entry.get("feedContent") or ""
    filtered_content = entry.get("filteredContent") or ""
    full_content = entry.get("fullContent") or ""

    # Priority 1: feedContent if >= 1000 chars
    if feed_content.strip() and len(feed_content) >= 1000:
        return feed_content, True

    # Priority 2: filteredContent (Markdown, cleaned content)
    if filtered_content.strip():
        return filtered_content, False

    # Priority 3: fullContent (Markdown)
    if full_content.strip():
        return full_content, False

    # Fallback: feedContent (HTML)
    if feed_content.strip():
        return feed_content, True

    return "", False


@activity.defn
async def get_entries_for_translation(
    input: GetEntriesForTranslationInput,
) -> GetEntriesForTranslationOutput:
    """
    Get entries that need translation.

    Parameters
    ----------
    input : GetEntriesForTranslationInput
        Input containing optional entry_ids to filter.

    Returns
    -------
    GetEntriesForTranslationOutput
        Output containing list of entry dicts with is_html flag.
    """
    config = get_config()

    async with APIClient(config.api_url, config.api_token) as api:
        if input.entry_ids:
            # Get specific entries in parallel
            async def get_single_entry(entry_id: str) -> dict | None:
                entry = await api.get_entry(entry_id)
                if "error" not in entry and entry:
                    content, is_html = _get_content_for_translation(entry)
                    if content:
                        return {
                            "entry_id": entry_id,
                            "title": entry.get("title", ""),
                            "url": entry.get("url", ""),
                            "full_content": content,
                            "is_html": is_html,
                        }
                return None

            tasks = [get_single_entry(eid) for eid in input.entry_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            result_entries: list[dict[str, Any]] = [
                r for r in results if r is not None and not isinstance(r, BaseException)
            ]
            return GetEntriesForTranslationOutput(entries=result_entries)
        else:
            # Get untranslated entries (entries with content but no translation)
            api_entries = await api.list_entries(has_translation=False, limit=100)
            result_entries: list[dict[str, Any]] = []
            for entry in api_entries:
                content, is_html = _get_content_for_translation(entry)
                if content:
                    result_entries.append(
                        {
                            "entry_id": str(entry["id"]),
                            "title": entry.get("title", ""),
                            "url": entry.get("url", ""),
                            "full_content": content,
                            "is_html": is_html,
                        }
                    )
            return GetEntriesForTranslationOutput(entries=result_entries)


@activity.defn
async def save_translations(input: SaveTranslationsInput) -> SaveTranslationsOutput:
    """
    Save translations to database via REST API.

    Parameters
    ----------
    input : SaveTranslationsInput
        Input containing list of translation dicts.

    Returns
    -------
    SaveTranslationsOutput
        Output containing saved_count.
    """
    if not input.translations:
        return SaveTranslationsOutput()

    config = get_config()
    total = len(input.translations)

    activity.heartbeat(f"Saving {total} translations")

    async with APIClient(config.api_url, config.api_token) as api:

        async def save_single_translation(t: dict) -> bool:
            """Save a single translation and return success status."""
            if not t.get("translated_content"):
                return False

            # Include trace_id in metadata if present
            metadata = None
            if t.get("trace_id"):
                metadata = {"translateTraceId": t["trace_id"]}

            try:
                await api.update_entry(
                    t["entry_id"],
                    translated_content=t["translated_content"],
                    metadata=metadata,
                )
                return True
            except Exception as e:
                logger.warning(
                    f"Failed to save translation: {e}",
                    entry_id=t["entry_id"],
                    error_type=type(e).__name__,
                )
                return False

        # Run all saves concurrently
        tasks = [save_single_translation(t) for t in input.translations]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        saved_count = sum(1 for r in results if r is True and not isinstance(r, Exception))
        activity.heartbeat(f"Saved {saved_count}/{total} translations")

    logger.info("Saved translations", saved_count=saved_count, total=total)
    return SaveTranslationsOutput(saved_count=saved_count)
