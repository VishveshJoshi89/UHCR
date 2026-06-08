# UHCR Runtime System

## Overview

The UHCR Runtime System is the execution engine that manages:

- **Memory Management** — Aligned allocation, garbage collection, memory pools
- **Thread Scheduling** — Work-stealing scheduler, parallel execution
- **Function Cache** — Compiled function storage and retrieval
- **Performance Monitoring** — Execution metrics and profiling
- **Resource Management** — CPU/GPU resource allocation

---

## Memory Management

### Aligned Memory Allocation

UHCR uses SIMD-aligned memory for optimal performance:

```python
import uhcr
from uhcr.storage.memory_pool import MemoryPool

# Initialize memory pool
pool = MemoryPool(size="2GB", alignment=64)

# Allocate aligned memory
buffer = pool.allocate(1024 * 1024)  # 1MB aligned to 64 bytes
print(f"Buffer address: {hex(buffer.address)}")
print(f"Alignment check: {buffer.address % 64 == 0}")

# Use with numpy arrays
import numpy as np
aligned_array = np.frombuffer(buffer, dtype=np.float32)
```

### Memory Pool Configuration

```python
# Configure memory pools
uhcr.config.set('memory.pool_size', '4GB')
uhcr.config.set('memory.alignment', 64)
uhcr.config.set('memory.gc_threshold', 0.8)  # GC at 80% usage

# Multiple pools for different use cases
compute_pool = MemoryPool(size="2GB", name="compute")
cache_pool = MemoryPool(size="1GB", name="cache")
temp_pool = MemoryPool(size="512MB", name="temporary")
```

### Garbage Collection

```python
from uhcr.runtime.gc import GarbageCollector

gc = GarbageCollector()

# Manual garbage collection
gc.collect()

# Automatic thresholds
gc.set_threshold(
    heap_size=0.8,      # Collect at 80% heap usage
    allocation_rate=100  # Collect after 100 allocations
)

# Reference counting for immediate cleanup
class ManagedBuffer:
    def __init__(self, size):
        self.buffer = pool.allocate(size)
        self.ref_count = 1
    
    def addref(self):
        self.ref_count += 1
        return self
    
    def release(self):
        self.ref_count -= 1
        if self.ref_count == 0:
            pool.deallocate(self.buffer)
```

---

## Thread Scheduling

### Work-Stealing Scheduler

UHCR uses a work-stealing scheduler for parallel execution:

```python
from uhcr.runtime.scheduler import Scheduler

# Create scheduler with auto-detected thread count
scheduler = Scheduler()

# Parallel for loop
def compute_task(start, end):
    result = 0
    for i in range(start, end):
        result += i * i
    return result

# Execute in parallel
results = scheduler.parallel_for(
    start=0, 
    end=10000, 
    func=compute_task,
    chunk_size=1000
)

total = sum(results)
print(f"Total: {total}")
```
### Thread Pinning

```python
# Pin threads to specific CPU cores
scheduler.set_thread_affinity({
    0: [0, 1],    # Thread 0 → CPU cores 0,1
    1: [2, 3],    # Thread 1 → CPU cores 2,3
    2: [4, 5],    # Thread 2 → CPU cores 4,5
    3: [6, 7],    # Thread 3 → CPU cores 6,7
})

# NUMA-aware scheduling
numa_scheduler = Scheduler(numa_aware=True)
numa_scheduler.bind_to_numa_node(0)  # Bind to NUMA node 0
```

### Thread Pool Management

