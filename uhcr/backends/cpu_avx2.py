import ctypes
import platform as _platform
from typing import Callable
from uhcr.backends.backend_base import Backend, register_backend
from uhcr.compiler.ir import Type, Function
from uhcr.compiler.x86_64.codegen import X86_64CodeGenerator
from uhcr.compiler.x86_64.executable_memory import ExecutableMemory
from uhcr.hardware.platform_info import HardwareProfile

class CPUAVX2Backend(Backend):
    """AVX2-optimized execution path translating UHCR IR to native AVX2 SIMD machine code."""
    @property
    def name(self) -> str:
        return "cpu_avx2"

    @property
    def priority(self) -> int:
        return 5

    def supports(self, profile: HardwareProfile) -> bool:
        # Requires AVX2 CPU flag
        return profile.cpu.has_avx2

    def compile(self, func: Function) -> Callable:
        # Safety check before AVX2 compilation
        try:
            from uhcr.native import get_safety_monitor, SafetyStatus
            monitor = get_safety_monitor()
            if monitor and monitor.is_enabled():
                # Check CPU temperature
                cpu_status = monitor.check_cpu_temperature()
                if cpu_status != SafetyStatus.OK:
                    raise RuntimeError(
                        f"CPU temperature too high for AVX2 compilation: {monitor.get_last_error()}"
                    )
                
                # Check for emergency stop
                if monitor.is_emergency_stopped():
                    raise RuntimeError("Emergency stop active - cannot compile AVX2 code")
        except ImportError:
            pass
        
        # AVX2 backend compiles to native machine code using X86_64CodeGenerator
        codegen = X86_64CodeGenerator(func)
        code_bytes = codegen.compile()
        
        # Allocate executable memory and write bytes
        mem = ExecutableMemory(len(code_bytes))
        mem.write(code_bytes)
        
        # Deduce argument types
        arg_types = []
        for arg in func.arguments:
            if arg.type == Type.PTR:
                arg_types.append(ctypes.c_void_p)
            elif arg.type == Type.I32:
                arg_types.append(ctypes.c_int32)
            elif arg.type == Type.I64:
                arg_types.append(ctypes.c_int64)
            elif arg.type == Type.F32:
                arg_types.append(ctypes.c_float)
            elif arg.type == Type.F64:
                arg_types.append(ctypes.c_double)

        # Deduce return type
        ret_type = None
        if func.return_type == Type.I32:
            ret_type = ctypes.c_int32
        elif func.return_type == Type.I64:
            ret_type = ctypes.c_int64
        elif func.return_type == Type.F32:
            ret_type = ctypes.c_float
        elif func.return_type == Type.F64:
            ret_type = ctypes.c_double
            
        proto = ctypes.WINFUNCTYPE(ret_type, *arg_types) if _platform.system() == "Windows" else ctypes.CFUNCTYPE(ret_type, *arg_types)
        native_fn = mem.get_function(proto)
        
        # Wrap native function to bind executable memory life cycle
        def native_wrapper(*args):
            resolved = [arg.address if hasattr(arg, "address") else arg for arg in args]
            return native_fn(*resolved)
        native_wrapper._mem_ref = mem
        return native_wrapper

register_backend(CPUAVX2Backend())
