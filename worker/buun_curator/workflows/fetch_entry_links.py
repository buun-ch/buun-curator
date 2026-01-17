"""
Fetch Entry Links Workflow.

Fetches content from URLs and saves them as entry enrichments.
Used when user clicks "+" button on a link in the Context Panel.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import fetch_and_save_entry_links
    from buun_curator.models import (
        FetchAndSaveLinksInput,
        FetchAndSaveLinksOutput,
        FetchEntryLinksInput,
        FetchEntryLinksProgress,
        FetchEntryLinksResult,
        UrlProgressState,
    )
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin


@workflow.defn
class FetchEntryLinksWorkflow(ProgressNotificationMixin):
    """Workflow for fetching content from URLs and saving as entry enrichments."""

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = FetchEntryLinksProgress()

    @workflow.query
    def get_progress(self) -> FetchEntryLinksProgress:
        """Return current workflow progress for Temporal Query."""
        return self._progress

    def _update_url_status(self, url: str, status: str, title: str = "", error: str = "") -> None:
        """Update status for a specific URL."""
        now = workflow_now_iso()
        if url in self._progress.url_progress:
            self._progress.url_progress[url].status = status
            self._progress.url_progress[url].changed_at = now
            if title:
                self._progress.url_progress[url].title = title
            if error:
                self._progress.url_progress[url].error = error
        self._progress.updated_at = now

    @workflow.run
    async def run(
        self,
        input: FetchEntryLinksInput,
    ) -> FetchEntryLinksResult:
        """
        Run the fetch entry links workflow.

        Parameters
        ----------
        input : FetchEntryLinksInput
            Workflow input containing entry_id and URLs to fetch.

        Returns
        -------
        FetchEntryLinksResult
            Result containing fetch statistics.
        """
        entry_id = input.entry_id
        urls = input.urls
        timeout = input.timeout

        wf_info = workflow.info()

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.entry_id = entry_id
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "initializing"
        self._progress.message = "Starting workflow..."
        self._progress.total_urls = len(urls)

        workflow.logger.info(
            "FetchEntryLinksWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "entry_id": entry_id,
                "urls": len(urls),
                "timeout": timeout,
            },
        )

        if not urls:
            workflow.logger.info(
                "FetchEntryLinksWorkflow end",
                extra={"workflow_id": wf_info.workflow_id, "reason": "no_urls"},
            )
            self._progress.status = "completed"
            self._progress.message = "No URLs to fetch"
            await self._notify_update()
            return FetchEntryLinksResult(status="no_urls")

        # Initialize URL progress tracking
        for url in urls:
            self._progress.url_progress[url] = UrlProgressState(
                url=url,
                status="pending",
                changed_at=now,
            )
        await self._notify_update()

        # Execute the fetch activity
        self._progress.current_step = "fetching"
        self._progress.message = f"Fetching {len(urls)} URLs..."

        # Mark all URLs as fetching
        for url in urls:
            self._update_url_status(url, "fetching")
        await self._notify_update()

        try:
            fetch_result: FetchAndSaveLinksOutput = await workflow.execute_activity(
                fetch_and_save_entry_links,
                FetchAndSaveLinksInput(
                    entry_id=entry_id,
                    urls=urls,
                    timeout=timeout,
                ),
                start_to_close_timeout=timedelta(minutes=len(urls) * 2 + 5),
                heartbeat_timeout=timedelta(seconds=90),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            # Update URL progress based on results
            self._progress.processed_urls = len(fetch_result.results)
            for result in fetch_result.results:
                if result.success:
                    self._update_url_status(
                        result.url,
                        "completed",
                        title=result.title,
                    )
                else:
                    self._update_url_status(
                        result.url,
                        "error",
                        error=result.error or "Unknown error",
                    )

            fetched_count = fetch_result.success_count
            failed_count = fetch_result.failed_count

            workflow.logger.info(
                "Fetch results",
                extra={"fetched_count": fetched_count, "failed_count": failed_count},
            )

        except Exception as e:
            error_msg = str(e)
            workflow.logger.error(f"Fetch activity failed: {error_msg}")

            # Mark all pending URLs as error
            for url in urls:
                if self._progress.url_progress.get(url, UrlProgressState()).status == "fetching":
                    self._update_url_status(url, "error", error=error_msg)

            self._progress.status = "failed"
            self._progress.error = error_msg
            self._progress.message = f"Failed: {error_msg}"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()

            workflow.logger.info(
                "FetchEntryLinksWorkflow end",
                extra={"workflow_id": wf_info.workflow_id, "status": "failed"},
            )

            return FetchEntryLinksResult(
                status="failed",
                fetched_count=0,
                failed_count=len(urls),
            )

        workflow.logger.info(
            "FetchEntryLinksWorkflow end",
            extra={"workflow_id": wf_info.workflow_id, "status": "completed"},
        )

        # Determine final status
        if failed_count == 0:
            status = "completed"
        elif fetched_count == 0:
            status = "failed"
        else:
            status = "partial"

        # Update final progress state
        self._progress.status = "completed"
        self._progress.current_step = "done"
        self._progress.message = f"Completed: {fetched_count} fetched, {failed_count} failed"
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        return FetchEntryLinksResult(
            status=status,
            fetched_count=fetched_count,
            failed_count=failed_count,
        )
