# UHCR — Universal Hardware-Aware Compute Runtime

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE.txt)
[![PyPI version](https://img.shields.io/pypi/v/uhcr)](https://pypi.org/project/uhcr/)
[![Documentation](https://img.shields.io/badge/docs-uhcr--docs.vercel.app-purple)](https://uhcr-docs.vercel.app/)

**UHCR integrates with your existing Python stack and optimizes performance automatically based on your actual hardware — no rewrites, no migration, zero config.**

```bash
pip install uhcr
```

```python
import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

result = compute(5, 3)  # Your existing code. Now hardware-optimized.
```

That's it. UHCR detects your hardware and selects the best execution path automatically.

---

## Why UHCR

Most performance tools ask you to rewrite your code for a specific backend — NumPy for arrays, Numba for loops, CUDA for GPU. UHCR doesn't. It sits underneath your existing code and makes it hardware-aware.

| Workload | Python | UHCR | Speedup |
|---|---|---|---|
| Loop (1K iterations) | 75.9 µs | 500 ns | **152x faster** |
| Array add (1K) + AVX2 plugin | 173 µs | 3.90 µs | **44x faster** |
| Matmul 32×32 | 7.36 ms | 217 µs | **34x faster** |
| Scalar add | 100 ns | 1.20 µs | slower (ctypes overhead) |

> Benchmarks on Intel i7-7600U, AVX2, Windows 10. Scalar ops have ctypes call overhead — UHCR is designed for compute-bound workloads, not single-call trivial ops.

---

## When To Use UHCR

| Use Case | Recommendation |
|---|---|
| Loop-heavy computation | ✅ UHCR base — 152x gain |
| Array operations | ✅ UHCR + plugin — 44x gain |
| Matrix operations | ✅ UHCR base — 34x gain |
| Single scalar calls | ❌ Use plain Python |
| Already using NumPy BLAS | ❌ NumPy wins for pure matmul |

---

## How It Works

UHCR uses a **plugin architecture**. The core runtime handles JIT compilation, hardware detection, IR generation, and backend selection. Plugins extend it for specific hardware or workloads — without touching core code.

```
Your Code
    ↓
UHCR Core (JIT + IR + Hardware Detection)
    ↓
Plugin Layer (AVX2 / CUDA / Docker / Custom)
    ↓
Your Hardware
```

Backend priority (auto-selected): `CUDA (15) → AVX512 (10) → AVX2 (5) → Generic CPU (1)`

---

## Installation

```bash
# Standard install
pip install uhcr

# Build native C++ safety library (optional, recommended)
uhcr build
```

---

## Core Usage

### JIT Compilation

```python
import uhcr

# Eager — compiles on first call
@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

# Lazy — compiles after 3 calls (default)
@uhcr.jit()
def heavy_loop(n):
    result = 0
    for i in range(n):
        result += i
    return result
```

### Hardware Detection

```bash
uhcr hw
# Output: Windows-AMD64-avx2-cuda_12.4+vulkan

uhcr hw --fingerprint
```

```python
from uhcr.hardware import detect
profile = detect()
print(profile.cpu.features)   # ['avx2', 'sse4_2', 'fma', ...]
print(profile.gpu.available)  # True
```

### Plugin System

```bash
# Auto-discovers plugins in ./plugins/ or ~/.uhcr/plugins/
uhcr run my_script.py

# Load specific plugin
uhcr --plugin avx2_optimizer run my_script.py
```

```python
from uhcr.plugins import PluginManager
pm = PluginManager(runtime=uhcr.get_runtime())
pm.load_all()
```

Plugin manifest (`plugin.toml`):
```toml
[plugin]
name = "my-plugin"
version = "1.0.0"
entry_point = "my_plugin.main"
```

### Safety Checks (v5+)

```python
from uhcr.security import enable_safety_checks, safe_add

enable_safety_checks()
result = safe_add(a, b)  # Raises SafetyViolation on overflow
```

```bash
uhcr safety status   # Check safety system
uhcr safety test     # Run safety suite
```

### Container Deployment

```bash
# Generate Dockerfile
uhcr docker myapp.py --image myorg/app:v1

# Generate Kubernetes manifest
uhcr k8s myapp.py --image myorg/app:v1 --replicas 3
```

### AI Agent Integration (MCP)

```bash
# Start MCP server
uhcr mcp_start --transport stdio

# Or HTTP mode
uhcr mcp_start --transport http --port 3000
```

AI agents (Claude, Cursor, Kiro) can then call:
- `detect_hardware` — live hardware profile
- `compile_function` — JIT-compile a function
- `benchmark` — run and time a callable
- `list_backends` — available backends and priorities
- `optimize_ir` — run IR optimization pipeline

See the [MCP Integration Guide](https://uhcr-docs.vercel.app/#/docs/mcp-integration) for config examples.

---

## CLI Reference

```bash
uhcr -v                      # Version
uhcr hw                      # Hardware detection
uhcr hw --fingerprint        # ISA fingerprint only
uhcr compile script.py       # AOT compile to .uhcrc/
uhcr run script.py --jit     # Run with JIT enabled
uhcr optimize script.py      # Optimize code
uhcr docker script.py        # Generate Dockerfile
uhcr k8s script.py           # Generate K8s manifest
uhcr safety status           # Safety system status
uhcr safety test             # Test safety features
uhcr build                   # Build C++ native library
uhcr mcp_start               # Start MCP server
uhcr benchmark               # Run benchmark suite
```

---

## Architecture

```
uhcr/
├── compiler/     # IR-based multi-backend code generation
├── runtime/      # JIT execution and memory management
├── hardware/     # CPUID, GPU detection, NUMA topology
├── security/     # C++ bounds checking, overflow detection
├── backends/     # CPU (AVX512/AVX2), CUDA, Metal, ROCm
├── storage/      # Memory pooling and hierarchical caching
├── network/      # gRPC/HTTP server, distributed coordination
├── plugins/      # First-party plugin base and PluginManager
└── native/       # C++ safety checker (optional build)

plugins/          # Third-party / user plugins (runtime-discovered)
mcp/              # MCP server for AI agent integration
```

---

## Plugin Tiers

| Tier | Location | Access | Use For |
|---|---|---|---|
| First-party | `uhcr/plugins/` | Full internal API | Official backends, built-in passes |
| Third-party | `plugins/` or `~/.uhcr/plugins/` | Public API only | Custom hardware, user extensions |

---

## Multi-ISA Support

UHCR targets multiple ISAs from a single codebase:

- x86_64 — AVX512, AVX2, SSE4.2
- AArch64 — NEON, SVE
- RISC-V — RVV (Vector Extension)
- CUDA — via CUDA backend
- Generic — fallback for any hardware

See [Multi-ISA Guide](https://uhcr-docs.vercel.app/#/docs/multi-isa).

---

## Documentation

| Resource | Link |
|---|---|
| Full Docs | https://uhcr-docs.vercel.app |
| Quick Start | https://uhcr-docs.vercel.app/#/docs/quickstart |
| Plugin Guide | https://uhcr-docs.vercel.app/#/docs/plugin-guide |
| MCP Integration | https://uhcr-docs.vercel.app/#/docs/mcp-integration |
| Benchmarks | https://uhcr-docs.vercel.app/#/docs/benchmarks |
| Safety Guide | https://uhcr-docs.vercel.app/#/docs/safety |
| API Reference | https://uhcr-docs.vercel.app/#/docs/api-reference |
| CLI Reference | https://uhcr-docs.vercel.app/#/docs/cli |
| Changelog | CHANGELOG.md |

---

## Contributing

```bash
git clone https://github.com/VishveshJoshi89/UHCR
cd UHCR
pip install -e .[dev]
uhcr build
pytest tests/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[Apache License 2.0](LICENSE.txt)

---

## Links

- **PyPI** — https://pypi.org/project/uhcr/
- **Repository** — https://github.com/VishveshJoshi89/UHCR
- **Documentation** — https://uhcr-docs.vercel.app
- **Issues** — https://github.com/VishveshJoshi89/UHCR/issues
- **Changelog** — https://github.com/VishveshJoshi89/UHCR/blob/main/CHANGELOG.md
