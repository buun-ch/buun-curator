"""
Content Distillation Workflow.

Standalone workflow for distilling entry content (filtering + summarization).
Can be called independently or as part of feed ingestion.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    import hashlib

    from buun_curator.activities import (
        compute_embeddings,
        distill_entry_content,
        get_app_settings,
        get_entries_for_distillation,
        save_distilled_entries,
    )
    from buun_curator.config import get_config
    from buun_curator.models import (
        ComputeEmbeddingsInput,
        ComputeEmbeddingsOutput,
        ContentDistillationProgress,
        DistillEntryContentInput,
        DistillEntryContentOutput,
        EntryProgressState,
        GetAppSettingsInput,
        GetAppSettingsOutput,
        GetEntriesForDistillationInput,
        GetEntriesForDistillationOutput,
        SaveDistilledEntriesInput,
        SaveDistilledEntriesOutput,
    )
    from buun_curator.models.workflow_io import (
        ContentDistillationInput,
        ContentDistillationResult,
        SummarizationEvaluationInput,
        SummarizationEvaluationItem,
    )
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.utils.trace import generate_entry_trace_id
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin


@workflow.defn
class ContentDistillationWorkflow(ProgressNotificationMixin):
    """
    Workflow for distilling entry content (filtering + summarization).

    Can be used:
    - Independently to distill specific entries
    - To batch distill all undistilled entries
    """

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = ContentDistillationProgress()

    @workflow.query
    def get_progress(self) -> ContentDistillationProgress:
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
        input: ContentDistillationInput,
    ) -> ContentDistillationResult:
        """
        Run the content distillation workflow.

        Parameters
        ----------
        input : ContentDistillationInput
            Workflow input containing entry IDs and options.

        Returns
        -------
        ContentDistillationResult
            Result containing workflow statistics.
        """
        # Extract input fields for convenience
        entry_ids = input.entry_ids
        batch_size = input.batch_size
        parent_workflow_id = input.parent_workflow_id
        show_toast = input.show_toast

        wf_info = workflow.info()

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.parent_workflow_id = parent_workflow_id
        self._progress.show_toast = show_toast
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "initializing"
        self._progress.message = "Starting content distillation..."

        workflow.logger.info(
            "ContentDistillationWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "entry_ids": len(entry_ids) if entry_ids else "auto",
                "batch_size": batch_size,
            },
        )

        # 0. Get app settings (target language)
        settings_result: GetAppSettingsOutput = await workflow.execute_activity(
            get_app_settings,
            GetAppSettingsInput(),
            start_to_close_timeout=timedelta(minutes=1),
        )
        target_language = settings_result.target_language
        workflow.logger.info("Target language", extra={"target_language": target_language})

        # 1. Get entries to distill
        get_result: GetEntriesForDistillationOutput = await workflow.execute_activity(
            get_entries_for_distillation,
            GetEntriesForDistillationInput(entry_ids=entry_ids),
            start_to_close_timeout=timedelta(minutes=2),
        )
        entries = get_result.entries

        if not entries:
            workflow.logger.info(
                "No entries to distill", extra={"workflow_id": wf_info.workflow_id}
            )

            self._progress.status = "completed"
            self._progress.current_step = "done"
            self._progress.message = "No entries to distill"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()

            return ContentDistillationResult(
                status="no_entries",
                total_entries=0,
                entries_distilled=0,
            )

        workflow.logger.info("Found entries to distill", extra={"entries": len(entries)})

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

        # 2. Distill entries
        self._progress.current_step = "distill"
        self._progress.message = f"Distilling {len(entries)} entries..."
        for entry_id in self._progress.entry_progress:
            self._update_entry_status(entry_id, "distilling")
        await self._notify_update()

        distill_result: DistillEntryContentOutput = await workflow.execute_activity(
            distill_entry_content,
            DistillEntryContentInput(
                entries=entries,
                batch_size=batch_size,
                target_language=target_language,
            ),
            start_to_close_timeout=timedelta(minutes=30),
            heartbeat_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=2,
                initial_interval=timedelta(seconds=10),
            ),
        )
        results = distill_result.results

        # 3. Save distilled entries
        entries_distilled = 0
        if results:
            save_result: SaveDistilledEntriesOutput = await workflow.execute_activity(
                save_distilled_entries,
                SaveDistilledEntriesInput(results=results),
                start_to_close_timeout=timedelta(minutes=2),
            )
            entries_distilled = save_result.saved_count

            # Mark distilled entries as completed
            distilled_ids = {r.get("entry_id") for r in results}
            for entry_id in self._progress.entry_progress:
                if entry_id in distilled_ids:
                    self._update_entry_status(entry_id, "completed")
                else:
                    self._update_entry_status(entry_id, "error")
            self._progress.entries_distilled = entries_distilled
            await self._notify_update()

            # 4. Compute embeddings for distilled entries
            distilled_entry_ids: list[str] = [
                str(r.get("entry_id")) for r in results if r.get("entry_id")
            ]
            if distilled_entry_ids:
                self._progress.current_step = "embedding"
                self._progress.message = (
                    f"Computing embeddings for {len(distilled_entry_ids)} entries..."
                )
                await self._notify_update()

                embedding_result: ComputeEmbeddingsOutput = await workflow.execute_activity(
                    compute_embeddings,
                    ComputeEmbeddingsInput(entry_ids=distilled_entry_ids),
                    start_to_close_timeout=timedelta(minutes=10),
                    heartbeat_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,
                        initial_interval=timedelta(seconds=5),
                    ),
                )
                workflow.logger.info(
                    "Computed embeddings",
                    extra={
                        "computed_count": embedding_result.computed_count,
                        "saved_count": embedding_result.saved_count,
                    },
                )
                if embedding_result.error:
                    workflow.logger.warning(
                        f"Embedding error: {embedding_result.error}",
                    )

            # 5. Start summarization evaluation (fire-and-forget)
            # Check if evaluation is enabled
            config = get_config()
            if config.ai_evaluation_enabled:
                # Get batch_trace_id from results (used for generating per-entry trace_ids)
                batch_trace_id = results[0].get("trace_id") if results else None
                if batch_trace_id:
                    # Build evaluation items with per-entry trace_ids
                    # Note: Only entry_id and trace_id are passed; content is fetched by activity
                    eval_items: list[SummarizationEvaluationItem] = []
                    workflow.logger.info("Building eval_items", extra={"results": len(results)})
                    for r in results:
                        entry_id = r.get("entry_id", "")
                        summary = r.get("summary", "")

                        if summary:
                            # Generate per-entry trace_id (same as ContentProcessor)
                            entry_trace_id = generate_entry_trace_id(entry_id, batch_trace_id)
                            eval_items.append(
                                SummarizationEvaluationItem(
                                    entry_id=entry_id,
                                    trace_id=entry_trace_id,
                                )
                            )
                        else:
                            workflow.logger.warning(
                                "Skipping eval: no summary",
                                extra={"entry_id": entry_id},
                            )

                    workflow.logger.info(
                        "Built eval_items",
                        extra={
                            "eval_items": len(eval_items),
                            "results": len(results),
                        },
                    )

                    if eval_items:
                        # Generate deterministic workflow ID using SHA1 hash
                        hash_input = f"{wf_info.workflow_id}:{wf_info.run_id}:{batch_trace_id}"
                        unique_suffix = hashlib.sha1(hash_input.encode()).hexdigest()[:8]
                        eval_workflow_id = f"summarize-eval-{unique_suffix}"
                        try:
                            await workflow.start_child_workflow(
                                "SummarizationEvaluationWorkflow",
                                SummarizationEvaluationInput(
                                    trace_id=batch_trace_id,  # Kept for backward compat
                                    items=eval_items,  # Each item has its own trace_id
                                    max_samples=5,
                                ),
                                id=eval_workflow_id,
                                parent_close_policy=workflow.ParentClosePolicy.ABANDON,
                            )
                            workflow.logger.info(
                                "Started summarization evaluation workflow",
                                extra={
                                    "eval_workflow_id": eval_workflow_id,
                                    "items": len(eval_items),
                                },
                            )
                        except Exception as e:
                            # Evaluation failure should not fail the main workflow
                            workflow.logger.warning(
                                f"Failed to start summarization evaluation: {e}"
                            )

        workflow.logger.info(
            "ContentDistillationWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "entries_distilled": entries_distilled,
                "total_entries": len(entries),
            },
        )

        # Update final progress state
        self._progress.status = "completed"
        self._progress.current_step = "done"
        self._progress.message = f"Completed: {entries_distilled} entries distilled"
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        return ContentDistillationResult(
            status="completed",
            total_entries=len(entries),
            entries_distilled=entries_distilled,
        )
