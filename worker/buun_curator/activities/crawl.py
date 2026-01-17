"""
Crawl Activities for Temporal.

Activities for feed crawling operations.
"""

from typing import Any

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    CrawlFeedsInput,
    CrawlFeedsOutput,
    CrawlSingleFeedInput,
    CrawlSingleFeedOutput,
    GetFeedOptionsInput,
    GetFeedOptionsOutput,
    ListFeedsInput,
    ListFeedsOutput,
)
from buun_curator.services.api import APIClient
from buun_curator.services.feed import FeedCrawler
from buun_curator.utils.youtube import extract_youtube_video_id

logger = get_logger(__name__)


@activity.defn
async def crawl_feeds(_input: CrawlFeedsInput) -> CrawlFeedsOutput:
    """
    Crawl all registered feeds.

    Parameters
    ----------
    _input : CrawlFeedsInput
        Input parameters (currently empty, for future extensibility).

    Returns
    -------
    CrawlFeedsOutput
        Output containing feeds processed and new entries created.
    """
    config = get_config()
    logger.info("Starting feed crawl", api_url=config.api_url)

    async with APIClient(config.api_url, config.api_token) as api:
        crawler = FeedCrawler(api)
        result = await crawler.crawl_all(on_progress=activity.heartbeat)

    activity.heartbeat(
        f"Completed: {result.feeds_processed} processed, {result.entries_created} new entries"
    )
    logger.info(
        "Crawl completed",
        feeds_processed=result.feeds_processed,
        entries_created=result.entries_created,
    )

    return CrawlFeedsOutput(
        feeds_processed=result.feeds_processed,
        feeds_skipped=result.feeds_skipped,
        entries_created=result.entries_created,
        entries_skipped=result.entries_skipped,
        new_entries=result.new_entries,
        feed_details=result.feed_details,
        entry_details=result.entry_details,
    )


@activity.defn
async def list_feeds(_input: ListFeedsInput) -> ListFeedsOutput:
    """
    List all registered feeds with their details.

    Parameters
    ----------
    _input : ListFeedsInput
        Input parameters (currently empty, for future extensibility).

    Returns
    -------
    ListFeedsOutput
        Output containing list of feeds with their configurations.
    """
    config = get_config()
    logger.info("Listing feeds", api_url=config.api_url)

    async with APIClient(config.api_url, config.api_token) as api:
        feeds = await api.list_feeds()

        # Enrich with feed details (etag, lastModified, fetchContent, fetchLimit)
        enriched_feeds: list[dict[str, Any]] = []
        for feed in feeds:
            feed_id = str(feed["id"])
            feed_detail = await api.get_feed(feed_id)

            # Get fields directly from feed detail
            fetch_limit = feed_detail.get("fetchLimit", 20)
            fetch_content = feed_detail.get("fetchContent", True)

            # extractionRules is still in options
            options = feed_detail.get("options")
            extraction_rules: list[dict] | None = None
            if options and isinstance(options, dict):
                extraction_rules = options.get("extractionRules")

            feed_name = feed.get("name", "Unknown")
            logger.debug(
                "list_feeds",
                feed_name=feed_name,
                fetch_limit=fetch_limit,
                fetch_content=fetch_content,
            )
            enriched_feeds.append(
                {
                    "id": feed_id,
                    "name": feed_name,
                    "url": feed.get("url", ""),
                    "etag": feed_detail.get("etag", "") or "",
                    "last_modified": feed_detail.get("lastModified", "") or "",
                    "fetch_limit": fetch_limit,
                    "fetch_content": fetch_content,
                    "extraction_rules": extraction_rules,
                }
            )

    logger.info("Found feeds", count=len(enriched_feeds))
    return ListFeedsOutput(feeds=enriched_feeds)


@activity.defn
async def get_feed_options(input: GetFeedOptionsInput) -> GetFeedOptionsOutput:
    """
    Get feed options (fetch_limit, fetch_content, extraction_rules) from API.

    Parameters
    ----------
    input : GetFeedOptionsInput
        Input containing feed ID.

    Returns
    -------
    GetFeedOptionsOutput
        Output containing feed options.
    """
    config = get_config()
    feed_id = input.feed_id

    logger.debug("get_feed_options: fetching options", feed_id=feed_id)

    async with APIClient(config.api_url, config.api_token) as api:
        feed_detail = await api.get_feed(feed_id)

        # Get fields directly from feed detail
        fetch_limit = feed_detail.get("fetchLimit", 20)
        fetch_content = feed_detail.get("fetchContent", True)

        # extractionRules is still in options
        options = feed_detail.get("options")
        extraction_rules: list[dict] | None = None
        if options and isinstance(options, dict):
            extraction_rules = options.get("extractionRules")

        logger.debug(
            "get_feed_options",
            feed_id=feed_id,
            fetch_limit=fetch_limit,
            fetch_content=fetch_content,
        )

        return GetFeedOptionsOutput(
            feed_id=feed_id,
            fetch_limit=fetch_limit,
            fetch_content=fetch_content,
            extraction_rules=extraction_rules,
        )


