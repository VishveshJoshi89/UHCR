"""Serialization helpers for UHCR network subsystem.

Provides JSON and Protocol Buffers serialization for job payloads and results,
zero-copy tensor streaming, and payload validation with descriptive errors.

"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Iterator, Optional, Tuple

logger = logging.getLogger(__name__)

# Required fields for a valid job payload dict
_REQUIRED_JOB_FIELDS = ("payload",)

# Optional fields with their expected types
_OPTIONAL_JOB_FIELDS: Dict[str, type] = {
    "timeout": (int, float),  # type: ignore[assignment]
    "worker_id": str,
    "job_id": str,
}

# Default chunk size for tensor streaming (64KB per Requirement 16.3)
_DEFAULT_CHUNK_SIZE = 65536


# ---------------------------------------------------------------------------
# Protobuf availability detection
# ---------------------------------------------------------------------------

_PROTOBUF_AVAILABLE = False
try:
    from google.protobuf import json_format, struct_pb2  # noqa: F401

    _PROTOBUF_AVAILABLE = True
except ImportError:
    logger.debug("protobuf package not installed; Protocol Buffers serialization disabled")


# ===========================================================================
# JSON Serialization
# ===========================================================================


def serialize_job_to_json(job: Any) -> str:
    """Serialize a Job dataclass to a JSON string.

    Converts the Job's fields to a JSON-compatible dict and encodes
    the payload bytes as base64. Datetime fields are ISO-formatted.

    Args:
        job: A Job dataclass instance (from uhcr.network.jobs).

    Returns:
        A JSON string representation of the job.

    Raises:
        TypeError: If the job cannot be serialized.
    """
    data: Dict[str, Any] = {
        "id": job.id,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "payload": base64.b64encode(job.payload).decode("ascii"),
        "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
        "timeout_seconds": job.timeout_seconds,
    }

    # Optional fields
    if job.started_at is not None:
        data["started_at"] = job.started_at.isoformat()
    if job.completed_at is not None:
        data["completed_at"] = job.completed_at.isoformat()
    if job.result is not None:
        data["result"] = base64.b64encode(job.result).decode("ascii")
    if job.error is not None:
        data["error"] = job.error
    if job.worker_id is not None:
        data["worker_id"] = job.worker_id

    return json.dumps(data)


def deserialize_job_from_json(data: str) -> Dict[str, Any]:
    """Parse a JSON string and validate required job fields.

    Args:
        data: A JSON string representing a job payload.

    Returns:
        A dict with the parsed job fields.

    Raises:
        ValueError: If the JSON is malformed or required fields are missing.
    """
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    if not isinstance(parsed, dict):
        raise ValueError("Job JSON must be an object (dict), got: " + type(parsed).__name__)

    # Validate required fields
    for field in _REQUIRED_JOB_FIELDS:
        if field not in parsed:
            raise ValueError(f"Missing required field: '{field}'")

    # Validate payload is a string (base64-encoded)
    payload_val = parsed.get("payload")
    if payload_val is not None and not isinstance(payload_val, str):
        raise ValueError(
            f"Field 'payload' must be a base64-encoded string, got: {type(payload_val).__name__}"
        )

    # Validate optional field types
    if "timeout" in parsed:
        timeout_val = parsed["timeout"]
        if not isinstance(timeout_val, (int, float)):
            raise ValueError(
                f"Field 'timeout' must be a number, got: {type(timeout_val).__name__}"
            )
        if timeout_val <= 0:
            raise ValueError("Field 'timeout' must be a positive number")

    return parsed


def serialize_result_to_json(result: bytes) -> str:
    """Serialize computation result bytes to a JSON string with base64 encoding.

    Args:
        result: Raw result bytes from a completed job.

    Returns:
        A JSON string with the base64-encoded result.

    Raises:
        TypeError: If result is not bytes.
    """
    if not isinstance(result, (bytes, bytearray)):
        raise TypeError(f"Result must be bytes, got: {type(result).__name__}")

    encoded = base64.b64encode(result).decode("ascii")
    return json.dumps({"result": encoded, "encoding": "base64", "size": len(result)})


# ===========================================================================
# Protocol Buffers Serialization
# ===========================================================================


def serialize_job_to_proto(job: Any) -> bytes:
    """Serialize a Job dataclass to Protocol Buffers bytes.

    If the protobuf package is not installed, falls back to a JSON-encoded
    bytes representation with a warning.

    Args:
        job: A Job dataclass instance (from uhcr.network.jobs).

    Returns:
        Serialized bytes (protobuf if available, JSON bytes otherwise).
    """
    if not _PROTOBUF_AVAILABLE:
        logger.warning(
            "protobuf not installed; falling back to JSON serialization for job %s",
            getattr(job, "id", "unknown"),
        )
        return serialize_job_to_json(job).encode("utf-8")

    # Use protobuf Struct for generic serialization
    from google.protobuf import struct_pb2

    struct = struct_pb2.Struct()
    struct.update(
        {
            "id": job.id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "payload": base64.b64encode(job.payload).decode("ascii"),
            "submitted_at": job.submitted_at.isoformat() if job.submitted_at else "",
            "timeout_seconds": job.timeout_seconds,
        }
    )

    if job.started_at is not None:
        struct["started_at"] = job.started_at.isoformat()
    if job.completed_at is not None:
        struct["completed_at"] = job.completed_at.isoformat()
    if job.result is not None:
        struct["result"] = base64.b64encode(job.result).decode("ascii")
    if job.error is not None:
        struct["error"] = job.error
    if job.worker_id is not None:
        struct["worker_id"] = job.worker_id

    return struct.SerializeToString()


def deserialize_job_from_proto(data: bytes) -> Dict[str, Any]:
    """Deserialize Protocol Buffers bytes into a job dict.

    If the protobuf package is not installed, attempts to parse as JSON bytes.

    Args:
        data: Serialized protobuf bytes (or JSON bytes as fallback).

    Returns:
        A dict with the parsed job fields.

    Raises:
        ValueError: If deserialization fails.
    """
    if not _PROTOBUF_AVAILABLE:
        logger.warning("protobuf not installed; attempting JSON fallback deserialization")
        try:
            return deserialize_job_from_json(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise ValueError(f"Failed to deserialize (protobuf unavailable): {e}") from e

    from google.protobuf import struct_pb2

    struct = struct_pb2.Struct()
    try:
        struct.ParseFromString(data)
    except Exception as e:
        raise ValueError(f"Failed to parse protobuf data: {e}") from e

    # Convert protobuf Struct to plain dict
    result = dict(struct)
    if not result:
        raise ValueError("Deserialized protobuf data is empty")

    return result


# ===========================================================================
# Zero-Copy Tensor Path
# ===========================================================================


def serialize_tensor(data: bytes, contiguous: bool = True) -> bytes:
    """Serialize tensor data, using zero-copy when possible.

    If the tensor data is already in contiguous memory layout, returns
    the data directly without copying.
    Otherwise, creates a copy to ensure contiguous layout.

    Args:
        data: Raw tensor bytes.
        contiguous: Whether the data is already in contiguous memory layout.

    Returns:
        The tensor bytes (same reference if contiguous, copy otherwise).
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError(f"Tensor data must be bytes-like, got: {type(data).__name__}")

    if contiguous:
        # Zero-copy path: return bytes directly without copying
        if isinstance(data, memoryview):
            return bytes(data)
        return data
    else:
        # Non-contiguous: make a copy to ensure contiguous layout
        if isinstance(data, memoryview):
            return bytes(data)
        return bytes(data)


