# UHCR Plugin Guide

## Overview

The UHCR plugin system allows you to extend the runtime with custom backends, kernels, and optimization passes without modifying the core codebase.

## Plugin Structure

A plugin is a directory containing:

```
my_plugin/
├── plugin.toml      # Manifest (required)
├── __init__.py      # Package init
└── main.py          # Entry point module
```

## Plugin Manifest (plugin.toml)

```toml
[plugin]
name = "my-custom-backend"
version = "0.1.0"
author = "Your Name"
description = "A custom backend for specialized hardware"
entry_point = "plugin.main"
dependencies = []
min_uhcr_version = "0.1.0"
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique plugin identifier |
| `version` | Yes | Semantic version string |
| `author` | No | Plugin author |
| `description` | No | Human-readable description |
| `entry_point` | Yes | Python module path containing the Plugin class |
| `dependencies` | No | List of required pip packages |
| `min_uhcr_version` | No | Minimum UHCR version required |

## Writing a Plugin

### Step 1: Create the Plugin Class

```python
# my_plugin/main.py
from uhcr.plugins.base import Plugin

class MyPlugin(Plugin):
    @property
    def name(self) -> str:
        return "my-plugin"

    @property
    def version(self) -> str:
        return "0.1.0"

    def initialize(self, runtime) -> None:
        """Called when the plugin is loaded."""
        # Register your extensions here
        self.register_kernel("my_fast_relu", self._fast_relu)
        print(f"[MyPlugin] Loaded!")

    def shutdown(self) -> None:
        """Called when the plugin is unloaded."""
        print(f"[MyPlugin] Goodbye!")

    def _fast_relu(self, data):
        return [max(0.0, x) for x in data]
```

### Step 2: Register Extensions

Plugins can register three types of extensions:

#### Custom Backends

```python
from uhcr.backends.backend_base import Backend

class MyBackend(Backend):
    @property
    def name(self): return "my_backend"

    @property
    def priority(self): return 20  # Higher = preferred

    def supports(self, profile): return True

    def compile(self, func):
        # Your compilation logic
        ...

class MyPlugin(Plugin):
    def initialize(self, runtime):
        self.register_backend(MyBackend())
```

#### Custom Kernels

```python
class MyPlugin(Plugin):
    def initialize(self, runtime):
        self.register_kernel("fast_matmul", self._matmul)

    def _matmul(self, a, b, out, m, n, k):
        # Your optimized implementation
        ...
```

#### Optimization Passes

```python
class MyPlugin(Plugin):
    def initialize(self, runtime):
        self.register_pass("constant_fold", self._constant_fold)

    def _constant_fold(self, ir_function):
        # Transform the IR and return optimized version
        return ir_function
```

## Loading Plugins

### Automatic Discovery

Plugins are discovered from:
1. `./plugins/` (project-local)
2. `~/.uhcr/plugins/` (user-global)

```python
from uhcr.plugins import PluginManager

pm = PluginManager(runtime=uhcr.get_runtime())
count = pm.load_all()
print(f"Loaded {count} plugins")
```

### Manual Loading

```python
from pathlib import Path
from uhcr.plugins import load_plugin

plugin = load_plugin(Path("path/to/my_plugin"), runtime=uhcr.get_runtime())
```

## Plugin Lifecycle

1. **Discovery** — `discover_plugins()` scans directories for `plugin.toml`
2. **Loading** — `load_plugin()` imports the entry point module
3. **Instantiation** — Finds the `Plugin` subclass and creates an instance
4. **Initialization** — Calls `plugin.initialize(runtime)`
5. **Active** — Plugin's registered extensions are available
6. **Shutdown** — Calls `plugin.shutdown()` on unload or runtime exit

## Accessing Registered Extensions

```python
from uhcr.plugins.base import get_registered_kernels, get_registered_passes

# Get all custom kernels
kernels = get_registered_kernels()
relu_fn = kernels["my_fast_relu"]
result = relu_fn([-1.0, 2.0, -3.0, 4.0])

# Get all optimization passes
passes = get_registered_passes()
```

## Example: Complete Plugin

See `plugins/example_plugin/` in the repository for a working example.
