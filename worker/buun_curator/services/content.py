"""
Content Fetcher Service for Buun Curator.

Fetches full entry content from URLs using Crawl4AI.
Migrated from agents/content_fetcher.py.
"""

import asyncio
import re
from base64 import b64decode
from typing import Any

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from buun_curator.logging import get_logger
from buun_curator.models import FetchedContent


class ImagePreservingFilter(PruningContentFilter):
    """
    PruningContentFilter that preserves figure and img elements.

    Overrides _prune_tree to ensure image-containing nodes are not pruned,
    while still applying normal pruning logic to other content.
    """

    # Tags that should always be preserved
    IMAGE_TAGS = {"figure", "img", "picture", "source", "video", "audio"}

    def __init__(self, **kwargs):
        """
        Initialize ImagePreservingFilter.

        Parameters
        ----------
        **kwargs
            Arguments passed to PruningContentFilter.
        """
        super().__init__(**kwargs)
        # Add image tags to tag_weights with high importance
        self.tag_weights.update(
            {
                "figure": 1.5,
                "figcaption": 1.2,
                "picture": 1.3,
                "img": 1.0,
            }
        )
        self.tag_importance.update(
            {
                "figure": 1.5,
                "figcaption": 1.2,
                "picture": 1.3,
            }
        )

    def _prune_tree(self, node) -> None:
        """
        Prune the tree starting from the given node, preserving images.

        Nodes containing image elements are preserved regardless of score.
        Other nodes follow the standard pruning algorithm.

        Parameters
        ----------
        node : Tag
            The node from which the pruning starts.
        """
        if not node or not hasattr(node, "name") or node.name is None:
            return

        # Always preserve image tags themselves
        if node.name in self.IMAGE_TAGS:
            return

        # Check if this node contains any image elements
        has_images = any(node.find_all(self.IMAGE_TAGS, recursive=True))

        if has_images:
            # Node contains images - preserve it but still prune children
            children = [child for child in node.children if hasattr(child, "name")]
            for child in children:
                self._prune_tree(child)
            return

        # No images - apply standard pruning logic
        text_len = len(node.get_text(strip=True))
        tag_len = len(node.encode_contents().decode("utf-8"))
        link_text_len = sum(
            len(s.strip()) for s in (a.string for a in node.find_all("a", recursive=False)) if s
        )

        metrics = {
            "node": node,
            "tag_name": node.name,
            "text_len": text_len,
            "tag_len": tag_len,
            "link_text_len": link_text_len,
        }

        score = self._compute_composite_score(metrics, text_len, tag_len, link_text_len)

        if self.threshold_type == "fixed":
            should_remove = score < self.threshold
        else:  # dynamic
            tag_importance = self.tag_importance.get(node.name, 0.7)
            text_ratio = text_len / tag_len if tag_len > 0 else 0
            link_ratio = link_text_len / text_len if text_len > 0 else 1

            threshold = self.threshold  # base threshold
            if tag_importance > 1:
                threshold *= 0.8
            if text_ratio > 0.4:
                threshold *= 0.9
            if link_ratio > 0.6:
                threshold *= 1.2

            should_remove = score < threshold

        if should_remove:
            node.decompose()
        else:
            children = [child for child in node.children if hasattr(child, "name")]
            for child in children:
                self._prune_tree(child)


logger = get_logger(__name__)


def html_to_markdown(html: str) -> str:
    """
    Convert HTML string to Markdown using Crawl4AI's markdown generator.

    Parameters
    ----------
    html : str
        HTML content to convert.

    Returns
    -------
    str
        Converted Markdown content.
    """
    if not html or not html.strip():
        return ""

    try:
        generator = DefaultMarkdownGenerator()
        result = generator.generate_markdown(
            input_html=html,
            citations=False,
        )
        return result.raw_markdown or ""
    except Exception as e:
        logger.warning(
            f"Failed to convert HTML to Markdown: {e}",
            error_type=type(e).__name__,
        )
        return ""


# Minimum content length for fallback to raw markdown (characters)
MIN_CONTENT_LENGTH = 500

# PruningContentFilter settings
# Note: min_word_threshold removes blocks with fewer words than the threshold,
# which can unintentionally filter out code blocks and short content sections.
# Set to None to avoid this issue.
FILTER_THRESHOLD = 0.3
FILTER_THRESHOLD_TYPE = "dynamic"
FILTER_MIN_WORDS: int | None = None


