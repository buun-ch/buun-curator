"""
Graph Rebuild Workflow.

Workflow for rebuilding the global knowledge graph from all entries.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities.global_graph import (
        fetch_and_add_to_graph_bulk,
        reset_global_graph,
    )
    from buun_curator.activities.search import get_entry_ids_for_indexing
    from buun_curator.models import (
        FetchAndAddToGraphBulkInput,
        FetchAndAddToGraphBulkOutput,
        GetEntryIdsForIndexingInput,
        GetEntryIdsForIndexingOutput,
        GraphRebuildInput,
        GraphRebuildOutput,
        ResetGlobalGraphOutput,
    )


@workflow.defn
class GraphRebuildWorkflow:
    """Workflow for rebuilding the global knowledge graph."""

    @workflow.run
    async def run(self, input: GraphRebuildInput) -> GraphRebuildOutput:
        """
        Rebuild the global knowledge graph from all entries.

        Parameters
        ----------
        input : GraphRebuildInput
            Input containing batch_size and clean options.

        Returns
        -------
        GraphRebuildOutput
            Output containing added_count and status.
        """
        # Batch size for processing (default 20 for reliability)
        batch_size = input.batch_size or 20

        wf_info = workflow.info()
        deleted_count = 0

        workflow.logger.info(
            "GraphRebuildWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "clean": input.clean,
                "batch_size": batch_size,
            },
        )

        # 0. Optionally reset graph first
        if input.clean:
            workflow.logger.info("Resetting global graph...")
            reset_result: ResetGlobalGraphOutput = await workflow.execute_activity(
                reset_global_graph,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            if not reset_result.success:
                workflow.logger.error(f"Failed to reset graph: {reset_result.error}")
                return GraphRebuildOutput(
                    status="error",
                    error=reset_result.error or "Failed to reset graph",
                )

            deleted_count = reset_result.deleted_count
            workflow.logger.info("Graph reset", extra={"deleted_count": deleted_count})

        # 1. Get first batch of entry IDs (entries with filtered_content)
        workflow.logger.info("Getting entry IDs...")
        ids_result: GetEntryIdsForIndexingOutput = await workflow.execute_activity(
            get_entry_ids_for_indexing,
            GetEntryIdsForIndexingInput(batch_size=batch_size),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        total_count = ids_result.total_count
        workflow.logger.info("Found entries to process", extra={"total_count": total_count})

        if total_count == 0:
            workflow.logger.info("No entries to process")
            return GraphRebuildOutput(
                status="completed",
                added_count=0,
                total_count=0,
                deleted_count=deleted_count,
            )

        # 2. Process entries in batches using cursor-based pagination
        added_count = 0
        skipped_count = 0
        batch_num = 0
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
                "Processing batch",
                extra={
                    "batch_num": batch_num,
                    "entries": len(ids_result.entry_ids),
                },
            )

            # Fetch and add entries to graph in a single activity
            # This avoids large payloads crossing the Temporal boundary
            bulk_result: FetchAndAddToGraphBulkOutput = await workflow.execute_activity(
                fetch_and_add_to_graph_bulk,
                FetchAndAddToGraphBulkInput(entry_ids=ids_result.entry_ids),
                start_to_close_timeout=timedelta(hours=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            added_count += bulk_result.success_count
            skipped_count += bulk_result.skipped_count
            workflow.logger.info(
                "Batch complete",
                extra={
                    "batch_num": batch_num,
                    "added": bulk_result.success_count,
                    "failed": bulk_result.failed_count,
                    "skipped": bulk_result.skipped_count,
                },
            )

            if bulk_result.error:
                workflow.logger.warning(
                    f"Batch error: {bulk_result.error}",
                    extra={"batch_num": batch_num},
                )

            if not ids_result.has_more:
                break

            cursor = ids_result.end_cursor

        workflow.logger.info(
            "GraphRebuildWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "added_count": added_count,
                "total_count": total_count,
                "skipped_count": skipped_count,
            },
        )

        return GraphRebuildOutput(
            status="completed",
            added_count=added_count,
            total_count=total_count,
            deleted_count=deleted_count,
        )
