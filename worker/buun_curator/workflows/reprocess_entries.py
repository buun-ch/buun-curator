"""
Reprocess Entries Workflow.

Reprocesses existing entries: fetch content and/or summarize.
Used for refetching content or regenerating summaries for specific entries.
Delegates distillation to ContentDistillationWorkflow for code reuse.
"""

import hashlib
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import (
        fetch_contents,
        get_entries,
    )
    from buun_curator.models import (
        EntryProgressState,
        FetchContentsInput,
        FetchContentsOutput,
        GetEntriesInput,
        GetEntriesOutput,
        ReprocessEntriesInput,
        ReprocessEntriesProgress,
    )
    from buun_curator.models.workflow_io import (
        ContentDistillationInput,
        ContentDistillationResult,
        ReprocessEntriesResult,
    )
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.workflows.content_distillation import ContentDistillationWorkflow
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin


@workflow.defn
class ReprocessEntriesWorkflow(ProgressNotificationMixin):
    """Workflow for reprocessing existing entries: fetch content -> summarize."""

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = ReprocessEntriesProgress()

    @workflow.query
    def get_progress(self) -> ReprocessEntriesProgress:
        """Return current workflow progress for Temporal Query."""
        return self._progress

    def _update_entry_status(self, entry_id: str, status: str, error: str = "") -> None:
        """Update status for a specific entry."""
        now = workflow_now_iso()
        if entry_id in self._progress.entry_progress:
            self._progress.entry_progress[entry_id].status = status
            self._progress.entry_progress[entry_id].changed_at = now
            if error:
                self._progress.entry_progress[entry_id].error = error
        self._progress.updated_at = now

    @workflow.run
    async def run(
        self,
        input: ReprocessEntriesInput,
    ) -> ReprocessEntriesResult:
        """
        Run the reprocess entries workflow.

        Parameters
        ----------
        input : ReprocessEntriesInput
            Workflow input containing entry IDs and options.

        Returns
        -------
        ReprocessEntriesResult
            Result containing workflow statistics.
        """
        # Extract input fields for convenience
        entry_ids = input.entry_ids
        fetch_content = input.fetch_content
        summarize = input.summarize

        wf_info = workflow.info()

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "initializing"
        self._progress.message = "Starting workflow..."

        workflow.logger.info(
            "ReprocessEntriesWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "entry_ids": len(entry_ids) if entry_ids else 0,
                "fetch_content": fetch_content,
                "summarize": summarize,
            },
        )

        if not entry_ids:
            workflow.logger.info(
                "No entry IDs provided",
                extra={"workflow_id": wf_info.workflow_id},
            )
            return ReprocessEntriesResult(status="no_entries")

        # 1. Get entry details from MCP
        get_result: GetEntriesOutput = await workflow.execute_activity(
            get_entries,
            GetEntriesInput(entry_ids=entry_ids),
            start_to_close_timeout=timedelta(minutes=2),
        )
        entries = get_result.entries

        if not entries:
            workflow.logger.warning(
                "No entries found for the given IDs",
                extra={"workflow_id": wf_info.workflow_id},
            )
            return ReprocessEntriesResult(
                status="no_entries_found",
                entries_processed=0,
            )

        workflow.logger.info("Found entries to process", extra={"entries": len(entries)})

        # Initialize entry progress tracking
        now = workflow_now_iso()
        self._progress.total_entries = len(entries)
        for entry in entries:
            entry_id = entry.get("entry_id", "")
            title = entry.get("title", "")
            self._progress.entry_progress[entry_id] = EntryProgressState(
                entry_id=entry_id,
                title=title,
                status="pending",
                changed_at=now,
            )
        self._progress.updated_at = now
        await self._notify_update()

        # 2. Fetch content (saved to DB within activity)
        contents_fetched = 0
        contents: dict[str, dict] = {}

        if fetch_content:
            workflow.logger.info("Fetching content", extra={"entries": len(entries)})

            # Update progress: mark all entries as fetching
            self._progress.current_step = "fetch"
            self._progress.message = f"Fetching content for {len(entries)} entries..."
            for entry in entries:
                self._update_entry_status(entry.get("entry_id", ""), "fetching")
            await self._notify_update()

            fetch_result: FetchContentsOutput = await workflow.execute_activity(
                fetch_contents,
                FetchContentsInput(entries=entries),
                start_to_close_timeout=timedelta(minutes=15),
                heartbeat_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            # Contents are saved to DB within the activity
            contents = fetch_result.contents_for_summarize
            contents_fetched = fetch_result.success_count
            workflow.logger.info(
                "Fetched and saved content", extra={"contents_fetched": contents_fetched}
            )

            # Update progress: mark fetched entries
            self._progress.entries_fetched = contents_fetched
            self._progress.message = f"Fetched content for {contents_fetched} entries"
            for entry_id in contents:
                self._update_entry_status(entry_id, "fetched")
            await self._notify_update()

        # 3. Distill via ContentDistillationWorkflow (waits for completion)
        entries_distilled = 0

        if summarize:
            # Update progress: distilling
            self._progress.current_step = "distill"
            self._progress.message = "Starting content distillation..."
            for entry in entries:
                self._update_entry_status(entry.get("entry_id", ""), "distilling")
            await self._notify_update()

            # Create unique child workflow ID
            hash_input = f"{wf_info.workflow_id}:{wf_info.run_id}:distill"
            unique_suffix = hashlib.sha1(hash_input.encode()).hexdigest()[:7]
            distill_wf_id = f"distill-reprocess-{unique_suffix}"

            workflow.logger.info(
                "Starting ContentDistillationWorkflow",
                extra={"distill_workflow_id": distill_wf_id},
            )

            # Execute child workflow and wait for completion
            distill_result: ContentDistillationResult = await workflow.execute_child_workflow(
                ContentDistillationWorkflow.run,
                ContentDistillationInput(
                    entry_ids=entry_ids,
                    parent_workflow_id=wf_info.workflow_id,
                ),
                id=distill_wf_id,
                execution_timeout=timedelta(minutes=30),
            )

            entries_distilled = distill_result.entries_distilled
            workflow.logger.info(
                "ContentDistillationWorkflow completed",
                extra={"entries_distilled": entries_distilled},
            )

            # Update progress: mark entries as completed
            self._progress.entries_distilled = entries_distilled
            self._progress.message = f"Distilled {entries_distilled} entries"
            for entry in entries:
                self._update_entry_status(entry.get("entry_id", ""), "completed")
            await self._notify_update()

        workflow.logger.info(
            "ReprocessEntriesWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "entries_processed": len(entries),
                "contents_fetched": contents_fetched,
                "entries_distilled": entries_distilled,
            },
        )

        # Update final progress state
        self._progress.status = "completed"
        self._progress.current_step = "done"
        self._progress.message = (
            f"Completed: {contents_fetched} fetched, {entries_distilled} distilled"
        )
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()  # Always notify on completion

        return ReprocessEntriesResult(
            status="completed",
            entries_processed=len(entries),
            contents_fetched=contents_fetched,
            entries_distilled=entries_distilled,
            entry_details=[
                {"entry_id": e["entry_id"], "title": e.get("title", "")} for e in entries
            ],
        )
