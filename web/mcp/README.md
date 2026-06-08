# UHCR MCP Server

Model Context Protocol (MCP) server for UHCR runtime operations.

## Features

### Tools

- **detect_hardware**: Detect hardware capabilities (CPU, GPU, memory)
- **compile_function**: JIT compile Python functions
- **benchmark**: Run performance benchmarks
- **list_backends**: List available execution backends
- **optimize_ir**: Optimize IR with specified passes

### Resources

- **hardware://profile**: Current hardware profile
- **backends://available**: Available execution backends
- **cache://stats**: Compilation cache statistics

## Installation

```bash
# Install UHCR
pip install uhcr

# No additional dependencies needed for MCP server
```

## Usage

### Standalone

```bash
python web/mcp/server.py
```

### With MCP Client

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "uhcr": {
      "command": "python",
      "args": ["web/mcp/server.py"],
      "env": {}
    }
  }
}
```

## Example Tool Calls

### Detect Hardware

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "detect_hardware",
    "arguments": {
      "format": "table"
    }
  }
}
```

### Compile Function

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "compile_function",
    "arguments": {
      "code": "@uhcr.jit\ndef add(a, b):\n    return a + b",
      "eager": true
    }
  }
}
```

### Benchmark

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "benchmark",
    "arguments": {
      "code": "def test():\n    return sum(range(1000))",
      "iterations": 10000
    }
  }
}
```

## Protocol

Implements MCP protocol version 2024-11-05 with:
- JSON-RPC 2.0 over stdio
- Tools capability
- Resources capability

## License

Apache-2.0
