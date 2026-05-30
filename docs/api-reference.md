---
layout: default
title: API Reference
nav_order: 5
---

# UHCR API Reference

## Top-Level Functions

### `uhcr.detect() → HardwareProfile`
Detects and returns the hardware capabilities of the current machine. Result is cached after first call.

### `uhcr.get_runtime() → UHCRRuntime`
Returns the global runtime singleton. Creates it on first call.

### `uhcr.tensor(data, dtype=None) → Tensor`
Creates a Tensor from nested Python lists. Default dtype is `Type.F32`.

```python
t = uhcr.tensor([[1.0, 2.0], [3.0, 4.0]])
```

---

## Tensor Class

### `Tensor(data, shape=None, dtype=Type.F32)`
N-dimensional hardware-aligned array.

**Properties:**
- `shape: Tuple[int, ...]` — dimensions
- `dtype: Type` — element type (F32 or F64)
- `address: int` — native memory address (64-byte aligned)
- `buffer: AlignedBuffer` — underlying memory

**Methods:**
- `matmul(other: Tensor) → Tensor` — matrix multiplication
- `__add__(other: Tensor) → Tensor` — element-wise addition
- `to_numpy() → np.ndarray` — convert to NumPy (requires numpy)

---

## IR Builder

### `IRBuilder`
Fluent API for constructing UHCR IR programs.

```python
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder

builder = IRBuilder()
builder.new_module()
func = builder.new_function("name", [Type.I64, Type.I64], Type.I64)
entry = func.create_block("entry")
builder.set_block(entry)
```

**Math Operations:**
- `builder.add(a, b)` — integer/float add (type-inferred)
- `builder.sub(a, b)` — subtract
- `builder.mul(a, b)` — multiply
- `builder.div(a, b)` — divide

**Vector Operations (SIMD):**
- `builder.vload(ptr, offset, type)` — load vector from memory
- `builder.vstore(val, ptr, offset)` — store vector to memory
- `builder.vadd(a, b)` — vector add
- `builder.vsub(a, b)` — vector subtract
- `builder.vmul(a, b)` — vector multiply
- `builder.vdiv(a, b)` — vector divide
- `builder.vfmadd(acc, a, b)` — fused multiply-add

**Memory:**
- `builder.load(ptr, offset, type)` — scalar load
- `builder.store(val, ptr, offset)` — scalar store

**Control Flow:**
- `builder.cmp(cond, a, b)` — compare (eq, ne, lt, le, gt, ge)
- `builder.br(cond, true_block, false_block)` — conditional branch
- `builder.jmp(block)` — unconditional jump
- `builder.ret(val=None)` — return

**High-Level:**
- `builder.matmul(a, b, out)` — matrix multiply intrinsic
- `builder.relu(a, out)` — ReLU activation intrinsic

---

## IR Types

| Type | Description | Width |
|------|-------------|-------|
| `Type.I32` | 32-bit integer | 4 bytes |
| `Type.I64` | 64-bit integer | 8 bytes |
| `Type.F32` | 32-bit float | 4 bytes |
| `Type.F64` | 64-bit float | 8 bytes |
| `Type.V4F32` | 4x float vector | 16 bytes (SSE/NEON) |
| `Type.V8F32` | 8x float vector | 32 bytes (AVX2) |
| `Type.PTR` | Memory pointer | 8 bytes |
| `Type.VOID` | No value | 0 bytes |

---

## Hardware Profile

### `HardwareProfile`
- `os: str` — "Windows", "Linux", "Darwin"
- `architecture: str` — "AMD64", "x86_64", "aarch64"
- `cpu: CPUCapabilities`
- `gpu: GPUCapabilities`
- `memory: MemoryCapabilities`

**Methods:**
- `to_json() → str` — JSON serialization
- `get_fingerprint() → str` — capability signature
- `format_table() → str` — formatted CLI output

---

## AlignedBuffer

### `AlignedBuffer(size_bytes, alignment=64)`
SIMD-safe aligned memory allocation.

```python
from uhcr.runtime.memory_manager import AlignedBuffer

with AlignedBuffer(1024, alignment=64) as buf:
    arr = buf.as_ctypes_array(ctypes.c_float)
    arr[0] = 3.14
```

**Methods:**
- `as_ctypes_array(ctypes_type)` — get typed array view
- `copy_from(bytes)` — write raw bytes
- `copy_to() → bytes` — read raw bytes
- `free()` — release memory

---

## Scheduler

### `Scheduler(num_threads=None)`
Parallel work distribution with thread pinning.

```python
from uhcr.runtime.scheduler import Scheduler

sched = Scheduler(num_threads=4)
sched.parallel_for(1000, lambda start, end: process(start, end))
```

---

## Storage Optimizer

### `StorageOptimizer`
Facade coordinating Redis cache, SQLite persistence, memory pool, and I/O optimization.

```python
from uhcr.storage import StorageOptimizer

storage = StorageOptimizer()
await storage.initialize()

# Access underlying components:
# - storage.redis_cache: RedisCache
# - storage.sqlite_store: SQLiteStore
# - storage.memory_pool: MemoryPool
# - storage.io_optimizer: IOOptimizer

await storage.shutdown()
```

---
