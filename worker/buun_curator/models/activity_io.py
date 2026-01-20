"""
Input/Output models for Temporal Activities.

Temporal best practice: Use a single model argument for activities.
This ensures proper serialization and forward compatibility.

All activity I/O uses Pydantic BaseModel for:
- Automatic validation
- Consistent serialization
- Type safety
"""

from pydantic import BaseModel, Field

from buun_curator.models.types import ULID

# ============================================================================
# Crawl Activities
# ============================================================================


class CrawlFeedsInput(BaseModel):
    """Input for crawl_feeds activity."""

    pass  # No input parameters needed


class GetFeedOptionsInput(BaseModel):
    """Input for get_feed_options activity."""

    feed_id: ULID


class GetFeedOptionsOutput(BaseModel):
    """Output from get_feed_options activity."""

    feed_id: ULID
    fetch_limit: int = 20
    fetch_content: bool = True
    extraction_rules: list[dict] | None = None


class CrawlSingleFeedInput(BaseModel):
    """Input for crawl_single_feed activity."""

    feed_id: ULID
    feed_name: str
    feed_url: str
    etag: str = ""
    last_modified: str = ""
    fetch_limit: int = 20
    extraction_rules: list[dict] | None = None
    # Entry age filtering (None = use config default, 0 = no limit)
    max_entry_age_days: int | None = None


class CrawlSingleFeedOutput(BaseModel):
    """Output from crawl_single_feed activity."""

    feed_id: ULID
    feed_name: str
    status: str  # "processed", "skipped", "error"
    entries_created: int = 0
    entries_skipped: int = 0
    new_entries: list[dict] = Field(default_factory=list)
    error: str | None = None
    new_etag: str = ""
    new_last_modified: str = ""


class ListFeedsInput(BaseModel):
    """Input for list_feeds activity."""

    pass  # No input parameters needed


class ListFeedsOutput(BaseModel):
    """Output from list_feeds activity."""

    feeds: list[dict] = Field(default_factory=list)


class CrawlFeedDetail(BaseModel):
    """Detail of a single feed crawl."""

    feed_id: ULID
    feed_name: str
    status: str  # "processed", "skipped", "error"
    entries_created: int = 0
    entries_skipped: int = 0
    error: str | None = None


class CrawlEntryDetail(BaseModel):
    """Detail of a created entry."""

    entry_id: ULID
    feed_id: ULID
    feed_name: str
    title: str
    url: str


class CrawlFeedsOutput(BaseModel):
    """Output from crawl_feeds activity."""

    feeds_processed: int
    feeds_skipped: int
    entries_created: int
    entries_skipped: int
    new_entries: list[dict] = Field(default_factory=list)
    # Detailed info for Temporal UI
    feed_details: list[dict] = Field(default_factory=list)  # List of CrawlFeedDetail as dicts
    entry_details: list[dict] = Field(default_factory=list)  # List of CrawlEntryDetail as dicts


# ============================================================================
# Fetch Activities
# ============================================================================


class FetchContentsInput(BaseModel):
    """Input for fetch_contents activity."""

    entries: list[dict]
    timeout: int = 60  # Crawl4AI needs time for browser rendering
    concurrency: int = 3
    extraction_rules: list[dict] | None = None  # Feed-specific extraction rules


class FetchContentDetail(BaseModel):
    """Detail of a fetched content."""

    entry_id: ULID
    url: str
    title: str
    status: str  # "success", "failed", "timeout"
    full_content_bytes: int = 0
    error: str | None = None


class FetchContentsOutput(BaseModel):
    """
    Output from fetch_contents activity.

    Contents are saved directly to DB via MCP within the activity.
    Only metadata is returned to avoid gRPC message size limits.
    """

    # entry_id -> {full_content} for summarization (no raw_html)
    contents_for_summarize: dict[str, dict] = Field(default_factory=dict)
    # Detailed info for Temporal UI
    fetch_details: list[dict] = Field(default_factory=list)  # List of FetchContentDetail as dicts
    success_count: int = 0
    failed_count: int = 0