def _normalize_text(text: str) -> str:
    """
    Normalize text for comparison (lowercase, strip whitespace/punctuation).

    Parameters
    ----------
    text : str
        Text to normalize.

    Returns
    -------
    str
        Normalized text.
    """
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _post_process_content(content: str, title: str | None = None) -> str:
    """
    Post-process extracted content.

    - Remove duplicate title heading if it matches the entry title
    - Convert single newlines to double newlines for paragraph breaks
      (Crawl4AI outputs single newlines between paragraphs)
    - Preserve original line breaks inside code blocks

    Parameters
    ----------
    content : str
        Raw markdown content.
    title : str | None, optional
        Entry title to check for duplicates (default: None).

    Returns
    -------
    str
        Processed markdown content.
    """
    if not content:
        return content

    lines = content.split("\n")
    processed_lines: list[str] = []
    title_normalized = _normalize_text(title) if title else ""
    in_code_block = False

    for line in lines:
        # Track code block state (``` or ~~~)
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block

        # Check if this line is a heading that matches the title
        if not in_code_block:
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_match and title_normalized:
                heading_text = heading_match.group(2)
                if _normalize_text(heading_text) == title_normalized:
                    # Skip this duplicate title heading
                    continue

        processed_lines.append(line)

    # Join lines with proper spacing:
    # - Code blocks: preserve single newlines
    # - Regular content: use double newlines for paragraph breaks
    result_parts: list[str] = []
    current_block: list[str] = []
    in_code_block = False

    for line in processed_lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if in_code_block:
                # End of code block
                current_block.append(line)
                result_parts.append("\n".join(current_block))
                current_block = []
            else:
                # Start of code block - flush regular content first
                if current_block:
                    # Join non-empty lines with double newlines
                    non_empty = [ln for ln in current_block if ln.strip()]
                    if non_empty:
                        result_parts.append("\n\n".join(non_empty))
                    current_block = []
                current_block.append(line)
            in_code_block = not in_code_block
        else:
            current_block.append(line)

    # Handle remaining content
    if current_block:
        if in_code_block:
            # Unclosed code block - preserve as-is
            result_parts.append("\n".join(current_block))
        else:
            non_empty = [ln for ln in current_block if ln.strip()]
            if non_empty:
                result_parts.append("\n\n".join(non_empty))

    return "\n\n".join(result_parts).strip()


def _generate_markdown_from_html(
    html: str,
    title: str | None = None,
) -> str:
    """
    Generate markdown content from HTML.

    Uses ImagePreservingFilter with fallback to raw markdown if too short.

    Parameters
    ----------
    html : str
        HTML content to process.
    title : str | None, optional
        Entry title to remove duplicate headings (default: None).

    Returns
    -------
    str
        Processed markdown content.
    """
    # Create ImagePreservingFilter for cleaner content while keeping images
    content_filter = ImagePreservingFilter(
        threshold=FILTER_THRESHOLD,
        threshold_type=FILTER_THRESHOLD_TYPE,
        min_word_threshold=FILTER_MIN_WORDS,  # type: ignore[arg-type]
    )

    # Generator without filter for raw markdown
    raw_generator = DefaultMarkdownGenerator(
        options={"body_width": 0},
    )

    # Generator with filter for cleaner content
    filtered_generator = DefaultMarkdownGenerator(
        content_filter=content_filter,
        options={"body_width": 0},
    )

    # Generate raw markdown
    raw_result = raw_generator.generate_markdown(input_html=html, citations=False)
    raw_markdown = raw_result.raw_markdown or ""

    # Generate filtered markdown
    filtered_result = filtered_generator.generate_markdown(input_html=html, citations=False)
    filtered_markdown = filtered_result.fit_markdown or ""

    # Post-process both
    processed_raw = _post_process_content(raw_markdown, title)
    processed_filtered = _post_process_content(filtered_markdown, title)

    # Use filtered content with fallback to raw if too short
    # or if filtered is suspiciously short compared to raw
    use_filtered = (
        len(processed_filtered) >= MIN_CONTENT_LENGTH
        and len(processed_filtered) >= len(processed_raw) * 0.1
    )
    if use_filtered:
        return processed_filtered
    return processed_raw


