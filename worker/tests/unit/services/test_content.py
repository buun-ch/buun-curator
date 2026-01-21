"""
Tests for content fetcher service.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from buun_curator.services.content import (
    ContentFetcher,
    ImagePreservingFilter,
    _normalize_text,
    _post_process_content,
)

# =============================================================================
# Tests for _normalize_text
# =============================================================================


def test_normalize_text_lowercase() -> None:
    """Should convert text to lowercase."""
    result = _normalize_text("Hello World")
    assert result == "hello world"


def test_normalize_text_removes_punctuation() -> None:
    """Should remove punctuation marks."""
    result = _normalize_text("Hello, World!")
    assert result == "hello world"


def test_normalize_text_strips_whitespace() -> None:
    """Should strip leading and trailing whitespace."""
    result = _normalize_text("  Hello World  ")
    assert result == "hello world"


def test_normalize_text_preserves_internal_spaces() -> None:
    """Should preserve internal spaces."""
    result = _normalize_text("Hello   World")
    assert result == "hello   world"


def test_normalize_text_empty_string() -> None:
    """Should handle empty string."""
    result = _normalize_text("")
    assert result == ""


def test_normalize_text_only_punctuation() -> None:
    """Should handle string with only punctuation."""
    result = _normalize_text("!!??...")
    assert result == ""


# =============================================================================
# Tests for _post_process_content
# =============================================================================


def test_post_process_content_empty_string() -> None:
    """Should return empty string unchanged."""
    result = _post_process_content("")
    assert result == ""


def test_post_process_content_none_title() -> None:
    """Should process content without title matching."""
    content = "# Some Heading\n\nParagraph text."
    result = _post_process_content(content, None)
    assert "# Some Heading" in result
    assert "Paragraph text" in result


def test_post_process_content_removes_duplicate_title() -> None:
    """Should remove heading that matches the entry title."""
    content = "# Entry Title\n\nParagraph text."
    result = _post_process_content(content, "Entry Title")
    assert "# Entry Title" not in result
    assert "Paragraph text" in result


def test_post_process_content_removes_duplicate_title_case_insensitive() -> None:
    """Should match titles case-insensitively."""
    content = "# ENTRY TITLE\n\nParagraph text."
    result = _post_process_content(content, "Entry Title")
    assert "# ENTRY TITLE" not in result
    assert "Paragraph text" in result


def test_post_process_content_removes_duplicate_title_ignores_punctuation() -> None:
    """Should match titles ignoring punctuation differences."""
    content = "# Entry Title!\n\nParagraph text."
    result = _post_process_content(content, "Entry Title")
    assert "# Entry Title!" not in result
    assert "Paragraph text" in result


def test_post_process_content_preserves_non_matching_heading() -> None:
    """Should preserve headings that don't match the title."""
    content = "# Different Heading\n\nParagraph text."
    result = _post_process_content(content, "Entry Title")
    assert "# Different Heading" in result
    assert "Paragraph text" in result


def test_post_process_content_handles_multiple_headings() -> None:
    """Should only remove the matching title heading."""
    content = "# Entry Title\n\n## Section 1\n\nContent.\n\n## Section 2\n\nMore content."
    result = _post_process_content(content, "Entry Title")
    assert "# Entry Title" not in result
    assert "## Section 1" in result
    assert "## Section 2" in result


def test_post_process_content_converts_single_newlines() -> None:
    """Should convert single newlines to double for paragraph breaks."""
    content = "Line 1\nLine 2\nLine 3"
    result = _post_process_content(content)
    assert result == "Line 1\n\nLine 2\n\nLine 3"


def test_post_process_content_preserves_code_block_newlines() -> None:
    """Should preserve single newlines inside code blocks."""
    content = "Before code\n```python\nline1\nline2\nline3\n```\nAfter code"
    result = _post_process_content(content)
    # Code block should have single newlines preserved
    assert "```python\nline1\nline2\nline3\n```" in result
    # Regular content should have double newlines
    assert "Before code\n\n```" in result
    assert "```\n\nAfter code" in result


def test_post_process_content_preserves_code_block_with_tilde() -> None:
    """Should preserve newlines in code blocks using tilde syntax."""
    content = "Before\n~~~\ncode line 1\ncode line 2\n~~~\nAfter"
    result = _post_process_content(content)
    assert "~~~\ncode line 1\ncode line 2\n~~~" in result


def test_post_process_content_handles_multiple_code_blocks() -> None:
    """Should handle multiple code blocks correctly."""
    content = "Text 1\n```\ncode1\n```\nText 2\n```\ncode2\n```\nText 3"
    result = _post_process_content(content)
    # Each code block should preserve internal newlines
    assert "```\ncode1\n```" in result
    assert "```\ncode2\n```" in result
    # Text sections should have double newlines
    assert "Text 1\n\n```" in result
    assert "```\n\nText 2\n\n```" in result
    assert "```\n\nText 3" in result


