"""
Tests for fetch activities.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from buun_curator.activities.fetch import (
    _fetch_single_entry,
    _merge_extraction_rules,
)
from buun_curator.models import FetchedContent

# =============================================================================
# Tests for _merge_extraction_rules
# =============================================================================


def test_merge_extraction_rules_both_none_returns_empty() -> None:
    """When both inputs are None, returns empty list."""
    result = _merge_extraction_rules(None, None)
    assert result == []


def test_merge_extraction_rules_empty_lists_returns_empty() -> None:
    """When both inputs are empty lists, returns empty list."""
    result = _merge_extraction_rules([], [])
    assert result == []


def test_merge_extraction_rules_feed_rules_only() -> None:
    """When only feed_rules provided, returns feed_rules."""
    feed_rules = [{"type": "css_selector", "value": ".sidebar"}]
    result = _merge_extraction_rules(feed_rules, None)

    assert result == feed_rules


def test_merge_extraction_rules_additional_rules_only() -> None:
    """When only additional_rules provided, returns additional_rules."""
    additional_rules = [{"type": "css_selector", "value": ".ads"}]
    result = _merge_extraction_rules(None, additional_rules)

    assert result == additional_rules


def test_merge_extraction_rules_merges_both() -> None:
    """When both provided, merges them in order (feed first, then additional)."""
    feed_rules = [{"type": "css_selector", "value": ".sidebar"}]
    additional_rules = [{"type": "css_selector", "value": ".ads"}]

    result = _merge_extraction_rules(feed_rules, additional_rules)

    assert result == [
        {"type": "css_selector", "value": ".sidebar"},
        {"type": "css_selector", "value": ".ads"},
    ]


def test_merge_extraction_rules_preserves_order() -> None:
    """Merged rules preserve order: feed rules first, then additional."""
    feed_rules = [
        {"type": "css_selector", "value": ".a"},
        {"type": "css_selector", "value": ".b"},
    ]
    additional_rules = [
        {"type": "css_selector", "value": ".c"},
    ]

    result = _merge_extraction_rules(feed_rules, additional_rules)

    assert len(result) == 3
    assert result[0]["value"] == ".a"
    assert result[1]["value"] == ".b"
    assert result[2]["value"] == ".c"


# =============================================================================
# Tests for _fetch_single_entry
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_single_entry_success(mock_fetcher: MagicMock, sample_entry: dict) -> None:
    """Successful fetch returns entry_id, content dict, and success detail."""
    entry_id, content, detail = await _fetch_single_entry(mock_fetcher, sample_entry, None)

    mock_fetcher.fetch.assert_called_once_with(sample_entry["url"], sample_entry["title"], [])
    assert entry_id == sample_entry["entry_id"]
    assert content is not None
    assert content["full_content"] == "# Test Entry\n\nThis is test content."
    assert content["raw_html"] == "<h1>Test Entry</h1><p>This is test content.</p>"
    assert detail["status"] == "success"
    assert detail["full_content_bytes"] > 0


@pytest.mark.asyncio
async def test_fetch_single_entry_failure(
    mock_fetcher_empty: MagicMock, sample_entry: dict
) -> None:
    """Failed fetch (empty content) returns None content and failed detail."""
    entry_id, content, detail = await _fetch_single_entry(mock_fetcher_empty, sample_entry, None)

    mock_fetcher_empty.fetch.assert_called_once_with(sample_entry["url"], sample_entry["title"], [])
    assert entry_id == sample_entry["entry_id"]
    assert content is None
    assert detail["status"] == "failed"
    assert detail["full_content_bytes"] == 0


@pytest.mark.asyncio
async def test_fetch_single_entry_merges_rules(
    mock_fetcher: MagicMock, sample_entry_with_rules: dict
) -> None:
    """Entry extraction_rules are merged and passed to fetcher."""
    additional_rules = [{"type": "css_selector", "value": ".extra"}]

    await _fetch_single_entry(mock_fetcher, sample_entry_with_rules, additional_rules)

    # Verify fetch was called with merged rules
    mock_fetcher.fetch.assert_called_once()
    call_args = mock_fetcher.fetch.call_args
    merged_rules = call_args[0][2]  # Third positional arg is extraction_rules

    assert len(merged_rules) == 3  # 2 from entry + 1 additional
    assert {"type": "css_selector", "value": ".sidebar"} in merged_rules
    assert {"type": "css_selector", "value": ".ads"} in merged_rules
    assert {"type": "css_selector", "value": ".extra"} in merged_rules


@pytest.mark.asyncio
async def test_fetch_single_entry_passes_url_and_title(
    mock_fetcher: MagicMock, sample_entry: dict
) -> None:
    """URL and title from entry are passed to fetcher."""
    await _fetch_single_entry(mock_fetcher, sample_entry, None)

    mock_fetcher.fetch.assert_called_once_with(
        sample_entry["url"],
        sample_entry["title"],
        [],  # Empty extraction rules
    )


@pytest.mark.asyncio
async def test_fetch_single_entry_detail_includes_metadata(
    mock_fetcher: MagicMock, sample_entry: dict
) -> None:
    """Detail dict includes entry_id, url, and title."""
    _, _, detail = await _fetch_single_entry(mock_fetcher, sample_entry, None)

    mock_fetcher.fetch.assert_called_once()
    assert detail["entry_id"] == sample_entry["entry_id"]
    assert detail["url"] == sample_entry["url"]
    assert detail["title"] == sample_entry["title"]


# =============================================================================
# Tests for fetch_single_content activity
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_single_content_success() -> None:
    """Activity returns fetched content on success (no raw_html)."""
    mock_content = FetchedContent(
        full_content="# Entry",
        raw_html="<h1>Entry</h1>",  # ContentFetcher returns this, but activity doesn't
    )

    with patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class:
        mock_instance = MagicMock()
        mock_instance.fetch = AsyncMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test Entry",
            timeout=30,
        )

        result = await fetch_single_content(input_data)

        mock_fetcher_class.assert_called_once_with(timeout=30, capture_screenshot=False)
        mock_instance.fetch.assert_called_once_with(
            "https://example.com/entry", "Test Entry", []
        )
        assert result.full_content == "# Entry"
        # raw_html is not included in FetchSingleContentOutput


@pytest.mark.asyncio
async def test_fetch_single_content_merges_rules() -> None:
    """Activity merges feed and additional extraction rules."""
    mock_content = FetchedContent(
        full_content="Content",
        raw_html="<p>Content</p>",
    )

    with patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class:
        mock_instance = MagicMock()
        mock_instance.fetch = AsyncMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test",
            feed_extraction_rules=[{"type": "css_selector", "value": ".feed-rule"}],
            additional_extraction_rules=[{"type": "css_selector", "value": ".test-rule"}],
        )

        await fetch_single_content(input_data)

        # Verify merged rules were passed
        mock_instance.fetch.assert_called_once()
        call_args = mock_instance.fetch.call_args
        passed_rules = call_args[0][2]

        assert len(passed_rules) == 2
        assert {"type": "css_selector", "value": ".feed-rule"} in passed_rules
        assert {"type": "css_selector", "value": ".test-rule"} in passed_rules


@pytest.mark.asyncio
async def test_fetch_single_content_empty_returns_no_content_status() -> None:
    """Activity returns no_content status when fetch returns empty."""
    mock_content = FetchedContent(
        full_content="",
        raw_html="",
    )

    with patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class:
        mock_instance = MagicMock()
        mock_instance.fetch = AsyncMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/nonexistent",
            title="Missing",
        )

        result = await fetch_single_content(input_data)

        mock_instance.fetch.assert_called_once_with(
            "https://example.com/nonexistent", "Missing", []
        )
        assert result.status == "no_content"
        assert result.full_content == ""


@pytest.mark.asyncio
async def test_fetch_single_content_with_entry_id_saves_to_db() -> None:
    """When entry_id is provided, content is saved to DB and not returned."""
    mock_content = FetchedContent(
        full_content="# Entry Content",
        raw_html="<h1>Entry Content</h1>",
    )

    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch._save_entry_content") as mock_save,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.fetch = AsyncMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance
        mock_save.return_value = None
        mock_config.return_value.enable_thumbnail = False

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test Entry",
            entry_id="test-entry-123",
        )

        result = await fetch_single_content(input_data)

        # Verify save was called with entry_id
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args.kwargs["entry_id"] == "test-entry-123"
        assert call_args.kwargs["content"] == mock_content

        # Content should NOT be returned when entry_id is provided
        assert result.status == "success"
        assert result.content_length == len("# Entry Content")
        assert result.full_content == ""  # Not returned


@pytest.mark.asyncio
async def test_fetch_single_content_without_entry_id_returns_content() -> None:
    """When entry_id is not provided (preview mode), content is returned."""
    mock_content = FetchedContent(
        full_content="# Entry Content",
        raw_html="<h1>Entry Content</h1>",
    )

    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch._save_entry_content") as mock_save,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.fetch = AsyncMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance
        mock_config.return_value.enable_thumbnail = False

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test Entry",
            # No entry_id - preview mode
        )

        result = await fetch_single_content(input_data)

        # Save should NOT be called
        mock_save.assert_not_called()

        # Content should be returned
        assert result.status == "success"
        assert result.full_content == "# Entry Content"
        assert result.content_length == len("# Entry Content")


@pytest.mark.asyncio
async def test_fetch_single_content_with_thumbnail_enabled() -> None:
    """When enable_thumbnail=True, ContentFetcher is called with capture_screenshot=True."""
    mock_content = FetchedContent(
        full_content="# Entry",
        raw_html="<h1>Entry</h1>",
    )

    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.fetch = AsyncMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance
        mock_config.return_value.enable_thumbnail = True

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test",
            enable_thumbnail=True,
        )

        await fetch_single_content(input_data)

        # ContentFetcher should be called with capture_screenshot=True
        mock_fetcher_class.assert_called_once_with(timeout=60, capture_screenshot=True)


@pytest.mark.asyncio
async def test_fetch_single_content_thumbnail_disabled_by_config() -> None:
    """When config.enable_thumbnail=False, screenshot is not captured even if requested."""
    mock_content = FetchedContent(
        full_content="# Entry",
        raw_html="<h1>Entry</h1>",
    )

    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.fetch = AsyncMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance
        mock_config.return_value.enable_thumbnail = False  # Config disables it

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test",
            enable_thumbnail=True,  # Requested but config overrides
        )

        await fetch_single_content(input_data)

        # capture_screenshot should be False because config disables it
        mock_fetcher_class.assert_called_once_with(timeout=60, capture_screenshot=False)


@pytest.mark.asyncio
async def test_fetch_single_content_fetch_exception_returns_failed() -> None:
    """When fetch raises exception, returns failed status with error."""
    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.fetch = AsyncMock(side_effect=Exception("Network error"))
        mock_fetcher_class.return_value = mock_instance
        mock_config.return_value.enable_thumbnail = False

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test",
        )

        result = await fetch_single_content(input_data)

        assert result.status == "failed"
        assert result.error == "Network error"
        assert result.full_content == ""


@pytest.mark.asyncio
async def test_fetch_single_content_save_exception_returns_failed() -> None:
    """When DB save fails, returns failed status with error."""
    mock_content = FetchedContent(
        full_content="# Entry",
        raw_html="<h1>Entry</h1>",
    )

    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch._save_entry_content") as mock_save,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.fetch = AsyncMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance
        mock_save.side_effect = Exception("DB connection failed")
        mock_config.return_value.enable_thumbnail = False

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test",
            entry_id="test-entry-123",
        )

        result = await fetch_single_content(input_data)

        assert result.status == "failed"
        assert result.error == "DB connection failed"
        assert result.content_length == len("# Entry")  # Content was fetched


# =============================================================================
# Tests for fetch_single_content activity - HTML processing mode
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_single_content_html_mode_success() -> None:
    """Activity processes HTML content directly when html_content is provided."""
    mock_content = FetchedContent(
        full_content="# Processed Entry",
        raw_html="<h1>Entry</h1><p>Content</p>",
    )

    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.process_html = MagicMock(return_value=mock_content)
        mock_instance.fetch = AsyncMock()  # Should not be called
        mock_fetcher_class.return_value = mock_instance
        mock_config.return_value.enable_thumbnail = False

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",  # URL is for logging only in HTML mode
            title="Test Entry",
            html_content="<h1>Entry</h1><p>Content</p>",
        )

        result = await fetch_single_content(input_data)

        # Should call process_html, not fetch
        mock_instance.process_html.assert_called_once_with(
            "<h1>Entry</h1><p>Content</p>", "Test Entry"
        )
        mock_instance.fetch.assert_not_called()

        assert result.status == "success"
        assert result.full_content == "# Processed Entry"
        assert result.content_length == len("# Processed Entry")


@pytest.mark.asyncio
async def test_fetch_single_content_html_mode_with_entry_id_saves_to_db() -> None:
    """HTML mode with entry_id saves content to DB."""
    mock_content = FetchedContent(
        full_content="# Entry",
        raw_html="<h1>Entry</h1>",
    )

    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch._save_entry_content") as mock_save,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.process_html = MagicMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance
        mock_save.return_value = None
        mock_config.return_value.enable_thumbnail = False

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test Entry",
            entry_id="test-entry-456",
            html_content="<h1>Entry</h1>",
        )

        result = await fetch_single_content(input_data)

        # Verify save was called
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args.kwargs["entry_id"] == "test-entry-456"
        assert call_args.kwargs["content"] == mock_content

        # Content not returned when entry_id is provided
        assert result.status == "success"
        assert result.content_length == len("# Entry")
        assert result.full_content == ""


@pytest.mark.asyncio
async def test_fetch_single_content_html_mode_empty_returns_no_content() -> None:
    """HTML mode returns no_content when processing yields empty result."""
    mock_content = FetchedContent(
        full_content="",
        raw_html="",
    )

    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.process_html = MagicMock(return_value=mock_content)
        mock_fetcher_class.return_value = mock_instance
        mock_config.return_value.enable_thumbnail = False

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test",
            html_content="<html></html>",  # Empty HTML
        )

        result = await fetch_single_content(input_data)

        assert result.status == "no_content"


@pytest.mark.asyncio
async def test_fetch_single_content_html_mode_exception_returns_failed() -> None:
    """HTML mode returns failed status when processing raises exception."""
    with (
        patch("buun_curator.activities.fetch.ContentFetcher") as mock_fetcher_class,
        patch("buun_curator.activities.fetch.get_config") as mock_config,
    ):
        mock_instance = MagicMock()
        mock_instance.process_html = MagicMock(side_effect=Exception("Parse error"))
        mock_fetcher_class.return_value = mock_instance
        mock_config.return_value.enable_thumbnail = False

        from buun_curator.activities.fetch import fetch_single_content
        from buun_curator.models import FetchSingleContentInput

        input_data = FetchSingleContentInput(
            url="https://example.com/entry",
            title="Test",
            html_content="<invalid>",
        )

        result = await fetch_single_content(input_data)

        assert result.status == "failed"
        assert result.error == "Parse error"
