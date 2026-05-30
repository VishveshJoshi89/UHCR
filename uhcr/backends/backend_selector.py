from uhcr.backends.backend_base import Backend, get_registered_backends
from uhcr.hardware.platform_info import HardwareProfile

# Ensure all backends are imported so they register themselves
from uhcr.backends import cpu_generic
from uhcr.backends import cpu_avx2
from uhcr.backends import cpu_avx512
from uhcr.backends import cuda_backend

def select_backend(profile: HardwareProfile) -> Backend:
    """Selects the highest priority execution backend compatible with the host hardware profile."""
    backends = get_registered_backends()
    for backend in backends:
        if backend.supports(profile):
            return backend
            
    # Default baseline fallback (should always be cpu_generic)
    for backend in backends:
        if backend.name == "cpu_generic":
            return backend
            
    raise RuntimeError("No compatible execution backend found (even cpu_generic was missing!)")
