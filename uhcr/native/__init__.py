"""UHCR Native Safety Layer - Python bindings."""

import ctypes
import os
import platform
from pathlib import Path
from typing import Optional

# Find the native library
def _find_library() -> Optional[Path]:
    """Locate the compiled safety monitor library."""
    system = platform.system()
    if system == "Windows":
        lib_name = "safety_monitor.dll"
    elif system == "Darwin":
        lib_name = "safety_monitor.dylib"
    else:
        lib_name = "safety_monitor.so"
    
    # Check in same directory as this file
    lib_path = Path(__file__).parent / lib_name
    if lib_path.exists():
        return lib_path
    
    # Check in uhcr/lib directory
    lib_path = Path(__file__).parent.parent / "lib" / lib_name
    if lib_path.exists():
        return lib_path
    
    return None

# Safety status codes
class SafetyStatus:
    OK = 0
    MEMORY_OVERFLOW = 1
    THERMAL_LIMIT = 2
    POWER_LIMIT = 3
    TIMEOUT = 4
    INVALID_OPERATION = 5
    RESOURCE_EXHAUSTED = 6
    HARDWARE_ERROR = 7

class SafetyMonitor:
    """Python wrapper for C++ SafetyMonitor."""
    
    def __init__(self):
        self._lib = None
        self._handle = None
        self._load_library()
    
    def _load_library(self):
        """Load the native safety monitor library."""
        lib_path = _find_library()
        if lib_path is None:
            # Library not compiled yet - run in Python-only mode
            import warnings
            warnings.warn(
                "Native safety monitor not found. Running without hardware protection. "
                "Run 'python uhcr/native/build_native.py' to compile the safety layer.",
                RuntimeWarning
            )
            return
        
        try:
            self._lib = ctypes.CDLL(str(lib_path))
            self._setup_functions()
            self._handle = self._lib.uhcr_safety_create()
            self._lib.uhcr_safety_initialize(self._handle)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to load native safety monitor: {e}", RuntimeWarning)
    
    def _setup_functions(self):
        """Setup function signatures for ctypes."""
        if not self._lib:
            return
        
        # Create/destroy
        self._lib.uhcr_safety_create.restype = ctypes.c_void_p
        self._lib.uhcr_safety_destroy.argtypes = [ctypes.c_void_p]
        
        # Initialize/shutdown
        self._lib.uhcr_safety_initialize.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_initialize.restype = ctypes.c_int
        self._lib.uhcr_safety_shutdown.argtypes = [ctypes.c_void_p]
        
        # Enable/disable
        self._lib.uhcr_safety_enable.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_disable.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_is_enabled.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_is_enabled.restype = ctypes.c_int
        
        # Memory validation
        self._lib.uhcr_safety_validate_memory.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int
        ]
        self._lib.uhcr_safety_validate_memory.restype = ctypes.c_int
        
        # Temperature monitoring
        self._lib.uhcr_safety_check_cpu_temp.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_check_cpu_temp.restype = ctypes.c_int
        self._lib.uhcr_safety_check_gpu_temp.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_check_gpu_temp.restype = ctypes.c_int
        
        self._lib.uhcr_safety_get_cpu_temp.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_get_cpu_temp.restype = ctypes.c_uint32
        self._lib.uhcr_safety_get_gpu_temp.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_get_gpu_temp.restype = ctypes.c_uint32
        
        # Resource monitoring
        self._lib.uhcr_safety_get_memory_usage.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_get_memory_usage.restype = ctypes.c_size_t
        
        # Emergency stop
        self._lib.uhcr_safety_emergency_stop.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_is_emergency_stopped.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_is_emergency_stopped.restype = ctypes.c_int
        
        # Error handling
        self._lib.uhcr_safety_get_error.argtypes = [ctypes.c_void_p]
        self._lib.uhcr_safety_get_error.restype = ctypes.c_char_p
        self._lib.uhcr_safety_clear_error.argtypes = [ctypes.c_void_p]
        
        # Configuration
        self._lib.uhcr_safety_set_max_memory.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self._lib.uhcr_safety_set_max_cpu_temp.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._lib.uhcr_safety_set_max_gpu_temp.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    
    def __del__(self):
        """Cleanup native resources."""
        if self._lib and self._handle:
            self._lib.uhcr_safety_destroy(self._handle)
    
    def enable(self):
        """Enable hardware safety monitoring."""
        if self._lib and self._handle:
            self._lib.uhcr_safety_enable(self._handle)
    
    def disable(self):
        """Disable hardware safety monitoring."""
        if self._lib and self._handle:
            self._lib.uhcr_safety_disable(self._handle)
    
    def is_enabled(self) -> bool:
        """Check if monitoring is enabled."""
        if self._lib and self._handle:
            return bool(self._lib.uhcr_safety_is_enabled(self._handle))
        return False
    
    def validate_memory(self, ptr: int, size: int, is_write: bool = False) -> int:
        """Validate memory access."""
        if self._lib and self._handle:
            return self._lib.uhcr_safety_validate_memory(
                self._handle, ptr, size, int(is_write)
            )
        return SafetyStatus.OK
    
    def check_cpu_temperature(self) -> int:
        """Check CPU temperature against limits."""
        if self._lib and self._handle:
            return self._lib.uhcr_safety_check_cpu_temp(self._handle)
        return SafetyStatus.OK
    
    def check_gpu_temperature(self) -> int:
        """Check GPU temperature against limits."""
        if self._lib and self._handle:
            return self._lib.uhcr_safety_check_gpu_temp(self._handle)
        return SafetyStatus.OK
    
    def get_cpu_temperature(self) -> int:
        """Get current CPU temperature in Celsius."""
        if self._lib and self._handle:
            return self._lib.uhcr_safety_get_cpu_temp(self._handle)
        return 0
    
    def get_gpu_temperature(self) -> int:
        """Get current GPU temperature in Celsius."""
        if self._lib and self._handle:
            return self._lib.uhcr_safety_get_gpu_temp(self._handle)
        return 0
    
    def get_memory_usage(self) -> int:
        """Get current memory usage in bytes."""
        if self._lib and self._handle:
            return self._lib.uhcr_safety_get_memory_usage(self._handle)
        return 0
    
    def emergency_stop(self):
        """Trigger emergency stop - halts all operations."""
        if self._lib and self._handle:
            self._lib.uhcr_safety_emergency_stop(self._handle)
    
    def is_emergency_stopped(self) -> bool:
        """Check if emergency stop is active."""
        if self._lib and self._handle:
            return bool(self._lib.uhcr_safety_is_emergency_stopped(self._handle))
        return False
    
    def get_last_error(self) -> str:
        """Get last error message."""
        if self._lib and self._handle:
            error_ptr = self._lib.uhcr_safety_get_error(self._handle)
            if error_ptr:
                return error_ptr.decode('utf-8')
        return ""
    
    def clear_error(self):
        """Clear last error."""
        if self._lib and self._handle:
            self._lib.uhcr_safety_clear_error(self._handle)
    
    def set_max_memory(self, bytes_limit: int):
        """Set maximum memory allocation limit."""
        if self._lib and self._handle:
            self._lib.uhcr_safety_set_max_memory(self._handle, bytes_limit)
    
    def set_max_cpu_temp(self, celsius: int):
        """Set maximum CPU temperature limit."""
        if self._lib and self._handle:
            self._lib.uhcr_safety_set_max_cpu_temp(self._handle, celsius)
    
    def set_max_gpu_temp(self, celsius: int):
        """Set maximum GPU temperature limit."""
        if self._lib and self._handle:
            self._lib.uhcr_safety_set_max_gpu_temp(self._handle, celsius)

# Global safety monitor instance
_global_monitor = None

def get_safety_monitor() -> SafetyMonitor:
    """Get the global safety monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SafetyMonitor()
    return _global_monitor

__all__ = ['SafetyMonitor', 'SafetyStatus', 'get_safety_monitor']
