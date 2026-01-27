"""
Pytest configuration and fixtures for Buun Curator tests.
"""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """
    Load fixture content from a text file.
    """
    return (FIXTURES_DIR / f"{name}.txt").read_text()


@pytest.fixture
def required_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Set required environment variables for Config.from_env().

    Use this fixture in tests that call code paths accessing get_config()
    without mocking it.
    """
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """
    Sort test items to run unit tests before integration tests.

    Tests marked with @pytest.mark.integration run last.
    """

    def sort_key(item: pytest.Item) -> tuple[int, str]:
        if item.get_closest_marker("integration"):
            return (1, item.nodeid)
        return (0, item.nodeid)

    items.sort(key=sort_key)
