"""
Input/Output models for Temporal Workflows.

Temporal best practice: Use a single model argument for workflows.
This ensures proper serialization and forward compatibility.

Uses Pydantic with camelCase aliases for JSON serialization via
pydantic_data_converter.
"""

from pydantic import Field

from buun_curator.config import (
    DEFAULT_DISTILLATION_BATCH_SIZE,
    DEFAULT_EMBEDDING_BACKFILL_BATCH_SIZE,
    DEFAULT_GLOBAL_GRAPH_UPDATE_BATCH_SIZE,
    DEFAULT_GRAPH_REBUILD_BATCH_SIZE,
    DEFAULT_SEARCH_PRUNE_BATCH_SIZE,
    DEFAULT_SEARCH_REINDEX_BATCH_SIZE,
)
from buun_curator.models.base import CamelCaseModel
from buun_curator.models.types import ULID

# ============================================================================
# AllFeedsIngestionWorkflow
# ============================================================================


class AllFeedsIngestionInput(CamelCaseModel):
    """Input for AllFeedsIngestionWorkflow."""

    pass


class AllFeedsIngestionResult(CamelCaseModel):
    """Result of all feeds ingestion workflow."""

    status: str
    feeds_total: int = 0
    feeds_processed: int = 0
    feeds_skipped: int = 0
    feeds_failed: int = 0
    entries_created: int = 0
    entries_skipped: int = 0
    contents_fetched: int = 0
    entries_distilled: int = 0


# ============================================================================
# SingleFeedIngestionWorkflow
# ============================================================================


class SingleFeedIngestionInput(CamelCaseModel):
    """Input for SingleFeedIngestionWorkflow."""

    feed_id: str
    feed_name: str
    feed_url: str
    etag: str = ""
    last_modified: str = ""
    fetch_limit: int = 20
    extraction_rules: list[dict] | None = None
    auto_distill: bool = True
    enable_content_fetch: bool = True
    target_language: str = ""
    enable_thumbnail: bool = False
    domain_fetch_delay: float = 2.0  # Delay between requests to same domain (seconds)
    parent_workflow_id: str = ""
    max_entry_age_days: int | None = None
    distillation_batch_size: int = DEFAULT_DISTILLATION_BATCH_SIZE


class SingleFeedIngestionResult(CamelCaseModel):
    """Result of single feed ingestion workflow."""

    feed_id: str
    feed_name: str
    status: str  # "completed", "skipped", "error"
    entries_created: int = 0
    entries_skipped: int = 0
    contents_fetched: int = 0
    entries_distilled: int = 0
    error: str | None = None
    new_entries: list[dict] = Field(default_factory=list)


# ============================================================================
# ScheduleFetchWorkflow
# ============================================================================


class ScheduleFetchInput(CamelCaseModel):
    """Input for ScheduleFetchWorkflow."""

    entries: list[dict]  # List of entries with entry_id, url, title, extraction_rules
    delay_seconds: float = 2.0  # Delay between requests to same domain
    timeout: int = 60  # Timeout per fetch request
    enable_thumbnail: bool = False  # Whether to capture and upload thumbnails
    auto_distill: bool = True  # Whether to distill after fetch
    target_language: str = ""  # Target language for distillation
    parent_workflow_id: str = ""  # Parent workflow ID for SSE notifications
    distillation_batch_size: int = DEFAULT_DISTILLATION_BATCH_SIZE


class ScheduleFetchOutput(CamelCaseModel):
    """Output from ScheduleFetchWorkflow."""

    # IDs of entries that were successfully fetched and saved to DB
    fetched_entry_ids: list[str] = Field(default_factory=list)
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0  # YouTube URLs, etc.
    domains_processed: int = 0
    entries_distilled: int = 0  # Number of entries successfully distilled


# ============================================================================
# DomainFetchWorkflow
# ============================================================================


class DomainFetchEntry(CamelCaseModel):
    """Entry to fetch within a domain."""

    entry_id: str
    url: str
    title: str = ""
    extraction_rules: list[dict] | None = None


