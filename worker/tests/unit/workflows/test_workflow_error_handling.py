"""
Tests for workflow error handling.

Verifies that workflows properly notify via SSE before failing when activities raise exceptions.
"""

from datetime import timedelta

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import (
    SandboxedWorkflowRunner,
    SandboxRestrictions,
)

from buun_curator.activities.notify import NotifyOutput, NotifyProgressInput
from buun_curator.models import (
    ComputeEmbeddingsInput,
    ComputeEmbeddingsOutput,
    ContentDistillationProgress,
    DistillEntryContentInput,
    DistillEntryContentOutput,
    GetAppSettingsInput,
    GetAppSettingsOutput,
    GetEntriesForDistillationInput,
    GetEntriesForDistillationOutput,
    SaveDistilledEntriesInput,
    SaveDistilledEntriesOutput,
)
from buun_curator.models.workflow_io import (
    ContentDistillationInput,
)
from buun_curator.workflows.content_distillation import ContentDistillationWorkflow


@pytest.fixture
def sandbox_runner() -> SandboxedWorkflowRunner:
    """Create a sandboxed workflow runner with Pydantic passthrough modules."""
    return SandboxedWorkflowRunner(
        restrictions=SandboxRestrictions.default.with_passthrough_modules(
            "annotated_types",
            "pydantic_core",
            "pydantic_core._pydantic_core",
            "pydantic_core.core_schema",
        )
    )


@pytest.fixture
def sample_entries() -> list[dict]:
    """Create sample entries for testing."""
    return [
        {
            "entry_id": "entry-1",
            "title": "Test Entry 1",
            "url": "https://example.com/1",
            "content": "Test content 1",
        },
        {
            "entry_id": "entry-2",
            "title": "Test Entry 2",
            "url": "https://example.com/2",
            "content": "Test content 2",
        },
    ]


@pytest.mark.asyncio
async def test_distill_activity_failure_notifies_sse(
    sample_entries: list[dict],
    sandbox_runner: SandboxedWorkflowRunner,
    required_env_vars: None,
) -> None:
    """
    Test that workflow notifies SSE before failing when distill activity fails.

    Verifies:
    1. Workflow raises WorkflowFailureError when activity fails
    2. _notify_update() is called with error status before raising
    3. Entry progress is set to "error" for all entries
    """
    # Track progress notifications
    progress_snapshots: list[ContentDistillationProgress] = []

    @activity.defn(name="get_app_settings")
    async def mock_get_app_settings(
        _input: GetAppSettingsInput,
    ) -> GetAppSettingsOutput:
        return GetAppSettingsOutput(
            auto_distill=True,
            enable_content_fetch=True,
            max_concurrent=5,
            enable_thumbnail=False,
            domain_fetch_delay=1,
            target_language="ja",
        )

    @activity.defn(name="get_entries_for_distillation")
    async def mock_get_entries(
        _input: GetEntriesForDistillationInput,
    ) -> GetEntriesForDistillationOutput:
        return GetEntriesForDistillationOutput(entries=sample_entries)

    @activity.defn(name="distill_entry_content")
    async def mock_distill_entry_content(
        _input: DistillEntryContentInput,
    ) -> DistillEntryContentOutput:
        # Simulate activity failure (e.g., LLM context window exceeded)
        raise RuntimeError(
            "ContextWindowExceededError: model's maximum context length is 4096 tokens"
        )

    @activity.defn(name="notify_progress")
    async def mock_notify(notify_input: NotifyProgressInput) -> NotifyOutput:
        # Capture progress snapshots for verification
        if "entryProgress" in notify_input.progress:
            progress_snapshots.append(ContentDistillationProgress(**notify_input.progress))
        return NotifyOutput(success=True)

    async with (
        await WorkflowEnvironment.start_time_skipping(
            data_converter=pydantic_data_converter,
        ) as env,
        Worker(
            env.client,
            task_queue="test-queue",
            workflow_runner=sandbox_runner,
            workflows=[ContentDistillationWorkflow],
            activities=[
                mock_get_app_settings,
                mock_get_entries,
                mock_distill_entry_content,
                mock_notify,
            ],
        ),
    ):
        # Execute workflow and expect it to fail
        with pytest.raises(WorkflowFailureError) as exc_info:
            await env.client.execute_workflow(
                ContentDistillationWorkflow.run,
                ContentDistillationInput(entry_ids=["entry-1", "entry-2"]),
                id="test-distill-error",
                task_queue="test-queue",
                execution_timeout=timedelta(minutes=5),
            )

        # Verify the workflow failed with expected error
        # The cause chain contains ActivityError -> ApplicationError with message
        cause = exc_info.value.cause
        assert cause is not None, "WorkflowFailureError should have a cause"
        # Check the full error chain for the expected message
        error_str = str(cause)
        # Check error chain for expected message (may be nested)
        cause_str = str(getattr(cause, "cause", "")) if hasattr(cause, "cause") else ""
        assert "ContextWindowExceededError" in error_str or (
            "ContextWindowExceededError" in cause_str
        ), f"Expected ContextWindowExceededError in cause chain, got: {error_str}"

        # Verify SSE notification was sent with error status
        assert len(progress_snapshots) > 0, "No progress notifications captured"

        # Find the error notification (last one should be error)
        error_notification = next(
            (p for p in reversed(progress_snapshots) if p.status == "error"),
            None,
        )
        assert error_notification is not None, "No error notification found"

        # Verify error message is present (Temporal wraps exceptions, so
        # the original message may not be directly visible)
        assert error_notification.error, "Error message should be set"
        assert error_notification.message, "Error message in progress should be set"
        assert "failed" in error_notification.message.lower(), (
            f"Expected 'failed' in message, got: {error_notification.message}"
        )

        # Verify all entries are marked as error
        for entry_id, entry_progress in error_notification.entry_progress.items():
            assert entry_progress.status == "error", f"Entry {entry_id} should be marked as error"
            assert entry_progress.error, f"Entry {entry_id} should have an error message"


