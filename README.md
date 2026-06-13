# UHCR - Universal Hardware-Aware Compute Runtime

**Enterprise-Grade Modular Execution Stack with C++ Safety Checking**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE.txt)
[![PyPI version](https://img.shields.io/pypi/v/uhcr)](https://pypi.org/project/uhcr/)
[![Documentation](https://img.shields.io/badge/docs-Pages-purple)](https://vishveshjoshi89.github.io/UHCR-DOCS/)
[![Production Ready](https://img.shields.io/badge/production-ready-success)](SAFETY.md)
[![Enterprise](https://img.shields.io/badge/enterprise-grade-gold)](SAFETY.md)

UHCR is a production-ready Python framework for hardware-optimized computation with comprehensive safety checking, JIT compilation, and enterprise deployment tools.

## 🚀 Key Features

### 🛡️ **Enterprise Safety** (NEW in v5.0)
- **C++ Safety Checkers** - Native memory bounds, overflow detection, division-by-zero prevention
- **Runtime Protection** - Stack overflow, heap exhaustion, execution timeout enforcement
- **17 Violation Types** - Comprehensive dangerous operation detection
- **Python Fallbacks** - Full safety even without native library

### ⚡ **Performance**
- **JIT Compilation** - Traces Python functions and compiles to native machine code
- **Multi-Backend** - CPU (AVX512/AVX2/SSE), CUDA, Metal, ROCm
- **SIMD Optimization** - Automatic vectorization and hardware feature detection
- **Near-Zero Overhead** - ~1-2ns safety check latency with native library

### 🔧 **Complete CLI Toolkit** (18 Commands)
- `uhcr compile` - AOT compilation with integrity checking
- `uhcr docker/k8s` - Generate deployment manifests
- `uhcr hw` - Comprehensive hardware detection
- `uhcr safety` - Runtime safety management
- `uhcr mcp_start` - AI agent integration (MCP server)
- ...and more!

### 🏢 **Enterprise Ready**
- **Provenance Tracking** - Full build metadata and SHA-256 checksums
- **Container Support** - Docker and Kubernetes manifest generation
- **Plugin System** - Extensible architecture with TOML manifests
- **Type Safety** - Full type hints with py.typed marker

## 📦 Installation

```bash
# Basic installation
pip install uhcr

# With enterprise features
pip install uhcr[enterprise]

# With all features
pip install uhcr[all]

# Build native safety library (optional but recommended)
uhcr build
```

## 🎯 Quick Start

### Basic JIT Compilation
```python
import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

result = compute(5, 3)  # Compiled on first call
```

### With Safety Checking
```python
from uhcr.security import enable_safety_checks, safe_add, safe_mul

# Enable runtime safety
enable_safety_checks()

# Safe operations - automatically checked
result = safe_add(a, b)  # Raises SafetyViolation on overflow
result = safe_mul(x, y)  # Protected multiplication
```

### Compile for Production
```bash
# Compile Python to native with integrity checks
uhcr compile myapp.py --optimize 3

# Creates myapp.uhcrc/ with:
#   • source.py - Original code
#   • metadata.json - Build provenance
#   • checksums.json - SHA-256 integrity
#   • __main__.py - Executable runner
#   • README.md - Documentation

# Run compiled module
python myapp.uhcrc/
```

### Hardware Detection
```bash
# Full hardware report
uhcr hw

# Just the fingerprint
uhcr hw --fingerprint
# Output: Windows-AMD64-avx2-cuda_12.4+vulkan
```

### Container Deployment
```bash
# Generate Dockerfile
uhcr docker myapp.py --image mycompany/app:v1

# Generate Kubernetes manifest
uhcr k8s myapp.py --image mycompany/app:v1 \
    --replicas 5 \
    --cpu-request 500m \
    --memory-request 1Gi
```

### AI Agent Integration
```bash
# Start MCP server for AI agents
uhcr mcp_start --transport http --port 3000

# AI agents can now use UHCR tools:
#   • compile_code
#   • optimize_code
#   • detect_hardware
#   • run_benchmark
#   • generate_docker/k8s
```

## 📋 CLI Commands

```bash
uhcr -v                    # Version
uhcr hw                    # Hardware detection
uhcr compile script.py     # Compile to native
uhcr docker script.py      # Generate Dockerfile
uhcr k8s script.py         # Generate K8s manifest
uhcr safety status         # Safety system status
uhcr safety test           # Test safety features
uhcr build                 # Build C++ safety library
uhcr run script.py --jit   # Run with JIT
uhcr optimize script.py    # Optimize code
uhcr mcp_start             # Start MCP server
# ... 18 total commands
```

## 🏗️ Architecture

### Core Components
- **Compiler** - IR-based multi-backend code generation
- **Runtime** - JIT execution and memory management
- **Hardware** - CPUID, GPU detection, NUMA topology
- **Safety** - C++ bounds checking, overflow detection
- **Backends** - CPU (AVX512/AVX2), CUDA, Metal, ROCm
- **Storage** - Memory pooling and hierarchical caching
- **Network** - gRPC/HTTP server, distributed coordination

### Safety System
```
uhcr/native/
├── safety_checker.hpp     # C++ safety header
├── safety_checker.cpp     # C++ implementation
├── CMakeLists.txt         # Build config
└── build_native.py        # Python build script

uhcr/security/
├── runtime_safety.py      # Python bindings
└── __init__.py            # Public API
```

## 🛡️ Safety Features

### Memory Safety
- ✅ Buffer overflow/underflow prevention
- ✅ Null pointer dereference detection
- ✅ Array bounds validation
- ✅ Use-after-free detection

### Arithmetic Safety
- ✅ Integer overflow/underflow detection
- ✅ Division by zero prevention
- ✅ Safe casting validation

### Resource Safety
- ✅ Stack overflow protection (10K recursion limit)
- ✅ Heap exhaustion prevention (1GB limit)
- ✅ Execution timeout (30s default)
- ✅ Infinite loop detection

[Complete Safety Documentation →](SAFETY.md)

## 📊 Performance

```python
# Benchmark example
uhcr benchmark --suite tensor --output results.json

# Expected performance:
# - Native safety checks: ~1-2ns overhead
# - Python fallbacks: ~10-50ns overhead
# - JIT compilation: 10-100x speedup vs Python
```

## 🏢 Enterprise Use Cases

### Financial Services
- High-frequency trading with safety guarantees
- Risk calculation with overflow protection
- Regulatory compliance (provenance tracking)

### Healthcare
- Medical imaging processing
- Patient data analysis with safety checks
- HIPAA-compliant deployments

### AI/ML
- Model training with GPU acceleration
- Inference optimization
- AI agent integration via MCP

### DevOps
- Automated code optimization
- Container generation
- CI/CD integration

## 📚 Documentation

- [Full Documentation](https://vishveshjoshi89.github.io/UHCR)
- [Safety Guide](SAFETY.md)
- [CLI Reference](docs/cli.md)
- [API Reference](docs/api-reference.md)
- [Changelog](CHANGELOG.md)

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Development setup
git clone https://github.com/VishveshJoshi89/UHCR
cd UHCR
pip install -e .[dev]
uhcr build
pytest tests/
```

## 📄 License

[Apache License 2.0](LICENSE.txt)

## 🔗 Links

- **PyPI**: https://pypi.org/project/uhcr/
- **Repository**: https://github.com/VishveshJoshi89/UHCR
- **Documentation**: https://vishveshjoshi89.github.io/UHCR-DOCS/
- **Bug Tracker**: https://github.com/VishveshJoshi89/UHCR/issues
- **Changelog**: https://github.com/VishveshJoshi89/UHCR/blob/main/CHANGELOG.md

## 🌟 Star History

If you find UHCR useful, please consider starring the repository!

---

**Built with ❤️ for enterprise Python developers**
