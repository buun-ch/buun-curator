"""
Trace ID utilities for Langfuse integration.
"""

import hashlib


def generate_entry_trace_id(entry_id: str, batch_trace_id: str | None = None) -> str:
    """
    Generate a deterministic trace_id for an entry.

    Uses SHA256 hash to create a 32-char hex trace_id from entry_id.
    If batch_trace_id is provided, it's included in the hash for uniqueness
    across different batch runs.

    Parameters
    ----------
    entry_id : str
        The entry ID.
    batch_trace_id : str | None, optional
        The batch trace ID for additional uniqueness (default: None).

    Returns
    -------
    str
        32-character lowercase hex trace_id compatible with Langfuse SDK v3.
    """
    hash_input = f"{entry_id}:{batch_trace_id or ''}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:32]
