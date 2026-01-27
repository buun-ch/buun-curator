#!/usr/bin/env python
"""CLI tool to trigger Buun Curator workflows.

Usage:
    # Run feed ingestion using child workflows (recommended)
    # Config is read from environment variables at runtime:
    # ENABLE_SUMMARIZATION, ENABLE_CONTENT_FETCH, ENABLE_THUMBNAIL,
    # FEED_INGESTION_CONCURRENCY, DOMAIN_FETCH_DELAY
    uv run trigger ingest

    # Ingest a single feed by ID
    uv run trigger ingest-feed FEED_ID

    # Ingest a single feed without entry processing
    uv run trigger ingest-feed FEED_ID --no-summarize

    # List all feeds
    uv run trigger list-feeds

    # Distill all undistilled entries (filter + summarize)
    uv run trigger distill-entries

    # Distill specific entries
    uv run trigger distill-entries --entry-ids ID1 ID2 ID3

    # Reprocess specific entry IDs (fetch + summarize) via Temporal
    uv run trigger reprocess ENTRY_ID1 ENTRY_ID2

    # Reprocess specific entry IDs (fetch only)
    uv run trigger reprocess ENTRY_ID1 --no-summarize

    # Reprocess specific entry IDs (summarize only)
    uv run trigger reprocess ENTRY_ID1 --no-fetch

    # Fetch content for a specific entry (debug, direct without Temporal)
    uv run trigger fetch ENTRY_ID

    # Fetch content for a URL directly (debug)
    uv run trigger fetch --url URL [--title TITLE]

    # Extract structured context from an entry (debug, tests LLM extraction)
    uv run trigger extract-context ENTRY_ID

    # Collect context from multiple entries and analyze
    uv run trigger collect-context ENTRY_ID1 ENTRY_ID2 ENTRY_ID3

    # Rebuild search index (Meilisearch)
    uv run trigger reindex

    # Rebuild search index with custom batch size
    uv run trigger reindex --batch-size 1000

    # Rebuild search index after clearing all existing documents
    uv run trigger reindex --clean

    # Remove orphaned documents from search index (documents not in DB)
    uv run trigger prune

    # Rebuild global knowledge graph
    uv run trigger graph-rebuild

    # Rebuild global knowledge graph with custom batch size
    uv run trigger graph-rebuild --batch-size 100

    # Rebuild global knowledge graph after clearing all existing nodes
    uv run trigger graph-rebuild --clean

    # Update graph with pending entries only (entries not yet added)
    uv run trigger graph-update

    # Update graph with custom batch size
    uv run trigger graph-update --batch-size 100

    # Run deep research on an entry with a query
    uv run trigger deep-research ENTRY_ID "What is the main topic?"

    # Cleanup old entries (delete read, unstarred, not upvoted entries older than 7 days)
    uv run trigger cleanup

    # Cleanup with custom age threshold
    uv run trigger cleanup --days 14

    # Dry run (count without deleting)
    uv run trigger cleanup --dry-run

    # Compute embeddings for entries without them
    uv run trigger embedding-backfill

    # Embedding backfill with custom batch size
    uv run trigger embedding-backfill --batch-size 200
"""

import argparse
import asyncio
import logging

from temporalio.client import Client
from ulid import ULID

from buun_curator.config import get_config
from buun_curator.models import (
    AllFeedsIngestionInput,
    ContentDistillationInput,
    ContextCollectionInput,
    DeepResearchInput,
    EmbeddingBackfillInput,
    EntriesCleanupInput,
    ExtractEntryContextInput,
    GlobalGraphUpdateInput,
    GraphRebuildInput,
    ReprocessEntriesInput,
    SearchPruneInput,
    SearchReindexInput,
)
from buun_curator.temporal import get_temporal_client
from buun_curator.workflows import (
    AllFeedsIngestionWorkflow,
    ContentDistillationWorkflow,
    ContextCollectionWorkflow,
    DeepResearchWorkflow,
    EmbeddingBackfillWorkflow,
    EntriesCleanupWorkflow,
    ExtractEntryContextWorkflow,
    GlobalGraphUpdateWorkflow,
    GraphRebuildWorkflow,
    ReprocessEntriesWorkflow,
    SearchPruneWorkflow,
    SearchReindexWorkflow,
    SingleFeedIngestionWorkflow,
)
from buun_curator.workflows.single_feed_ingestion import SingleFeedIngestionInput

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("trigger_workflow")


