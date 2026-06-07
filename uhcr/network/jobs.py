"""Job manager for UHCR network subsystem.

Manages job lifecycle: submit → queue → run → complete/fail/timeout.
Thread-safe concurrent job management with configurable timeouts.

"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class JobStatus(Enum):
    """Job lifecycle states.

    State machine transitions:
        queued → running → completed | failed | timeout
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


# Valid state transitions for the job state machine
_VALID_TRANSITIONS: Dict[JobStatus, List[JobStatus]] = {
    JobStatus.QUEUED: [JobStatus.RUNNING],
    JobStatus.RUNNING: [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMEOUT],
    # Terminal states — no transitions allowed
    JobStatus.COMPLETED: [],
    JobStatus.FAILED: [],
    JobStatus.TIMEOUT: [],
}

# Terminal states that cannot be changed
_TERMINAL_STATES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMEOUT})


class InvalidTransitionError(Exception):
    """Raised when an invalid job state transition is attempted."""

    def __init__(self, job_id: str, current: JobStatus, target: JobStatus):
        self.job_id = job_id
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid transition for job {job_id}: "
            f"{current.value} → {target.value}"
        )


class InvalidPayloadError(Exception):
    """Raised when a job payload fails validation."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Invalid job payload: {reason}")


@dataclass
class Job:
    """Represents a computation job in the UHCR system.

    Attributes:
        id: UUID4 identifier assigned at submission.
        status: Current lifecycle state.
        payload: Serialized IR or script bytes.
        submitted_at: UTC timestamp when the job was submitted.
        started_at: UTC timestamp when execution began (None if not started).
        completed_at: UTC timestamp when execution finished (None if not done).
        result: Computation result bytes (None until completed).
        error: Error description (None unless failed).
        timeout_seconds: Maximum execution time before timeout cancellation.
        worker_id: Assigned worker node identifier (None until assigned).
    """

    id: str
    status: JobStatus
    payload: bytes
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[bytes] = None
    error: Optional[str] = None
    timeout_seconds: float = 300.0
    worker_id: Optional[str] = None


# Minimum payload size — an empty payload is invalid
_MIN_PAYLOAD_SIZE = 1

# Magic bytes for recognized payload formats.
# UHCR IR serialized format starts with these bytes.
_IR_MAGIC = b"UHCR"
# Python script payloads are also accepted (UTF-8 text)
_SCRIPT_MAGIC_PREFIXES = (b"#!", b"import ", b"from ", b"def ", b"class ")


class JobManager:
    """Manages job lifecycle with thread-safe concurrent access.

    The JobManager handles:
    - Job submission with UUID4 identifier assignment
    - Payload validation against supported IR format
    - Status tracking with state machine enforcement
    - Timeout cancellation (configurable per-job, default 300s)
    - Result storage for completed jobs
    - Thread-safe concurrent job management

    """

    def __init__(self, default_timeout: float = 300.0) -> None:
        """Initialize the JobManager.

        Args:
            default_timeout: Default timeout in seconds for jobs (default: 300).
        """
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._default_timeout = default_timeout

    @property
    def default_timeout(self) -> float:
        """Default timeout in seconds for new jobs."""
        return self._default_timeout

    def submit_job(self, payload: bytes, timeout: float = 0) -> str:
        """Submit a new job for execution.

        Validates the payload, assigns a UUID4 identifier, and queues the job.

        Args:
            payload: Serialized IR or script bytes.
            timeout: Maximum execution time in seconds. Uses default if 0.

        Returns:
            The assigned job ID (UUID4 string).

        Raises:
            InvalidPayloadError: If the payload fails validation.
            ValueError: If timeout is negative.
        """
        # Validate payload
        self._validate_payload(payload)

        # Resolve timeout
        effective_timeout = timeout if timeout > 0 else self._default_timeout
        if effective_timeout < 0:
            raise ValueError("Timeout must be non-negative")

        # Generate unique ID
        job_id = str(uuid.uuid4())

        # Create job
        job = Job(
            id=job_id,
            status=JobStatus.QUEUED,
            payload=payload,
            submitted_at=datetime.now(timezone.utc),
            timeout_seconds=effective_timeout,
        )

        with self._lock:
            self._jobs[job_id] = job

        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by its ID.

        Args:
            job_id: The UUID4 job identifier.

        Returns:
            The Job instance, or None if not found.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def get_status(self, job_id: str) -> Optional[JobStatus]:
        """Get the current status of a job.

        Args:
            job_id: The UUID4 job identifier.

        Returns:
            The current JobStatus, or None if the job is not found.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return job.status

    def start_job(self, job_id: str, worker_id: str) -> None:
        """Transition a job from queued to running.

        Args:
            job_id: The UUID4 job identifier.
            worker_id: The worker node assigned to execute this job.

        Raises:
            KeyError: If the job is not found.
            InvalidTransitionError: If the job is not in QUEUED state.
        """
        with self._lock:
            job = self._get_job_or_raise(job_id)
            self._transition(job, JobStatus.RUNNING)
            job.worker_id = worker_id
            job.started_at = datetime.now(timezone.utc)

    def complete_job(self, job_id: str, result: bytes) -> None:
        """Mark a job as completed with its result.

        Args:
            job_id: The UUID4 job identifier.
            result: The computation result bytes.

        Raises:
            KeyError: If the job is not found.
            InvalidTransitionError: If the job is not in RUNNING state.
        """
        with self._lock:
            job = self._get_job_or_raise(job_id)
            self._transition(job, JobStatus.COMPLETED)
            job.result = result
            job.completed_at = datetime.now(timezone.utc)

    def fail_job(self, job_id: str, error: str) -> None:
        """Mark a job as failed with an error description.

        Args:
            job_id: The UUID4 job identifier.
            error: Description of the failure.

        Raises:
            KeyError: If the job is not found.
            InvalidTransitionError: If the job is not in RUNNING state.
        """
        with self._lock:
            job = self._get_job_or_raise(job_id)
            self._transition(job, JobStatus.FAILED)
            job.error = error
            job.completed_at = datetime.now(timezone.utc)

    def cancel_job(self, job_id: str) -> None:
        """Cancel a job due to timeout or user request.

        Jobs in QUEUED or RUNNING state can be cancelled (set to TIMEOUT).
        Jobs already in a terminal state are silently ignored.

        Args:
            job_id: The UUID4 job identifier.

        Raises:
            KeyError: If the job is not found.
        """
        with self._lock:
            job = self._get_job_or_raise(job_id)

            # Already terminal — nothing to do
            if job.status in _TERMINAL_STATES:
                return

            if job.status == JobStatus.QUEUED:
                # Queued jobs transition to RUNNING first, then TIMEOUT
                # per state machine: queued → running → timeout
                job.status = JobStatus.RUNNING
                job.started_at = job.started_at or datetime.now(timezone.utc)

            # Now transition running → timeout
            self._transition(job, JobStatus.TIMEOUT)
            job.error = "Job cancelled (timeout)"
            job.completed_at = datetime.now(timezone.utc)

    def list_jobs(self, status: Optional[JobStatus] = None) -> List[Job]:
        """List all jobs, optionally filtered by status.

        Args:
            status: If provided, only return jobs with this status.

        Returns:
            List of matching Job instances.
        """
        with self._lock:
            if status is None:
                return list(self._jobs.values())
            return [j for j in self._jobs.values() if j.status == status]

    def job_count(self) -> int:
        """Return the total number of tracked jobs."""
        with self._lock:
            return len(self._jobs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_job_or_raise(self, job_id: str) -> Job:
        """Retrieve a job or raise KeyError. Must be called under lock."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        return job

    def _transition(self, job: Job, target: JobStatus) -> None:
        """Enforce state machine transition. Must be called under lock.

        Raises:
            InvalidTransitionError: If the transition is not valid.
        """
        valid_targets = _VALID_TRANSITIONS.get(job.status, [])
        if target not in valid_targets:
            raise InvalidTransitionError(job.id, job.status, target)
        job.status = target

    @staticmethod
    def _validate_payload(payload: bytes) -> None:
        """Validate that the payload is a supported format.

        Accepts:
        - UHCR serialized IR (starts with b"UHCR" magic bytes)
        - Python scripts (starts with common Python prefixes)
        - Any non-empty bytes payload (generic binary IR)

        Raises:
            InvalidPayloadError: If the payload is empty or invalid.
        """
        if not isinstance(payload, bytes):
            raise InvalidPayloadError("Payload must be bytes")

        if len(payload) < _MIN_PAYLOAD_SIZE:
            raise InvalidPayloadError("Payload must not be empty")
