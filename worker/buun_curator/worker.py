"""
Temporal Worker for Buun Curator.

Runs the Temporal worker that executes workflows and activities.
Supports hot reload via --reload flag for development.
"""

import asyncio
import logging
import os
from pathlib import Path

import temporalio.api.workflowservice.v1
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import (
    SandboxedWorkflowRunner,
    SandboxRestrictions,
)

from buun_curator.activities import (
    add_to_global_graph,
    add_to_global_graph_bulk,
    add_to_graph_rag_session,
    build_graph_rag_graph,
    cleanup_old_entries,
    clear_search_index,
    close_graph_rag_session,
    compute_embeddings,
    crawl_feeds,
    crawl_single_feed,
    deepl_translate_entries,
    delete_enrichment,
    distill_entry_content,
    evaluate_ragas,
    evaluate_summarization,
    extract_entry_context,
    fetch_and_add_to_graph_bulk,
    fetch_and_save_entry_links,
    fetch_contents,
    fetch_github_readme,
    fetch_single_content,
    get_app_settings,
    get_entries,
    get_entries_for_distillation,
    get_entries_for_embedding,
    get_entries_for_graph_update,
    get_entries_for_translation,
    get_entry,
    get_entry_ids_for_indexing,
    get_feed_options,
    get_orphaned_document_ids,
    index_entries_batch,
    init_search_index,
    list_feeds,
    list_unsummarized_entry_ids,
    mark_entries_graph_added,
    ms_translate_entries,
    notify_progress,
    remove_documents_from_index,
    rerank_github_results,
    reset_global_graph,
    reset_graph_rag_session,
    save_distilled_entries,
    save_entry_context,
    save_entry_links,
    save_github_enrichment,
    save_translations,
    save_web_page_enrichment,
    search_github_candidates,
    search_github_repository,
    search_graph_rag_session,
    update_entry_index,
)
from buun_curator.config import get_config
from buun_curator.health import HealthServer
from buun_curator.logging import configure_logging as configure_structlog
from buun_curator.logging import get_logger
from buun_curator.temporal import get_temporal_client
from buun_curator.tracing import init_tracing, shutdown_tracing
from buun_curator.workflows import (
    AllFeedsIngestionWorkflow,
    ContentDistillationWorkflow,
    ContextCollectionWorkflow,
    DeepResearchWorkflow,
    DeleteEnrichmentWorkflow,
    DomainFetchWorkflow,
    EmbeddingBackfillWorkflow,
    EntriesCleanupWorkflow,
    EvaluationWorkflow,
    ExtractEntryContextWorkflow,
    FetchEntryLinksWorkflow,
    GlobalGraphUpdateWorkflow,
    GraphRebuildWorkflow,
    PreviewFetchWorkflow,
    ReprocessEntriesWorkflow,
    ScheduleFetchWorkflow,
    SearchPruneWorkflow,
    SearchReindexWorkflow,
    SingleFeedIngestionWorkflow,
    SummarizationEvaluationWorkflow,
    TranslationWorkflow,
    UpdateEntryIndexWorkflow,
)


def configure_logging() -> None:
    """Configure logging for the worker."""
    # LOG_LEVEL: Controls buun_curator loggers (default: INFO)
    # Third-party libraries stay at WARNING to reduce noise
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    environment = os.getenv("ENVIRONMENT", "development")

    # Use structlog for structured logging with trace context
    configure_structlog(
        json_logs=environment != "development",
        log_level=log_level,
        component="worker",
    )

    # Add filter to root handler to strip context dicts from Temporal SDK log messages
    # (Filters on loggers don't apply to child loggers, so we add to handler instead)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(WorkflowLogFilter())

    # Temporal SDK logging - set via TEMPORAL_LOG_LEVEL env var (default: WARNING)
    # temporalio.workflow is set to LOG_LEVEL to see workflow.logger output
    temporal_log_level = os.getenv("TEMPORAL_LOG_LEVEL", "WARNING").upper()
    logging.getLogger("temporalio").setLevel(getattr(logging, temporal_log_level))
    logging.getLogger("temporalio.workflow").setLevel(getattr(logging, log_level))

    # Suppress noisy HTTP client logs (httpx/httpcore trace logs)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Graphiti logging - set to DEBUG to see LLM communication details
    # Set via GRAPHITI_LOG_LEVEL env var (default: WARNING)
    graphiti_log_level = os.getenv("GRAPHITI_LOG_LEVEL", "WARNING").upper()
    logging.getLogger("graphiti_core").setLevel(getattr(logging, graphiti_log_level))
    logging.getLogger("buun_curator.graphiti").setLevel(getattr(logging, graphiti_log_level))

    # LightRAG logging - set to DEBUG to see LLM communication details
    # Set via LIGHTRAG_LOG_LEVEL env var (default: WARNING)
    lightrag_log_level = os.getenv("LIGHTRAG_LOG_LEVEL", "WARNING").upper()
    for logger_name in [
        "lightrag",
        "buun_curator.lightrag",
    ]:
        logging.getLogger(logger_name).setLevel(getattr(logging, lightrag_log_level))


