"""
Update Entry Index Workflow.

Simple workflow for updating a single entry in the Meilisearch index.
Designed to be called from the frontend as fire-and-forget.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities.search import update_entry_index
    from buun_curator.models import (
        UpdateEntryIndexInput as ActivityInput,
    )
    from buun_curator.models import (
        UpdateEntryIndexOutput as ActivityOutput,
    )
    from buun_curator.models.workflow_io import (
        UpdateEntryIndexInput,
        UpdateEntryIndexOutput,
    )


@workflow.defn
class UpdateEntryIndexWorkflow:
    """Workflow for updating a single entry in the Meilisearch index."""

    @workflow.run
    async def run(self, input: UpdateEntryIndexInput) -> UpdateEntryIndexOutput:
        """
        Update a single entry in the Meilisearch index.

        Parameters
        ----------
        input : UpdateEntryIndexInput
            Input containing entry_id to update.

        Returns
        -------
        UpdateEntryIndexOutput
            Output containing success status.
        """
        workflow.logger.info(
            "UpdateEntryIndexWorkflow start",
            extra={"entry_id": str(input.entry_id)},
        )

        result: ActivityOutput = await workflow.execute_activity(
            update_entry_index,
            ActivityInput(entry_id=input.entry_id),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        if result.error:
            workflow.logger.error(
                "UpdateEntryIndexWorkflow failed",
                extra={"entry_id": str(input.entry_id), "error": result.error},
            )
            return UpdateEntryIndexOutput(
                status="error",
                success=False,
                error=result.error,
            )

        workflow.logger.info(
            "UpdateEntryIndexWorkflow completed",
            extra={"entry_id": str(input.entry_id)},
        )

        return UpdateEntryIndexOutput(
            status="completed",
            success=True,
        )
