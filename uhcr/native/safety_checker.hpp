/**
 * UHCR Safety Checker - Runtime Safety Validation
 * 
 * Provides comprehensive safety checking for code execution:
 * - Memory bounds validation
 * - Buffer overflow prevention
 * - Integer overflow detection
 * - Null pointer checks
 * - Stack overflow protection
 * - Resource limit enforcement
 * - Dangerous operation detection
 */

#ifndef UHCR_SAFETY_CHECKER_HPP
#define UHCR_SAFETY_CHECKER_HPP

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
#include <memory>
#include <chrono>
#include <stdexcept>

namespace uhcr {
namespace safety {

// Safety violation types
enum class ViolationType {
    NONE = 0,
    BUFFER_OVERFLOW,
    BUFFER_UNDERFLOW,
    NULL_POINTER_DEREFERENCE,
    INTEGER_OVERFLOW,
    INTEGER_UNDERFLOW,
    STACK_OVERFLOW,
    HEAP_EXHAUSTION,
    DIVISION_BY_ZERO,
    INFINITE_LOOP,
    EXCESSIVE_RECURSION,
    UNSAFE_CAST,
    UNINITIALIZED_MEMORY,
    DOUBLE_FREE,
    USE_AFTER_FREE,
    RESOURCE_EXHAUSTION,
    TIMEOUT,
    SUSPICIOUS_OPERATION
};

// Safety check result
struct SafetyCheckResult {
    bool is_safe;
    ViolationType violation;
    std::string message;
    uint64_t timestamp;
    
    SafetyCheckResult() 
        : is_safe(true), violation(ViolationType::NONE), 
          timestamp(std::chrono::steady_clock::now().time_since_epoch().count()) {}
    
    SafetyCheckResult(ViolationType v, const std::string& msg)
        : is_safe(false), violation(v), message(msg),
          timestamp(std::chrono::steady_clock::now().time_since_epoch().count()) {}
};

// Memory bounds checker
class MemoryBoundsChecker {
public:
    // Check if pointer access is within bounds
    static SafetyCheckResult check_bounds(const void* ptr, size_t offset, size_t size, 
                                         const void* buffer_start, size_t buffer_size) {
        if (ptr == nullptr) {
            return SafetyCheckResult(ViolationType::NULL_POINTER_DEREFERENCE, 
                                    "Attempted to dereference null pointer");
        }
        
        const uint8_t* access_ptr = static_cast<const uint8_t*>(ptr) + offset;
        const uint8_t* buffer_ptr = static_cast<const uint8_t*>(buffer_start);
        const uint8_t* buffer_end = buffer_ptr + buffer_size;
        
        if (access_ptr < buffer_ptr) {
            return SafetyCheckResult(ViolationType::BUFFER_UNDERFLOW,
                                    "Buffer underflow detected: access before buffer start");
        }
        
        if (access_ptr + size > buffer_end) {
            return SafetyCheckResult(ViolationType::BUFFER_OVERFLOW,
                                    "Buffer overflow detected: access beyond buffer end");
        }
        
        return SafetyCheckResult();
    }
    
    // Check array index bounds
    static SafetyCheckResult check_array_index(int64_t index, size_t array_size) {
        if (index < 0) {
            return SafetyCheckResult(ViolationType::BUFFER_UNDERFLOW,
                                    "Negative array index: " + std::to_string(index));
        }
        
        if (static_cast<size_t>(index) >= array_size) {
            return SafetyCheckResult(ViolationType::BUFFER_OVERFLOW,
                                    "Array index out of bounds: " + std::to_string(index) + 
                                    " >= " + std::to_string(array_size));
        }
        
        return SafetyCheckResult();
    }
};

// Integer overflow checker
class IntegerOverflowChecker {
public:
    // Check signed addition overflow
    static SafetyCheckResult check_add(int64_t a, int64_t b) {
        if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b)) {
            return SafetyCheckResult(ViolationType::INTEGER_OVERFLOW,
                                    "Integer overflow in addition: " + 
                                    std::to_string(a) + " + " + std::to_string(b));
        }
        return SafetyCheckResult();
    }
    