def chunk_tensor(data: bytes, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> Iterator[bytes]:
    """Yield chunks of tensor data for streaming transfer.

    Splits tensor data into chunks of the specified size for chunked
    transfer encoding.

    Args:
        data: Raw tensor bytes to chunk.
        chunk_size: Size of each chunk in bytes (default: 65536 = 64KB).

    Yields:
        Chunks of the tensor data, each at most chunk_size bytes.

    Raises:
        ValueError: If chunk_size is not positive.
        TypeError: If data is not bytes-like.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError(f"Tensor data must be bytes-like, got: {type(data).__name__}")

    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got: {chunk_size}")

    offset = 0
    length = len(data)

    while offset < length:
        end = min(offset + chunk_size, length)
        yield data[offset:end]
        offset = end


# ===========================================================================
# Payload Validation
# ===========================================================================


def validate_payload(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate a job payload dict, returning field-level error descriptions.

    Checks for required fields, correct types, and valid values.
    Returns descriptive errors.

    Args:
        data: A dict representing a job payload.

    Returns:
        A tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if not isinstance(data, dict):
        return False, "Payload must be a dict (JSON object)"

    # Check required field: payload
    if "payload" not in data:
        return False, "Missing required field: 'payload'"

    payload_val = data["payload"]

    # payload can be a base64 string or bytes
    if isinstance(payload_val, str):
        # Validate base64 encoding
        try:
            base64.b64decode(payload_val, validate=True)
        except Exception:
            return False, (
                "Field 'payload': invalid base64 encoding. "
                "The payload must be a valid base64-encoded string."
            )
        if len(payload_val) == 0:
            return False, "Field 'payload': must not be empty"
    elif isinstance(payload_val, bytes):
        if len(payload_val) == 0:
            return False, "Field 'payload': must not be empty"
    else:
        return False, (
            f"Field 'payload': expected a base64-encoded string or bytes, "
            f"got {type(payload_val).__name__}"
        )

    # Validate optional field: timeout
    if "timeout" in data:
        timeout_val = data["timeout"]
        if not isinstance(timeout_val, (int, float)):
            return False, (
                f"Field 'timeout': must be a number (int or float), "
                f"got {type(timeout_val).__name__}"
            )
        if timeout_val <= 0:
            return False, "Field 'timeout': must be a positive number"

    # Validate optional field: worker_id
    if "worker_id" in data:
        worker_id_val = data["worker_id"]
        if worker_id_val is not None and not isinstance(worker_id_val, str):
            return False, (
                f"Field 'worker_id': must be a string or null, "
                f"got {type(worker_id_val).__name__}"
            )

    # Validate optional field: job_id
    if "job_id" in data:
        job_id_val = data["job_id"]
        if job_id_val is not None and not isinstance(job_id_val, str):
            return False, (
                f"Field 'job_id': must be a string or null, "
                f"got {type(job_id_val).__name__}"
            )

    return True, None
