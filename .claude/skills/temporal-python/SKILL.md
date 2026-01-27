---
name: temporal-python
description: Develop Temporal Workflows and Activities in Python following project conventions and Temporal best practices. Use when creating, modifying, or debugging Temporal workflows/activities in the worker/ directory.
---

# Temporal Python Development

This skill provides guidance for developing Temporal Workflows and Activities in this project's Python worker (`worker/`).

## Project Structure

```text
worker/
├── buun_curator/
│   ├── workflows/           # Workflow definitions
│   │   ├── __init__.py      # Exports all workflows
│   │   ├── progress_mixin.py # SSE notification mixin
│   │   └── *.py             # Individual workflow files
│   ├── activities/          # Activity definitions
│   │   ├── __init__.py      # Exports all activities
│   │   └── *.py             # Individual activity files
│   ├── services/            # Business logic (called by activities)
│   ├── models/
│   │   ├── base.py          # CamelCaseModel base class
│   │   ├── workflow_io.py   # Workflow Input/Output models
│   │   ├── activity_io.py   # Activity Input/Output models
│   │   └── sse_events.py    # SSE progress models
│   ├── temporal.py          # Temporal client configuration
│   └── worker.py            # Worker entry point
└── tests/
    ├── activities/          # Activity unit tests
    ├── services/            # Service unit tests
    └── integration/         # Integration tests
```

## Data Models: Pydantic

**CRITICAL:** All Temporal I/O uses Pydantic models. This ensures proper serialization and validation.

### Model Selection

| Context      | Model Type       | Reason                         |
| :----------- | :--------------- | :----------------------------- |
| Workflow I/O | `CamelCaseModel` | camelCase for Next.js frontend |
| Activity I/O | `BaseModel`      | Internal to worker, validation |
| SSE/API      | `CamelCaseModel` | camelCase for external APIs    |
| LLM output   | `BaseModel`      | LangChain structured output    |

### CamelCaseModel (Workflow I/O)

```python
# models/base.py
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class CamelCaseModel(BaseModel):
    """Base model with camelCase JSON serialization."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

# models/workflow_io.py
from buun_curator.models.base import CamelCaseModel

class SingleFeedIngestionInput(CamelCaseModel):
    """Input for SingleFeedIngestionWorkflow."""
    feed_id: str                    # → "feedId" in JSON
    enable_content_fetch: bool = True
    # New fields at end for backward compatibility
    parent_workflow_id: str = ""
```

### BaseModel (Activity I/O)

```python
# models/activity_io.py
from pydantic import BaseModel, Field

class FetchContentsInput(BaseModel):
    """Input for fetch_contents activity."""
    entries: list[dict]
    timeout: int = 60

class FetchContentsOutput(BaseModel):
    """Output from fetch_contents activity."""
    contents_for_distill: dict[str, dict] = Field(default_factory=dict)
    success_count: int = 0
    failed_count: int = 0
```

## Workflow Definition

### Input/Output Convention

**IMPORTANT:** Workflow `run` methods MUST take a single Pydantic model argument.

- Define Input/Output models in `models/workflow_io.py`
- Use `CamelCaseModel` for camelCase JSON serialization
- This ensures proper serialization and forward compatibility (add new fields at end with defaults)

```python
# models/workflow_io.py
from buun_curator.models.base import CamelCaseModel

class MyWorkflowInput(CamelCaseModel):
    """Input for MyWorkflow."""
    required_field: str
    optional_field: str = ""

class MyWorkflowResult(CamelCaseModel):
    """Result of MyWorkflow."""
    status: str
    processed_count: int = 0
```

### Basic Structure

```python
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import inside unsafe block for sandbox compatibility
with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import my_activity
    from buun_curator.models import MyInput, MyOutput, MyProgress
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin

@workflow.defn
class MyWorkflow(ProgressNotificationMixin):
    """Workflow description."""

    def __init__(self) -> None:
        """Initialize workflow state."""
        self._progress = MyProgress()

    @workflow.query
    def get_progress(self) -> MyProgress:
        """Return current progress for Temporal Query."""
        return self._progress

    @workflow.run
    async def run(self, input: MyInput) -> MyOutput:
        """
        Run the workflow.

        Parameters
        ----------
        input : MyInput
            Workflow input.

        Returns
        -------
        MyOutput
            Workflow result.
        """
        wf_info = workflow.info()
        workflow.logger.info(
            "Workflow started",
            extra={"workflow_id": wf_info.workflow_id},
        )

        # Execute activity
        result = await workflow.execute_activity(
            my_activity,
            MyActivityInput(data=input.data),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )

        return MyOutput(status="completed", result=result)
```