class WorkflowLogFilter(logging.Filter):
    """Filter to remove Temporal context dict from workflow log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Remove trailing context dict from workflow log messages."""
        msg = record.getMessage()
        # Temporal SDK appends " ({'attempt': ..., ...})" or " ({...})" to messages
        if msg.endswith(")"):
            # Try both patterns: " ({'" (dict with string keys) and " ({" (any dict)
            for pattern in (" ({'", ' ({"'):
                if pattern in msg:
                    idx = msg.rfind(pattern)
                    if idx > 0:
                        record.msg = msg[:idx]
                        record.args = ()
                        break
        return True


async def run_worker() -> None:
    """Run the Temporal worker."""
    config = get_config()
    logger = get_logger("buun-curator")

    # Initialize tracing (returns interceptor if enabled, None otherwise)
    tracing_interceptor = init_tracing()

    logger.info(
        f"Connecting to Temporal at {config.temporal_host} (namespace: {config.temporal_namespace})"
    )
    # Pass tracing interceptor to Client.connect() per Temporal docs
    interceptors = [tracing_interceptor] if tracing_interceptor else []
    client = await get_temporal_client(interceptors=interceptors)

    # Create health check function that verifies Temporal connectivity
    # Track consecutive failures to avoid flapping on transient errors
    health_check_failures = 0
    max_consecutive_failures = 2  # Allow 1 transient failure

    async def temporal_health_check() -> bool:
        nonlocal health_check_failures
        try:
            # Describe namespace to verify gRPC connectivity
            # Use a short timeout to avoid blocking
            await asyncio.wait_for(
                client.service_client.workflow_service.describe_namespace(
                    temporalio.api.workflowservice.v1.DescribeNamespaceRequest(
                        namespace=client.namespace
                    )
                ),
                timeout=5.0,
            )
            health_check_failures = 0  # Reset on success
            return True
        except asyncio.CancelledError:
            # Don't count cancellation as failure (happens during shutdown)
            logger.warning("Temporal health check was cancelled")
            return True
        except TimeoutError:
            health_check_failures += 1
            logger.warning(
                f"Temporal health check timed out "
                f"(failure {health_check_failures}/{max_consecutive_failures})"
            )
            return health_check_failures < max_consecutive_failures
        except Exception as e:
            health_check_failures += 1
            # Log as warning for transient errors, error for persistent ones
            if health_check_failures < max_consecutive_failures:
                logger.warning(
                    f"Temporal health check failed (transient): {e} "
                    f"(failure {health_check_failures}/{max_consecutive_failures})"
                )
                return True  # Allow transient failure
            else:
                logger.error(
                    f"Temporal health check failed (persistent): {e} "
                    f"(failure {health_check_failures}/{max_consecutive_failures})"
                )
                return False

    # Start health server
    health_port = int(os.getenv("HEALTH_PORT", "8080"))
    health_server = HealthServer(port=health_port, health_check=temporal_health_check)
    await health_server.start()

    logger.info(f"Starting worker on task queue: {config.task_queue}")

    # Log concurrency settings
    if config.max_concurrent_activities:
        logger.info(f"Max concurrent activities: {config.max_concurrent_activities}")
    if config.max_concurrent_workflow_tasks:
        logger.info(f"Max concurrent workflow tasks: {config.max_concurrent_workflow_tasks}")
    if config.max_concurrent_local_activities:
        logger.info(f"Max concurrent local activities: {config.max_concurrent_local_activities}")

    # Configure sandbox to passthrough Pydantic's lazy-loaded modules
    sandbox_runner = SandboxedWorkflowRunner(
        restrictions=SandboxRestrictions.default.with_passthrough_modules(
            "annotated_types",
            "pydantic_core",
            "pydantic_core._pydantic_core",
            "pydantic_core.core_schema",
        )
    )

    worker = Worker(
        client,
        task_queue=config.task_queue,
        workflow_runner=sandbox_runner,
        interceptors=interceptors,
        workflows=[
            AllFeedsIngestionWorkflow,
            ContentDistillationWorkflow,
            ContextCollectionWorkflow,
            DeepResearchWorkflow,
            DeleteEnrichmentWorkflow,
            DomainFetchWorkflow,
            EmbeddingBackfillWorkflow,
            EntriesCleanupWorkflow,
            EvaluationWorkflow,
            ExtractEntryContextWorkflow,
            FetchEntryLinksWorkflow,
            GlobalGraphUpdateWorkflow,
            GraphRebuildWorkflow,
            PreviewFetchWorkflow,
            ReprocessEntriesWorkflow,
            ScheduleFetchWorkflow,
            SearchPruneWorkflow,
            SearchReindexWorkflow,
            SingleFeedIngestionWorkflow,
            SummarizationEvaluationWorkflow,
            TranslationWorkflow,
            UpdateEntryIndexWorkflow,
        ],
        activities=[
            # Cleanup
            cleanup_old_entries,
            # Crawl
            crawl_feeds,
            crawl_single_feed,
            get_feed_options,
            list_feeds,
            # Fetch
            fetch_and_save_entry_links,
            fetch_contents,
            fetch_single_content,
            # API
            get_app_settings,
            get_entry,
            get_entries,
            list_unsummarized_entry_ids,
            save_entry_context,
            # Notify (local activity for SSE)
            notify_progress,
            # Content distillation
            get_entries_for_distillation,
            distill_entry_content,
            save_distilled_entries,
            # Embedding
            compute_embeddings,
            get_entries_for_embedding,
            # Translate
            get_entries_for_translation,
            save_translations,
            # DeepL Translate
            deepl_translate_entries,
            # MS Translate
            ms_translate_entries,
            # Search index
            clear_search_index,
            get_entry_ids_for_indexing,
            get_orphaned_document_ids,
            index_entries_batch,
            init_search_index,
            remove_documents_from_index,
            update_entry_index,
            # Context extraction
            extract_entry_context,
            # GitHub enrichment
            search_github_repository,
            search_github_candidates,
            fetch_github_readme,
            rerank_github_results,
            save_github_enrichment,
            delete_enrichment,
            # Web page enrichment
            save_web_page_enrichment,
            # Entry links
            save_entry_links,
            # Global graph
            add_to_global_graph,
            add_to_global_graph_bulk,
            fetch_and_add_to_graph_bulk,
            get_entries_for_graph_update,
            mark_entries_graph_added,
            reset_global_graph,
            # GraphRAG session (Graphiti)
            add_to_graph_rag_session,
            build_graph_rag_graph,
            close_graph_rag_session,
            reset_graph_rag_session,
            search_graph_rag_session,
            # Evaluation
            evaluate_ragas,
            evaluate_summarization,
        ],
        # Concurrency limits (None = use Temporal defaults)
        max_concurrent_activities=(
            config.max_concurrent_activities if config.max_concurrent_activities else None
        ),
        max_concurrent_workflow_tasks=(
            config.max_concurrent_workflow_tasks if config.max_concurrent_workflow_tasks else None
        ),
        max_concurrent_local_activities=(
            config.max_concurrent_local_activities
            if config.max_concurrent_local_activities
            else None
        ),
    )

    logger.info("Worker started, waiting for tasks...")
    try:
        await worker.run()
    finally:
        shutdown_tracing()


def worker_target() -> None:
    """Target function for subprocess when using reload mode."""
    configure_logging()
    asyncio.run(run_worker())


def main() -> None:
    """Entry point for the worker with optional --reload support."""
    import click

    @click.command()
    @click.option(
        "--reload", is_flag=True, default=False, help="Enable auto-reload on file changes"
    )
    def worker_main(reload: bool) -> None:
        """Start the Temporal worker."""
        configure_logging()
        logger = get_logger("buun-curator")

        if reload:
            from buun_curator.reload import ChangeReload

            base_dir = Path(__file__).parent
            reload_dirs = (
                str(base_dir / "activities"),
                str(base_dir / "chains"),
                str(base_dir / "graph_rag"),
                str(base_dir / "graphiti"),
                str(base_dir / "lightrag"),
                str(base_dir / "models"),
                str(base_dir / "ontology"),
                str(base_dir / "services"),
                str(base_dir / "utils"),
                str(base_dir / "workflows"),
            )
            logger.info(f"Hot reload enabled, watching: {', '.join(reload_dirs)}")
            ChangeReload(target=worker_target, reload_dirs=list(reload_dirs)).run()
        else:
            asyncio.run(run_worker())

    worker_main()


if __name__ == "__main__":
    main()
