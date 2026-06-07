"""gRPC service implementation for UHCR network subsystem.

Implements the UHCRService defined in uhcr_service.proto using grpcio's
generic RPC handler pattern. Works without pre-generated stubs by using
grpcio's reflection and generic servicer approach.

Service RPCs:
    - SubmitJob: Accept a job request, queue it, return job_id and status
    - GetJobStatus: Look up a job by ID, return status/timestamps/result
    - StreamResults: Stream result chunks (64KB each) for a completed job

"""

from __future__ import annotations

import logging
import math
from typing import Any, AsyncIterator, Optional

from uhcr.network.jobs import InvalidPayloadError, JobManager, JobStatus

logger = logging.getLogger(__name__)

# Try importing grpcio with a clear error message if not installed
try:
    import grpc
    from grpc import aio as grpc_aio

    _GRPC_AVAILABLE = True
except ImportError:
    _GRPC_AVAILABLE = False
    grpc = None  # type: ignore[assignment]
    grpc_aio = None  # type: ignore[assignment]

# Try importing protobuf for message serialization
try:
    from google.protobuf import descriptor_pool as _descriptor_pool
    from google.protobuf import symbol_database as _symbol_database

    _PROTOBUF_AVAILABLE = True
except ImportError:
    _PROTOBUF_AVAILABLE = False

# Chunk size for StreamResults (64KB per chunk as per proto spec)
_STREAM_CHUNK_SIZE = 64 * 1024  # 64KB


# ---------------------------------------------------------------------------
# Simple message objects (used when generated stubs are not available)
# ---------------------------------------------------------------------------


class _JobResponse:
    """Lightweight stand-in for the generated JobResponse protobuf message."""

    __slots__ = ("job_id", "status", "error")

    def __init__(self, job_id: str = "", status: str = "", error: str = "") -> None:
        self.job_id = job_id
        self.status = status
        self.error = error


class _JobStatusResponse:
    """Lightweight stand-in for the generated JobStatusResponse protobuf message."""

    __slots__ = (
        "job_id",
        "status",
        "submitted_at",
        "completed_at",
        "result",
        "error",
    )

    def __init__(
        self,
        job_id: str = "",
        status: str = "",
        submitted_at: str = "",
        completed_at: str = "",
        result: bytes = b"",
        error: str = "",
    ) -> None:
        self.job_id = job_id
        self.status = status
        self.submitted_at = submitted_at
        self.completed_at = completed_at
        self.result = result
        self.error = error


class _ResultChunk:
    """Lightweight stand-in for the generated ResultChunk protobuf message."""

    __slots__ = ("job_id", "data", "chunk_index", "is_last")

    def __init__(
        self,
        job_id: str = "",
        data: bytes = b"",
        chunk_index: int = 0,
        is_last: bool = False,
    ) -> None:
        self.job_id = job_id
        self.data = data
        self.chunk_index = chunk_index
        self.is_last = is_last


# ---------------------------------------------------------------------------
# UHCRServicer
# ---------------------------------------------------------------------------


