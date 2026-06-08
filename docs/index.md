---

layout: default
title: Home
nav_order: 0
------------

# UHCR

> High-performance Python JIT runtime for modern hardware

Universal Hardware-Aware Compute Runtime for Python developers.

Ship faster compute with JIT compilation, hardware-aware dispatch, and powerful plugin extensibility.

[Get Started](#quick-start) • [Explore the Docs]({{ '/quickstart/' | relative_url }})

---

## Ship production-ready compute on every device

### Hardware-aware performance

Optimized execution across CPUs, GPUs, and multiple instruction sets.

### Dynamic JIT compilation

Backend-specific optimization with runtime compilation.

### Plugin architecture

Extend UHCR with custom kernels, compiler passes, and runtime plugins.

### Modern documentation

Fast search, responsive layouts, and offline-ready docs.

---

# What is UHCR?

UHCR compiles a custom intermediate representation (IR) into native machine code while automatically selecting the optimal backend for your hardware.

### Features

* **JIT Compilation**
  Trace Python functions and compile them to native instructions

* **Hardware Detection**
  Automatic CPUID, GPU discovery, and cache-aware execution

* **Backend Flexibility**
  CUDA, AVX2, AVX512, and generic CPU support

---

# Quick Start

Install UHCR:

```bash
pip install uhcr
```

Create a compiled function:

```python
import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

result = compute(10, 11)

print(result)  # 42
```

---

# Documentation

## [Quick Start]({{ '/quickstart/' | relative_url }})

Get up and running with installation and first examples.

## [JIT Guide]({{ '/jit-guide/' | relative_url }})

Learn how to trace and compile Python functions with UHCR.

## [API Reference]({{ '/api-reference/' | relative_url }})

Browse every module, class, and supported backend API.

## [Architecture]({{ '/architecture/' | relative_url }})

Explore UHCR runtime, compiler, and storage design.

---

# Built for developers and hardware teams

## Performance-first

Automatic backend selection and IR optimizations tuned for real workloads.

## Extensible

Custom plugin support allows new backends and compiler passes.

## Modern docs

Responsive guides, search, and offline-ready content.

## Hardware aware

Detects CPU, GPU, and platform details to choose optimal execution paths.

---

# Documentation at a glance

Browse comprehensive guides, reference material, and hardware documentation that help build fast, reliable applications.

[Explore Features]({{ '/features/' | relative_url }}) • [Explore Plugins]({{ '/plugins/' | relative_url }})
