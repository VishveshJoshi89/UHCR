"""UHCR Security Module

Provides comprehensive security and safety features:
- Runtime safety checking (C++ backed)
- Memory bounds validation
- Integer overflow detection
- Dangerous operation prevention
- Code sanitization
"""

from uhcr.security.runtime_safety import (
    SafetyChecker,
    SafetyViolation,
    ViolationType,
    get_safety_checker,
    enable_safety_checks,
    disable_safety_checks,
    safe_add,
    safe_mul,
    safe_div,
    check_array_bounds,
)

__all__ = [
    "SafetyChecker",
    "SafetyViolation",
    "ViolationType",
    "get_safety_checker",
    "enable_safety_checks",
    "disable_safety_checks",
    "safe_add",
    "safe_mul",
    "safe_div",
    "check_array_bounds",
]
