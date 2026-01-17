"""
Content Distillation Activities for Temporal.

Activities for entry content distillation (filtering + summarization).
"""

import asyncio
import uuid
from typing import Any

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    DistillEntryContentInput,
    DistillEntryContentOutput,
    GetEntriesForDistillationInput,
    GetEntriesForDistillationOutput,
    SaveDistilledEntriesInput,
    SaveDistilledEntriesOutput,
)
from buun_curator.models.entry import EntryToProcess
from buun_curator.services.api import APIClient
from buun_curator.services.content import html_to_markdown
from buun_curator.services.content_processor import ContentProcessor
from buun_curator.services.search import index_entries

logger = get_logger(__name__)


def _get_content_for_distillation(entry: dict) -> str:
    """
    Get content for distillation from an entry with fallback chain.

    Tries fullContent, then filteredContent, then feedContent (HTML -> Markdown).

    Parameters
    ----------
    entry : dict
        Entry data from MCP.

    Returns
    -------
    str
        Content suitable for distillation, or empty string if none available.
    """
    content = entry.get("fullContent") or ""
    if content.strip() and len(content) >= 1000:
        return content

    content = entry.get("filteredContent") or ""
    if content.strip() and len(content) >= 1000:
        return content

    # Fallback to feedContent (HTML -> Markdown)
    feed_content = entry.get("feedContent") or ""
    if feed_content.strip():
        converted = html_to_markdown(feed_content)
        if converted.strip() and len(converted) >= 500:
            logger.info(
                "Using feedContent for entry",
                html_chars=len(feed_content),
                markdown_chars=len(converted),
            )
            return converted

    return ""


