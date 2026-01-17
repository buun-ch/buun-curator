"""
Entries Cleanup Workflow.

Workflow for deleting old entries that meet cleanup criteria.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities.cleanup import cleanup_old_entries
    from buun_curator.activities.search import remove_documents_from_index
    from buun_curator.models import (
        CleanupOldEntriesInput,
        CleanupOldEntriesOutput,
        RemoveDocumentsFromIndexInput,
        RemoveDocumentsFromIndexOutput,
    )
    from buun_curator.models.workflow_io import (
        EntriesCleanupInput,
        EntriesCleanupResult,
    )


@workflow.defn
class EntriesCleanupWorkflow:
    """
    Workflow for deleting old entries.

    Deletes entries that meet cleanup criteria:
    - isRead = true
    - isStarred = false
    - keep = false
    - publishedAt is older than the specified days
    """

    @workflow.run
    async def run(self, input: EntriesCleanupInput) -> EntriesCleanupResult:
        """
        Delete old entries that meet cleanup criteria.

        Parameters
        ----------
        input : EntriesCleanupInput
            Input containing older_than_days and dry_run options.

        Returns
        -------
        EntriesCleanupResult
            Output containing deleted_count and status.
        """
        wf_info = workflow.info()

        workflow.logger.info(
            "EntriesCleanupWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "older_than_days": input.older_than_days,
                "dry_run": input.dry_run,
            },
        )

        # Execute cleanup activity
        result: CleanupOldEntriesOutput = await workflow.execute_activity(
            cleanup_old_entries,
            CleanupOldEntriesInput(
                older_than_days=input.older_than_days,
                dry_run=input.dry_run,
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        if result.error:
            workflow.logger.error(f"Cleanup failed: {result.error}")
            return EntriesCleanupResult(
                status="error",
                error=result.error,
                older_than_days=input.older_than_days,
            )

        workflow.logger.info(
            "Deleted entries" if not input.dry_run else "Would delete entries",
            extra={
                "deleted_count": result.deleted_count,
                "cutoff_date": result.cutoff_date,
            },
        )

        # Remove deleted entries from search index (skip for dry run)
        search_removed_count = 0
        if not input.dry_run and result.deleted_ids:
            workflow.logger.info(
                "Removing entries from search index",
                extra={"entries": len(result.deleted_ids)},
            )

            # Remove in batches (Meilisearch can handle large batches)
            batch_size = 1000
            for i in range(0, len(result.deleted_ids), batch_size):
                batch = result.deleted_ids[i : i + batch_size]
                workflow.logger.debug(
                    "Removing batch",
                    extra={
                        "batch_num": i // batch_size + 1,
                        "documents": len(batch),
                    },
                )

                remove_result: RemoveDocumentsFromIndexOutput = (
                    await workflow.execute_activity(
                        remove_documents_from_index,
                        RemoveDocumentsFromIndexInput(document_ids=batch),
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RetryPolicy(maximum_attempts=3),
                    )
                )

                if remove_result.error:
                    workflow.logger.warning(
                        f"Search index removal error: {remove_result.error}",
                    )
                else:
                    search_removed_count += remove_result.removed_count

            workflow.logger.info(
                "Removed entries from search index",
                extra={"removed_count": search_removed_count},
            )

        workflow.logger.info(
            "EntriesCleanupWorkflow end",
            extra={"workflow_id": wf_info.workflow_id},
        )

        return EntriesCleanupResult(
            status="completed",
            deleted_count=result.deleted_count,
            older_than_days=result.older_than_days,
            cutoff_date=result.cutoff_date,
        )
