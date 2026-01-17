"""
Date utility functions for Temporal workflows.
"""

from temporalio import workflow


def workflow_now_iso() -> str:
    """
    Get current UTC timestamp in ISO 8601 format.

    Uses Temporal's deterministic workflow.now() for replay-safe time.
    Must be called within a workflow context.

    Returns
    -------
    str
        ISO 8601 formatted timestamp.
    """
    return workflow.now().isoformat()