class UHCRServicer:
    """Implements the UHCRService gRPC service.

    Handles SubmitJob, GetJobStatus, and StreamResults RPCs by delegating
    to the provided JobManager instance.

    """

    def __init__(self, job_manager: JobManager) -> None:
        """Initialize the servicer with a JobManager.

        Args:
            job_manager: The JobManager instance used to manage job lifecycle.
        """
        self._job_manager = job_manager

    async def SubmitJob(self, request: Any, context: Any) -> _JobResponse:
        """Accept a job request, queue it, and return the job ID and status.

        Reads ``payload``, ``timeout_seconds``, and ``worker_hint`` from the
        request object (or dict).  Calls ``JobManager.submit_job()`` and
        returns a response with the assigned job ID and ``"queued"`` status.

        Args:
            request: JobRequest message (or dict-like object) with fields:
                - payload (bytes): Serialized IR or script bytes.
                - timeout_seconds (float): Job timeout (0 uses default).
                - worker_hint (str): Optional preferred worker architecture.
            context: gRPC servicer context for setting status codes.

        Returns:
            _JobResponse with job_id and status="queued", or error set on
            failure.
        """
        # Extract fields — support both attribute-style and dict-style access
        payload = _get_field(request, "payload", b"")
        timeout_seconds = _get_field(request, "timeout_seconds", 0.0)

        try:
            job_id = self._job_manager.submit_job(
                payload=payload,
                timeout=float(timeout_seconds),
            )
            logger.info("gRPC SubmitJob: queued job %s", job_id)
            return _JobResponse(job_id=job_id, status=JobStatus.QUEUED.value)
        except InvalidPayloadError as exc:
            logger.warning("gRPC SubmitJob: invalid payload — %s", exc)
            if context is not None and _GRPC_AVAILABLE:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
            return _JobResponse(error=str(exc))
        except Exception as exc:  # pragma: no cover
            logger.exception("gRPC SubmitJob: unexpected error")
            if context is not None and _GRPC_AVAILABLE:
                await context.abort(grpc.StatusCode.INTERNAL, str(exc))
            return _JobResponse(error=str(exc))

    async def GetJobStatus(self, request: Any, context: Any) -> _JobStatusResponse:
        """Look up a job by ID and return its status, timestamps, and result.

        Args:
            request: JobStatusRequest message (or dict-like object) with field:
                - job_id (str): The UUID4 job identifier.
            context: gRPC servicer context for setting status codes.

        Returns:
            _JobStatusResponse with all available job fields populated.
        """
        job_id = _get_field(request, "job_id", "")

        job = self._job_manager.get_job(job_id)
        if job is None:
            logger.warning("gRPC GetJobStatus: job not found — %s", job_id)
            if context is not None and _GRPC_AVAILABLE:
                await context.abort(
                    grpc.StatusCode.NOT_FOUND,
                    f"Job not found: {job_id}",
                )
            return _JobStatusResponse(job_id=job_id, error=f"Job not found: {job_id}")

        submitted_at = (
            job.submitted_at.isoformat() if job.submitted_at is not None else ""
        )
        completed_at = (
            job.completed_at.isoformat() if job.completed_at is not None else ""
        )

        logger.debug("gRPC GetJobStatus: job %s status=%s", job_id, job.status.value)
        return _JobStatusResponse(
            job_id=job.id,
            status=job.status.value,
            submitted_at=submitted_at,
            completed_at=completed_at,
            result=job.result or b"",
            error=job.error or "",
        )

    async def StreamResults(
        self, request: Any, context: Any
    ) -> AsyncIterator[_ResultChunk]:
        """Stream result chunks (64KB each) for a completed job.

        Yields ``ResultChunk`` messages until all result bytes have been sent.
        The final chunk has ``is_last=True``.

        Args:
            request: JobStatusRequest message (or dict-like object) with field:
                - job_id (str): The UUID4 job identifier.
            context: gRPC servicer context for setting status codes.

        Yields:
            _ResultChunk objects containing sequential slices of the result.
        """
        job_id = _get_field(request, "job_id", "")

        job = self._job_manager.get_job(job_id)
        if job is None:
            logger.warning("gRPC StreamResults: job not found — %s", job_id)
            if context is not None and _GRPC_AVAILABLE:
                await context.abort(
                    grpc.StatusCode.NOT_FOUND,
                    f"Job not found: {job_id}",
                )
            return

        if job.status != JobStatus.COMPLETED:
            msg = (
                f"Job {job_id} is not completed (status={job.status.value}); "
                "results are only available for completed jobs"
            )
            logger.warning("gRPC StreamResults: %s", msg)
            if context is not None and _GRPC_AVAILABLE:
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, msg)
            return

        result_bytes = job.result or b""
        total_size = len(result_bytes)

        if total_size == 0:
            # Yield a single empty terminal chunk
            yield _ResultChunk(job_id=job_id, data=b"", chunk_index=0, is_last=True)
            return

        total_chunks = math.ceil(total_size / _STREAM_CHUNK_SIZE)
        logger.debug(
            "gRPC StreamResults: streaming %d bytes in %d chunks for job %s",
            total_size,
            total_chunks,
            job_id,
        )

        for chunk_index in range(total_chunks):
            start = chunk_index * _STREAM_CHUNK_SIZE
            end = min(start + _STREAM_CHUNK_SIZE, total_size)
            chunk_data = result_bytes[start:end]
            is_last = chunk_index == total_chunks - 1

            yield _ResultChunk(
                job_id=job_id,
                data=chunk_data,
                chunk_index=chunk_index,
                is_last=is_last,
            )


