"""Entry service for fetching entry data from Next.js API."""

from datetime import datetime

from pydantic import BaseModel

from buun_curator_agent.services.api import APIService


class Entry(BaseModel):
    """Entry data from the API."""

    id: str
    feed_id: str
    feed_name: str | None = None
    feed_site_url: str | None = None
    title: str
    url: str
    feed_content: str = ""
    full_content: str = ""
    filtered_content: str = ""
    translated_content: str = ""
    summary: str = ""
    author: str | None = None
    published_at: datetime | None = None
    is_read: bool = False
    is_starred: bool = False
    preference: str | None = None
    metadata: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EntryService(APIService):
    """Service for fetching entry data from Next.js API."""

    async def get_entry(self, entry_id: str) -> Entry | None:
        """
        Fetch an entry by ID from the API.

        Parameters
        ----------
        entry_id : str
            The entry ID to fetch.

        Returns
        -------
        Entry | None
            The entry data, or None if not found.
        """
        url = f"{self.api_base_url}/api/entries/{entry_id}"

        async with self._get_client() as client:
            response = await client.get(url, headers=self._get_headers())

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            return Entry(
                id=data["id"],
                feed_id=data["feedId"],
                feed_name=data.get("feedName"),
                feed_site_url=data.get("feedSiteUrl"),
                title=data["title"],
                url=data["url"],
                feed_content=data.get("feedContent", ""),
                full_content=data.get("fullContent", ""),
                filtered_content=data.get("filteredContent", ""),
                translated_content=data.get("translatedContent", ""),
                summary=data.get("summary", ""),
                author=data.get("author"),
                published_at=data.get("publishedAt"),
                is_read=data.get("isRead", False),
                is_starred=data.get("isStarred", False),
                preference=data.get("preference"),
                metadata=data.get("metadata"),
                created_at=data.get("createdAt"),
                updated_at=data.get("updatedAt"),
            )

    def build_context(self, entry: Entry) -> str:
        """
        Build context string from entry for the AI assistant.

        Parameters
        ----------
        entry : Entry
            The entry to build context from.

        Returns
        -------
        str
            Formatted context string for the system prompt.
        """
        parts = [f"# {entry.title}"]

        if entry.feed_name:
            parts.append(f"Source: {entry.feed_name}")

        if entry.author:
            parts.append(f"Author: {entry.author}")

        if entry.published_at:
            parts.append(f"Published: {entry.published_at}")

        parts.append(f"URL: {entry.url}")
        parts.append("")

        # Use the best available content
        content = (
            entry.translated_content
            or entry.filtered_content
            or entry.full_content
            or entry.feed_content
        )

        if content:
            parts.append("## Content")
            parts.append(content)

        if entry.summary:
            parts.append("")
            parts.append("## Summary")
            parts.append(entry.summary)

        return "\n".join(parts)
