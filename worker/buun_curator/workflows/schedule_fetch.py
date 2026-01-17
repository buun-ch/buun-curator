"""
Schedule Fetch Workflow.

Orchestrates content fetching with domain-based rate limiting.
Groups entries by domain and runs parallel child workflows for each domain.
Within each domain, requests are processed sequentially with delays.

Distillation is batched: as domains complete, entries are collected and
sent to ContentDistillationWorkflow in batches of 5 (fire-and-forget).
"""

import asyncio
import hashlib
from datetime import timedelta
from urllib.parse import urlparse

from temporalio import workflow
from temporalio.workflow import ParentClosePolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.models.workflow_io import (
        ContentDistillationInput,
        DomainFetchInput,
        DomainFetchOutput,
        ScheduleFetchInput,
        ScheduleFetchOutput,
        ScheduleFetchProgress,
    )
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.workflows.content_distillation import ContentDistillationWorkflow
    from buun_curator.workflows.domain_fetch import DomainFetchWorkflow
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin

# Batch size for distillation
DISTILL_BATCH_SIZE = 5


def _extract_domain(url: str) -> str:
    """
    Extract domain from URL for grouping.

    Parameters
    ----------
    url : str
        The URL to extract domain from.

    Returns
    -------
    str
        The domain (netloc) or "unknown" if parsing fails.
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc or "unknown"
    except Exception:
        return "unknown"


async def _group_entries_by_domain(entries: list[dict]) -> dict[str, list[dict]]:
    """
    Group entries by their URL domain.

    Yields control periodically to avoid Temporal deadlock detection.

    Parameters
    ----------
    entries : list[dict]
        List of entry dicts with url field.

    Returns
    -------
    dict[str, list[dict]]
        Domain -> list of entries mapping.
    """
    by_domain: dict[str, list[dict]] = {}
    for i, entry in enumerate(entries):
        url = entry.get("url", "")
        domain = _extract_domain(url)
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(entry)

        # Yield control periodically to avoid deadlock detection
        if (i + 1) % 100 == 0:
            await workflow.sleep(timedelta(seconds=0))

    return by_domain


def _is_youtube_url(url: str) -> bool:
    """
    Check if URL is a YouTube video URL.

    Parameters
    ----------
    url : str
        The URL to check.

    Returns
    -------
    bool
        True if the URL is a YouTube video URL.
    """
    domain = _extract_domain(url)
    return domain in ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com")


@workflow.defn
class ScheduleFetchWorkflow(ProgressNotificationMixin):
    """
    Workflow for scheduling content fetches with domain-based rate limiting.

    Groups entries by domain and processes each domain in parallel via child
    workflows. Within each domain, requests are sequential with configurable
    delays to avoid rate limiting.

    This approach ensures:
    - Different domains are fetched in parallel for efficiency
    - Same domain requests are spaced out to avoid rate limits
    - Works correctly across multiple Temporal workers
    """

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = ScheduleFetchProgress()

    @workflow.query
    def get_progress(self) -> ScheduleFetchProgress:
        """Return current workflow progress for Temporal Query."""
        return self._progress

    @workflow.run
    async def run(self, input: ScheduleFetchInput) -> ScheduleFetchOutput:
        """
        Run schedule fetch workflow.

        Parameters
        ----------
        input : ScheduleFetchInput
            Input containing entries and rate limit configuration.

        Returns
        -------
        ScheduleFetchOutput
            Aggregated results from all domain fetch workflows.
        """
        wf_info = workflow.info()
        entries = input.entries

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.parent_workflow_id = input.parent_workflow_id
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "init"
        self._progress.total_entries = len(entries)

        if not entries:
            workflow.logger.info("ScheduleFetchWorkflow: No entries to fetch")
            self._progress.status = "completed"
            self._progress.message = "No entries to fetch"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()
            return ScheduleFetchOutput()

        # Separate YouTube URLs (skip fetching)
        entries_to_fetch: list[dict] = []
        skipped_entries: list[dict] = []

        for i, entry in enumerate(entries):
            url = entry.get("url", "")
            metadata = entry.get("metadata") or {}
            if metadata.get("youtubeVideoId") or _is_youtube_url(url):
                skipped_entries.append(entry)
            else:
                entries_to_fetch.append(entry)

            # Yield control periodically to avoid deadlock detection
            if (i + 1) % 100 == 0:
                await workflow.sleep(timedelta(seconds=0))

        skipped_count = len(skipped_entries)
        self._progress.skipped_count = skipped_count
        if skipped_count > 0:
            workflow.logger.info("Skipping YouTube URLs", extra={"count": skipped_count})

        if not entries_to_fetch:
            workflow.logger.info("ScheduleFetchWorkflow: No non-YouTube entries to fetch")
            self._progress.status = "completed"
            self._progress.message = f"Skipped {skipped_count} YouTube URLs"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()
            return ScheduleFetchOutput(skipped_count=skipped_count)

        # Group entries by domain
        by_domain = await _group_entries_by_domain(entries_to_fetch)
        domain_count = len(by_domain)

        # Update progress
        self._progress.total_domains = domain_count
        self._progress.current_step = "fetch"
        self._progress.message = (
            f"Fetching {len(entries_to_fetch)} entries from {domain_count} domains"
        )
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        workflow.logger.info(
            "ScheduleFetchWorkflow start",
            extra={
                "entries": len(entries_to_fetch),
                "domains": domain_count,
                "delay_seconds": input.delay_seconds,
                "auto_distill": input.auto_distill,
            },
        )

        # Start child workflows for each domain (parallel)
        child_handles: list[tuple[str, workflow.ChildWorkflowHandle]] = []

        for i, (domain, domain_entries) in enumerate(by_domain.items()):
            # Create unique child workflow ID
            hash_input = f"{wf_info.workflow_id}:{wf_info.run_id}:{domain}"
            unique_suffix = hashlib.sha1(hash_input.encode()).hexdigest()[:7]
            child_wf_id = f"domain-fetch-{unique_suffix}"

            workflow.logger.info(
                "Starting DomainFetchWorkflow",
                extra={
                    "domain": domain,
                    "entries": len(domain_entries),
                    "child_workflow_id": child_wf_id,
                },
            )

            handle = await workflow.start_child_workflow(
                DomainFetchWorkflow.run,
                DomainFetchInput(
                    domain=domain,
                    entries=domain_entries,
                    delay_seconds=input.delay_seconds,
                    timeout=input.timeout,
                    enable_thumbnail=input.enable_thumbnail,
                    auto_distill=input.auto_distill,
                    target_language=input.target_language,
                    parent_workflow_id=wf_info.workflow_id,
                ),
                id=child_wf_id,
                execution_timeout=timedelta(minutes=30),
            )
            child_handles.append((domain, handle))

            # Yield control periodically to avoid deadlock detection
            if (i + 1) % 10 == 0:
                await workflow.sleep(timedelta(seconds=0))

        # Wait for child workflows using asyncio.wait with FIRST_COMPLETED
        # Start distillation as entries become available
        all_fetched_entry_ids: list[str] = []
        total_success = 0
        total_failed = 0
        total_distilled = 0
        distill_workflow_count = 0

        # Helper to wrap handle in awaitable coroutine for asyncio.wait
        async def await_handle(h: workflow.ChildWorkflowHandle) -> DomainFetchOutput:  # type: ignore[type-arg]
            return await h

        # Map task -> domain for tracking
        pending_tasks: dict[asyncio.Task[DomainFetchOutput], str] = {}
        for domain, handle in child_handles:
            # Wrap handle in a task for asyncio.wait compatibility
            task = asyncio.create_task(await_handle(handle))
            pending_tasks[task] = domain

        # Entries waiting to be distilled
        pending_entries: list[str] = []

        while pending_tasks:
            # Wait for at least one task to complete
            done, _ = await asyncio.wait(
                pending_tasks.keys(),
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                domain = pending_tasks.pop(task)
                try:
                    result: DomainFetchOutput = task.result()
                    workflow.logger.info(
                        "DomainFetchWorkflow completed",
                        extra={
                            "domain": domain,
                            "success_count": result.success_count,
                            "failed_count": result.failed_count,
                        },
                    )

                    total_success += result.success_count
                    total_failed += result.failed_count
                    all_fetched_entry_ids.extend(result.fetched_entry_ids)
                    pending_entries.extend(result.fetched_entry_ids)

                    # Update progress after each domain completes
                    self._progress.domains_completed += 1
                    self._progress.entries_fetched = total_success
                    self._progress.message = (
                        f"Completed {self._progress.domains_completed}/{domain_count} domains, "
                        f"{total_success} fetched"
                    )
                    self._progress.updated_at = workflow_now_iso()
                    await self._notify_update()

                except Exception as e:
                    workflow.logger.error(
                        f"DomainFetchWorkflow failed: {e}",
                        extra={"domain": domain},
                    )
                    # Count all entries in this domain as failed
                    domain_entries = by_domain.get(domain, [])
                    total_failed += len(domain_entries)
                    self._progress.domains_completed += 1
                    self._progress.updated_at = workflow_now_iso()
                    await self._notify_update()

            # Start distillation for batches of DISTILL_BATCH_SIZE entries
            if input.auto_distill:
                while len(pending_entries) >= DISTILL_BATCH_SIZE:
                    batch = pending_entries[:DISTILL_BATCH_SIZE]
                    pending_entries = pending_entries[DISTILL_BATCH_SIZE:]

                    # Create unique child workflow ID for distillation
                    hash_input = (
                        f"{wf_info.workflow_id}:{wf_info.run_id}:distill:{distill_workflow_count}"
                    )
                    unique_suffix = hashlib.sha1(hash_input.encode()).hexdigest()[:7]
                    distill_wf_id = f"content-distill-{unique_suffix}"

                    workflow.logger.info(
                        "Starting ContentDistillationWorkflow",
                        extra={
                            "entries": len(batch),
                            "distill_workflow_id": distill_wf_id,
                        },
                    )

                    # Fire-and-forget: start child workflow without waiting
                    # parent_workflow_id="" and show_toast=False to avoid orphan notifications
                    await workflow.start_child_workflow(
                        ContentDistillationWorkflow.run,
                        ContentDistillationInput(
                            entry_ids=batch,
                            parent_workflow_id="",
                            show_toast=False,
                        ),
                        id=distill_wf_id,
                        parent_close_policy=ParentClosePolicy.ABANDON,
                        execution_timeout=timedelta(minutes=30),
                    )
                    distill_workflow_count += 1
                    total_distilled += len(batch)
                    self._progress.entries_distilled = total_distilled
                    await self._notify_update()

        # Handle remaining entries (less than DISTILL_BATCH_SIZE)
        if input.auto_distill and pending_entries:
            hash_input = f"{wf_info.workflow_id}:{wf_info.run_id}:distill:{distill_workflow_count}"
            unique_suffix = hashlib.sha1(hash_input.encode()).hexdigest()[:7]
            distill_wf_id = f"content-distill-{unique_suffix}"

            workflow.logger.info(
                "Starting ContentDistillationWorkflow (remaining)",
                extra={
                    "entries": len(pending_entries),
                    "distill_workflow_id": distill_wf_id,
                },
            )

            # Fire-and-forget: parent_workflow_id="" and show_toast=False
            await workflow.start_child_workflow(
                ContentDistillationWorkflow.run,
                ContentDistillationInput(
                    entry_ids=pending_entries,
                    parent_workflow_id="",
                    show_toast=False,
                ),
                id=distill_wf_id,
                parent_close_policy=ParentClosePolicy.ABANDON,
                execution_timeout=timedelta(minutes=30),
            )
            total_distilled += len(pending_entries)
            self._progress.entries_distilled = total_distilled

        workflow.logger.info(
            "ScheduleFetchWorkflow end",
            extra={
                "success": total_success,
                "failed": total_failed,
                "distilled": total_distilled,
                "skipped": skipped_count,
                "domains": domain_count,
            },
        )

        # Update final progress
        self._progress.status = "completed"
        self._progress.current_step = "done"
        self._progress.entries_fetched = total_success
        self._progress.entries_distilled = total_distilled
        self._progress.message = (
            f"Completed: {total_success} fetched, {total_distilled} distilled, "
            f"{skipped_count} skipped"
        )
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        return ScheduleFetchOutput(
            fetched_entry_ids=all_fetched_entry_ids,
            success_count=total_success,
            failed_count=total_failed,
            skipped_count=skipped_count,
            domains_processed=domain_count,
            entries_distilled=total_distilled,
        )
