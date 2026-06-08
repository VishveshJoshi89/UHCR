#ifndef UHCR_SAFETY_MONITOR_HPP
#define UHCR_SAFETY_MONITOR_HPP

#include <cstdint>
#include <cstddef>
#include <memory>
#include <string>
#include <chrono>
#include <atomic>

namespace uhcr {
namespace safety {

// Safety status codes
enum class SafetyStatus {
    OK = 0,
    MEMORY_OVERFLOW = 1,
    THERMAL_LIMIT = 2,
    POWER_LIMIT = 3,
    TIMEOUT = 4,
    INVALID_OPERATION = 5,
    RESOURCE_EXHAUSTED = 6,
    HARDWARE_ERROR = 7
};

// Resource limits configuration
struct ResourceLimits {
    size_t max_memory_bytes = 16ULL * 1024 * 1024 * 1024;  // 16GB default
    size_t max_vram_bytes = 8ULL * 1024 * 1024 * 1024;     // 8GB default
    uint32_t max_threads = 256;
    uint32_t max_cpu_temp_celsius = 95;
    uint32_t max_gpu_temp_celsius = 90;
    uint64_t max_execution_time_ms = 300000;  // 5 minutes
    uint32_t max_cpu_usage_percent = 95;
    uint32_t max_power_watts = 1000;
};

// Memory operation validation
struct MemoryOperation {
    void* address = nullptr;
    size_t size = 0;
    bool is_write = false;
    bool is_executable = false;
};

// CPU operation validation
struct CPUOperation {
    const char* instruction = nullptr;
    uint32_t core_id = 0;
    bool is_privileged = false;
    bool is_vectorized = false;
};

// GPU operation validation
struct GPUOperation {
    const char* kernel_name = nullptr;
    size_t vram_required = 0;
    uint32_t block_size = 0;
    uint32_t grid_size = 0;
};

class SafetyMonitor {
public:
    SafetyMonitor();
    ~SafetyMonitor();

    // Initialize monitoring
    bool initialize();
    void shutdown();

    // Configuration
    void set_limits(const ResourceLimits& limits);
    ResourceLimits get_limits() const;

    // Enable/disable monitoring
    void enable();
    void disable();
    bool is_enabled() const;

    // Memory safety
    SafetyStatus validate_memory_access(const MemoryOperation& op);
    SafetyStatus check_memory_bounds(void* ptr, size_t size);
    SafetyStatus validate_alignment(void* ptr, size_t alignment);
    
    // CPU safety
    SafetyStatus validate_cpu_operation(const CPUOperation& op);
    SafetyStatus check_cpu_temperature();
    SafetyStatus check_cpu_throttling();
    uint32_t get_cpu_temperature();
    
    // GPU safety
    SafetyStatus validate_gpu_operation(const GPUOperation& op);
    SafetyStatus check_gpu_temperature();
    SafetyStatus check_vram_available(size_t required);
    uint32_t get_gpu_temperature();
    
    // Resource monitoring
    size_t get_memory_usage();
    size_t get_vram_usage();
    uint32_t get_thread_count();
    uint32_t get_cpu_usage_percent();
    
    // Execution control
    SafetyStatus start_operation(uint64_t timeout_ms = 0);
    SafetyStatus end_operation();
    bool check_timeout();
    
    // Emergency shutdown
    void emergency_stop();
    bool is_emergency_stopped() const;
    
    // Error reporting
    const char* get_last_error() const;
    void clear_error();

private:
    class Impl;
    std::unique_ptr<Impl> pimpl;
    
    std::atomic<bool> enabled_;
    std::atomic<bool> emergency_stopped_;
    ResourceLimits limits_;
    std::chrono::steady_clock::time_point operation_start_;
    uint64_t operation_timeout_ms_;
    std::string last_error_;
};

// Guard classes for RAII safety
class MemoryGuard {
public:
    MemoryGuard(SafetyMonitor& monitor, void* ptr, size_t size, bool is_write = false);
    ~MemoryGuard();
    bool is_valid() const { return valid_; }
    SafetyStatus status() const { return status_; }

private:
    SafetyMonitor& monitor_;
    bool valid_;
    SafetyStatus status_;
};

class OperationGuard {
public:
    OperationGuard(SafetyMonitor& monitor, uint64_t timeout_ms = 0);
    ~OperationGuard();
    bool is_valid() const { return valid_; }
    SafetyStatus status() const { return status_; }

private:
    SafetyMonitor& monitor_;
    bool valid_;
    SafetyStatus status_;
};

// C API for Python ctypes binding
extern "C" {
    void* uhcr_safety_create();
    void uhcr_safety_destroy(void* handle);
    
    int uhcr_safety_initialize(void* handle);
    void uhcr_safety_shutdown(void* handle);
    
    void uhcr_safety_enable(void* handle);
    void uhcr_safety_disable(void* handle);
    int uhcr_safety_is_enabled(void* handle);
    
    int uhcr_safety_validate_memory(void* handle, void* ptr, size_t size, int is_write);
    int uhcr_safety_check_cpu_temp(void* handle);
    int uhcr_safety_check_gpu_temp(void* handle);
    
    uint32_t uhcr_safety_get_cpu_temp(void* handle);
    uint32_t uhcr_safety_get_gpu_temp(void* handle);
    size_t uhcr_safety_get_memory_usage(void* handle);
    
    void uhcr_safety_emergency_stop(void* handle);
    int uhcr_safety_is_emergency_stopped(void* handle);
    
    const char* uhcr_safety_get_error(void* handle);
    void uhcr_safety_clear_error(void* handle);
    
    void uhcr_safety_set_max_memory(void* handle, size_t bytes);
    void uhcr_safety_set_max_cpu_temp(void* handle, uint32_t celsius);
    void uhcr_safety_set_max_gpu_temp(void* handle, uint32_t celsius);
}

} // namespace safety
} // namespace uhcr

#endif // UHCR_SAFETY_MONITOR_HPP
