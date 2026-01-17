"""
All Feeds Ingestion Workflow.

Parent workflow that orchestrates ingestion of all feeds using child workflows.
Each feed is processed by a SingleFeedIngestionWorkflow child workflow.
"""

import asyncio
import hashlib
import math
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import get_app_settings, list_feeds
    from buun_curator.models import (
        AllFeedsIngestionInput,
        GetAppSettingsInput,
        GetAppSettingsOutput,
        ListFeedsInput,
        ListFeedsOutput,
    )
    from buun_curator.models.workflow_io import (
        AllFeedsIngestionProgress,
        AllFeedsIngestionResult,
        SingleFeedIngestionInput,
        SingleFeedIngestionResult,
    )
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin
    from buun_curator.workflows.single_feed_ingestion import SingleFeedIngestionWorkflow


@workflow.defn
class AllFeedsIngestionWorkflow(ProgressNotificationMixin):
    """
    Parent workflow for ingesting all feeds.

    Uses child workflows to process each feed independently, allowing for:
    - Parallel processing with configurable concurrency
    - Independent retries and timeouts per feed
    - Fault isolation between feeds
    - Better visibility in Temporal UI
    """

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = AllFeedsIngestionProgress()

    @workflow.query
    def get_progress(self) -> AllFeedsIngestionProgress:
        """Return current workflow progress for Temporal Query."""
        return self._progress

    @workflow.run
    async def run(
        self,
        _input: AllFeedsIngestionInput,
    ) -> AllFeedsIngestionResult:
        """
        Run all feeds ingestion workflow.

        All configuration is read from environment variables at runtime via
        the get_app_settings activity.

        Parameters
        ----------
        _input : AllFeedsIngestionInput
            Workflow input (empty, config is read from environment).

        Returns
        -------
        AllFeedsIngestionResult
            Aggregated result containing statistics from all feeds.
        """
        wf_info = workflow.info()

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "init"
        self._progress.message = "Initializing..."

        workflow.logger.info(
            "AllFeedsIngestionWorkflow start", extra={"workflow_id": wf_info.workflow_id}
        )
        await self._notify_update()

        # 1. Get app settings and workflow config from environment
        # All config values are read at runtime from environment variables
        settings_result: GetAppSettingsOutput = await workflow.execute_activity(
            get_app_settings,
            GetAppSettingsInput(),
            start_to_close_timeout=timedelta(minutes=1),
        )

        # Use config values from environment
        auto_distill = settings_result.auto_distill
        enable_content_fetch = settings_result.enable_content_fetch
        max_concurrent = settings_result.max_concurrent
        enable_thumbnail = settings_result.enable_thumbnail
        domain_fetch_delay = settings_result.domain_fetch_delay
        target_language = settings_result.target_language

        workflow.logger.info(
            "Options loaded",
            extra={
                "auto_distill": auto_distill,
                "enable_content_fetch": enable_content_fetch,
                "enable_thumbnail": enable_thumbnail,
                "max_concurrent": max_concurrent,
                "domain_fetch_delay": domain_fetch_delay,
                "target_language": target_language,
            },
        )

        # 2. List all feeds
        self._progress.current_step = "list"
        self._progress.message = "Listing feeds..."
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        feeds_result: ListFeedsOutput = await workflow.execute_activity(
            list_feeds,
            ListFeedsInput(),
            start_to_close_timeout=timedelta(minutes=2),
        )
        feeds = feeds_result.feeds
        total_feeds = len(feeds)

        workflow.logger.info("Found feeds to process", extra={"total_feeds": total_feeds})

        if not feeds:
            self._progress.status = "completed"
            self._progress.current_step = "done"
            self._progress.message = "No feeds to process"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()
            return AllFeedsIngestionResult(
                status="no_feeds",
                feeds_total=0,
            )

        # Update progress with feed count
        total_batches = math.ceil(total_feeds / max_concurrent)
        self._progress.feeds_total = total_feeds
        self._progress.total_batches = total_batches
        self._progress.current_step = "process"
        self._progress.message = f"Processing {total_feeds} feeds..."
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        # 3. Process feeds in batches with concurrency limit
        # Note: Temporal workflows require deterministic execution, so we use
        # batch processing instead of asyncio.Semaphore
        results: list[SingleFeedIngestionResult] = []

        for batch_start in range(0, total_feeds, max_concurrent):
            batch_end = min(batch_start + max_concurrent, total_feeds)
            batch_feeds = feeds[batch_start:batch_end]
            batch_names = [f["name"] for f in batch_feeds]
            batch_num = batch_start // max_concurrent + 1

            # Update progress for this batch
            self._progress.current_batch = batch_num
            self._progress.message = (
                f"Batch {batch_num}/{total_batches}: {', '.join(batch_names[:3])}"
                + ("..." if len(batch_names) > 3 else "")
            )
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()

            workflow.logger.info(
                "Processing batch",
                extra={
                    "batch_num": batch_num,
                    "total_batches": total_batches,
                    "feeds": batch_names,
                },
            )

            # Start all child workflows in this batch concurrently
            child_handles = []
            for i, feed in enumerate(batch_feeds):
                feed_id = feed["id"]
                feed_name = feed["name"]

                # Use unique child workflow ID with hash to avoid conflicts
                # between concurrent parent workflows (git-style short hash)
                hash_input = f"{wf_info.workflow_id}:{wf_info.run_id}:{feed_id}"
                unique_suffix = hashlib.sha1(hash_input.encode()).hexdigest()[:7]
                child_wf_id = f"single-feed-{feed_id}-{unique_suffix}"
                workflow.logger.info(
                    "Starting child workflow",
                    extra={"feed_name": feed_name, "child_workflow_id": child_wf_id},
                )
                # Use per-feed fetchContent option, falling back to workflow setting
                feed_fetch_content = feed.get("fetch_content", enable_content_fetch)
                handle = await workflow.start_child_workflow(
                    SingleFeedIngestionWorkflow.run,
                    SingleFeedIngestionInput(
                        feed_id=feed_id,
                        feed_name=feed_name,
                        feed_url=feed["url"],
                        etag=feed.get("etag", ""),
                        last_modified=feed.get("last_modified", ""),
                        fetch_limit=feed.get("fetch_limit", 20),
                        extraction_rules=feed.get("extraction_rules"),
                        auto_distill=auto_distill,
                        enable_content_fetch=feed_fetch_content,
                        enable_thumbnail=enable_thumbnail,
                        target_language=target_language,
                        domain_fetch_delay=domain_fetch_delay,
                        parent_workflow_id=wf_info.workflow_id,
                    ),
                    id=child_wf_id,
                )
                child_handles.append((feed_name, handle))

                # Yield control periodically to avoid deadlock detection
                if (i + 1) % 5 == 0:
                    await workflow.sleep(timedelta(seconds=0))

            # Wait for all child workflows in this batch to complete (parallel)
            # Create tasks for asyncio.wait compatibility
            async def await_handle(
                h: workflow.ChildWorkflowHandle,  # type: ignore[type-arg]
            ) -> SingleFeedIngestionResult:
                return await h

            pending_tasks: dict[asyncio.Task[SingleFeedIngestionResult], str] = {}
            for feed_name, handle in child_handles:
                task = asyncio.create_task(await_handle(handle))
                pending_tasks[task] = feed_name

            # Process results as they complete
            while pending_tasks:
                done, _ = await asyncio.wait(
                    pending_tasks.keys(),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    feed_name = pending_tasks.pop(task)
                    try:
                        result = task.result()
                        workflow.logger.info(
                            "Child workflow completed",
                            extra={"feed_name": feed_name, "status": result.status},
                        )
                        results.append(result)

                        # Update progress counters
                        self._progress.feeds_completed += 1
                        if result.status == "completed":
                            self._progress.feeds_processed += 1
                            self._progress.entries_created += result.entries_created
                            self._progress.contents_fetched += result.contents_fetched
                            self._progress.entries_distilled += result.entries_distilled
                        elif result.status == "skipped":
                            self._progress.feeds_skipped += 1
                        else:
                            self._progress.feeds_failed += 1

                        self._progress.updated_at = workflow_now_iso()
                        await self._notify_update()

                    except Exception as e:
                        workflow.logger.error(
                            f"Child workflow failed: {e}",
                            extra={"feed_name": feed_name},
                        )
                        # Create error result
                        results.append(
                            SingleFeedIngestionResult(
                                feed_id="",
                                feed_name=feed_name,
                                status="error",
                                error=str(e),
                            )
                        )
                        self._progress.feeds_completed += 1
                        self._progress.feeds_failed += 1
                        self._progress.updated_at = workflow_now_iso()
                        await self._notify_update()

        # 4. Aggregate results (already tracked in progress, just for return value)
        feeds_processed = self._progress.feeds_processed
        feeds_skipped = self._progress.feeds_skipped
        feeds_failed = self._progress.feeds_failed
        entries_created = self._progress.entries_created
        contents_fetched = self._progress.contents_fetched
        entries_distilled = self._progress.entries_distilled

        # Count skipped entries from results
        entries_skipped = sum(r.entries_skipped for r in results if r.status == "completed")

        workflow.logger.info(
            "AllFeedsIngestionWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "feeds_processed": feeds_processed,
                "feeds_skipped": feeds_skipped,
                "feeds_failed": feeds_failed,
                "entries_created": entries_created,
            },
        )

        # Update final progress state
        self._progress.status = "completed"
        self._progress.current_step = "done"
        self._progress.message = (
            f"Completed: {feeds_processed} feeds, "
            f"{entries_created} entries, {entries_distilled} distilled"
        )
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        return AllFeedsIngestionResult(
            status="completed",
            feeds_total=total_feeds,
            feeds_processed=feeds_processed,
            feeds_skipped=feeds_skipped,
            feeds_failed=feeds_failed,
            entries_created=entries_created,
            entries_skipped=entries_skipped,
            contents_fetched=contents_fetched,
            entries_distilled=entries_distilled,
        )
