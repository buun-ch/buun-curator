"""
Script for fixing markdown table alignment with proper Unicode display width handling.

Uses wcwidth to correctly calculate display width for emoji and CJK characters.
"""

import argparse
import re
import sys
from glob import glob
from pathlib import Path

from wcwidth import wcswidth


def display_width(text: str) -> int:
    """
    Calculate the display width of text accounting for Unicode characters.

    Parameters
    ----------
    text : str
        Text to measure.

    Returns
    -------
    int
        Display width in terminal columns.
    """
    width = wcswidth(text)
    # wcswidth returns -1 if text contains non-printable characters
    # Fall back to len() in that case
    return width if width >= 0 else len(text)


def parse_table(lines: list[str]) -> tuple[list[list[str]], int, int] | None:
    """
    Parse markdown table lines into cells.

    Parameters
    ----------
    lines : list[str]
        Lines that may form a markdown table.

    Returns
    -------
    tuple[list[list[str]], int, int] | None
        (rows, separator_index, num_columns) or None if not a valid table.
    """
    if len(lines) < 2:
        return None

    rows: list[list[str]] = []
    separator_idx = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            return None

        # Split by | and strip whitespace from cells
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        rows.append(cells)

        # Check if this is the separator row (contains only dashes and colons)
        if all(re.match(r"^:?-+:?$", cell) for cell in cells):
            separator_idx = i

    if separator_idx < 0:
        return None

    # Verify all rows have the same number of columns
    num_cols = len(rows[0])
    if not all(len(row) == num_cols for row in rows):
        return None

    return rows, separator_idx, num_cols


def format_table(rows: list[list[str]], separator_idx: int, num_cols: int) -> list[str]:
    """
    Format table rows with proper alignment based on display width.

    Parameters
    ----------
    rows : list[list[str]]
        Table rows as lists of cell contents.
    separator_idx : int
        Index of the separator row.
    num_cols : int
        Number of columns.

    Returns
    -------
    list[str]
        Formatted table lines.
    """
    # Calculate max display width for each column (excluding separator row)
    col_widths = [0] * num_cols
    for i, row in enumerate(rows):
        if i == separator_idx:
            continue
        for j, cell in enumerate(row):
            col_widths[j] = max(col_widths[j], display_width(cell))

    # Ensure minimum width of 3 for separator dashes
    col_widths = [max(w, 3) for w in col_widths]

    result = []
    for i, row in enumerate(rows):
        if i == separator_idx:
            # Format separator row
            cells = []
            for j, cell in enumerate(row):
                left_colon = cell.startswith(":")
                right_colon = cell.endswith(":")
                dash_count = col_widths[j] - (1 if left_colon else 0) - (1 if right_colon else 0)
                prefix = ":" if left_colon else ""
                suffix = ":" if right_colon else ""
                separator = prefix + "-" * dash_count + suffix
                cells.append(separator)
            result.append("| " + " | ".join(cells) + " |")
        else:
            # Format content row with proper padding
            cells = []
            for j, cell in enumerate(row):
                cell_width = display_width(cell)
                padding = col_widths[j] - cell_width
                cells.append(cell + " " * padding)
            result.append("| " + " | ".join(cells) + " |")

    return result


def process_markdown(content: str) -> str:
    """
    Process markdown content and fix table alignment.

    Parameters
    ----------
    content : str
        Markdown content.

    Returns
    -------
    str
        Content with fixed table alignment.
    """
    lines = content.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this might be the start of a table
        if line.strip().startswith("|") and line.strip().endswith("|"):
            # Collect consecutive table lines
            table_lines = []
            j = i
            while j < len(lines):
                current = lines[j].strip()
                if current.startswith("|") and current.endswith("|"):
                    table_lines.append(lines[j])
                    j += 1
                else:
                    break

            # Try to parse as a table
            parsed = parse_table(table_lines)
            if parsed:
                rows, separator_idx, num_cols = parsed
                formatted = format_table(rows, separator_idx, num_cols)
                result.extend(formatted)
                i = j
                continue

        result.append(line)
        i += 1

    return "\n".join(result)


def process_file(filepath: Path, dry_run: bool = False) -> bool:
    """
    Process a single markdown file.

    Parameters
    ----------
    filepath : Path
        Path to the markdown file.
    dry_run : bool, optional
        If True, don't write changes (default: False).

    Returns
    -------
    bool
        True if file was modified, False otherwise.
    """
    content = filepath.read_text(encoding="utf-8")
    fixed = process_markdown(content)

    if content != fixed:
        if not dry_run:
            filepath.write_text(fixed, encoding="utf-8")
            print(f"Fixed: {filepath}")
        else:
            print(f"Would fix: {filepath}")
        return True
    return False


def main() -> int:
    """
    CLI entry point for fixing markdown tables.

    Returns
    -------
    int
        Exit code (0 for success).
    """
    parser = argparse.ArgumentParser(
        description="Fix markdown table alignment with proper Unicode width handling.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  fix-md-tables ../docs/**/*.md ../README.md
  fix-md-tables --dry-run ../docs/copilot-chat.md
  fix-md-tables --base-dir .. docs/*.md README.md
        """,
    )
    parser.add_argument(
        "patterns",
        nargs="+",
        help="File paths or glob patterns to process",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Base directory to resolve file paths from",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )

    args = parser.parse_args()

    base_dir: Path | None = args.base_dir

    files_processed = 0
    files_modified = 0

    for pattern in args.patterns:
        # Prepend base_dir if specified
        if base_dir:
            pattern = str(base_dir / pattern)

        # Expand glob patterns
        matches = glob(pattern, recursive=True)
        if not matches:
            # If no glob match, treat as literal path
            matches = [pattern]

        for match in matches:
            filepath = Path(match)
            if filepath.is_file() and filepath.suffix.lower() == ".md":
                files_processed += 1
                if process_file(filepath, dry_run=args.dry_run):
                    files_modified += 1

    print(f"\nProcessed {files_processed} file(s), modified {files_modified} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
