---
layout: default
title: Home
nav_order: 0
---

# UHCR
{: .fs-9 }

Universal Hardware-Aware Compute Runtime — A Python framework for hardware-optimized computation with JIT compilation.
{: .fs-6 .fw-300 }

[Get Started](#quick-start){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[View on GitHub](https://github.com/VishveshJoshi89/UHCR){: .btn .fs-5 .mb-4 .mb-md-0 }

---

## What is UHCR?

UHCR compiles a custom intermediate representation (IR) to native machine code at runtime, automatically selecting the optimal backend for your hardware. It features:

- **JIT Compilation** — Traces Python functions and compiles to native machine code
- **Hardware Detection** — Automatic CPUID, GPU probe, and NUMA topology discovery
- **Multiple Backends** — CUDA, AVX2, AVX512, and generic CPU support
- **Optimization Pipeline** — Constant folding, dead code elimination, strength reduction, CSE
- **Storage Optimization** — High-performance memory pooling and hierarchical caching
- **Plugin System** — Extend with custom backends, kernels, and passes
- **Tensor API** — High-level tensor operations dispatched to the optimal backend

---

## Quick Start

Install UHCR:

```bash
pip install uhcr
```

Basic usage:

```python
import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

t = uhcr.tensor([1.0, 2.0, 3.0])
result = compute(10, 11)
print(result)  # 42
```

---

## Documentation

### Guides

- [JIT Guide](jit-guide) — Using the `@uhcr.jit` decorator for compilation
- [Plugin Guide](plugin-guide) — Writing and loading UHCR plugins
- [Contributing](contributing) — How to contribute to the project

### Reference

- [Architecture](architecture) — System design and module layout
- [API Reference](api-reference) — Complete API documentation
- [Hardware Detection](hardware-reference) — RAM, cache, and platform detection details
- [Optimization Passes](optimization-passes) — IR optimization pipeline details
- [Storage Subsystem](storage) — Caching, persistence, and memory management

---

## License

UHCR is licensed under the [Apache-2.0 License](https://github.com/VishveshJoshi89/UHCR/blob/main/LICENSE.txt).
