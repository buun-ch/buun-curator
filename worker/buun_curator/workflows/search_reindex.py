"""
Search Reindex Workflow.

Workflow for rebuilding the Meilisearch index from all entries.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities.search import (
        clear_search_index,
        get_entry_ids_for_indexing,
        index_entries_batch,
        init_search_index,
    )
    from buun_curator.models import (
        ClearSearchIndexInput,
        ClearSearchIndexOutput,
        GetEntryIdsForIndexingInput,
        GetEntryIdsForIndexingOutput,
        IndexEntriesBatchInput,
        IndexEntriesBatchOutput,
        InitSearchIndexInput,
        InitSearchIndexOutput,
    )
    from buun_curator.models.workflow_io import (
        SearchReindexInput,
        SearchReindexOutput,
    )


@workflow.defn
class SearchReindexWorkflow:
    """Workflow for rebuilding the Meilisearch index."""

    @workflow.run
    async def run(self, input: SearchReindexInput) -> SearchReindexOutput:
        """
        Rebuild the Meilisearch index from all entries.

        Parameters
        ----------
        input : SearchReindexInput
            Input containing batch_size option.

        Returns
        -------
        SearchReindexOutput
            Output containing indexed_count and status.
        """
        # API max is 100, so cap batch_size
        batch_size = min(input.batch_size or 100, 100)
        wf_info = workflow.info()

        workflow.logger.info(
            "SearchReindexWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "clean": input.clean,
                "batch_size": batch_size,
            },
        )

        # 0. Optionally clear all documents first
        if input.clean:
            workflow.logger.info("Clearing all documents from index...")
            clear_result: ClearSearchIndexOutput = await workflow.execute_activity(
                clear_search_index,
                ClearSearchIndexInput(),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            if not clear_result.success:
                workflow.logger.error(f"Failed to clear index: {clear_result.error}")
                return SearchReindexOutput(
                    status="error",
                    error=clear_result.error or "Failed to clear index",
                )
            workflow.logger.info("Index cleared successfully")

        # 1. Initialize index settings
        workflow.logger.info("Initializing search index...")
        init_result: InitSearchIndexOutput = await workflow.execute_activity(
            init_search_index,
            InitSearchIndexInput(),
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        if not init_result.success:
            workflow.logger.error(f"Failed to initialize index: {init_result.error}")
            return SearchReindexOutput(
                status="error",
                error=init_result.error or "Failed to initialize index",
            )

        # 2. Get first batch of entry IDs
        workflow.logger.info("Getting entry IDs...")
        ids_result: GetEntryIdsForIndexingOutput = await workflow.execute_activity(
            get_entry_ids_for_indexing,
            GetEntryIdsForIndexingInput(batch_size=batch_size),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        total_count = ids_result.total_count
        workflow.logger.info("Found entries to index", extra={"total_count": total_count})

        if total_count == 0:
            workflow.logger.info("No entries to index")
            return SearchReindexOutput(
                status="completed",
                indexed_count=0,
                total_count=0,
            )

        # 3. Index entries in batches using cursor-based pagination
        indexed_count = 0
        batch_num = 0
        error_count = 0
        last_error: str | None = None
        cursor: str | None = None

        while True:
            batch_num += 1

            # Get batch of entry IDs (first batch already fetched)
            if batch_num > 1:
                ids_result = await workflow.execute_activity(
                    get_entry_ids_for_indexing,
                    GetEntryIdsForIndexingInput(batch_size=batch_size, after=cursor),
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )

            if not ids_result.entry_ids:
                break

            workflow.logger.info(
                "Indexing batch",
                extra={"batch_num": batch_num, "entries": len(ids_result.entry_ids)},
            )

            # Index the batch
            index_result: IndexEntriesBatchOutput = await workflow.execute_activity(
                index_entries_batch,
                IndexEntriesBatchInput(entry_ids=ids_result.entry_ids),
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            indexed_count += index_result.indexed_count

            if index_result.error:
                error_count += 1
                last_error = index_result.error
                workflow.logger.error(
                    "Batch indexing failed",
                    extra={
                        "batch_num": batch_num,
                        "error": index_result.error,
                        "expected": len(ids_result.entry_ids),
                        "indexed": index_result.indexed_count,
                    },
                )

            if not ids_result.has_more:
                break

            cursor = ids_result.end_cursor

        # Determine final status - fail if any errors occurred
        if error_count > 0:
            workflow.logger.error(
                "SearchReindexWorkflow failed",
                extra={
                    "workflow_id": wf_info.workflow_id,
                    "indexed_count": indexed_count,
                    "total_count": total_count,
                    "error_count": error_count,
                    "last_error": last_error,
                },
            )
            return SearchReindexOutput(
                status="error",
                indexed_count=indexed_count,
                total_count=total_count,
                error=f"{error_count} batch(es) failed: {last_error}",
            )

        workflow.logger.info(
            "SearchReindexWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "indexed_count": indexed_count,
                "total_count": total_count,
            },
        )

        return SearchReindexOutput(
            status="completed",
            indexed_count=indexed_count,
            total_count=total_count,
        )