```python
from uhcr.runtime.thread_pool import ThreadPool

class AdaptiveThreadPool(ThreadPool):
    def __init__(self, min_threads=2, max_threads=16):
        super().__init__()
        self.min_threads = min_threads
        self.max_threads = max_threads
        self.load_history = []
    
    def adjust_thread_count(self):
        """Dynamically adjust thread count based on load"""
        
        current_load = self.get_load_average()
        self.load_history.append(current_load)
        
        if len(self.load_history) > 10:
            self.load_history.pop(0)
        
        avg_load = sum(self.load_history) / len(self.load_history)
        
        if avg_load > 0.8 and self.thread_count < self.max_threads:
            self.add_thread()
        elif avg_load < 0.3 and self.thread_count > self.min_threads:
            self.remove_thread()

# Usage
pool = AdaptiveThreadPool(min_threads=4, max_threads=32)
pool.start_monitoring()  # Automatically adjusts thread count
```

---

## Function Cache System

### Cache Implementation

```python
from uhcr.runtime.cache import FunctionCache

cache = FunctionCache(max_size=1000, eviction_policy='lru')

# Cache compiled functions
@uhcr.jit(cache=True)
def cached_function(x, y):
    return x * y + x

# Cache statistics
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Cache size: {stats['size']}/{stats['max_size']}")
```

### Multi-level Cache

```python
class MultiLevelCache:
    def __init__(self):
        self.l1_cache = FunctionCache(max_size=100, name="L1")  # Hot functions
        self.l2_cache = FunctionCache(max_size=500, name="L2")  # Warm functions
        self.l3_cache = FunctionCache(max_size=1000, name="L3") # Cold functions
    
    def get(self, key):
        # Try L1 first
        result = self.l1_cache.get(key)
        if result:
            return result
        
        # Try L2
        result = self.l2_cache.get(key)
        if result:
            # Promote to L1
            self.l1_cache.put(key, result)
            return result
        
        # Try L3
        result = self.l3_cache.get(key)
        if result:
            # Promote to L2
            self.l2_cache.put(key, result)
            return result
        
        return None
```

### Persistent Cache

```python
import uhcr
from uhcr.storage.persistent_cache import PersistentCache

# Enable persistent caching
cache = PersistentCache(
    cache_dir="~/.uhcr/cache",
    max_size="1GB",
    compression=True
)

uhcr.config.set('cache.persistent', True)
uhcr.config.set('cache.directory', cache.cache_dir)

# Cache survives process restarts
@uhcr.jit(persistent_cache=True)
def expensive_function(data):
    # Complex computation
    return sum(x**2 for x in data)

# First call compiles and caches
result1 = expensive_function(range(1000))

# Restart process...
# Second call loads from persistent cache
result2 = expensive_function(range(1000))
```

---

## Performance Monitoring

### Runtime Profiler

```python
from uhcr.runtime.profiler import RuntimeProfiler

profiler = RuntimeProfiler()

# Enable profiling
profiler.enable()

@uhcr.jit(profile=True)
def profiled_function(n):
    total = 0
    for i in range(n):
        total += i * i
    return total

# Execute with profiling
result = profiled_function(100000)

# Get performance metrics
metrics = profiler.get_metrics('profiled_function')
print(f"Compile time: {metrics['compile_time']:.3f}ms")
print(f"Execute time: {metrics['execute_time']:.3f}ms")
print(f"Speedup: {metrics['speedup']:.2f}x")
```

### Custom Metrics

```python
class CustomMetrics:
    def __init__(self):
        self.metrics = {}
        self.start_times = {}
    
    def start_timer(self, name):
        """Start timing a code section"""
        self.start_times[name] = time.perf_counter()
    
    def end_timer(self, name):
        """End timing and record metric"""
        if name in self.start_times:
            duration = time.perf_counter() - self.start_times[name]
            if name not in self.metrics:
                self.metrics[name] = []
            self.metrics[name].append(duration)
            del self.start_times[name]
    
    def get_stats(self, name):
        """Get statistics for a metric"""
        if name not in self.metrics:
            return None
        
        values = self.metrics[name]
        return {
            'count': len(values),
            'total': sum(values),
            'average': sum(values) / len(values),
            'min': min(values),
            'max': max(values)
        }

# Usage in UHCR functions
metrics = CustomMetrics()

@uhcr.jit(eager=True)
def monitored_computation(data):
    metrics.start_timer('preprocessing')
    # Preprocessing code
    processed = [x * 2 for x in data]
    metrics.end_timer('preprocessing')
    
    metrics.start_timer('computation')
    # Main computation
    result = sum(processed)
    metrics.end_timer('computation')
    
    return result
```
---