class FetchSingleContentInput(BaseModel):
    """
    Input for fetch_single_content activity.

    Supports two modes:
    1. URL fetch mode (default): Fetch content from URL using AsyncWebCrawler
    2. HTML processing mode: Process provided HTML content directly

    When html_content is provided, URL is ignored and HTML is processed directly.
    """

    url: str
    title: str | None = None
    timeout: int = 60
    feed_extraction_rules: list[dict] | None = None  # Extraction rules from feed options
    additional_extraction_rules: list[dict] | None = None  # Additional rules for testing
    entry_id: ULID | None = None  # If provided, save content to DB after fetching
    enable_thumbnail: bool = False  # Whether to capture and upload thumbnail
    html_content: str | None = None  # If provided, process HTML directly instead of fetching


class FetchSingleContentOutput(BaseModel):
    """
    Output from fetch_single_content activity.

    Note: When entry_id is provided in input, content is saved directly to DB
    and only status is returned to avoid gRPC response size limits.
    When entry_id is not provided (preview mode), content is returned.
    """

    full_content: str = ""
    # Status fields for when content is saved to DB
    status: str = "success"  # "success", "failed", "no_content"
    content_length: int = 0  # Length of full_content (for logging/stats)
    error: str | None = None


# ============================================================================
# Content Distillation Activities
# ============================================================================


class GetEntriesForDistillationInput(BaseModel):
    """Input for get_entries_for_distillation activity."""

    entry_ids: list[ULID] | None = None  # None means get all undistilled


class GetEntriesForDistillationOutput(BaseModel):
    """Output from get_entries_for_distillation activity."""

    entries: list[dict] = Field(default_factory=list)


class DistillEntryContentInput(BaseModel):
    """Input for distill_entry_content activity."""

    entries: list[dict]
    batch_size: int = 5
    target_language: str = ""  # Empty string means use entry's original language
    # Batch mode options:
    # - "parallel": Individual prompts with parallel API calls (recommended)
    # - "prompt_batch": Single prompt for multiple entries (experimental, may have accuracy issues)
    # - "sequential": Individual prompts, sequential processing (legacy)
    batch_mode: str = "parallel"


class DistillEntryContentOutput(BaseModel):
    """Output from distill_entry_content activity."""

    results: list[dict] = Field(default_factory=list)  # entry_id, summary, filtered_content


class SaveDistilledEntriesInput(BaseModel):
    """Input for save_distilled_entries activity."""

    results: list[dict]


class SaveDistilledEntriesOutput(BaseModel):
    """Output from save_distilled_entries activity."""

    saved_count: int = 0


# ============================================================================
# Translate Activities
# ============================================================================


class GetEntriesForTranslationInput(BaseModel):
    """Input for get_entries_for_translation activity."""

    entry_ids: list[ULID] | None = None  # None means get all untranslated


class GetEntriesForTranslationOutput(BaseModel):
    """Output from get_entries_for_translation activity."""

    entries: list[dict] = Field(default_factory=list)


class TranslateEntriesInput(BaseModel):
    """Input for translate_entries activity."""

    entries: list[dict]
    batch_size: int = 3
    target_language: str = ""


class TranslateEntriesOutput(BaseModel):
    """Output from translate_entries activity."""

    translations: list[dict] = Field(default_factory=list)  # entry_id, translated_content


class SaveTranslationsInput(BaseModel):
    """Input for save_translations activity."""

    translations: list[dict]


class SaveTranslationsOutput(BaseModel):
    """Output from save_translations activity."""

    saved_count: int = 0


# ============================================================================
# MCP Activities
# ============================================================================


class GetEntryInput(BaseModel):
    """Input for get_entry activity."""

    entry_id: ULID


class GetEntryOutput(BaseModel):
    """Output from get_entry activity."""

    entry: dict = Field(default_factory=dict)


class GetEntriesInput(BaseModel):
    """Input for get_entries activity."""

    entry_ids: list[ULID]


