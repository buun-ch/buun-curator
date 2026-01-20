"""
Search Index Activities for Temporal.

Activities for Meilisearch index management.
"""

import asyncio

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    ClearSearchIndexInput,
    ClearSearchIndexOutput,
    GetEntryIdsForIndexingInput,
    GetEntryIdsForIndexingOutput,
    GetOrphanedDocumentIdsInput,
    GetOrphanedDocumentIdsOutput,
    IndexEntriesBatchInput,
    IndexEntriesBatchOutput,
    InitSearchIndexInput,
    InitSearchIndexOutput,
    RemoveDocumentsFromIndexInput,
    RemoveDocumentsFromIndexOutput,
    UpdateEntryIndexInput,
    UpdateEntryIndexOutput,
)
from buun_curator.services.api import APIClient
from buun_curator.services.search import (
    delete_all_documents,
    get_all_document_ids,
    index_entries,
    initialize_index,
    is_meilisearch_enabled,
    remove_entries,
    update_entry,
)

logger = get_logger(__name__)


@activity.defn
async def init_search_index(
    input: InitSearchIndexInput,  # noqa: ARG001 - Required by Temporal
) -> InitSearchIndexOutput:
    """
    Initialize Meilisearch index with proper settings.

    Creates the index if needed and configures searchable/filterable attributes.

    Returns
    -------
    InitSearchIndexOutput
        Output containing success status and optional error.
    """
    if not is_meilisearch_enabled():
        logger.warning("Meilisearch not configured")
        return InitSearchIndexOutput(success=False, error="Meilisearch not configured")

    try:
        success = await asyncio.to_thread(initialize_index)
        if success:
            logger.info("Search index initialized successfully")
            return InitSearchIndexOutput(success=True)
        else:
            return InitSearchIndexOutput(success=False, error="Failed to initialize index")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to initialize search index: {error_msg}")
        return InitSearchIndexOutput(success=False, error=error_msg)


@activity.defn
async def get_entry_ids_for_indexing(
    input: GetEntryIdsForIndexingInput,
) -> GetEntryIdsForIndexingOutput:
    """
    Get entry IDs for batch indexing.

    Fetches entry IDs from the database with cursor-based pagination.

    Parameters
    ----------
    input : GetEntryIdsForIndexingInput
        Input containing batch_size and cursor.

    Returns
    -------
    GetEntryIdsForIndexingOutput
        Output containing entry_ids, total_count, has_more, and end_cursor.
    """
    config = get_config()

    async with APIClient(config.api_url, config.api_token) as api:
        # Fetch entries with cursor-based pagination
        result = await api.list_entries_paginated(
            limit=input.batch_size,
            after=input.after,
        )

        entries = result["entries"]
        page_info = result["pageInfo"]
        total_count = result["totalCount"]

        entry_ids = [str(e["id"]) for e in entries]
        has_more = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")

        logger.info(
            "Got entry IDs for indexing",
            count=len(entry_ids),
            cursor=input.after,
            total=total_count,
            has_more=has_more,
        )

        return GetEntryIdsForIndexingOutput(
            entry_ids=entry_ids,
            total_count=total_count,
            has_more=has_more,
            end_cursor=end_cursor,
        )


@activity.defn
async def index_entries_batch(
    input: IndexEntriesBatchInput,
) -> IndexEntriesBatchOutput:
    """
    Index a batch of entries in Meilisearch.

    Fetches full entry data and indexes in Meilisearch.

    Parameters
    ----------
    input : IndexEntriesBatchInput
        Input containing entry_ids to index.

    Returns
    -------
    IndexEntriesBatchOutput
        Output containing indexed_count and optional error.
    """
    if not input.entry_ids:
        return IndexEntriesBatchOutput(indexed_count=0)

    if not is_meilisearch_enabled():
        logger.warning("Meilisearch not configured, skipping indexing")
        return IndexEntriesBatchOutput(indexed_count=0, error="Meilisearch not configured")

    config = get_config()
    entries_to_index: list[dict] = []

    async with APIClient(config.api_url, config.api_token) as api:
        # Fetch full entry data for each ID
        for entry_id in input.entry_ids:
            activity.heartbeat(f"Fetching entry {entry_id}")
            entry = await api.get_entry(entry_id)
            if entry and "error" not in entry:
                entries_to_index.append(entry)

    if not entries_to_index:
        logger.warning("No entries to index")
        return IndexEntriesBatchOutput(indexed_count=0)

    try:
        activity.heartbeat(f"Indexing {len(entries_to_index)} entries")
        success = await asyncio.to_thread(index_entries, entries_to_index)
        if success:
            logger.info("Indexed entries", count=len(entries_to_index))
            return IndexEntriesBatchOutput(indexed_count=len(entries_to_index))
        else:
            return IndexEntriesBatchOutput(indexed_count=0, error="Indexing failed")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to index entries: {error_msg}")
        return IndexEntriesBatchOutput(indexed_count=0, error=error_msg)


@activity.defn
async def clear_search_index(
    input: ClearSearchIndexInput,  # noqa: ARG001 - Required by Temporal
) -> ClearSearchIndexOutput:
    """
    Delete all documents from the Meilisearch index.

    Returns
    -------
    ClearSearchIndexOutput
        Output containing success status and optional error.
    """
    if not is_meilisearch_enabled():
        logger.warning("Meilisearch not configured")
        return ClearSearchIndexOutput(success=False, error="Meilisearch not configured")

    try:
        success = await asyncio.to_thread(delete_all_documents)
        if success:
            logger.info("Cleared all documents from search index")
            return ClearSearchIndexOutput(success=True)
        else:
            return ClearSearchIndexOutput(success=False, error="Failed to clear index")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to clear search index: {error_msg}")
        return ClearSearchIndexOutput(success=False, error=error_msg)


