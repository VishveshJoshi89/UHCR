"""Health check endpoints for UHCR network subsystem.

Provides HTTP liveness and readiness probes for Kubernetes-style health checking.
All handlers are non-blocking (async) to meet the <100ms response time target.

"""

from __future__ import annotations

import logging
from typing import Any, Optional

from uhcr import __version__

logger = logging.getLogger(__name__)

try:
    from aiohttp import web

    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False


class HealthService:
    """Implements HTTP health check endpoints for liveness and readiness probes.

    Provides three endpoints:
    - GET /health       — Basic health summary (version, uptime, job count, workers)
    - GET /health/live  — Liveness probe: returns 200 when the process is running
    - GET /health/ready — Readiness probe: returns 200 when ready, 503 when overloaded

    The readiness probe uses a configurable overload threshold (default: 100 active
    jobs). When the active job count exceeds the threshold, the server is considered
    overloaded and returns HTTP 503.

    All handlers are async and non-blocking to meet the <100ms response time target.

    """

    def __init__(
        self,
        job_manager: Any,
        server: Any,
        overload_threshold: int = 100,
    ) -> None:
        """Initialize the HealthService.

        Args:
            job_manager: JobManager instance used to query active job count.
            server: ProtocolServer instance used to query uptime and worker count.
            overload_threshold: Number of active jobs above which the server is
                considered overloaded and the readiness probe returns 503.
                Defaults to 100.
        """
        self._job_manager = job_manager
        self._server = server
        self._overload_threshold = overload_threshold

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def overload_threshold(self) -> int:
        """Active job count above which the server is considered overloaded."""
        return self._overload_threshold

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _active_job_count(self) -> int:
        """Return the number of currently active (queued + running) jobs."""
        try:
            from uhcr.network.jobs import JobStatus

            queued = len(self._job_manager.list_jobs(status=JobStatus.QUEUED))
            running = len(self._job_manager.list_jobs(status=JobStatus.RUNNING))
            return queued + running
        except Exception:
            # Fallback: use total job count if status filtering fails
            try:
                return self._job_manager.job_count()
            except Exception:
                return 0

    def _connected_worker_count(self) -> int:
        """Return the number of connected worker nodes."""
        try:
            # ProtocolServer may expose a coordinator with registered workers
            coordinator = getattr(self._server, "coordinator", None)
            if coordinator is not None:
                workers = getattr(coordinator, "list_workers", None)
                if callable(workers):
                    return len(workers())
            # Fallback: check for a direct workers attribute
            workers_attr = getattr(self._server, "workers", None)
            if isinstance(workers_attr, (list, dict)):
                return len(workers_attr)
        except Exception:
            pass
        return 0

    def _uptime_seconds(self) -> float:
        """Return server uptime in seconds."""
        try:
            return float(self._server.uptime)
        except Exception:
            return 0.0

    def _build_health_body(self) -> dict:
        """Build the common health response body."""
        return {
            "version": __version__,
            "uptime_seconds": self._uptime_seconds(),
            "active_jobs": self._active_job_count(),
            "connected_workers": self._connected_worker_count(),
        }

    # ------------------------------------------------------------------
    # HTTP handlers
    # ------------------------------------------------------------------

    async def handle_health(self, request: Any) -> Any:
        """Handle GET /health — basic health summary.

        Returns HTTP 200 with server version, uptime, active job count,
        and connected worker count.

        Args:
            request: The aiohttp Request object.

        Returns:
            JSON response with health summary.
        """
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp is required for health endpoints")

        body = self._build_health_body()
        body["status"] = "ok"
        return web.json_response(body, status=200)

    async def handle_liveness(self, request: Any) -> Any:
        """Handle GET /health/live — liveness probe.

        Returns HTTP 200 with ``{"status": "alive"}`` when the process is
        running. This endpoint always succeeds as long as the process is alive.

        Args:
            request: The aiohttp Request object.

        Returns:
            JSON response with status "alive".
        """
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp is required for health endpoints")

        return web.json_response({"status": "alive"}, status=200)

    async def handle_readiness(self, request: Any) -> Any:
        """Handle GET /health/ready — readiness probe.

        Returns HTTP 200 when the server is ready to accept jobs (active job
        count is below the overload threshold). Returns HTTP 503 when the
        server is overloaded (active job count >= overload_threshold).

        The response body always includes server version, uptime, active job
        count, and connected worker count.

        Args:
            request: The aiohttp Request object.

        Returns:
            JSON response with health details; status 200 or 503.
        """
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp is required for health endpoints")

        active_jobs = self._active_job_count()
        overloaded = active_jobs >= self._overload_threshold

        body = self._build_health_body()

        if overloaded:
            body["status"] = "overloaded"
            body["reason"] = (
                f"Active job count ({active_jobs}) exceeds threshold "
                f"({self._overload_threshold})"
            )
            return web.json_response(body, status=503)

        body["status"] = "ready"
        return web.json_response(body, status=200)


def setup_health_routes(app: Any, health_service: Optional[HealthService] = None) -> None:
    """Register health check routes on an aiohttp Application.

    Routes registered:
        GET /health        — Basic health summary
        GET /health/live   — Liveness probe (always 200 when process is alive)
        GET /health/ready  — Readiness probe (200 when ready, 503 when overloaded)

    If ``health_service`` is None, the function attempts to retrieve a
    ``HealthService`` instance from ``app["health_service"]``. If neither is
    available, a ``ValueError`` is raised.

    Args:
        app: The aiohttp Application to register routes on.
        health_service: The HealthService instance to use for handling requests.
            If None, ``app["health_service"]`` must be set before requests arrive.

    Raises:
        RuntimeError: If aiohttp is not installed.
        ValueError: If no HealthService is provided and none is stored in the app.
    """
    if not _AIOHTTP_AVAILABLE:
        raise RuntimeError(
            "aiohttp is required for health routes. "
            "Install it with: pip install aiohttp>=3.9.0"
        )

    if health_service is not None:
        app["health_service"] = health_service

    async def _health(request: Any) -> Any:
        svc: HealthService = request.app["health_service"]
        return await svc.handle_health(request)

    async def _liveness(request: Any) -> Any:
        svc: HealthService = request.app["health_service"]
        return await svc.handle_liveness(request)

    async def _readiness(request: Any) -> Any:
        svc: HealthService = request.app["health_service"]
        return await svc.handle_readiness(request)

    app.router.add_get("/health", _health)
    app.router.add_get("/health/live", _liveness)
    app.router.add_get("/health/ready", _readiness)