@activity.defn
async def get_entries_for_distillation(
    input: GetEntriesForDistillationInput,
) -> GetEntriesForDistillationOutput:
    """
    Get entries that need distillation.

    Parameters
    ----------
    input : GetEntriesForDistillationInput
        Input containing optional entry_ids to filter.

    Returns
    -------
    GetEntriesForDistillationOutput
        Output containing list of entry dicts.
    """
    config = get_config()

    async with APIClient(config.api_url, config.api_token) as api:
        if input.entry_ids:
            # Get specific entries in parallel
            async def get_single_entry(entry_id: str) -> dict | None:
                entry = await api.get_entry(entry_id)
                if "error" not in entry and entry:
                    content = _get_content_for_distillation(entry)
                    if content:
                        return {
                            "entry_id": entry_id,
                            "title": entry.get("title", ""),
                            "url": entry.get("url", ""),
                            "full_content": content,
                        }
                return None

            tasks = [get_single_entry(eid) for eid in input.entry_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            entries: list[dict[str, Any]] = [
                r for r in results if r is not None and not isinstance(r, BaseException)
            ]
            return GetEntriesForDistillationOutput(entries=entries)
        else:
            # Get undistilled entries
            api_entries = await api.list_entries(has_summary=False, limit=100)
            entries: list[dict[str, Any]] = []
            for entry in api_entries:
                content = _get_content_for_distillation(entry)
                if content:
                    entries.append(
                        {
                            "entry_id": str(entry["id"]),
                            "title": entry.get("title", ""),
                            "url": entry.get("url", ""),
                            "full_content": content,
                        }
                    )
            return GetEntriesForDistillationOutput(entries=entries)


@activity.defn
async def distill_entry_content(
    input: DistillEntryContentInput,
) -> DistillEntryContentOutput:
    """
    Distill entry content: filter content and generate summaries.

    Distills entries one by one, generating both summary and filtered_content.

    Parameters
    ----------
    input : DistillEntryContentInput
        Input containing entries list.

    Returns
    -------
    DistillEntryContentOutput
        Output containing list of result dicts with summary and filtered_content.
    """
    if not input.entries:
        logger.info("No entries to distill")
        return DistillEntryContentOutput()

    config = get_config()

    if not config.openai_api_key:
        logger.error("OPENAI_API_KEY not configured")
        return DistillEntryContentOutput()

    # Generate trace ID for Langfuse (32-char hex format for SDK v3 compatibility)
    trace_id = uuid.uuid4().hex
    target_language = input.target_language or ""

    logger.info(
        "Distill trace started",
        trace_id=trace_id,
        count=len(input.entries),
        target_language=target_language or "original",
    )

    # Uses summarization_llm_model with Structured Output
    processor = ContentProcessor(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url or None,  # None = OpenAI direct
        model=config.summarization_llm_model,
        target_language=target_language,
        trace_id=trace_id,
        trace_name="distillation-batch",
        max_content_chars=config.max_content_chars,
        heartbeat_callback=activity.heartbeat,
    )

    # Convert dicts to EntryToProcess objects and filter empty content
    entries = [
        EntryToProcess(
            entry_id=e["entry_id"],
            title=e.get("title", ""),
            url=e.get("url", ""),
            full_content=e.get("full_content", ""),
        )
        for e in input.entries
        if e.get("full_content", "").strip()
    ]

    if not entries:
        logger.info("No entries with content to distill")
        return DistillEntryContentOutput()

    total = len(entries)
    batch_mode = input.batch_mode
    activity.heartbeat(f"Starting distillation: {total} entries (mode={batch_mode})")
    logger.info("Distillation mode", batch_mode=batch_mode)

    # Process entries based on batch_mode
    if batch_mode == "prompt_batch":
        # Single prompt for multiple entries (experimental)
        processed = await processor.process_entries_batch(entries)
    elif batch_mode == "sequential":
        # Individual prompts, sequential processing (legacy)
        processed = await processor.process_entries(entries)
    else:
        # Default: "parallel" - individual prompts with parallel API calls
        processed = await processor.process_entries_parallel(
            entries, max_concurrency=input.batch_size
        )

    # Convert to output format
    all_results: list[dict] = [
        {
            "entry_id": result.entry_id,
            "summary": result.summary,
            "filtered_content": result.filtered_content,
            "start_line": result.start_line,
            "end_line": result.end_line,
            "trace_id": trace_id,
        }
        for result in processed
    ]

    success_count = sum(1 for r in all_results if r.get("summary"))
    activity.heartbeat(f"Completed: {success_count}/{total} successful")
    logger.info(
        "Distillation completed",
        batch_mode=batch_mode,
        success_count=success_count,
        total=total,
    )

    return DistillEntryContentOutput(results=all_results)


@activity.defn
async def save_distilled_entries(
    input: SaveDistilledEntriesInput,
) -> SaveDistilledEntriesOutput:
    """
    Save distilled entries (summaries and filtered content) to database via REST API.

    Parameters
    ----------
    input : SaveDistilledEntriesInput
        Input containing list of result dicts with summary and filtered_content.

    Returns
    -------
    SaveDistilledEntriesOutput
        Output containing saved_count.
    """
    if not input.results:
        return SaveDistilledEntriesOutput()

    config = get_config()
    total = len(input.results)

    activity.heartbeat(f"Saving {total} results")

    async with APIClient(config.api_url, config.api_token) as api:

        async def save_single_result(s: dict) -> bool:
            """Save a single result and return success status."""
            # Skip if no summary (distillation failed)
            if not s.get("summary"):
                return False

            # Build metadata with trace_id and line range
            metadata: dict = {}
            if s.get("trace_id"):
                metadata["distillTraceId"] = s["trace_id"]
            if s.get("start_line"):
                metadata["mainContentStartLine"] = s["start_line"]
            if s.get("end_line"):
                metadata["mainContentEndLine"] = s["end_line"]

            try:
                await api.update_entry(
                    s["entry_id"],
                    summary=s["summary"],
                    filtered_content=s.get("filtered_content", ""),
                    metadata=metadata or None,
                )
                return True
            except Exception as e:
                logger.warning(
                    f"Failed to save result: {e}",
                    entry_id=s["entry_id"],
                    error_type=type(e).__name__,
                )
                return False

        # Run all saves concurrently
        tasks = [save_single_result(s) for s in input.results]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        saved_count = sum(1 for r in results if r is True and not isinstance(r, Exception))
        activity.heartbeat(f"Saved {saved_count}/{total} results")

        # Index saved entries in Meilisearch
        saved_entry_ids = [s["entry_id"] for s in input.results if s.get("summary")]
        if saved_entry_ids:
            activity.heartbeat(f"Indexing {len(saved_entry_ids)} entries in Meilisearch")
            try:
                # Fetch full entry data for indexing
                entries_to_index: list[dict] = []
                for entry_id in saved_entry_ids:
                    entry = await api.get_entry(entry_id)
                    if entry and "error" not in entry:
                        entries_to_index.append(entry)
                if entries_to_index:
                    await asyncio.to_thread(index_entries, entries_to_index)
                    logger.info("Indexed entries in Meilisearch", count=len(entries_to_index))
            except Exception as e:
                # Log but don't fail the activity
                logger.warning(
                    f"Failed to index entries in Meilisearch: {e}",
                    error_type=type(e).__name__,
                )

    logger.info("Saved distillation results", saved_count=saved_count)
    return SaveDistilledEntriesOutput(saved_count=saved_count)
