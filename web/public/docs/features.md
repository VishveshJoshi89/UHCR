

## JIT Compilation

UHCR traces Python functions and compiles them to native machine code for maximum performance.

```python
import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

result = compute(10, 11)  # Compiled to native code!
```

**Benefits:**
- Zero-overhead native execution
- Automatic type inference
- Transparent fallback to Python
- Compilation caching for repeated calls

---

## Hardware Detection

Automatically detects and adapts to your hardware capabilities.

```python
profile = uhcr.detect()

print(f"CPU: {profile.cpu.brand}")
print(f"Features: {', '.join(profile.cpu.features)}")
print(f"GPU: {profile.gpu.name}")
print(f"CUDA: {profile.gpu.cuda_available}")
```

**Detected Information:**
- CPU vendor, cores, threads, and instruction sets (SSE, AVX2, AVX512)
- Cache hierarchy (L1, L2, L3 sizes and line sizes)
- Memory size, speed, and type (DDR3/4/5)
- GPU capabilities (CUDA, Vulkan, ROCm, Metal)
- NUMA topology

---

## Multiple Backends

UHCR automatically selects the best backend for your hardware.

| Backend | Priority | Requirements | Use Case |
|---------|----------|--------------|----------|
| **CUDA** | 15 | NVIDIA GPU + CUDA | GPU-accelerated operations |
| **AVX512** | 10 | Intel/AMD with AVX-512 | High-performance SIMD |
| **AVX2** | 5 | Intel/AMD with AVX2 | Standard SIMD operations |
| **Generic** | 1 | Any CPU | Fallback interpreter |

The runtime automatically picks the highest-priority backend that supports your hardware.

---

## Optimization Pipeline

IR code passes through multiple optimization stages before compilation.

### Constant Folding

Evaluates constant expressions at compile time:

```python
# Before optimization
%0 = add i32 3, 5
%1 = mul i32 %0, 2

# After optimization
ret i32 16
```

### Dead Code Elimination

Removes unused instructions:

```python
# Before
%0 = add i32 %arg0, %arg1   # Used
%1 = mul i32 %arg0, 10      # DEAD - never used
ret %0

# After
%0 = add i32 %arg0, %arg1
ret %0
```

### Strength Reduction

Replaces expensive operations with cheaper equivalents:

- `x * 0` → `0`
- `x * 1` → `x`
- `x + 0` → `x`
- `x - x` → `0`

### Common Subexpression Elimination (CSE)

Reuses duplicate computations:

```python
# Before
%0 = add i32 %arg0, %arg1
%1 = add i32 %arg0, %arg1   # Duplicate!
%2 = mul i32 %0, %1

# After
%0 = add i32 %arg0, %arg1
%1 = mul i32 %0, %0         # Reuses %0
```

---

## Storage Optimization

High-performance caching and persistence layer.

### Memory Pool

Pre-allocated aligned buffers for zero-allocation performance:

```python
from uhcr.storage.memory_pool import MemoryPool

pool = MemoryPool(buffer_size=1024*1024, num_buffers=100)
buf = pool.acquire()
# ... use buffer ...
pool.release(buf)
```

### Redis Cache

Fast distributed caching for compiled kernels:

```python
from uhcr.storage.redis_cache import RedisCache

cache = RedisCache()
cache.set('kernel_hash', compiled_binary, ttl=3600)
binary = cache.get('kernel_hash')
```

### SQLite Persistence

Durable storage for execution history and metrics:

```python
from uhcr.storage.sqlite_store import SQLiteStore

store = SQLiteStore('uhcr.db')
store.record_job(job_id, status, duration, result)
```

---

## Plugin System

Extend UHCR with custom backends, kernels, and optimization passes.

### Plugin Structure

```
my_plugin/
├── plugin.toml      # Manifest
├── __init__.py
└── main.py          # Entry point
```

### Example Plugin

```python
from uhcr.plugins.base import Plugin

class MyPlugin(Plugin):
    @property
    def name(self):
        return "my-plugin"
    
    def initialize(self, runtime):
        self.register_kernel("fast_relu", self._fast_relu)
        print("[MyPlugin] Loaded!")
    
    def _fast_relu(self, data):
        return [max(0.0, x) for x in data]
```

**Plugin Capabilities:**
- Custom backends for specialized hardware
- Optimized kernel implementations
- Additional IR optimization passes
- Runtime extensions

---

## Tensor API

High-level tensor operations with automatic backend dispatch.

```python
import uhcr

# Create tensors
a = uhcr.tensor([[1.0, 2.0], [3.0, 4.0]])
b = uhcr.tensor([[5.0, 6.0], [7.0, 8.0]])

# Matrix multiplication (dispatched to best backend)
c = a.matmul(b)

# Element-wise operations
d = a + b

# Convert to NumPy
numpy_array = c.to_numpy()
```

**Features:**
- N-dimensional arrays with hardware-aligned memory
- Automatic backend selection (CUDA, AVX2, etc.)
- Zero-copy interop with NumPy
- Type safety (F32, F64)

---

## Performance

UHCR delivers significant speedups over pure Python:

| Operation | Python | UHCR (AVX2) | UHCR (CUDA) | Speedup |
|-----------|--------|-------------|-------------|---------|
| Vector Add (1M) | 45ms | 2.1ms | 0.3ms | 21x - 150x |
| Matrix Multiply (512×512) | 890ms | 18ms | 3.2ms | 49x - 278x |
| Element-wise ops | 120ms | 4.5ms | 0.8ms | 27x - 150x |

*Benchmarks run on Intel i7-10700K with NVIDIA RTX 3070*

---

## Cross-Platform

UHCR works seamlessly across operating systems:

- **Windows** — Full support with MSVC and MinGW
- **Linux** — Native support with GCC/Clang
- **macOS** — Intel and Apple Silicon support

All features work consistently across platforms, with automatic hardware detection and backend selection.

---

## Getting Started

Ready to use UHCR? Check out these resources:

- [JIT Guide](jit-guide) — Learn how to use `@uhcr.jit`
- [API Reference](api-reference) — Complete API documentation
- [Plugin Guide](plugin-guide) — Extend UHCR with plugins
- [Contributing](contributing) — Join the development

[Get Started →](jit-guide){: .btn .btn-primary }
