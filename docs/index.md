---
layout: default
title: Home
nav_order: 0
---

# UHCR
[GitHub Repository](https://github.com/VishveshJoshi89/UHCR)

> Storage optimization subsystem (Redis cache, SQLite persistence, memory pooling, IO optimizer)

Universal Hardware-Aware Compute Runtime — a Python framework for hardware-optimized computation with JIT compilation across multiple ISAs. UHCR compiles a custom IR to native machine code at runtime, automatically selecting the optimal backend for your hardware.

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

## Documentation

### Guides

- [Getting Started](.) — Install UHCR and run your first program
- [JIT Guide](jit-guide) — Using the `@uhcr.jit` decorator for compilation
- [Plugin Guide](plugin-guide) — Writing and loading UHCR plugins
- [Contributing](contributing) — How to contribute to the project

### Reference

- [Architecture](architecture) — System design and module layout
- [API Reference](api-reference) — Complete API documentation
- [Hardware Detection](hardware-reference) — RAM, cache, and platform detection details
- [Optimization Passes](optimization-passes) — IR optimization pipeline details
- [Benchmarks](benchmarks) — Performance measurement and results

---

UHCR — Apache-2.0 License*
