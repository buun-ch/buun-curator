"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from buun_curator_agent.config import settings
from buun_curator_agent.logging import configure_logging, get_logger
from buun_curator_agent.routes import ag_ui_router, chat_router, health_router
from buun_curator_agent.tracing import init_tracing, instrument_fastapi

# Initialize structured logging first (before any logging calls)
configure_logging(component="agent")

# Initialize OpenTelemetry tracing
init_tracing()


class HealthCheckFilter(logging.Filter):
    """Filter to exclude health check requests from access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False for health check requests to suppress them."""
        message = record.getMessage()
        return "/health" not in message


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    logger = get_logger(__name__)
    logger.info(
        "Agent starting",
        log_level=settings.log_level,
        otel_enabled=settings.otel_tracing_enabled,
    )
    yield
    # Shutdown


app = FastAPI(
    title="Buun Agent",
    description="LangGraph-based AI agent service for Buun Curator",
    version="0.1.0",
    lifespan=lifespan,
)

# Instrument FastAPI with OpenTelemetry
instrument_fastapi(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, tags=["health"])
app.include_router(chat_router, tags=["chat"])
app.include_router(ag_ui_router, prefix="/ag-ui", tags=["ag-ui"])


def main() -> None:
    """Run the application with uvicorn."""
    import uvicorn

    # Apply health check filter to uvicorn access logs
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.addFilter(HealthCheckFilter())

    uvicorn.run(
        "buun_curator_agent.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_config=None,  # Use our structlog configuration
    )


if __name__ == "__main__":
    main()
