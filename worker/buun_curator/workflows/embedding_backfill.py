"""
Embedding Backfill Workflow.

Computes embeddings for entries that have content but no embedding.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import (
        compute_embeddings,
        get_entries_for_embedding,
    )
    from buun_curator.models import (
        ComputeEmbeddingsInput,
        ComputeEmbeddingsOutput,
        GetEntriesForEmbeddingInput,
        GetEntriesForEmbeddingOutput,
    )
    from buun_curator.models.workflow_io import (
        EmbeddingBackfillInput,
        EmbeddingBackfillResult,
    )


@workflow.defn
class EmbeddingBackfillWorkflow:
    """
    Workflow for backfilling embeddings.

    Fetches entries that have content but no embedding,
    computes embeddings in batches, and saves them.
    """

    @workflow.run
    async def run(self, input: EmbeddingBackfillInput) -> EmbeddingBackfillResult:
        """
        Run the embedding backfill workflow.

        Parameters
        ----------
        input : EmbeddingBackfillInput
            Workflow input containing batch size.

        Returns
        -------
        EmbeddingBackfillResult
            Result containing statistics.
        """
        wf_info = workflow.info()
        workflow.logger.info(
            "EmbeddingBackfillWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "batch_size": input.batch_size,
            },
        )

        total_count = 0
        computed_count = 0
        saved_count = 0
        cursor: str | None = None

        # Process entries in batches
        while True:
            # 1. Get entries that need embeddings
            get_result: GetEntriesForEmbeddingOutput = await workflow.execute_activity(
                get_entries_for_embedding,
                GetEntriesForEmbeddingInput(
                    batch_size=input.batch_size,
                    after=cursor,
                ),
                start_to_close_timeout=timedelta(minutes=2),
            )

            if not get_result.entry_ids:
                workflow.logger.info("No more entries to process")
                break

            # Update total count on first iteration
            if cursor is None:
                total_count = get_result.total_count
                workflow.logger.info("Total entries to process", extra={"total_count": total_count})

            workflow.logger.info(
                "Processing batch",
                extra={
                    "batch_size": len(get_result.entry_ids),
                    "cursor": cursor,
                },
            )

            # 2. Compute embeddings for this batch
            embedding_result: ComputeEmbeddingsOutput = await workflow.execute_activity(
                compute_embeddings,
                ComputeEmbeddingsInput(entry_ids=get_result.entry_ids),
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=5),
                ),
            )

            computed_count += embedding_result.computed_count
            saved_count += embedding_result.saved_count

            workflow.logger.info(
                "Batch complete",
                extra={
                    "computed": embedding_result.computed_count,
                    "saved": embedding_result.saved_count,
                },
            )

            if embedding_result.error:
                workflow.logger.warning(f"Batch error: {embedding_result.error}")

            # Check if there are more entries
            if not get_result.has_more:
                workflow.logger.info("No more entries")
                break

            cursor = get_result.end_cursor

        workflow.logger.info(
            "EmbeddingBackfillWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "total_count": total_count,
                "computed_count": computed_count,
                "saved_count": saved_count,
            },
        )

        return EmbeddingBackfillResult(
            status="completed",
            total_count=total_count,
            computed_count=computed_count,
            saved_count=saved_count,
        )
