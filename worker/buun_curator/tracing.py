"""
OpenTelemetry tracing configuration for Buun Curator Worker.

Provides optional distributed tracing with graceful degradation when
tracing is disabled or the collector is unavailable.
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from temporalio.contrib.opentelemetry import TracingInterceptor

logger = logging.getLogger(__name__)


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled via environment variable."""
    return os.getenv("OTEL_TRACING_ENABLED", "false").lower() == "true"


def init_tracing() -> TracingInterceptor | None:
    """
    Initialize OpenTelemetry tracing if enabled.

    Sets up the global TracerProvider and returns a Temporal interceptor.
    Uses OpenTelemetry's built-in global state management.

    Returns
    -------
    TracingInterceptor | None
        Temporal tracing interceptor if enabled, None otherwise.
    """
    if not is_tracing_enabled():
        logger.info("Tracing disabled (OTEL_TRACING_ENABLED != true)")
        return None

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    service_name = os.getenv("OTEL_SERVICE_NAME", "buun-curator-worker")

    logger.info(f"Initializing tracing: service={service_name}, endpoint={endpoint}")

    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv("APP_VERSION", "0.1.0"),
            "deployment.environment": os.getenv("DEPLOYMENT_ENV", "development"),
        }
    )

    # Set global TracerProvider (can only be done once)
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # Create OTLP exporter with batch processor
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true",
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))

    logger.info("Tracing initialized successfully")
    return TracingInterceptor()


def shutdown_tracing() -> None:
    """Shutdown tracing and flush any pending spans."""
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.shutdown()
        logger.info("Tracing shut down")
