#include "safety_monitor.hpp"
#include <thread>
#include <mutex>
#include <vector>
#include <cstring>
#include <algorithm>

#ifdef _WIN32
    #include <windows.h>
    #include <psapi.h>
    #include <pdh.h>
    #include <pdhmsg.h>
#else
    #include <unistd.h>
    #include <sys/sysinfo.h>
    #include <sys/resource.h>
    #include <fstream>
#endif

namespace uhcr {
namespace safety {

// Platform-specific helpers
namespace platform {

#ifdef _WIN32
    uint32_t get_cpu_temperature() {
        // Windows: Use WMI or hardware monitoring libraries
        // Simplified implementation - in production use OpenHardwareMonitor API
        return 0; // Return 0 if not available
    }
    
    uint32_t get_gpu_temperature() {
        // Windows: Use NVML for NVIDIA or similar for AMD
        return 0;
    }
    
    size_t get_process_memory() {
        PROCESS_MEMORY_COUNTERS pmc;
        if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc))) {
            return pmc.WorkingSetSize;
        }
        return 0;
    }
    
    uint32_t get_thread_count() {
        return std::thread::hardware_concurrency();
    }
#else
    uint32_t get_cpu_temperature() {
        // Linux: Read from /sys/class/thermal/thermal_zone*/temp
        std::ifstream temp_file("/sys/class/thermal/thermal_zone0/temp");
        if (temp_file.is_open()) {
            int temp_millicelsius;
            temp_file >> temp_millicelsius;
            return temp_millicelsius / 1000;
        }
        return 0;
    }
    
    uint32_t get_gpu_temperature() {
        // Linux: Use nvidia-smi or similar
        return 0;
    }
    
    size_t get_process_memory() {
        std::ifstream status("/proc/self/status");
        std::string line;
        while (std::getline(status, line)) {
            if (line.find("VmRSS:") == 0) {
                size_t kb;
                sscanf(line.c_str(), "VmRSS: %zu kB", &kb);
                return kb * 1024;
            }
        }
        return 0;
    }
    
    uint32_t get_thread_count() {
        return std::thread::hardware_concurrency();
    }
#endif

} // namespace platform

// Implementation class
class SafetyMonitor::Impl {
public:
    std::mutex mutex_;
    std::vector<void*> allocated_regions_;
    size_t total_allocated_ = 0;
    uint32_t active_operations_ = 0;
};

SafetyMonitor::SafetyMonitor() 
    : pimpl(std::make_unique<Impl>())
    , enabled_(false)
    , emergency_stopped_(false)
    , operation_timeout_ms_(0)
{
}

SafetyMonitor::~SafetyMonitor() {
    shutdown();
}

bool SafetyMonitor::initialize() {
    std::lock_guard<std::mutex> lock(pimpl->mutex_);
    emergency_stopped_ = false;
    last_error_.clear();
    return true;
}

void SafetyMonitor::shutdown() {
    std::lock_guard<std::mutex> lock(pimpl->mutex_);
    enabled_ = false;
    pimpl->allocated_regions_.clear();
    pimpl->total_allocated_ = 0;
}

void SafetyMonitor::set_limits(const ResourceLimits& limits) {
    std::lock_guard<std::mutex> lock(pimpl->mutex_);
    limits_ = limits;
}

ResourceLimits SafetyMonitor::get_limits() const {
    std::lock_guard<std::mutex> lock(pimpl->mutex_);
    return limits_;
}

void SafetyMonitor::enable() {
    enabled_ = true;
}

void SafetyMonitor::disable() {
    enabled_ = false;
}

bool SafetyMonitor::is_enabled() const {
    return enabled_;
}

SafetyStatus SafetyMonitor::validate_memory_access(const MemoryOperation& op) {
    if (!enabled_) return SafetyStatus::OK;
    if (emergency_stopped_) return SafetyStatus::HARDWARE_ERROR;
    
    std::lock_guard<std::mutex> lock(pimpl->mutex_);
    
    // Check NULL pointer
    if (op.address == nullptr) {
        last_error_ = "NULL pointer access";
        return SafetyStatus::INVALID_OPERATION;
    }
    
    // Check size
    if (op.size == 0) {
        last_error_ = "Zero-size memory operation";
        return SafetyStatus::INVALID_OPERATION;
    }
    
    // Check total memory limit
    if (pimpl->total_allocated_ + op.size > limits_.max_memory_bytes) {
        last_error_ = "Memory limit exceeded";
        return SafetyStatus::MEMORY_OVERFLOW;
    }
    
    // Check alignment for SIMD operations
    if (op.is_executable) {
        uintptr_t addr = reinterpret_cast<uintptr_t>(op.address);
        if (addr % 4096 != 0) {
            last_error_ = "Executable memory must be page-aligned";
            return SafetyStatus::INVALID_OPERATION;
        }
    }
    
    return SafetyStatus::OK;
}

