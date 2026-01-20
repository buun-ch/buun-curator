"""
Global Graph Activities.

Temporal activities for adding content to the global knowledge graph.
Supports multiple backends (Graphiti, LightRAG) based on configuration.
"""

import asyncio
from typing import Any

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    AddToGlobalGraphBulkInput,
    AddToGlobalGraphBulkOutput,
    AddToGlobalGraphInput,
    AddToGlobalGraphOutput,
    FetchAndAddToGraphBulkInput,
    FetchAndAddToGraphBulkOutput,
    GetEntriesForGraphUpdateInput,
    GetEntriesForGraphUpdateOutput,
    MarkEntriesGraphAddedInput,
    MarkEntriesGraphAddedOutput,
    ResetGlobalGraphOutput,
)
from buun_curator.services.api import APIClient

logger = get_logger(__name__)


def _get_backend() -> str:
    """Get the configured GraphRAG backend."""
    return get_config().graph_rag_backend


async def _add_content(
    content: str,
    entry_id: str,
    source_type: str,
    title: str | None,
    url: str | None,
) -> bool:
    """
    Add content to global graph using the configured backend.

    Parameters
    ----------
    content : str
        Text content to add.
    entry_id : str
        Entry ID for tracking.
    source_type : str
        Content type.
    title : str | None
        Optional title.
    url : str | None
        Optional URL.

    Returns
    -------
    bool
        True if successful.
    """
    backend = _get_backend()

    if backend == "lightrag":
        from buun_curator.lightrag.global_graph import add_content_to_global_graph

        return await add_content_to_global_graph(
            content=content,
            entry_id=entry_id,
            source_type=source_type,
            title=title,
            url=url,
        )
    else:
        # Default to graphiti
        from buun_curator.graphiti.global_graph import add_episode_to_global_graph

        return await add_episode_to_global_graph(
            content=content,
            entry_id=entry_id,
            source_type=source_type,
            title=title,
            url=url,
        )


async def _add_contents_bulk(
    episodes: list[dict[str, Any]],
) -> tuple[int, int]:
    """
    Add multiple contents to global graph using the configured backend.

    Parameters
    ----------
    episodes : list[dict[str, Any]]
        List of episode dicts.

    Returns
    -------
    tuple[int, int]
        (success_count, failed_count)
    """
    backend = _get_backend()

    if backend == "lightrag":
        from buun_curator.lightrag.global_graph import add_contents_bulk_to_global_graph

        return await add_contents_bulk_to_global_graph(episodes)
    else:
        # Default to graphiti
        from buun_curator.graphiti.global_graph import add_episodes_bulk_to_global_graph

        return await add_episodes_bulk_to_global_graph(episodes)


async def _reset_graph() -> tuple[bool, int]:
    """
    Reset global graph using the configured backend.

    Returns
    -------
    tuple[bool, int]
        (success, deleted_count)
    """
    backend = _get_backend()

    if backend == "lightrag":
        from buun_curator.lightrag.global_graph import reset_global_lightrag

        return await reset_global_lightrag()
    else:
        # Default to graphiti
        from buun_curator.graphiti.global_graph import reset_global_graph

        return await reset_global_graph()


@activity.defn
async def add_to_global_graph(
    input: AddToGlobalGraphInput,
) -> AddToGlobalGraphOutput:
    """
    Add entry content to the global knowledge graph.

    Parameters
    ----------
    input : AddToGlobalGraphInput
        Entry ID, content, and metadata.

    Returns
    -------
    AddToGlobalGraphOutput
        Success status.
    """
    backend = _get_backend()
    logger.info(
        "Adding entry to global graph",
        entry_id=input.entry_id,
        backend=backend,
        chars=len(input.content),
    )

    try:
        success = await _add_content(
            content=input.content,
            entry_id=str(input.entry_id),
            source_type=input.source_type,
            title=input.title,
            url=input.url,
        )

        if success:
            logger.info("Successfully added entry to global graph", entry_id=input.entry_id)
        else:
            logger.warning("Failed to add entry to global graph", entry_id=input.entry_id)

        return AddToGlobalGraphOutput(success=success)

    except Exception as e:
        logger.error(f"Error adding entry to global graph: {e}", entry_id=input.entry_id)
        return AddToGlobalGraphOutput(
            success=False,
            error=str(e),
        )


