"""UHCR Plugin System — extensible architecture for custom backends, kernels, and passes."""

from uhcr.plugins.base import Plugin, PluginManager, load_plugin, discover_plugins

__all__ = ["Plugin", "PluginManager", "load_plugin", "discover_plugins"]
