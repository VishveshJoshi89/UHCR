# Contributing to UHCR

## Getting Started

```bash
git clone https://github.com/VishveshJoshi89/UHCR.git
cd Project
pip install -e ".[dev]"
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
uhcr/
├── api/              # User-facing Tensor and ops
├── backends/         # Execution backends (CUDA, AVX2, generic)
├── benchmarks/       # Performance benchmarks
├── compiler/         # IR, IR builder, code generation
│   ├── frontend/     # Language parser (WIP)
│   ├── x86_64/       # x86-64 assembler and codegen
│   ├── aarch64/      # ARM64 assembler and codegen
│   ├── riscv/        # RISC-V assembler and codegen
│   ├── passes/       # Compiler optimization passes
│   ├── ir.py         # IR definitions
│   ├── ir_builder.py # IR builder utilities
│   └── __init__.py   # Compiler package init
├── contanerization/  # Dockerfiles and scripts for building and testing in containers
├── frontend/         # Python bindings and user interface
├── hardware/         # Hardware detection (CPUID, GPU, memory)
├── network/          # Distributed execution and communication
├── plugins/          # Plugin system
├── runtime/          # Runtime orchestrator, memory, scheduler
├── security/         # Module signing, sandboxing (WIP)
├── storage/          # Persistent storage and caching
└── __init__.py       # Package initializer
```

## Adding a New Backend

1. Create `uhcr/backends/my_backend.py`
2. Subclass `Backend` from `uhcr.backends.backend_base`
3. Implement `name`, `priority`, `supports()`, `compile()`
4. Call `register_backend(MyBackend())` at module level
5. Import your module in `uhcr/backends/backend_selector.py`

## Adding a New ISA Target (Future)

1. Create `uhcr/compiler/<isa>/` directory
2. Implement assembler (instruction encoding)
3. Implement code generator (IR lowering)
4. Add hardware detection in `uhcr/hardware/`
5. Create a backend that uses your codegen

## Code Style

- Python 3.10+ type hints
- Docstrings on all public classes and functions
- No external dependencies in core (ctypes only)
- Cross-platform: test on Windows, Linux, macOS

## Commit Messages

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code restructuring
- `test:` adding tests

## Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the test suite
5. Submit a PR with a clear description