class GetEntriesOutput(BaseModel):
    """Output from get_entries activity."""

    entries: list[dict] = Field(default_factory=list)


class ListUnsummarizedEntryIdsInput(BaseModel):
    """Input for list_unsummarized_entry_ids activity."""

    limit: int = 100


class ListUnsummarizedEntryIdsOutput(BaseModel):
    """Output from list_unsummarized_entry_ids activity."""

    entry_ids: list[ULID] = Field(default_factory=list)


class GetAppSettingsInput(BaseModel):
    """Input for get_app_settings activity."""

    pass  # No input parameters needed


class GetAppSettingsOutput(BaseModel):
    """Output from get_app_settings activity."""

    target_language: str = ""  # Empty string means no translation

    # Workflow config from environment variables
    auto_distill: bool = True  # ENABLE_SUMMARIZATION
    enable_content_fetch: bool = True  # ENABLE_CONTENT_FETCH
    max_concurrent: int = 5  # FEED_INGESTION_CONCURRENCY
    enable_thumbnail: bool = True  # ENABLE_THUMBNAIL
    domain_fetch_delay: float = 2.0  # DOMAIN_FETCH_DELAY


# ============================================================================
# Context Extraction Activities
# ============================================================================


class ExtractEntryContextActivityInput(BaseModel):
    """Input for extract_entry_context activity."""

    entry_id: ULID
    title: str
    url: str
    content: str  # Markdown content


class SaveEntryContextInput(BaseModel):
    """Input for save_entry_context activity."""

    entry_id: ULID
    context: dict  # EntryContext as dict


class SaveEntryContextOutput(BaseModel):
    """Output from save_entry_context activity."""

    success: bool = False
    error: str | None = None


# ============================================================================
# GitHub Enrichment Activities
# ============================================================================


class GitHubRepoInfo(BaseModel):
    """GitHub repository information."""

    owner: str
    repo: str
    full_name: str  # "owner/repo"
    description: str | None
    url: str  # https://github.com/owner/repo
    stars: int
    forks: int
    language: str | None
    topics: list[str] = Field(default_factory=list)
    license: str | None = None
    updated_at: str | None = None
    open_issues: int = 0
    homepage: str | None = None  # Project website URL
    readme_filename: str | None = None  # e.g., "README.md"
    readme_content: str | None = None  # Decoded README content


class SearchGitHubInput(BaseModel):
    """Input for search_github_repository activity."""

    query: str  # Entity name (e.g., "Pyrefly")
    owner_hint: str | None = None  # From createdBy relationship (e.g., "Meta" -> "facebook")


class SearchGitHubOutput(BaseModel):
    """Output from search_github_repository activity."""

    found: bool = False
    repo: GitHubRepoInfo | None = None
    error: str | None = None


class SearchGitHubCandidatesInput(BaseModel):
    """Input for search_github_candidates activity."""

    query: str  # Entity name (e.g., "Pyrefly")
    owner_hint: str | None = None  # From createdBy relationship
    max_candidates: int = 5  # Maximum number of candidates to return


class GitHubCandidate(BaseModel):
    """A GitHub repository candidate with relevance score."""

    repo: GitHubRepoInfo
    score: float  # Relevance score from initial scoring


class SearchGitHubCandidatesOutput(BaseModel):
    """Output from search_github_candidates activity."""

    candidates: list[GitHubCandidate] = Field(default_factory=list)
    error: str | None = None


class RerankGitHubInput(BaseModel):
    """Input for rerank_github_results activity."""

    query: str  # Entity name being searched
    candidates: list[dict] = Field(default_factory=list)  # GitHubCandidate as dicts
    # Entry context for better ranking
    entry_title: str | None = None
    entry_key_points: list[str] = Field(default_factory=list)
    owner_hint: str | None = None  # From createdBy relationship


class RerankGitHubOutput(BaseModel):
    """Output from rerank_github_results activity."""

    selected: GitHubRepoInfo | None = None
    reason: str | None = None  # LLM's explanation for selection
    error: str | None = None


