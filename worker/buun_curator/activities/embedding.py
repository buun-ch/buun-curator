"""
Embedding Activities.

Temporal activities for computing and saving entry embeddings.
Uses FastEmbed for local embedding generation.
"""

from typing import Any

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    ComputeEmbeddingsInput,
    ComputeEmbeddingsOutput,
    GetEntriesForEmbeddingInput,
    GetEntriesForEmbeddingOutput,
)
from buun_curator.services.api import APIClient
from buun_curator.services.embedder import compute_embeddings as compute_embeddings_batch

logger = get_logger(__name__)


async def _get_entries_content(
    api: APIClient, entry_ids: list[str]
) -> list[dict[str, Any]]:
    """
    Fetch entries and extract content for embedding.

    Parameters
    ----------
    api : APIClient
        API client instance.
    entry_ids : list[str]
        Entry IDs to fetch.

    Returns
    -------
    list[dict[str, Any]]
        List of dicts with entry_id and text for embedding.
    """
    entries = []
    for entry_id in entry_ids:
        entry = await api.get_entry(entry_id)
        if not entry:
            logger.warning("Entry not found", entry_id=entry_id)
            continue

        # Use filteredContent > summary > title for embedding
        text = (
            entry.get("filteredContent")
            or entry.get("summary")
            or entry.get("title")
            or ""
        )

        if text:
            entries.append({"entry_id": entry_id, "text": text})
        else:
            logger.warning("No content for embedding", entry_id=entry_id)

    return entries


@activity.defn
async def compute_embeddings(
    input: ComputeEmbeddingsInput,
) -> ComputeEmbeddingsOutput:
    """
    Compute and save embeddings for entries.

    Fetches entry content, computes embeddings using FastEmbed,
    and saves them via API.

    Parameters
    ----------
    input : ComputeEmbeddingsInput
        Entry IDs to process.

    Returns
    -------
    ComputeEmbeddingsOutput
        Count of computed and saved embeddings.
    """
    if not input.entry_ids:
        return ComputeEmbeddingsOutput(computed_count=0, saved_count=0)

    config = get_config()
    entry_ids = [str(eid) for eid in input.entry_ids]

    logger.info("Computing embeddings", count=len(entry_ids))

    try:
        async with APIClient(config.api_url, config.api_token) as api:
            # 1. Fetch entry content
            entries = await _get_entries_content(api, entry_ids)

            if not entries:
                logger.warning("No entries with content found")
                return ComputeEmbeddingsOutput(computed_count=0, saved_count=0)

            # 2. Compute embeddings
            texts = [e["text"] for e in entries]
            embeddings = await compute_embeddings_batch(texts)

            computed_count = len(embeddings)
            logger.info("Computed embeddings", count=computed_count)

            # 3. Save embeddings via API
            embedding_data = [
                {"entryId": entries[i]["entry_id"], "embedding": embeddings[i].tolist()}
                for i in range(len(entries))
            ]

            result = await api.save_embeddings(embedding_data)

            if "error" in result:
                logger.error(f"Failed to save embeddings: {result['error']}")
                return ComputeEmbeddingsOutput(
                    computed_count=computed_count,
                    saved_count=0,
                    error=result["error"],
                )

            saved_count = result.get("updatedCount", 0)
            logger.info(
                "Saved embeddings",
                saved_count=saved_count,
                computed_count=computed_count,
            )

            return ComputeEmbeddingsOutput(
                computed_count=computed_count,
                saved_count=saved_count,
            )

    except Exception as e:
        logger.error(
            f"Error computing embeddings: {e}",
            error_type=type(e).__name__,
        )
        return ComputeEmbeddingsOutput(
            computed_count=0,
            saved_count=0,
            error=str(e),
        )


@activity.defn
async def get_entries_for_embedding(
    input: GetEntriesForEmbeddingInput,
) -> GetEntriesForEmbeddingOutput:
    """
    Get entries that need embeddings (have content but no embedding).

    Parameters
    ----------
    input : GetEntriesForEmbeddingInput
        Batch size and cursor for pagination.

    Returns
    -------
    GetEntriesForEmbeddingOutput
        Entry IDs and pagination info.
    """
    config = get_config()

    try:
        async with APIClient(config.api_url, config.api_token) as api:
            result = await api.get_entries_for_embedding(
                batch_size=input.batch_size,
                after=input.after,
            )

            if "error" in result:
                logger.error(f"Failed to get entries for embedding: {result['error']}")
                return GetEntriesForEmbeddingOutput()

            return GetEntriesForEmbeddingOutput(
                entry_ids=result.get("entryIds", []),
                total_count=result.get("totalCount", 0),
                has_more=result.get("hasMore", False),
                end_cursor=result.get("endCursor"),
            )

    except Exception as e:
        logger.error(
            f"Error getting entries for embedding: {e}",
            error_type=type(e).__name__,
        )
        return GetEntriesForEmbeddingOutput()
