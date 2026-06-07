"""REST API endpoint handlers for UHCR network subsystem.

Provides aiohttp-based HTTP/REST handlers for job submission and status queries.
All responses use JSON serialization with descriptive error messages.

"""

from __future__ import annotations

import base64
import logging
from typing import Any

from uhcr.network.jobs import InvalidPayloadError, JobManager

logger = logging.getLogger(__name__)

try:
    from aiohttp import web
except ImportError:
    raise ImportError(
        "aiohttp is required for the REST API. "
        "Install it with: pip install aiohttp>=3.9.0"
    )

# Threshold for chunked transfer encoding (64KB)
_CHUNKED_THRESHOLD = 64 * 1024


async def submit_job(request: web.Request) -> web.Response:
    """Handle POST /jobs — submit a new computation job.

    Accepts a JSON body with:
        - payload (str): Base64-encoded IR or script bytes (required).
        - timeout (int): Maximum execution time in seconds (optional, default 300).

    Returns:
        201: JSON with job_id and status "queued".
        400: JSON with error description if payload is malformed.
    """
    job_manager: JobManager = request.app["job_manager"]

    # Parse JSON body
    try:
        body = await request.json()
    except Exception as e:
        return web.json_response(
            {"error": "Invalid JSON body", "detail": str(e)},
            status=400,
        )

    if not isinstance(body, dict):
        return web.json_response(
            {"error": "Request body must be a JSON object"},
            status=400,
        )

    # Validate required field: payload
    if "payload" not in body:
        return web.json_response(
            {"error": "Missing required field", "field": "payload",
             "detail": "The 'payload' field is required and must be a base64-encoded string"},
            status=400,
        )

    payload_str = body["payload"]
    if not isinstance(payload_str, str):
        return web.json_response(
            {"error": "Invalid field type", "field": "payload",
             "detail": "The 'payload' field must be a base64-encoded string"},
            status=400,
        )

    # Decode base64 payload
    try:
        payload_bytes = base64.b64decode(payload_str, validate=True)
    except Exception as e:
        return web.json_response(
            {"error": "Invalid base64 encoding", "field": "payload",
             "detail": f"Failed to decode payload: {e}"},
            status=400,
        )

    # Validate optional field: timeout
    timeout = body.get("timeout", 300)
    if not isinstance(timeout, (int, float)):
        return web.json_response(
            {"error": "Invalid field type", "field": "timeout",
             "detail": "The 'timeout' field must be an integer (seconds)"},
            status=400,
        )
    if timeout <= 0:
        return web.json_response(
            {"error": "Invalid field value", "field": "timeout",
             "detail": "The 'timeout' field must be a positive integer"},
            status=400,
        )

    # Submit job via JobManager
    try:
        job_id = job_manager.submit_job(payload=payload_bytes, timeout=float(timeout))
    except InvalidPayloadError as e:
        return web.json_response(
            {"error": "Invalid payload", "detail": e.reason},
            status=400,
        )
    except Exception as e:
        logger.exception("Unexpected error submitting job")
        return web.json_response(
            {"error": "Internal server error", "detail": str(e)},
            status=500,
        )

    return web.json_response(
        {"job_id": job_id, "status": "queued"},
        status=201,
    )


async def get_job(request: web.Request) -> web.Response:
    """Handle GET /jobs/{id} — get job status and result.

    Returns:
        200: JSON with job_id, status, submitted_at, and result.
        404: JSON with error if job not found.
    """
    job_manager: JobManager = request.app["job_manager"]
    job_id = request.match_info["id"]

    job = job_manager.get_job(job_id)
    if job is None:
        return web.json_response(
            {"error": "Job not found", "job_id": job_id},
            status=404,
        )

    # Build response payload
    response_data: dict[str, Any] = {
        "job_id": job.id,
        "status": job.status.value,
        "submitted_at": job.submitted_at.isoformat(),
    }

    # Include result if available
    if job.result is not None:
        result_b64 = base64.b64encode(job.result).decode("ascii")

        # For large results (>64KB), use chunked transfer encoding
        if len(job.result) > _CHUNKED_THRESHOLD:
            response_data["result"] = result_b64
            resp = web.StreamResponse(
                status=200,
                headers={"Content-Type": "application/json"},
            )
            resp.enable_chunked_encoding()
            await resp.prepare(request)

            import json
            chunk = json.dumps(response_data).encode("utf-8")
            await resp.write(chunk)
            await resp.write_eof()
            return resp

        response_data["result"] = result_b64
    else:
        response_data["result"] = None

    # Include error if present
    if job.error is not None:
        response_data["error"] = job.error

    return web.json_response(response_data, status=200)


def setup_routes(app: web.Application) -> None:
    """Register all REST API routes on an aiohttp Application.

    Routes registered:
        POST /jobs       — Submit a new job
        GET  /jobs/{id}  — Get job status and result

    Args:
        app: The aiohttp Application to register routes on.
    """
    app.router.add_post("/jobs", submit_job)
    app.router.add_get("/jobs/{id}", get_job)
