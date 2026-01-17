"""
Fetch Activities for Temporal.

Activities for content fetching operations.
"""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.graphiti.session import GraphitiSession
from buun_curator.logging import get_logger
from buun_curator.models import (
    FetchAndSaveLinksInput,
    FetchAndSaveLinksOutput,
    FetchContentsInput,
    FetchContentsOutput,
    FetchedContent,
    FetchLinkResult,
    FetchSingleContentInput,
    FetchSingleContentOutput,
)
from buun_curator.services.api import APIClient
from buun_curator.services.content import ContentFetcher
from buun_curator.services.thumbnail import ThumbnailService
from buun_curator.utils.youtube import is_youtube_url

logger = get_logger(__name__)


def _merge_extraction_rules(
    feed_rules: list[dict] | None,
    additional_rules: list[dict] | None,
) -> list[dict]:
    """
    Merge feed-level and additional extraction rules.

    Parameters
    ----------
    feed_rules : list[dict] | None
        Extraction rules from the feed's options.
    additional_rules : list[dict] | None
        Additional rules (e.g., from preview/testing).

    Returns
    -------
    list[dict]
        Merged rules list (empty list if no rules).
    """
    merged: list[dict] = []
    if feed_rules:
        merged.extend(feed_rules)
    if additional_rules:
        merged.extend(additional_rules)
    return merged


async def _fetch_single_entry(
    fetcher: ContentFetcher,
    entry: dict,
    additional_rules: list[dict] | None,
) -> tuple[str, dict[str, Any] | None, dict]:
    """
    Fetch content for a single entry with merged extraction rules.

    Parameters
    ----------
    fetcher : ContentFetcher
        The content fetcher instance.
    entry : dict
        Entry dict containing entry_id, url, title, extraction_rules.
    additional_rules : list[dict] | None
        Additional extraction rules to merge with feed rules.

    Returns
    -------
    tuple[str, dict[str, Any] | None, dict]
        Tuple of (entry_id, content_dict or None, detail_dict).
        content_dict includes full_content, filtered_content, raw_html, and screenshot.
    """
    entry_id = entry["entry_id"]
    url = entry["url"]
    title = entry.get("title", "")

    # Merge feed rules with additional input rules
    feed_rules = entry.get("extraction_rules")
    merged_rules = _merge_extraction_rules(feed_rules, additional_rules)

    content = await fetcher.fetch(url, title, merged_rules)

    if content and content.full_content:
        return (
            entry_id,
            {
                "full_content": content.full_content,
                "raw_html": content.raw_html,
                "screenshot": content.screenshot,
            },
            {
                "entry_id": entry_id,
                "url": url,
                "title": title,
                "status": "success",
                "full_content_bytes": len(content.full_content),
                "has_screenshot": content.screenshot is not None,
            },
        )
    else:
        title_short = title[:30]
        logger.warning(
            "No content fetched", entry_id=entry_id, title=title_short, url=url
        )
        return (
            entry_id,
            None,
            {
                "entry_id": entry_id,
                "url": url,
                "title": title,
                "status": "failed",
                "full_content_bytes": 0,
                "has_screenshot": False,
            },
        )


