"""Distributed coordinator for UHCR network subsystem.

Manages worker registration, heartbeat tracking, health monitoring, and
job assignment across a pool of worker nodes.

Thread-safe using threading.Lock for all registry mutations.

"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class WorkerInfo:
    """Represents a registered worker node in the UHCR distributed system.

    Attributes:
        id: Unique worker identifier (UUID4 string).
        address: Worker network address in "host:port" format.
        architecture: CPU architecture string (e.g. "x86_64", "aarch64").
        simd_capabilities: List of SIMD feature strings (e.g. ["avx2", "neon"]).
        available_memory_mb: Available memory on the worker in megabytes.
        last_heartbeat: UTC timestamp of the most recent heartbeat.
        active_jobs: Number of jobs currently executing on this worker.
        healthy: Whether the worker is considered healthy.
    """

    id: str
    address: str
    architecture: str
    simd_capabilities: List[str]
    available_memory_mb: int
    last_heartbeat: datetime
    active_jobs: int = 0
    healthy: bool = True


class CoordinatorNode:
    """Coordinates job distribution across a pool of registered worker nodes.

    Supports up to 64+ concurrent worker connections. All registry operations
    are thread-safe via an internal threading.Lock.

    Scheduling strategies:
    - "round-robin": Cycle through healthy workers in registration order.
    - "least-loaded": Assign to the healthy worker with the fewest active jobs.
    - "hardware-affinity": Prefer workers whose architecture matches the job's
      requirements (falls back to least-loaded when no affinity match exists).

    """

    def __init__(self) -> None:
        """Initialize the CoordinatorNode with an empty worker registry."""
        self._workers: Dict[str, WorkerInfo] = {}
        self._lock = threading.Lock()
        # Round-robin cursor: index into the ordered list of worker IDs
        self._rr_index: int = 0

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def register_worker(self, worker_info: WorkerInfo) -> str:
        """Register a new worker node and return its assigned worker ID.

        If the WorkerInfo already has a non-empty id, that id is used as-is.
        Otherwise a new UUID4 is generated and assigned.

        Args:
            worker_info: WorkerInfo describing the worker to register.

        Returns:
            The worker ID string (UUID4).
        """
        if not worker_info.id:
            worker_info.id = str(uuid.uuid4())

        with self._lock:
            self._workers[worker_info.id] = worker_info

        return worker_info.id

    def deregister_worker(self, worker_id: str) -> None:
        """Remove a worker from the registry.

        Silently does nothing if the worker_id is not found.

        Args:
            worker_id: The worker ID to remove.
        """
        with self._lock:
            self._workers.pop(worker_id, None)

    # ------------------------------------------------------------------
    # Heartbeat and health
    # ------------------------------------------------------------------

    def update_heartbeat(self, worker_id: str) -> None:
        """Update the last_heartbeat timestamp for a worker to now (UTC).

        Also marks the worker as healthy if it was previously unhealthy.

        Args:
            worker_id: The worker ID whose heartbeat should be refreshed.

        Raises:
            KeyError: If the worker_id is not registered.
        """
        with self._lock:
            worker = self._workers.get(worker_id)
            if worker is None:
                raise KeyError(f"Worker not found: {worker_id}")
            worker.last_heartbeat = datetime.now(timezone.utc)
            worker.healthy = True

    def check_worker_health(self, threshold_seconds: float = 30.0) -> List[str]:
        """Identify workers that have not sent a heartbeat within the threshold.

        Workers whose last_heartbeat is older than threshold_seconds are marked
        unhealthy and their IDs are returned.

        Args:
            threshold_seconds: Maximum allowed seconds since last heartbeat
                before a worker is considered unhealthy. Default: 30.0.

        Returns:
            List of worker IDs that are now (or remain) unhealthy.
        """
        now = datetime.now(timezone.utc)
        unhealthy: List[str] = []

        with self._lock:
            for worker in self._workers.values():
                elapsed = (now - worker.last_heartbeat).total_seconds()
                if elapsed > threshold_seconds:
                    worker.healthy = False
                    unhealthy.append(worker.id)

        return unhealthy

    # ------------------------------------------------------------------
    # Job assignment
    # ------------------------------------------------------------------

    def assign_job(
        self,
        job_id: str,
        strategy: str = "round-robin",
    ) -> Optional[str]:
        """Assign a job to a healthy worker using the specified strategy.

        Increments the chosen worker's active_jobs counter.

        Args:
            job_id: The job identifier (used for hardware-affinity hint parsing).
            strategy: Scheduling strategy — one of "round-robin",
                "least-loaded", or "hardware-affinity". Defaults to
                "round-robin".

        Returns:
            The worker_id of the assigned worker, or None if no healthy
            workers are available.
        """
        with self._lock:
            healthy = [w for w in self._workers.values() if w.healthy]
            if not healthy:
                return None

            if strategy == "round-robin":
                chosen = self._assign_round_robin(healthy)
            elif strategy == "least-loaded":
                chosen = self._assign_least_loaded(healthy)
            elif strategy == "hardware-affinity":
                chosen = self._assign_hardware_affinity(healthy, job_id)
            else:
                # Unknown strategy — fall back to round-robin
                chosen = self._assign_round_robin(healthy)

            chosen.active_jobs += 1
            return chosen.id

    def _assign_round_robin(self, healthy: List[WorkerInfo]) -> WorkerInfo:
        """Select the next worker in round-robin order.

        Must be called under self._lock.
        """
        # Clamp the cursor to the current healthy pool size
        self._rr_index = self._rr_index % len(healthy)
        chosen = healthy[self._rr_index]
        self._rr_index = (self._rr_index + 1) % len(healthy)
        return chosen

    def _assign_least_loaded(self, healthy: List[WorkerInfo]) -> WorkerInfo:
        """Select the healthy worker with the fewest active jobs.

        Ties are broken by the order workers appear in the list (i.e. earliest
        registered worker wins).

        Must be called under self._lock.
        """
        return min(healthy, key=lambda w: w.active_jobs)

    def _assign_hardware_affinity(
        self, healthy: List[WorkerInfo], job_id: str
    ) -> WorkerInfo:
        """Select a worker whose architecture or SIMD capabilities best match
        the job's requirements.

        The job_id may encode hints in the form "arch:x86_64" or
        "simd:avx512" (colon-separated key:value pairs separated by
        underscores). Workers matching the hint are preferred; if none match,
        falls back to least-loaded selection.

        Must be called under self._lock.
        """
        # Parse hints from job_id (e.g. "arch:x86_64", "simd:avx512")
        arch_hint: Optional[str] = None
        simd_hint: Optional[str] = None

        for part in job_id.replace("-", "_").split("_"):
            if part.startswith("arch:"):
                arch_hint = part[5:]
            elif part.startswith("simd:"):
                simd_hint = part[5:]

        # Filter workers that match the hints
        candidates = healthy
        if arch_hint:
            arch_matches = [w for w in healthy if w.architecture == arch_hint]
            if arch_matches:
                candidates = arch_matches

        if simd_hint:
            simd_matches = [w for w in candidates if simd_hint in w.simd_capabilities]
            if simd_matches:
                candidates = simd_matches

        # Among matching candidates, pick the least-loaded
        return self._assign_least_loaded(candidates)

    # ------------------------------------------------------------------
    # Registry queries
    # ------------------------------------------------------------------

    def list_workers(self, healthy_only: bool = False) -> List[WorkerInfo]:
        """Return a snapshot of registered workers.

        Args:
            healthy_only: If True, only return workers currently marked healthy.

        Returns:
            List of WorkerInfo instances (copies of the registry state).
        """
        with self._lock:
            workers = list(self._workers.values())

        if healthy_only:
            workers = [w for w in workers if w.healthy]

        return workers

    def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """Retrieve a single worker by ID.

        Args:
            worker_id: The worker ID to look up.

        Returns:
            The WorkerInfo instance, or None if not found.
        """
        with self._lock:
            return self._workers.get(worker_id)