class DomainFetchInput(CamelCaseModel):
    """Input for DomainFetchWorkflow."""

    domain: str
    entries: list[dict]  # List of DomainFetchEntry as dicts
    delay_seconds: float = 1.0
    timeout: int = 60
    enable_thumbnail: bool = False
    auto_distill: bool = True  # Whether to distill after fetch
    target_language: str = ""  # Target language for distillation
    parent_workflow_id: str = ""  # Parent workflow ID for SSE notifications


class DomainFetchResult(CamelCaseModel):
    """Result of fetching a single entry."""

    entry_id: str
    url: str
    title: str
    status: str  # "success", "failed", "no_content"
    content_length: int = 0  # Length of fetched content
    error: str | None = None


class DomainFetchOutput(CamelCaseModel):
    """Output from DomainFetchWorkflow."""

    domain: str
    results: list[dict] = Field(default_factory=list)  # List of DomainFetchResult as dicts
    success_count: int = 0
    failed_count: int = 0
    fetched_entry_ids: list[str] = Field(default_factory=list)
    entries_distilled: int = 0  # Number of entries successfully distilled


# ============================================================================
# ReprocessEntriesWorkflow
# ============================================================================


class ReprocessEntriesInput(CamelCaseModel):
    """Input for ReprocessEntriesWorkflow."""

    entry_ids: list[ULID] = Field(default_factory=list)
    fetch_content: bool = True
    summarize: bool = True


class ReprocessEntriesResult(CamelCaseModel):
    """Result of the reprocess entries workflow."""

    status: str
    entries_processed: int = 0
    contents_fetched: int = 0
    entries_distilled: int = 0
    entry_details: list[dict] | None = None


# ============================================================================
# ContentDistillationWorkflow
# ============================================================================


class ContentDistillationInput(CamelCaseModel):
    """Input for ContentDistillationWorkflow."""

    entry_ids: list[ULID] | None = None
    batch_size: int = DEFAULT_DISTILLATION_BATCH_SIZE
    parent_workflow_id: str = ""  # Parent workflow ID for SSE notifications
    show_toast: bool = True  # Whether to show toast in frontend


class ContentDistillationResult(CamelCaseModel):
    """Result of the content distillation workflow."""

    status: str
    total_entries: int = 0
    entries_distilled: int = 0


# ============================================================================
# TranslationWorkflow (unified)
# ============================================================================


class TranslationInput(CamelCaseModel):
    """Input for TranslationWorkflow."""

    entry_ids: list[ULID] | None = None
    provider: str = "microsoft"  # "deepl" or "microsoft"


class TranslationResult(CamelCaseModel):
    """Result of the translation workflow."""

    status: str
    provider: str = ""
    total_entries: int = 0
    translations_created: int = 0


# ============================================================================
# PreviewFetchWorkflow
# ============================================================================


class PreviewFetchInput(CamelCaseModel):
    """Input for PreviewFetchWorkflow."""

    url: str
    title: str | None = None
    feed_extraction_rules: list[dict] | None = None
    additional_extraction_rules: list[dict] | None = None
    timeout: int = 60


class PreviewFetchResult(CamelCaseModel):
    """Result of the preview fetch workflow."""

    status: str
    full_content: str = ""
    error: str | None = None


# ============================================================================
# ExtractEntryContextWorkflow
# ============================================================================


class ExtractEntryContextInput(CamelCaseModel):
    """Input for ExtractEntryContextWorkflow."""

    entry_id: ULID


# ============================================================================
# ContextCollectionWorkflow
# ============================================================================


class ContextCollectionInput(CamelCaseModel):
    """Input for ContextCollectionWorkflow."""

    entry_ids: list[ULID] = Field(default_factory=list)


class ContextCollectionOutput(CamelCaseModel):
    """Output for ContextCollectionWorkflow."""

    status: str  # "completed", "partial", "error"
    total_entries: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    plan: list[str] = Field(default_factory=list)
    enrichment_results: list[dict] = Field(default_factory=list)  # EnrichmentResult as dicts
    error: str | None = None


# ============================================================================
# Workflow Progress Query Response (for Temporal Query)
# ============================================================================


class EntryProgressState(CamelCaseModel):
    """
    Progress state for a single entry.

    Tracks the current status and when it changed.
    """

    entry_id: ULID = ""
    title: str = ""
    status: str = "pending"  # "pending", "fetching", "fetched", "distilling", "completed", "error"
    changed_at: str = ""  # ISO 8601 format
    error: str = ""