class FetchGitHubReadmeInput(BaseModel):
    """Input for fetch_github_readme activity."""

    owner: str
    repo: str


class FetchGitHubReadmeOutput(BaseModel):
    """Output from fetch_github_readme activity."""

    found: bool = False
    filename: str | None = None  # e.g., "README.md"
    content: str | None = None  # Decoded README content
    error: str | None = None


class EnrichmentCandidate(BaseModel):
    """Candidate entity for enrichment."""

    name: str
    entity_type: str  # "Software", "Company", etc.
    role: str | None  # "subject", "compared", etc.
    owner_hint: str | None = None  # From createdBy relationship
    github_url_hint: str | None = None  # From references if found


class EnrichmentPlan(BaseModel):
    """Plan for entity enrichment."""

    entry_id: ULID
    candidates: list[EnrichmentCandidate] = Field(default_factory=list)


class EnrichmentResult(BaseModel):
    """Result of enriching an entity with GitHub info."""

    name: str  # Entity name
    found: bool = False
    repo: GitHubRepoInfo | None = None
    error: str | None = None


class SaveGitHubEnrichmentInput(BaseModel):
    """Input for save_github_enrichment activity."""

    entry_id: ULID
    enrichment_results: list[dict]  # List of enrichment result dicts


class SaveGitHubEnrichmentOutput(BaseModel):
    """Output from save_github_enrichment activity."""

    success: bool = False
    saved_count: int = 0
    error: str | None = None


# ============================================================================
# Web Page Enrichment Activities
# ============================================================================


class WebPageInfo(BaseModel):
    """Information about a web page."""

    url: str  # Normalized URL
    title: str | None = None  # Page title (from link text)


class SaveWebPageEnrichmentInput(BaseModel):
    """Input for save_web_page_enrichment activity."""

    entry_id: ULID
    web_pages: list[WebPageInfo]


class SaveWebPageEnrichmentOutput(BaseModel):
    """Output from save_web_page_enrichment activity."""

    success: bool = False
    saved_count: int = 0
    error: str | None = None


# ============================================================================
# Entry Links Activities
# ============================================================================


class EntryLinkInfo(BaseModel):
    """Information about an entry link."""

    url: str  # Normalized URL
    title: str  # Link text


class SaveEntryLinksInput(BaseModel):
    """Input for save_entry_links activity."""

    entry_id: ULID
    links: list[EntryLinkInfo]


class SaveEntryLinksOutput(BaseModel):
    """Output from save_entry_links activity."""

    success: bool = False
    saved_count: int = 0
    error: str | None = None


# ============================================================================
# Search Index Activities
# ============================================================================


class InitSearchIndexInput(BaseModel):
    """Input for init_search_index activity."""

    pass  # No input parameters needed


class InitSearchIndexOutput(BaseModel):
    """Output from init_search_index activity."""

    success: bool = False
    error: str | None = None


class IndexEntriesBatchInput(BaseModel):
    """Input for index_entries_batch activity."""

    entry_ids: list[ULID]


class IndexEntriesBatchOutput(BaseModel):
    """Output from index_entries_batch activity."""

    indexed_count: int = 0
    error: str | None = None


class GetEntryIdsForIndexingInput(BaseModel):
    """Input for get_entry_ids_for_indexing activity."""

    batch_size: int = 100  # Max 100 per API call
    after: str | None = None  # Cursor for pagination


class GetEntryIdsForIndexingOutput(BaseModel):
    """Output from get_entry_ids_for_indexing activity."""

    entry_ids: list[ULID] = Field(default_factory=list)
    total_count: int = 0
    has_more: bool = False
    end_cursor: str | None = None  # Cursor for next page


class ClearSearchIndexInput(BaseModel):
    """Input for clear_search_index activity."""

    pass  # No input parameters needed


class ClearSearchIndexOutput(BaseModel):
    """Output from clear_search_index activity."""

    success: bool = False
    error: str | None = None