def test_post_process_content_handles_code_block_with_language() -> None:
    """Should handle code blocks with language specifier."""
    content = "Intro\n```sql\nSELECT * FROM users;\nWHERE id = 1;\n```\nOutro"
    result = _post_process_content(content)
    assert "```sql\nSELECT * FROM users;\nWHERE id = 1;\n```" in result


def test_post_process_content_handles_empty_code_block() -> None:
    """Should handle empty code blocks."""
    content = "Before\n```\n```\nAfter"
    result = _post_process_content(content)
    assert "```\n```" in result


def test_post_process_content_handles_unclosed_code_block() -> None:
    """Should handle unclosed code blocks gracefully."""
    content = "Before\n```python\ncode line\nmore code"
    result = _post_process_content(content)
    # Should preserve the content, treating as still in code block
    assert "```python\ncode line\nmore code" in result


def test_post_process_content_strips_result() -> None:
    """Should strip leading and trailing whitespace from result."""
    content = "\n\n  Content here  \n\n"
    result = _post_process_content(content)
    assert result == "Content here"


# =============================================================================
# Tests for ContentFetcher initialization
# =============================================================================


def test_content_fetcher_default_timeout() -> None:
    """Should use default timeout of 30 seconds."""
    fetcher = ContentFetcher()
    assert fetcher.timeout == 30


def test_content_fetcher_default_concurrency() -> None:
    """Should use default concurrency of 3."""
    fetcher = ContentFetcher()
    assert fetcher.concurrency == 3


def test_content_fetcher_custom_timeout() -> None:
    """Should accept custom timeout value."""
    fetcher = ContentFetcher(timeout=60)
    assert fetcher.timeout == 60


def test_content_fetcher_custom_concurrency() -> None:
    """Should accept custom concurrency value."""
    fetcher = ContentFetcher(concurrency=5)
    assert fetcher.concurrency == 5


# =============================================================================
# Tests for ContentFetcher.fetch
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_success(
    mock_crawler: MagicMock,
    patch_async_web_crawler: Any,
) -> None:
    """Should return FetchedContent on successful fetch."""
    fetcher = ContentFetcher(timeout=30)

    with patch_async_web_crawler(mock_crawler):
        result = await fetcher.fetch("https://example.com/entry", "Test Entry")

    mock_crawler.arun.assert_called_once()
    assert result.full_content != ""
    assert result.raw_html != ""


@pytest.mark.asyncio
async def test_fetch_returns_processed_content(
    mock_crawler: MagicMock,
    patch_async_web_crawler: Any,
) -> None:
    """Should return post-processed content."""
    fetcher = ContentFetcher()

    with patch_async_web_crawler(mock_crawler):
        result = await fetcher.fetch("https://example.com/entry")

    # Content should have double newlines (post-processed)
    assert "\n\n" in result.full_content


@pytest.mark.asyncio
async def test_fetch_empty_content(
    mock_crawler_empty: MagicMock,
    patch_async_web_crawler: Any,
) -> None:
    """Should return empty FetchedContent when no content extracted."""
    fetcher = ContentFetcher()

    with patch_async_web_crawler(mock_crawler_empty):
        result = await fetcher.fetch("https://example.com/empty")

    mock_crawler_empty.arun.assert_called_once()
    assert result.full_content == ""


@pytest.mark.asyncio
async def test_fetch_failure(
    mock_crawler_failure: MagicMock,
    patch_async_web_crawler: Any,
) -> None:
    """Should return empty FetchedContent on fetch failure."""
    fetcher = ContentFetcher()

    with patch_async_web_crawler(mock_crawler_failure):
        result = await fetcher.fetch("https://example.com/fail")

    mock_crawler_failure.arun.assert_called_once()
    assert result.full_content == ""
    assert result.raw_html == ""


@pytest.mark.asyncio
async def test_fetch_timeout(
    mock_crawler_timeout: MagicMock,
    patch_async_web_crawler: Any,
) -> None:
    """Should return empty FetchedContent on timeout."""
    fetcher = ContentFetcher(timeout=1)

    with patch_async_web_crawler(mock_crawler_timeout):
        result = await fetcher.fetch("https://example.com/slow")

    mock_crawler_timeout.arun.assert_called_once()
    assert result.full_content == ""
    assert result.raw_html == ""


