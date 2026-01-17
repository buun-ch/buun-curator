"""
Search Prune Workflow.

Workflow for removing orphaned documents from the Meilisearch index.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities.search import (
        get_orphaned_document_ids,
        remove_documents_from_index,
    )
    from buun_curator.models import (
        GetOrphanedDocumentIdsInput,
        GetOrphanedDocumentIdsOutput,
        RemoveDocumentsFromIndexInput,
        RemoveDocumentsFromIndexOutput,
    )
    from buun_curator.models.workflow_io import (
        SearchPruneInput,
        SearchPruneOutput,
    )


@workflow.defn
class SearchPruneWorkflow:
    """Workflow for removing orphaned documents from Meilisearch."""

    @workflow.run
    async def run(self, input: SearchPruneInput) -> SearchPruneOutput:
        """
        Remove orphaned documents from the Meilisearch index.

        Finds documents in Meilisearch that don't exist in the database
        and removes them.

        Parameters
        ----------
        input : SearchPruneInput
            Input containing batch_size option.

        Returns
        -------
        SearchPruneOutput
            Output containing removed_count and status.
        """
        wf_info = workflow.info()

        workflow.logger.info(
            "SearchPruneWorkflow start",
            extra={"workflow_id": wf_info.workflow_id},
        )

        # 1. Find orphaned document IDs
        workflow.logger.info("Finding orphaned documents...")
        orphaned_result: GetOrphanedDocumentIdsOutput = await workflow.execute_activity(
            get_orphaned_document_ids,
            GetOrphanedDocumentIdsInput(batch_size=input.batch_size),
            start_to_close_timeout=timedelta(minutes=10),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        if orphaned_result.error:
            workflow.logger.error(f"Failed to find orphaned documents: {orphaned_result.error}")
            return SearchPruneOutput(
                status="error",
                error=orphaned_result.error,
            )

        total_in_index = orphaned_result.total_in_index
        total_in_db = orphaned_result.total_in_db
        orphaned_ids = orphaned_result.orphaned_ids

        workflow.logger.info(
            "Orphan check complete",
            extra={
                "total_in_index": total_in_index,
                "total_in_db": total_in_db,
                "orphaned": len(orphaned_ids),
            },
        )

        if not orphaned_ids:
            workflow.logger.info("No orphaned documents to remove")
            return SearchPruneOutput(
                status="completed",
                removed_count=0,
                total_in_index=total_in_index,
                total_in_db=total_in_db,
            )

        # 2. Remove orphaned documents in batches
        removed_count = 0
        batch_size = 1000  # Meilisearch can handle large batches for deletion

        for i in range(0, len(orphaned_ids), batch_size):
            batch = orphaned_ids[i : i + batch_size]
            workflow.logger.info(
                "Removing batch",
                extra={"batch_num": i // batch_size + 1, "documents": len(batch)},
            )

            remove_result: RemoveDocumentsFromIndexOutput = await workflow.execute_activity(
                remove_documents_from_index,
                RemoveDocumentsFromIndexInput(document_ids=batch),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            if remove_result.error:
                workflow.logger.warning(f"Batch removal error: {remove_result.error}")
            else:
                removed_count += remove_result.removed_count

        workflow.logger.info(
            "SearchPruneWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "removed_count": removed_count,
            },
        )

        return SearchPruneOutput(
            status="completed",
            removed_count=removed_count,
            total_in_index=total_in_index,
            total_in_db=total_in_db,
        )
