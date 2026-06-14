"""UHCR Plugin System — extensible architecture for custom backends, kernels, and passes.

Two plugin locations are supported:

  uhcr/plugins/          — Core / contributor plugins (this package).
                           Importable as  uhcr.plugins.<name>
                           Maintained by UHCR core team.

  <project_root>/plugins/ — 3rd-party / quick-drop plugins.
                            Loaded by PluginManager via plugin.toml discovery.
                            No package install needed; just drop a folder with
                            plugin.toml and main.py.

Built-in core plugins
---------------------
  avx2_optimizer  — CPU AVX2 SIMD-optimised kernels
  gpu_nvidia      — NVIDIA CUDA / PTX kernels
  gpu_amd         — AMD ROCm / HIP kernels
  gpu_intel       — Intel OpenCL (Arc, Iris Xe, HD Graphics) kernels
"""

from uhcr.plugins.base import Plugin, PluginManager, load_plugin, discover_plugins

__all__ = [
    "Plugin",
    "PluginManager",
    "load_plugin",
    "discover_plugins",
]
