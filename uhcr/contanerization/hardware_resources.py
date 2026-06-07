"""Hardware-aware resource calculation for Kubernetes manifests."""

import sys
from typing import Optional, Tuple

from uhcr.hardware.platform_info import detect_platform


def compute_k8s_resources() -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Compute Kubernetes CPU and memory resource values from detected hardware.

    Uses uhcr.hardware.platform_info.detect_platform() to read the current
    machine's CPU core count and total memory, then derives resource
    requests and limits suitable for a Kubernetes container spec.

    Returns:
        A tuple of (cpu_request, cpu_limit, memory_request, memory_limit).
        All values are Optional[str] in Kubernetes resource quantity format.
        Returns (None, None, None, None) when hardware detection is incomplete
        (0 cores or 0 total memory).
    """
    profile = detect_platform()
    cpu_cores = profile.cpu.cores
    total_memory_bytes = profile.memory.total_bytes

    if cpu_cores > 0 and total_memory_bytes > 0:
        cpu_request = f"{cpu_cores}"
        cpu_limit = f"{cpu_cores}"
        memory_request_mib = int(total_memory_bytes * 0.5 / 1048576)
        memory_limit_mib = int(total_memory_bytes * 0.75 / 1048576)
        memory_request = f"{memory_request_mib}Mi"
        memory_limit = f"{memory_limit_mib}Mi"
        return cpu_request, cpu_limit, memory_request, memory_limit
    else:
        print(
            "Warning: Hardware detection returned incomplete data "
            "(0 cores or 0 memory). Resource requests/limits will be omitted.",
            file=sys.stderr,
        )
        return None, None, None, None