@activity.defn
async def get_orphaned_document_ids(
    input: GetOrphanedDocumentIdsInput,
) -> GetOrphanedDocumentIdsOutput:
    """
    Find document IDs in Meilisearch that don't exist in the database.

    Compares document IDs in Meilisearch with entry IDs in the database
    to identify orphaned documents that should be removed.

    Parameters
    ----------
    input : GetOrphanedDocumentIdsInput
        Input containing batch_size for fetching from Meilisearch.

    Returns
    -------
    GetOrphanedDocumentIdsOutput
        Output containing orphaned_ids and counts.
    """
    if not is_meilisearch_enabled():
        logger.warning("Meilisearch not configured")
        return GetOrphanedDocumentIdsOutput(error="Meilisearch not configured")

    config = get_config()

    try:
        # Get all document IDs from Meilisearch
        activity.heartbeat("Fetching document IDs from Meilisearch")
        all_doc_ids = await asyncio.to_thread(get_all_document_ids, input.batch_size)
        index_ids = set(all_doc_ids)
        total_in_index = len(index_ids)

        if not index_ids:
            logger.info("No documents in Meilisearch index")
            return GetOrphanedDocumentIdsOutput(
                orphaned_ids=[],
                total_in_index=0,
                total_in_db=0,
            )

        # Get all entry IDs from database
        activity.heartbeat("Fetching entry IDs from database")
        db_ids: set[str] = set()

        async with APIClient(config.api_url, config.api_token) as api:
            cursor: str | None = None
            while True:
                result = await api.list_entries_paginated(limit=100, after=cursor)
                entries = result["entries"]
                page_info = result["pageInfo"]

                for entry in entries:
                    db_ids.add(str(entry["id"]))

                if not page_info.get("hasNextPage", False):
                    break
                cursor = page_info.get("endCursor")
                activity.heartbeat(f"Fetched {len(db_ids)} entry IDs from DB")

        total_in_db = len(db_ids)

        # Find orphaned IDs (in index but not in DB)
        orphaned_ids = list(index_ids - db_ids)

        logger.info(
            "Found orphaned documents",
            orphaned_count=len(orphaned_ids),
            total_in_index=total_in_index,
            total_in_db=total_in_db,
        )

        return GetOrphanedDocumentIdsOutput(
            orphaned_ids=orphaned_ids,
            total_in_index=total_in_index,
            total_in_db=total_in_db,
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to get orphaned document IDs: {error_msg}")
        return GetOrphanedDocumentIdsOutput(error=error_msg)


@activity.defn
async def remove_documents_from_index(
    input: RemoveDocumentsFromIndexInput,
) -> RemoveDocumentsFromIndexOutput:
    """
    Remove documents from the Meilisearch index.

    Parameters
    ----------
    input : RemoveDocumentsFromIndexInput
        Input containing document_ids to remove.

    Returns
    -------
    RemoveDocumentsFromIndexOutput
        Output containing removed_count and optional error.
    """
    if not input.document_ids:
        return RemoveDocumentsFromIndexOutput(removed_count=0)

    if not is_meilisearch_enabled():
        logger.warning("Meilisearch not configured")
        return RemoveDocumentsFromIndexOutput(error="Meilisearch not configured")

    try:
        activity.heartbeat(f"Removing {len(input.document_ids)} documents")
        success = await asyncio.to_thread(remove_entries, input.document_ids)
        if success:
            logger.info("Removed documents from index", count=len(input.document_ids))
            return RemoveDocumentsFromIndexOutput(removed_count=len(input.document_ids))
        else:
            return RemoveDocumentsFromIndexOutput(error="Failed to remove documents")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to remove documents: {error_msg}")
        return RemoveDocumentsFromIndexOutput(error=error_msg)


@activity.defn
async def update_entry_index(
    input: UpdateEntryIndexInput,
) -> UpdateEntryIndexOutput:
    """
    Update a single entry in the Meilisearch index.

    Fetches the entry data from the API and updates its index document.

    Parameters
    ----------
    input : UpdateEntryIndexInput
        Input containing entry_id to update.

    Returns
    -------
    UpdateEntryIndexOutput
        Output containing success status and optional error.
    """
    if not is_meilisearch_enabled():
        logger.warning("Meilisearch not configured")
        return UpdateEntryIndexOutput(success=True)  # Skip silently

    config = get_config()

    try:
        async with APIClient(config.api_url, config.api_token) as api:
            entry = await api.get_entry(str(input.entry_id))
            if not entry or "error" in entry:
                return UpdateEntryIndexOutput(
                    success=False, error=f"Entry not found: {input.entry_id}"
                )

        success = await asyncio.to_thread(update_entry, entry)
        if success:
            logger.info("Updated entry in search index", entry_id=str(input.entry_id))
            return UpdateEntryIndexOutput(success=True)
        else:
            return UpdateEntryIndexOutput(success=False, error="Failed to update index")
    except Exception as e:
        error_msg = str(e)
        logger.error(
            "Failed to update entry in search index",
            entry_id=str(input.entry_id),
            error=error_msg,
        )
        return UpdateEntryIndexOutput(success=False, error=error_msg)
