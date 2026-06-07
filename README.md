# UHCR

A Python framework for hardware-optimized computation with JIT compilation across x86_64

<img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+">
<img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0">
<img src="https://img.shields.io/badge/docs-Pages-purple" alt="Docs: GitHub Pages">



[Full documentation](https://vishveshjoshi89.github.io/UHCR/)

## Install

```bash
pip install uhcr
```

## Quick Example

```python
import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2
```

## Features

- **JIT Compilation** - Traces Python functions and compiles to native machine code
- **CUDA Backend** - GPU acceleration via PTX JIT for NVIDIA hardware
- **Optimization Pipeline** - Constant folding, dead code elimination, strength reduction, CSE
- **Hardware Detection** - Automatic CPUID, GPU probe, and NUMA topology discovery
- **Storage Optimization** - High-performance memory pooling and hierarchical caching
- **Plugin System** - Extend with custom backends, kernels, and passes via TOML manifests
- **Tensor API** - High-level tensor operations dispatched to the optimal backend
- **Built-in Benchmarks** - Performance measurement suite for comparing execution paths

## License

[Apache-2.0](LICENSE.txt)