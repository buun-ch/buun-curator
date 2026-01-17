"""
HTTP health check server for the Temporal worker.

Provides a /health endpoint for Kubernetes liveness probes.
The health check verifies that the worker can still communicate
with the Temporal server by attempting a simple namespace describe call.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from aiohttp import web

logger = logging.getLogger("buun_curator.health")


class HealthServer:
    """HTTP server for health check endpoints."""

    def __init__(
        self,
        port: int = 8080,
        health_check: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        """
        Initialize the health server.

        Parameters
        ----------
        port : int
            Port to listen on (default: 8080).
        health_check : Callable[[], Awaitable[bool]] | None
            Async function to check worker health. Returns True if healthy.
        """
        self.port = port
        self.health_check = health_check
        self.app = web.Application()
        self.app.router.add_get("/health", self._handle_health)
        self.app.router.add_get("/ready", self._handle_ready)
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def _handle_health(self, _request: web.Request) -> web.Response:
        """
        Handle /health endpoint for liveness probe.

        Returns 200 if worker is healthy, 503 if not.
        """
        if self.health_check:
            try:
                is_healthy = await asyncio.wait_for(self.health_check(), timeout=5.0)
                if is_healthy:
                    return web.Response(text="OK", status=200)
                return web.Response(text="Unhealthy", status=503)
            except TimeoutError:
                logger.warning("Health check timed out")
                return web.Response(text="Timeout", status=503)
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return web.Response(text=f"Error: {e}", status=503)
        return web.Response(text="OK", status=200)

    async def _handle_ready(self, _request: web.Request) -> web.Response:
        """
        Handle /ready endpoint for readiness probe.

        Returns 200 when the server is ready to receive requests.
        """
        return web.Response(text="OK", status=200)

    async def start(self) -> None:
        """Start the health server."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await self._site.start()
        logger.info(f"Health server started on port {self.port}")

    async def stop(self) -> None:
        """Stop the health server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("Health server stopped")
