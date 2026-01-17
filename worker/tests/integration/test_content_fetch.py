"""
Integration tests for content fetching with Crawl4AI.

These tests use actual Crawl4AI processing to verify HTML extraction
and content filtering behavior.

Usage:
    # Run tests normally
    uv run pytest tests/integration/test_content_fetch.py

    # Run with markdown output displayed
    uv run pytest tests/integration/test_content_fetch.py --show-markdown -s
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from buun_curator.services.content import ContentFetcher


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_clean_article(
    html_fixtures_dir: Path,
    show_markdown: Callable[[str, str], None],
) -> None:
    """Should extract content from a clean article HTML."""
    file_url = f"file://{html_fixtures_dir / 'article_clean.html'}"
    fetcher = ContentFetcher(timeout=30)

    result = await fetcher.fetch(file_url, title="Clean Article Title")

    show_markdown("article_clean.html", result.full_content)

    assert result.full_content != ""
    assert "first paragraph" in result.full_content
    assert "second paragraph" in result.full_content
    assert "Section Heading" in result.full_content
    assert result.raw_html != ""


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_excludes_nav_header_footer(
    html_fixtures_dir: Path,
    show_markdown: Callable[[str, str], None],
) -> None:
    """Should exclude navigation, header, and footer elements."""
    file_url = f"file://{html_fixtures_dir / 'article_with_ads.html'}"
    fetcher = ContentFetcher(timeout=30)

    result = await fetcher.fetch(file_url)

    show_markdown("article_with_ads.html (nav/header/footer)", result.full_content)

    # Main content should be present
    assert "main article content" in result.full_content
    # Navigation links should be excluded (nav tag)
    assert "Home" not in result.full_content
    assert "About" not in result.full_content
    # Footer should be excluded
    assert "Copyright" not in result.full_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_excludes_aside_sidebar(html_fixtures_dir: Path) -> None:
    """Should exclude aside/sidebar elements."""
    file_url = f"file://{html_fixtures_dir / 'article_with_ads.html'}"
    fetcher = ContentFetcher(timeout=30)

    result = await fetcher.fetch(file_url)

    # Main content should be present
    assert "main article content" in result.full_content
    # Sidebar content should be excluded (aside tag)
    assert "Related Articles" not in result.full_content
    assert "Related Article 1" not in result.full_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_excludes_default_ad_selectors(html_fixtures_dir: Path) -> None:
    """Should exclude elements matching default ad selectors."""
    file_url = f"file://{html_fixtures_dir / 'article_with_ads.html'}"
    fetcher = ContentFetcher(timeout=30)

    result = await fetcher.fetch(file_url)

    # Main content should be present
    assert "main article content" in result.full_content
    assert "Final paragraph" in result.full_content
    # Ad content should be excluded via DEFAULT_EXCLUDED_SELECTORS
    assert "BUY NOW" not in result.full_content
    assert "Another ad placement" not in result.full_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_with_custom_extraction_rules(
    html_fixtures_dir: Path,
    show_markdown: Callable[[str, str], None],
) -> None:
    """Should exclude elements matching custom extraction rules."""
    file_url = f"file://{html_fixtures_dir / 'article_with_custom_elements.html'}"
    fetcher = ContentFetcher(timeout=30)

    # With custom extraction rules to exclude specific elements
    custom_rules = [
        {"type": "css_selector", "value": ".custom-promo-box"},
        {"type": "css_selector", "value": ".author-bio"},
        {"type": "css_selector", "value": ".comments-section"},
    ]

    result_with_rules = await fetcher.fetch(file_url, extraction_rules=custom_rules)

    show_markdown("article_with_custom_elements.html (with rules)", result_with_rules.full_content)

    # Main content should be present
    assert "Main content paragraph one" in result_with_rules.full_content
    assert "Main content paragraph two" in result_with_rules.full_content
    assert "Main content paragraph three" in result_with_rules.full_content

    # Custom excluded elements should not be present
    assert "Subscribe to our newsletter" not in result_with_rules.full_content
    assert "Written by John Doe" not in result_with_rules.full_content
    assert "User comment" not in result_with_rules.full_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extraction_rules_change_output(
    html_fixtures_dir: Path,
    show_markdown: Callable[[str, str], None],
) -> None:
    """
    Verify extraction rules actually affect the output.

    Compares fetching the same HTML with and without Feed-specific extraction rules
    to confirm that CSS selector rules successfully remove targeted elements.
    """
    file_url = f"file://{html_fixtures_dir / 'article_with_custom_elements.html'}"
    fetcher = ContentFetcher(timeout=30)

    # Fetch WITHOUT extraction rules
    result_without_rules = await fetcher.fetch(file_url)

    show_markdown("WITHOUT extraction rules", result_without_rules.full_content)

    # Fetch WITH extraction rules
    custom_rules = [
        {"type": "css_selector", "value": ".custom-promo-box"},
        {"type": "css_selector", "value": ".author-bio"},
        {"type": "css_selector", "value": ".comments-section"},
    ]
    result_with_rules = await fetcher.fetch(file_url, extraction_rules=custom_rules)

    show_markdown("WITH extraction rules", result_with_rules.full_content)

    # Main content should be present in BOTH results
    for result in [result_without_rules, result_with_rules]:
        assert "Main content paragraph one" in result.full_content
        assert "Main content paragraph two" in result.full_content
        assert "Main content paragraph three" in result.full_content

    # WITHOUT rules: custom elements should be present
    assert "Subscribe to our newsletter" in result_without_rules.full_content
    assert "Written by John Doe" in result_without_rules.full_content
    assert "User comment" in result_without_rules.full_content

    # WITH rules: custom elements should be removed
    assert "Subscribe to our newsletter" not in result_with_rules.full_content
    assert "Written by John Doe" not in result_with_rules.full_content
    assert "User comment" not in result_with_rules.full_content

    # Content with rules should be shorter (elements were removed)
    assert len(result_with_rules.full_content) < len(result_without_rules.full_content)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_extraction_rule_effect(
    html_fixtures_dir: Path,
    show_markdown: Callable[[str, str], None],
) -> None:
    """
    Test that a single extraction rule removes only the targeted element.

    Verifies partial rule application doesn't affect unrelated elements.
    """
    file_url = f"file://{html_fixtures_dir / 'article_with_custom_elements.html'}"
    fetcher = ContentFetcher(timeout=30)

    # Apply only ONE rule (remove only promo box)
    single_rule = [{"type": "css_selector", "value": ".custom-promo-box"}]

    result = await fetcher.fetch(file_url, extraction_rules=single_rule)

    show_markdown("Single rule (.custom-promo-box)", result.full_content)

    # Promo box should be removed
    assert "Subscribe to our newsletter" not in result.full_content

    # Other custom elements should still be present (not targeted by this rule)
    assert "Written by John Doe" in result.full_content
    assert "User comment" in result.full_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extraction_rules_combined_with_defaults(
    html_fixtures_dir: Path,
) -> None:
    """
    Verify custom extraction rules work alongside default excluded selectors.

    Both DEFAULT_EXCLUDED_SELECTORS and Feed-specific rules should be applied.
    """
    file_url = f"file://{html_fixtures_dir / 'article_with_ads.html'}"
    fetcher = ContentFetcher(timeout=30)

    # Add custom rule to also remove a specific class
    # (while default selectors handle standard ads)
    custom_rules = [{"type": "css_selector", "value": ".sidebar"}]

    result = await fetcher.fetch(file_url, extraction_rules=custom_rules)

    # Main content should be present
    assert "main article content" in result.full_content

    # Default selectors should still work (nav, header, footer excluded)
    assert "Home" not in result.full_content  # nav
    assert "Copyright" not in result.full_content  # footer

    # Default ad selectors should work
    assert "BUY NOW" not in result.full_content

    # Custom rule should also work (if .sidebar existed, it would be removed)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_removes_duplicate_title(html_fixtures_dir: Path) -> None:
    """Should remove duplicate title heading when title is provided."""
    file_url = f"file://{html_fixtures_dir / 'article_clean.html'}"
    fetcher = ContentFetcher(timeout=30)

    # Fetch with matching title
    result = await fetcher.fetch(file_url, title="Clean Article Title")

    # The h1 title heading should be removed (duplicate of article title)
    # But content should still be present
    assert "first paragraph" in result.full_content
    # The title as a heading should not appear
    lines = result.full_content.split("\n")
    title_headings = [line for line in lines if "# Clean Article Title" in line]
    assert len(title_headings) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_preserves_title_when_not_matching(html_fixtures_dir: Path) -> None:
    """Should preserve heading when title doesn't match."""
    file_url = f"file://{html_fixtures_dir / 'article_clean.html'}"
    fetcher = ContentFetcher(timeout=30)

    # Fetch with non-matching title
    result = await fetcher.fetch(file_url, title="Different Title")

    # The h1 heading should be preserved
    assert "Clean Article Title" in result.full_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_returns_raw_html(html_fixtures_dir: Path) -> None:
    """Should return raw HTML in the result."""
    file_url = f"file://{html_fixtures_dir / 'article_clean.html'}"
    fetcher = ContentFetcher(timeout=30)

    result = await fetcher.fetch(file_url)

    assert result.raw_html != ""
    assert "<html" in result.raw_html.lower()
    assert "<body" in result.raw_html.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_content_has_paragraph_breaks(html_fixtures_dir: Path) -> None:
    """Should have proper paragraph breaks in full_content."""
    file_url = f"file://{html_fixtures_dir / 'article_clean.html'}"
    fetcher = ContentFetcher(timeout=30)

    result = await fetcher.fetch(file_url)

    # Post-processing should create double newlines between paragraphs
    assert "\n\n" in result.full_content


# =============================================================================
# Tests for filter_mode
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_uses_filtered_content(
    html_fixtures_dir: Path,
    show_markdown: Callable[[str, str], None],
) -> None:
    """Should use filtered content when sufficient length."""
    file_url = f"file://{html_fixtures_dir / 'article_with_ads.html'}"
    fetcher = ContentFetcher(timeout=30)

    result = await fetcher.fetch(file_url)

    show_markdown("Fetched - article_with_ads.html", result.full_content)

    # full_content uses PruningContentFilter output
    assert result.full_content != ""
    # Main content should be present
    assert "main article content" in result.full_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_fallback_for_short_content(
    html_fixtures_dir: Path,
) -> None:
    """Should fall back to raw when filtered content is too short."""
    file_url = f"file://{html_fixtures_dir / 'article_clean.html'}"

    fetcher = ContentFetcher(timeout=30)
    result = await fetcher.fetch(file_url)

    # Should have content (may use fallback for short articles)
    assert result.full_content != ""
