# UHCR Plugin System
---
## Overview

UHCR's plugin system allows developers to extend the runtime with:

- **Custom Backends** — New ISA targets and hardware accelerators
- **Optimization Passes** — IR transformations and code optimizations  
- **Compute Kernels** — Specialized operation implementations
- **Storage Adapters** — Custom caching and persistence layers
- **Network Protocols** — Distributed computing extensions

All plugins are dynamically loaded using TOML manifests and Python entry points.

---

## Plugin Architecture

### Plugin Discovery

UHCR discovers plugins through multiple mechanisms:

```python
# Plugin discovery process
import uhcr.plugins

# 1. Built-in plugins (always available)
builtin_plugins = uhcr.plugins.get_builtin()

# 2. Installed package plugins (via entry points)  
package_plugins = uhcr.plugins.discover_packages()

# 3. Local directory plugins (development)
local_plugins = uhcr.plugins.discover_local('./plugins/')

# 4. Environment variable plugins
env_plugins = uhcr.plugins.discover_env('UHCR_PLUGIN_PATH')

print(f"Found {len(builtin_plugins + package_plugins)} plugins")
```

### Plugin Lifecycle

```python
# Plugin lifecycle management
from uhcr.plugins import PluginManager

manager = PluginManager()

# Load all discovered plugins
loaded_count = manager.load_all()
print(f"Loaded {loaded_count} plugins")

# Query loaded plugins
print("Loaded plugin names:", list(manager.loaded_plugins))
```

---

## Execution Modes

### Normal execution (built-in runtime)

UHCR runs normally with its built-in backend support without requiring any custom plugins.

```python
import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

print(compute(10, 20))
```

No plugin manager invocation is required for normal execution. Built-in backend plugins such as `cpu-generic`, `cpu-avx2`, `cpu-avx512`, and `cuda-ptx` are available automatically when supported by the host.

### With plugins

Load custom plugins explicitly when you want additional backends, kernels, or optimization passes.

```python
from pathlib import Path
from uhcr.plugins import PluginManager

manager = PluginManager()
loaded = manager.load_all([Path('plugins')])
print(f'Loaded {loaded} plugins')
print('Loaded plugin names:', list(manager.loaded_plugins))
```

To load a single plugin directory:

```python
plugin_dir = Path('plugins/example_plugin')
manager.load_single(plugin_dir)
```

### Without plugins

If you want to run UHCR without custom plugins, simply do not call the plugin loader.

```python
import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return a * b

print(compute(3, 5))
```

This ensures UHCR runs on the default built-in backends only. To be explicit, avoid `PluginManager.load_all()` and unset `UHCR_PLUGIN_PATH` if it is defined.

---

## Built-in Plugins

### Backend Plugins

UHCR includes several built-in backend plugins:

| Plugin | Target | Features |
|--------|--------|----------|
| `cpu-generic` | Generic x86_64 | Scalar operations, basic optimizations |
| `cpu-avx2` | AVX2-capable CPUs | 256-bit SIMD, vectorized loops |
| `cpu-avx512` | AVX512-capable CPUs | 512-bit SIMD, advanced intrinsics |
| `cuda-ptx` | NVIDIA GPUs | CUDA kernels, GPU memory management |

```python
# List available backend plugins
import uhcr

# Get all backend plugins
backends = uhcr.plugins.get_category('backend')

for backend in backends:
    print(f"{backend.name}: {backend.description}")
    print(f"  Targets: {', '.join(backend.supported_targets)}")
    print(f"  Priority: {backend.priority}")
```

### Optimizer Plugins

Built-in optimization passes:

```python
# Optimization pipeline with plugins
from uhcr.compiler import IRBuilder, OptimizationPipeline

builder = IRBuilder()
# ... build IR ...

# Create optimization pipeline
pipeline = OptimizationPipeline([
    'constant-folding',      # Built-in plugin
    'dead-code-elimination', # Built-in plugin
    'strength-reduction',    # Built-in plugin
    'common-subexpression',  # Built-in plugin
    'custom-optimizer'       # Custom plugin
])

optimized_ir = pipeline.run(builder.module)
```

---

## Plugin Development

### Plugin Manifest

Create a TOML manifest for your plugin:

