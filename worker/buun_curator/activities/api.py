"""
API Activities for Temporal.

Activities for REST API server operations.
"""

import asyncio
from typing import Any

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    GetAppSettingsInput,
    GetAppSettingsOutput,
    GetEntriesInput,
    GetEntriesOutput,
    GetEntryInput,
    GetEntryOutput,
    ListUnsummarizedEntryIdsInput,
    ListUnsummarizedEntryIdsOutput,
    SaveEntryContextInput,
    SaveEntryContextOutput,
)
from buun_curator.services.api import APIClient

logger = get_logger(__name__)


@activity.defn
async def get_entry(input: GetEntryInput) -> GetEntryOutput:
    """
    Get entry details from REST API.

    Parameters
    ----------
    input : GetEntryInput
        Input containing entry_id.

    Returns
    -------
    GetEntryOutput
        Output containing entry dict.
    """
    config = get_config()

    async with APIClient(config.api_url, config.api_token) as api:
        entry = await api.get_entry(input.entry_id)

    return GetEntryOutput(entry=entry)


@activity.defn
async def get_entries(input: GetEntriesInput) -> GetEntriesOutput:
    """
    Get multiple entries from REST API.

    Parameters
    ----------
    input : GetEntriesInput
        Input containing list of entry_ids.

    Returns
    -------
    GetEntriesOutput
        Output containing list of entry dicts (includes feed extraction_rules).
    """
    config = get_config()
    entries: list[dict[str, Any]] = []
    # Cache feeds to avoid repeated fetches
    feed_cache: dict[str, dict] = {}

    async with APIClient(config.api_url, config.api_token) as api:
        # Fetch entries in parallel
        async def fetch_entry(entry_id: str) -> dict[str, Any] | None:
            entry = await api.get_entry(entry_id)
            if "error" in entry or not entry:
                return None

            feed_id = entry.get("feedId", "")

            # Get feed details (cached)
            extraction_rules = None
            if feed_id:
                if feed_id not in feed_cache:
                    feed_cache[feed_id] = await api.get_feed(feed_id)
                feed = feed_cache[feed_id]
                options = feed.get("options")
                if options and isinstance(options, dict):
                    extraction_rules = options.get("extractionRules")

            return {
                "id": entry_id,
                "entry_id": entry_id,
                "feed_id": feed_id,
                "feed_name": entry.get("feedName", "Unknown"),
                "title": entry.get("title", "Unknown"),
                "url": entry.get("url", ""),
                "feed_content": entry.get("feedContent", ""),
                "full_content": entry.get("fullContent", ""),
                "filteredContent": entry.get("filteredContent", ""),
                "author": entry.get("author", ""),
                "published_at": entry.get("publishedAt"),
                "extraction_rules": extraction_rules,
            }

        tasks = [fetch_entry(eid) for eid in input.entry_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, BaseException):
                logger.warning(f"Failed to fetch entry: {result}")
                continue
            if result is not None:
                entries.append(result)

    return GetEntriesOutput(entries=entries)


@activity.defn
async def list_unsummarized_entry_ids(
    input: ListUnsummarizedEntryIdsInput,
) -> ListUnsummarizedEntryIdsOutput:
    """
    Get IDs of entries that don't have summaries.

    Parameters
    ----------
    input : ListUnsummarizedEntryIdsInput
        Input containing limit for query.

    Returns
    -------
    ListUnsummarizedEntryIdsOutput
        Output containing list of entry_ids.
    """
    config = get_config()

    async with APIClient(config.api_url, config.api_token) as api:
        entries = await api.list_entries(has_summary=False, limit=input.limit)

    entry_ids = [str(e["id"]) for e in entries if e.get("fullContent") or e.get("filteredContent")]
    logger.info("Found unsummarized entries with content", count=len(entry_ids))

    return ListUnsummarizedEntryIdsOutput(entry_ids=entry_ids)


@activity.defn
async def get_app_settings(_input: GetAppSettingsInput) -> GetAppSettingsOutput:
    """
    Get application settings from REST API and environment config.

    Parameters
    ----------
    input : GetAppSettingsInput
        Input (no parameters needed).

    Returns
    -------
    GetAppSettingsOutput
        Output containing target_language setting and workflow config.
    """
    config = get_config()

    async with APIClient(config.api_url, config.api_token) as api:
        settings = await api.get_settings()

    target_language = settings.get("targetLanguage", "")
    logger.info(
        "Got app settings",
        target_language=target_language,
        auto_distill=config.enable_summarization,
        enable_content_fetch=config.enable_content_fetch,
        max_concurrent=config.feed_ingestion_concurrency,
        enable_thumbnail=config.enable_thumbnail,
        domain_fetch_delay=config.domain_fetch_delay,
    )

    return GetAppSettingsOutput(
        target_language=target_language,
        auto_distill=config.enable_summarization,
        enable_content_fetch=config.enable_content_fetch,
        max_concurrent=config.feed_ingestion_concurrency,
        enable_thumbnail=config.enable_thumbnail,
        domain_fetch_delay=config.domain_fetch_delay,
    )


@activity.defn
async def save_entry_context(input: SaveEntryContextInput) -> SaveEntryContextOutput:
    """
    Save context data for an entry via REST API.

    Parameters
    ----------
    input : SaveEntryContextInput
        Input containing entry_id and context dict.

    Returns
    -------
    SaveEntryContextOutput
        Output with success status and optional error message.
    """
    config = get_config()

    async with APIClient(config.api_url, config.api_token) as api:
        result = await api.save_entry_context(input.entry_id, input.context)

    if "error" in result:
        logger.error(f"Failed to save context: {result['error']}", entry_id=input.entry_id)
        return SaveEntryContextOutput(success=False, error=result["error"])

    logger.info("Saved context for entry", entry_id=input.entry_id)
    return SaveEntryContextOutput(success=True)
