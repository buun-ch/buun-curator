"""
Meilisearch service for indexing and searching entries.
"""

import os
from datetime import datetime
from typing import Any

import meilisearch

from buun_curator.logging import get_logger

logger = get_logger(__name__)


def is_meilisearch_enabled() -> bool:
    """Check if Meilisearch is configured."""
    host = os.getenv("MEILISEARCH_HOST")
    api_key = os.getenv("MEILISEARCH_API_KEY")
    return bool(host and api_key)


def get_meilisearch_client() -> meilisearch.Client | None:
    """
    Create a Meilisearch client instance.

    Returns None if Meilisearch is not configured.
    """
    host = os.getenv("MEILISEARCH_HOST")
    api_key = os.getenv("MEILISEARCH_API_KEY")

    if not host or not api_key:
        return None

    # Add protocol if not present
    if not host.startswith("http"):
        host = f"http://{host}"

    return meilisearch.Client(host, api_key)


def get_index_name() -> str:
    """Get the Meilisearch index name from environment."""
    return os.getenv("MEILISEARCH_INDEX", "buun-curator")


def datetime_to_timestamp(dt: datetime | str | None) -> int | None:
    """Convert datetime to Unix timestamp."""
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    return int(dt.timestamp())


def entry_to_document(entry: dict[str, Any]) -> dict[str, Any]:
    """
    Convert an entry dict to a Meilisearch document.

    Parameters
    ----------
    entry : dict
        Entry data from the database.

    Returns
    -------
    dict
        Document suitable for Meilisearch indexing.

    Note
    ----
    isRead/isStarred are not indexed - they change frequently and
    should be fetched from DB when displaying search results.
    """
    return {
        "id": entry["id"],
        "feedId": entry.get("feedId") or entry.get("feed_id", ""),
        "title": entry.get("title", ""),
        "summary": entry.get("summary", "") or "",
        "feedContent": entry.get("feedContent") or entry.get("feed_content", "") or "",
        "filteredContent": (
            entry.get("filteredContent") or entry.get("filtered_content", "") or ""
        ),
        "author": entry.get("author"),
        "publishedAt": datetime_to_timestamp(entry.get("publishedAt") or entry.get("published_at")),
        "createdAt": datetime_to_timestamp(
            entry.get("createdAt") or entry.get("created_at") or datetime.now()
        ),
    }


def index_entries(entries: list[dict[str, Any]]) -> bool:
    """
    Index entries in Meilisearch.

    Parameters
    ----------
    entries : list
        List of entry dicts to index.

    Returns
    -------
    bool
        True if indexing was successful or skipped, False on error.
    """
    if not entries:
        return True

    client = get_meilisearch_client()
    if client is None:
        # Meilisearch not configured, skip silently
        return True

    try:
        index = client.index(get_index_name())
        documents = [entry_to_document(entry) for entry in entries]
        index.add_documents(documents, primary_key="id")
        return True
    except Exception as e:
        logger.error(
            "Failed to index entries in Meilisearch",
            count=len(entries),
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


def remove_entries(entry_ids: list[str]) -> bool:
    """
    Remove entries from Meilisearch index.

    Parameters
    ----------
    entry_ids : list
        List of entry IDs to remove.

    Returns
    -------
    bool
        True if removal was successful or skipped, False on error.
    """
    if not entry_ids:
        return True

    client = get_meilisearch_client()
    if client is None:
        return True

    try:
        index = client.index(get_index_name())
        index.delete_documents(entry_ids)
        return True
    except Exception as e:
        logger.error(
            "Failed to remove entries from Meilisearch",
            count=len(entry_ids),
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


def initialize_index() -> bool:
    """
    Initialize Meilisearch index with proper settings.

    Creates the index if it doesn't exist and configures
    searchable attributes, filterable attributes, and ranking rules.

    Returns
    -------
    bool
        True if initialization was successful, False on error.
    """
    client = get_meilisearch_client()
    if client is None:
        logger.warning("Meilisearch not configured, skipping initialization")
        return False

    try:
        index_name = get_index_name()

        # Create index if it doesn't exist
        try:
            client.create_index(index_name, {"primaryKey": "id"})
            logger.info("Created Meilisearch index", index_name=index_name)
        except Exception as e:
            if "index_already_exists" not in str(e):
                raise
            logger.info("Meilisearch index already exists", index_name=index_name)

        index = client.index(index_name)

        # Configure searchable attributes (order matters for relevance)
        index.update_searchable_attributes(
            [
                "title",
                "summary",
                "filteredContent",
                "feedContent",
                "author",
            ]
        )

        # Configure filterable attributes
        # Note: isRead/isStarred are not indexed - managed in DB only
        index.update_filterable_attributes(
            [
                "feedId",
                "publishedAt",
                "createdAt",
            ]
        )

        # Configure sortable attributes
        index.update_sortable_attributes(["publishedAt", "createdAt"])

        # Configure ranking rules
        index.update_ranking_rules(
            [
                "words",
                "typo",
                "proximity",
                "attribute",
                "sort",
                "exactness",
            ]
        )

        # Configure typo tolerance for better CJK support
        index.update_typo_tolerance(
            {
                "enabled": True,
                "minWordSizeForTypos": {
                    "oneTypo": 4,
                    "twoTypos": 8,
                },
            }
        )

        logger.info("Meilisearch index settings configured")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize Meilisearch index: {e}")
        return False


def get_index_stats() -> dict[str, Any] | None:
    """
    Get Meilisearch index statistics.

    Returns
    -------
    dict | None
        Index stats including numberOfDocuments, or None on error.
    """
    client = get_meilisearch_client()
    if client is None:
        return None

    try:
        index = client.index(get_index_name())
        stats = index.get_stats()
        return stats.model_dump()
    except Exception as e:
        logger.error(f"Failed to get index stats: {e}")
        return None


def delete_all_documents() -> bool:
    """
    Delete all documents from the Meilisearch index.

    Returns
    -------
    bool
        True if deletion was successful or skipped, False on error.
    """
    client = get_meilisearch_client()
    if client is None:
        return True

    try:
        index = client.index(get_index_name())
        task = index.delete_all_documents()
        # Wait for task to complete
        client.wait_for_task(task.task_uid, timeout_in_ms=60000)
        logger.info("Deleted all documents from Meilisearch index")
        return True
    except Exception as e:
        logger.error(f"Failed to delete all documents: {e}")
        return False


def get_all_document_ids(batch_size: int = 1000) -> list[str]:
    """
    Get all document IDs from the Meilisearch index.

    Parameters
    ----------
    batch_size : int
        Number of documents to fetch per request (default: 1000).

    Returns
    -------
    list[str]
        List of all document IDs in the index.
    """
    client = get_meilisearch_client()
    if client is None:
        return []

    try:
        index = client.index(get_index_name())
        all_ids: list[str] = []
        offset = 0

        while True:
            # Fetch only the id field to minimize data transfer
            result = index.get_documents(
                {"offset": offset, "limit": batch_size, "fields": ["id"]}
            )
            documents = result.results

            if not documents:
                break

            # Document objects from Meilisearch can be dict-like or have attributes
            for doc in documents:
                doc_id = doc.get("id") if isinstance(doc, dict) else getattr(doc, "id", None)
                if doc_id:
                    all_ids.append(str(doc_id))
            offset += len(documents)

            # Check if we've fetched all documents
            if len(documents) < batch_size:
                break

        logger.info("Found documents in Meilisearch index", count=len(all_ids))
        return all_ids
    except Exception as e:
        logger.error(f"Failed to get document IDs: {e}")
        return []
