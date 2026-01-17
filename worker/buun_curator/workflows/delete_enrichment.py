"""
Delete Enrichment Workflow.

Deletes an enrichment from the database via REST API.
Used when user clicks "X" button on an enrichment card in the Context Panel.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import delete_enrichment
    from buun_curator.models import (
        DeleteEnrichmentActivityInput,
        DeleteEnrichmentActivityOutput,
        DeleteEnrichmentInput,
        DeleteEnrichmentProgress,
        DeleteEnrichmentResult,
    )
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin


@workflow.defn
class DeleteEnrichmentWorkflow(ProgressNotificationMixin):
    """Workflow for deleting an enrichment from the database."""

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = DeleteEnrichmentProgress()

    @workflow.query
    def get_progress(self) -> DeleteEnrichmentProgress:
        """Return current workflow progress for Temporal Query."""
        return self._progress

    @workflow.run
    async def run(
        self,
        input: DeleteEnrichmentInput,
    ) -> DeleteEnrichmentResult:
        """
        Run the delete enrichment workflow.

        Parameters
        ----------
        input : DeleteEnrichmentInput
            Workflow input containing entry_id, type, and source to delete.

        Returns
        -------
        DeleteEnrichmentResult
            Result indicating whether the enrichment was deleted.
        """
        entry_id = input.entry_id
        enrichment_type = input.enrichment_type
        source = input.source

        wf_info = workflow.info()

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.entry_id = entry_id
        self._progress.enrichment_type = enrichment_type
        self._progress.source = source
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "deleting"
        self._progress.message = f"Deleting {enrichment_type} enrichment..."

        workflow.logger.info(
            "DeleteEnrichmentWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "entry_id": entry_id,
                "enrichment_type": enrichment_type,
                "source": source,
            },
        )

        await self._notify_update()

        try:
            result: DeleteEnrichmentActivityOutput = await workflow.execute_activity(
                delete_enrichment,
                DeleteEnrichmentActivityInput(
                    entry_id=entry_id,
                    enrichment_type=enrichment_type,
                    source=source,
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            if result.deleted:
                workflow.logger.info(
                    "DeleteEnrichmentWorkflow end (deleted)",
                    extra={
                        "workflow_id": wf_info.workflow_id,
                        "source": source,
                    },
                )
                self._progress.status = "completed"
                self._progress.message = "Enrichment deleted"
            else:
                workflow.logger.info(
                    "DeleteEnrichmentWorkflow end (not found)",
                    extra={
                        "workflow_id": wf_info.workflow_id,
                        "source": source,
                    },
                )
                self._progress.status = "completed"
                self._progress.message = "Enrichment not found"

            self._progress.current_step = "done"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()

            return DeleteEnrichmentResult(
                status="completed" if result.deleted else "not_found",
                deleted=result.deleted,
                error=result.error,
            )

        except Exception as e:
            error_msg = str(e)
            workflow.logger.error(
                f"Delete activity failed: {error_msg}",
                extra={"workflow_id": wf_info.workflow_id},
            )

            self._progress.status = "error"
            self._progress.error = error_msg
            self._progress.message = f"Failed: {error_msg}"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()

            return DeleteEnrichmentResult(
                status="error",
                deleted=False,
                error=error_msg,
            )
