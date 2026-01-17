"""
Prompt loader for Deep Research agents.

Loads prompts from markdown files in this directory.
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """
    Load a prompt from a markdown file.

    Parameters
    ----------
    name : str
        Prompt name (without .md extension).

    Returns
    -------
    str
        Prompt content.

    Raises
    ------
    FileNotFoundError
        If prompt file does not exist.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")
