"""
Temporal Activities for Buun Curator.
"""

from buun_curator.activities.api import (
    get_app_settings,
    get_entries,
    get_entry,
    list_unsummarized_entry_ids,
    save_entry_context,
)
from buun_curator.activities.cleanup import cleanup_old_entries
from buun_curator.activities.context import extract_entry_context
from buun_curator.activities.crawl import (
    crawl_feeds,
    crawl_single_feed,
    get_feed_options,
    list_feeds,
)
from buun_curator.activities.deepl_translate import deepl_translate_entries
from buun_curator.activities.distill import (
    distill_entry_content,
    get_entries_for_distillation,
    save_distilled_entries,
)
from buun_curator.activities.embedding import compute_embeddings, get_entries_for_embedding
from buun_curator.activities.enrichment import delete_enrichment, save_github_enrichment
from buun_curator.activities.entry_links import save_entry_links
from buun_curator.activities.evaluation import (
    EvaluateRagasInput,
    EvaluateRagasOutput,
    EvaluateSummarizationInput,
    EvaluateSummarizationOutput,
    SummarizeItem,
    evaluate_ragas,
    evaluate_summarization,
)
from buun_curator.activities.fetch import (
    fetch_and_save_entry_links,
    fetch_contents,
    fetch_single_content,
)
from buun_curator.activities.github import (
    fetch_github_readme,
    search_github_candidates,
    search_github_repository,
)
from buun_curator.activities.github_rerank import rerank_github_results
from buun_curator.activities.global_graph import (
    add_to_global_graph,
    add_to_global_graph_bulk,
    fetch_and_add_to_graph_bulk,
    get_entries_for_graph_update,
    mark_entries_graph_added,
    reset_global_graph,
)
from buun_curator.activities.graph_rag_session import (
    add_to_graph_rag_session,
    build_graph_rag_graph,
    close_graph_rag_session,
    reset_graph_rag_session,
    search_graph_rag_session,
)
from buun_curator.activities.ms_translate import ms_translate_entries
from buun_curator.activities.notify import (
    NotifyOutput,
    NotifyProgressInput,
    notify_progress,
)
from buun_curator.activities.search import (
    clear_search_index,
    get_entry_ids_for_indexing,
    get_orphaned_document_ids,
    index_entries_batch,
    init_search_index,
    remove_documents_from_index,
)
from buun_curator.activities.translate import (
    get_entries_for_translation,
    save_translations,
)
from buun_curator.activities.web_page_enrichment import save_web_page_enrichment

__all__ = [
    # Cleanup
    "cleanup_old_entries",
    # Global graph
    "add_to_global_graph",
    "add_to_global_graph_bulk",
    "fetch_and_add_to_graph_bulk",
    "get_entries_for_graph_update",
    "mark_entries_graph_added",
    "reset_global_graph",
    # GraphRAG session (Graphiti)
    "add_to_graph_rag_session",
    "build_graph_rag_graph",
    "close_graph_rag_session",
    "reset_graph_rag_session",
    "search_graph_rag_session",
    # Context extraction
    "extract_entry_context",
    # Crawl
    "crawl_feeds",
    "crawl_single_feed",
    "get_feed_options",
    "list_feeds",
    # Fetch
    "fetch_and_save_entry_links",
    "fetch_contents",
    "fetch_single_content",
    # API
    "get_app_settings",
    "get_entry",
    "get_entries",
    "list_unsummarized_entry_ids",
    "save_entry_context",
    # Notify (local activity for SSE)
    "notify_progress",
    "NotifyProgressInput",
    "NotifyOutput",
    # Content distillation
    "get_entries_for_distillation",
    "distill_entry_content",
    "save_distilled_entries",
    # Embedding
    "compute_embeddings",
    "get_entries_for_embedding",
    # Translate
    "get_entries_for_translation",
    "save_translations",
    # DeepL Translate
    "deepl_translate_entries",
    # MS Translate
    "ms_translate_entries",
    # GitHub enrichment
    "search_github_repository",
    "search_github_candidates",
    "fetch_github_readme",
    "rerank_github_results",
    "save_github_enrichment",
    "delete_enrichment",
    # Web page enrichment
    "save_web_page_enrichment",
    # Entry links
    "save_entry_links",
    # Search index
    "clear_search_index",
    "get_entry_ids_for_indexing",
    "get_orphaned_document_ids",
    "index_entries_batch",
    "init_search_index",
    "remove_documents_from_index",
    # Evaluation
    "evaluate_ragas",
    "EvaluateRagasInput",
    "EvaluateRagasOutput",
    "evaluate_summarization",
    "EvaluateSummarizationInput",
    "EvaluateSummarizationOutput",
    "SummarizeItem",
]