### Determinism Rules

**Workflow code MUST be deterministic.** Never use:

- `datetime.now()` → Use `workflow.now()`
- `random.random()` → Use `workflow.random()`
- `uuid.uuid4()` → Use deterministic ID generation
- Network I/O → Call activities instead
- Global state mutation
- Threading

```python
# utils/date.py
from temporalio import workflow

def workflow_now_iso() -> str:
    """Get current UTC timestamp (deterministic)."""
    return workflow.now().isoformat()
```

### Child Workflows

```python
from temporalio.workflow import ParentClosePolicy

# Fire-and-forget (parent doesn't wait)
await workflow.start_child_workflow(
    ContentDistillationWorkflow.run,
    ContentDistillationInput(entry_ids=entry_ids),
    id=f"distill-{workflow.info().workflow_id}",
    parent_close_policy=ParentClosePolicy.ABANDON,
)

# Wait for completion
result = await workflow.execute_child_workflow(
    ChildWorkflow.run,
    ChildInput(data=data),
    id=f"child-{workflow.info().workflow_id}",
)
```

### Error Handling

```python
@workflow.run
async def run(self, input: MyInput) -> MyOutput:
    try:
        return await self._run_workflow(input)
    except Exception as e:
        # Update progress for SSE notification
        self._progress.status = "error"
        self._progress.error = str(e)
        await self._notify_update(force=True)
        raise  # Re-raise to mark workflow as failed
```

## Activity Definition

### Basic Structure

```python
from temporalio import activity

from buun_curator.logging import get_logger
from buun_curator.models import MyActivityInput, MyActivityOutput

logger = get_logger(__name__)

@activity.defn
async def my_activity(input: MyActivityInput) -> MyActivityOutput:
    """
    Activity description.

    Parameters
    ----------
    input : MyActivityInput
        Activity input.

    Returns
    -------
    MyActivityOutput
        Activity result.
    """
    # structlog-style keyword arguments
    logger.info("Processing", entry_id=input.entry_id)

    # Business logic here (can use await, network I/O, etc.)
    result = await do_something(input.data)

    return MyActivityOutput(result=result)
```

### Heartbeats (Long-running Activities)

```python
@activity.defn
async def long_running_activity(input: LongRunningInput) -> LongRunningOutput:
    """Activity with heartbeat for long operations."""
    for i, item in enumerate(input.items):
        # Report progress
        activity.heartbeat(f"Processing item {i+1}/{len(input.items)}")

        await process_item(item)

    return LongRunningOutput(processed=len(input.items))
```

### Local Activities (Fast, No Retry)

```python
# Use for quick operations that don't need full activity features
result = await workflow.execute_local_activity(
    notify_update,
    NotifyInput(workflow_id=wf_info.workflow_id),
    start_to_close_timeout=timedelta(seconds=10),
)
```

## Logging

### Workflow Logging (Inside Sandbox)

```python
# workflow.logger is a standard Python logger
# Does NOT support keyword arguments → use extra={}
workflow.logger.info(
    "Processing started",
    extra={"workflow_id": wf_info.workflow_id, "count": 10},
)
```

### Activity/Service Logging (Outside Sandbox)

```python
from buun_curator.logging import get_logger

logger = get_logger(__name__)

# structlog-style keyword arguments
logger.info("Processing entry", entry_id=entry_id, count=10)
```

### JSON Output

Both styles produce identical JSON output:

```json
{
  "event": "Processing started",
  "workflow_id": "wf-123",
  "count": 10,
  "level": "info",
  "component": "worker",
  "timestamp": "2026-01-15T10:30:00.000000Z"
}
```

## Progress and SSE Notifications

### Progress Model

```python
# models/sse_events.py
from buun_curator.models.base import CamelCaseModel

class WorkflowProgress(CamelCaseModel):
    """Base progress model for all workflows."""
    workflow_id: str = ""
    workflow_type: str = ""
    status: str = "pending"  # pending, running, completed, error
    current_step: str = ""
    message: str = ""
    started_at: str = ""
    updated_at: str = ""
    error: str | None = None
    parent_workflow_id: str = ""  # For child workflow hierarchy

class MyWorkflowProgress(WorkflowProgress):
    """Progress for MyWorkflow."""
    workflow_type: str = "MyWorkflow"
    total_items: int = 0
    processed_items: int = 0
```

### ProgressNotificationMixin