    // Check signed subtraction overflow
    static SafetyCheckResult check_sub(int64_t a, int64_t b) {
        if ((b < 0 && a > INT64_MAX + b) || (b > 0 && a < INT64_MIN + b)) {
            return SafetyCheckResult(ViolationType::INTEGER_UNDERFLOW,
                                    "Integer underflow in subtraction: " +
                                    std::to_string(a) + " - " + std::to_string(b));
        }
        return SafetyCheckResult();
    }
    
    // Check signed multiplication overflow
    static SafetyCheckResult check_mul(int64_t a, int64_t b) {
        if (a == 0 || b == 0) return SafetyCheckResult();
        
        if (a == INT64_MIN || b == INT64_MIN) {
            if (a != 1 && b != 1) {
                return SafetyCheckResult(ViolationType::INTEGER_OVERFLOW,
                                        "Integer overflow in multiplication");
            }
        }
        
        int64_t result = a * b;
        if (result / a != b) {
            return SafetyCheckResult(ViolationType::INTEGER_OVERFLOW,
                                    "Integer overflow in multiplication: " +
                                    std::to_string(a) + " * " + std::to_string(b));
        }
        return SafetyCheckResult();
    }
    
    // Check division by zero
    static SafetyCheckResult check_div(int64_t a, int64_t b) {
        if (b == 0) {
            return SafetyCheckResult(ViolationType::DIVISION_BY_ZERO,
                                    "Division by zero: " + std::to_string(a) + " / 0");
        }
        return SafetyCheckResult();
    }
    
    // Check unsigned overflow
    static SafetyCheckResult check_add_unsigned(uint64_t a, uint64_t b) {
        if (a > UINT64_MAX - b) {
            return SafetyCheckResult(ViolationType::INTEGER_OVERFLOW,
                                    "Unsigned integer overflow in addition");
        }
        return SafetyCheckResult();
    }
};

// Stack and recursion checker
class StackChecker {
private:
    static constexpr size_t MAX_RECURSION_DEPTH = 10000;
    static constexpr size_t STACK_GUARD_SIZE = 16384; // 16KB guard zone
    
    size_t current_depth;
    const void* stack_start;
    
public:
    StackChecker() : current_depth(0), stack_start(nullptr) {}
    
    SafetyCheckResult check_recursion_depth(size_t depth) {
        if (depth > MAX_RECURSION_DEPTH) {
            return SafetyCheckResult(ViolationType::EXCESSIVE_RECURSION,
                                    "Excessive recursion depth: " + std::to_string(depth) +
                                    " > " + std::to_string(MAX_RECURSION_DEPTH));
        }
        return SafetyCheckResult();
    }
    
    SafetyCheckResult check_stack_space() {
        // Check remaining stack space (platform-specific implementation needed)
        // This is a simplified version
        char stack_var;
        const void* current_stack = &stack_var;
        
        if (stack_start == nullptr) {
            stack_start = current_stack;
            return SafetyCheckResult();
        }
        
        ptrdiff_t stack_used = static_cast<const char*>(stack_start) - 
                               static_cast<const char*>(current_stack);
        
        // Typical stack size is 1-8MB, warn if we've used too much
        if (std::abs(stack_used) > 7 * 1024 * 1024) {
            return SafetyCheckResult(ViolationType::STACK_OVERFLOW,
                                    "Stack space nearly exhausted");
        }
        
        return SafetyCheckResult();
    }
};

// Resource limit checker
class ResourceLimitChecker {
private:
    static constexpr size_t MAX_MEMORY_ALLOCATION = 1ULL * 1024 * 1024 * 1024; // 1GB
    static constexpr uint64_t MAX_EXECUTION_TIME_MS = 30000; // 30 seconds
    
    size_t total_allocated;
    std::chrono::steady_clock::time_point start_time;
    
public:
    ResourceLimitChecker() 
        : total_allocated(0), 
          start_time(std::chrono::steady_clock::now()) {}
    
