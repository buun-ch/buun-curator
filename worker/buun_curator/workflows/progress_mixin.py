"""
Progress notification mixin for Temporal workflows.

Provides SSE update notifications to the frontend.
Throttling is handled inside the notify_update activity (per workflow ID).
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Protocol

from temporalio import workflow

if TYPE_CHECKING:
    from buun_curator.models import WorkflowProgress

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import NotifyProgressInput, notify_progress


class HasProgress(Protocol):
    """Protocol for workflows that have a get_progress method."""

    def get_progress(self) -> "WorkflowProgress":
        """Return current workflow progress."""
        ...


class ProgressNotificationMixin:
    """
    Mixin providing SSE notification functionality for workflows.

    Usage
    -----
    1. Inherit from this mixin: `class MyWorkflow(ProgressNotificationMixin):`
    2. Define `get_progress()` method decorated with `@workflow.query`
    3. Call `await self._notify_update()` to send notifications

    Throttling is handled inside the notify_update activity to ensure
    deterministic workflow execution.
    """

    async def _notify_update(self: "HasProgress") -> None:
        """
        Send progress update notification via SSE (fire-and-forget).

        Calls self.get_progress() to get current progress and sends it
        directly to the frontend via HTTP POST.

        Throttling is handled inside the activity (per workflow ID).
        """
        try:
            progress = self.get_progress()
            await workflow.execute_local_activity(
                notify_progress,
                NotifyProgressInput(
                    workflow_id=workflow.info().workflow_id,
                    progress=progress.model_dump(by_alias=True),
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )
        except Exception as e:
            workflow.logger.warning(f"Failed to send progress notification: {e}")