@activity.defn
async def crawl_single_feed(input: CrawlSingleFeedInput) -> CrawlSingleFeedOutput:
    """
    Crawl a single feed and create entries.

    Parameters
    ----------
    input : CrawlSingleFeedInput
        Input containing feed ID, URL, and cache headers.

    Returns
    -------
    CrawlSingleFeedOutput
        Output containing crawl results for this feed.
    """
    import asyncio
    import time

    activity_start = time.perf_counter()
    config = get_config()
    feed_id = input.feed_id
    feed_name = input.feed_name
    feed_url = input.feed_url

    logger.info(
        "crawl_single_feed start",
        feed_name=feed_name,
        feed_id=feed_id,
        fetch_limit=input.fetch_limit,
    )
    logger.debug(
        "crawl_single_feed details",
        url=feed_url,
        etag=input.etag,
        last_modified=input.last_modified,
    )

    if not feed_url:
        logger.warning("Feed has no URL, skipping", feed_id=feed_id)
        return CrawlSingleFeedOutput(
            feed_id=feed_id,
            feed_name=feed_name,
            status="error",
            error="No URL configured",
        )

    logger.debug("crawl_single_feed: connecting to API...")
    async with APIClient(config.api_url, config.api_token) as api:
        api_connect_elapsed = (time.perf_counter() - activity_start) * 1000
        logger.debug("crawl_single_feed: API connected", elapsed_ms=f"{api_connect_elapsed:.1f}")

        # Use FeedCrawler to fetch feed content
        logger.debug("crawl_single_feed: fetching feed content...")
        fetch_start = time.perf_counter()
        crawler = FeedCrawler(api)
        feed_result = crawler.fetch_feed_content(
            feed_url,
            input.fetch_limit,
            input.etag,
            input.last_modified,
            max_entry_age_days=input.max_entry_age_days,
        )
        fetch_elapsed = (time.perf_counter() - fetch_start) * 1000
        logger.debug(
            "crawl_single_feed: feed fetched",
            elapsed_ms=f"{fetch_elapsed:.1f}",
            success=feed_result.get("success"),
            not_modified=feed_result.get("not_modified"),
            entries=len(feed_result.get("entries", [])),
        )

        if not feed_result["success"]:
            logger.error(
                f"Failed to fetch feed: {feed_result.get('error')}",
                feed_name=feed_name,
            )
            return CrawlSingleFeedOutput(
                feed_id=feed_id,
                feed_name=feed_name,
                status="error",
                error=feed_result.get("error", "Unknown error"),
            )

        if feed_result["not_modified"]:
            # Still update checkedAt
            await api.update_feed_checked(
                feed_id,
                input.etag,
                input.last_modified,
            )
            return CrawlSingleFeedOutput(
                feed_id=feed_id,
                feed_name=feed_name,
                status="skipped",
                new_etag=input.etag,
                new_last_modified=input.last_modified,
            )

        # Create entries in parallel (REST API supports concurrent requests)
        entries_created = 0
        entries_skipped = 0
        new_entries: list[dict[str, Any]] = []
        total_entries = len(feed_result["entries"])

        async def create_single_entry(idx: int, entry: dict) -> tuple[int, dict[str, Any] | None]:
            """Create a single entry and return result."""
            # Use feedContent for RSS/Atom content (content or summary)
            feed_content = entry.get("content") or entry.get("summary") or ""

            # Build metadata for special URL types (e.g., YouTube)
            entry_url = entry["url"]
            metadata: dict[str, Any] | None = None
            youtube_video_id = extract_youtube_video_id(entry_url)
            if youtube_video_id:
                metadata = {"youtubeVideoId": youtube_video_id}

            entry_data = {
                "feedId": feed_id,
                "title": entry["title"],
                "url": entry_url,
                "feedContent": feed_content,
                "author": entry.get("author"),
                "publishedAt": entry.get("published_at"),
                "metadata": metadata,
            }

            try:
                create_result = await api.create_entry(entry_data)
            except Exception as e:
                logger.warning(
                    f"API error creating entry: {e}",
                    index=idx + 1,
                    total=total_entries,
                )
                return (idx, None)

            if "error" in create_result:
                if "already exists" in str(create_result.get("error", "")):
                    return (idx, {"skipped": True})
                else:
                    logger.warning(
                        f"Failed to create entry: {create_result.get('error')}",
                        entry_url=entry_url,
                    )
                    return (idx, None)

            entry_id = str(create_result.get("id", ""))
            if not entry_id:
                logger.warning(
                    "Entry created but no ID returned",
                    entry_url=entry_url,
                    create_result=create_result,
                )
                return (idx, None)

            return (
                idx,
                {
                    "entry_id": entry_id,
                    "feed_id": feed_id,
                    "feed_name": feed_name,
                    "title": entry["title"],
                    "url": entry_url,
                    "feed_content": feed_content,
                    "author": entry.get("author", ""),
                    "published_at": entry.get("published_at"),
                    "metadata": metadata,
                    "extraction_rules": input.extraction_rules,
                },
            )

        # Run all entry creations concurrently
        tasks = [
            create_single_entry(idx, entry) for idx, entry in enumerate(feed_result["entries"])
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, BaseException):
                logger.warning(f"Entry creation task failed: {result}", feed_id=feed_id)
                continue
            _idx, entry_result = result
            if entry_result is None:
                continue
            elif entry_result.get("skipped"):
                entries_skipped += 1
            else:
                entries_created += 1
                new_entries.append(entry_result)

        activity.heartbeat(f"Created {entries_created}/{total_entries} entries")

        # Update feed checked timestamp with new etag/lastModified
        new_etag = feed_result.get("etag", "")
        new_last_modified = feed_result.get("last_modified", "")
        logger.debug("crawl_single_feed: updating feed checked timestamp...")
        await api.update_feed_checked(feed_id, new_etag, new_last_modified)

        total_elapsed = (time.perf_counter() - activity_start) * 1000
        logger.info(
            "crawl_single_feed end",
            feed_name=feed_name,
            entries_created=entries_created,
            entries_skipped=entries_skipped,
            elapsed_ms=f"{total_elapsed:.1f}",
        )

        return CrawlSingleFeedOutput(
            feed_id=feed_id,
            feed_name=feed_name,
            status="processed",
            entries_created=entries_created,
            entries_skipped=entries_skipped,
            new_entries=new_entries,
            new_etag=new_etag,
            new_last_modified=new_last_modified,
        )