    SafetyCheckResult check_allocation(size_t size) {
        if (size > MAX_MEMORY_ALLOCATION) {
            return SafetyCheckResult(ViolationType::HEAP_EXHAUSTION,
                                    "Single allocation too large: " + 
                                    std::to_string(size) + " bytes");
        }
        
        if (total_allocated + size > MAX_MEMORY_ALLOCATION) {
            return SafetyCheckResult(ViolationType::HEAP_EXHAUSTION,
                                    "Total memory allocation limit exceeded");
        }
        
        total_allocated += size;
        return SafetyCheckResult();
    }
    
    SafetyCheckResult check_execution_time() {
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            now - start_time).count();
        
        if (elapsed > MAX_EXECUTION_TIME_MS) {
            return SafetyCheckResult(ViolationType::TIMEOUT,
                                    "Execution timeout: " + std::to_string(elapsed) + 
                                    "ms > " + std::to_string(MAX_EXECUTION_TIME_MS) + "ms");
        }
        
        return SafetyCheckResult();
    }
    
    void deallocate(size_t size) {
        if (total_allocated >= size) {
            total_allocated -= size;
        }
    }
};

// Dangerous operation detector
class DangerousOperationDetector {
public:
    // Check for suspicious pointer cast
    static SafetyCheckResult check_pointer_cast(const void* ptr, size_t target_align) {
        uintptr_t addr = reinterpret_cast<uintptr_t>(ptr);
        if (addr % target_align != 0) {
            return SafetyCheckResult(ViolationType::UNSAFE_CAST,
                                    "Misaligned pointer cast detected");
        }
        return SafetyCheckResult();
    }
    
    // Check for uninitialized memory read
    static SafetyCheckResult check_initialized(const void* ptr, size_t size) {
        // This would require memory tracking in practice
        // Simplified version just checks for null
        if (ptr == nullptr) {
            return SafetyCheckResult(ViolationType::UNINITIALIZED_MEMORY,
                                    "Reading from null pointer (possibly uninitialized)");
        }
        return SafetyCheckResult();
    }
    
    // Detect potential infinite loop
    static SafetyCheckResult check_loop_iterations(uint64_t iterations, 
                                                   uint64_t max_iterations = 100000000) {
        if (iterations > max_iterations) {
            return SafetyCheckResult(ViolationType::INFINITE_LOOP,
                                    "Loop iteration count excessive: " + 
                                    std::to_string(iterations));
        }
        return SafetyCheckResult();
    }
};

// Main safety checker orchestrator
class SafetyChecker {
private:
    MemoryBoundsChecker memory_checker;
    IntegerOverflowChecker overflow_checker;
    StackChecker stack_checker;
    ResourceLimitChecker resource_checker;
    DangerousOperationDetector danger_detector;
    
    bool strict_mode;
    std::vector<SafetyCheckResult> violations;
    
public:
    SafetyChecker(bool strict = true) : strict_mode(strict) {}
    
    // Comprehensive safety check
    bool is_safe() const {
        return violations.empty() || !strict_mode;
    }
    
    // Get all violations
    const std::vector<SafetyCheckResult>& get_violations() const {
        return violations;
    }
    
    // Record a violation
    void record_violation(const SafetyCheckResult& result) {
        if (!result.is_safe) {
            violations.push_back(result);
            if (strict_mode) {
                throw std::runtime_error("Safety violation: " + result.message);
            }
        }
    }
    
    // Check and record
    SafetyCheckResult check_and_record(const SafetyCheckResult& result) {
        if (!result.is_safe) {
            record_violation(result);
        }
        return result;
    }
    
    // Enable/disable strict mode
    void set_strict_mode(bool strict) {
        strict_mode = strict;
    }
    
    // Clear violation history
    void clear_violations() {
        violations.clear();
    }
    
    // Get statistics
    std::string get_statistics() const {
        if (violations.empty()) {
            return "No safety violations detected";
        }
        
        std::string stats = "Safety Violations: " + std::to_string(violations.size()) + "\n";
        for (const auto& v : violations) {
            stats += "  - " + v.message + "\n";
        }
        return stats;
    }
};

} // namespace safety
} // namespace uhcr

#endif // UHCR_SAFETY_CHECKER_HPP
