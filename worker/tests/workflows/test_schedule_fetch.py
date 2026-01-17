"""Tests for ScheduleFetchWorkflow helper functions."""

import pytest

from buun_curator.workflows.schedule_fetch import (
    _extract_domain,
    _group_entries_by_domain,
    _is_youtube_url,
)

# Tests for _extract_domain


def test_extract_domain_https() -> None:
    """Extract domain from HTTPS URL."""
    assert _extract_domain("https://example.com/path/to/page") == "example.com"


def test_extract_domain_http() -> None:
    """Extract domain from HTTP URL."""
    assert _extract_domain("http://example.com/page") == "example.com"


def test_extract_domain_with_subdomain() -> None:
    """Extract domain with subdomain."""
    assert _extract_domain("https://www.example.com/page") == "www.example.com"


def test_extract_domain_with_port() -> None:
    """Extract domain with port number."""
    assert _extract_domain("https://example.com:8080/page") == "example.com:8080"


def test_extract_domain_with_auth() -> None:
    """Extract domain from URL with authentication."""
    assert _extract_domain("https://user:pass@example.com/page") == "user:pass@example.com"


def test_extract_domain_complex_path() -> None:
    """Extract domain from URL with complex path and query."""
    url = "https://blog.example.com/2024/01/entry?id=123&ref=home#section"
    assert _extract_domain(url) == "blog.example.com"


def test_extract_domain_empty_string() -> None:
    """Return 'unknown' for empty string."""
    assert _extract_domain("") == "unknown"


def test_extract_domain_invalid_url() -> None:
    """Return 'unknown' for invalid URL without netloc."""
    assert _extract_domain("not-a-valid-url") == "unknown"


def test_extract_domain_path_only() -> None:
    """Return 'unknown' for path-only string."""
    assert _extract_domain("/path/to/page") == "unknown"


# Tests for _group_entries_by_domain


@pytest.mark.asyncio
async def test_group_entries_single_domain() -> None:
    """Group entries from single domain."""
    entries = [
        {"entry_id": "1", "url": "https://example.com/page1"},
        {"entry_id": "2", "url": "https://example.com/page2"},
    ]
    result = await _group_entries_by_domain(entries)

    assert isinstance(result, dict)
    assert len(result) == 1
    assert "example.com" in result
    assert len(result["example.com"]) == 2


@pytest.mark.asyncio
async def test_group_entries_multiple_domains() -> None:
    """Group entries from multiple domains."""
    entries = [
        {"entry_id": "1", "url": "https://example.com/page1"},
        {"entry_id": "2", "url": "https://other.com/page1"},
        {"entry_id": "3", "url": "https://example.com/page2"},
        {"entry_id": "4", "url": "https://third.com/page1"},
    ]
    result = await _group_entries_by_domain(entries)

    assert isinstance(result, dict)
    assert len(result) == 3
    assert len(result["example.com"]) == 2
    assert len(result["other.com"]) == 1
    assert len(result["third.com"]) == 1


@pytest.mark.asyncio
async def test_group_entries_preserves_entry_data() -> None:
    """Ensure entry data is preserved after grouping."""
    entries = [
        {"entry_id": "1", "url": "https://example.com/page", "title": "Test Title"},
    ]
    result = await _group_entries_by_domain(entries)

    assert isinstance(result, dict)
    assert result["example.com"][0]["entry_id"] == "1"
    assert result["example.com"][0]["title"] == "Test Title"


@pytest.mark.asyncio
async def test_group_entries_empty_list() -> None:
    """Return empty dict for empty list."""
    result = await _group_entries_by_domain([])
    assert result == {}


@pytest.mark.asyncio
async def test_group_entries_missing_url() -> None:
    """Group entries with missing url field to 'unknown'."""
    entries = [
        {"entry_id": "1"},
        {"entry_id": "2", "url": ""},
    ]
    result = await _group_entries_by_domain(entries)

    assert isinstance(result, dict)
    assert len(result) == 1
    assert "unknown" in result
    assert len(result["unknown"]) == 2


@pytest.mark.asyncio
async def test_group_entries_preserves_order() -> None:
    """Ensure entries are grouped in order."""
    entries = [
        {"entry_id": "1", "url": "https://example.com/page1"},
        {"entry_id": "2", "url": "https://example.com/page2"},
        {"entry_id": "3", "url": "https://example.com/page3"},
    ]
    result = await _group_entries_by_domain(entries)

    assert isinstance(result, dict)
    entry_ids = [e["entry_id"] for e in result["example.com"]]
    assert entry_ids == ["1", "2", "3"]


# Tests for _is_youtube_url


def test_is_youtube_url_youtube_com() -> None:
    """Detect youtube.com URLs."""
    assert _is_youtube_url("https://youtube.com/watch?v=abc123") is True


def test_is_youtube_url_www_youtube_com() -> None:
    """Detect www.youtube.com URLs."""
    assert _is_youtube_url("https://www.youtube.com/watch?v=abc123") is True


def test_is_youtube_url_youtu_be() -> None:
    """Detect youtu.be short URLs."""
    assert _is_youtube_url("https://youtu.be/abc123") is True


def test_is_youtube_url_m_youtube_com() -> None:
    """Detect mobile YouTube URLs."""
    assert _is_youtube_url("https://m.youtube.com/watch?v=abc123") is True


def test_is_youtube_url_non_youtube() -> None:
    """Return False for non-YouTube URLs."""
    assert _is_youtube_url("https://example.com/page") is False


def test_is_youtube_url_in_path() -> None:
    """Return False for URLs with youtube in path (not domain)."""
    assert _is_youtube_url("https://example.com/youtube/video") is False


def test_is_youtube_url_similar_domain() -> None:
    """Return False for similar but different domains."""
    assert _is_youtube_url("https://notyoutube.com/watch") is False
    assert _is_youtube_url("https://youtube.example.com/watch") is False


def test_is_youtube_url_empty() -> None:
    """Return False for empty URL."""
    assert _is_youtube_url("") is False


def test_is_youtube_url_http() -> None:
    """Detect HTTP YouTube URLs (not just HTTPS)."""
    assert _is_youtube_url("http://www.youtube.com/watch?v=abc123") is True
