"""UHCR Model Context Protocol (MCP) module.

Exposes UHCR capabilities as MCP tools so AI agents (Claude, GPT-4, Copilot,
etc.) can interact with the runtime without reading source code.

Quick-start
-----------
Start the MCP server from CLI::

    uhcr mcp_start                         # stdio transport (default)
    uhcr mcp_start --transport http --port 3000

Or embed in Python::

    from uhcr.mcp import start_server
    start_server(transport="stdio")

Available MCP tools
-------------------
+-------------------------+--------------------------------------------+
| Tool name               | What it does                               |
+=========================+============================================+
| detect_hardware         | Return full hardware profile (CPU/GPU)     |
| list_backends           | List registered execution backends        |
| list_plugins            | List loaded plugins and their kernels      |
| compile_ir              | Compile an IR snippet, return timing       |
| run_benchmark           | Run a named benchmark, return results      |
| tensor_add              | Add two in-memory tensors                  |
| tensor_matmul           | Multiply two matrices                      |
| get_performance_tips    | AI-friendly performance advice for hw      |
| load_plugin             | Dynamically load a plugin by path          |
+-------------------------+--------------------------------------------+
"""

from uhcr.mcp.server import start_server, MCPServer
from uhcr.mcp.tools  import TOOL_REGISTRY

__all__ = ["start_server", "MCPServer", "TOOL_REGISTRY"]
