from typing import Callable
from uhcr.compiler.ir import Function
from uhcr.hardware.platform_info import HardwareProfile
from abc import ABC, abstractmethod

class Backend(ABC):
    """Abstract base class for all hardware-specific execution backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """Higher priority backends are preferred over lower priority ones (e.g. CUDA > AVX2 > Generic)."""
        pass

    @abstractmethod
    def supports(self, profile: HardwareProfile) -> bool:
        """Returns True if the backend is compatible with the detected hardware profile."""
        pass

    @abstractmethod
    def compile(self, func: Function) -> Callable:
        """Compiles the IR Function into a callable native function."""
        pass


_backends_registry: list[Backend] = []

def register_backend(backend: Backend):
    if backend not in _backends_registry:
        _backends_registry.append(backend)

def get_registered_backends() -> list[Backend]:
    return sorted(_backends_registry, key=lambda b: b.priority, reverse=True)
