"""Search service for Meilisearch via Next.js API."""

import httpx

from buun_curator_agent.logging import get_logger
from buun_curator_agent.models.research import RetrievedDoc
from buun_curator_agent.services.api import APIService

logger = get_logger(__name__)


class SearchService(APIService):
    """Service for searching entries via Meilisearch."""

    async def search_entries(
        self,
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
        url = f"{self.api_base_url}/api/search"
        params: dict[str, str | int] = {
            "q": query,
            "limit": limit,
        }
        if feed_id:
            params["feedId"] = feed_id

        try:
            async with self._get_client() as client:
                response = await client.get(url, params=params, headers=self._get_headers())

                if response.status_code == 503:
                    logger.warning(
                        "Meilisearch is not configured, returning empty results",
                        query=query,
                    )
                    return []

                response.raise_for_status()
                data = response.json()

                results: list[RetrievedDoc] = []
                for entry in data.get("entries", []):
                    results.append(
                        RetrievedDoc(
                            source="meilisearch",
                            id=entry["id"],
                            title=entry["title"],
                            content=entry.get("summary", ""),
                            url=entry.get("url"),
                            relevance_score=None,
                        )
                    )

                logger.info(
                    "Search completed",
                    query=query,
                    result_count=len(results),
                    total_count=data.get("totalCount", 0),
                )
                return results

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Search API error: {e.response.status_code} - {e.response.text}",
                query=query,
                error_type=type(e).__name__,
            )
            return []
        except Exception as e:
            logger.error(
                f"Search failed: {e}",
                query=query,
                error_type=type(e).__name__,
            )
            return []
