"""
Pytest fixtures for integration tests.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

HTML_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "html"


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Add custom command line options for integration tests.
    """
    parser.addoption(
        "--show-markdown",
        action="store_true",
        default=False,
        help="Show markdown output from content fetcher",
    )


@pytest.fixture
def show_markdown(request: pytest.FixtureRequest) -> Callable[[str, str], None]:
    """
    Fixture that returns a function to print markdown if --show-markdown is enabled.

    Usage:
        result = await fetcher.fetch(url)
        show_markdown("Test Name", result.full_content)
    """
    enabled = request.config.getoption("--show-markdown")

    def _show(label: str, content: str) -> None:
        if enabled:
            print(f"\n{'=' * 60}")
            print(f"[{label}]")
            print("=" * 60)
            print(content)
            print("=" * 60)

    return _show


def _load_html(name: str) -> str:
    """
    Load HTML content from a fixture file.

    Parameters
    ----------
    name : str
        Name of the HTML file (without extension).

    Returns
    -------
    str
        HTML content.
    """
    return (HTML_FIXTURES_DIR / f"{name}.html").read_text()


@pytest.fixture
def html_article_clean() -> str:
    """
    Clean article HTML without ads or sidebars.
    """
    return _load_html("article_clean")


@pytest.fixture
def html_article_with_ads() -> str:
    """
    Article HTML with ads, sidebar, header, and footer.
    """
    return _load_html("article_with_ads")


@pytest.fixture
def html_article_with_custom_elements() -> str:
    """
    Article HTML with custom elements for testing extraction rules.
    """
    return _load_html("article_with_custom_elements")


@pytest.fixture
def html_fixtures_dir() -> Path:
    """
    Path to the HTML fixtures directory.
    """
    return HTML_FIXTURES_DIR
