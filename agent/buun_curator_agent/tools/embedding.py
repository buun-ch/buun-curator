"""Embedding-based semantic search tool for Deep Research."""

import httpx

from buun_curator_agent.config import settings
from buun_curator_agent.logging import get_logger
from buun_curator_agent.models.research import RetrievedDoc
from buun_curator_agent.services.embedder import compute_query_embedding

logger = get_logger(__name__)


async def search_entries_by_embedding(
    query: str,
    limit: int = 10,
    threshold: float = 0.8,
) -> list[RetrievedDoc]:
    """
    Search entries using embedding vector similarity.

    Computes embedding for the query and searches via the Next.js API.

    Parameters
    ----------
    query : str
        Search query string.
    limit : int, optional
        Maximum number of results (default: 10).
    threshold : float, optional
        Maximum cosine distance threshold (default: 0.8).

    Returns
    -------
    list[RetrievedDoc]
        List of retrieved documents.
    """
    try:
        # Compute embedding for query
        embedding = await compute_query_embedding(query)

        # Call the vector search API
        url = f"{settings.api_base_url}/api/entries/search-by-vector"
        headers: dict[str, str] = {}
        if settings.internal_api_token:
            headers["Authorization"] = f"Bearer {settings.internal_api_token}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                json={
                    "embedding": embedding,
                    "limit": limit,
                    "threshold": threshold,
                },
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            results: list[RetrievedDoc] = []
            for entry in data.get("entries", []):
                # Convert similarity score (cosine distance) to relevance
                # Lower distance = higher relevance
                similarity_score = entry.get("similarityScore")
                relevance = 1.0 - similarity_score if similarity_score is not None else None

                results.append(
                    RetrievedDoc(
                        source="embedding",
                        id=entry["id"],
                        title=entry["title"],
                        content=entry.get("summary", ""),
                        url=entry.get("url"),
                        relevance_score=relevance,
                    )
                )

            logger.info(
                "Embedding search completed",
                query=query[:50],
                result_count=len(results),
                total_count=data.get("totalCount", 0),
            )
            return results

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Embedding search API error: {e.response.status_code} - {e.response.text}",
            query=query[:50],
            error_type=type(e).__name__,
        )
        return []
    except Exception as e:
        logger.error(
            f"Embedding search failed: {e}",
            query=query[:50],
            error_type=type(e).__name__,
        )
        return []