SafetyStatus SafetyMonitor::check_memory_bounds(void* ptr, size_t size) {
    if (!enabled_) return SafetyStatus::OK;
    
    MemoryOperation op;
    op.address = ptr;
    op.size = size;
    op.is_write = false;
    
    return validate_memory_access(op);
}

SafetyStatus SafetyMonitor::validate_alignment(void* ptr, size_t alignment) {
    if (!enabled_) return SafetyStatus::OK;
    
    uintptr_t addr = reinterpret_cast<uintptr_t>(ptr);
    if (addr % alignment != 0) {
        last_error_ = "Memory alignment violation";
        return SafetyStatus::INVALID_OPERATION;
    }
    
    return SafetyStatus::OK;
}

SafetyStatus SafetyMonitor::validate_cpu_operation(const CPUOperation& op) {
    if (!enabled_) return SafetyStatus::OK;
    if (emergency_stopped_) return SafetyStatus::HARDWARE_ERROR;
    
    // Check temperature first
    auto temp_status = check_cpu_temperature();
    if (temp_status != SafetyStatus::OK) {
        return temp_status;
    }
    
    // Check for privileged instructions
    if (op.is_privileged) {
        last_error_ = "Privileged CPU instruction not allowed";
        return SafetyStatus::INVALID_OPERATION;
    }
    
    return SafetyStatus::OK;
}

SafetyStatus SafetyMonitor::check_cpu_temperature() {
    if (!enabled_) return SafetyStatus::OK;
    
    uint32_t temp = platform::get_cpu_temperature();
    if (temp > 0 && temp >= limits_.max_cpu_temp_celsius) {
        last_error_ = "CPU temperature limit exceeded: " + std::to_string(temp) + "°C";
        emergency_stop();
        return SafetyStatus::THERMAL_LIMIT;
    }
    
    return SafetyStatus::OK;
}

SafetyStatus SafetyMonitor::check_cpu_throttling() {
    // Check if CPU is thermally throttling
    // Implementation depends on platform
    return SafetyStatus::OK;
}

uint32_t SafetyMonitor::get_cpu_temperature() {
    return platform::get_cpu_temperature();
}

SafetyStatus SafetyMonitor::validate_gpu_operation(const GPUOperation& op) {
    if (!enabled_) return SafetyStatus::OK;
    if (emergency_stopped_) return SafetyStatus::HARDWARE_ERROR;
    
    // Check GPU temperature
    auto temp_status = check_gpu_temperature();
    if (temp_status != SafetyStatus::OK) {
        return temp_status;
    }
    
    // Check VRAM availability
    if (op.vram_required > 0) {
        auto vram_status = check_vram_available(op.vram_required);
        if (vram_status != SafetyStatus::OK) {
            return vram_status;
        }
    }
    
    // Validate kernel parameters
    if (op.block_size == 0 || op.grid_size == 0) {
        last_error_ = "Invalid GPU kernel dimensions";
        return SafetyStatus::INVALID_OPERATION;
    }
    
    // Check for excessive resource usage
    uint64_t total_threads = static_cast<uint64_t>(op.block_size) * op.grid_size;
    if (total_threads > 1ULL << 30) {  // 1 billion threads max
        last_error_ = "GPU kernel too large";
        return SafetyStatus::RESOURCE_EXHAUSTED;
    }
    
    return SafetyStatus::OK;
}

SafetyStatus SafetyMonitor::check_gpu_temperature() {
    if (!enabled_) return SafetyStatus::OK;
    
    uint32_t temp = platform::get_gpu_temperature();
    if (temp > 0 && temp >= limits_.max_gpu_temp_celsius) {
        last_error_ = "GPU temperature limit exceeded: " + std::to_string(temp) + "°C";
        emergency_stop();
        return SafetyStatus::THERMAL_LIMIT;
    }
    
    return SafetyStatus::OK;
}

SafetyStatus SafetyMonitor::check_vram_available(size_t required) {
    if (!enabled_) return SafetyStatus::OK;
    
    if (required > limits_.max_vram_bytes) {
        last_error_ = "VRAM requirement exceeds limit";
        return SafetyStatus::MEMORY_OVERFLOW;
    }
    
    return SafetyStatus::OK;
}

uint32_t SafetyMonitor::get_gpu_temperature() {
    return platform::get_gpu_temperature();
}

size_t SafetyMonitor::get_memory_usage() {
    return platform::get_process_memory();
}

size_t SafetyMonitor::get_vram_usage() {
    // Platform-specific VRAM query
    return 0;
}

uint32_t SafetyMonitor::get_thread_count() {
    return platform::get_thread_count();
}

uint32_t SafetyMonitor::get_cpu_usage_percent() {
    // Platform-specific CPU usage
    return 0;
}

