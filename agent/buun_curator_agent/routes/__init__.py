"""API routes."""

from buun_curator_agent.routes.ag_ui import router as ag_ui_router
from buun_curator_agent.routes.chat import router as chat_router
from buun_curator_agent.routes.health import router as health_router

__all__ = ["ag_ui_router", "chat_router", "health_router"]
