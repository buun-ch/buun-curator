"""Meilisearch tool for Deep Research."""

from buun_curator_agent.config import settings
from buun_curator_agent.models.research import RetrievedDoc
from buun_curator_agent.services.search import SearchService

# Module-level service instance
_search_service: SearchService | None = None


def _get_search_service() -> SearchService:
    """Get or create the search service singleton."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService(
            api_base_url=settings.api_base_url,
            api_token=settings.internal_api_token,
        )
    return _search_service


async def search_entries(
    query: str,
    limit: int = 10,
    feed_id: str | None = None,
) -> list[RetrievedDoc]:
    """
    Search entries using Meilisearch via the Next.js API.

    Parameters
    ----------
    query : str
        Search query string.
    limit : int, optional
        Maximum number of results (default: 10).
    feed_id : str | None, optional
        Filter by feed ID.

    Returns
    -------
    list[RetrievedDoc]
        List of retrieved documents.
    """
    service = _get_search_service()
    return await service.search_entries(query, limit, feed_id)