```python
# workflows/progress_mixin.py
class ProgressNotificationMixin:
    """Mixin for SSE progress notifications."""

    _NOTIFY_THROTTLE_SECONDS = 0.3  # Prevent notification floods

    async def _notify_update(self, force: bool = False) -> None:
        """Send progress update via SSE."""
        now = workflow.now().timestamp()
        if not force and (now - self._last_notify_time) < self._NOTIFY_THROTTLE_SECONDS:
            return
        self._last_notify_time = now

        await workflow.execute_local_activity(
            notify_update,
            NotifyUpdateInput(workflow_id=workflow.info().workflow_id),
            start_to_close_timeout=timedelta(seconds=10),
        )
```

## Testing

### Running Tests

```bash
cd worker

# All tests
uv run pytest

# Unit tests only (fast)
uv run pytest -m "not integration"

# Integration tests only
uv run pytest -m integration

# Specific file
uv run pytest tests/activities/test_fetch.py -v
```

### Activity Unit Test

```python
import pytest
from unittest.mock import AsyncMock, patch

from buun_curator.activities import my_activity
from buun_curator.models import MyActivityInput

@pytest.mark.asyncio
async def test_my_activity():
    """Test my_activity with mocked dependencies."""
    input = MyActivityInput(entry_id="test-123")

    with patch("buun_curator.activities.my_activity.external_service") as mock:
        mock.fetch.return_value = {"data": "test"}

        result = await my_activity(input)

    assert result.success is True
    mock.fetch.assert_called_once()
```

### Workflow Test with Time-Skipping

```python
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from buun_curator.workflows import MyWorkflow
from buun_curator.activities import my_activity
from buun_curator.models import MyInput

@pytest.mark.asyncio
async def test_my_workflow():
    """Test workflow with time-skipping."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[MyWorkflow],
            activities=[my_activity],
        ):
            result = await env.client.execute_workflow(
                MyWorkflow.run,
                MyInput(data="test"),
                id="test-workflow",
                task_queue="test-queue",
            )

    assert result.status == "completed"
```

## Code Quality

After writing or modifying Python code:

```bash
cd worker
uv run ruff check .   # Linting
uv run ruff format .  # Formatting
uv run pyright        # Type checking
```

## Common Patterns

### Batch Processing with Concurrency

```python
import asyncio

async def _process_in_batches(self, items: list, batch_size: int = 5) -> list:
    """Process items in batches with limited concurrency."""
    results = []

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]

        # Start child workflows for batch
        handles = []
        for item in batch:
            handle = await workflow.start_child_workflow(
                ItemWorkflow.run,
                ItemInput(item_id=item.id),
                id=f"item-{item.id}",
            )
            handles.append(handle)

        # Wait for batch to complete
        batch_results = await asyncio.gather(*[h.result() for h in handles])
        results.extend(batch_results)

        # Update progress
        self._progress.processed = len(results)
        await self._notify_update()

    return results
```

### Process as Completed (FIRST_COMPLETED)

Use `asyncio.wait(FIRST_COMPLETED)` to process results as they complete, enabling early
follow-up actions (e.g., start distillation while other fetches are still running).

```python
import asyncio
from temporalio import workflow

async def _process_as_completed(self, items: list) -> list:
    """Start all tasks and process results as they complete."""
    # Start all child workflows
    pending_tasks: dict[asyncio.Task, str] = {}
    for item in items:
        handle = await workflow.start_child_workflow(
            ItemWorkflow.run,
            ItemInput(item_id=item.id),
            id=f"item-{item.id}",
        )
        task = asyncio.create_task(handle.result())
        pending_tasks[task] = item.id

    results = []
    batch_for_next_step = []

    while pending_tasks:
        done, _ = await asyncio.wait(
            pending_tasks.keys(),
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            item_id = pending_tasks.pop(task)
            try:
                result = task.result()
                results.append(result)
                batch_for_next_step.append(result)

                # Process batch when enough items collected
                if len(batch_for_next_step) >= 5:
                    await self._start_next_step(batch_for_next_step)
                    batch_for_next_step = []

            except Exception as e:
                workflow.logger.error(
                    "Task failed",
                    extra={"item_id": item_id, "error": str(e)},
                )

        # Update progress
        self._progress.completed = len(results)
        await self._notify_update()

    # Handle remaining items
    if batch_for_next_step:
        await self._start_next_step(batch_for_next_step)

    return results
```

### Domain-based Rate Limiting

```python
from collections import defaultdict

# Group entries by domain
entries_by_domain = defaultdict(list)
for entry in entries:
    domain = extract_domain(entry["url"])
    entries_by_domain[domain].append(entry)

# Process each domain sequentially with delay
for domain, domain_entries in entries_by_domain.items():
    for i, entry in enumerate(domain_entries):
        if i > 0:
            await asyncio.sleep(delay_seconds)
        await process_entry(entry)
```

### Backward-Compatible Input Changes