class GetOrphanedDocumentIdsInput(BaseModel):
    """Input for get_orphaned_document_ids activity."""

    batch_size: int = 1000  # Batch size for fetching from Meilisearch


class GetOrphanedDocumentIdsOutput(BaseModel):
    """Output from get_orphaned_document_ids activity."""

    orphaned_ids: list[str] = Field(default_factory=list)
    total_in_index: int = 0
    total_in_db: int = 0
    error: str | None = None


class RemoveDocumentsFromIndexInput(BaseModel):
    """Input for remove_documents_from_index activity."""

    document_ids: list[str]


class RemoveDocumentsFromIndexOutput(BaseModel):
    """Output from remove_documents_from_index activity."""

    removed_count: int = 0
    error: str | None = None


class UpdateEntryIndexInput(BaseModel):
    """Input for update_entry_index activity."""

    entry_id: ULID


class UpdateEntryIndexOutput(BaseModel):
    """Output from update_entry_index activity."""

    success: bool = False
    error: str | None = None


# ============================================================================
# Fetch Entry Links Activities
# ============================================================================


class FetchAndSaveLinksInput(BaseModel):
    """Input for fetch_and_save_entry_links activity."""

    entry_id: ULID
    urls: list[str]
    timeout: int = 60


class FetchLinkResult(BaseModel):
    """Result of fetching a single URL."""

    url: str
    title: str = ""
    success: bool = False
    content_length: int = 0
    error: str | None = None


class FetchAndSaveLinksOutput(BaseModel):
    """Output from fetch_and_save_entry_links activity."""

    results: list[FetchLinkResult] = Field(default_factory=list)
    success_count: int = 0
    failed_count: int = 0


# ============================================================================
# Delete Enrichment Activities
# ============================================================================


class DeleteEnrichmentActivityInput(BaseModel):
    """Input for delete_enrichment activity."""

    entry_id: ULID
    enrichment_type: str  # "web_page", "github", etc.
    source: str | None = None  # URL or identifier. If None, deletes all of this type.


class DeleteEnrichmentActivityOutput(BaseModel):
    """Output from delete_enrichment activity."""

    deleted: bool = False
    error: str | None = None


# ============================================================================
# GraphRAG Session Activities (Graphiti)
# ============================================================================


class AddToGraphRAGSessionInput(BaseModel):
    """Input for add_to_graph_rag_session activity."""

    entry_id: ULID
    content: str
    source_type: str = "text"  # "entry", "readme", "web_page", etc.
    metadata: dict | None = None  # Optional metadata for the content


class AddToGraphRAGSessionOutput(BaseModel):
    """Output from add_to_graph_rag_session activity."""

    success: bool = False
    graph_name: str = ""  # Graphiti graph name
    error: str | None = None


class BuildGraphRAGGraphInput(BaseModel):
    """Input for build_graph_rag_graph activity."""

    entry_id: ULID


class BuildGraphRAGGraphOutput(BaseModel):
    """Output from build_graph_rag_graph activity."""

    success: bool = False
    graph_name: str = ""
    error: str | None = None


class SearchGraphRAGSessionInput(BaseModel):
    """Input for search_graph_rag_session activity."""

    entry_id: ULID
    query: str
    search_mode: str = "hybrid"  # Graphiti uses hybrid search
    top_k: int = 10


class SearchGraphRAGSessionOutput(BaseModel):
    """Output from search_graph_rag_session activity."""

    success: bool = False
    results: list[dict] = Field(default_factory=list)
    error: str | None = None


class ResetGraphRAGSessionInput(BaseModel):
    """Input for reset_graph_rag_session activity."""

    entry_id: ULID


class ResetGraphRAGSessionOutput(BaseModel):
    """Output from reset_graph_rag_session activity."""

    success: bool = False
    deleted: bool = False
    error: str | None = None


class CloseGraphRAGSessionInput(BaseModel):
    """Input for close_graph_rag_session activity."""

    entry_id: ULID