```toml
# plugin.toml
[plugin]
name = "my-custom-backend"
version = "1.0.0"
description = "Custom backend for specialized hardware"
author = "Your Name <email@example.com>"
license = "MIT"

[plugin.metadata]
category = "backend"
priority = 100
supported_targets = ["custom-isa"]
requires_uhcr = ">=1.0.0"

[plugin.dependencies]
numpy = ">=1.21.0"
custom_compiler = ">=2.0.0"

[plugin.entry_points]
backend = "my_plugin.backend:CustomBackend"
optimizer = "my_plugin.optimizer:CustomOptimizer"

[plugin.configuration]
enable_debug = false
optimization_level = 2
custom_flags = []
```

### Backend Plugin Implementation

```python
# my_plugin/backend.py
from uhcr.backends.backend_base import BackendBase
from uhcr.compiler.ir import Module, Type
import logging

class CustomBackend(BackendBase):
    """Custom backend for specialized hardware"""
    
    def __init__(self, config=None):
        super().__init__()
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize custom compiler
        self.compiler = self._init_compiler()
    
    @property
    def name(self) -> str:
        return "custom-backend"
    
    @property
    def priority(self) -> int:
        return 100
    
    @property
    def supported_targets(self) -> list[str]:
        return ["custom-isa", "custom-accelerator"]
    
    def can_compile(self, module: Module) -> bool:
        """Check if this backend can compile the given IR module"""
        
        # Check for unsupported operations
        unsupported_ops = {'NETWORK_SEND', 'FILE_IO'}
        
        for instruction in module.get_instructions():
            if instruction.opcode in unsupported_ops:
                return False
        
        return True
    
    def compile(self, module: Module) -> bytes:
        """Compile IR module to native code"""
        
        self.logger.info(f"Compiling module with {len(module.functions)} functions")
        
        # Generate custom assembly
        assembly = self._generate_assembly(module)
        
        # Assemble to machine code
        machine_code = self.compiler.assemble(assembly)
        
        # Apply custom optimizations
        if self.config.get('enable_optimizations', True):
            machine_code = self._apply_optimizations(machine_code)
        
        return machine_code
    
    def execute(self, code: bytes, args: list) -> any:
        """Execute compiled code with given arguments"""
        
        # Load code into custom runtime
        function = self.compiler.load_code(code)
        
        # Convert arguments to custom format
        custom_args = [self._convert_arg(arg) for arg in args]
        
        # Execute on custom hardware
        result = function(*custom_args)
        
        return self._convert_result(result)
    
    def _init_compiler(self):
        """Initialize custom compiler"""
        # Custom implementation
        pass
    
    def _generate_assembly(self, module: Module) -> str:
        """Generate assembly code for custom ISA"""
        
        assembly = []
        
        for function in module.functions:
            assembly.append(f".function {function.name}")
            
            for block in function.blocks:
                assembly.append(f".block {block.name}:")
                
                for instruction in block.instructions:
                    asm_line = self._compile_instruction(instruction)
                    assembly.append(f"    {asm_line}")
        
        return '\n'.join(assembly)
    
    def _compile_instruction(self, instruction) -> str:
        """Compile single IR instruction to assembly"""
        
        opcode_map = {
            'ADD': 'add.i64',
            'SUB': 'sub.i64', 
            'MUL': 'mul.i64',
            'LOAD': 'ld',
            'STORE': 'st',
            'RET': 'ret'
        }
        
        asm_op = opcode_map.get(instruction.opcode, 'unknown')
        
        if instruction.operands:
            operands = ', '.join(str(op) for op in instruction.operands)
            return f"{asm_op} {operands}"
        else:
            return asm_op
```

### Optimizer Plugin Implementation

```python
# my_plugin/optimizer.py
from uhcr.compiler.optimization import OptimizationPass
from uhcr.compiler.ir import Module, Instruction

class CustomOptimizer(OptimizationPass):
    """Custom optimization pass"""
    
    def __init__(self, config=None):
        super().__init__()
        self.config = config or {}
        self.name = "custom-optimizer"
    
    def run(self, module: Module) -> Module:
        """Run custom optimization on IR module"""
        
        modified = False
        
        for function in module.functions:
            for block in function.blocks:
                # Apply custom optimization patterns
                modified |= self._optimize_block(block)
        
        if modified:
            self.logger.info(f"Applied {self.name} optimization")
        
        return module
    
    def _optimize_block(self, block) -> bool:
        """Optimize instructions in a basic block"""
        
        modified = False
        instructions = list(block.instructions)
        
        # Pattern: x * 1 → x
        for i, instr in enumerate(instructions):
            if (instr.opcode == 'MUL' and 
                len(instr.operands) == 2 and
                instr.operands[1].is_constant() and
                instr.operands[1].value == 1):
                
                # Replace multiplication by 1 with move
                new_instr = Instruction('MOV', [instr.operands[0]])
                instructions[i] = new_instr
                modified = True
        
        # Pattern: x + 0 → x  
        for i, instr in enumerate(instructions):
            if (instr.opcode == 'ADD' and
                len(instr.operands) == 2 and
                instr.operands[1].is_constant() and
                instr.operands[1].value == 0):
                
                # Replace addition by 0 with move
                new_instr = Instruction('MOV', [instr.operands[0]])
                instructions[i] = new_instr
                modified = True
        
        if modified:
            block.instructions = instructions
        
        return modified
```