class ContentFetcher:
    """
    Service for fetching full entry content.
    """

    # Default excluded CSS selectors (global rules)
    DEFAULT_EXCLUDED_SELECTORS = [
        "[data-component='ad-slot']",
        "[data-testid='ad']",
        "[class*='advertisement']",
        "[class*='ad-slot']",
        "[class*='advert']",
    ]

    def __init__(
        self,
        timeout: int = 30,
        concurrency: int = 3,
        capture_screenshot: bool = False,
    ):
        """
        Initialize ContentFetcher.

        Parameters
        ----------
        timeout : int, optional
            Request timeout in seconds (default: 30).
        concurrency : int, optional
            Maximum concurrent requests (default: 3).
        capture_screenshot : bool, optional
            Whether to capture page screenshots (default: False).
        """
        self.timeout = timeout
        self.concurrency = concurrency
        self.capture_screenshot = capture_screenshot

    def process_html(
        self,
        html: str,
        title: str | None = None,
    ) -> FetchedContent:
        """
        Process HTML content to generate markdown.

        Use this when fetchContent is disabled to process feed_content (RSS/Atom HTML).
        Uses the same filtering logic as URL-based fetching.

        Parameters
        ----------
        html : str
            HTML content to process (typically from RSS feed).
        title : str | None, optional
            Entry title to remove duplicate headings (default: None).

        Returns
        -------
        FetchedContent
            Content with full_content.
        """
        if not html or not html.strip():
            return FetchedContent(full_content="", raw_html="")

        logger.debug("Processing HTML content", chars=len(html))
        try:
            full_content = _generate_markdown_from_html(html, title)
            return FetchedContent(full_content=full_content, raw_html=html)

        except Exception as e:
            logger.warning(
                f"Failed to process HTML content: {e}",
                error_type=type(e).__name__,
            )
            # Fallback to simple conversion
            simple_markdown = html_to_markdown(html)
            processed = _post_process_content(simple_markdown, title)
            return FetchedContent(
                full_content=processed,
                raw_html=html,
            )

    async def fetch(
        self,
        url: str,
        title: str | None = None,
        extraction_rules: list[dict] | None = None,
    ) -> FetchedContent:
        """
        Fetch entry content from URL and return as Markdown.

        Parameters
        ----------
        url : str
            The entry URL to fetch.
        title : str | None, optional
            Entry title to remove duplicate headings (default: None).
        extraction_rules : list[dict] | None, optional
            Feed-specific extraction rules with 'type' and 'value' keys
            (default: None). Supported types: 'css_selector', 'xpath'.

        Returns
        -------
        FetchedContent
            Content with full_content and raw_html.
        """
        try:
            # Build excluded selectors: defaults + feed-specific rules
            excluded_selectors = list(self.DEFAULT_EXCLUDED_SELECTORS)
            if extraction_rules:
                for rule in extraction_rules:
                    rule_type = rule.get("type")
                    rule_value = rule.get("value")
                    if rule_type == "css_selector" and rule_value:
                        excluded_selectors.append(rule_value)
                    # Note: xpath rules would require different handling

            # ImagePreservingFilter for cleaner content while keeping images
            content_filter = ImagePreservingFilter(
                threshold=FILTER_THRESHOLD,
                threshold_type=FILTER_THRESHOLD_TYPE,
                min_word_threshold=FILTER_MIN_WORDS,  # type: ignore[arg-type]
            )

            markdown_generator = DefaultMarkdownGenerator(
                content_filter=content_filter,
                options={
                    "body_width": 0,  # No line wrapping, preserve paragraph structure
                },
            )

            # Configure crawler to extract entry content
            # Use excluded_tags and excluded_selector to filter out non-content elements
            # Note: We don't use css_selector because sites use different structures
            # (e.g., <article>, #maincol, .post-content, etc.)
            run_config = CrawlerRunConfig(
                word_count_threshold=10,
                # Note: exclude_external_links=True removes link text too,
                # breaking content where important text is in <a> tags
                exclude_external_links=False,
                remove_overlay_elements=True,
                process_iframes=False,
                # Exclude common non-content elements (navigation, headers, footers, etc.)
                excluded_tags=[
                    "nav",
                    "header",
                    "footer",
                    "aside",
                    "form",
                    "script",
                    "style",
                    "noscript",
                    "iframe",
                    "button",
                    "input",
                    "select",
                    "textarea",
                ],
                # Exclude ads, related entries, etc. by CSS selector
                # Combines default selectors with feed-specific extraction rules
                excluded_selector=",".join(excluded_selectors),
                markdown_generator=markdown_generator,
                # Screenshot capture for thumbnails
                screenshot=self.capture_screenshot,
                screenshot_wait_for=1.0,  # Wait 1 second for screenshot
            )

            async with AsyncWebCrawler() as crawler:
                result: Any = await asyncio.wait_for(
                    crawler.arun(url=url, config=run_config),
                    timeout=self.timeout,
                )

                # CrawlResultContainer is iterable, get first result
                crawl_result: Any = result[0] if result else None

                if crawl_result and crawl_result.success:
                    raw_markdown = crawl_result.markdown.raw_markdown or ""
                    filtered_markdown = crawl_result.markdown.fit_markdown or ""
                    raw_html = crawl_result.html or ""

                    # Extract HTML title from metadata
                    html_title = ""
                    if crawl_result.metadata and isinstance(crawl_result.metadata, dict):
                        html_title = crawl_result.metadata.get("title", "") or ""

                    # Decode screenshot if available
                    screenshot_bytes: bytes | None = None
                    if self.capture_screenshot and crawl_result.screenshot:
                        try:
                            screenshot_bytes = b64decode(crawl_result.screenshot)
                            logger.debug(
                                "Captured screenshot", url=url, bytes=len(screenshot_bytes)
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to decode screenshot: {e}",
                                url=url,
                                error_type=type(e).__name__,
                            )

                    # Post-process and select best content
                    processed_raw = _post_process_content(raw_markdown, title)
                    processed_filtered = _post_process_content(filtered_markdown, title)

                    # Log both versions for debugging
                    logger.debug(
                        f"Content extraction for {url}: "
                        f"raw={len(processed_raw)} chars, "
                        f"filtered={len(processed_filtered)} chars"
                    )

                    # Use filtered content with fallback to raw if too short
                    # or if filtered is suspiciously short compared to raw
                    # (indicates over-aggressive filtering)
                    use_filtered = (
                        len(processed_filtered) >= MIN_CONTENT_LENGTH
                        and len(processed_filtered) >= len(processed_raw) * 0.1
                    )
                    if use_filtered:
                        full_content = processed_filtered
                    else:
                        full_content = processed_raw
                        if processed_filtered and len(processed_raw) > len(processed_filtered):
                            logger.debug(
                                f"Using raw content (filtered too short): "
                                f"raw={len(processed_raw)}, filtered={len(processed_filtered)}"
                            )

                    if full_content:
                        logger.info(
                            "Fetched content",
                            url=url,
                            content_chars=len(full_content),
                            html_chars=len(raw_html),
                            screenshot_bytes=len(screenshot_bytes) if screenshot_bytes else 0,
                        )
                        return FetchedContent(
                            full_content=full_content,
                            raw_html=raw_html,
                            screenshot=screenshot_bytes,
                            title=html_title,
                        )
                    else:
                        logger.warning("No content extracted", url=url)
                        return FetchedContent(full_content="", raw_html=raw_html, title=html_title)
                else:
                    error_msg = crawl_result.error_message if crawl_result else "No result"
                    logger.warning(f"Failed to fetch content: {error_msg}", url=url)
                    return FetchedContent(full_content="", raw_html="")

        except TimeoutError:
            logger.warning("Timeout fetching content", url=url, error_type="TimeoutError")
            return FetchedContent(full_content="", raw_html="")
        except Exception as e:
            logger.error(
                f"Error fetching content: {e}",
                url=url,
                error_type=type(e).__name__,
            )
            return FetchedContent(full_content="", raw_html="")

    async def fetch_multiple(
        self,
        urls_with_titles: list[tuple[str, str | None]],
        extraction_rules: list[dict] | None = None,
    ) -> dict[str, FetchedContent]:
        """
        Fetch content from multiple URLs concurrently.

        Parameters
        ----------
        urls_with_titles : list[tuple[str, str | None]]
            List of (url, title) tuples.
        extraction_rules : list[dict] | None, optional
            Feed-specific extraction rules to apply to all URLs (default: None).

        Returns
        -------
        dict[str, FetchedContent]
            Dict mapping URL to FetchedContent.
        """
        semaphore = asyncio.Semaphore(self.concurrency)
        results: dict[str, FetchedContent] = {}

        async def fetch_with_semaphore(url: str, title: str | None) -> tuple[str, FetchedContent]:
            async with semaphore:
                content = await self.fetch(url, title, extraction_rules)
                return url, content

        tasks = [fetch_with_semaphore(url, title) for url, title in urls_with_titles]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for item in completed:
            if isinstance(item, BaseException):
                logger.error(f"Fetch task failed: {item}")
            else:
                url, content = item
                results[url] = content

        success_count = sum(1 for c in results.values() if c.full_content)
        logger.info(
            "Fetched entries",
            success_count=success_count,
            total=len(urls_with_titles),
        )

        return results
