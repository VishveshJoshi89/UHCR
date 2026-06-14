"""MCP server — exposes UHCR tools over stdio or HTTP.

The server implements the Model Context Protocol (MCP) JSON-RPC 2.0 wire
format so any MCP-compatible AI agent can call UHCR tools directly.

Transport options
-----------------
stdio  (default)
    Reads newline-delimited JSON from stdin, writes responses to stdout.
    Works with Claude Desktop, Cursor, VS Code Copilot, etc.

http
    Starts a minimal HTTP server (no external dependencies).
    POST /mcp  — single JSON-RPC 2.0 call
    GET  /     — server info + tool list

Usage
-----
From CLI (added by uhcr mcp_start)::

    uhcr mcp_start                         # stdio
    uhcr mcp_start --transport http --port 3000

From Python::

    from uhcr.mcp import start_server
    start_server(transport="stdio")
    start_server(transport="http", port=3000)
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict, Optional

from uhcr.mcp.tools  import TOOL_REGISTRY
from uhcr.mcp.schema import TOOL_SCHEMAS


# ── JSON-RPC 2.0 helpers ──────────────────────────────────────────────────────

def _ok(req_id: Any, result: Any) -> Dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str, data: Any = None) -> Dict:
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


# ── MCP method dispatch ───────────────────────────────────────────────────────

def _handle_request(body: Dict) -> Dict:
    """Dispatch a single JSON-RPC 2.0 request and return the response dict."""
    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    # ── MCP protocol methods ─────────────────────────────────────────────────

    if method == "initialize":
        return _ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name":    "uhcr-mcp-server",
                "version": "1.0.0",
            },
        })

    if method == "tools/list":
        tools = []
        for name, schema in TOOL_SCHEMAS.items():
            tools.append({
                "name":        name,
                "description": schema["description"],
                "inputSchema": schema["inputSchema"],
            })
        return _ok(req_id, {"tools": tools})

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        handler = TOOL_REGISTRY.get(tool_name)
        if handler is None:
            return _err(req_id, -32601,
                        f"Tool not found: '{tool_name}'",
                        {"available": list(TOOL_REGISTRY.keys())})
        try:
            result = handler(arguments)
            return _ok(req_id, {
                "content": [{"type": "text",
                             "text": json.dumps(result, indent=2)}],
                "isError": False,
            })
        except Exception as exc:
            tb = traceback.format_exc()
            return _ok(req_id, {
                "content": [{"type": "text",
                             "text": f"Error: {exc}\n\n{tb}"}],
                "isError": True,
            })

    if method == "notifications/initialized":
        # Fire-and-forget notification — no response needed
        return None   # type: ignore

    # Unknown method
    return _err(req_id, -32601, f"Method not found: '{method}'")


# ── MCPServer class ───────────────────────────────────────────────────────────

class MCPServer:
    """Minimal MCP server supporting stdio and HTTP transports."""

    def __init__(self, transport: str = "stdio", port: int = 3000,
                 host: str = "127.0.0.1"):
        self.transport = transport
        self.port = port
        self.host = host

    # ── stdio ─────────────────────────────────────────────────────────────────

    def run_stdio(self):
        """Read JSON-RPC lines from stdin, write responses to stdout."""
        print(
            json.dumps({"jsonrpc": "2.0", "method": "uhcr/ready",
                        "params": {"transport": "stdio"}}),
            file=sys.stderr, flush=True
        )
        for raw_line in sys.stdin:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                body = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                response = _err(None, -32700, f"Parse error: {exc}")
                print(json.dumps(response), flush=True)
                continue

            response = _handle_request(body)
            if response is not None:
                print(json.dumps(response), flush=True)

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def run_http(self):
        """Start a simple HTTP server on self.host:self.port."""
        import http.server

        server = self  # capture for closure

        class _Handler(http.server.BaseHTTPRequestHandler):

            def log_message(self, fmt, *args):
                pass   # silence default access log

            def do_GET(self):
                if self.path == "/":
                    info = {
                        "server":    "uhcr-mcp-server",
                        "version":   "1.0.0",
                        "transport": "http",
                        "tools":     list(TOOL_REGISTRY.keys()),
                        "usage":     "POST /mcp  body: JSON-RPC 2.0",
                    }
                    self._send(200, json.dumps(info, indent=2))
                else:
                    self._send(404, json.dumps({"error": "not found"}))

            def do_POST(self):
                if self.path != "/mcp":
                    self._send(404, json.dumps({"error": "use POST /mcp"}))
                    return
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError as exc:
                    self._send(400,
                               json.dumps(_err(None, -32700, str(exc))))
                    return
                response = _handle_request(body)
                self._send(200, json.dumps(response))

            def _send(self, status: int, body: str):
                enc = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(enc)))
                self.end_headers()
                self.wfile.write(enc)

        addr = (server.host, server.port)
        httpd = http.server.HTTPServer(addr, _Handler)
        print(f"[UHCR MCP] HTTP server listening on "
              f"http://{server.host}:{server.port}/mcp",
              file=sys.stderr, flush=True)
        print(f"[UHCR MCP] Tools: {list(TOOL_REGISTRY.keys())}",
              file=sys.stderr, flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[UHCR MCP] Shutting down.", file=sys.stderr)
            httpd.server_close()

    # ── entry point ───────────────────────────────────────────────────────────

    def run(self):
        if self.transport == "http":
            self.run_http()
        else:
            self.run_stdio()


# ── module-level helper ───────────────────────────────────────────────────────

def start_server(transport: str = "stdio",
                 port: int = 3000,
                 host: str = "127.0.0.1") -> None:
    """Start the UHCR MCP server.

    Args:
        transport: "stdio" or "http".
        port:      HTTP port (ignored for stdio).
        host:      HTTP bind address (ignored for stdio).
    """
    MCPServer(transport=transport, port=port, host=host).run()