class CloseGraphRAGSessionOutput(BaseModel):
    """Output from close_graph_rag_session activity."""

    success: bool = False
    error: str | None = None


# ============================================================================
# Global Graph Activities
# ============================================================================


class AddToGlobalGraphInput(BaseModel):
    """Input for add_to_global_graph activity."""

    entry_id: ULID
    content: str
    title: str | None = None
    url: str | None = None
    source_type: str = "entry"  # "entry", "readme", etc.


class AddToGlobalGraphOutput(BaseModel):
    """Output from add_to_global_graph activity."""

    success: bool = False
    error: str | None = None


class GraphEpisodeInput(BaseModel):
    """Single episode input for bulk graph addition."""

    entry_id: ULID
    content: str
    title: str | None = None
    url: str | None = None
    source_type: str = "entry"


class AddToGlobalGraphBulkInput(BaseModel):
    """Input for add_to_global_graph_bulk activity."""

    episodes: list[GraphEpisodeInput] = Field(default_factory=list)


class AddToGlobalGraphBulkOutput(BaseModel):
    """Output from add_to_global_graph_bulk activity."""

    success_count: int = 0
    failed_count: int = 0
    error: str | None = None


class FetchAndAddToGraphBulkInput(BaseModel):
    """
    Input for fetch_and_add_to_graph_bulk activity.

    Fetches entries internally and adds them to the graph,
    avoiding large payloads crossing the Temporal boundary.
    """

    entry_ids: list[ULID]


class FetchAndAddToGraphBulkOutput(BaseModel):
    """Output from fetch_and_add_to_graph_bulk activity."""

    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0  # Entries without content
    error: str | None = None


class ResetGlobalGraphOutput(BaseModel):
    """Output from reset_global_graph activity."""

    success: bool = False
    deleted_count: int = 0
    error: str | None = None


# ============================================================================
# Global Graph Update Activities
# ============================================================================


class GetEntriesForGraphUpdateInput(BaseModel):
    """Input for get_entries_for_graph_update activity."""

    batch_size: int = 50
    after: str | None = None  # Cursor for pagination


class GetEntriesForGraphUpdateOutput(BaseModel):
    """Output from get_entries_for_graph_update activity."""

    entry_ids: list[str]
    total_count: int
    has_more: bool
    end_cursor: str | None = None


class MarkEntriesGraphAddedInput(BaseModel):
    """Input for mark_entries_graph_added activity."""

    entry_ids: list[str]


class MarkEntriesGraphAddedOutput(BaseModel):
    """Output from mark_entries_graph_added activity."""

    updated_count: int = 0
    error: str | None = None


# ============================================================================
# Entries Cleanup Activities
# ============================================================================


class CleanupOldEntriesInput(BaseModel):
    """Input for cleanup_old_entries activity."""

    older_than_days: int = 7
    dry_run: bool = False


class CleanupOldEntriesOutput(BaseModel):
    """Output from cleanup_old_entries activity."""

    deleted_count: int = 0
    deleted_ids: list[str] = Field(default_factory=list)
    dry_run: bool = False
    older_than_days: int = 7
    cutoff_date: str = ""  # ISO 8601 format
    error: str | None = None


# ============================================================================
# Embedding Activities
# ============================================================================


class ComputeEmbeddingsInput(BaseModel):
    """Input for compute_embeddings activity."""

    entry_ids: list[ULID]


class ComputeEmbeddingsOutput(BaseModel):
    """Output from compute_embeddings activity."""

    computed_count: int = 0
    saved_count: int = 0
    error: str | None = None


class GetEntriesForEmbeddingInput(BaseModel):
    """Input for get_entries_for_embedding activity."""

    batch_size: int = 100
    after: str | None = None  # Cursor for pagination


class GetEntriesForEmbeddingOutput(BaseModel):
    """Output from get_entries_for_embedding activity."""

    entry_ids: list[str] = Field(default_factory=list)
    total_count: int = 0
    has_more: bool = False
    end_cursor: str | None = None
