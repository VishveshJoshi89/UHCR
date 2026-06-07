"""Network subsystem for UHCR production infrastructure.

The network subsystem provides the dual-protocol server layer enabling UHCR
to operate as a distributed computation service. It coordinates five components:

- ProtocolServer: Main server orchestrating REST (aiohttp) and gRPC listeners
- JobManager: Job lifecycle management (submit, queue, run, complete/fail, timeout)
- HealthService: HTTP and gRPC health checking (liveness, readiness)
- CoordinatorNode: Distributed job scheduling across registered workers
- WorkerNode: Job execution and hardware profile reporting
- Serialization helpers for Protocol Buffers and JSON payloads
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uhcr.network.server import ProtocolServer
    from uhcr.network.jobs import JobManager
    from uhcr.network.health import HealthService
    from uhcr.network.coordinator import CoordinatorNode
    from uhcr.network.worker import WorkerNode

__all__ = [
    "ProtocolServer",
    "JobManager",
    "HealthService",
    "CoordinatorNode",
    "WorkerNode",
]