@activity.defn
async def fetch_contents(input: FetchContentsInput) -> FetchContentsOutput:
    """
    Fetch content for multiple entries.

    Parameters
    ----------
    input : FetchContentsInput
        Input containing entries list, timeout, and concurrency settings.

    Returns
    -------
    FetchContentsOutput
        Output containing contents dict mapping entry_id to content.
    """
    if not input.entries:
        return FetchContentsOutput()

    # Separate entries: skip YouTube URLs, fetch others
    entries_to_fetch: list[dict] = []
    skipped_entries: list[dict] = []

    for entry in input.entries:
        url = entry.get("url", "")
        metadata = entry.get("metadata") or {}
        # Check both metadata and URL pattern for YouTube detection
        if metadata.get("youtubeVideoId") or is_youtube_url(url):
            skipped_entries.append(entry)
            logger.info("Skipping YouTube URL", entry_id=entry["entry_id"], url=url)
        else:
            entries_to_fetch.append(entry)

    config = get_config()
    enable_thumbnail = config.enable_thumbnail

    # Use config values for concurrency if not explicitly set
    fetch_concurrency = input.concurrency or config.fetch_concurrency

    logger.info(
        "Fetching content for entries",
        entries=len(entries_to_fetch),
        skipped_youtube=len(skipped_entries),
        timeout=input.timeout,
        fetch_concurrency=fetch_concurrency,
        thumbnail=enable_thumbnail,
    )

    fetcher = ContentFetcher(
        timeout=input.timeout,
        concurrency=fetch_concurrency,
        capture_screenshot=enable_thumbnail,
    )
    thumbnail_service = ThumbnailService(config) if enable_thumbnail else None

    # Track results
    results: dict[str, dict] = {}
    fetch_details: list[dict] = []
    success_count = 0
    failed_count = 0
    skipped_count = len(skipped_entries)
    total_entries = len(entries_to_fetch) + skipped_count

    # Record skipped YouTube entries
    for entry in skipped_entries:
        entry_id = entry["entry_id"]
        url = entry["url"]
        title = entry.get("title", "")
        fetch_details.append(
            {
                "entry_id": entry_id,
                "url": url,
                "title": title,
                "status": "skipped_youtube",
                "full_content_bytes": 0,
                "filtered_content_bytes": 0,
            }
        )

    # Fetch entries with per-entry extraction rules using semaphore for concurrency
    semaphore = asyncio.Semaphore(input.concurrency)
    processed_count = 0

    async def fetch_with_semaphore(entry: dict) -> tuple[str, dict | None, dict]:
        """Wrapper to apply semaphore and report progress."""
        nonlocal processed_count
        async with semaphore:
            result = await _fetch_single_entry(fetcher, entry, input.extraction_rules)
            processed_count += 1
            title_short = entry.get("title", "")[:30]
            activity.heartbeat(
                f"Processed {skipped_count + processed_count}/{total_entries}: {title_short}"
            )
            return result

    # Run fetches concurrently
    fetch_tasks = [fetch_with_semaphore(entry) for entry in entries_to_fetch]
    fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    # Process results
    for item in fetch_results:
        if isinstance(item, BaseException):
            logger.error(f"Fetch task failed: {item}")
            failed_count += 1
        else:
            entry_id, content_dict, detail = item
            fetch_details.append(detail)
            if content_dict:
                results[entry_id] = content_dict
                success_count += 1
                logger.info(
                    "Fetched content",
                    entry_id=entry_id,
                    chars=len(content_dict["full_content"]),
                )
            else:
                failed_count += 1

    # Save contents to DB via REST API (avoids large gRPC response)
    # Upload thumbnails to MinIO if enabled
    # REST API supports parallel requests for better performance
    if results:
        activity.heartbeat(f"Saving {len(results)} contents to DB")
        thumbnail_count = 0
        total_saves = len(results)

        async with APIClient(config.api_url, config.api_token) as api:

            async def save_single_entry(entry_id: str, content: dict) -> tuple[str, bool]:
                """Save a single entry and return success status."""
                nonlocal thumbnail_count

                # Skip entries with empty ID (defensive check)
                if not entry_id:
                    logger.warning("Skipping entry with empty ID")
                    return (entry_id, False)

                # Upload screenshot to S3 if available
                uploaded_thumbnail_url: str = ""
                screenshot = content.get("screenshot")
                logger.debug(
                    f"Entry {entry_id}: "
                    f"thumbnail_service={thumbnail_service is not None}, "
                    f"screenshot="
                    f"{screenshot is not None and len(screenshot) if screenshot else 0} bytes"
                )
                if thumbnail_service and screenshot:
                    try:
                        uploaded_thumbnail_url = await thumbnail_service.upload_thumbnail(
                            entry_id, screenshot
                        )
                        thumbnail_count += 1
                        logger.debug(
                            f"Thumbnail uploaded for {entry_id}: {uploaded_thumbnail_url}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to upload thumbnail: {e}", entry_id=entry_id)

                await api.update_entry(
                    entry_id,
                    full_content=content["full_content"],
                    raw_html=content["raw_html"],
                    thumbnail_url=uploaded_thumbnail_url,
                )
                return (entry_id, True)

            # Run all saves concurrently
            save_tasks = [
                save_single_entry(entry_id, content) for entry_id, content in results.items()
            ]
            save_results = await asyncio.gather(*save_tasks, return_exceptions=True)

            save_count = sum(1 for r in save_results if not isinstance(r, BaseException) and r[1])
            activity.heartbeat(f"Saved {save_count}/{total_saves} to DB")

        logger.info(
            "Saved content to DB",
            save_count=save_count,
            thumbnail_count=thumbnail_count,
        )

    # Build contents_for_summarize (without raw_html to reduce size)
    contents_for_summarize: dict[str, dict] = {
        entry_id: {
            "full_content": content["full_content"],
        }
        for entry_id, content in results.items()
    }

    logger.info(
        "Fetched content summary",
        success_count=success_count,
        total_entries=total_entries,
        skipped_youtube=skipped_count,
    )
    return FetchContentsOutput(
        contents_for_summarize=contents_for_summarize,
        fetch_details=fetch_details,
        success_count=success_count,
        failed_count=failed_count,
    )


