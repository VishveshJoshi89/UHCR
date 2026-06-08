#!/usr/bin/env python3
"""UHCR MCP Server - Model Context Protocol server for UHCR operations."""

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

# MCP Protocol implementation
class MCPServer:
    """MCP Server for UHCR runtime operations."""
    
    def __init__(self):
        self.tools = self._register_tools()
        self.resources = self._register_resources()
        
    def _register_tools(self) -> Dict[str, Dict[str, Any]]:
        """Register available MCP tools."""
        return {
            "detect_hardware": {
                "description": "Detect hardware capabilities of the system",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["json", "table"],
                            "description": "Output format",
                            "default": "json"
                        }
                    }
                }
            },
            "compile_function": {
                "description": "JIT compile a Python function using UHCR",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python function code to compile"
                        },
                        "eager": {
                            "type": "boolean",
                            "description": "Compile eagerly on first call",
                            "default": True
                        }
                    },
                    "required": ["code"]
                }
            },
            "benchmark": {
                "description": "Run performance benchmarks",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Code to benchmark"
                        },
                        "iterations": {
                            "type": "integer",
                            "description": "Number of iterations",
                            "default": 1000
                        }
                    },
                    "required": ["code"]
                }
            },
            "list_backends": {
                "description": "List available execution backends",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "optimize_ir": {
                "description": "Optimize IR with specified passes",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ir_code": {
                            "type": "string",
                            "description": "IR code to optimize"
                        },
                        "passes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optimization passes to run",
                            "default": ["constant-folding", "dce", "cse"]
                        }
                    },
                    "required": ["ir_code"]
                }
            }
        }
    
    def _register_resources(self) -> Dict[str, Dict[str, Any]]:
        """Register available MCP resources."""
        return {
            "hardware://profile": {
                "description": "Current hardware profile",
                "mimeType": "application/json"
            },
            "backends://available": {
                "description": "Available execution backends",
                "mimeType": "application/json"
            },
            "cache://stats": {
                "description": "Compilation cache statistics",
                "mimeType": "application/json"
            }
        }
    
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": False
                },
                "resources": {
                    "subscribe": False,
                    "listChanged": False
                }
            },
            "serverInfo": {
                "name": "uhcr-mcp-server",
                "version": "1.0.0"
            }
        }
    
    async def handle_tools_list(self) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools_list = []
        for name, spec in self.tools.items():
            tools_list.append({
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"]
            })
        return {"tools": tools_list}
    
    async def handle_tools_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        if name == "detect_hardware":
            return await self._tool_detect_hardware(arguments)
        elif name == "compile_function":
            return await self._tool_compile_function(arguments)
        elif name == "benchmark":
            return await self._tool_benchmark(arguments)
        elif name == "list_backends":
            return await self._tool_list_backends(arguments)
        elif name == "optimize_ir":
            return await self._tool_optimize_ir(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    async def handle_resources_list(self) -> Dict[str, Any]:
        """Handle resources/list request."""
        resources_list = []
        for uri, spec in self.resources.items():
            resources_list.append({
                "uri": uri,
                "name": uri.split("://")[1],
                "description": spec["description"],
                "mimeType": spec["mimeType"]
            })
        return {"resources": resources_list}
    
    async def handle_resources_read(self, uri: str) -> Dict[str, Any]:
        """Handle resources/read request."""
        if uri == "hardware://profile":
            return await self._resource_hardware_profile()
        elif uri == "backends://available":
            return await self._resource_backends()
        elif uri == "cache://stats":
            return await self._resource_cache_stats()
        else:
            raise ValueError(f"Unknown resource: {uri}")
    
    # Tool implementations
    async def _tool_detect_hardware(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Detect hardware capabilities."""
        try:
            import uhcr
            profile = uhcr.detect()
            
            output_format = args.get("format", "json")
            if output_format == "table":
                content = profile.format_table()
            else:
                content = profile.to_json()
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": content
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error detecting hardware: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _tool_compile_function(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Compile a Python function."""
        try:
            import uhcr
            code = args["code"]
            eager = args.get("eager", True)
            
            # Create namespace and execute
            namespace = {"uhcr": uhcr}
            exec(code, namespace)
            
            # Find the decorated function
            func_name = None
            for name, obj in namespace.items():
                if callable(obj) and hasattr(obj, "_python_fn"):
                    func_name = name
                    break
            
            if func_name:
                result = f"Successfully compiled function: {func_name}\n"
                result += f"Eager mode: {eager}\n"
                result += f"Function ready for execution"
            else:
                result = "No @uhcr.jit decorated function found in code"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": result
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error compiling function: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _tool_benchmark(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run performance benchmark."""
        try:
            import time
            code = args["code"]
            iterations = args.get("iterations", 1000)
            
            # Execute code and benchmark
            namespace = {}
            exec(code, namespace)
            
            # Find function to benchmark
            func = None
            for obj in namespace.values():
                if callable(obj) and not obj.__name__.startswith("_"):
                    func = obj
                    break
            
            if not func:
                raise ValueError("No function found to benchmark")
            
            # Warmup
            for _ in range(10):
                func()
            
            # Benchmark
            start = time.perf_counter()
            for _ in range(iterations):
                func()
            elapsed = time.perf_counter() - start
            
            result = f"Benchmark Results:\n"
            result += f"Function: {func.__name__}\n"
            result += f"Iterations: {iterations}\n"
            result += f"Total time: {elapsed:.6f}s\n"
            result += f"Average time: {elapsed/iterations*1e6:.3f}µs\n"
            result += f"Throughput: {iterations/elapsed:.2f} ops/sec"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": result
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error running benchmark: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _tool_list_backends(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List available backends."""
        try:
            from uhcr.backends.backend_base import get_registered_backends
            import uhcr
            
            backends = get_registered_backends()
            profile = uhcr.detect()
            
            result = "Available Backends:\n\n"
            for backend in backends:
                supported = backend.supports(profile)
                status = "✓" if supported else "✗"
                result += f"{status} {backend.name} (priority: {backend.priority})\n"
                result += f"   Supported: {supported}\n\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": result
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error listing backends: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _tool_optimize_ir(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize IR code."""
        try:
            result = "IR optimization not yet implemented in MCP server"
            return {
                "content": [
                    {
                        "type": "text",
                        "text": result
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error optimizing IR: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    # Resource implementations
    async def _resource_hardware_profile(self) -> Dict[str, Any]:
        """Get hardware profile resource."""
        try:
            import uhcr
            profile = uhcr.detect()
            return {
                "contents": [
                    {
                        "uri": "hardware://profile",
                        "mimeType": "application/json",
                        "text": profile.to_json()
                    }
                ]
            }
        except Exception as e:
            raise ValueError(f"Error reading hardware profile: {str(e)}")
    
    async def _resource_backends(self) -> Dict[str, Any]:
        """Get available backends resource."""
        try:
            from uhcr.backends.backend_base import get_registered_backends
            backends = get_registered_backends()
            
            backend_list = [
                {
                    "name": b.name,
                    "priority": b.priority
                }
                for b in backends
            ]
            
            return {
                "contents": [
                    {
                        "uri": "backends://available",
                        "mimeType": "application/json",
                        "text": json.dumps(backend_list, indent=2)
                    }
                ]
            }
        except Exception as e:
            raise ValueError(f"Error reading backends: {str(e)}")
    
    async def _resource_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics resource."""
        try:
            import uhcr
            runtime = uhcr.get_runtime()
            
            stats = {
                "cache_size": len(runtime._cache),
                "optimize_enabled": runtime.optimize
            }
            
            return {
                "contents": [
                    {
                        "uri": "cache://stats",
                        "mimeType": "application/json",
                        "text": json.dumps(stats, indent=2)
                    }
                ]
            }
        except Exception as e:
            raise ValueError(f"Error reading cache stats: {str(e)}")
    
    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle incoming MCP message."""
        method = message.get("method")
        params = message.get("params", {})
        
        try:
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "tools/list":
                result = await self.handle_tools_list()
            elif method == "tools/call":
                result = await self.handle_tools_call(
                    params.get("name"),
                    params.get("arguments", {})
                )
            elif method == "resources/list":
                result = await self.handle_resources_list()
            elif method == "resources/read":
                result = await self.handle_resources_read(params.get("uri"))
            else:
                raise ValueError(f"Unknown method: {method}")
            
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": result
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
    
    async def run(self):
        """Run the MCP server on stdio."""
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                if not line:
                    break
                
                message = json.loads(line.strip())
                response = await self.handle_message(message)
                
                if response:
                    print(json.dumps(response), flush=True)
            except json.JSONDecodeError:
                continue
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                print(json.dumps(error_response), flush=True)


async def main():
    """Main entry point."""
    server = MCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
