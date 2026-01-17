"""
REST API Client for Buun Curator.

Provides a client for communicating with the Buun Curator REST API.
This is the preferred method over MCP for better parallelism.
"""

from typing import Any

import httpx

from buun_curator.logging import get_logger

logger = get_logger(__name__)


class APIClient:
    """
    Client for Buun Curator REST API.
    """

    # Default connection limits to prevent connection exhaustion
    DEFAULT_MAX_CONNECTIONS = 20
    DEFAULT_MAX_KEEPALIVE = 5

    def __init__(
        self,
        base_url: str,
        api_token: str = "",
        timeout: float = 30.0,
        max_connections: int | None = None,
        max_keepalive_connections: int | None = None,
    ):
        """
        Initialize the API client.

        Parameters
        ----------
        base_url : str
            Base URL of the API (e.g., "http://localhost:3000").
        api_token : str, optional
            Internal API token for authentication (default: "").
        timeout : float, optional
            Request timeout in seconds (default: 30.0).
        max_connections : int | None, optional
            Maximum concurrent connections (default: 20).
        max_keepalive_connections : int | None, optional
            Maximum keepalive connections (default: 5).
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.max_connections = max_connections or self.DEFAULT_MAX_CONNECTIONS
        self.max_keepalive_connections = max_keepalive_connections or self.DEFAULT_MAX_KEEPALIVE
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "APIClient":
        """Enter async context and create HTTP client."""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        # Configure connection limits to prevent resource exhaustion
        limits = httpx.Limits(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_keepalive_connections,
        )

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=headers,
            limits=limits,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context and close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get the HTTP client, raising if not in context."""
        if not self._client:
            raise RuntimeError("APIClient must be used as async context manager")
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """
        Make an HTTP request and return the JSON response.

        Parameters
        ----------
        method : str
            HTTP method (GET, POST, PATCH, etc.).
        path : str
            API path (e.g., "/api/feeds").
        json : dict[str, Any] | None, optional
            JSON body for POST/PATCH requests.

        Returns
        -------
        dict[str, Any] | list[Any]
            Parsed JSON response.

        Raises
        ------
        httpx.HTTPStatusError
            If the response status code indicates an error.
        """
        client = self._get_client()

        # start_time = time.perf_counter()
        # logger.debug("API request", method=method, path=path)

        response = await client.request(method, path, json=json)

        # elapsed_ms = (time.perf_counter() - start_time) * 1000
        # logger.debug(
        #     "API response",
        #     method=method,
        #     path=path,
        #     status=response.status_code,
        #     elapsed_ms=round(elapsed_ms, 1),
        # )

        response.raise_for_status()
        return response.json()

    # Feed operations

    async def list_feeds(self) -> list[dict[str, Any]]:
        """
        Get all registered feeds.

        Returns
        -------
        list[dict[str, Any]]
            List of feed dicts.
        """
        result = await self._request("GET", "/api/feeds")
        return result if isinstance(result, list) else []

    async def get_feed(self, feed_id: str) -> dict[str, Any]:
        """
        Get feed details including etag and lastModified.

        Parameters
        ----------
        feed_id : str
            Feed ID to fetch.

        Returns
        -------
        dict[str, Any]
            Feed details dict, or empty dict if not found.
        """
        try:
            result = await self._request("GET", f"/api/feeds/{feed_id}")
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {}
            raise

    async def update_feed_checked(
        self, feed_id: str, etag: str = "", last_modified: str = ""
    ) -> dict[str, Any]:
        """
        Update feed's checkedAt and cache headers.

        Parameters
        ----------
        feed_id : str
            Feed ID to update.
        etag : str, optional
            ETag value to store (default: "").
        last_modified : str, optional
            Last-Modified value to store (default: "").

        Returns
        -------
        dict[str, Any]
            Updated feed dict.
        """
        result = await self._request(
            "POST",
            f"/api/feeds/{feed_id}/checked",
            json={"etag": etag, "lastModified": last_modified},
        )
        return result if isinstance(result, dict) else {}

    # Entry operations

    async def create_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new entry.

        Parameters
        ----------
        entry_data : dict[str, Any]
            Entry data to create.

        Returns
        -------
        dict[str, Any]
            Created entry dict or error.
        """
        try:
            result = await self._request("POST", "/api/entries", json=entry_data)
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            # Return error response body for 4xx errors
            if e.response.status_code in (400, 404, 409):
                return e.response.json()
            raise

    async def get_entry(self, entry_id: str) -> dict[str, Any]:
        """
        Get an entry by ID with full details.

        Parameters
        ----------
        entry_id : str
            Entry ID to fetch.

        Returns
        -------
        dict[str, Any]
            Entry details dict, or empty dict if not found.
        """
        try:
            result = await self._request("GET", f"/api/entries/{entry_id}")
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {}
            raise

    async def list_entries(
        self,
        feed_id: str | None = None,
        limit: int = 50,
        has_summary: bool | None = None,
        has_translation: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        List entries with optional filtering.

        Parameters
        ----------
        feed_id : str | None, optional
            Filter by feed ID (default: None).
        limit : int, optional
            Maximum entries to return (default: 50, max: 100).
        has_summary : bool | None, optional
            Filter by summary presence (default: None).
        has_translation : bool | None, optional
            Filter by translation presence (default: None).

        Returns
        -------
        list[dict[str, Any]]
            List of entry dicts.
        """
        result = await self.list_entries_paginated(
            feed_id=feed_id,
            limit=limit,
            has_summary=has_summary,
            has_translation=has_translation,
        )
        return result["entries"]

    async def list_entries_paginated(
        self,
        feed_id: str | None = None,
        limit: int = 50,
        has_summary: bool | None = None,
        has_translation: bool | None = None,
        graph_added: bool | None = None,
        keep_only: bool | None = None,
        after: str | None = None,
    ) -> dict[str, Any]:
        """
        List entries with pagination support.

        Parameters
        ----------
        feed_id : str | None, optional
            Filter by feed ID (default: None).
        limit : int, optional
            Maximum entries to return (default: 50, max: 100).
        has_summary : bool | None, optional
            Filter by summary presence (default: None).
        has_translation : bool | None, optional
            Filter by translation presence (default: None).
        graph_added : bool | None, optional
            Filter by graph status (default: None).
        keep_only : bool | None, optional
            Filter to only entries with keep=true (default: None).
        after : str | None, optional
            Cursor for pagination (default: None).

        Returns
        -------
        dict[str, Any]
            Dict with 'entries', 'pageInfo', and 'totalCount'.
        """
        params = [f"first={min(limit, 100)}"]
        if feed_id:
            params.append(f"feedId={feed_id}")
        if has_summary is not None:
            params.append(f"hasSummary={'true' if has_summary else 'false'}")
        if has_translation is not None:
            params.append(f"hasTranslation={'true' if has_translation else 'false'}")
        if graph_added is not None:
            params.append(f"graphAdded={'true' if graph_added else 'false'}")
        if keep_only is True:
            params.append("keepOnly=true")
        if after:
            params.append(f"after={after}")

        path = f"/api/entries?{'&'.join(params)}"
        result = await self._request("GET", path)

        # API returns { edges: [...], pageInfo: {...}, totalCount }
        if isinstance(result, dict) and "edges" in result:
            edges = result.get("edges", [])
            entries = [edge["node"] for edge in edges]
            end_cursor = edges[-1]["cursor"] if edges else None
            return {
                "entries": entries,
                "pageInfo": {
                    **result.get("pageInfo", {}),
                    "endCursor": end_cursor,
                },
                "totalCount": result.get("totalCount", 0),
            }
        return {"entries": [], "pageInfo": {}, "totalCount": 0}

    async def update_entry(
        self,
        entry_id: str,
        full_content: str = "",
        filtered_content: str = "",
        raw_html: str = "",
        summary: str = "",
        translated_content: str = "",
        thumbnail_url: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Update an entry's content fields.

        Parameters
        ----------
        entry_id : str
            Entry ID to update.
        full_content : str, optional
            Full content to set (default: "").
        filtered_content : str, optional
            Filtered content to set (default: "").
        raw_html : str, optional
            Raw HTML to set (default: "").
        summary : str, optional
            Summary to set (default: "").
        translated_content : str, optional
            Translated content to set (default: "").
        thumbnail_url : str, optional
            Thumbnail URL to set (default: "").
        metadata : dict[str, Any] | None, optional
            Metadata to merge (default: None).

        Returns
        -------
        dict[str, Any]
            Updated entry dict.
        """
        data: dict[str, Any] = {}
        if full_content:
            data["fullContent"] = full_content
        if filtered_content:
            data["filteredContent"] = filtered_content
        if raw_html:
            data["rawHtml"] = raw_html
        if summary:
            data["summary"] = summary
        if translated_content:
            data["translatedContent"] = translated_content
        if thumbnail_url:
            data["thumbnailUrl"] = thumbnail_url
        if metadata is not None:
            data["metadata"] = metadata

        try:
            result = await self._request("PATCH", f"/api/entries/{entry_id}", json=data)
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"error": "Entry not found"}
            raise

    async def save_entry_context(
        self,
        entry_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Save context data for an entry.

        Parameters
        ----------
        entry_id : str
            Entry ID to update.
        context : dict[str, Any]
            Context data to save.

        Returns
        -------
        dict[str, Any]
            Updated entry dict or error.
        """
        try:
            result = await self._request(
                "PATCH",
                f"/api/entries/{entry_id}/context",
                json={"context": context},
            )
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"error": "Entry not found"}
            raise

    async def save_entry_enrichment(
        self,
        entry_id: str,
        enrichment_type: str,
        data: dict[str, Any],
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Save an enrichment for an entry.

        Parameters
        ----------
        entry_id : str
            Entry ID to add enrichment to.
        enrichment_type : str
            Type of enrichment (e.g., 'github').
        data : dict[str, Any]
            Enrichment data to save.
        source : str | None, optional
            Source identifier (default: None).
        metadata : dict[str, Any] | None, optional
            Additional metadata (default: None).

        Returns
        -------
        dict[str, Any]
            Created enrichment dict or error.
        """
        payload: dict[str, Any] = {
            "type": enrichment_type,
            "data": data,
        }
        if source:
            payload["source"] = source
        if metadata:
            payload["metadata"] = metadata

        try:
            result = await self._request(
                "POST",
                f"/api/entries/{entry_id}/enrichments",
                json=payload,
            )
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"error": "Entry not found"}
            raise

    async def delete_entry_enrichment(
        self,
        entry_id: str,
        enrichment_type: str,
        source: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete enrichment(s) for an entry.

        Parameters
        ----------
        entry_id : str
            Entry ID to delete enrichment from.
        enrichment_type : str
            Type of enrichment (e.g., 'web_page', 'github').
        source : str | None, optional
            Source identifier. If None, deletes all enrichments of this type.

        Returns
        -------
        dict[str, Any]
            Result with 'deleted' bool and 'deletedCount' or error.
        """
        try:
            body: dict[str, str] = {"type": enrichment_type}
            if source is not None:
                body["source"] = source

            result = await self._request(
                "DELETE",
                f"/api/entries/{entry_id}/enrichments",
                json=body,
            )
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"error": "Not found", "deleted": False}
            raise

    async def save_entry_links(
        self,
        entry_id: str,
        links: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Save links for an entry.

        Parameters
        ----------
        entry_id : str
            Entry ID to add links to.
        links : list[dict[str, str]]
            List of links with 'url' and 'title' keys.

        Returns
        -------
        dict[str, Any]
            Result with savedCount or error.
        """
        try:
            result = await self._request(
                "POST",
                f"/api/entries/{entry_id}/links",
                json={"links": links},
            )
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"error": "Entry not found"}
            raise

    # Settings operations

    async def get_settings(self) -> dict[str, Any]:
        """
        Get application settings.

        Returns
        -------
        dict[str, Any]
            Settings dict with targetLanguage, etc.
        """
        result = await self._request("GET", "/api/settings")
        return result if isinstance(result, dict) else {}

    # SSE event operations

    async def send_sse_event(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Send an SSE event to all connected browser clients.

        Parameters
        ----------
        event_type : str
            Event type: "progress", "complete", or "error".
        data : dict[str, Any]
            Event payload.

        Returns
        -------
        bool
            True if event was sent successfully.
        """
        try:
            await self._request(
                "POST",
                "/api/events/send",
                json={"type": event_type, "data": data},
            )
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to send SSE event: {e.response.status_code}", event_type=event_type
            )
            return False

    async def send_progress(
        self,
        task_id: str,
        progress: int,
        message: str = "",
    ) -> bool:
        """
        Send a progress event to browser clients.

        Parameters
        ----------
        task_id : str
            Unique task identifier (e.g., workflow ID).
        progress : int
            Progress percentage (0-100).
        message : str, optional
            Human-readable progress message (default: "").

        Returns
        -------
        bool
            True if event was sent successfully.
        """
        data: dict[str, Any] = {"taskId": task_id, "progress": progress}
        if message:
            data["message"] = message
        return await self.send_sse_event("progress", data)

    async def send_complete(
        self,
        task_id: str,
        result: dict[str, Any] | None = None,
    ) -> bool:
        """
        Send a completion event to browser clients.

        Parameters
        ----------
        task_id : str
            Unique task identifier (e.g., workflow ID).
        result : dict[str, Any] | None, optional
            Result data to include (default: None).

        Returns
        -------
        bool
            True if event was sent successfully.
        """
        data: dict[str, Any] = {"taskId": task_id, "result": result or {}}
        return await self.send_sse_event("complete", data)

    async def send_error(
        self,
        task_id: str,
        error: str,
    ) -> bool:
        """
        Send an error event to browser clients.

        Parameters
        ----------
        task_id : str
            Unique task identifier (e.g., workflow ID).
        error : str
            Error message.

        Returns
        -------
        bool
            True if event was sent successfully.
        """
        return await self.send_sse_event("error", {"taskId": task_id, "error": error})

    async def mark_entries_graph_added(self, entry_ids: list[str]) -> dict[str, Any]:
        """
        Mark entries as added to the knowledge graph.

        Parameters
        ----------
        entry_ids : list[str]
            List of entry IDs to mark as graph-added.

        Returns
        -------
        dict[str, Any]
            Result with 'updatedCount' or error.
        """
        try:
            result = await self._request(
                "POST",
                "/api/entries/mark-graph-added",
                json={"entryIds": entry_ids},
            )
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to mark entries as graph-added: {e.response.status_code}",
                count=len(entry_ids),
            )
            return {"error": str(e)}

    async def save_embeddings(self, embeddings: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Save embeddings for entries.

        Parameters
        ----------
        embeddings : list[dict[str, Any]]
            List of dicts with 'entryId' and 'embedding' keys.

        Returns
        -------
        dict[str, Any]
            Result with 'updatedCount' or error.
        """
        try:
            result = await self._request(
                "POST",
                "/api/entries/embeddings",
                json={"embeddings": embeddings},
            )
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to save embeddings: {e.response.status_code}", count=len(embeddings)
            )
            return {"error": str(e)}

    async def get_entries_for_embedding(
        self, batch_size: int = 100, after: str | None = None
    ) -> dict[str, Any]:
        """
        Get entries that need embeddings.

        Parameters
        ----------
        batch_size : int, optional
            Number of entries to fetch (default: 100, max: 500).
        after : str | None, optional
            Cursor for pagination (default: None).

        Returns
        -------
        dict[str, Any]
            Dict with 'entryIds', 'totalCount', 'hasMore', 'endCursor'.
        """
        params = [f"first={min(batch_size, 500)}"]
        if after:
            params.append(f"after={after}")

        path = f"/api/entries/embeddings?{'&'.join(params)}"
        try:
            result = await self._request("GET", path)
            return result if isinstance(result, dict) else {}
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to get entries for embedding: {e.response.status_code}",
                batch_size=batch_size,
            )
            return {"error": str(e)}