class WorkflowProgress(CamelCaseModel):
    """
    Base class for workflow progress state returned by Temporal Query.

    Subclass this for each workflow type to add workflow-specific fields.
    The `workflow_type` field is used as a discriminator in TypeScript.
    """

    # Workflow identification
    workflow_id: str = ""
    workflow_type: str = ""  # Discriminator: "ProcessEntries", etc.

    # Parent workflow ID (when called as child workflow)
    # Empty string means this is a top-level workflow or fire-and-forget
    parent_workflow_id: str = ""

    # Whether to show a toast notification in the frontend
    # Set to False for fire-and-forget child workflows to avoid orphan notifications
    show_toast: bool = True

    # Current status
    status: str = "running"  # "running", "completed", "error"
    current_step: str = "idle"  # Current step being executed

    # Human-readable message
    message: str = ""

    # Timestamps (ISO 8601 format)
    started_at: str = ""
    updated_at: str = ""

    # Error info (only set when status is "error")
    error: str = ""


class ReprocessEntriesProgress(WorkflowProgress):
    """Progress for ReprocessEntriesWorkflow."""

    workflow_type: str = "ReprocessEntries"

    # Per-entry progress: entry_id (ULID) -> EntryProgressState
    entry_progress: dict[ULID, EntryProgressState] = Field(default_factory=dict)

    # Summary counters (derived from entry_progress)
    total_entries: int = 0
    entries_fetched: int = 0
    entries_distilled: int = 0


class SingleFeedIngestionProgress(WorkflowProgress):
    """Progress for SingleFeedIngestionWorkflow."""

    workflow_type: str = "SingleFeedIngestion"

    # Feed info
    feed_id: str = ""
    feed_name: str = ""

    # Summary counters
    total_entries: int = 0
    entries_created: int = 0
    entries_skipped: int = 0
    contents_fetched: int = 0
    entries_distilled: int = 0


class ScheduleFetchProgress(WorkflowProgress):
    """Progress for ScheduleFetchWorkflow."""

    workflow_type: str = "ScheduleFetch"

    # Summary counters
    total_entries: int = 0
    total_domains: int = 0
    domains_completed: int = 0
    entries_fetched: int = 0
    entries_distilled: int = 0
    skipped_count: int = 0


class DomainFetchProgress(WorkflowProgress):
    """Progress for DomainFetchWorkflow."""

    workflow_type: str = "DomainFetch"

    # Domain info
    domain: str = ""

    # Current entry being processed
    current_entry_index: int = 0
    current_entry_title: str = ""

    # Per-entry progress: entry_id (ULID) -> EntryProgressState
    entry_progress: dict[ULID, EntryProgressState] = Field(default_factory=dict)

    # Summary counters
    total_entries: int = 0
    entries_fetched: int = 0
    entries_distilled: int = 0
    entries_failed: int = 0


class AllFeedsIngestionProgress(WorkflowProgress):
    """Progress for AllFeedsIngestionWorkflow."""

    workflow_type: str = "AllFeedsIngestion"

    # Feeds summary
    feeds_total: int = 0
    feeds_completed: int = 0  # processed + skipped + failed
    feeds_processed: int = 0
    feeds_skipped: int = 0
    feeds_failed: int = 0

    # Current batch info
    current_batch: int = 0
    total_batches: int = 0

    # Aggregate entry counters (from child workflows)
    entries_created: int = 0
    contents_fetched: int = 0
    entries_distilled: int = 0


class TranslationProgress(WorkflowProgress):
    """Progress for TranslationWorkflow."""

    workflow_type: str = "Translation"

    # Translation provider ("deepl" or "microsoft")
    provider: str = ""

    # Per-entry progress: entry_id (ULID) -> EntryProgressState
    # status values: "pending", "translating", "completed", "error"
    entry_progress: dict[ULID, EntryProgressState] = Field(default_factory=dict)

    # Summary counters
    total_entries: int = 0
    entries_translated: int = 0


class ContentDistillationProgress(WorkflowProgress):
    """Progress for ContentDistillationWorkflow."""

    workflow_type: str = "ContentDistillation"

    # Per-entry progress: entry_id (ULID) -> EntryProgressState
    # status values: "pending", "distilling", "completed", "error"
    entry_progress: dict[ULID, EntryProgressState] = Field(default_factory=dict)

    # Summary counters
    total_entries: int = 0
    entries_distilled: int = 0


