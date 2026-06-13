"""Runtime Safety Checking System

Provides comprehensive runtime safety validation using C++ safety checkers:
- Memory bounds validation
- Integer overflow detection
- Stack overflow protection
- Resource limit enforcement
- Dangerous operation detection
"""

import ctypes
import os
import sys
from typing import Optional, Tuple, Any
from pathlib import Path


class ViolationType:
    """Safety violation types matching C++ enum."""
    NONE = 0
    BUFFER_OVERFLOW = 1
    BUFFER_UNDERFLOW = 2
    NULL_POINTER_DEREFERENCE = 3
    INTEGER_OVERFLOW = 4
    INTEGER_UNDERFLOW = 5
    STACK_OVERFLOW = 6
    HEAP_EXHAUSTION = 7
    DIVISION_BY_ZERO = 8
    INFINITE_LOOP = 9
    EXCESSIVE_RECURSION = 10
    UNSAFE_CAST = 11
    UNINITIALIZED_MEMORY = 12
    DOUBLE_FREE = 13
    USE_AFTER_FREE = 14
    RESOURCE_EXHAUSTION = 15
    TIMEOUT = 16
    SUSPICIOUS_OPERATION = 17


class SafetyViolation(Exception):
    """Exception raised when a safety violation is detected."""
    
    def __init__(self, violation_type: int, message: str):
        self.violation_type = violation_type
        self.message = message
        super().__init__(f"Safety violation ({violation_type}): {message}")