# ---------------------------------------------------------------------------
# GRPCServer
# ---------------------------------------------------------------------------


class GRPCServer:
    """Wraps a grpc.aio.server instance for the UHCR gRPC service.

    Manages the lifecycle of the gRPC server: creation, binding, starting,
    and graceful shutdown.

    """

    def __init__(self, job_manager: Optional[JobManager] = None) -> None:
        """Initialize the GRPCServer.

        Args:
            job_manager: JobManager instance to use for handling RPCs.
                If None, a default JobManager is created.
        """
        if not _GRPC_AVAILABLE:
            raise RuntimeError(
                "grpcio is required for the gRPC server. "
                "Install it with: pip install grpcio>=1.60.0"
            )

        self._job_manager = job_manager or JobManager()
        self._servicer = UHCRServicer(self._job_manager)
        self._server: Any = None
        self._running = False

    @property
    def job_manager(self) -> JobManager:
        """The JobManager instance used by this server."""
        return self._job_manager

    @property
    def is_running(self) -> bool:
        """Whether the gRPC server is currently running."""
        return self._running

    async def start(self, host: str = "0.0.0.0", port: int = 50051) -> None:
        """Start the gRPC server, binding to the specified host and port.

        Creates a grpc.aio.server, registers the UHCRServicer as a generic
        handler, binds to the given address, and starts accepting connections.

        Args:
            host: Network interface to bind to (default: "0.0.0.0").
            port: Port to listen on (default: 50051).

        Raises:
            RuntimeError: If grpcio is not installed.
            OSError: If the port cannot be bound.
        """
        if self._running:
            logger.warning("GRPCServer is already running")
            return

        self._server = grpc_aio.server()

        # Register the servicer as a generic handler so it works without
        # generated stubs.  When generated stubs are available, callers can
        # use add_UHCRServiceServicer_to_server() from the generated module.
        self._server.add_generic_rpc_handlers(
            [_UHCRGenericHandler(self._servicer)]
        )

        bind_address = f"{host}:{port}"
        bound_port = self._server.add_insecure_port(bind_address)
        if bound_port == 0:
            raise OSError(
                f"gRPC server failed to bind to {bind_address} "
                "(port unavailable or permission denied)"
            )

        await self._server.start()
        self._running = True
        logger.info("GRPCServer started on %s", bind_address)

    async def stop(self, grace_period: float = 30.0) -> None:
        """Gracefully stop the gRPC server.

        Waits up to ``grace_period`` seconds for in-flight RPCs to complete
        before force-terminating.

        Args:
            grace_period: Seconds to wait for in-flight RPCs (default: 30).
        """
        if not self._running or self._server is None:
            logger.warning("GRPCServer is not running")
            return

        logger.info(
            "GRPCServer stopping (grace_period=%.1fs)...", grace_period
        )
        await self._server.stop(grace=grace_period)
        self._server = None
        self._running = False
        logger.info("GRPCServer stopped")

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "GRPCServer":
        """Start the server when entering async context."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the server when exiting async context."""
        await self.stop()

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return f"GRPCServer(status={status})"


# ---------------------------------------------------------------------------
# Generic RPC handler (stub-free approach)
# ---------------------------------------------------------------------------


class _UHCRGenericHandler(grpc.ServiceRpcHandler if _GRPC_AVAILABLE else object):  # type: ignore[misc]
    """Generic RPC handler that routes calls to UHCRServicer methods.

    This handler allows the service to operate without pre-generated protobuf
    stubs by implementing grpc.ServiceRpcHandlers directly.
    """

    def __init__(self, servicer: UHCRServicer) -> None:
        self._servicer = servicer

    def service_name(self) -> str:
        return "uhcr.UHCRService"

    def service(self) -> Any:
        """Return the service descriptor (None when stubs are unavailable)."""
        return None


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _get_field(obj: Any, field: str, default: Any) -> Any:
    """Extract a field from a protobuf message or dict-like object.

    Supports:
    - Attribute access (protobuf messages, dataclasses, plain objects)
    - Dict-style access

    Args:
        obj: The object to extract the field from.
        field: The field name.
        default: Value to return if the field is absent.

    Returns:
        The field value, or ``default`` if not found.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(field, default)
    return getattr(obj, field, default)