class ContextCollectionProgress(WorkflowProgress):
    """Progress for ContextCollectionWorkflow."""

    workflow_type: str = "ContextCollection"

    # Per-entry progress: entry_id (ULID) -> EntryProgressState
    # status values: "pending", "extracting", "completed", "error"
    entry_progress: dict[ULID, EntryProgressState] = Field(default_factory=dict)

    # Summary counters
    total_entries: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0

    # Enrichment phase info
    enrichment_candidates_count: int = 0


# ============================================================================
# SearchReindexWorkflow
# ============================================================================


class SearchReindexInput(CamelCaseModel):
    """Input for SearchReindexWorkflow."""

    batch_size: int = DEFAULT_SEARCH_REINDEX_BATCH_SIZE
    clean: bool = False  # Delete all documents before reindexing


class SearchReindexOutput(CamelCaseModel):
    """Output for SearchReindexWorkflow."""

    status: str  # "completed", "error"
    indexed_count: int = 0
    total_count: int = 0
    error: str | None = None


class SearchPruneInput(CamelCaseModel):
    """Input for SearchPruneWorkflow."""

    batch_size: int = DEFAULT_SEARCH_PRUNE_BATCH_SIZE


class SearchPruneOutput(CamelCaseModel):
    """Output for SearchPruneWorkflow."""

    status: str  # "completed", "error"
    removed_count: int = 0
    total_in_index: int = 0
    total_in_db: int = 0
    error: str | None = None


# ============================================================================
# UpdateEntryIndexWorkflow
# ============================================================================


class UpdateEntryIndexInput(CamelCaseModel):
    """Input for UpdateEntryIndexWorkflow."""

    entry_id: ULID


class UpdateEntryIndexOutput(CamelCaseModel):
    """Output for UpdateEntryIndexWorkflow."""

    status: str  # "completed", "error"
    success: bool = False
    error: str | None = None


# ============================================================================
# GraphRebuildWorkflow
# ============================================================================


class GraphRebuildInput(CamelCaseModel):
    """Input for GraphRebuildWorkflow."""

    batch_size: int = DEFAULT_GRAPH_REBUILD_BATCH_SIZE
    clean: bool = False  # Delete all nodes before rebuilding


class GraphRebuildOutput(CamelCaseModel):
    """Output for GraphRebuildWorkflow."""

    status: str  # "completed", "error"
    added_count: int = 0
    total_count: int = 0
    deleted_count: int = 0  # Nodes deleted (if clean=True)
    error: str | None = None


# ============================================================================
# FetchEntryLinksWorkflow
# ============================================================================


class FetchEntryLinksInput(CamelCaseModel):
    """Input for FetchEntryLinksWorkflow."""

    entry_id: ULID
    urls: list[str] = Field(default_factory=list)
    timeout: int = 60


class FetchEntryLinksResult(CamelCaseModel):
    """Result of the fetch entry links workflow."""

    status: str  # "completed", "partial", "failed"
    fetched_count: int = 0
    failed_count: int = 0


class UrlProgressState(CamelCaseModel):
    """Progress state for a single URL."""

    url: str = ""
    status: str = "pending"  # "pending", "fetching", "completed", "error"
    title: str = ""
    changed_at: str = ""  # ISO 8601 format
    error: str = ""


class FetchEntryLinksProgress(WorkflowProgress):
    """Progress for FetchEntryLinksWorkflow."""

    workflow_type: str = "FetchEntryLinks"

    # Entry info
    entry_id: ULID = ""

    # Per-URL progress: url -> UrlProgressState
    url_progress: dict[str, UrlProgressState] = Field(default_factory=dict)

    # Summary counters
    total_urls: int = 0
    processed_urls: int = 0


# ============================================================================
# DeleteEnrichmentWorkflow
# ============================================================================


class DeleteEnrichmentInput(CamelCaseModel):
    """Input for DeleteEnrichmentWorkflow."""

    entry_id: ULID
    enrichment_type: str  # "web_page", "github", etc.
    source: str  # URL or identifier


