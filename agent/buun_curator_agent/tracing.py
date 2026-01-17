"""
OpenTelemetry tracing configuration for Agent.

Provides FastAPI auto-instrumentation and trace context propagation.

@module buun_curator_agent/tracing
"""

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from buun_curator_agent.config import settings
from buun_curator_agent.logging import get_logger

logger = get_logger(__name__)


def init_tracing() -> None:
    """
    Initialize OpenTelemetry tracing for the Agent.

    Sets up trace export to Grafana Tempo and auto-instruments httpx.
    """
    if not settings.otel_tracing_enabled:
        logger.info("Tracing disabled (OTEL_TRACING_ENABLED != true)")
        return

    logger.info(
        "Initializing tracing",
        service=settings.otel_service_name,
        endpoint=settings.otel_exporter_otlp_endpoint,
    )

    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: settings.otel_service_name,
        ResourceAttributes.SERVICE_VERSION: "0.1.0",
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: settings.environment,
    })

    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(
        OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Auto-instrument httpx for outbound HTTP calls
    HTTPXClientInstrumentor().instrument()

    logger.info("Tracing initialized successfully")


def instrument_fastapi(app: FastAPI) -> None:
    """
    Instrument FastAPI application with OpenTelemetry.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance.
    """
    if settings.otel_tracing_enabled:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