@activity.defn
async def add_to_global_graph_bulk(
    input: AddToGlobalGraphBulkInput,
) -> AddToGlobalGraphBulkOutput:
    """
    Add multiple entries to the global knowledge graph in bulk.

    Parameters
    ----------
    input : AddToGlobalGraphBulkInput
        List of episodes to add.

    Returns
    -------
    AddToGlobalGraphBulkOutput
        Success and failure counts.
    """
    if not input.episodes:
        return AddToGlobalGraphBulkOutput(success_count=0, failed_count=0)

    backend = _get_backend()
    logger.info(
        "Adding entries to global graph in bulk",
        entries=len(input.episodes),
        backend=backend,
    )

    # Convert to dict format expected by bulk function
    episodes = [
        {
            "entry_id": str(ep.entry_id),
            "content": ep.content,
            "title": ep.title,
            "url": ep.url,
            "source_type": ep.source_type,
        }
        for ep in input.episodes
    ]

    try:
        success_count, failed_count = await _add_contents_bulk(episodes)

        logger.info("Bulk add completed", success_count=success_count, failed_count=failed_count)

        return AddToGlobalGraphBulkOutput(
            success_count=success_count,
            failed_count=failed_count,
        )

    except Exception as e:
        logger.error(f"Error in bulk add to global graph: {e}")
        return AddToGlobalGraphBulkOutput(
            success_count=0,
            failed_count=len(input.episodes),
            error=str(e),
        )


