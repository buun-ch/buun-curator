"""
Single Feed Ingestion Workflow.

Handles ingestion of a single feed: crawl -> fetch -> summarize.
Designed to be called as a child workflow from AllFeedsIngestionWorkflow.
Distillation is started in fire-and-forget mode for background processing.
"""

import hashlib
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.workflow import ParentClosePolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import (
        crawl_single_feed,
        fetch_single_content,
        get_app_settings,
        get_feed_options,
    )
    from buun_curator.models import (
        CrawlSingleFeedInput,
        CrawlSingleFeedOutput,
        FetchSingleContentInput,
        FetchSingleContentOutput,
        GetAppSettingsInput,
        GetAppSettingsOutput,
        GetFeedOptionsInput,
        GetFeedOptionsOutput,
        SingleFeedIngestionProgress,
    )
    from buun_curator.models.workflow_io import (
        ContentDistillationInput,
        ScheduleFetchInput,
        ScheduleFetchOutput,
        SingleFeedIngestionInput,
        SingleFeedIngestionResult,
    )
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.workflows.content_distillation import ContentDistillationWorkflow
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin
    from buun_curator.workflows.schedule_fetch import ScheduleFetchWorkflow


@workflow.defn
class SingleFeedIngestionWorkflow(ProgressNotificationMixin):
    """Workflow for ingesting a single feed: crawl -> fetch -> summarize."""

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = SingleFeedIngestionProgress()

    @workflow.query
    def get_progress(self) -> SingleFeedIngestionProgress:
        """Return current workflow progress for Temporal Query."""
        return self._progress

    @workflow.run
    async def run(self, input: SingleFeedIngestionInput) -> SingleFeedIngestionResult:
        """
        Run single feed ingestion workflow.

        Parameters
        ----------
        input : SingleFeedIngestionInput
            Input containing feed details and processing options.

        Returns
        -------
        SingleFeedIngestionResult
            Result containing workflow statistics for this feed.
        """
        feed_id = input.feed_id
        feed_name = input.feed_name
        wf_info = workflow.info()

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.feed_id = feed_id
        self._progress.feed_name = feed_name
        self._progress.parent_workflow_id = input.parent_workflow_id
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "crawl"
        self._progress.message = f"Crawling {feed_name}..."

        workflow.logger.info(
            "SingleFeedIngestionWorkflow start",
            extra={"workflow_id": wf_info.workflow_id, "feed_id": feed_id, "feed_name": feed_name},
        )
        await self._notify_update()

        try:
            return await self._run_ingestion(input)
        except Exception as e:
            # Send error notification via SSE before failing the workflow
            error_msg = str(e)
            self._progress.status = "error"
            self._progress.error = error_msg
            self._progress.message = f"Ingestion failed: {error_msg}"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()
            raise

    async def _run_ingestion(self, input: SingleFeedIngestionInput) -> SingleFeedIngestionResult:
        """
        Run the main ingestion logic.

        Separated from run() to enable top-level error handling with SSE notification.
        """
        feed_id = input.feed_id
        feed_name = input.feed_name
        wf_info = workflow.info()

        # 0. Fetch feed options from API (to get accurate fetch_limit)
        # This ensures we always use the correct fetch_limit from the database
        feed_options: GetFeedOptionsOutput = await workflow.execute_activity(
            get_feed_options,
            GetFeedOptionsInput(feed_id=feed_id),
            start_to_close_timeout=timedelta(minutes=1),
        )
        fetch_limit = feed_options.fetch_limit
        extraction_rules = feed_options.extraction_rules
        workflow.logger.debug("Feed options", extra={"fetch_limit": fetch_limit})

        # 1. Crawl the feed
        crawl_result: CrawlSingleFeedOutput = await workflow.execute_activity(
            crawl_single_feed,
            CrawlSingleFeedInput(
                feed_id=feed_id,
                feed_name=feed_name,
                feed_url=input.feed_url,
                etag=input.etag,
                last_modified=input.last_modified,
                fetch_limit=fetch_limit,
                extraction_rules=extraction_rules,
                max_entry_age_days=input.max_entry_age_days,
            ),
            start_to_close_timeout=timedelta(minutes=10),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=5),
            ),
        )

        if crawl_result.status == "error":
            workflow.logger.error(
                f"Crawl failed: {crawl_result.error}",
                extra={"workflow_id": wf_info.workflow_id, "feed_name": feed_name},
            )
            self._progress.status = "error"
            self._progress.error = crawl_result.error or "Unknown error"
            self._progress.message = f"Crawl failed: {crawl_result.error}"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()
            return SingleFeedIngestionResult(
                feed_id=feed_id,
                feed_name=feed_name,
                status="error",
                error=crawl_result.error,
            )

        if crawl_result.status == "skipped":
            workflow.logger.info(
                "Feed not modified, skipping",
                extra={"workflow_id": wf_info.workflow_id, "feed_name": feed_name},
            )
            self._progress.status = "completed"
            self._progress.current_step = "done"
            self._progress.message = "Feed not modified, skipped"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()
            return SingleFeedIngestionResult(
                feed_id=feed_id,
                feed_name=feed_name,
                status="skipped",
            )

        new_entries = crawl_result.new_entries
        if not new_entries:
            workflow.logger.info(
                "No new entries",
                extra={"workflow_id": wf_info.workflow_id, "feed_name": feed_name},
            )
            self._progress.status = "completed"
            self._progress.current_step = "done"
            self._progress.entries_skipped = crawl_result.entries_skipped
            self._progress.message = "No new entries"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()
            return SingleFeedIngestionResult(
                feed_id=feed_id,
                feed_name=feed_name,
                status="completed",
                entries_created=0,
                entries_skipped=crawl_result.entries_skipped,
            )

        workflow.logger.info(
            "Crawl completed",
            extra={"feed_name": feed_name, "entries_created": crawl_result.entries_created},
        )

        # Update progress: crawl completed
        self._progress.entries_created = crawl_result.entries_created
        self._progress.entries_skipped = crawl_result.entries_skipped
        self._progress.message = f"Crawled {crawl_result.entries_created} new entries"
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        # Get target language from app settings if not provided (needed for distillation)
        target_language = input.target_language
        if input.auto_distill and not target_language:
            settings_result: GetAppSettingsOutput = await workflow.execute_activity(
                get_app_settings,
                GetAppSettingsInput(),
                start_to_close_timeout=timedelta(minutes=1),
            )
            target_language = settings_result.target_language or ""
            workflow.logger.info(
                "Target language from settings", extra={"target_language": target_language}
            )

        # Update progress: total entries
        self._progress.total_entries = len(new_entries)
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        # 2. Fetch content for new entries (or process feed_content if fetch disabled)
        contents_fetched = 0
        fetched_entry_ids: list[str] = []

        # Update progress: fetch step
        self._progress.current_step = "fetch"
        self._progress.message = f"Fetching content for {len(new_entries)} entries..."
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        if input.enable_content_fetch:
            # URL fetch mode: use ScheduleFetchWorkflow for domain-based rate limiting
            workflow.logger.info(
                "Fetching content",
                extra={"feed_name": feed_name, "entries": len(new_entries)},
            )

            # Create unique child workflow ID for fetch scheduling
            hash_input = f"{wf_info.workflow_id}:{wf_info.run_id}:fetch"
            unique_suffix = hashlib.sha1(hash_input.encode()).hexdigest()[:7]
            fetch_wf_id = f"schedule-fetch-{feed_id}-{unique_suffix}"

            fetch_result: ScheduleFetchOutput = await workflow.execute_child_workflow(
                ScheduleFetchWorkflow.run,
                ScheduleFetchInput(
                    entries=new_entries,
                    delay_seconds=input.domain_fetch_delay,
                    enable_thumbnail=input.enable_thumbnail,
                    auto_distill=input.auto_distill,
                    target_language=target_language,
                    parent_workflow_id=wf_info.workflow_id,
                    distillation_batch_size=input.distillation_batch_size,
                ),
                id=fetch_wf_id,
                execution_timeout=timedelta(minutes=30),
            )
            fetched_entry_ids = fetch_result.fetched_entry_ids
            contents_fetched = fetch_result.success_count
            # Note: entries_distilled from ScheduleFetch is always 0 now (fire-and-forget)
            workflow.logger.info(
                "Fetched content",
                extra={"feed_name": feed_name, "contents_fetched": contents_fetched},
            )

        else:
            # HTML processing mode: process feed_content for each entry
            workflow.logger.info(
                "Processing feed_content (content fetch disabled)",
                extra={"feed_name": feed_name, "entries": len(new_entries)},
            )

            for entry in new_entries:
                entry_id = entry.get("entry_id", "")
                feed_content = entry.get("feed_content", "")
                title = entry.get("title", "")

                if not entry_id or not feed_content:
                    workflow.logger.debug(
                        "Skipping entry: no feed_content", extra={"entry_id": entry_id}
                    )
                    continue

                try:
                    result: FetchSingleContentOutput = await workflow.execute_activity(
                        fetch_single_content,
                        FetchSingleContentInput(
                            url=entry.get("url", ""),  # For logging only
                            title=title,
                            entry_id=entry_id,
                            html_content=feed_content,
                        ),
                        start_to_close_timeout=timedelta(minutes=2),
                        retry_policy=RetryPolicy(maximum_attempts=2),
                    )

                    if result.status == "success":
                        fetched_entry_ids.append(entry_id)
                        contents_fetched += 1

                        # Start ContentDistillationWorkflow in fire-and-forget mode
                        if input.auto_distill:
                            hash_input = f"{wf_info.workflow_id}:{entry_id}:distill"
                            unique_suffix = hashlib.sha1(hash_input.encode()).hexdigest()[:7]
                            distill_wf_id = f"distill-{entry_id[:8]}-{unique_suffix}"

                            # Fire-and-forget: parent_workflow_id="" and show_toast=False
                            await workflow.start_child_workflow(
                                ContentDistillationWorkflow.run,
                                ContentDistillationInput(
                                    entry_ids=[entry_id],
                                    batch_size=input.distillation_batch_size,
                                    parent_workflow_id="",
                                    show_toast=False,
                                ),
                                id=distill_wf_id,
                                parent_close_policy=ParentClosePolicy.ABANDON,
                                execution_timeout=timedelta(minutes=10),
                            )
                            workflow.logger.info(
                                "Started ContentDistillationWorkflow (fire-and-forget)",
                                extra={"entry_id": entry_id, "distill_workflow_id": distill_wf_id},
                            )

                except Exception as e:
                    workflow.logger.warning(
                        f"Failed to process feed_content: {e}",
                        extra={"entry_id": entry_id},
                    )

            workflow.logger.info(
                "Processed feed_content",
                extra={"feed_name": feed_name, "contents_fetched": contents_fetched},
            )

        # Update progress: fetch completed (distillation runs in background)
        self._progress.contents_fetched = contents_fetched
        self._progress.message = f"Fetched {contents_fetched} entries"
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        workflow.logger.info(
            "SingleFeedIngestionWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "feed_name": feed_name,
                "entries_created": crawl_result.entries_created,
                "contents_fetched": contents_fetched,
            },
        )

        # Update final progress state
        self._progress.status = "completed"
        self._progress.current_step = "done"
        self._progress.message = (
            f"Completed: {crawl_result.entries_created} entries, {contents_fetched} fetched"
        )
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        return SingleFeedIngestionResult(
            feed_id=feed_id,
            feed_name=feed_name,
            status="completed",
            entries_created=crawl_result.entries_created,
            entries_skipped=crawl_result.entries_skipped,
            contents_fetched=contents_fetched,
            entries_distilled=0,  # Distillation happens asynchronously
            new_entries=new_entries,
        )
