# Safety Monitor Integration

## Overview

The C++ safety monitor is integrated at every critical hardware access point in UHCR to prevent damage before operations reach hardware.

## Integration Points

### 1. Runtime System (`uhcr/runtime/runtime.py`)

**Location:** `UHCRRuntime.compile()`

**Protection:**
- CPU temperature check before compilation
- GPU temperature check for GPU workloads
- Emergency stop detection
- Prevents compilation if thermal limits exceeded

**Behavior:**
```python
cpu_status = monitor.check_cpu_temperature()
if cpu_status != 0:  # Not OK
    raise RuntimeError(f"CPU too hot: {cpu_temp}°C")
```

### 2. Executable Memory (`uhcr/compiler/x86_64/executable_memory.py`)

**Locations:**
- `ExecutableMemory.__init__()` - Allocation
- `ExecutableMemory.write()` - Writing machine code

**Protection:**
- Memory bounds validation
- Emergency stop check
- Allocation limit enforcement

**Behavior:**
- Validates memory request before `VirtualAlloc`/`mmap`
- Checks write permissions before `memmove`
- Raises `RuntimeError` on violations

### 3. CPUID Execution (`uhcr/hardware/cpuid.py`)

**Location:** `_allocate_executable_memory()`

**Protection:**
- CPU temperature check before JIT execution
- Emergency stop detection
- Prevents CPUID if CPU overheating

**Rationale:**
CPUID is a privileged instruction that can stress CPU. Must check thermal state first.

### 4. CUDA Backend (`uhcr/backends/cuda_backend.py`)

**Locations:**
- `CUDABackend.compile()` - Kernel compilation
- `cuda_runner()` - Kernel launch

**Protection:**
- GPU temperature monitoring
- Operation timeouts (60s for kernels)
- Emergency stop checks
- VRAM validation (implicit)

**Behavior:**
```python
gpu_status = monitor.check_gpu_temperature()
if gpu_status != 0:
    raise RuntimeError("GPU too hot for kernel launch")
```

### 5. AVX2 Backend (`uhcr/backends/cpu_avx2.py`)

**Location:** `CPUAVX2Backend.compile()`

**Protection:**
- CPU temperature check before SIMD compilation
- Emergency stop detection

**Rationale:**
AVX2 instructions generate significant heat. Must verify thermal headroom.

### 6. Optimization Pipeline (`uhcr/compiler/passes/pipeline.py`)

**Location:** `OptimizationPipeline.run()`

**Protection:**
- Operation timeout (30s)
- Timeout checks during iterations
- Emergency stop detection

**Behavior:**
- Starts operation timer at pipeline entry
- Checks timeout each iteration
- Aborts if exceeded
- Cleans up on exit

### 7. Memory Pool (`uhcr/storage/memory_pool.py`)

**Location:** `MemoryPool.allocate()`

**Protection:**
- Memory limit enforcement
- Allocation validation
- Current usage tracking

**Behavior:**
```python
current_usage = monitor.get_memory_usage()
if current_usage + size > 16GB:
    raise MemoryError("Would exceed safety limit")
```

### 8. IR Builder (`uhcr/compiler/ir_builder.py`)

**Location:** `IRBuilder._emit()`

**Protection:**
- Emergency stop detection on all instruction emission
- CPU temperature check for vector operations (VADD, VSUB, VMUL, VDIV, VFMADD)
- CPU temperature check for memory-intensive operations (VLOAD, VSTORE)
- CPU/GPU temperature check for high-level operations (MATMUL, RELU)

**Rationale:**
The IR builder is the bottleneck through which ALL instructions flow. By adding safety checks here, we protect against dangerous IR generation during thermal stress.

**Behavior:**
```python
# Emergency stop check
if monitor.is_emergency_stopped():
    raise RuntimeError("Emergency stop active")

# Vector operations generate significant heat
if opcode in (VADD, VSUB, VMUL, VDIV, VFMADD):
    cpu_status = monitor.check_cpu_temperature()
    if cpu_status != 0:
        raise RuntimeError(f"CPU too hot for {opcode}")
```

### 9. IR Function (`uhcr/compiler/ir.py`)

**Locations:**
- `Function.create_block()` - Basic block creation
- `Function.validate()` - Function validation

**Protection:**
- Emergency stop detection
- Complexity limit enforcement (>1000 blocks with thermal check)
- Prevents creating overly complex functions during thermal stress

**Rationale:**
Functions with many basic blocks (>1000) can cause long compilation times and CPU stress. We check temperature when complexity grows high.

**Behavior:**
```python
if len(self.blocks) > 1000:
    cpu_status = monitor.check_cpu_temperature()
    if cpu_status != 0:
        raise RuntimeError(f"CPU too hot for complex function with {len(self.blocks)} blocks")
```

## Call Flow Example

### Compilation Flow with Safety

