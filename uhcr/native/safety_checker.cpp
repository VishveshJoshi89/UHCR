/**
 * UHCR Safety Checker Implementation
 * 
 * C++ implementation for runtime safety validation
 */

#include "safety_checker.hpp"
#include <iostream>
#include <sstream>
#include <iomanip>

namespace uhcr {
namespace safety {

// Violation type to string conversion
const char* violation_type_to_string(ViolationType type) {
    switch (type) {
        case ViolationType::NONE: return "NONE";
        case ViolationType::BUFFER_OVERFLOW: return "BUFFER_OVERFLOW";
        case ViolationType::BUFFER_UNDERFLOW: return "BUFFER_UNDERFLOW";
        case ViolationType::NULL_POINTER_DEREFERENCE: return "NULL_POINTER_DEREFERENCE";
        case ViolationType::INTEGER_OVERFLOW: return "INTEGER_OVERFLOW";
        case ViolationType::INTEGER_UNDERFLOW: return "INTEGER_UNDERFLOW";
        case ViolationType::STACK_OVERFLOW: return "STACK_OVERFLOW";
        case ViolationType::HEAP_EXHAUSTION: return "HEAP_EXHAUSTION";
        case ViolationType::DIVISION_BY_ZERO: return "DIVISION_BY_ZERO";
        case ViolationType::INFINITE_LOOP: return "INFINITE_LOOP";
        case ViolationType::EXCESSIVE_RECURSION: return "EXCESSIVE_RECURSION";
        case ViolationType::UNSAFE_CAST: return "UNSAFE_CAST";
        case ViolationType::UNINITIALIZED_MEMORY: return "UNINITIALIZED_MEMORY";
        case ViolationType::DOUBLE_FREE: return "DOUBLE_FREE";
        case ViolationType::USE_AFTER_FREE: return "USE_AFTER_FREE";
        case ViolationType::RESOURCE_EXHAUSTION: return "RESOURCE_EXHAUSTION";
        case ViolationType::TIMEOUT: return "TIMEOUT";
        case ViolationType::SUSPICIOUS_OPERATION: return "SUSPICIOUS_OPERATION";
        default: return "UNKNOWN";
    }
}

// Format safety check result for logging
std::string format_safety_result(const SafetyCheckResult& result) {
    std::ostringstream oss;
    
    if (result.is_safe) {
        oss << "[SAFE] No violations detected";
    } else {
        oss << "[UNSAFE] " << violation_type_to_string(result.violation)
            << ": " << result.message
            << " (timestamp: " << result.timestamp << ")";
    }
    
    return oss.str();
}

// Global safety checker instance
static SafetyChecker* g_global_checker = nullptr;

// Initialize global safety checker
void initialize_safety_checker(bool strict_mode) {
    if (g_global_checker == nullptr) {
        g_global_checker = new SafetyChecker(strict_mode);
    }
}

// Get global safety checker
SafetyChecker* get_global_checker() {
    if (g_global_checker == nullptr) {
        initialize_safety_checker(true);
    }
    return g_global_checker;
}

// Cleanup global safety checker
void cleanup_safety_checker() {
    if (g_global_checker != nullptr) {
        delete g_global_checker;
        g_global_checker = nullptr;
    }
}

// C-style API for Python binding
extern "C" {

// Check memory bounds
int uhcr_check_bounds(const void* ptr, size_t offset, size_t size,
                     const void* buffer_start, size_t buffer_size,
                     char* error_msg, size_t error_msg_size) {
    auto result = MemoryBoundsChecker::check_bounds(ptr, offset, size, 
                                                     buffer_start, buffer_size);
    
    if (!result.is_safe && error_msg != nullptr && error_msg_size > 0) {
        strncpy(error_msg, result.message.c_str(), error_msg_size - 1);
        error_msg[error_msg_size - 1] = '\0';
    }
    
    return result.is_safe ? 0 : -1;
}

// Check array index
int uhcr_check_array_index(int64_t index, size_t array_size,
                           char* error_msg, size_t error_msg_size) {
    auto result = MemoryBoundsChecker::check_array_index(index, array_size);
    
    if (!result.is_safe && error_msg != nullptr && error_msg_size > 0) {
        strncpy(error_msg, result.message.c_str(), error_msg_size - 1);
        error_msg[error_msg_size - 1] = '\0';
    }
    
    return result.is_safe ? 0 : -1;
}

// Check integer addition
int uhcr_check_add(int64_t a, int64_t b, int64_t* result,
                   char* error_msg, size_t error_msg_size) {
    auto check = IntegerOverflowChecker::check_add(a, b);
    
    if (check.is_safe && result != nullptr) {
        *result = a + b;
    }
    
    if (!check.is_safe && error_msg != nullptr && error_msg_size > 0) {
        strncpy(error_msg, check.message.c_str(), error_msg_size - 1);
        error_msg[error_msg_size - 1] = '\0';
    }
    
    return check.is_safe ? 0 : -1;
}

// Check integer multiplication
int uhcr_check_mul(int64_t a, int64_t b, int64_t* result,
                   char* error_msg, size_t error_msg_size) {
    auto check = IntegerOverflowChecker::check_mul(a, b);
    
    if (check.is_safe && result != nullptr) {
        *result = a * b;
    }
    
    if (!check.is_safe && error_msg != nullptr && error_msg_size > 0) {
        strncpy(error_msg, check.message.c_str(), error_msg_size - 1);
        error_msg[error_msg_size - 1] = '\0';
    }
    
    return check.is_safe ? 0 : -1;
}

// Check division
int uhcr_check_div(int64_t a, int64_t b, int64_t* result,
                   char* error_msg, size_t error_msg_size) {
    auto check = IntegerOverflowChecker::check_div(a, b);
    
    if (check.is_safe && result != nullptr) {
        *result = a / b;
    }
    
    if (!check.is_safe && error_msg != nullptr && error_msg_size > 0) {
        strncpy(error_msg, check.message.c_str(), error_msg_size - 1);
        error_msg[error_msg_size - 1] = '\0';
    }
    
    return check.is_safe ? 0 : -1;
}

// Initialize safety system
void uhcr_safety_init(int strict_mode) {
    initialize_safety_checker(strict_mode != 0);
}

// Cleanup safety system
void uhcr_safety_cleanup() {
    cleanup_safety_checker();
}

// Get violation count
int uhcr_get_violation_count() {
    auto checker = get_global_checker();
    return static_cast<int>(checker->get_violations().size());
}

// Get statistics
const char* uhcr_get_statistics() {
    auto checker = get_global_checker();
    static std::string stats;
    stats = checker->get_statistics();
    return stats.c_str();
}

} // extern "C"

} // namespace safety
} // namespace uhcr
