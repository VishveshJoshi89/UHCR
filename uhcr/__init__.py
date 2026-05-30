"""
UHCR — Universal Hardware-Aware Compute Runtime

A modular, capability-driven execution stack that sits between
applications and OS/hardware layers to deliver near-native performance
with portable developer APIs.

Usage:
    import uhcr

    # Detect hardware
    profile = uhcr.detect()
    print(profile)

    # Create tensors and compute
    a = uhcr.tensor([[1.0, 2.0], [3.0, 4.0]])
    b = uhcr.tensor([[5.0, 6.0], [7.0, 8.0]])
    c = a.matmul(b)  # Dispatches to best available backend (AVX2, CUDA, etc.)
"""

__version__ = "v1"
__author__ = "Vishvesh Joshi"

_runtime_instance = None


def detect():
    """Detect hardware capabilities and return a HardwareProfile."""
    from uhcr.hardware.platform_info import detect_platform
    return detect_platform()


def get_runtime():
    """Get or create the global UHCR runtime instance."""
    global _runtime_instance
    if _runtime_instance is None:
        from uhcr.runtime.runtime import UHCRRuntime
        _runtime_instance = UHCRRuntime()
    return _runtime_instance


def tensor(data, dtype=None):
    """Create a UHCR Tensor from nested lists or a flat buffer."""
    from uhcr.api.tensor import Tensor
    from uhcr.compiler.ir import Type
    if dtype is None:
        dtype = Type.F32
    return Tensor(data, dtype=dtype)


def compile_ir(ir_module):
    """Compile an IR module using the best available backend."""
    rt = get_runtime()
    return rt.compile(ir_module)


def jit(func=None, **kwargs):
    """JIT-compile a Python function to native code.

    Usage:
        @uhcr.jit
        def add(a, b):
            return a + b

        @uhcr.jit(eager=True)
        def multiply(x, y):
            return x * y
    """
    from uhcr.frontend.decorator import jit as _jit
    return _jit(func, **kwargs)