---

## Plugin Installation

### Package Installation

Install plugins as Python packages:

```bash
# Install from PyPI
pip install uhcr-custom-backend

# Install from source
pip install git+https://github.com/user/uhcr-plugin.git

# Install local development plugin
pip install -e ./my-plugin/
```

### Local Development

For plugin development, use local directories:

```python
# Development setup
import uhcr.plugins

# Add local plugin directory
uhcr.plugins.add_search_path('./my-plugins/')

# Load development plugin
plugin = uhcr.plugins.load_local('./my-plugins/custom-backend/')

# Activate for testing
uhcr.plugins.activate(plugin)
```

---

## Plugin Configuration

### Global Configuration

Configure plugins in `uhcr.toml`:

```toml
# uhcr.toml
[plugins]
search_paths = ["./plugins", "~/.uhcr/plugins"]
auto_load = true
enable_remote = false

[plugins.backends]
prefer = ["custom-backend", "cuda-ptx", "cpu-avx512"]
fallback = "cpu-generic"

[plugins.optimizers]
enable_all = true
custom_pipeline = [
    "constant-folding",
    "custom-optimizer", 
    "dead-code-elimination"
]

# Plugin-specific configuration
[plugins.config.custom-backend]
optimization_level = 3
enable_debug = true
custom_flags = ["--fast-math", "--vectorize"]
```

### Runtime Configuration

```python
# Runtime plugin configuration
import uhcr

# Configure specific plugin
uhcr.plugins.configure('custom-backend', {
    'optimization_level': 2,
    'enable_profiling': True,
    'memory_limit': '4GB'
})

# Get plugin configuration
config = uhcr.plugins.get_config('custom-backend')
print(f"Optimization level: {config['optimization_level']}")
```

---

## Advanced Plugin Features

### Plugin Dependencies

```python
# Plugin with dependencies
from uhcr.plugins.base import PluginBase

class AdvancedPlugin(PluginBase):
    
    dependencies = ['base-optimizer', 'memory-manager']
    
    def load(self):
        """Load plugin after dependencies are satisfied"""
        
        # Access dependency plugins
        optimizer = self.get_dependency('base-optimizer')
        memory_mgr = self.get_dependency('memory-manager')
        
        # Initialize with dependencies
        self._init_with_deps(optimizer, memory_mgr)
    
    def _init_with_deps(self, optimizer, memory_mgr):
        """Initialize plugin with dependencies"""
        self.optimizer = optimizer
        self.memory_manager = memory_mgr
```

### Plugin Communication

```python
# Inter-plugin communication
from uhcr.plugins import PluginRegistry

class CommunicatingPlugin(PluginBase):
    
    def __init__(self):
        super().__init__()
        self.registry = PluginRegistry.get_instance()
    
    def send_message(self, target_plugin: str, message: dict):
        """Send message to another plugin"""
        
        target = self.registry.get_plugin(target_plugin)
        if target and hasattr(target, 'receive_message'):
            target.receive_message(self.name, message)
    
    def receive_message(self, sender: str, message: dict):
        """Receive message from another plugin"""
        
        self.logger.info(f"Received message from {sender}: {message}")
        
        # Handle different message types
        if message['type'] == 'optimization_hint':
            self._apply_optimization_hint(message['data'])
        elif message['type'] == 'performance_data':
            self._update_performance_model(message['data'])
```

### Plugin Hooks

```python
# Plugin lifecycle hooks
from uhcr.plugins.hooks import PluginHooks

@PluginHooks.on_load
def on_plugin_load(plugin):
    """Called when any plugin is loaded"""
    print(f"Plugin loaded: {plugin.name}")

@PluginHooks.on_compile_start
def on_compile_start(module):
    """Called before compilation starts"""
    # Pre-compilation setup
    pass

@PluginHooks.on_compile_end
def on_compile_end(module, result):
    """Called after compilation completes"""
    # Post-compilation cleanup
    pass

class HookedPlugin(PluginBase):
    
    @PluginHooks.register('before_optimization')
    def prepare_optimization(self, module):
        """Custom hook for optimization preparation"""
        # Plugin-specific preparation
        return module

    @PluginHooks.register('after_execution')
    def cleanup_execution(self, result):
        """Custom hook for post-execution cleanup"""
        # Plugin-specific cleanup
        return result
```

