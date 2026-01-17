"""
Structured logging configuration with OpenTelemetry trace context.

Provides JSON logging with automatic trace_id/span_id injection for
Grafana Trace-to-Logs correlation.

@module buun_curator/logging
"""

import logging
import sys
from typing import Any

import structlog
from opentelemetry import trace
from structlog.typing import EventDict, WrappedLogger


def _json_fallback_handler(obj: Any) -> str:
    """
    JSON fallback handler for non-serializable objects.

    Uses simple repr() without importing external modules like rich,
    which is important for Temporal workflow sandbox compatibility.
    The default structlog fallback handler imports rich for pretty
    printing, but rich uses os.path which is restricted in workflow sandbox.

    Parameters
    ----------
    obj : Any
        Non-JSON-serializable object.

    Returns
    -------
    str
        String representation of the object.
    """
    return repr(obj)


def add_trace_context(
    _logger: WrappedLogger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Add OpenTelemetry trace context to log entries.

    Processor that injects trace_id and span_id from the current span
    into every log entry for Grafana Trace-to-Logs correlation.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def make_add_component_processor(
    component: str,
) -> structlog.types.Processor:
    """
    Create a processor that adds a static component field to log entries.

    Parameters
    ----------
    component : str
        Component name to add (e.g., "worker", "agent").

    Returns
    -------
    structlog.types.Processor
        Processor function that adds the component field.
    """

    def add_component(
        _logger: WrappedLogger,
        _method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        event_dict["component"] = component
        return event_dict

    return add_component


def configure_logging(
    json_logs: bool = True,
    log_level: str = "INFO",
    component: str | None = None,
) -> None:
    """
    Configure structlog with OpenTelemetry trace context injection.

    Parameters
    ----------
    json_logs : bool
        If True, output JSON logs (production). If False, use console renderer (dev).
    log_level : str
        Logging level (DEBUG, INFO, WARNING, ERROR).
    component : str | None
        Component name to include in all log entries (e.g., "worker", "agent").
    """
    # Shared processors for both structlog and standard logging
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_trace_context,
    ]

    # Add component processor if specified (must be added to shared_processors
    # to apply to both structlog and standard library loggers)
    if component:
        shared_processors.append(make_add_component_processor(component))

    if json_logs:
        # Production: JSON output
        # Custom fallback avoids importing rich (os.path restricted in workflow sandbox)
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer(
            default=_json_fallback_handler
        )
    else:
        # Development: colored console output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to use structlog formatter
    # This ensures third-party libraries using standard logging also get structured output
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[
                # ExtraAdder extracts extra dict from LogRecord and adds to event dict
                # This enables structured logging via workflow.logger.info("msg", extra={...})
                structlog.stdlib.ExtraAdder(),
                *shared_processors,
            ],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.WARNING)  # Default for third-party libraries

    # Set buun_curator loggers to specified level
    logging.getLogger("buun_curator").setLevel(getattr(logging, log_level))
    logging.getLogger("buun-curator").setLevel(getattr(logging, log_level))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger with the given name.

    Parameters
    ----------
    name : str
        Logger name (typically __name__).

    Returns
    -------
    structlog.stdlib.BoundLogger
        Configured logger with trace context injection.
    """
    return structlog.get_logger(name)
