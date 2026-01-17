"""
Entry-related data models for content processing.
"""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from buun_curator.models.types import ULID


class ContentProcessingLLMOutput(BaseModel):
    """
    Result of content processing (filtering + summarization).

    Used as Structured Output for LLM response.
    """

    main_content_start_line: int = Field(
        default=1,
        description="Line number where main entry content STARTS (1-indexed). "
        "This is the first line of actual entry text, after any navigation/headers.",
        ge=1,
    )
    main_content_end_line: int = Field(
        default=1,
        description="Line number where main entry content ENDS (1-indexed). "
        "This is the last line of actual entry text, before any footer/related content.",
        ge=1,
    )
    summary: str = Field(description="3-4 sentence summary of the main content")


class BatchEntryResult(BaseModel):
    """Result for a single entry in batch processing."""

    entry_id: str = Field(description="The ENTRY_ID from the input")
    main_content_start_line: int = Field(
        default=1,
        description="Line number where main entry content STARTS (1-indexed)",
        ge=1,
    )
    main_content_end_line: int = Field(
        default=1,
        description="Line number where main entry content ENDS (1-indexed)",
        ge=1,
    )
    summary: str = Field(description="3-4 sentence summary of the entry content")


class BatchContentProcessingOutput(BaseModel):
    """
    Batch result of content processing for multiple entries.

    Used as Structured Output for LLM response.
    """

    results: list[BatchEntryResult] = Field(
        description="Processing results for each entry, in the same order as input"
    )


@dataclass
class FeedEntry:
    """
    Represents a feed entry to be processed.
    """

    entry_id: ULID
    feed_id: ULID
    feed_name: str
    title: str
    url: str
    feed_content: str  # Content from RSS/Atom feed
    author: str
    published_at: str | None


@dataclass
class CrawlResult:
    """
    Result of a crawl operation.
    """

    feeds_processed: int
    feeds_skipped: int  # 304 Not Modified
    entries_created: int
    entries_skipped: int  # Duplicates
    new_entries: list[dict]  # List of entry dicts for Temporal serialization
    # Detailed info
    feed_details: list[dict]  # Per-feed results
    entry_details: list[dict]  # Created entry details


@dataclass
class FetchedContent:
    """Represents fetched entry content."""

    full_content: str  # Markdown content
    raw_html: str = ""  # Original HTML for extraction rule creation
    screenshot: bytes | None = None  # PNG screenshot (base64 decoded)
    title: str = ""  # HTML page title from metadata


@dataclass
class ProcessedEntry:
    """
    Result of entry content processing (filtering + summarization).
    """

    entry_id: ULID
    summary: str
    filtered_content: str  # Content with irrelevant parts removed
    start_line: int = 1  # First line of main content (1-indexed)
    end_line: int = 0  # Last line of main content (1-indexed), 0 = not set


@dataclass
class EntryToProcess:
    """
    Entry data for content processing.
    """

    entry_id: ULID
    title: str
    url: str
    full_content: str  # Markdown content


@dataclass
class EntryToTranslate:
    """
    Entry data for translation.
    """

    entry_id: ULID
    title: str
    url: str
    full_content: str  # Content to translate (Markdown or HTML)
    is_html: bool = False  # True if full_content is HTML (feedContent)


@dataclass
class TranslatedEntry:
    """
    Result of translation.
    """

    entry_id: ULID
    translated_content: str
