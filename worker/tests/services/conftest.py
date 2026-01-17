"""
Pytest fixtures for service tests.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_crawl_result_success() -> MagicMock:
    """
    Mock successful CrawlResult from Crawl4AI.
    """
    result = MagicMock()
    result.success = True
    result.markdown = MagicMock()
    result.markdown.raw_markdown = (
        "# Test Entry\n\nThis is the entry content.\n\nAnother paragraph."
    )
    result.markdown.fit_markdown = "Test Entry. This is the entry content. Another paragraph."
    result.html = (
        "<html><body><h1>Test Entry</h1><p>This is the entry content.</p></body></html>"
    )
    result.error_message = None
    return result


@pytest.fixture
def mock_crawl_result_empty() -> MagicMock:
    """
    Mock CrawlResult with empty content.
    """
    result = MagicMock()
    result.success = True
    result.markdown = MagicMock()
    result.markdown.raw_markdown = ""
    result.markdown.fit_markdown = ""
    result.html = ""
    result.error_message = None
    return result


@pytest.fixture
def mock_crawl_result_failure() -> MagicMock:
    """
    Mock failed CrawlResult from Crawl4AI.
    """
    result = MagicMock()
    result.success = False
    result.markdown = None
    result.html = None
    result.error_message = "Connection timeout"
    return result


@pytest.fixture
def mock_crawler(mock_crawl_result_success: MagicMock) -> MagicMock:
    """
    Mock AsyncWebCrawler that returns successful result.
    """
    crawler = MagicMock()
    # arun returns an iterable container with results
    crawler.arun = AsyncMock(return_value=[mock_crawl_result_success])
    return crawler


@pytest.fixture
def mock_crawler_empty(mock_crawl_result_empty: MagicMock) -> MagicMock:
    """
    Mock AsyncWebCrawler that returns empty content.
    """
    crawler = MagicMock()
    crawler.arun = AsyncMock(return_value=[mock_crawl_result_empty])
    return crawler


@pytest.fixture
def mock_crawler_failure(mock_crawl_result_failure: MagicMock) -> MagicMock:
    """
    Mock AsyncWebCrawler that returns failed result.
    """
    crawler = MagicMock()
    crawler.arun = AsyncMock(return_value=[mock_crawl_result_failure])
    return crawler


@pytest.fixture
def mock_crawler_timeout() -> MagicMock:
    """
    Mock AsyncWebCrawler that times out.
    """
    crawler = MagicMock()
    crawler.arun = AsyncMock(side_effect=TimeoutError("Request timed out"))
    return crawler


@pytest.fixture
def patch_async_web_crawler() -> Any:
    """
    Patch AsyncWebCrawler context manager with mock crawler.

    Returns a function that creates the patch with custom crawler.
    Usage:
        with patch_async_web_crawler(mock_crawler):
            result = await fetcher.fetch(url)
    """

    def create_patch(crawler_mock: MagicMock) -> Any:
        async_cm = MagicMock()
        async_cm.__aenter__ = AsyncMock(return_value=crawler_mock)
        async_cm.__aexit__ = AsyncMock(return_value=None)

        return patch(
            "buun_curator.services.content.AsyncWebCrawler",
            return_value=async_cm,
        )

    return create_patch