## Resource Management

### CPU Resource Management

```python
from uhcr.runtime.resources import CPUResourceManager

cpu_mgr = CPUResourceManager()

# Get CPU information
cpu_info = cpu_mgr.get_cpu_info()
print(f"CPU: {cpu_info['brand']}")
print(f"Cores: {cpu_info['physical_cores']}")
print(f"Threads: {cpu_info['logical_cores']}")

# Set CPU limits
cpu_mgr.set_limits(
    max_threads=8,
    cpu_percent=80.0,  # Limit to 80% CPU usage
    numa_node=0        # Prefer NUMA node 0
)

# Monitor CPU usage
while True:
    usage = cpu_mgr.get_current_usage()
    if usage > 90:
        cpu_mgr.throttle_threads(0.8)  # Reduce to 80% capacity
    
    time.sleep(1.0)
```

### GPU Resource Management

```python
from uhcr.runtime.resources import GPUResourceManager

gpu_mgr = GPUResourceManager()

if gpu_mgr.has_gpu():
    # Get GPU information
    gpu_info = gpu_mgr.get_gpu_info()
    print(f"GPU: {gpu_info['name']}")
    print(f"Memory: {gpu_info['memory_total']} GB")
    
    # Allocate GPU memory
    gpu_buffer = gpu_mgr.allocate_memory(1024 * 1024 * 1024)  # 1GB
    
    # Set memory limits
    gpu_mgr.set_memory_limit(0.8)  # Use max 80% of GPU memory
    
    # Monitor GPU usage
    usage = gpu_mgr.get_memory_usage()
    print(f"GPU memory usage: {usage:.1%}")
```

### Dynamic Resource Allocation

```python
class DynamicResourceManager:
    def __init__(self):
        self.cpu_mgr = CPUResourceManager()
        self.gpu_mgr = GPUResourceManager() if GPUResourceManager.available() else None
        self.memory_mgr = MemoryManager()
        
        self.workload_history = []
    
    def allocate_for_workload(self, workload_type, workload_size):
        """Dynamically allocate resources based on workload"""
        
        if workload_type == 'cpu_intensive':
            # Allocate more CPU threads
            self.cpu_mgr.set_thread_count(
                min(self.cpu_mgr.max_threads, workload_size // 1000)
            )
            
        elif workload_type == 'memory_intensive':
            # Pre-allocate memory pool
            required_memory = workload_size * 8  # 8 bytes per element
            self.memory_mgr.ensure_available(required_memory)
            
        elif workload_type == 'gpu_compute' and self.gpu_mgr:
            # Allocate GPU resources
            self.gpu_mgr.prepare_for_compute(workload_size)
        
        # Record for future predictions
        self.workload_history.append({
            'type': workload_type,
            'size': workload_size,
            'timestamp': time.time()
        })
    
    def predict_resource_needs(self, workload_type):
        """Predict resource needs based on history"""
        
        similar_workloads = [
            w for w in self.workload_history 
            if w['type'] == workload_type
        ]
        
        if similar_workloads:
            avg_size = sum(w['size'] for w in similar_workloads) / len(similar_workloads)
            return self._calculate_resources(workload_type, avg_size)
        
        return self._default_resources(workload_type)

# Usage
resource_mgr = DynamicResourceManager()

@uhcr.jit(eager=True)
def adaptive_computation(data):
    # System automatically adapts resources
    workload_size = len(data)
    resource_mgr.allocate_for_workload('cpu_intensive', workload_size)
    
    # Perform computation
    return sum(x * x for x in data)
```