```
User: @uhcr.jit def compute(a, b): return a + b

↓ UHCRRuntime.compile()
  → monitor.check_cpu_temperature()  ✓ 65°C OK
  → monitor.check_gpu_temperature()  ✓ N/A
  → monitor.is_emergency_stopped()   ✓ False

↓ IRBuilder (during @uhcr.jit decoration)
  → IRBuilder._emit(ADD, ...)
    → monitor.is_emergency_stopped() ✓ False
    → [Scalar ADD - no thermal check needed]
  
↓ Function.validate()
  → monitor.is_emergency_stopped()   ✓ False
  → [Validation passes]

↓ OptimizationPipeline.run()
  → monitor.start_operation(30000ms)
  → [Run passes]
  → monitor.check_timeout()          ✓ Not exceeded
  → monitor.end_operation()

↓ CPUAVX2Backend.compile()
  → monitor.check_cpu_temperature()  ✓ 67°C OK
  → monitor.is_emergency_stopped()   ✓ False

↓ X86_64CodeGenerator.compile()
  → [Generate code bytes]

↓ ExecutableMemory.__init__(size)
  → monitor.validate_memory(0, size) ✓ OK
  → VirtualAlloc(size)               ✓ Success

↓ ExecutableMemory.write(code_bytes)
  → monitor.validate_memory(addr, len, write=True) ✓ OK
  → memmove(addr, code_bytes)        ✓ Success

Result: Compiled function ready
```

### Thermal Violation Example

```
User: Compile during thermal stress

↓ UHCRRuntime.compile()
  → monitor.check_cpu_temperature()  ✗ 92°C > 85°C limit
  → RuntimeError: "CPU temperature too high (92°C)"

Result: Compilation aborted, no hardware damage
```

### IR Emission Thermal Violation Example

```
User: Build complex vector function during thermal stress

↓ IRBuilder._emit(VADD, ...)
  → monitor.is_emergency_stopped()   ✓ False
  → monitor.check_cpu_temperature()  ✗ 88°C > 85°C limit
  → RuntimeError: "CPU temperature too high (88°C) for vector operation vadd"

Result: IR emission aborted, prevents compilation stress
```

### Complex Function Thermal Violation Example

```
User: Create function with 1500 basic blocks during thermal stress

↓ Function.create_block() [block #1001]
  → monitor.is_emergency_stopped()   ✓ False
  → len(self.blocks) > 1000          ✓ True (complexity threshold)
  → monitor.check_cpu_temperature()  ✗ 86°C > 85°C limit
  → RuntimeError: "CPU temperature too high (86°C) for complex function with 1001 blocks"

Result: Complex function creation aborted, prevents compilation stress
```

### Emergency Stop Example

```
User: Trigger emergency stop

→ monitor.emergency_stop()
  Sets emergency_stopped = true

↓ Any subsequent operation:
  → monitor.is_emergency_stopped()   ✗ True
  → RuntimeError: "Emergency stop active"

Result: All operations blocked until system cools
```

## Safety Guarantees

| Operation | Check | Prevents |
|-----------|-------|----------|
| Compilation | CPU/GPU temp | Thermal damage during codegen |
| IR emission | CPU temp (vectors) | Thermal stress during IR building |
| IR emission | GPU temp (matmul) | GPU thermal damage during IR |
| Function creation | Complexity + CPU | Compilation stress from complex IR |
| Function validation | Emergency stop | Operations during critical state |
| CPUID exec | CPU temp | CPU stress during detection |
| Executable alloc | Memory limits | Resource exhaustion |
| Memory write | Bounds check | Buffer overflows |
| Kernel launch | GPU temp | GPU thermal damage |
| AVX2 codegen | CPU temp | SIMD thermal stress |
| Optimization | Timeout | Infinite loops |
| Memory pool | Allocation limits | OOM crashes |

## Performance Impact

| Integration Point | Overhead | Frequency |
|-------------------|----------|-----------|
| Temperature check | ~1µs | Per compile (rare) |
| IR emission check | ~50ns | Per IR instruction |
| Block creation check | ~30ns | Per basic block |
| Memory validation | ~20ns | Per allocation |
| Timeout check | ~50ns | Per iteration |
| Emergency check | ~5ns | Per operation |

**Total overhead:** <1% for typical workloads, ~2-3% for IR-heavy code generation

## Fallback Behavior

If native safety monitor fails to load:

1. Warning issued at runtime initialization
2. All safety checks return immediately (no-op)
3. System runs in Python-only mode
4. **No hardware protection active**

**Production deployment:** Always verify native library compiled and loaded.

## Testing Safety Integration

```python
from uhcr.native import get_safety_monitor

monitor = get_safety_monitor()

# Test temperature limits
monitor.set_max_cpu_temp(50)  # Very low for testing
# Next compilation will fail if CPU > 50°C

# Test emergency stop
monitor.emergency_stop()
# All operations now blocked

# Test memory limits
monitor.set_max_memory(1024 * 1024)  # 1MB limit
# Large allocations will fail
```

## Troubleshooting

**"CPU temperature too high"**
- Check system cooling
- Reduce workload intensity
- Wait for cooldown

**"Emergency stop active"**
- System detected critical condition
- Wait for thermal recovery
- Restart Python process

**"Memory safety check failed"**
- Reduce allocation size
- Clear memory pool
- Increase limits if safe

## Future Enhancements

- [ ] Power consumption monitoring
- [ ] Frequency throttling detection
- [ ] Per-core temperature tracking
- [ ] VRAM usage tracking
- [ ] Network-wide safety coordination