@activity.defn
async def fetch_and_add_to_graph_bulk(
    input: FetchAndAddToGraphBulkInput,
) -> FetchAndAddToGraphBulkOutput:
    """
    Fetch entries and add them to the global knowledge graph.

    Combines fetching and adding to avoid large payloads crossing
    the Temporal boundary. Only returns counts, not content.

    Parameters
    ----------
    input : FetchAndAddToGraphBulkInput
        List of entry IDs to fetch and add.

    Returns
    -------
    FetchAndAddToGraphBulkOutput
        Success, failure, and skipped counts.
    """
    if not input.entry_ids:
        return FetchAndAddToGraphBulkOutput(success_count=0, failed_count=0, skipped_count=0)

    backend = _get_backend()
    config = get_config()

    logger.info(
        "Fetching and adding entries to global graph",
        entries=len(input.entry_ids),
        backend=backend,
    )

    # Fetch entries from API
    async with APIClient(config.api_url, config.api_token) as api:

        async def fetch_entry(entry_id: str) -> dict[str, Any] | None:
            entry = await api.get_entry(entry_id)
            if "error" in entry or not entry:
                return None
            return {
                "id": entry_id,
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "filteredContent": entry.get("filteredContent", ""),
                "full_content": entry.get("fullContent", ""),
                "feed_content": entry.get("feedContent", ""),
            }

        tasks = [fetch_entry(str(eid)) for eid in input.entry_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Build episodes from fetched entries
    episodes: list[dict[str, Any]] = []
    skipped_count = 0

    for result in results:
        if isinstance(result, BaseException):
            logger.warning(f"Failed to fetch entry: {result}")
            skipped_count += 1
            continue
        if result is None:
            skipped_count += 1
            continue

        # Priority: filteredContent → full_content → feed_content
        content = result.get("filteredContent") or ""
        if not content:
            content = result.get("full_content") or ""
        if not content:
            content = result.get("feed_content") or ""
        if not content:
            skipped_count += 1
            continue

        episodes.append(
            {
                "entry_id": result["id"],
                "content": content,
                "title": result.get("title"),
                "url": result.get("url"),
                "source_type": "entry",
            }
        )

    if not episodes:
        logger.info("No episodes to add (all entries skipped)")
        return FetchAndAddToGraphBulkOutput(
            success_count=0,
            failed_count=0,
            skipped_count=skipped_count,
        )

    # Add to graph
    try:
        success_count, failed_count = await _add_contents_bulk(episodes)

        logger.info(
            "Fetch and add completed",
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        )

        return FetchAndAddToGraphBulkOutput(
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        )

    except Exception as e:
        logger.error(f"Error in fetch and add to global graph: {e}")
        return FetchAndAddToGraphBulkOutput(
            success_count=0,
            failed_count=len(episodes),
            skipped_count=skipped_count,
            error=str(e),
        )


@activity.defn
async def reset_global_graph() -> ResetGlobalGraphOutput:
    """
    Reset the global knowledge graph.

    Deletes all nodes and relationships from the graph storage.

    Returns
    -------
    ResetGlobalGraphOutput
        Success status and deleted node count.
    """
    backend = _get_backend()
    logger.info("Resetting global knowledge graph", backend=backend)

    try:
        success, deleted_count = await _reset_graph()

        if success:
            logger.info("Global graph reset successfully", deleted_count=deleted_count)
        else:
            logger.warning("Failed to reset global graph")

        return ResetGlobalGraphOutput(
            success=success,
            deleted_count=deleted_count,
        )

    except Exception as e:
        logger.error(f"Error resetting global graph: {e}")
        return ResetGlobalGraphOutput(
            success=False,
            deleted_count=0,
            error=str(e),
        )


@activity.defn
async def get_entries_for_graph_update(
    input: GetEntriesForGraphUpdateInput,
) -> GetEntriesForGraphUpdateOutput:
    """
    Get entries pending graph update.

    Fetches entries with filteredContent that haven't been added to the graph yet
    and have keep=true.

    Parameters
    ----------
    input : GetEntriesForGraphUpdateInput
        Batch size and optional cursor for pagination.

    Returns
    -------
    GetEntriesForGraphUpdateOutput
        List of entry IDs, total count, and pagination info.
    """
    config = get_config()

    async with APIClient(config.api_url, config.api_token) as api:
        result = await api.list_entries_paginated(
            limit=input.batch_size,
            graph_added=False,
            keep_only=True,
            after=input.after,
        )

        entries = result.get("entries", [])
        page_info = result.get("pageInfo", {})
        total_count = result.get("totalCount", 0)

        entry_ids = [entry["id"] for entry in entries]
        has_more = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")

        logger.info(
            "Found entries pending graph update",
            entries=len(entry_ids),
            total_count=total_count,
            has_more=has_more,
        )

        return GetEntriesForGraphUpdateOutput(
            entry_ids=entry_ids,
            total_count=total_count,
            has_more=has_more,
            end_cursor=end_cursor,
        )


@activity.defn
async def mark_entries_graph_added(
    input: MarkEntriesGraphAddedInput,
) -> MarkEntriesGraphAddedOutput:
    """
    Mark entries as added to the knowledge graph.

    Parameters
    ----------
    input : MarkEntriesGraphAddedInput
        List of entry IDs to mark.

    Returns
    -------
    MarkEntriesGraphAddedOutput
        Updated count and any error.
    """
    if not input.entry_ids:
        return MarkEntriesGraphAddedOutput(updated_count=0)

    config = get_config()

    async with APIClient(config.api_url, config.api_token) as api:
        result = await api.mark_entries_graph_added(input.entry_ids)

        if "error" in result:
            logger.error(f"Failed to mark entries as graph-added: {result['error']}")
            return MarkEntriesGraphAddedOutput(
                updated_count=0,
                error=result["error"],
            )

        updated_count = result.get("updatedCount", 0)
        logger.info("Marked entries as graph-added", updated_count=updated_count)

        return MarkEntriesGraphAddedOutput(updated_count=updated_count)
