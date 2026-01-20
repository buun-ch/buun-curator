"""
Feed Crawler Service for Buun Curator.

Handles feed fetching and parsing without LLM involvement.
Migrated from agents/crawler.py.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol

import feedparser
import httpx

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import CrawlResult
from buun_curator.utils.youtube import extract_youtube_video_id

if TYPE_CHECKING:
    from time import struct_time


class FeedAPIClient(Protocol):
    """
    Protocol for API client used by FeedCrawler.

    Both MCPClient and APIClient implement this interface.
    """

    async def list_feeds(self) -> list[dict[str, Any]]: ...
    async def get_feed(self, feed_id: str) -> dict[str, Any]: ...
    async def create_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]: ...
    async def update_feed_checked(
        self, feed_id: str, etag: str = "", last_modified: str = ""
    ) -> dict[str, Any]: ...


logger = get_logger(__name__)


def _parse_time_struct(t: "struct_time | None") -> datetime | None:
    """
    Parse feedparser time struct to datetime.

    Parameters
    ----------
    t : struct_time | None
        Time struct from feedparser.

    Returns
    -------
    datetime | None
        Parsed datetime or None if input is None.
    """
    if t is None:
        return None
    return datetime(
        t.tm_year,
        t.tm_mon,
        t.tm_mday,
        t.tm_hour,
        t.tm_min,
        t.tm_sec,
        tzinfo=UTC,
    )


class FeedCrawler:
    """
    Service for crawling RSS/Atom feeds.
    """

    def __init__(self, api: FeedAPIClient):
        self.api = api

    def fetch_feed_content(
        self,
        feed_url: str,
        limit: int = 20,
        etag: str = "",
        last_modified: str = "",
        *,
        max_entry_age_days: int | None = None,
    ) -> dict[str, Any]:
        """
        Fetch and parse RSS/Atom feed from URL.

        Parameters
        ----------
        feed_url : str
            URL of the RSS/Atom feed.
        limit : int, optional
            Maximum number of entries to fetch (default: 20).
        etag : str, optional
            ETag for conditional request (default: "").
        last_modified : str, optional
            Last-Modified header for conditional request (default: "").
        max_entry_age_days : int | None, optional
            Skip entries older than this many days. None uses config default,
            0 disables filtering (default: None).

        Returns
        -------
        dict[str, Any]
            Dict with keys: success, not_modified, entries, etag, last_modified.
        """
        fetch_start = time.perf_counter()
        logger.debug("fetch_feed_content start", feed_url=feed_url)

        try:
            headers: dict[str, str] = {}
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified

            logger.debug("fetch_feed_content: sending HTTP request...")
            with httpx.Client(timeout=30.0) as client:
                http_start = time.perf_counter()
                response = client.get(feed_url, headers=headers, follow_redirects=True)
                http_elapsed = (time.perf_counter() - http_start) * 1000
                logger.debug(
                    f"fetch_feed_content: HTTP response {response.status_code} "
                    f"in {http_elapsed:.1f}ms"
                )

                # Handle 304 Not Modified
                if response.status_code == 304:
                    total_elapsed = (time.perf_counter() - fetch_start) * 1000
                    logger.info(
                        f"fetch_feed_content end: 304 Not Modified in {total_elapsed:.1f}ms"
                    )
                    return {
                        "success": True,
                        "not_modified": True,
                        "entries": [],
                        "etag": etag,
                        "last_modified": last_modified,
                    }

                response.raise_for_status()
                content = response.text

                # Extract cache headers from response
                response_etag = response.headers.get("ETag", "")
                response_last_modified = response.headers.get("Last-Modified", "")

            logger.debug("fetch_feed_content: parsing feed", bytes=len(content))
            parse_start = time.perf_counter()
            parsed = feedparser.parse(content)
            parse_elapsed = (time.perf_counter() - parse_start) * 1000
            logger.debug(
                f"fetch_feed_content: parsed {len(parsed.entries)} entries in {parse_elapsed:.1f}ms"
            )

            entries: list[dict[str, Any]] = []
            skipped_old = 0

            # Determine max_entry_age_days: use parameter if provided, else config default
            if max_entry_age_days is None:
                config = get_config()
                max_age_days = config.max_entry_age_days
            else:
                max_age_days = max_entry_age_days

            cutoff_date = (
                datetime.now(UTC) - timedelta(days=max_age_days) if max_age_days > 0 else None
            )

            for entry in parsed.entries[:limit]:
                published: datetime | None = None
                published_parsed = getattr(entry, "published_parsed", None)
                updated_parsed = getattr(entry, "updated_parsed", None)

                if published_parsed and isinstance(published_parsed, time.struct_time):
                    published = _parse_time_struct(published_parsed)
                elif updated_parsed and isinstance(updated_parsed, time.struct_time):
                    published = _parse_time_struct(updated_parsed)

                # Skip entries older than max_entry_age_days
                if cutoff_date and published and published < cutoff_date:
                    skipped_old += 1
                    continue

                entry_content = ""
                entry_content_list = getattr(entry, "content", None)
                if entry_content_list and isinstance(entry_content_list, list):
                    first_content = entry_content_list[0]
                    if isinstance(first_content, dict):
                        entry_content = str(first_content.get("value", ""))
                elif hasattr(entry, "summary"):
                    entry_content = str(entry.get("summary", ""))

                summary_raw = entry.get("summary", "")
                summary = str(summary_raw) if summary_raw else ""

                entries.append(
                    {
                        "title": str(entry.get("title", "")),
                        "url": str(entry.get("link", "")),
                        "content": entry_content,
                        "summary": summary,
                        "author": str(entry.get("author", "")),
                        "published_at": published.isoformat() if published else None,
                    }
                )

            total_elapsed = (time.perf_counter() - fetch_start) * 1000
            skip_msg = f", {skipped_old} old entries skipped" if skipped_old > 0 else ""
            logger.info(
                f"fetch_feed_content end: {len(entries)} entries in {total_elapsed:.1f}ms{skip_msg}"
            )
            return {
                "success": True,
                "not_modified": False,
                "entries": entries,
                "etag": response_etag,
                "last_modified": response_last_modified,
            }

        except Exception as e:
            elapsed = (time.perf_counter() - fetch_start) * 1000
            logger.error(
                f"fetch_feed_content failed: {e}",
                feed_url=feed_url,
                elapsed_ms=round(elapsed, 1),
                error_type=type(e).__name__,
            )
            return {
                "success": False,
                "not_modified": False,
                "error": str(e),
                "entries": [],
                "etag": "",
                "last_modified": "",
            }

    async def crawl_all(
        self,
        on_progress: Callable[[str], None] | None = None,
    ) -> CrawlResult:
        """
        Crawl all registered feeds and create entries.

        Parameters
        ----------
        on_progress : Callable[[str], None] | None, optional
            Callback for progress updates (default: None).

        Returns
        -------
        CrawlResult
            Result containing feeds processed, entries created, and details.
        """
        feeds = await self.api.list_feeds()
        total_feeds = len(feeds)
        logger.info("Found feeds to process", count=total_feeds)

        if on_progress:
            on_progress(f"Starting: {total_feeds} feeds")

        result = CrawlResult(
            feeds_processed=0,
            feeds_skipped=0,
            entries_created=0,
            entries_skipped=0,
            new_entries=[],
            feed_details=[],
            entry_details=[],
        )

        for feed_idx, feed in enumerate(feeds):
            feed_id = str(feed["id"])  # ULID string
            feed_name = feed.get("name", "Unknown")
            feed_url = feed.get("url", "")

            if on_progress:
                on_progress(f"Feed {feed_idx + 1}/{total_feeds}: {feed_name}")

            # Track per-feed stats
            feed_entries_created = 0
            feed_entries_skipped = 0

            if not feed_url:
                logger.warning("Feed has no URL, skipping", feed_id=feed_id)
                result.feed_details.append(
                    {
                        "feed_id": feed_id,
                        "feed_name": feed_name,
                        "status": "error",
                        "error": "No URL configured",
                    }
                )
                continue

            # Get feed details for etag/lastModified
            feed_detail = await self.api.get_feed(feed_id)
            etag = feed_detail.get("etag", "") or ""
            last_modified = feed_detail.get("lastModified", "") or ""

            # Get fetchLimit directly from feed detail
            fetch_limit = feed_detail.get("fetchLimit", 20)

            # extractionRules is still in options
            options = feed_detail.get("options")
            extraction_rules: list[dict] | None = None
            if options and isinstance(options, dict):
                extraction_rules = options.get("extractionRules")

            # Fetch feed content
            feed_result = self.fetch_feed_content(feed_url, fetch_limit, etag, last_modified)

            if not feed_result["success"]:
                logger.error("Failed to fetch feed", feed_name=feed_name, feed_id=feed_id)
                result.feed_details.append(
                    {
                        "feed_id": feed_id,
                        "feed_name": feed_name,
                        "status": "error",
                        "error": feed_result.get("error", "Unknown error"),
                    }
                )
                continue

            if feed_result["not_modified"]:
                result.feeds_skipped += 1
                result.feed_details.append(
                    {
                        "feed_id": feed_id,
                        "feed_name": feed_name,
                        "status": "skipped",
                        "entries_created": 0,
                        "entries_skipped": 0,
                    }
                )
                # Still update checkedAt
                await self.api.update_feed_checked(feed_id, etag, last_modified)
                continue

            result.feeds_processed += 1

            # Create entries
            for entry in feed_result["entries"]:
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

                create_result = await self.api.create_entry(entry_data)

                if "error" in create_result:
                    if "already exists" in str(create_result.get("error", "")):
                        result.entries_skipped += 1
                        feed_entries_skipped += 1
                    else:
                        logger.warning(
                            f"Failed to create entry: {create_result.get('error')}",
                            entry_url=entry_url,
                        )
                else:
                    result.entries_created += 1
                    feed_entries_created += 1
                    entry_id = str(create_result.get("id", ""))  # ULID string
                    # Use dict format for Temporal serialization compatibility
                    result.new_entries.append(
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
                            "extraction_rules": extraction_rules,
                        }
                    )
                    # Add to entry_details for Temporal UI
                    result.entry_details.append(
                        {
                            "entry_id": entry_id,
                            "feed_id": feed_id,
                            "feed_name": feed_name,
                            "title": entry["title"],
                            "url": entry_url,
                        }
                    )

            # Add feed detail
            result.feed_details.append(
                {
                    "feed_id": feed_id,
                    "feed_name": feed_name,
                    "status": "processed",
                    "entries_created": feed_entries_created,
                    "entries_skipped": feed_entries_skipped,
                }
            )

            # Update feed checked timestamp with new etag/lastModified
            await self.api.update_feed_checked(
                feed_id,
                feed_result.get("etag", ""),
                feed_result.get("last_modified", ""),
            )

        logger.info(
            f"Crawl completed: {result.feeds_processed} feeds processed, "
            f"{result.feeds_skipped} skipped, {result.entries_created} entries created, "
            f"{result.entries_skipped} duplicates"
        )

        return result