---

## Error Handling and Recovery

### Runtime Error Management

```python
from uhcr.runtime.errors import RuntimeErrorHandler

class UHCRErrorHandler(RuntimeErrorHandler):
    def __init__(self):
        super().__init__()
        self.error_counts = {}
        self.recovery_strategies = {
            'memory_error': self._handle_memory_error,
            'compilation_error': self._handle_compilation_error,
            'execution_error': self._handle_execution_error
        }
    
    def handle_error(self, error, context):
        """Handle runtime errors with recovery strategies"""
        
        error_type = self._classify_error(error)
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        if error_type in self.recovery_strategies:
            try:
                return self.recovery_strategies[error_type](error, context)
            except Exception as recovery_error:
                self.logger.error(f"Recovery failed: {recovery_error}")
        
        # Fallback to Python execution
        return self._fallback_to_python(context)
    
    def _handle_memory_error(self, error, context):
        """Handle out-of-memory errors"""
        
        # Trigger garbage collection
        uhcr.gc.collect()
        
        # Reduce memory pool sizes
        uhcr.config.set('memory.pool_size', 
                       str(int(uhcr.config.get('memory.pool_size')[:-2]) // 2) + 'MB')
        
        # Retry with reduced memory
        return self._retry_with_reduced_memory(context)
    
    def _handle_compilation_error(self, error, context):
        """Handle compilation errors"""
        
        # Try different backend
        available_backends = uhcr.get_available_backends()
        current_backend = context.get('backend')
        
        for backend in available_backends:
            if backend != current_backend:
                try:
                    return uhcr.compile_with_backend(context, backend)
                except Exception:
                    continue
        
        # All backends failed, fall back to Python
        return self._fallback_to_python(context)

# Enable error handling
error_handler = UHCRErrorHandler()
uhcr.set_error_handler(error_handler)

@uhcr.jit(error_recovery=True)
def robust_function(data):
    # Function automatically recovers from errors
    return [x * 2 + 1 for x in data]
```

### Health Monitoring

```python
from uhcr.runtime.health import HealthMonitor

class SystemHealthMonitor:
    def __init__(self):
        self.monitors = {
            'memory': MemoryHealthMonitor(),
            'cpu': CPUHealthMonitor(), 
            'cache': CacheHealthMonitor(),
            'scheduler': SchedulerHealthMonitor()
        }
        
        self.health_status = {}
        self.alerts = []
    
    def check_health(self):
        """Check overall system health"""
        
        for name, monitor in self.monitors.items():
            try:
                status = monitor.check()
                self.health_status[name] = status
                
                if status['status'] != 'healthy':
                    self._handle_unhealthy_component(name, status)
                    
            except Exception as e:
                self.health_status[name] = {
                    'status': 'error',
                    'message': str(e),
                    'timestamp': time.time()
                }
    
    def _handle_unhealthy_component(self, component, status):
        """Handle unhealthy component"""
        
        alert = {
            'component': component,
            'status': status,
            'timestamp': time.time(),
            'severity': status.get('severity', 'warning')
        }
        
        self.alerts.append(alert)
        
        # Auto-remediation
        if component == 'memory' and status['severity'] == 'critical':
            uhcr.gc.collect()
            uhcr.cache.clear_old_entries()
            
        elif component == 'scheduler' and status['severity'] == 'warning':
            uhcr.scheduler.rebalance_workload()
    
    def get_health_report(self):
        """Generate comprehensive health report"""
        
        return {
            'overall_status': self._calculate_overall_status(),
            'components': self.health_status,
            'recent_alerts': self.alerts[-10:],  # Last 10 alerts
            'recommendations': self._generate_recommendations()
        }

# Start health monitoring
health_monitor = SystemHealthMonitor()
health_monitor.start_monitoring(interval=30)  # Check every 30 seconds
```

---

## Configuration and Tuning

