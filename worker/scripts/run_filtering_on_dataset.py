"""
Run filtering (Distillation) on Langfuse filtering evaluation dataset.

For each item in the dataset, runs the content filtering chain and updates
the expected_output with the filtering results. This provides a baseline
that can be manually corrected in the Langfuse UI.

Required Environment Variables
------------------------------
OPENAI_API_KEY : str
    API key for OpenAI-compatible LLM service.
LANGFUSE_PUBLIC_KEY : str
    Langfuse public key for dataset access.
LANGFUSE_SECRET_KEY : str
    Langfuse secret key for dataset access.

Optional Environment Variables
------------------------------
OPENAI_BASE_URL : str
    Base URL for OpenAI-compatible LLM service (e.g., LiteLLM proxy).
LANGFUSE_HOST : str
    Langfuse host URL (default: https://cloud.langfuse.com).
DISTILL_MODEL : str
    LLM model for filtering (default: gemini-flash-lite).

Usage
-----
cd worker
uv run run-filtering-on-dataset --dataset-name filtering-evaluation
uv run run-filtering-on-dataset --dataset-name filtering-evaluation --dry-run
"""

import argparse
import logging
import os

from langchain_openai import ChatOpenAI
from langfuse import Langfuse
from pydantic import SecretStr

from buun_curator.chains.content_processing import create_content_processing_chain
from buun_curator.services.content_processor import _add_line_numbers, _extract_main_content

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_langfuse_client() -> Langfuse:
    """Get Langfuse client."""
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        raise ValueError(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set"
        )

    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def get_llm() -> ChatOpenAI:
    """Get LLM for content processing."""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("DISTILL_MODEL", "gemini-flash-lite")

    if not api_key:
        raise ValueError("OPENAI_API_KEY must be set")

    return ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
        temperature=0,
    )


def run_filtering_on_dataset(
    dataset_name: str,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    """
    Run filtering on all items in the dataset and update expected_output.

    Parameters
    ----------
    dataset_name : str
        Name of the Langfuse dataset.
    dry_run : bool
        If True, show what would be done without making changes.
    limit : int | None
        Maximum number of items to process.

    Returns
    -------
    dict
        Summary with processed count and any errors.
    """
    langfuse = get_langfuse_client()
    llm = get_llm()
    chain = create_content_processing_chain(llm)

    # Get dataset
    dataset = langfuse.get_dataset(dataset_name)
    items = dataset.items

    if limit:
        items = items[:limit]

    print(f"Dataset: {dataset_name}")
    print(f"Items to process: {len(items)}")

    if dry_run:
        print("\n[DRY RUN] Would process the following items:")
        for i, item in enumerate(items):
            title = item.metadata.get("title", "N/A") if item.metadata else "N/A"
            print(f"  {i + 1}. {item.id}: {title}")
        return {"processed": 0, "errors": 0, "dry_run": True}

    processed = 0
    errors = 0

    for i, item in enumerate(items):
        title = item.metadata.get("title", "Unknown") if item.metadata else "Unknown"
        print(f"\n[{i + 1}/{len(items)}] Processing: {title[:60]}...")

        try:
            # Get original content from input
            original_content = item.input.get("original_content", "")
            if not original_content:
                logger.warning(f"  No original_content in item {item.id}")
                errors += 1
                continue

            # Add line numbers for LLM processing
            numbered_content = _add_line_numbers(original_content)

            # Run filtering chain
            result = chain.invoke({
                "language": "Unknown",  # Language detection not needed for filtering
                "title": title,
                "content": numbered_content,
            })

            # Extract main content using start/end line numbers
            filtered_content = _extract_main_content(
                original_content,
                result.main_content_start_line,
                result.main_content_end_line,
            )

            # Build expected_output
            total_lines = len(original_content.split("\n"))
            expected_output = {
                "main_content_start_line": result.main_content_start_line,
                "main_content_end_line": result.main_content_end_line,
                "total_lines": total_lines,
                "filtered_content": filtered_content,
            }

            print(
                f"  main_content: lines {result.main_content_start_line}"
                f"-{result.main_content_end_line} of {total_lines}"
            )
            print(
                f"  filtered_content: {len(filtered_content)} chars "
                f"(original: {len(original_content)})"
            )

            # Update item by deleting and recreating
            # (Langfuse API doesn't have an update endpoint for dataset items)
            api = langfuse._resources.api if langfuse._resources else None
            if not api:
                raise RuntimeError("Langfuse API not available")

            # Store original data
            original_input = item.input
            original_metadata = item.metadata

            # Delete and recreate with expected_output
            api.dataset_items.delete(id=item.id)
            langfuse.create_dataset_item(
                dataset_name=dataset_name,
                input=original_input,
                expected_output=expected_output,
                metadata=original_metadata,
            )

            processed += 1

        except Exception as e:
            logger.error(f"  Error processing item {item.id}: {e}")
            errors += 1

    langfuse.flush()

    summary = {
        "dataset_name": dataset_name,
        "total_items": len(items),
        "processed": processed,
        "errors": errors,
    }

    print(f"\n{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print(f"{'=' * 60}")

    return summary


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run filtering on Langfuse dataset items"
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="filtering-evaluation",
        help="Langfuse dataset name (default: filtering-evaluation)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    # Check required environment variables
    missing = []
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        missing.append("LANGFUSE_PUBLIC_KEY")
    if not os.environ.get("LANGFUSE_SECRET_KEY"):
        missing.append("LANGFUSE_SECRET_KEY")

    if missing:
        print("Error: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        return

    run_filtering_on_dataset(
        dataset_name=args.dataset_name,
        dry_run=args.dry_run,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