SafetyStatus SafetyMonitor::start_operation(uint64_t timeout_ms) {
    if (!enabled_) return SafetyStatus::OK;
    if (emergency_stopped_) return SafetyStatus::HARDWARE_ERROR;
    
    std::lock_guard<std::mutex> lock(pimpl->mutex_);
    
    operation_start_ = std::chrono::steady_clock::now();
    operation_timeout_ms_ = timeout_ms > 0 ? timeout_ms : limits_.max_execution_time_ms;
    pimpl->active_operations_++;
    
    return SafetyStatus::OK;
}

SafetyStatus SafetyMonitor::end_operation() {
    if (!enabled_) return SafetyStatus::OK;
    
    std::lock_guard<std::mutex> lock(pimpl->mutex_);
    if (pimpl->active_operations_ > 0) {
        pimpl->active_operations_--;
    }
    
    return SafetyStatus::OK;
}

bool SafetyMonitor::check_timeout() {
    if (!enabled_ || operation_timeout_ms_ == 0) return false;
    
    auto now = std::chrono::steady_clock::now();
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
        now - operation_start_).count();
    
    if (static_cast<uint64_t>(elapsed) > operation_timeout_ms_) {
        last_error_ = "Operation timeout exceeded";
        return true;
    }
    
    return false;
}

void SafetyMonitor::emergency_stop() {
    emergency_stopped_ = true;
    enabled_ = false;
    last_error_ = "EMERGENCY STOP ACTIVATED";
}

bool SafetyMonitor::is_emergency_stopped() const {
    return emergency_stopped_;
}

const char* SafetyMonitor::get_last_error() const {
    return last_error_.c_str();
}

void SafetyMonitor::clear_error() {
    last_error_.clear();
}

// Guard implementations
MemoryGuard::MemoryGuard(SafetyMonitor& monitor, void* ptr, size_t size, bool is_write)
    : monitor_(monitor), valid_(false), status_(SafetyStatus::OK)
{
    MemoryOperation op;
    op.address = ptr;
    op.size = size;
    op.is_write = is_write;
    
    status_ = monitor_.validate_memory_access(op);
    valid_ = (status_ == SafetyStatus::OK);
}

MemoryGuard::~MemoryGuard() {
    // Could add cleanup here if needed
}

OperationGuard::OperationGuard(SafetyMonitor& monitor, uint64_t timeout_ms)
    : monitor_(monitor), valid_(false), status_(SafetyStatus::OK)
{
    status_ = monitor_.start_operation(timeout_ms);
    valid_ = (status_ == SafetyStatus::OK);
}

OperationGuard::~OperationGuard() {
    if (valid_) {
        monitor_.end_operation();
    }
}

// C API implementation
extern "C" {

void* uhcr_safety_create() {
    return new SafetyMonitor();
}

void uhcr_safety_destroy(void* handle) {
    delete static_cast<SafetyMonitor*>(handle);
}

int uhcr_safety_initialize(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    return monitor->initialize() ? 1 : 0;
}

void uhcr_safety_shutdown(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    monitor->shutdown();
}

void uhcr_safety_enable(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    monitor->enable();
}

void uhcr_safety_disable(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    monitor->disable();
}

int uhcr_safety_is_enabled(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    return monitor->is_enabled() ? 1 : 0;
}

int uhcr_safety_validate_memory(void* handle, void* ptr, size_t size, int is_write) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    MemoryOperation op;
    op.address = ptr;
    op.size = size;
    op.is_write = (is_write != 0);
    return static_cast<int>(monitor->validate_memory_access(op));
}

int uhcr_safety_check_cpu_temp(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    return static_cast<int>(monitor->check_cpu_temperature());
}

int uhcr_safety_check_gpu_temp(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    return static_cast<int>(monitor->check_gpu_temperature());
}

uint32_t uhcr_safety_get_cpu_temp(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    return monitor->get_cpu_temperature();
}

uint32_t uhcr_safety_get_gpu_temp(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    return monitor->get_gpu_temperature();
}

size_t uhcr_safety_get_memory_usage(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    return monitor->get_memory_usage();
}

void uhcr_safety_emergency_stop(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    monitor->emergency_stop();
}

int uhcr_safety_is_emergency_stopped(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    return monitor->is_emergency_stopped() ? 1 : 0;
}

const char* uhcr_safety_get_error(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    return monitor->get_last_error();
}

void uhcr_safety_clear_error(void* handle) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    monitor->clear_error();
}

void uhcr_safety_set_max_memory(void* handle, size_t bytes) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    auto limits = monitor->get_limits();
    limits.max_memory_bytes = bytes;
    monitor->set_limits(limits);
}

void uhcr_safety_set_max_cpu_temp(void* handle, uint32_t celsius) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    auto limits = monitor->get_limits();
    limits.max_cpu_temp_celsius = celsius;
    monitor->set_limits(limits);
}

void uhcr_safety_set_max_gpu_temp(void* handle, uint32_t celsius) {
    auto* monitor = static_cast<SafetyMonitor*>(handle);
    auto limits = monitor->get_limits();
    limits.max_gpu_temp_celsius = celsius;
    monitor->set_limits(limits);
}

} // extern "C"

} // namespace safety
} // namespace uhcr