@pytest.mark.asyncio
async def test_fetch_with_extraction_rules(
    mock_crawler: MagicMock,
    patch_async_web_crawler: Any,
) -> None:
    """Should pass extraction rules to crawler config."""
    fetcher = ContentFetcher()
    rules = [
        {"type": "css_selector", "value": ".sidebar"},
        {"type": "css_selector", "value": ".ads"},
    ]

    with patch_async_web_crawler(mock_crawler):
        await fetcher.fetch("https://example.com/entry", extraction_rules=rules)

    mock_crawler.arun.assert_called_once()
    # Verify that arun was called (rules are applied via config)
    call_kwargs = mock_crawler.arun.call_args
    assert call_kwargs is not None


@pytest.mark.asyncio
async def test_fetch_removes_duplicate_title(
    patch_async_web_crawler: Any,
) -> None:
    """Should remove duplicate title heading from content."""
    # Create mock with title in content
    crawl_result = MagicMock()
    crawl_result.success = True
    crawl_result.markdown = MagicMock()
    crawl_result.markdown.raw_markdown = "# My Entry Title\n\nEntry content here."
    crawl_result.markdown.fit_markdown = "My Entry Title. Entry content here."
    crawl_result.html = "<h1>My Entry Title</h1><p>Entry content here.</p>"

    crawler = MagicMock()
    crawler.arun = AsyncMock(return_value=[crawl_result])

    fetcher = ContentFetcher()

    with patch_async_web_crawler(crawler):
        result = await fetcher.fetch("https://example.com/entry", title="My Entry Title")

    # Title heading should be removed
    assert "# My Entry Title" not in result.full_content
    assert "Entry content here" in result.full_content


# =============================================================================
# Tests for ContentFetcher.fetch_multiple
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_multiple_success(
    mock_crawler: MagicMock,
    patch_async_web_crawler: Any,
) -> None:
    """Should fetch multiple URLs concurrently."""
    fetcher = ContentFetcher(concurrency=2)
    urls_with_titles: list[tuple[str, str | None]] = [
        ("https://example.com/entry1", "Entry 1"),
        ("https://example.com/entry2", "Entry 2"),
    ]

    with patch_async_web_crawler(mock_crawler):
        results = await fetcher.fetch_multiple(urls_with_titles)

    assert len(results) == 2
    assert "https://example.com/entry1" in results
    assert "https://example.com/entry2" in results
    assert results["https://example.com/entry1"].full_content != ""
    assert results["https://example.com/entry2"].full_content != ""


@pytest.mark.asyncio
async def test_fetch_multiple_with_extraction_rules(
    mock_crawler: MagicMock,
    patch_async_web_crawler: Any,
) -> None:
    """Should apply extraction rules to all URLs."""
    fetcher = ContentFetcher()
    urls_with_titles: list[tuple[str, str | None]] = [
        ("https://example.com/entry1", "Entry 1"),
    ]
    rules = [{"type": "css_selector", "value": ".ads"}]

    with patch_async_web_crawler(mock_crawler):
        results = await fetcher.fetch_multiple(urls_with_titles, extraction_rules=rules)

    assert len(results) == 1
    mock_crawler.arun.assert_called()


@pytest.mark.asyncio
async def test_fetch_multiple_partial_failure(
    patch_async_web_crawler: Any,
) -> None:
    """Should handle partial failures gracefully."""
    # First call succeeds, second fails
    success_result = MagicMock()
    success_result.success = True
    success_result.markdown = MagicMock()
    success_result.markdown.raw_markdown = "# Entry\n\nContent."
    success_result.markdown.fit_markdown = "Entry. Content."
    success_result.html = "<h1>Entry</h1><p>Content.</p>"

    failure_result = MagicMock()
    failure_result.success = False
    failure_result.error_message = "Not found"

    crawler = MagicMock()
    crawler.arun = AsyncMock(side_effect=[[success_result], [failure_result]])

    fetcher = ContentFetcher(concurrency=1)
    urls_with_titles: list[tuple[str, str | None]] = [
        ("https://example.com/success", "Success"),
        ("https://example.com/fail", "Fail"),
    ]

    with patch_async_web_crawler(crawler):
        results = await fetcher.fetch_multiple(urls_with_titles)

    assert len(results) == 2
    assert results["https://example.com/success"].full_content != ""
    assert results["https://example.com/fail"].full_content == ""


@pytest.mark.asyncio
async def test_fetch_multiple_empty_list() -> None:
    """Should handle empty URL list."""
    fetcher = ContentFetcher()
    results = await fetcher.fetch_multiple([])
    assert results == {}


# =============================================================================
# Tests for DEFAULT_EXCLUDED_SELECTORS
# =============================================================================


def test_default_excluded_selectors_exists() -> None:
    """Should have default excluded selectors defined."""
    assert hasattr(ContentFetcher, "DEFAULT_EXCLUDED_SELECTORS")
    assert len(ContentFetcher.DEFAULT_EXCLUDED_SELECTORS) > 0


