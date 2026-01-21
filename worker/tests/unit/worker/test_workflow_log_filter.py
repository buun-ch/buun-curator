"""
Tests for WorkflowLogFilter.

Verifies that the filter properly strips Temporal context dicts from log messages.
"""

import logging

import pytest

from buun_curator.worker import WorkflowLogFilter


@pytest.fixture
def log_filter() -> WorkflowLogFilter:
    """Create a WorkflowLogFilter instance."""
    return WorkflowLogFilter()


def test_strips_single_quoted_dict_suffix(log_filter: WorkflowLogFilter) -> None:
    """Test that filter strips ({'key': 'value'}) suffix from messages."""
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="Completing activity as failed ({'activity_id': '5', 'activity_type': 'distill'})",
        args=(),
        exc_info=None,
    )

    result = log_filter.filter(record)

    assert result is True
    assert record.msg == "Completing activity as failed"
    assert record.args == ()


def test_strips_double_quoted_dict_suffix(log_filter: WorkflowLogFilter) -> None:
    """Test that filter strips ({"key": "value"}) suffix from messages."""
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg='Completing activity as failed ({"activity_id": "5", "activity_type": "distill"})',
        args=(),
        exc_info=None,
    )

    result = log_filter.filter(record)

    assert result is True
    assert record.msg == "Completing activity as failed"
    assert record.args == ()


def test_preserves_message_without_dict_suffix(log_filter: WorkflowLogFilter) -> None:
    """Test that filter preserves messages without dict suffix."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Normal log message without context",
        args=(),
        exc_info=None,
    )

    result = log_filter.filter(record)

    assert result is True
    assert record.msg == "Normal log message without context"


def test_preserves_message_with_parentheses_not_dict(
    log_filter: WorkflowLogFilter,
) -> None:
    """Test that filter preserves messages with parentheses that are not dicts."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Processing entry (total: 5)",
        args=(),
        exc_info=None,
    )

    result = log_filter.filter(record)

    assert result is True
    assert record.msg == "Processing entry (total: 5)"


def test_handles_complex_nested_dict(log_filter: WorkflowLogFilter) -> None:
    """Test that filter handles complex nested dict structures."""
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg=(
            "Activity failed ({'attempt': 2, 'namespace': 'buun-curator', "
            "'workflow_id': 'test-123'})"
        ),
        args=(),
        exc_info=None,
    )

    result = log_filter.filter(record)

    assert result is True
    assert record.msg == "Activity failed"


def test_handles_message_with_multiple_parentheses(
    log_filter: WorkflowLogFilter,
) -> None:
    """Test that filter only strips the trailing dict, preserving other parentheses."""
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="Processing (step 1 of 3) completed ({'status': 'ok'})",
        args=(),
        exc_info=None,
    )

    result = log_filter.filter(record)

    assert result is True
    assert record.msg == "Processing (step 1 of 3) completed"


@pytest.mark.parametrize(
    "msg",
    [
        "Normal message",
        "Message with dict ({'key': 'value'})",
        "",
        "Message ending with )",
    ],
)
def test_always_returns_true(log_filter: WorkflowLogFilter, msg: str) -> None:
    """Test that filter always returns True (never suppresses messages)."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    assert log_filter.filter(record) is True


def test_handles_empty_message(log_filter: WorkflowLogFilter) -> None:
    """Test that filter handles empty messages gracefully."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    )

    result = log_filter.filter(record)

    assert result is True
    assert record.msg == ""


def test_real_temporal_activity_failed_message(log_filter: WorkflowLogFilter) -> None:
    """Test with a real Temporal SDK activity failure message format."""
    record = logging.LogRecord(
        name="temporalio.activity",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg=(
            "Completing activity as failed ({'activity_id': '5', "
            "'activity_type': 'distill_entry_content', 'attempt': 2, "
            "'namespace': 'buun-curator', 'task_queue': 'buun-curator', "
            "'workflow_id': 'distill-reprocess-70ffafe', "
            "'workflow_run_id': '019be071-60f9-7be9-b162-d5e9fbc490d5', "
            "'workflow_type': 'ContentDistillationWorkflow'})"
        ),
        args=(),
        exc_info=None,
    )

    result = log_filter.filter(record)

    assert result is True
    assert record.msg == "Completing activity as failed"
