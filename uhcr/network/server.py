"""Protocol server for UHCR network subsystem.

Manages the dual-protocol server lifecycle: HTTP/REST (aiohttp) and gRPC (grpcio).
Handles binding, accepting connections, graceful shutdown, and signal handling.

"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time
from typing import Any, Optional

from uhcr.network.jobs import JobManager

logger = logging.getLogger(__name__)

# Try importing optional dependencies with graceful fallback
try:
    import aiohttp
    from aiohttp import web

    from uhcr.network.health import HealthService, setup_health_routes

    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False

try:
    import grpc
    from grpc import aio as grpc_aio

    _GRPC_AVAILABLE = True
except ImportError:
    _GRPC_AVAILABLE = False


class PortBindError(Exception):
    """Raised when the server fails to bind to the specified port."""

    def __init__(self, host: str, port: int, reason: str = ""):
        self.host = host
        self.port = port
        self.reason = reason
        msg = f"Failed to bind to {host}:{port}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class ProtocolServer:
    """Main server orchestrating REST (aiohttp) and gRPC listeners.

    The ProtocolServer manages the full server lifecycle including:
    - Binding to configured host/port for both HTTP and gRPC
    - Starting and stopping both protocol listeners
    - Graceful shutdown with configurable grace period
    - Signal handling for SIGTERM/SIGINT
    - Integration with JobManager for request handling

    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        grpc_port: int = 50051,
        http_port: int = 8080,
        workers: int = 4,
        grace_period: int = 30,
        job_manager: Optional[JobManager] = None,
    ) -> None:
        """Initialize the ProtocolServer.

        Args:
            host: Network interface to bind to (default: "0.0.0.0").
            grpc_port: Port for gRPC listener (default: 50051).
            http_port: Port for HTTP/REST listener (default: 8080).
            workers: Number of worker threads/processes (default: 4).
            grace_period: Seconds to wait for in-flight requests during
                shutdown before force-terminating (default: 30).
            job_manager: JobManager instance for handling job requests.
                If None, a default JobManager is created.
        """
        self._host = host
        self._grpc_port = grpc_port
        self._http_port = http_port
        self._workers = workers
        self._grace_period = grace_period
        self._job_manager = job_manager or JobManager()

        # Internal state
        self._running = False
        self._ready = False
        self._start_time: Optional[float] = None
        self._shutdown_event: Optional[asyncio.Event] = None

        # Server instances
        self._http_app: Any = None
        self._http_runner: Any = None
        self._http_site: Any = None
        self._grpc_server: Any = None

        # Health service (only created when aiohttp is available)
        if _AIOHTTP_AVAILABLE:
            self._health_service: Optional[HealthService] = HealthService(
                job_manager=self._job_manager,
                server=self,
                overload_threshold=100,
            )
        else:
            self._health_service = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def host(self) -> str:
        """The network interface the server binds to."""
        return self._host

    @property
    def grpc_port(self) -> int:
        """The port for the gRPC listener."""
        return self._grpc_port

    @property
    def http_port(self) -> int:
        """The port for the HTTP/REST listener."""
        return self._http_port

    @property
    def workers(self) -> int:
        """Number of worker threads/processes."""
        return self._workers

    @property
    def grace_period(self) -> int:
        """Seconds to wait during graceful shutdown."""
        return self._grace_period

    @property
    def job_manager(self) -> JobManager:
        """The JobManager instance used by this server."""
        return self._job_manager

    @property
    def is_running(self) -> bool:
        """Whether the server is currently running and accepting connections."""
        return self._running

    @property
    def uptime(self) -> float:
        """Seconds since the server started. Returns 0.0 if not running."""
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def health_service(self) -> Optional["HealthService"]:
        """The HealthService instance, or None if aiohttp is not available."""
        return self._health_service

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the server, binding to host/port for both REST and gRPC.

        Starts both the aiohttp HTTP/REST listener and the gRPC listener.
        Registers signal handlers for graceful shutdown.

        Raises:
            PortBindError: If binding to the configured port fails.
            RuntimeError: If required dependencies (aiohttp, grpcio) are
                not installed.
        """
        if self._running:
            logger.warning("Server is already running")
            return

        self._shutdown_event = asyncio.Event()

        # Start HTTP/REST listener
        await self._start_http()

        # Start gRPC listener
        await self._start_grpc()

        # Register signal handlers
        self._register_signal_handlers()

        self._running = True
        self._start_time = time.monotonic()
        self._ready = True

        logger.info(
            "ProtocolServer started: HTTP on %s:%d, gRPC on %s:%d",
            self._host,
            self._http_port,
            self._host,
            self._grpc_port,
        )

    async def stop(self) -> None:
        """Gracefully stop the server.

        Signals in-flight requests to complete, waits up to grace_period
        seconds, then force-terminates any remaining connections.
        """
        if not self._running:
            logger.warning("Server is not running")
            return

        logger.info(
            "Initiating graceful shutdown (grace_period=%ds)...",
            self._grace_period,
        )

        # Signal shutdown
        if self._shutdown_event:
            self._shutdown_event.set()

        # Stop accepting new connections and drain in-flight requests
        await self._stop_http()
        await self._stop_grpc()

        self._running = False
        self._ready = False
        self._start_time = None

        logger.info("ProtocolServer stopped")

    # ------------------------------------------------------------------
    # HTTP/REST lifecycle
    # ------------------------------------------------------------------

    async def _start_http(self) -> None:
        """Start the aiohttp HTTP/REST listener."""
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError(
                "aiohttp is required for the HTTP/REST server. "
                "Install it with: pip install aiohttp>=3.9.0"
            )

        self._http_app = web.Application()
        self._setup_http_routes(self._http_app)

        self._http_runner = web.AppRunner(self._http_app)
        await self._http_runner.setup()

        try:
            self._http_site = web.TCPSite(
                self._http_runner,
                self._host,
                self._http_port,
            )
            await self._http_site.start()
        except OSError as e:
            # Clean up runner on bind failure
            await self._http_runner.cleanup()
            self._http_runner = None
            self._http_site = None
            logger.error(
                "Failed to bind HTTP server to %s:%d: %s",
                self._host,
                self._http_port,
                e,
            )
            raise PortBindError(self._host, self._http_port, str(e)) from e

    async def _stop_http(self) -> None:
        """Stop the aiohttp HTTP/REST listener gracefully."""
        if self._http_site:
            await self._http_site.stop()
            self._http_site = None

        if self._http_runner:
            # Shutdown with grace period for in-flight requests
            await self._http_runner.shutdown()
            await self._http_runner.cleanup()
            self._http_runner = None

        self._http_app = None

    def _setup_http_routes(self, app: Any) -> None:
        """Configure HTTP routes on the aiohttp application.

        Registers the full health check endpoints via HealthService, plus
        stores references to the job manager and server in the app context.
        """
        app["job_manager"] = self._job_manager
        app["server"] = self

        # Register /health, /health/live, /health/ready via HealthService
        setup_health_routes(app, self._health_service)

    # ------------------------------------------------------------------
    # gRPC lifecycle
    # ------------------------------------------------------------------

    async def _start_grpc(self) -> None:
        """Start the gRPC listener."""
        if not _GRPC_AVAILABLE:
            raise RuntimeError(
                "grpcio is required for the gRPC server. "
                "Install it with: pip install grpcio>=1.60.0"
            )

        self._grpc_server = grpc_aio.server(
            options=[
                ("grpc.max_workers", self._workers),
            ]
        )

        bind_address = f"{self._host}:{self._grpc_port}"

        # add_insecure_port returns 0 if binding fails
        port = self._grpc_server.add_insecure_port(bind_address)
        if port == 0:
            logger.error(
                "Failed to bind gRPC server to %s:%d",
                self._host,
                self._grpc_port,
            )
            raise PortBindError(
                self._host,
                self._grpc_port,
                "gRPC port binding returned 0 (port unavailable)",
            )

        try:
            await self._grpc_server.start()
        except Exception as e:
            logger.error(
                "Failed to start gRPC server on %s:%d: %s",
                self._host,
                self._grpc_port,
                e,
            )
            raise PortBindError(self._host, self._grpc_port, str(e)) from e

    async def _stop_grpc(self) -> None:
        """Stop the gRPC listener gracefully."""
        if self._grpc_server:
            # Grace period for in-flight RPCs
            await self._grpc_server.stop(grace=self._grace_period)
            self._grpc_server = None

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _register_signal_handlers(self) -> None:
        """Register SIGTERM and SIGINT handlers for graceful shutdown.

        On Windows, signal handlers are registered differently since
        asyncio loop.add_signal_handler is not supported.
        """
        loop = asyncio.get_running_loop()

        if sys.platform == "win32":
            # Windows does not support loop.add_signal_handler
            # Use signal.signal instead (runs in main thread)
            signal.signal(signal.SIGINT, self._sync_signal_handler)
            signal.signal(signal.SIGTERM, self._sync_signal_handler)
        else:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._handle_signal, sig)

    def _handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signal by scheduling graceful stop.

        Args:
            sig: The signal that was received.
        """
        logger.info("Received signal %s, initiating graceful shutdown...", sig.name)
        asyncio.ensure_future(self.stop())

    def _sync_signal_handler(self, signum: int, frame: Any) -> None:
        """Synchronous signal handler for Windows compatibility.

        Args:
            signum: The signal number.
            frame: The current stack frame.
        """
        sig_name = signal.Signals(signum).name
        logger.info("Received signal %s, initiating graceful shutdown...", sig_name)
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.stop()))

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "ProtocolServer":
        """Start the server when entering async context."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the server when exiting async context."""
        await self.stop()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def wait_for_shutdown(self) -> None:
        """Block until the server receives a shutdown signal.

        Useful for keeping the main coroutine alive while the server runs.
        """
        if self._shutdown_event:
            await self._shutdown_event.wait()

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return (
            f"ProtocolServer("
            f"host={self._host!r}, "
            f"grpc_port={self._grpc_port}, "
            f"http_port={self._http_port}, "
            f"workers={self._workers}, "
            f"status={status})"
        )
