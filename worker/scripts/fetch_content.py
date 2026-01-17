"""
CLI tool for testing ContentFetcher.

Usage:
    uv run fetch <url>
    uv run fetch <url> --title "Entry Title"
    uv run fetch <url> --screenshot  # Match workflow behavior
    uv run fetch <url> --html  # Show raw HTML
    uv run fetch <url> --exclude ".sidebar" --exclude ".ad-slot"
"""

import argparse
import asyncio
import sys

from buun_curator.services.content import ContentFetcher


async def fetch_url(
    url: str,
    title: str | None = None,
    show_html: bool = False,
    screenshot: bool = False,
    exclude_selectors: list[str] | None = None,
) -> None:
    """
    Fetch content from URL and print markdown.

    Parameters
    ----------
    url : str
        URL to fetch content from.
    title : str | None, optional
        Entry title for duplicate heading removal (default: None).
    show_html : bool, optional
        Show raw HTML instead of markdown (default: False).
    screenshot : bool, optional
        Capture screenshot like workflow does (default: False).
    exclude_selectors : list[str] | None, optional
        CSS selectors to exclude from content (default: None).
    """
    print(f"Fetching: {url}")
    if title:
        print(f"Title: {title}")
    if screenshot:
        print("Screenshot: enabled")
    if exclude_selectors:
        print(f"Exclude selectors: {exclude_selectors}")
    print("=" * 60)

    fetcher = ContentFetcher(timeout=60, capture_screenshot=screenshot)

    # Build extraction_rules from exclude_selectors
    extraction_rules: list[dict] | None = None
    if exclude_selectors:
        extraction_rules = [
            {"type": "css_selector", "value": selector} for selector in exclude_selectors
        ]

    result = await fetcher.fetch(url, title=title, extraction_rules=extraction_rules)

    if not result.full_content and not result.raw_html:
        print("ERROR: No content fetched")
        sys.exit(1)

    # Show content based on options
    if show_html:
        print("\n[raw_html]")
        print("=" * 60)
        print(result.raw_html[:5000] if len(result.raw_html) > 5000 else result.raw_html)
        if len(result.raw_html) > 5000:
            print(f"\n... (truncated, total {len(result.raw_html)} chars)")
    else:
        print("\n[full_content]")
        print("=" * 60)
        print(result.full_content)

    # Show stats
    print("\n" + "=" * 60)
    print("[Stats]")
    print(f"  full_content: {len(result.full_content)} chars")
    print(f"  raw_html: {len(result.raw_html)} chars")
    if result.screenshot:
        print(f"  screenshot: {len(result.screenshot)} bytes")


def cli() -> None:
    """
    CLI entry point.
    """
    parser = argparse.ArgumentParser(
        description="Fetch entry content using ContentFetcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run fetch https://example.com/blog
  uv run fetch https://example.com/blog --title "Title"
  uv run fetch https://example.com/blog --screenshot
  uv run fetch https://example.com/blog --exclude ".sidebar" --exclude ".ad-slot"
  uv run fetch https://example.com/blog --html
        """,
    )
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--title", "-t", help="Entry title (for duplicate heading removal)")
    parser.add_argument(
        "--screenshot",
        "-s",
        action="store_true",
        help="Capture screenshot (matches workflow behavior)",
    )
    parser.add_argument(
        "--exclude",
        "-e",
        action="append",
        dest="exclude_selectors",
        metavar="SELECTOR",
        help="CSS selector to exclude (can be specified multiple times)",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Show raw_html (first 5000 chars)",
    )

    args = parser.parse_args()

    asyncio.run(
        fetch_url(
            url=args.url,
            title=args.title,
            show_html=args.html,
            screenshot=args.screenshot,
            exclude_selectors=args.exclude_selectors,
        )
    )


if __name__ == "__main__":
    cli()
