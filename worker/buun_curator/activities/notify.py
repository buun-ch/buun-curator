"""
SSE notification local activity.

Lightweight activity for sending real-time notifications to browser clients.
Designed to be used as a local activity from workflows.

Architecture:
- Worker sends full progress data directly to Next.js API via HTTP POST
- Next.js broadcasts progress to browser clients via SSE (no Temporal Query)

This avoids blocking Worker threads during CPU-bound operations, as Temporal
Query requires the worker to replay workflow state to respond.

Throttling is handled inside the activity (per workflow ID) to ensure
deterministic workflow execution.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.services.api import APIClient

# Throttle state per workflow ID (module-level for persistence across activity calls)
_last_notify_times: dict[str, float] = {}

# Throttle interval in seconds
_THROTTLE_SECONDS: float = 0.3


@dataclass
class NotifyProgressInput:
    """Input for notify_progress local activity."""

    workflow_id: str
    progress: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotifyOutput:
    """Output for notification activities."""

    success: bool
    error: str = ""


def _cleanup_old_throttle_entries() -> None:
    """Remove throttle entries older than 1 hour to prevent memory leaks."""
    now = time.time()
    cutoff = now - 3600  # 1 hour
    keys_to_remove = [k for k, v in _last_notify_times.items() if v < cutoff]
    for key in keys_to_remove:
        del _last_notify_times[key]


@activity.defn
async def notify_progress(input: NotifyProgressInput) -> NotifyOutput:
    """
    Send workflow progress directly to Next.js via HTTP POST.

    Next.js will broadcast the progress to browser clients via SSE
    without querying Temporal.

    Throttling is applied per workflow ID to avoid flooding the frontend.
    Final status updates (completed/error) bypass throttling.

    Parameters
    ----------
    input : NotifyProgressInput
        Contains workflow ID and full progress data.

    Returns
    -------
    NotifyOutput
        Result indicating success or failure.
    """
    now = time.time()
    workflow_id = input.workflow_id
    progress_status = input.progress.get("status", "")

    # Bypass throttle for final status updates (completed/error)
    is_final_status = progress_status in ("completed", "error")

    # Throttle check (per workflow ID) - skip for final status
    if not is_final_status:
        last_notify = _last_notify_times.get(workflow_id, 0)
        if now - last_notify < _THROTTLE_SECONDS:
            return NotifyOutput(success=True)  # Throttled, but not an error

    # Update last notify time
    _last_notify_times[workflow_id] = now

    # Cleanup old entries periodically (roughly every 100 calls)
    if len(_last_notify_times) > 100:
        _cleanup_old_throttle_entries()

    config = get_config()

    if not config.api_url or not config.api_token:
        return NotifyOutput(success=False, error="API not configured")

    try:
        async with APIClient(config.api_url, config.api_token) as api:
            event_data = {
                "workflowId": workflow_id,
                "progress": input.progress,
            }
            success = await api.send_sse_event("progress", event_data)
            return NotifyOutput(success=success)
    except asyncio.CancelledError:
        # Workflow was cancelled, silently ignore
        # This is expected when workflow completes quickly
        return NotifyOutput(success=False, error="cancelled")
    except Exception as e:
        return NotifyOutput(success=False, error=str(e))