### Runtime Configuration

```python
# Runtime configuration options
uhcr.config.set('runtime.scheduler.type', 'work_stealing')
uhcr.config.set('runtime.scheduler.threads', 'auto')
uhcr.config.set('runtime.memory.pool_size', '2GB')
uhcr.config.set('runtime.cache.max_size', 1000)
uhcr.config.set('runtime.profiling.enabled', True)

# Environment-specific tuning
def tune_for_environment():
    """Auto-tune runtime for current environment"""
    
    profile = uhcr.detect()
    
    # CPU-specific tuning
    if profile.cpu.cores >= 16:
        uhcr.config.set('runtime.scheduler.threads', profile.cpu.cores)
    else:
        uhcr.config.set('runtime.scheduler.threads', profile.cpu.cores * 2)
    
    # Memory-specific tuning
    memory_gb = profile.memory.total_bytes // (1024**3)
    pool_size = min(memory_gb // 4, 8)  # Use 1/4 of memory, max 8GB
    uhcr.config.set('runtime.memory.pool_size', f'{pool_size}GB')
    
    # Cache tuning
    if memory_gb >= 32:
        uhcr.config.set('runtime.cache.max_size', 5000)
    elif memory_gb >= 16:
        uhcr.config.set('runtime.cache.max_size', 2000)
    else:
        uhcr.config.set('runtime.cache.max_size', 1000)

# Apply tuning
tune_for_environment()
```

### Performance Tuning

```python
class PerformanceTuner:
    def __init__(self):
        self.benchmark_results = {}
        self.optimal_settings = {}
    
    def benchmark_configuration(self, config_name, settings):
        """Benchmark a configuration"""
        
        # Apply settings
        for key, value in settings.items():
            uhcr.config.set(key, value)
        
        # Run benchmark workload
        start_time = time.perf_counter()
        
        @uhcr.jit(eager=True)
        def benchmark_workload(n):
            return sum(i * i for i in range(n))
        
        # Multiple iterations
        times = []
        for _ in range(10):
            iter_start = time.perf_counter()
            result = benchmark_workload(100000)
            iter_time = time.perf_counter() - iter_start
            times.append(iter_time)
        
        avg_time = sum(times) / len(times)
        
        self.benchmark_results[config_name] = {
            'settings': settings.copy(),
            'avg_time': avg_time,
            'min_time': min(times),
            'max_time': max(times)
        }
        
        return avg_time
    
    def find_optimal_configuration(self):
        """Find optimal configuration through benchmarking"""
        
        configurations = [
            ('default', {}),
            ('high_thread', {'runtime.scheduler.threads': 16}),
            ('large_cache', {'runtime.cache.max_size': 5000}),
            ('big_memory', {'runtime.memory.pool_size': '4GB'}),
            ('optimized', {
                'runtime.scheduler.threads': 12,
                'runtime.cache.max_size': 3000,
                'runtime.memory.pool_size': '3GB'
            })
        ]
        
        best_config = None
        best_time = float('inf')
        
        for config_name, settings in configurations:
            avg_time = self.benchmark_configuration(config_name, settings)
            
            if avg_time < best_time:
                best_time = avg_time
                best_config = config_name
        
        self.optimal_settings = self.benchmark_results[best_config]['settings']
        return best_config, best_time

# Tune performance automatically
tuner = PerformanceTuner()
best_config, best_time = tuner.find_optimal_configuration()

print(f"Best configuration: {best_config}")
print(f"Best time: {best_time:.6f}s")

# Apply optimal settings
for key, value in tuner.optimal_settings.items():
    uhcr.config.set(key, value)
```

This comprehensive runtime documentation covers all aspects of UHCR's execution environment, from low-level memory management to high-level performance tuning.

[Next: Benchmarks →](benchmarks){: .btn .btn-primary }
[Previous: How UHCR Works ←](how-uhcr-works){: .btn }