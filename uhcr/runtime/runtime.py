import hashlib
import threading
from typing import Callable, Dict
from uhcr.hardware.platform_info import detect_platform, HardwareProfile
from uhcr.backends.backend_selector import select_backend
from uhcr.compiler.ir import Function

class UHCRRuntime:
    """The central orchestrator of the Universal Hardware-Aware Compute Runtime."""
    def __init__(self):
        self.profile: HardwareProfile = detect_platform()
        self._cache: Dict[str, Callable] = {}
        self._cache_lock = threading.Lock()
        self.optimize = True  # Enable IR optimization by default

    def get_profile(self) -> HardwareProfile:
        """Returns the detected hardware profile of the host system."""
        return self.profile

    def compile(self, func: Function) -> Callable:
        """Compiles the function using the best available backend and caches the result."""
        # Build a cache key that includes function structure, not just signature
        ir_hash = self._hash_function(func)
        cache_key = f"{func.name}-{func.return_type.value}-[" + ",".join([arg.type.value for arg in func.arguments]) + f"]-{ir_hash}"
        
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            # Run optimization passes if enabled
            if self.optimize:
                from uhcr.compiler.passes import run_default_passes
                func = run_default_passes(func)
            
            # Select compatible backend based on function requirements
            backend = self._select_backend_for(func)
            
            # Compile using selected backend
            compiled_fn = backend.compile(func)
            
            # Cache it
            self._cache[cache_key] = compiled_fn
            return compiled_fn

    def _select_backend_for(self, func: Function):
        """Select the best backend for a specific function based on its IR content."""
        from uhcr.compiler.ir import Opcode, Type
        
        # Analyze what the function needs
        needs_gpu = False
        for block in func.blocks:
            for inst in block.instructions:
                # Only route to CUDA if the function uses GPU-friendly operations
                # with pointer arguments (tensor data)
                if inst.opcode in (Opcode.MATMUL,) and any(
                    a.type == Type.PTR for a in func.arguments
                ):
                    needs_gpu = True
                elif inst.opcode in (Opcode.VADD, Opcode.VSUB, Opcode.VMUL, Opcode.VDIV, Opcode.VFMADD):
                    if any(a.type == Type.PTR for a in func.arguments):
                        needs_gpu = True
        
        if needs_gpu and self.profile.gpu.cuda_available:
            # Use CUDA for GPU-friendly workloads
            return select_backend(self.profile)
        
        # For scalar/non-GPU functions, skip CUDA and use CPU backends
        from uhcr.backends.backend_base import get_registered_backends
        backends = get_registered_backends()
        for backend in backends:
            if backend.name == "cuda":
                continue  # Skip CUDA for scalar functions
            if backend.supports(self.profile):
                return backend
        
        return select_backend(self.profile)  # Fallback

    @staticmethod
    def _hash_function(func: Function) -> str:
        """Produces a structural hash of the IR function for cache keying."""
        import hashlib
        h = hashlib.md5()
        h.update(func.name.encode())
        h.update(func.return_type.value.encode())
        for arg in func.arguments:
            h.update(arg.type.value.encode())
        for block in func.blocks:
            h.update(block.label.encode())
            for inst in block.instructions:
                h.update(inst.opcode.value.encode())
                h.update(inst.type.value.encode())
        return h.hexdigest()[:12]

    def clear_cache(self):
        """Clears all compiled function caches."""
        with self._cache_lock:
            # If any native compilation wrapper holds executable memory pointers,
            # letting python garbage-collect the wrappers will free the executable memory.
            self._cache.clear()