@activity.defn
async def fetch_single_content(input: FetchSingleContentInput) -> FetchSingleContentOutput:
    """
    Fetch or process content for a single entry.

    Supports two modes:
    1. URL fetch mode: Fetch content from URL using AsyncWebCrawler
    2. HTML processing mode: Process provided HTML content directly

    When entry_id is provided, content is saved directly to DB and only status
    is returned (to avoid gRPC response size limits). When entry_id is not
    provided (preview mode), content is returned in the output.

    Parameters
    ----------
    input : FetchSingleContentInput
        Input containing url/html_content, title, timeout, and optional extraction rules.
        feed_extraction_rules: Rules from the feed's options.
        additional_extraction_rules: Extra rules for testing/preview.
        entry_id: If provided, save content to DB (content not returned).
        enable_thumbnail: Whether to capture and upload thumbnail.
        html_content: If provided, process HTML directly instead of fetching URL.

    Returns
    -------
    FetchSingleContentOutput
        Output containing status and optionally content (if entry_id not provided).
    """
    config = get_config()
    capture_screenshot = input.enable_thumbnail and config.enable_thumbnail

    fetcher = ContentFetcher(
        timeout=input.timeout,
        capture_screenshot=capture_screenshot,
    )

    # Determine processing mode: HTML processing or URL fetch
    if input.html_content:
        # HTML processing mode: process provided HTML directly
        logger.info("Processing HTML content", entry_id=input.entry_id or "preview")
        try:
            content = fetcher.process_html(input.html_content, input.title)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to process HTML content: {error_msg}")
            return FetchSingleContentOutput(
                status="failed",
                error=error_msg,
            )
    else:
        # URL fetch mode: fetch content from URL
        logger.info("Fetching content for URL", url=input.url)

        # Merge feed rules with additional rules
        merged_rules = _merge_extraction_rules(
            input.feed_extraction_rules, input.additional_extraction_rules
        )

        try:
            content = await fetcher.fetch(input.url, input.title, merged_rules)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to fetch content: {error_msg}", url=input.url)
            return FetchSingleContentOutput(
                status="failed",
                error=error_msg,
            )

    if not content.full_content:
        source = "HTML content" if input.html_content else input.url
        logger.warning("No content extracted", source=source)
        return FetchSingleContentOutput(
            status="no_content",
        )

    content_length = len(content.full_content)
    source = "HTML content" if input.html_content else input.url
    logger.info("Processed content", chars=content_length, source=source)

    # If entry_id is provided, save to DB and return only status
    if input.entry_id:
        try:
            await _save_entry_content(
                entry_id=input.entry_id,
                content=content,
                enable_thumbnail=capture_screenshot,
            )
            return FetchSingleContentOutput(
                status="success",
                content_length=content_length,
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to save content: {error_msg}", entry_id=input.entry_id)
            return FetchSingleContentOutput(
                status="failed",
                content_length=content_length,
                error=error_msg,
            )

    # Preview mode: return content in output
    return FetchSingleContentOutput(
        full_content=content.full_content,
        status="success",
        content_length=content_length,
    )


async def _save_entry_content(
    entry_id: str,
    content: FetchedContent,
    enable_thumbnail: bool = False,
) -> None:
    """
    Save fetched content to DB via REST API.

    Parameters
    ----------
    entry_id : str
        The entry ID to save content for.
    content : FetchedContent
        The fetched content to save.
    enable_thumbnail : bool, optional
        Whether to upload thumbnail to S3 (default: False).
    """
    config = get_config()
    thumbnail_service = ThumbnailService(config) if enable_thumbnail else None

    uploaded_thumbnail_url: str = ""

    # Upload screenshot to S3 if available
    if thumbnail_service and content.screenshot:
        try:
            uploaded_thumbnail_url = await thumbnail_service.upload_thumbnail(
                entry_id, content.screenshot
            )
            logger.debug(
                "Thumbnail uploaded", entry_id=entry_id, url=uploaded_thumbnail_url
            )
        except Exception as e:
            logger.warning(f"Failed to upload thumbnail: {e}", entry_id=entry_id)

    # Save content to DB via REST API
    async with APIClient(config.api_url, config.api_token) as api:
        await api.update_entry(
            entry_id,
            full_content=content.full_content,
            raw_html=content.raw_html,
            thumbnail_url=uploaded_thumbnail_url,
        )

    logger.info("Saved content to DB", entry_id=entry_id)


def _extract_title_from_markdown(content: str) -> str:
    """
    Extract title from markdown content.

    Looks for the first H1 heading (# Title) or falls back to the first line.

    Parameters
    ----------
    content : str
        Markdown content.

    Returns
    -------
    str
        Extracted title, or empty string if not found.
    """
    if not content:
        return ""

    # Look for H1 heading (# Title)
    h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()

    # Fall back to first non-empty line
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped:
            # Remove markdown formatting
            stripped = re.sub(r"^\*+|\*+$", "", stripped)  # bold/italic
            stripped = re.sub(r"^#+\s*", "", stripped)  # headers
            if stripped:
                return stripped[:200]  # Limit title length

    return ""


@activity.defn
async def fetch_and_save_entry_links(
    input: FetchAndSaveLinksInput,
) -> FetchAndSaveLinksOutput:
    """
    Fetch content from URLs and save as entry enrichments.

    For each URL:
    1. Fetch content using ContentFetcher
    2. Extract title from content
    3. Save to entry_enrichments with type='web_page'

    Parameters
    ----------
    input : FetchAndSaveLinksInput
        Input containing entry_id, urls list, and timeout.

    Returns
    -------
    FetchAndSaveLinksOutput
        Output containing results for each URL.
    """
    if not input.urls:
        return FetchAndSaveLinksOutput()

    config = get_config()
    entry_id = input.entry_id
    total_urls = len(input.urls)

    logger.info("Fetching URLs for entry", entry_id=entry_id, total_urls=total_urls)

    fetcher = ContentFetcher(timeout=input.timeout)
    results: list[FetchLinkResult] = []
    success_count = 0
    failed_count = 0

    async with APIClient(config.api_url, config.api_token) as api:
        for i, url in enumerate(input.urls):
            activity.heartbeat(f"Fetching URL {i + 1}/{total_urls}: {url[:50]}...")

            try:
                # Fetch content
                content = await fetcher.fetch(url)

                if not content or not content.full_content:
                    logger.warning("No content fetched for URL", url=url)
                    results.append(
                        FetchLinkResult(
                            url=url,
                            success=False,
                            error="No content extracted",
                        )
                    )
                    failed_count += 1
                    continue

                # Use HTML title from metadata, fallback to markdown extraction
                title = content.title or _extract_title_from_markdown(content.full_content)
                content_length = len(content.full_content)

                # Save to entry_enrichments
                fetched_at = datetime.now(UTC).isoformat()
                enrichment_data = {
                    "title": title,
                    "content": content.full_content,
                    "fetchedAt": fetched_at,
                }
                enrichment_metadata = {
                    "contentLength": content_length,
                }

                await api.save_entry_enrichment(
                    entry_id=entry_id,
                    enrichment_type="web_page",
                    data=enrichment_data,
                    source=url,
                    metadata=enrichment_metadata,
                )

                logger.info(
                    "Saved enrichment for URL",
                    url=url[:50],
                    title=title[:30],
                    chars=content_length,
                )

                # Add content to Graphiti session for Deep Research
                try:
                    session = await GraphitiSession.create(entry_id)
                    await session.add_content(content.full_content, source_type="web_page")
                    logger.info(
                        "Added web page to Graphiti", entry_id=entry_id, url=url[:50]
                    )
                except Exception as graphiti_err:
                    logger.warning(
                        f"Failed to add web page to Graphiti for {entry_id}: {graphiti_err}"
                    )

                results.append(
                    FetchLinkResult(
                        url=url,
                        title=title,
                        success=True,
                        content_length=content_length,
                    )
                )
                success_count += 1

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to fetch/save URL: {error_msg}", url=url)
                results.append(
                    FetchLinkResult(
                        url=url,
                        success=False,
                        error=error_msg,
                    )
                )
                failed_count += 1

    logger.info(
        "Completed fetching URLs for entry",
        entry_id=entry_id,
        total_urls=total_urls,
        success_count=success_count,
        failed_count=failed_count,
    )

    return FetchAndSaveLinksOutput(
        results=results,
        success_count=success_count,
        failed_count=failed_count,
    )