async def run_all_feeds_ingestion(
    client: Client,
    task_queue: str,
) -> None:
    """
    Run the all feeds ingestion workflow (uses child workflows).

    All config (auto_distill, enable_content_fetch, max_concurrent,
    enable_thumbnail, domain_fetch_delay) is read from environment
    variables at runtime.
    """
    workflow_id = f"all-feeds-ingestion-{ULID()}"

    logger.info(f"Starting AllFeedsIngestionWorkflow: {workflow_id}")
    logger.info("  Config will be read from environment variables at runtime")

    handle = await client.start_workflow(
        AllFeedsIngestionWorkflow.run,
        AllFeedsIngestionInput(),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("Workflow completed:")
    logger.info(f"  Status: {result.status}")
    logger.info(f"  Feeds total: {result.feeds_total}")
    logger.info(f"  Feeds processed: {result.feeds_processed}")
    logger.info(f"  Feeds skipped: {result.feeds_skipped}")
    logger.info(f"  Feeds failed: {result.feeds_failed}")
    logger.info(f"  Entries created: {result.entries_created}")
    logger.info(f"  Contents fetched: {result.contents_fetched}")
    logger.info(f"  Entries distilled: {result.entries_distilled}")


async def run_single_feed_ingestion(
    client: Client,
    task_queue: str,
    feed_id: str,
    auto_distill: bool = True,
    enable_content_fetch: bool = True,
    enable_thumbnail: bool = False,
    domain_fetch_delay: float = 2.0,
) -> None:
    """Run ingestion workflow for a single feed."""
    from buun_curator.services.api import APIClient

    config = get_config()

    # Get feed details from REST API
    logger.info(f"Fetching feed details for {feed_id}...")
    async with APIClient(config.api_url, config.api_token) as api:
        feed = await api.get_feed(feed_id)

        if not feed or "error" in feed:
            logger.error(f"Feed not found: {feed_id}")
            return

        feed_name = feed.get("name", "Unknown")
        feed_url = feed.get("url", "")
        etag = feed.get("etag", "") or ""
        last_modified = feed.get("lastModified", "") or ""

        # Get fetchLimit directly from feed
        fetch_limit = feed.get("fetchLimit", 20)

        # extractionRules is still in options
        options = feed.get("options")
        extraction_rules: list[dict] | None = None
        if options and isinstance(options, dict):
            extraction_rules = options.get("extractionRules")

        # Get target language if distilling
        target_language = ""
        if auto_distill:
            settings = await api.get_settings()
            target_language = settings.get("targetLanguage", "")

    workflow_id = f"single-feed-{feed_id}-{ULID()}"

    logger.info(f"Starting SingleFeedIngestionWorkflow: {workflow_id}")
    logger.info(f"  Feed: {feed_name} ({feed_id})")
    logger.info(f"  URL: {feed_url}")
    logger.info(f"  auto_distill: {auto_distill}")
    logger.info(f"  enable_content_fetch: {enable_content_fetch}")
    logger.info(f"  enable_thumbnail: {enable_thumbnail}")
    logger.info(f"  domain_fetch_delay: {domain_fetch_delay}s")

    handle = await client.start_workflow(
        SingleFeedIngestionWorkflow.run,
        SingleFeedIngestionInput(
            feed_id=feed_id,
            feed_name=feed_name,
            feed_url=feed_url,
            etag=etag,
            last_modified=last_modified,
            fetch_limit=fetch_limit,
            extraction_rules=extraction_rules,
            auto_distill=auto_distill,
            enable_content_fetch=enable_content_fetch,
            enable_thumbnail=enable_thumbnail,
            target_language=target_language,
            domain_fetch_delay=domain_fetch_delay,
        ),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("Workflow completed:")
    logger.info(f"  Status: {result.status}")
    logger.info(f"  Feed: {result.feed_name}")
    logger.info(f"  Entries created: {result.entries_created}")
    logger.info(f"  Entries skipped: {result.entries_skipped}")
    logger.info(f"  Contents fetched: {result.contents_fetched}")
    logger.info(f"  Entries distilled: {result.entries_distilled}")

    if result.error:
        logger.error(f"  Error: {result.error}")


async def list_feeds_command() -> None:
    """List all registered feeds."""
    from buun_curator.services.api import APIClient

    config = get_config()

    logger.info("Fetching feeds from API...")
    async with APIClient(config.api_url, config.api_token) as api:
        feeds = await api.list_feeds()

    if not feeds:
        logger.info("No feeds found.")
        return

    logger.info(f"Found {len(feeds)} feeds:\n")
    for feed in feeds:
        feed_id = feed.get("id", "")
        name = feed.get("name", "Unknown")
        url = feed.get("url", "")
        logger.info(f"  {feed_id}")
        logger.info(f"    Name: {name}")
        logger.info(f"    URL: {url}")
        logger.info("")


async def run_content_distillation(
    client: Client,
    task_queue: str,
    entry_ids: list[str] | None = None,
    batch_size: int = 5,
) -> None:
    """Run the content distillation workflow."""
    workflow_id = f"content-distillation-{ULID()}"

    logger.info(f"Starting ContentDistillationWorkflow: {workflow_id}")
    logger.info(f"  entry_ids: {entry_ids if entry_ids else 'auto (undistilled)'}")
    logger.info(f"  batch_size: {batch_size}")

    handle = await client.start_workflow(
        ContentDistillationWorkflow.run,
        ContentDistillationInput(
            entry_ids=entry_ids,
            batch_size=batch_size,
        ),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("Workflow completed:")
    logger.info(f"  Status: {result.status}")
    logger.info(f"  Total entries: {result.total_entries}")
    logger.info(f"  Entries distilled: {result.entries_distilled}")


async def run_reprocess_entries(
    client: Client,
    task_queue: str,
    entry_ids: list[str],
    fetch_content: bool = True,
    summarize: bool = True,
) -> None:
    """Run the reprocess entries workflow for specific entry IDs."""
    workflow_id = f"reprocess-entries-{ULID()}"

    logger.info(f"Starting ReprocessEntriesWorkflow: {workflow_id}")
    logger.info(f"  entry_ids: {entry_ids}")
    logger.info(f"  fetch_content: {fetch_content}")
    logger.info(f"  summarize: {summarize}")

    handle = await client.start_workflow(
        ReprocessEntriesWorkflow.run,
        ReprocessEntriesInput(
            entry_ids=entry_ids,
            fetch_content=fetch_content,
            summarize=summarize,
        ),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("Workflow completed:")
    logger.info(f"  Status: {result.status}")
    logger.info(f"  Entries processed: {result.entries_processed}")
    logger.info(f"  Contents fetched: {result.contents_fetched}")
    logger.info(f"  Entries distilled: {result.entries_distilled}")

    if result.entry_details:
        logger.info("Entry details:")
        for detail in result.entry_details:
            logger.info(f"  - {detail.get('entry_id')}: {detail.get('title')}")


async def run_extract_context(
    client: Client,
    task_queue: str,
    entry_id: str,
) -> None:
    """Run the extract entry context workflow."""
    workflow_id = f"extract-context-{entry_id}-{ULID()}"

    logger.info(f"Starting ExtractEntryContextWorkflow: {workflow_id}")
    logger.info(f"  Entry ID: {entry_id}")

    handle = await client.start_workflow(
        ExtractEntryContextWorkflow.run,
        ExtractEntryContextInput(entry_id=entry_id),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("\n" + "=" * 60)
    logger.info("EXTRACTION RESULT:")
    logger.info("=" * 60)

    # Handle None result (entry not found or no content)
    if result is None:
        logger.warning("No result returned. Entry may not exist or have no content.")
        return

    # Debug: Check result type
    logger.info(f"  [DEBUG] Result type: {type(result)}")
    logger.info(f"  [DEBUG] Result: {result}")

    # Handle both dict (from Temporal) and Pydantic model
    if isinstance(result, dict):
        logger.info(f"  Domain: {result.get('domain')}")
        logger.info(f"  Content Type: {result.get('content_type')}")
        logger.info(f"  Language: {result.get('language')}")
        logger.info(f"  Confidence: {result.get('confidence', 0):.2f}")

        entities = result.get("entities", [])
        logger.info(f"\n  Entities ({len(entities)}):")
        for e in entities:
            if isinstance(e, dict):
                role_str = f", role={e.get('role')}" if e.get("role") else ""
                logger.info(f"    - {e.get('name')} ({e.get('type')}{role_str})")
                if e.get("description"):
                    logger.info(f"      {e.get('description')}")

        relationships = result.get("relationships", [])
        if relationships:
            logger.info(f"\n  Relationships ({len(relationships)}):")
            for r in relationships:
                if isinstance(r, dict):
                    logger.info(
                        f"    - {r.get('source')} --[{r.get('relation')}]--> {r.get('target')}"
                    )

        key_points = result.get("key_points", [])
        logger.info(f"\n  Key Points ({len(key_points)}):")
        for point in key_points:
            logger.info(f"    - {point}")

        metadata = result.get("metadata", {})
        logger.info("\n  Metadata:")
        if metadata.get("author"):
            logger.info(f"    Author: {metadata.get('author')}")
        if metadata.get("author_affiliation"):
            logger.info(f"    Affiliation: {metadata.get('author_affiliation')}")
        logger.info(f"    Sentiment: {metadata.get('sentiment', 'unknown')}")
        if metadata.get("target_audience"):
            logger.info(f"    Target Audience: {metadata.get('target_audience')}")
    else:
        # Pydantic model result (with use_enum_values=True, values are strings)
        logger.info(f"  Domain: {result.domain}")
        logger.info(f"  Content Type: {result.content_type}")
        logger.info(f"  Language: {result.language}")
        logger.info(f"  Confidence: {result.confidence:.2f}")

        logger.info(f"\n  Entities ({len(result.entities)}):")
        for e in result.entities:
            role_str = f", role={e.role}" if e.role else ""
            logger.info(f"    - {e.name} ({e.type}{role_str})")
            if e.description:
                logger.info(f"      {e.description}")

        if result.relationships:
            logger.info(f"\n  Relationships ({len(result.relationships)}):")
            for r in result.relationships:
                logger.info(f"    - {r.source} --[{r.relation}]--> {r.target}")

        logger.info(f"\n  Key Points ({len(result.key_points)}):")
        for point in result.key_points:
            logger.info(f"    - {point}")

        logger.info("\n  Metadata:")
        if result.metadata.author:
            logger.info(f"    Author: {result.metadata.author}")
        if result.metadata.author_affiliation:
            logger.info(f"    Affiliation: {result.metadata.author_affiliation}")
        logger.info(f"    Sentiment: {result.metadata.sentiment}")
        if result.metadata.target_audience:
            logger.info(f"    Target Audience: {result.metadata.target_audience}")

        if result.extracted_links:
            logger.info(f"\n  Extracted Links ({len(result.extracted_links)}):")
            for link in result.extracted_links[:10]:  # Show first 10
                logger.info(f"    - [{link.text}]({link.url})")


async def run_context_collection(
    client: Client,
    task_queue: str,
    entry_ids: list[str],
) -> None:
    """Run the context collection workflow for multiple entries."""
    workflow_id = f"context-collection-{ULID()}"

    logger.info(f"Starting ContextCollectionWorkflow: {workflow_id}")
    logger.info(f"  Entry IDs: {entry_ids}")

    handle = await client.start_workflow(
        ContextCollectionWorkflow.run,
        ContextCollectionInput(entry_ids=entry_ids),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("\n" + "=" * 60)
    logger.info("CONTEXT COLLECTION RESULT:")
    logger.info("=" * 60)

    # Handle dict result from Temporal
    if isinstance(result, dict):
        logger.info(f"  Status: {result.get('status')}")
        logger.info(f"  Total entries: {result.get('total_entries')}")
        logger.info(f"  Successful extractions: {result.get('successful_extractions')}")
        logger.info(f"  Failed extractions: {result.get('failed_extractions')}")

        plan = result.get("plan", [])
        if plan:
            logger.info("\n  Execution Plan:")
            for i, step in enumerate(plan, 1):
                logger.info(f"    [{i}] {step}")

        enrichment_results = result.get("enrichment_results", [])
        if enrichment_results:
            logger.info("\n  GitHub Enrichment Results:")
            for er in enrichment_results:
                if er.get("found") and er.get("repo"):
                    repo = er["repo"]
                    logger.info(f"    {er['name']}:")
                    logger.info(f"      Repository: {repo.get('full_name')}")
                    logger.info(f"      URL: {repo.get('url')}")
                    logger.info(f"      Stars: {repo.get('stars')} | Forks: {repo.get('forks')}")
                    if repo.get("description"):
                        logger.info(f"      Description: {repo.get('description')}")
                    if repo.get("language"):
                        logger.info(f"      Language: {repo.get('language')}")
                    if repo.get("topics"):
                        logger.info(f"      Topics: {', '.join(repo.get('topics', []))}")
                    if repo.get("license"):
                        logger.info(f"      License: {repo.get('license')}")
                else:
                    logger.info(f"    {er['name']}: Not found")

        if result.get("error"):
            logger.error(f"  Error: {result.get('error')}")
    else:
        # Pydantic model result
        logger.info(f"  Status: {result.status}")
        logger.info(f"  Total entries: {result.total_entries}")
        logger.info(f"  Successful extractions: {result.successful_extractions}")
        logger.info(f"  Failed extractions: {result.failed_extractions}")

        if result.plan:
            logger.info("\n  Execution Plan:")
            for i, step in enumerate(result.plan, 1):
                logger.info(f"    [{i}] {step}")

        if result.enrichment_results:
            logger.info("\n  GitHub Enrichment Results:")
            for er in result.enrichment_results:
                if er.get("found") and er.get("repo"):
                    repo = er["repo"]
                    logger.info(f"    {er['name']}:")
                    logger.info(f"      Repository: {repo.get('full_name')}")
                    logger.info(f"      URL: {repo.get('url')}")
                    logger.info(f"      Stars: {repo.get('stars')} | Forks: {repo.get('forks')}")
                    if repo.get("description"):
                        logger.info(f"      Description: {repo.get('description')}")
                    if repo.get("language"):
                        logger.info(f"      Language: {repo.get('language')}")
                    if repo.get("topics"):
                        logger.info(f"      Topics: {', '.join(repo.get('topics', []))}")
                    if repo.get("license"):
                        logger.info(f"      License: {repo.get('license')}")
                else:
                    logger.info(f"    {er['name']}: Not found")

        if result.error:
            logger.error(f"  Error: {result.error}")


async def run_search_reindex(
    client: Client,
    task_queue: str,
    batch_size: int = 500,
    clean: bool = False,
) -> None:
    """Run the search reindex workflow to rebuild Meilisearch index."""
    workflow_id = f"search-reindex-{ULID()}"

    logger.info(f"Starting SearchReindexWorkflow: {workflow_id}")
    logger.info(f"  batch_size: {batch_size}")
    logger.info(f"  clean: {clean}")

    handle = await client.start_workflow(
        SearchReindexWorkflow.run,
        SearchReindexInput(batch_size=batch_size, clean=clean),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("\n" + "=" * 60)
    logger.info("SEARCH REINDEX RESULT:")
    logger.info("=" * 60)

    if isinstance(result, dict):
        logger.info(f"  Status: {result.get('status')}")
        logger.info(f"  Indexed: {result.get('indexed_count')}/{result.get('total_count')}")
        if result.get("error"):
            logger.error(f"  Error: {result.get('error')}")
    else:
        logger.info(f"  Status: {result.status}")
        logger.info(f"  Indexed: {result.indexed_count}/{result.total_count}")
        if result.error:
            logger.error(f"  Error: {result.error}")


async def run_search_prune(
    client: Client,
    task_queue: str,
    batch_size: int = 1000,
) -> None:
    """Run the search prune workflow to remove orphaned documents."""
    workflow_id = f"search-prune-{ULID()}"

    logger.info(f"Starting SearchPruneWorkflow: {workflow_id}")
    logger.info(f"  batch_size: {batch_size}")

    handle = await client.start_workflow(
        SearchPruneWorkflow.run,
        SearchPruneInput(batch_size=batch_size),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("\n" + "=" * 60)
    logger.info("SEARCH PRUNE RESULT:")
    logger.info("=" * 60)

    if isinstance(result, dict):
        logger.info(f"  Status: {result.get('status')}")
        logger.info(f"  Removed: {result.get('removed_count')}")
        logger.info(
            f"  Index had: {result.get('total_in_index')}, DB has: {result.get('total_in_db')}"
        )
        if result.get("error"):
            logger.error(f"  Error: {result.get('error')}")
    else:
        logger.info(f"  Status: {result.status}")
        logger.info(f"  Removed: {result.removed_count}")
        logger.info(f"  Index had: {result.total_in_index}, DB has: {result.total_in_db}")
        if result.error:
            logger.error(f"  Error: {result.error}")


async def run_deep_research(
    client: Client,
    task_queue: str,
    entry_id: str,
    query: str,
) -> None:
    """Run the deep research workflow."""
    workflow_id = f"deep-research-{entry_id}-{ULID()}"

    logger.info(f"Starting DeepResearchWorkflow: {workflow_id}")
    logger.info(f"  Entry ID: {entry_id}")
    logger.info(f"  Query: {query}")

    handle = await client.start_workflow(
        DeepResearchWorkflow.run,
        DeepResearchInput(entry_id=entry_id, query=query),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("\n" + "=" * 60)
    logger.info("DEEP RESEARCH RESULT:")
    logger.info("=" * 60)

    if isinstance(result, dict):
        logger.info(f"  Status: {result.get('status')}")
        results = result.get("results", [])
        logger.info(f"  Results count: {len(results)}")
        if result.get("error"):
            logger.error(f"  Error: {result.get('error')}")
        if results:
            logger.info("\n  Search Results:")
            for i, r in enumerate(results[:5], 1):
                logger.info(f"    [{i}] {r}")
    else:
        logger.info(f"  Status: {result.status}")
        logger.info(f"  Results count: {len(result.results)}")
        if result.error:
            logger.error(f"  Error: {result.error}")
        if result.results:
            logger.info("\n  Search Results:")
            for i, r in enumerate(result.results[:5], 1):
                logger.info(f"    [{i}] {r}")


async def run_graph_rebuild(
    client: Client,
    task_queue: str,
    batch_size: int = 50,
    clean: bool = False,
) -> None:
    """Run the graph rebuild workflow to rebuild the global knowledge graph."""
    workflow_id = f"graph-rebuild-{ULID()}"

    logger.info(f"Starting GraphRebuildWorkflow: {workflow_id}")
    logger.info(f"  batch_size: {batch_size}")
    logger.info(f"  clean: {clean}")

    handle = await client.start_workflow(
        GraphRebuildWorkflow.run,
        GraphRebuildInput(batch_size=batch_size, clean=clean),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("\n" + "=" * 60)
    logger.info("GRAPH REBUILD RESULT:")
    logger.info("=" * 60)

    if isinstance(result, dict):
        logger.info(f"  Status: {result.get('status')}")
        logger.info(f"  Added: {result.get('added_count')}/{result.get('total_count')}")
        if result.get("deleted_count"):
            logger.info(f"  Deleted (clean): {result.get('deleted_count')}")
        if result.get("error"):
            logger.error(f"  Error: {result.get('error')}")
    else:
        logger.info(f"  Status: {result.status}")
        logger.info(f"  Added: {result.added_count}/{result.total_count}")
        if result.deleted_count:
            logger.info(f"  Deleted (clean): {result.deleted_count}")
        if result.error:
            logger.error(f"  Error: {result.error}")


async def run_graph_update(
    client: Client,
    task_queue: str,
    batch_size: int = 50,
) -> None:
    """Run the graph update workflow to add pending entries to the knowledge graph."""
    workflow_id = f"graph-update-{ULID()}"

    logger.info(f"Starting GlobalGraphUpdateWorkflow: {workflow_id}")
    logger.info(f"  batch_size: {batch_size}")
    logger.info("  (Only entries with graphAddedAt=NULL will be processed)")

    handle = await client.start_workflow(
        GlobalGraphUpdateWorkflow.run,
        GlobalGraphUpdateInput(batch_size=batch_size),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("\n" + "=" * 60)
    logger.info("GRAPH UPDATE RESULT:")
    logger.info("=" * 60)

    if isinstance(result, dict):
        logger.info(f"  Status: {result.get('status')}")
        logger.info(f"  Added: {result.get('added_count')}/{result.get('total_count')}")
        if result.get("error"):
            logger.error(f"  Error: {result.get('error')}")
    else:
        logger.info(f"  Status: {result.status}")
        logger.info(f"  Added: {result.added_count}/{result.total_count}")
        if result.error:
            logger.error(f"  Error: {result.error}")


async def run_entries_cleanup(
    client: Client,
    task_queue: str,
    older_than_days: int = 7,
    dry_run: bool = False,
) -> None:
    """Run the entries cleanup workflow to delete old entries."""
    workflow_id = f"entries-cleanup-{ULID()}"

    logger.info(f"Starting EntriesCleanupWorkflow: {workflow_id}")
    logger.info(f"  older_than_days: {older_than_days}")
    logger.info(f"  dry_run: {dry_run}")
    logger.info("  Criteria: isRead=true, isStarred=false, keep=false")

    handle = await client.start_workflow(
        EntriesCleanupWorkflow.run,
        EntriesCleanupInput(older_than_days=older_than_days, dry_run=dry_run),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("\n" + "=" * 60)
    logger.info("ENTRIES CLEANUP RESULT:")
    logger.info("=" * 60)

    if isinstance(result, dict):
        logger.info(f"  Status: {result.get('status')}")
        action = "Would delete" if dry_run else "Deleted"
        count = result.get("deletedCount", result.get("deleted_count", 0))
        logger.info(f"  {action}: {count} entries")
        days = result.get("olderThanDays", result.get("older_than_days", 0))
        logger.info(f"  Older than: {days} days")
        cutoff = result.get("cutoffDate", result.get("cutoff_date", ""))
        logger.info(f"  Cutoff date: {cutoff}")
        if result.get("error"):
            logger.error(f"  Error: {result.get('error')}")
    else:
        logger.info(f"  Status: {result.status}")
        action = "Would delete" if dry_run else "Deleted"
        logger.info(f"  {action}: {result.deleted_count} entries")
        logger.info(f"  Older than: {result.older_than_days} days")
        logger.info(f"  Cutoff date: {result.cutoff_date}")
        if result.error:
            logger.error(f"  Error: {result.error}")


async def run_embedding_backfill(
    client: Client,
    task_queue: str,
    batch_size: int = 100,
) -> None:
    """Run the embedding backfill workflow to compute embeddings for entries without them."""
    workflow_id = f"embedding-backfill-{ULID()}"

    logger.info(f"Starting EmbeddingBackfillWorkflow: {workflow_id}")
    logger.info(f"  batch_size: {batch_size}")
    logger.info("  (Entries with content but no embedding will be processed)")

    handle = await client.start_workflow(
        EmbeddingBackfillWorkflow.run,
        EmbeddingBackfillInput(batch_size=batch_size),
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info("Workflow started, waiting for result...")
    result = await handle.result()

    logger.info("\n" + "=" * 60)
    logger.info("EMBEDDING BACKFILL RESULT:")
    logger.info("=" * 60)

    if isinstance(result, dict):
        logger.info(f"  Status: {result.get('status')}")
        logger.info(f"  Total: {result.get('total_count', result.get('totalCount', 0))}")
        logger.info(f"  Computed: {result.get('computed_count', result.get('computedCount', 0))}")
        logger.info(f"  Saved: {result.get('saved_count', result.get('savedCount', 0))}")
        if result.get("error"):
            logger.error(f"  Error: {result.get('error')}")
    else:
        logger.info(f"  Status: {result.status}")
        logger.info(f"  Total: {result.total_count}")
        logger.info(f"  Computed: {result.computed_count}")
        logger.info(f"  Saved: {result.saved_count}")
        if result.error:
            logger.error(f"  Error: {result.error}")


async def run_fetch_debug(
    entry_id: str | None = None,
    url: str | None = None,
    title: str | None = None,
    save: bool = False,
) -> None:
    """Fetch content for debugging (directly, without Temporal).

    Args:
        entry_id: Entry ID to fetch content for (will get URL from API)
        url: Direct URL to fetch
        title: Title for duplicate heading removal
        save: Whether to save fetched content to API
    """
    # Enable debug logging for content fetcher
    logging.getLogger("buun_curator.services.content").setLevel(logging.DEBUG)
    logging.getLogger("crawl4ai").setLevel(logging.DEBUG)

    from buun_curator.services.api import APIClient
    from buun_curator.services.content import ContentFetcher

    config = get_config()

    if entry_id:
        # Get entry from API
        logger.info(f"Fetching entry {entry_id} from API...")
        async with APIClient(config.api_url, config.api_token) as api:
            entry = await api.get_entry(entry_id)

            if "error" in entry or not entry:
                logger.error(f"Entry not found: {entry.get('error', 'Unknown error')}")
                return

            url = entry.get("url", "")
            title = entry.get("title", "")
            existing_content = entry.get("fullContent") or entry.get("filteredContent")

            logger.info("Entry details:")
            logger.info(f"  ID: {entry_id}")
            logger.info(f"  Title: {title}")
            logger.info(f"  URL: {url}")
            logger.info(f"  Has existing content: {bool(existing_content)}")
            if existing_content:
                logger.info(f"  Existing content length: {len(existing_content)} chars")

    if not url:
        logger.error("No URL to fetch")
        return

    logger.info(f"\nFetching content from URL: {url}")
    logger.info(f"Title: {title}")

    fetcher = ContentFetcher(timeout=60)
    result = await fetcher.fetch(url, title)

    logger.info("\n" + "=" * 60)
    logger.info("FETCH RESULT:")
    logger.info("=" * 60)
    logger.info(f"  full_content: {len(result.full_content)} chars")

    if result.full_content:
        logger.info("\n--- Full content (first 1000 chars) ---")
        print(result.full_content[:1000])
        if len(result.full_content) > 1000:
            print("... (truncated)")
    else:
        logger.warning("\n*** NO CONTENT EXTRACTED ***")

    # Save to API if requested
    if save and entry_id and result.full_content:
        logger.info("\nSaving content to API...")
        async with APIClient(config.api_url, config.api_token) as api:
            await api.update_entry(
                entry_id,
                full_content=result.full_content,
            )
            logger.info("Content saved successfully")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Trigger Buun Curator workflows")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Feed ingestion command
    # Note: Config (auto_distill, enable_content_fetch, etc.) is read from env vars at runtime
    subparsers.add_parser("ingest", help="Run feed ingestion workflow")

    # Single feed ingestion command
    ingest_feed_parser = subparsers.add_parser(
        "ingest-feed", help="Run ingestion workflow for a single feed"
    )
    ingest_feed_parser.add_argument(
        "feed_id",
        help="Feed ID to ingest",
    )
    ingest_feed_parser.add_argument(
        "--no-summarize",
        action="store_true",
        help="Skip automatic summarization",
    )
    ingest_feed_parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip content fetching",
    )

    # List feeds command
    subparsers.add_parser("list-feeds", help="List all registered feeds")

    # Entry distillation command
    distill_parser = subparsers.add_parser(
        "distill-entries", help="Run entry distillation workflow"
    )
    distill_parser.add_argument(
        "--entry-ids",
        nargs="+",
        help="Specific entry IDs to distill",
    )
    distill_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for distillation (default: from config or 5)",
    )

    # Reprocess entries command
    reprocess_parser = subparsers.add_parser(
        "reprocess", help="Reprocess specific entry IDs (fetch + summarize)"
    )
    reprocess_parser.add_argument(
        "entry_ids",
        nargs="+",
        help="Entry IDs to reprocess",
    )
    reprocess_parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip content fetching (summarize only)",
    )
    reprocess_parser.add_argument(
        "--no-summarize",
        action="store_true",
        help="Skip summarization (fetch only)",
    )

    # Fetch debug command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch content for debugging")
    fetch_parser.add_argument(
        "entry_id",
        nargs="?",
        help="Entry ID to fetch content for",
    )
    fetch_parser.add_argument(
        "--url",
        help="Direct URL to fetch (instead of entry ID)",
    )
    fetch_parser.add_argument(
        "--title",
        help="Title for duplicate heading removal",
    )
    fetch_parser.add_argument(
        "--save",
        action="store_true",
        help="Save fetched content to API (requires entry_id)",
    )

    # Extract context command
    extract_parser = subparsers.add_parser(
        "extract-context", help="Extract structured context from an entry"
    )
    extract_parser.add_argument(
        "entry_id",
        help="Entry ID to extract context from",
    )

    # Context collection command
    collect_parser = subparsers.add_parser(
        "collect-context", help="Collect context from multiple entries and analyze"
    )
    collect_parser.add_argument(
        "entry_ids",
        nargs="+",
        help="Entry IDs to collect context from",
    )

    # Search reindex command
    reindex_parser = subparsers.add_parser("reindex", help="Rebuild search index (Meilisearch)")
    reindex_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for indexing (default: from config or 500)",
    )
    reindex_parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete all documents before reindexing",
    )

    # Search prune command
    prune_parser = subparsers.add_parser(
        "prune", help="Remove orphaned documents from search index"
    )
    prune_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for fetching from Meilisearch (default: from config or 1000)",
    )

    # Deep research command
    deep_research_parser = subparsers.add_parser(
        "deep-research", help="Run deep research on an entry with a query"
    )
    deep_research_parser.add_argument(
        "entry_id",
        help="Entry ID to research",
    )
    deep_research_parser.add_argument(
        "query",
        help="Research query",
    )

    # Graph rebuild command
    graph_rebuild_parser = subparsers.add_parser(
        "graph-rebuild", help="Rebuild global knowledge graph"
    )
    graph_rebuild_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for processing (default: from config or 50)",
    )
    graph_rebuild_parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete all nodes before rebuilding",
    )

    # Graph update command (incremental, only pending entries)
    graph_update_parser = subparsers.add_parser(
        "graph-update", help="Add pending entries to knowledge graph (graphAddedAt=NULL)"
    )
    graph_update_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for processing (default: from config or 50)",
    )

    # Entries cleanup command
    cleanup_parser = subparsers.add_parser(
        "cleanup", help="Delete old entries (read, unstarred, not upvoted)"
    )
    cleanup_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Delete entries older than this many days (default: 7)",
    )
    cleanup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count entries without deleting",
    )

    # Embedding backfill command
    embedding_backfill_parser = subparsers.add_parser(
        "embedding-backfill", help="Compute embeddings for entries without them"
    )
    embedding_backfill_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for processing (default: from config or 100)",
    )

    args = parser.parse_args()
    config = get_config()

    # Commands that don't need Temporal
    if args.command == "fetch":
        if not args.entry_id and not args.url:
            parser.error("Either entry_id or --url is required")
        await run_fetch_debug(
            entry_id=args.entry_id,
            url=args.url,
            title=args.title,
            save=args.save,
        )
        return

    if args.command == "list-feeds":
        await list_feeds_command()
        return

    logger.info(
        f"Connecting to Temporal at {config.temporal_host} (namespace: {config.temporal_namespace})"
    )
    client = await get_temporal_client()

    if args.command == "ingest":
        await run_all_feeds_ingestion(
            client,
            config.task_queue,
        )
    elif args.command == "distill-entries":
        await run_content_distillation(
            client,
            config.task_queue,
            entry_ids=args.entry_ids,
            batch_size=(
                args.batch_size if args.batch_size is not None else config.distillation_batch_size
            ),
        )
    elif args.command == "reprocess":
        await run_reprocess_entries(
            client,
            config.task_queue,
            entry_ids=args.entry_ids,
            fetch_content=not args.no_fetch,
            summarize=not args.no_summarize,
        )
    elif args.command == "ingest-feed":
        await run_single_feed_ingestion(
            client,
            config.task_queue,
            feed_id=args.feed_id,
            auto_distill=not args.no_summarize,
            enable_content_fetch=not args.no_fetch,
            enable_thumbnail=config.enable_thumbnail,
            domain_fetch_delay=config.domain_fetch_delay,
        )
    elif args.command == "extract-context":
        await run_extract_context(
            client,
            config.task_queue,
            entry_id=args.entry_id,
        )
    elif args.command == "collect-context":
        await run_context_collection(
            client,
            config.task_queue,
            entry_ids=args.entry_ids,
        )
    elif args.command == "reindex":
        await run_search_reindex(
            client,
            config.task_queue,
            batch_size=(
                args.batch_size if args.batch_size is not None else config.search_reindex_batch_size
            ),
            clean=args.clean,
        )
    elif args.command == "prune":
        await run_search_prune(
            client,
            config.task_queue,
            batch_size=(
                args.batch_size if args.batch_size is not None else config.search_prune_batch_size
            ),
        )
    elif args.command == "deep-research":
        await run_deep_research(
            client,
            config.task_queue,
            entry_id=args.entry_id,
            query=args.query,
        )
    elif args.command == "graph-rebuild":
        await run_graph_rebuild(
            client,
            config.task_queue,
            batch_size=(
                args.batch_size if args.batch_size is not None else config.graph_rebuild_batch_size
            ),
            clean=args.clean,
        )
    elif args.command == "graph-update":
        await run_graph_update(
            client,
            config.task_queue,
            batch_size=(
                args.batch_size
                if args.batch_size is not None
                else config.global_graph_update_batch_size
            ),
        )
    elif args.command == "cleanup":
        await run_entries_cleanup(
            client,
            config.task_queue,
            older_than_days=args.days,
            dry_run=args.dry_run,
        )
    elif args.command == "embedding-backfill":
        await run_embedding_backfill(
            client,
            config.task_queue,
            batch_size=(
                args.batch_size
                if args.batch_size is not None
                else config.embedding_backfill_batch_size
            ),
        )


def cli() -> None:
    """Entry point for the CLI."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