```python
class MyWorkflowInput(CamelCaseModel):
    """Input for MyWorkflow."""
    # Original fields
    required_field: str
    optional_field: str = ""

    # New fields MUST be at end with defaults
    # This ensures running workflows can complete after code update
    new_feature_enabled: bool = False
    new_config: dict = Field(default_factory=dict)
```

## Configuration Management

### Design Principles

1. **Default values are constants in `config.py`**
2. **Input models reference these constants**
3. **Top-level workflows read from config; child workflows receive values via input**
4. **Priority: CLI args > parent workflow input > environment variable > default constant**

### Environment Variable Helpers

```python
# config.py
def get_env(name: str, default: str | None) -> str:
    """Get env var. default=None means required (raises ValueError if not set)."""
    value = os.getenv(name)
    if value is None:
        if default is None:
            raise ValueError(f"Required environment variable '{name}' is not set")
        return default
    return value

def get_env_bool(name: str, default: bool | None) -> bool:
    """Get boolean env var. Returns True if value is 'true' (case-insensitive)."""
    str_default = str(default) if default is not None else None
    return get_env(name, str_default).lower() == "true"

def get_env_int(name: str, default: int | None) -> int:
    """Get integer env var."""
    str_default = str(default) if default is not None else None
    return int(get_env(name, str_default))

def get_env_float(name: str, default: float | None) -> float:
    """Get float env var."""
    str_default = str(default) if default is not None else None
    return float(get_env(name, str_default))
```

### Defining Configurable Parameters

```python
# config.py - Step 1: Define default constant
DEFAULT_DISTILLATION_BATCH_SIZE = 5

@dataclass
class Config:
    # Step 2: Add config field
    distillation_batch_size: int

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            # Step 3: Read from env with default
            distillation_batch_size=get_env_int(
                "DISTILLATION_BATCH_SIZE", DEFAULT_DISTILLATION_BATCH_SIZE
            ),
        )
```

```python
# workflow_io.py - Step 4: Input model references constant
from buun_curator.config import DEFAULT_DISTILLATION_BATCH_SIZE

class ContentDistillationInput(CamelCaseModel):
    batch_size: int = DEFAULT_DISTILLATION_BATCH_SIZE

class SingleFeedIngestionInput(CamelCaseModel):
    # Propagate to child workflows
    distillation_batch_size: int = DEFAULT_DISTILLATION_BATCH_SIZE
```

### Where to Read Config

**Top-level workflows** (triggered directly by CLI/API) read from config:

```python
# all_feeds_ingestion.py - Top-level workflow
from buun_curator.config import get_config

@workflow.defn
class AllFeedsIngestionWorkflow:
    @workflow.run
    async def run(self, input: AllFeedsIngestionInput) -> AllFeedsIngestionResult:
        config = get_config()

        # Pass config value to child workflow
        await workflow.execute_child_workflow(
            SingleFeedIngestionWorkflow.run,
            SingleFeedIngestionInput(
                feed_id=feed.id,
                distillation_batch_size=config.distillation_batch_size,  # From config
            ),
        )
```

**Child workflows** receive values via input (never read config directly):

```python
# single_feed_ingestion.py - Child workflow
@workflow.defn
class SingleFeedIngestionWorkflow:
    @workflow.run
    async def run(self, input: SingleFeedIngestionInput) -> SingleFeedIngestionResult:
        # Use value from input, NOT from config
        await workflow.start_child_workflow(
            ContentDistillationWorkflow.run,
            ContentDistillationInput(
                entry_ids=entry_ids,
                batch_size=input.distillation_batch_size,  # From parent
            ),
        )
```

### CLI Argument Priority

In trigger scripts, CLI args override config when explicitly provided:

```python
# scripts/trigger_workflow.py
config = get_config()

# Use explicit None check, NOT `or` (0 is a valid value)
batch_size = (
    args.batch_size
    if args.batch_size is not None
    else config.distillation_batch_size
)
```

**IMPORTANT:** Never use `args.batch_size or config.xxx` pattern because `0` is falsy and would incorrectly use config value.

### Workflow Call Hierarchy Example

```text
AllFeedsIngestionWorkflow (reads config.distillation_batch_size)
  └─→ SingleFeedIngestionInput.distillation_batch_size
        └─→ ScheduleFetchInput.distillation_batch_size
              └─→ ContentDistillationInput.batch_size
```

## References

- [Temporal Python SDK Guide](https://docs.temporal.io/develop/python/core-application)
- [Temporal Testing Guide](https://docs.temporal.io/develop/python/testing-suite)
- Project docs: `docs/workflow.md`, `docs/logs-and-tracing.md`
