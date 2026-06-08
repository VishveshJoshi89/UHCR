# UHCR Architecture

## Overview

UHCR is a layered execution stack that compiles a custom intermediate representation (IR) to native machine code at runtime, selecting the optimal execution path based on detected hardware capabilities.

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    @uhcr.jit Decorator                  │
│         Trace Python → Build IR → Compile → Cache       │
├─────────────────────────────────────────────────────────┤
│                    Application Code                     │
│              uhcr.tensor(), a.matmul(b)                 │
├─────────────────────────────────────────────────────────┤
│                      API Layer                          │
│           uhcr/api/tensor.py, uhcr/api/ops.py           │
│  - Tensor creation and shape management                 │
│  - Operation dispatch (matmul, vadd)                    │
├─────────────────────────────────────────────────────────┤
│                 IR Optimization Pipeline                │
│  Constant Fold → Strength Reduce → DCE → CSE            │
├─────────────────────────────────────────────────────────┤
│                   Compiler Pipeline                     │
│        uhcr/compiler/ir.py, ir_builder.py               │
│  - IR types: I32, I64, F32, F64, V4F32, V8F32, PTR      │
│  - Opcodes: scalar math, vector SIMD, memory, control   │
│  - High-level intrinsics: MATMUL, RELU                  │
├─────────────────────────────────────────────────────────┤
│                  Code Generation                        │
│  uhcr/compiler/x86_64/ — native x86-64 (AVX2)           │
├─────────────────────────────────────────────────────────┤
│                  Backend Selection                      │
│              uhcr/backends/                             │
│  - Backend ABC: name, priority, supports(), compile()   │
│  - Smart routing: GPU ops → CUDA, scalar → CPU          │
│  - Backends: CUDA(15) > AVX512(10) > AVX2(5) > Gen(1)   │
├─────────────────────────────────────────────────────────┤
│                Hardware Detection                       │
│              uhcr/hardware/                             │
│  - cpuid.py: JIT CPUID execution for feature flags      │
│  - gpu_detect.py: CUDA/Vulkan/ROCm/Metal probing        │
│  - memory_detect.py: RAM, NUMA, page size               │
│  - platform_info.py: aggregated HardwareProfile         │
├─────────────────────────────────────────────────────────┤
│                   Plugin System                         │
│              uhcr/plugins/                              │
│  - Plugin ABC: initialize(), shutdown()                 │
│  - PluginManager: discover, load, unload                │
│  - TOML manifest: plugin.toml                           │
│  - Registries: kernels, backends, passes                │
└─────────────────────────────────────────────────────────┘
```

## Subsystem Details

### Storage & Caching Subsystem (`uhcr.storage`)
The storage layer provides performance optimization and reliability via:
- **`MemoryPool`** (`memory_pool.py`): Manages a pre-allocated pool of `AlignedBuffer` instances, minimizing overhead by avoiding frequent runtime kernel requests.
- **`RedisCache`** (`redis_cache.py`): Houses a fast hot-tier memory storage key-value system for quick retrieval of JIT-compiled binary functions.
- **`SQLiteStore`** (`sqlite_store.py`): Serves as a persistent database for job execution metrics, histories, and server state.
- **`IOOptimizer`** (`io_optimizer.py`): Combines memory-mapped I/O, LZ4 compression, and batched writes for lightning-fast disk/network transfers.
- **`ChecksumValidator`** (`checksum.py`): SHA256-based integrity verification for cached kernels and data.

## Compilation Flow

1. **User calls** `a.matmul(b)` on a Tensor
2. **ops.py** builds IR using `IRBuilder` (emits MATMUL opcode)
3. **UHCRRuntime.compile()** checks the cache (keyed by IR hash)
4. **BackendSelector** picks the highest-priority compatible backend
5. **Backend.compile()** generates native code:
   - CUDA: generates PTX, JIT-loads via cuModuleLoadData
   - AVX2: uses X86_64CodeGenerator → assembler → ExecutableMemory
   - AArch64: uses AArch64CodeGenerator → NEON assembler → Darwin MAP_JIT ExecutableMemory
   - Generic: returns Python interpreter closure
6. **Result** is cached and returned as a callable

## Key Design Decisions

### Capability-Driven Selection
Backends declare what hardware they need (`supports(profile)`). The selector picks the best match automatically. No user configuration required.

### JIT-Only Architecture
All code generation happens at runtime. There is no ahead-of-time compilation step. This allows the runtime to adapt to the exact hardware it's running on.

### IR as the Contract
The IR is the boundary between the API layer and backends. Any backend that can lower the IR opcodes can be plugged in. This enables the multi-ISA roadmap (ARM, RISC-V).

### Interpreter Fallback
The generic backend includes a pure-Python IR interpreter. This guarantees every IR program can execute on any platform, even without native codegen support.

## Module Dependencies

```
uhcr/__init__.py
  → uhcr.hardware.platform_info (detect)
  → uhcr.api.tensor (tensor)

uhcr.api.ops
  → uhcr.compiler.ir_builder (build IR)

uhcr.hardware.platform_info
  → uhcr.hardware.cpuid
  → uhcr.hardware.gpu_detect
  → uhcr.hardware.memory_detect

uhcr.backends.backend_selector
  → uhcr.backends.cpu_generic
  → uhcr.backends.cpu_avx2
  → uhcr.backends.cpu_avx512
  → uhcr.backends.cuda_backend

uhcr.backends.cpu_avx2
  → uhcr.compiler.x86_64.codegen
  → uhcr.compiler.x86_64.executable_memory
```
