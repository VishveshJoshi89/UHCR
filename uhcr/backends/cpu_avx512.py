from uhcr.backends.backend_base import register_backend
from uhcr.backends.cpu_avx2 import CPUAVX2Backend
from uhcr.compiler.ir import Function
from uhcr.hardware.platform_info import HardwareProfile

class CPUAVX512Backend(CPUAVX2Backend):
    """AVX-512 execution path (falls back to AVX2 compiler, demonstrating capability-driven selection)."""
    @property
    def name(self) -> str:
        return "cpu_avx512"

    @property
    def priority(self) -> int:
        return 10

    def supports(self, profile: HardwareProfile) -> bool:
        # Requires AVX-512 Foundation flag
        return profile.cpu.has_avx512

    # Inherits compile() from CPUAVX2Backend for backward compatibility

register_backend(CPUAVX512Backend())