---

## Plugin Testing

### Unit Testing

```python
# test_custom_plugin.py
import unittest
from unittest.mock import Mock, patch
import uhcr
from my_plugin.backend import CustomBackend

class TestCustomBackend(unittest.TestCase):
    
    def setUp(self):
        self.backend = CustomBackend({
            'optimization_level': 2,
            'enable_debug': True
        })
    
    def test_can_compile_basic_module(self):
        """Test basic compilation capability"""
        
        # Create test IR module
        from uhcr.compiler.ir_builder import IRBuilder
        
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test", [], uhcr.Type.I64)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        # Add simple operations
        a = builder.constant(42, uhcr.Type.I64)
        b = builder.constant(7, uhcr.Type.I64)
        result = builder.add(a, b)
        builder.ret(result)
        
        module = builder.module
        
        # Test compilation
        self.assertTrue(self.backend.can_compile(module))
        
        compiled = self.backend.compile(module)
        self.assertIsInstance(compiled, bytes)
        self.assertGreater(len(compiled), 0)
    
    def test_execute_compiled_code(self):
        """Test code execution"""
        
        # Mock compiled code
        mock_code = b'\x48\x89\xc8'  # Simple assembly
        
        with patch.object(self.backend, 'compile', return_value=mock_code):
            result = self.backend.execute(mock_code, [42, 7])
            self.assertIsNotNone(result)
    
    def test_optimization_config(self):
        """Test optimization configuration"""
        
        self.assertEqual(self.backend.config['optimization_level'], 2)
        self.assertTrue(self.backend.config['enable_debug'])

if __name__ == '__main__':
    unittest.main()
```

### Integration Testing

```python
# test_plugin_integration.py
import uhcr
import pytest

@pytest.fixture
def loaded_plugin():
    """Load plugin for testing"""
    
    # Load custom plugin
    plugin = uhcr.plugins.load('custom-backend')
    uhcr.plugins.activate(plugin)
    
    yield plugin
    
    # Cleanup
    uhcr.plugins.deactivate(plugin)

def test_plugin_integration(loaded_plugin):
    """Test plugin integration with UHCR"""
    
    @uhcr.jit(backend='custom-backend')
    def test_function(x, y):
        return x + y * 2
    
    # Test compilation and execution
    result = test_function(10, 5)
    assert result == 20
    
    # Verify plugin was used
    assert uhcr.get_last_backend() == 'custom-backend'

def test_plugin_optimization(loaded_plugin):
    """Test plugin optimization passes"""
    
    from uhcr.compiler.ir_builder import IRBuilder
    
    # Create suboptimal IR
    builder = IRBuilder()
    # ... create IR with optimization opportunities ...
    
    # Apply plugin optimizations
    optimized = uhcr.optimize(builder.module, passes=['custom-optimizer'])
    
    # Verify optimizations were applied
    assert optimized.instruction_count < builder.module.instruction_count
```

---

## Plugin Distribution

### Package Structure

```
my-uhcr-plugin/
├── setup.py
├── plugin.toml
├── my_plugin/
│   ├── __init__.py
│   ├── backend.py
│   ├── optimizer.py
│   └── utils.py
├── tests/
│   ├── test_backend.py
│   └── test_optimizer.py
└── README.md
```

### Setup Script

```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="uhcr-custom-backend",
    version="1.0.0",
    description="Custom backend plugin for UHCR",
    author="Your Name",
    author_email="email@example.com",
    packages=find_packages(),
    install_requires=[
        "uhcr>=1.0.0",
        "numpy>=1.21.0"
    ],
    entry_points={
        "uhcr.plugins.backend": [
            "custom-backend = my_plugin.backend:CustomBackend"
        ],
        "uhcr.plugins.optimizer": [
            "custom-optimizer = my_plugin.optimizer:CustomOptimizer"
        ]
    },
    include_package_data=True,
    package_data={
        "my_plugin": ["plugin.toml"]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10+",
    ],
)
```

This comprehensive plugin guide provides everything needed to understand, develop, and distribute UHCR plugins effectively.

[Next: How UHCR Works →](how-uhcr-works){: .btn .btn-primary }
[Previous: Containerization ←](containerization){: .btn }