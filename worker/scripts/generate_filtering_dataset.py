"""
Generate filtering evaluation dataset from labeled entries.

Samples entries with label 'eval-filtering' from the database and uploads
them to Langfuse Dataset for manual annotation.

Required Environment Variables
------------------------------
DATABASE_URL : str
    PostgreSQL connection URL for fetching entries.
LANGFUSE_PUBLIC_KEY : str
    Langfuse public key for dataset upload (required unless --no-upload).
LANGFUSE_SECRET_KEY : str
    Langfuse secret key for dataset upload (required unless --no-upload).

Optional Environment Variables
------------------------------
LANGFUSE_HOST : str
    Langfuse host URL (default: https://cloud.langfuse.com).

Output Directory Structure
--------------------------
worker/evaluation/<dataset-name>/
├── data/
│   └── filtering_entries.json   # Sampled entries for filtering evaluation
└── results/                     # Evaluation results (created by eval script)

Usage
-----
cd worker
uv run generate-filtering-dataset
uv run generate-filtering-dataset --dataset-name my-filtering-eval
uv run generate-filtering-dataset --label custom-label
uv run generate-filtering-dataset --no-upload
"""

import argparse
import json
import os
from pathlib import Path

import psycopg

# Langfuse import (lazy loaded)
Langfuse = None


def get_langfuse_client():
    """Get Langfuse client for dataset upload."""
    global Langfuse
    if Langfuse is None:
        from langfuse import Langfuse as LangfuseClass

        Langfuse = LangfuseClass

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        raise ValueError(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set "
            "for Langfuse upload"
        )

    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def fetch_labeled_entries(label_name: str, limit: int | None = None) -> list[dict]:
    """
    Fetch entries with the specified label from the database.

    Parameters
    ----------
    label_name : str
        Label name to filter entries (e.g., 'eval-filtering').
    limit : int | None
        Maximum number of entries to fetch.

    Returns
    -------
    list[dict]
        List of entry dictionaries with id, title, url, full_content,
        filtered_content.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    query = """
        SELECT
            e.id,
            e.title,
            e.url,
            e.full_content,
            e.filtered_content
        FROM entries e
        JOIN entry_labels el ON e.id = el.entry_id
        JOIN labels l ON el.label_id = l.id
        WHERE l.name = %s
          AND e.full_content IS NOT NULL
          AND e.full_content != ''
        ORDER BY e.updated_at DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(query, (label_name,))  # type: ignore[arg-type]
        rows = cur.fetchall()

    entries = []
    for row in rows:
        entries.append({
            "id": row[0],
            "title": row[1],
            "url": row[2],
            "full_content": row[3],
            "filtered_content": row[4],
        })

    return entries


def upload_to_langfuse(
    entries: list[dict],
    dataset_name: str,
) -> None:
    """
    Upload entries to Langfuse Dataset.

    Parameters
    ----------
    entries : list[dict]
        List of entry dictionaries.
    dataset_name : str
        Name of the Langfuse dataset.
    """
    langfuse = get_langfuse_client()

    # Create or get dataset
    print(f"\nUploading to Langfuse Dataset: {dataset_name}")
    dataset = langfuse.create_dataset(
        name=dataset_name,
        description=(
            "Filtering evaluation dataset - "
            "entries for content filtering quality assessment"
        ),
    )
    print(f"  Dataset ID: {dataset.id}")

    # Upload each entry as a dataset item
    uploaded = 0
    for entry in entries:
        # Input: original content before filtering
        input_data = {
            "original_content": entry["full_content"],
        }

        # Metadata for reference
        metadata = {
            "entry_id": entry["id"],
            "title": entry["title"],
            "url": entry["url"],
        }

        # Include current filtered_content as reference (not expected_output)
        # expected_output should be manually annotated
        if entry["filtered_content"]:
            metadata["current_filtered_content"] = entry["filtered_content"]

        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            input=input_data,
            expected_output=None,  # To be filled in via manual annotation
            metadata=metadata,
        )
        uploaded += 1

    langfuse.flush()
    print(f"  Uploaded: {uploaded} items")
    print(
        "\nNext steps:\n"
        "  1. Open Langfuse Dataset UI\n"
        "  2. For each item, add expected_output with:\n"
        "     - skip_lines_top: number of lines to remove from start\n"
        "     - skip_lines_bottom: number of lines to remove from end\n"
        "     - filtered_content: expected filtered content"
    )


def main():
    """Generate filtering evaluation dataset."""
    parser = argparse.ArgumentParser(
        description="Generate filtering evaluation dataset from labeled entries"
    )
    parser.add_argument(
        "--label",
        type=str,
        default="eval-filtering",
        help="Label name to filter entries (default: eval-filtering)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of entries to fetch",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="filtering-evaluation",
        help="Dataset name for directory and Langfuse (default: filtering-evaluation)",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip uploading to Langfuse Dataset",
    )
    args = parser.parse_args()

    # Set output directory based on dataset name
    output_dir = Path("evaluation") / args.dataset_name / "data"

    # Fetch entries with label
    print(f"Fetching entries with label '{args.label}'...")
    entries = fetch_labeled_entries(args.label, args.limit)
    print(f"  Found: {len(entries)} entries")

    if not entries:
        print(f"\nNo entries found with label '{args.label}'.")
        print("Add the label to entries you want to use for filtering evaluation.")
        return

    # Save to local file
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "filtering_entries.json"

    output_data = {
        "label": args.label,
        "count": len(entries),
        "entries": [
            {
                "id": e["id"],
                "title": e["title"],
                "url": e["url"],
                "full_content_length": (
                    len(e["full_content"]) if e["full_content"] else 0
                ),
                "filtered_content_length": (
                    len(e["filtered_content"]) if e["filtered_content"] else 0
                ),
            }
            for e in entries
        ],
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved entry list to: {output_file}")

    # Upload to Langfuse
    if not args.no_upload:
        upload_to_langfuse(entries, args.dataset_name)
    else:
        print("\nSkipped Langfuse upload (--no-upload specified).")


if __name__ == "__main__":
    main()