class DeleteEnrichmentResult(CamelCaseModel):
    """Result of the delete enrichment workflow."""

    status: str  # "completed", "not_found", "error"
    deleted: bool = False
    error: str | None = None


class DeleteEnrichmentProgress(WorkflowProgress):
    """Progress for DeleteEnrichmentWorkflow."""

    workflow_type: str = "DeleteEnrichment"

    # Target info
    entry_id: ULID = ""
    enrichment_type: str = ""
    source: str = ""


# ============================================================================
# DeepResearchWorkflow
# ============================================================================


class DeepResearchInput(CamelCaseModel):
    """Input for DeepResearchWorkflow."""

    entry_id: ULID
    query: str
    search_mode: str = "hybrid"  # "graph", "summary", "hybrid", "chunks"


class DeepResearchResult(CamelCaseModel):
    """Result of the deep research workflow."""

    status: str  # "completed", "error"
    results: list[dict] = Field(default_factory=list)
    error: str | None = None


class EvaluationInput(CamelCaseModel):
    """Input for EvaluationWorkflow."""

    trace_id: str
    mode: str  # "research" or "dialogue"
    question: str
    contexts: list[str]
    answer: str


class EvaluationResult(CamelCaseModel):
    """Result of the evaluation workflow."""

    trace_id: str
    mode: str
    scores: dict[str, float] = Field(default_factory=dict)
    success: bool = True
    error: str = ""


# ============================================================================
# SummarizationEvaluationWorkflow
# ============================================================================


class SummarizationEvaluationItem(CamelCaseModel):
    """
    Single item for summarization evaluation.

    Note: Only entry_id and trace_id are passed to avoid large data in workflow input.
    The evaluation activity fetches content from the database using entry_id.
    """

    entry_id: str
    trace_id: str = ""  # Per-entry trace_id for Langfuse


class SummarizationEvaluationInput(CamelCaseModel):
    """Input for SummarizationEvaluationWorkflow."""

    trace_id: str
    items: list[SummarizationEvaluationItem]
    max_samples: int = 5  # Max entries to evaluate (for cost control)


class SummarizationEvaluationResult(CamelCaseModel):
    """Result of the summarization evaluation workflow."""

    trace_id: str
    average_scores: dict[str, float] = Field(default_factory=dict)
    evaluated_count: int = 0
    success: bool = True
    error: str = ""


# ============================================================================
# GlobalGraphUpdateWorkflow
# ============================================================================


class GlobalGraphUpdateInput(CamelCaseModel):
    """
    Input for GlobalGraphUpdateWorkflow.

    When entry_ids is empty, the workflow fetches entries with graphAddedAt=null.
    """

    entry_ids: list[str] = Field(default_factory=list)
    batch_size: int = DEFAULT_GLOBAL_GRAPH_UPDATE_BATCH_SIZE


class GlobalGraphUpdateResult(CamelCaseModel):
    """Result of the global graph update workflow."""

    status: str  # "completed", "error"
    added_count: int = 0
    total_count: int = 0
    error: str = ""


# ============================================================================
# EntriesCleanupWorkflow
# ============================================================================


class EntriesCleanupInput(CamelCaseModel):
    """
    Input for EntriesCleanupWorkflow.

    Deletes old entries that meet cleanup criteria:
    - isRead = true
    - isStarred = false
    - keep = false
    - publishedAt is older than the specified days
    """

    older_than_days: int = 7
    dry_run: bool = False  # If true, only count without deleting


class EntriesCleanupResult(CamelCaseModel):
    """Result of the entries cleanup workflow."""

    status: str  # "completed", "error"
    deleted_count: int = 0
    older_than_days: int = 7
    cutoff_date: str = ""  # ISO 8601 format
    error: str = ""


# ============================================================================
# EmbeddingBackfillWorkflow
# ============================================================================


class EmbeddingBackfillInput(CamelCaseModel):
    """
    Input for EmbeddingBackfillWorkflow.

    Computes embeddings for entries that have content but no embedding.
    """

    batch_size: int = DEFAULT_EMBEDDING_BACKFILL_BATCH_SIZE


class EmbeddingBackfillResult(CamelCaseModel):
    """Result of the embedding backfill workflow."""

    status: str  # "completed", "error"
    total_count: int = 0
    computed_count: int = 0
    saved_count: int = 0
    error: str = ""
