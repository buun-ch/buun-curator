"""
Domain Fetch Workflow.

Handles sequential fetching of entries for a single domain with rate limiting.
Ensures a delay between requests to the same domain to avoid rate limits.
Distillation is handled by ScheduleFetchWorkflow after all domains complete.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import fetch_single_content
    from buun_curator.models import (
        FetchSingleContentInput,
        FetchSingleContentOutput,
    )
    from buun_curator.models.workflow_io import (
        DomainFetchInput,
        DomainFetchOutput,
        DomainFetchProgress,
        EntryProgressState,
    )
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin


@workflow.defn
class DomainFetchWorkflow(ProgressNotificationMixin):
    """
    Workflow for fetching entries from a single domain sequentially.

    Ensures a configurable delay between requests to avoid rate limiting.
    Each entry is fetched one at a time with proper spacing.
    """

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = DomainFetchProgress()

    @workflow.query
    def get_progress(self) -> DomainFetchProgress:
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
    async def run(self, input: DomainFetchInput) -> DomainFetchOutput:
        """
        Run domain fetch workflow.

        Parameters
        ----------
        input : DomainFetchInput
            Input containing domain, entries, and delay configuration.

        Returns
        -------
        DomainFetchOutput
            Results of fetching all entries for this domain.
        """
        wf_info = workflow.info()
        domain = input.domain
        entries = input.entries
        delay_seconds = input.delay_seconds

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.domain = domain
        self._progress.parent_workflow_id = input.parent_workflow_id
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "fetch"
        self._progress.total_entries = len(entries)
        self._progress.message = f"Fetching {len(entries)} entries from {domain}"

        # Initialize entry progress for all entries
        for i, entry in enumerate(entries):
            entry_id = entry["entry_id"]
            title = entry.get("title", "")
            self._progress.entry_progress[entry_id] = EntryProgressState(
                entry_id=entry_id,
                title=title,
                status="pending",
                changed_at=now,
            )

            # Yield control periodically to avoid deadlock detection
            if (i + 1) % 100 == 0:
                await workflow.sleep(timedelta(seconds=0))

        await self._notify_update()

        workflow.logger.info(
            "DomainFetchWorkflow start",
            extra={
                "domain": domain,
                "entries": len(entries),
                "delay_seconds": delay_seconds,
            },
        )

        results: list[dict] = []
        success_count = 0
        failed_count = 0
        fetched_entry_ids: list[str] = []

        for i, entry in enumerate(entries):
            entry_id = entry["entry_id"]
            url = entry["url"]
            title = entry.get("title", "")
            extraction_rules = entry.get("extraction_rules")

            # Update progress for current entry
            title_short = title[:30] if title else ""
            self._progress.current_entry_index = i + 1
            self._progress.current_entry_title = title_short
            self._progress.current_step = "fetch"
            self._progress.message = f"Fetching [{i + 1}/{len(entries)}] {title_short}"
            self._update_entry_status(entry_id, "fetching")
            await self._notify_update()

            # Apply delay before subsequent requests (not before first)
            if i > 0:
                workflow.logger.debug(
                    "Waiting before next request",
                    extra={"delay_seconds": delay_seconds, "domain": domain},
                )
                await workflow.sleep(timedelta(seconds=delay_seconds))

            workflow.logger.info(
                "Fetching entry",
                extra={
                    "index": i + 1,
                    "total": len(entries),
                    "title": title_short,
                    "url": url,
                },
            )

            try:
                # Pass entry_id to save content directly to DB
                fetch_result: FetchSingleContentOutput = await workflow.execute_activity(
                    fetch_single_content,
                    FetchSingleContentInput(
                        url=url,
                        title=title,
                        timeout=input.timeout,
                        feed_extraction_rules=extraction_rules,
                        entry_id=entry_id,
                        enable_thumbnail=input.enable_thumbnail,
                    ),
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,
                        initial_interval=timedelta(seconds=5),
                    ),
                )

                if fetch_result.status == "success":
                    results.append(
                        {
                            "entry_id": entry_id,
                            "url": url,
                            "title": title,
                            "status": "success",
                            "content_length": fetch_result.content_length,
                        }
                    )
                    success_count += 1
                    fetched_entry_ids.append(entry_id)
                    workflow.logger.info(
                        "Fetched entry",
                        extra={
                            "entry_id": entry_id,
                            "content_length": fetch_result.content_length,
                        },
                    )

                    self._update_entry_status(entry_id, "fetched")

                    # Update progress after fetch
                    self._progress.entries_fetched = success_count
                    await self._notify_update()
                else:
                    results.append(
                        {
                            "entry_id": entry_id,
                            "url": url,
                            "title": title,
                            "status": fetch_result.status,
                            "error": fetch_result.error or "No content returned",
                        }
                    )
                    failed_count += 1
                    self._progress.entries_failed = failed_count
                    self._update_entry_status(entry_id, "error", fetch_result.error or "No content")
                    await self._notify_update()
                    workflow.logger.warning(
                        f"Fetch failed: {fetch_result.error or 'no content'}",
                        extra={"entry_id": entry_id},
                    )

            except Exception as e:
                error_msg = str(e)
                results.append(
                    {
                        "entry_id": entry_id,
                        "url": url,
                        "title": title,
                        "status": "failed",
                        "error": error_msg,
                    }
                )
                failed_count += 1
                self._progress.entries_failed = failed_count
                self._update_entry_status(entry_id, "error", error_msg)
                await self._notify_update()
                workflow.logger.error(
                    f"Failed to fetch entry: {error_msg}", extra={"entry_id": entry_id}
                )

        workflow.logger.info(
            "DomainFetchWorkflow end",
            extra={
                "domain": domain,
                "success_count": success_count,
                "failed_count": failed_count,
            },
        )

        # Update final progress
        self._progress.status = "completed"
        self._progress.current_step = "done"
        self._progress.entries_fetched = success_count
        self._progress.entries_failed = failed_count
        self._progress.message = f"Completed: {success_count} fetched, {failed_count} failed"
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        return DomainFetchOutput(
            domain=domain,
            results=results,
            success_count=success_count,
            failed_count=failed_count,
            fetched_entry_ids=fetched_entry_ids,
            entries_distilled=0,  # Distillation happens asynchronously
        )