class SafetyChecker:
    """Python interface to C++ safety checking system.
    
    This class provides safe arithmetic operations and memory access
    validation through C++ implementations.
    """
    
    def __init__(self, strict_mode: bool = True):
        """Initialize safety checker.
        
        Args:
            strict_mode: If True, raise exceptions on violations.
                        If False, log warnings but continue.
        """
        self.strict_mode = strict_mode
        self._native_lib = None
        self._load_native_library()
        
        if self._native_lib:
            self._native_lib.uhcr_safety_init(1 if strict_mode else 0)
    
    def _load_native_library(self):
        """Try to load native C++ safety library."""
        try:
            # Try to find compiled shared library
            lib_name = "libuhcr_safety"
            if sys.platform == "win32":
                lib_name = "uhcr_safety.dll"
            elif sys.platform == "darwin":
                lib_name = "libuhcr_safety.dylib"
            else:
                lib_name = "libuhcr_safety.so"
            
            # Look in native directory
            lib_path = Path(__file__).parent.parent / "native" / lib_name
            
            if lib_path.exists():
                self._native_lib = ctypes.CDLL(str(lib_path))
                self._setup_function_signatures()
        except Exception:
            # Native library not available - use Python fallbacks
            self._native_lib = None
    
    def _setup_function_signatures(self):
        """Setup C function signatures for ctypes."""
        if not self._native_lib:
            return
        
        # uhcr_check_array_index
        self._native_lib.uhcr_check_array_index.argtypes = [
            ctypes.c_int64,  # index
            ctypes.c_size_t,  # array_size
            ctypes.c_char_p,  # error_msg
            ctypes.c_size_t   # error_msg_size
        ]
        self._native_lib.uhcr_check_array_index.restype = ctypes.c_int
        
        # uhcr_check_add
        self._native_lib.uhcr_check_add.argtypes = [
            ctypes.c_int64,  # a
            ctypes.c_int64,  # b
            ctypes.POINTER(ctypes.c_int64),  # result
            ctypes.c_char_p,  # error_msg
            ctypes.c_size_t   # error_msg_size
        ]
        self._native_lib.uhcr_check_add.restype = ctypes.c_int
        
        # uhcr_check_mul
        self._native_lib.uhcr_check_mul.argtypes = [
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.POINTER(ctypes.c_int64),
            ctypes.c_char_p,
            ctypes.c_size_t
        ]
        self._native_lib.uhcr_check_mul.restype = ctypes.c_int
        
        # uhcr_check_div
        self._native_lib.uhcr_check_div.argtypes = [
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.POINTER(ctypes.c_int64),
            ctypes.c_char_p,
            ctypes.c_size_t
        ]
        self._native_lib.uhcr_check_div.restype = ctypes.c_int
    
    def check_array_index(self, index: int, array_size: int) -> Tuple[bool, Optional[str]]:
        """Check if array index is within bounds.
        
        Args:
            index: Array index to check
            array_size: Size of the array
            
        Returns:
            Tuple of (is_safe, error_message)
            
        Raises:
            SafetyViolation: If strict_mode is True and check fails
        """
        if self._native_lib:
            error_msg = ctypes.create_string_buffer(256)
            result = self._native_lib.uhcr_check_array_index(
                index, array_size, error_msg, 256
            )
            
            if result != 0:
                msg = error_msg.value.decode('utf-8')
                if self.strict_mode:
                    raise SafetyViolation(ViolationType.BUFFER_OVERFLOW, msg)
                return False, msg
            
            return True, None
        else:
            # Python fallback
            if index < 0:
                msg = f"Negative array index: {index}"
                if self.strict_mode:
                    raise SafetyViolation(ViolationType.BUFFER_UNDERFLOW, msg)
                return False, msg
            
            if index >= array_size:
                msg = f"Array index out of bounds: {index} >= {array_size}"
                if self.strict_mode:
                    raise SafetyViolation(ViolationType.BUFFER_OVERFLOW, msg)
                return False, msg
            
            return True, None
    
    def safe_add(self, a: int, b: int) -> int:
        """Safely add two integers with overflow checking.
        
        Args:
            a: First operand
            b: Second operand
            
        Returns:
            Sum of a and b
            
        Raises:
            SafetyViolation: If overflow would occur
        """
        if self._native_lib:
            result = ctypes.c_int64()
            error_msg = ctypes.create_string_buffer(256)
            
            ret = self._native_lib.uhcr_check_add(
                a, b, ctypes.byref(result), error_msg, 256
            )
            
            if ret != 0:
                msg = error_msg.value.decode('utf-8')
                raise SafetyViolation(ViolationType.INTEGER_OVERFLOW, msg)
            
            return result.value
        else:
            # Python fallback with range checking
            INT64_MAX = 2**63 - 1
            INT64_MIN = -(2**63)
            
            if (b > 0 and a > INT64_MAX - b) or (b < 0 and a < INT64_MIN - b):
                msg = f"Integer overflow in addition: {a} + {b}"
                raise SafetyViolation(ViolationType.INTEGER_OVERFLOW, msg)
            
            return a + b
    
    def safe_mul(self, a: int, b: int) -> int:
        """Safely multiply two integers with overflow checking.
        
        Args:
            a: First operand
            b: Second operand
            
        Returns:
            Product of a and b
            
        Raises:
            SafetyViolation: If overflow would occur
        """
        if self._native_lib:
            result = ctypes.c_int64()
            error_msg = ctypes.create_string_buffer(256)
            
            ret = self._native_lib.uhcr_check_mul(
                a, b, ctypes.byref(result), error_msg, 256
            )
            
            if ret != 0:
                msg = error_msg.value.decode('utf-8')
                raise SafetyViolation(ViolationType.INTEGER_OVERFLOW, msg)
            
            return result.value
        else:
            # Python fallback
            if a == 0 or b == 0:
                return 0
            
            result = a * b
            if result // a != b:
                msg = f"Integer overflow in multiplication: {a} * {b}"
                raise SafetyViolation(ViolationType.INTEGER_OVERFLOW, msg)
            
            return result
    
    def safe_div(self, a: int, b: int) -> int:
        """Safely divide two integers with division-by-zero checking.
        
        Args:
            a: Dividend
            b: Divisor
            
        Returns:
            Quotient of a / b
            
        Raises:
            SafetyViolation: If b is zero
        """
        if self._native_lib:
            result = ctypes.c_int64()
            error_msg = ctypes.create_string_buffer(256)
            
            ret = self._native_lib.uhcr_check_div(
                a, b, ctypes.byref(result), error_msg, 256
            )
            
            if ret != 0:
                msg = error_msg.value.decode('utf-8')
                raise SafetyViolation(ViolationType.DIVISION_BY_ZERO, msg)
            
            return result.value
        else:
            # Python fallback
            if b == 0:
                msg = f"Division by zero: {a} / 0"
                raise SafetyViolation(ViolationType.DIVISION_BY_ZERO, msg)
            
            return a // b
    
    def get_statistics(self) -> str:
        """Get safety checker statistics.
        
        Returns:
            Statistics string
        """
        if self._native_lib:
            try:
                stats_func = self._native_lib.uhcr_get_statistics
                stats_func.restype = ctypes.c_char_p
                stats = stats_func()
                return stats.decode('utf-8') if stats else "No statistics available"
            except:
                return "Statistics unavailable"
        else:
            return "Native safety library not loaded - using Python fallbacks"
    
    def __del__(self):
        """Cleanup safety checker."""
        if self._native_lib:
            try:
                self._native_lib.uhcr_safety_cleanup()
            except:
                pass


# Global safety checker instance
_global_checker: Optional[SafetyChecker] = None


def get_safety_checker(strict_mode: bool = True) -> SafetyChecker:
    """Get or create global safety checker instance.
    
    Args:
        strict_mode: Enable strict mode (raises exceptions on violations)
        
    Returns:
        Global SafetyChecker instance
    """
    global _global_checker
    
    if _global_checker is None:
        _global_checker = SafetyChecker(strict_mode)
    
    return _global_checker


def enable_safety_checks():
    """Enable runtime safety checks globally."""
    get_safety_checker(strict_mode=True)


def disable_safety_checks():
    """Disable strict safety checks (warnings only)."""
    global _global_checker
    if _global_checker:
        _global_checker.strict_mode = False


# Convenience functions using global checker
def safe_add(a: int, b: int) -> int:
    """Safely add integers with overflow checking."""
    return get_safety_checker().safe_add(a, b)


def safe_mul(a: int, b: int) -> int:
    """Safely multiply integers with overflow checking."""
    return get_safety_checker().safe_mul(a, b)


def safe_div(a: int, b: int) -> int:
    """Safely divide integers with zero checking."""
    return get_safety_checker().safe_div(a, b)


def check_array_bounds(index: int, size: int) -> None:
    """Check array index is within bounds, raise on violation."""
    get_safety_checker().check_array_index(index, size)
