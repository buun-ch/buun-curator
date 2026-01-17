"""
Pytest configuration and fixtures for Buun Curator tests.
"""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """
    Load fixture content from a text file.
    """
    return (FIXTURES_DIR / f"{name}.txt").read_text()