@pytest.mark.asyncio
async def test_workflow_completes_successfully_on_no_error(
    sample_entries: list[dict],
    sandbox_runner: SandboxedWorkflowRunner,
    required_env_vars: None,
) -> None:
    """
    Test that workflow completes successfully when no errors occur.

    Verifies normal flow still works after adding error handling.
    """
    progress_snapshots: list[ContentDistillationProgress] = []

    @activity.defn(name="get_app_settings")
    async def mock_get_app_settings(
        _input: GetAppSettingsInput,
    ) -> GetAppSettingsOutput:
        return GetAppSettingsOutput(
            auto_distill=True,
            enable_content_fetch=True,
            max_concurrent=5,
            enable_thumbnail=False,
            domain_fetch_delay=1,
            target_language="ja",
        )

    @activity.defn(name="get_entries_for_distillation")
    async def mock_get_entries(
        _input: GetEntriesForDistillationInput,
    ) -> GetEntriesForDistillationOutput:
        return GetEntriesForDistillationOutput(entries=sample_entries)

    @activity.defn(name="distill_entry_content")
    async def mock_distill_entry_content(
        _input: DistillEntryContentInput,
    ) -> DistillEntryContentOutput:
        # Return successful results
        return DistillEntryContentOutput(
            results=[
                {
                    "entry_id": "entry-1",
                    "summary": "Summary 1",
                    "trace_id": "trace-1",
                },
                {
                    "entry_id": "entry-2",
                    "summary": "Summary 2",
                    "trace_id": "trace-2",
                },
            ]
        )

    @activity.defn(name="save_distilled_entries")
    async def mock_save_distilled(
        _input: SaveDistilledEntriesInput,
    ) -> SaveDistilledEntriesOutput:
        return SaveDistilledEntriesOutput(saved_count=2)

    @activity.defn(name="compute_embeddings")
    async def mock_compute_embeddings(
        _input: ComputeEmbeddingsInput,
    ) -> ComputeEmbeddingsOutput:
        return ComputeEmbeddingsOutput(computed_count=2, saved_count=2, error=None)

    @activity.defn(name="notify_progress")
    async def mock_notify(notify_input: NotifyProgressInput) -> NotifyOutput:
        if "entryProgress" in notify_input.progress:
            progress_snapshots.append(ContentDistillationProgress(**notify_input.progress))
        return NotifyOutput(success=True)

    async with (
        await WorkflowEnvironment.start_time_skipping(
            data_converter=pydantic_data_converter,
        ) as env,
        Worker(
            env.client,
            task_queue="test-queue",
            workflow_runner=sandbox_runner,
            workflows=[ContentDistillationWorkflow],
            activities=[
                mock_get_app_settings,
                mock_get_entries,
                mock_distill_entry_content,
                mock_save_distilled,
                mock_compute_embeddings,
                mock_notify,
            ],
        ),
    ):
        # Execute workflow - should complete successfully
        result = await env.client.execute_workflow(
            ContentDistillationWorkflow.run,
            ContentDistillationInput(entry_ids=["entry-1", "entry-2"]),
            id="test-distill-success",
            task_queue="test-queue",
            execution_timeout=timedelta(minutes=5),
        )

        # Verify successful completion
        assert result.status == "completed"
        assert result.entries_distilled == 2

        # Verify final progress notification shows completed
        assert len(progress_snapshots) > 0
        final_progress = progress_snapshots[-1]
        assert final_progress.status == "completed"


@pytest.mark.asyncio
async def test_no_entries_returns_early_without_error(
    sandbox_runner: SandboxedWorkflowRunner,
    required_env_vars: None,
) -> None:
    """
    Test that workflow returns early when no entries to distill.

    This should not trigger error handling.
    """
    progress_snapshots: list[ContentDistillationProgress] = []

    @activity.defn(name="get_app_settings")
    async def mock_get_app_settings(
        _input: GetAppSettingsInput,
    ) -> GetAppSettingsOutput:
        return GetAppSettingsOutput(
            auto_distill=True,
            enable_content_fetch=True,
            max_concurrent=5,
            enable_thumbnail=False,
            domain_fetch_delay=1,
            target_language="ja",
        )

    @activity.defn(name="get_entries_for_distillation")
    async def mock_get_entries(
        _input: GetEntriesForDistillationInput,
    ) -> GetEntriesForDistillationOutput:
        # Return empty list
        return GetEntriesForDistillationOutput(entries=[])

    @activity.defn(name="notify_progress")
    async def mock_notify(notify_input: NotifyProgressInput) -> NotifyOutput:
        if "entryProgress" in notify_input.progress:
            progress_snapshots.append(ContentDistillationProgress(**notify_input.progress))
        return NotifyOutput(success=True)

    async with (
        await WorkflowEnvironment.start_time_skipping(
            data_converter=pydantic_data_converter,
        ) as env,
        Worker(
            env.client,
            task_queue="test-queue",
            workflow_runner=sandbox_runner,
            workflows=[ContentDistillationWorkflow],
            activities=[
                mock_get_app_settings,
                mock_get_entries,
                mock_notify,
            ],
        ),
    ):
        # Execute workflow - should complete with no_entries
        result = await env.client.execute_workflow(
            ContentDistillationWorkflow.run,
            ContentDistillationInput(entry_ids=None),
            id="test-distill-no-entries",
            task_queue="test-queue",
            execution_timeout=timedelta(minutes=5),
        )

        # Verify it returns no_entries status (not error)
        assert result.status == "no_entries"
        assert result.total_entries == 0