def test_default_excluded_selectors_contains_ad_patterns() -> None:
    """Should contain common ad-related selectors."""
    selectors = ContentFetcher.DEFAULT_EXCLUDED_SELECTORS
    ad_selectors = [s for s in selectors if "ad" in s.lower()]
    assert len(ad_selectors) > 0


# =============================================================================
# Tests for ContentFetcher.process_html
# =============================================================================


def test_process_html_returns_fetched_content() -> None:
    """Should return FetchedContent with full_content."""
    fetcher = ContentFetcher()
    html = "<h1>Test Entry</h1><p>This is the main content of the entry.</p>"

    result = fetcher.process_html(html)

    assert result.full_content != ""
    assert result.raw_html == html


def test_process_html_empty_string_returns_empty() -> None:
    """Should return empty FetchedContent for empty HTML."""
    fetcher = ContentFetcher()

    result = fetcher.process_html("")

    assert result.full_content == ""
    assert result.raw_html == ""


def test_process_html_whitespace_only_returns_empty() -> None:
    """Should return empty FetchedContent for whitespace-only HTML."""
    fetcher = ContentFetcher()

    result = fetcher.process_html("   \n\t  ")

    assert result.full_content == ""
    assert result.raw_html == ""


def test_process_html_removes_duplicate_title() -> None:
    """Should remove duplicate title heading from content."""
    fetcher = ContentFetcher()
    html = "<h1>My Entry Title</h1><p>Entry content here.</p>"

    result = fetcher.process_html(html, title="My Entry Title")

    # Title heading should be removed
    assert "# My Entry Title" not in result.full_content
    assert "Entry content" in result.full_content


def test_process_html_extracts_text_content() -> None:
    """Should extract text content from HTML elements."""
    fetcher = ContentFetcher()
    html = """
    <article>
        <h2>Section Title</h2>
        <p>First paragraph with important information.</p>
        <p>Second paragraph with more details.</p>
    </article>
    """

    result = fetcher.process_html(html)

    assert "Section Title" in result.full_content
    assert "First paragraph" in result.full_content
    assert "Second paragraph" in result.full_content


# =============================================================================
# Tests for ImagePreservingFilter
# =============================================================================


def test_image_preserving_filter_has_image_tags() -> None:
    """Should have image-related tags defined."""
    assert "figure" in ImagePreservingFilter.IMAGE_TAGS
    assert "img" in ImagePreservingFilter.IMAGE_TAGS
    assert "picture" in ImagePreservingFilter.IMAGE_TAGS


def test_image_preserving_filter_tag_weights() -> None:
    """Should have high tag weights for image-related elements."""
    filter_instance = ImagePreservingFilter()
    assert filter_instance.tag_weights.get("figure", 0) >= 1.0
    assert filter_instance.tag_weights.get("figcaption", 0) >= 1.0


def test_image_preserving_filter_preserves_figure() -> None:
    """Should preserve figure elements in filtered content."""
    filter_instance = ImagePreservingFilter(threshold=0.3, threshold_type="dynamic")
    html = """
    <body>
        <article>
            <p>This is some paragraph text with enough words to pass threshold.</p>
            <figure>
                <img src="test.jpg" alt="Test image">
                <figcaption>Image caption text</figcaption>
            </figure>
            <p>Another paragraph with sufficient content for the filter.</p>
        </article>
    </body>
    """

    result = filter_instance.filter_content(html)

    # Join all content blocks
    content = " ".join(result)
    assert "figure" in content.lower() or "img" in content.lower()


def test_image_preserving_filter_preserves_standalone_img() -> None:
    """Should preserve standalone img elements."""
    filter_instance = ImagePreservingFilter(threshold=0.3, threshold_type="dynamic")
    html = """
    <body>
        <article>
            <p>Introduction paragraph with enough words to be included.</p>
            <img src="photo.jpg" alt="Photo description">
            <p>Conclusion paragraph with additional content for context.</p>
        </article>
    </body>
    """

    result = filter_instance.filter_content(html)

    content = " ".join(result)
    assert "img" in content.lower()


def test_image_preserving_filter_still_prunes_non_image_content() -> None:
    """Should still prune low-value content without images."""
    filter_instance = ImagePreservingFilter(threshold=0.5, threshold_type="fixed")
    html = """
    <body>
        <nav>Navigation menu should be removed</nav>
        <article>
            <p>Main content paragraph with sufficient length.</p>
            <figure>
                <img src="test.jpg" alt="Test">
            </figure>
        </article>
        <aside>Sidebar content that may be pruned</aside>
    </body>
    """

    result = filter_instance.filter_content(html)

    content = " ".join(result)
    # Nav should be removed (it's in excluded_tags)
    assert "Navigation menu" not in content
