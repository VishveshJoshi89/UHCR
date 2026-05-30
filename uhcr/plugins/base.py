"""Plugin base class and lifecycle management for UHCR."""

import importlib
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from uhcr.backends.backend_base import Backend, register_backend


@dataclass
class PluginManifest:
    """Parsed plugin.toml manifest."""
    name: str
    version: str
    author: str = ""
    description: str = ""
    entry_point: str = ""  # e.g., "plugin.main"
    dependencies: List[str] = field(default_factory=list)
    min_uhcr_version: str = "0.1.0"


class Plugin(ABC):
    """Base class for all UHCR plugins.

    Plugins can register backends, kernels, or optimization passes.
    Implement the lifecycle methods to hook into the runtime.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version string."""
        ...

    def initialize(self, runtime: Any) -> None:
        """Called when the plugin is loaded. Use this to register backends, kernels, etc.

        Args:
            runtime: The UHCRRuntime instance.
        """
        pass

    def shutdown(self) -> None:
        """Called when the plugin is unloaded or the runtime shuts down."""
        pass

    def register_backend(self, backend: Backend) -> None:
        """Convenience method to register a backend with the global registry."""
        register_backend(backend)

    def register_kernel(self, name: str, kernel_fn: Callable) -> None:
        """Register a custom kernel function by name.

        Args:
            name: Kernel identifier (e.g., "custom_matmul").
            kernel_fn: The kernel implementation callable.
        """
        _kernel_registry[name] = kernel_fn

    def register_pass(self, name: str, pass_fn: Callable) -> None:
        """Register an IR optimization pass.

        Args:
            name: Pass identifier (e.g., "loop_unroll").
            pass_fn: Function that takes a Function IR and returns optimized Function IR.
        """
        _pass_registry[name] = pass_fn


# Global registries
_kernel_registry: Dict[str, Callable] = {}
_pass_registry: Dict[str, Callable] = {}


def get_registered_kernels() -> Dict[str, Callable]:
    """Returns all registered custom kernels."""
    return dict(_kernel_registry)


def get_registered_passes() -> Dict[str, Callable]:
    """Returns all registered optimization passes."""
    return dict(_pass_registry)


def _parse_toml_simple(path: Path) -> Dict[str, Any]:
    """Minimal TOML parser for plugin.toml files.

    Handles basic key-value pairs and [section] headers.
    For production use, consider tomllib (Python 3.11+) or tomli.
    """
    result: Dict[str, Any] = {}
    current_section: Optional[str] = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Section header
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                if current_section not in result:
                    result[current_section] = {}
                continue
            # Key-value pair
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Strip quotes
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                # Handle arrays
                elif value.startswith("[") and value.endswith("]"):
                    inner = value[1:-1].strip()
                    if inner:
                        value = [v.strip().strip('"').strip("'") for v in inner.split(",")]
                    else:
                        value = []

                if current_section:
                    result[current_section][key] = value
                else:
                    result[key] = value

    return result


def parse_manifest(path: Path) -> PluginManifest:
    """Parse a plugin.toml file into a PluginManifest."""
    data = _parse_toml_simple(path)
    plugin_data = data.get("plugin", {})

    return PluginManifest(
        name=plugin_data.get("name", "unknown"),
        version=plugin_data.get("version", "0.0.0"),
        author=plugin_data.get("author", ""),
        description=plugin_data.get("description", ""),
        entry_point=plugin_data.get("entry_point", ""),
        dependencies=plugin_data.get("dependencies", []),
        min_uhcr_version=plugin_data.get("min_uhcr_version", "0.1.0"),
    )


def load_plugin(plugin_dir: Path, runtime: Any = None) -> Optional[Plugin]:
    """Load a plugin from a directory containing plugin.toml.

    Args:
        plugin_dir: Path to the plugin directory.
        runtime: Optional UHCRRuntime instance to pass to initialize().

    Returns:
        The loaded Plugin instance, or None if loading failed.
    """
    manifest_path = plugin_dir / "plugin.toml"
    if not manifest_path.exists():
        return None

    manifest = parse_manifest(manifest_path)

    if not manifest.entry_point:
        return None

    # Add plugin directory to sys.path temporarily
    plugin_parent = str(plugin_dir.parent)
    if plugin_parent not in sys.path:
        sys.path.insert(0, plugin_parent)

    try:
        module = importlib.import_module(manifest.entry_point)
    except ImportError as e:
        print(f"[UHCR] Failed to import plugin '{manifest.name}': {e}")
        return None

    # Look for a Plugin subclass in the module
    plugin_instance = None
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin):
            plugin_instance = attr()
            break

    if plugin_instance is None:
        # Check for a create_plugin() factory function
        factory = getattr(module, "create_plugin", None)
        if callable(factory):
            plugin_instance = factory()

    if plugin_instance is None:
        print(f"[UHCR] No Plugin subclass found in '{manifest.entry_point}'")
        return None

    # Initialize the plugin
    if runtime is not None:
        plugin_instance.initialize(runtime)

    return plugin_instance


def discover_plugins(search_dirs: Optional[List[Path]] = None) -> List[Path]:
    """Discover plugin directories by looking for plugin.toml files.

    Args:
        search_dirs: Directories to search. Defaults to ./plugins/ and ~/.uhcr/plugins/.

    Returns:
        List of paths to directories containing plugin.toml.
    """
    if search_dirs is None:
        search_dirs = [
            Path.cwd() / "plugins",
            Path.home() / ".uhcr" / "plugins",
        ]

    found = []
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for item in search_dir.iterdir():
            if item.is_dir() and (item / "plugin.toml").exists():
                found.append(item)

    return found


class PluginManager:
    """Manages plugin lifecycle — discovery, loading, and shutdown."""

    def __init__(self, runtime: Any = None):
        self.runtime = runtime
        self._plugins: Dict[str, Plugin] = {}

    @property
    def loaded_plugins(self) -> Dict[str, Plugin]:
        """Returns all currently loaded plugins."""
        return dict(self._plugins)

    def load_all(self, search_dirs: Optional[List[Path]] = None) -> int:
        """Discover and load all plugins from search directories.

        Returns:
            Number of plugins successfully loaded.
        """
        plugin_dirs = discover_plugins(search_dirs)
        count = 0
        for plugin_dir in plugin_dirs:
            plugin = load_plugin(plugin_dir, self.runtime)
            if plugin is not None:
                self._plugins[plugin.name] = plugin
                count += 1
        return count

    def load_single(self, plugin_dir: Path) -> Optional[Plugin]:
        """Load a single plugin from a directory."""
        plugin = load_plugin(plugin_dir, self.runtime)
        if plugin is not None:
            self._plugins[plugin.name] = plugin
        return plugin

    def unload(self, name: str) -> bool:
        """Unload a plugin by name, calling its shutdown() method."""
        plugin = self._plugins.pop(name, None)
        if plugin is not None:
            plugin.shutdown()
            return True
        return False

    def shutdown_all(self) -> None:
        """Shutdown and unload all plugins."""
        for plugin in self._plugins.values():
            plugin.shutdown()
        self._plugins.clear()
