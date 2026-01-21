"""
Pytest fixtures for activity tests.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from buun_curator.models import FetchedContent


@pytest.fixture
def mock_fetcher() -> MagicMock:
    """
    Mock ContentFetcher for testing fetch activities.

    The fetch method is an AsyncMock that returns a successful FetchedContent
    by default. Override the return_value in individual tests as needed.
    """
    fetcher = MagicMock()
    fetcher.fetch = AsyncMock(
        return_value=FetchedContent(
            full_content="# Test Entry\n\nThis is test content.",
            raw_html="<h1>Test Entry</h1><p>This is test content.</p>",
        )
    )
    return fetcher


@pytest.fixture
def mock_fetcher_empty() -> MagicMock:
    """
    Mock ContentFetcher that returns empty content (fetch failure).
    """
    fetcher = MagicMock()
    fetcher.fetch = AsyncMock(
        return_value=FetchedContent(
            full_content="",
            raw_html="",
        )
    )
    return fetcher


@pytest.fixture
def sample_entry() -> dict:
    """
    Sample entry dict for testing.
    """
    return {
        "entry_id": "01HTEST12345678901234",
        "feed_id": "01HFEED12345678901234",
        "feed_name": "Test Feed",
        "title": "Test Entry Title",
        "url": "https://example.com/entry",
        "feed_content": "RSS feed content",
        "author": "Test Author",
        "published_at": "2024-01-01T00:00:00Z",
        "extraction_rules": None,
    }


@pytest.fixture
def sample_entry_with_rules() -> dict:
    """
    Sample entry dict with extraction rules.
    """
    return {
        "entry_id": "01HTEST12345678901234",
        "feed_id": "01HFEED12345678901234",
        "feed_name": "Test Feed",
        "title": "Test Entry Title",
        "url": "https://example.com/entry",
        "feed_content": "RSS feed content",
        "author": "Test Author",
        "published_at": "2024-01-01T00:00:00Z",
        "extraction_rules": [
            {"type": "css_selector", "value": ".sidebar"},
            {"type": "css_selector", "value": ".ads"},
        ],
    }


@pytest.fixture
def sample_youtube_entry() -> dict:
    """
    Sample YouTube entry dict for testing skip logic.
    """
    return {
        "entry_id": "01HYOUTUBE1234567890",
        "feed_id": "01HFEED12345678901234",
        "feed_name": "YouTube Channel",
        "title": "YouTube Video Title",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "feed_content": "",
        "author": "YouTuber",
        "published_at": "2024-01-01T00:00:00Z",
        "metadata": {"youtubeVideoId": "dQw4w9WgXcQ"},
        "extraction_rules": None,
    }
