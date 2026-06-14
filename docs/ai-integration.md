---
layout: default
title: AI Agent Integration
nav_order: 17
---

# AI Agent Integration
{: .no_toc }

Enable AI agents to understand and interact with UHCR through the Model Context Protocol (MCP) integration.
{: .fs-6 .fw-300 }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Overview

UHCR provides a **Model Context Protocol (MCP) server** that allows AI agents to:

- 📚 **Search Documentation** - Find relevant information by keywords
- 🔍 **Browse API References** - Get detailed API docs and examples
- 💻 **Extract Code Examples** - Find working code snippets
- 🗺️ **Navigate Structure** - Understand documentation hierarchy  
- ⚡ **Quick Reference** - Get instant cheat sheets

This enables AI assistants to quickly understand UHCR capabilities and help users with implementation.

---

## MCP Server Setup

### Installation

```bash
# Navigate to UHCR directory
cd /path/to/UHCR

# Install MCP dependencies
pip install -r mcp/requirements.txt
```

### Verify Installation

```bash
# Test the MCP server
python mcp/server.py --docs-path docs

# Should output: "Starting UHCR Documentation MCP Server..."
```

---

## AI Agent Configuration

### Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "uhcr-docs": {
      "command": "python",
      "args": ["/path/to/UHCR/mcp/server.py", "--docs-path", "/path/to/UHCR/docs"],
      "env": {},
      "description": "UHCR Documentation and API Reference"
    }
  }
}
```

### Kiro AI Assistant

Add to your Kiro configuration:

```json
{
  "mcpServers": {
    "uhcr-docs": {
      "command": "python", 
      "args": ["mcp/server.py"],
      "autoApprove": ["search_docs", "get_code_examples", "get_quick_reference"],
      "disabled": false
    }
  }
}
```

### Generic MCP Client

```python
import asyncio
from mcp import ClientSession, StdioServerParameters

async def query_uhcr():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp/server.py", "--docs-path", "docs"]
    )
    
    async with ClientSession(server_params) as session:
        # Search for JIT compilation info
        result = await session.call_tool("search_docs", {
            "query": "jit compilation optimization",
            "max_results": 3
        })
        
        print(result[0].text)

asyncio.run(query_uhcr())
```

---

## Available MCP Tools

### 1. Search Documentation

Find relevant documentation by keywords:

```json
{
  "name": "search_docs",
  "arguments": {
    "query": "tensor operations matmul",
    "category": "api",
    "max_results": 5
  }
}
```

**Categories:**
- `all` - Search everything (default)
- `guides` - Tutorial and how-to content
- `reference` - Technical reference docs
- `api` - API documentation
- `examples` - Code example focused

### 2. Get Code Examples

Extract working code examples:

```json
{
  "name": "get_code_examples",
  "arguments": {
    "topic": "jit decorator",
    "language": "python"
  }
}
```

**Languages:**
- `python` - Python code examples
- `bash` - Shell commands
- `dockerfile` - Docker configurations
- `yaml` - YAML configurations
- `all` - All languages

### 3. API Reference Lookup

Get detailed API documentation:

```json
{
  "name": "get_api_reference", 
  "arguments": {
    "api_name": "uhcr.tensor"
  }
}
```

**Common APIs:**
- `uhcr.jit` - JIT compilation decorator
- `uhcr.tensor` - Tensor operations
- `uhcr.detect` - Hardware detection
- `Tensor.matmul` - Matrix multiplication
- `Backend.compile` - Code compilation

### 4. Navigation Structure

Get complete documentation hierarchy:

```json
{
  "name": "get_navigation_structure",
  "arguments": {}
}
```

### 5. Quick Reference

Get instant cheat sheets:

```json
{
  "name": "get_quick_reference",
  "arguments": {
    "category": "jit"
  }
}
```

**Categories:**
- `installation` - Setup and installation
- `jit` - JIT compilation basics
- `tensors` - Tensor operations
- `backends` - Backend selection
- `plugins` - Plugin development
- `deployment` - Container deployment

---

## Documentation Resources

Access specific documentation pages directly:

### Resource URIs

- `uhcr://docs/quickstart` - Getting started guide
- `uhcr://docs/jit-guide` - JIT compilation guide  
- `uhcr://docs/api-reference` - Complete API reference
- `uhcr://docs/containerization` - Container deployment
- `uhcr://docs/plugins` - Plugin development
- `uhcr://docs/architecture` - System architecture

### Reading Resources

```python
# Example: Read JIT guide
async with ClientSession(server_params) as session:
    content = await session.read_resource("uhcr://docs/jit-guide")
    print(content)
```

---

## Example AI Agent Interactions

### Scenario 1: Getting Started with UHCR

**AI Agent Query:**
```json
{
  "name": "get_quick_reference",
  "arguments": {"category": "installation"}
}
```

**Response:** Complete installation instructions with verification steps.

### Scenario 2: Understanding JIT Compilation

**AI Agent Query:**
```json
{
  "name": "search_docs",
  "arguments": {
    "query": "jit decorator eager compilation",
    "category": "guides"
  }
}
```

**Response:** JIT guide excerpts with examples and explanations.

### Scenario 3: Finding Tensor Examples

**AI Agent Query:**
```json
{
  "name": "get_code_examples",
  "arguments": {
    "topic": "tensor matmul",
    "language": "python"
  }
}
```

**Response:** Working Python code for tensor operations.

### Scenario 4: API Documentation Lookup

**AI Agent Query:**
```json
{
  "name": "get_api_reference",
  "arguments": {"api_name": "Backend.compile"}
}
```

**Response:** Backend compilation API with parameters and examples.

---

## Advanced Usage

### Custom Tool Development

Extend the MCP server with custom tools:

```python
# Add to server.py
@app.app.call_tool()
async def handle_custom_tool(name: str, arguments: dict):
    if name == "get_performance_tips":
        return await _get_performance_tips(arguments)
    
async def _get_performance_tips(args: dict) -> List[types.TextContent]:
    category = args.get("category", "general")
    
    tips = {
        "jit": [
            "Use eager=True for hot paths",
            "Profile compilation overhead", 
            "Cache compiled functions"
        ],
        "memory": [
            "Use memory pools for allocation",
            "Enable garbage collection tuning",
            "Monitor memory usage"
        ]
    }
    
    return [types.TextContent(
        type="text",
        text=f"Performance Tips for {category}:\n" + 
             "\n".join(f"• {tip}" for tip in tips.get(category, []))
    )]
```

### Monitoring and Analytics

Track AI agent usage:

```python
class UsageTracker:
    def __init__(self):
        self.tool_calls = {}
        self.popular_queries = []
    
    def track_tool_call(self, tool_name: str, args: dict):
        if tool_name not in self.tool_calls:
            self.tool_calls[tool_name] = 0
        self.tool_calls[tool_name] += 1
        
        if tool_name == "search_docs":
            self.popular_queries.append(args.get("query", ""))
    
    def get_stats(self):
        return {
            "total_calls": sum(self.tool_calls.values()),
            "popular_tools": sorted(self.tool_calls.items(), 
                                  key=lambda x: x[1], reverse=True),
            "top_queries": self._get_top_queries()
        }
```

### Integration Testing

Automated testing of MCP server:

```bash
# Run MCP server tests
python mcp/test_client.py

# Test specific functionality
python -c "
import asyncio
from mcp.test_client import UHCRDocsTester

async def test_search():
    tester = UHCRDocsTester()
    await tester._test_search_docs(session)

asyncio.run(test_search())
"
```

---

## Troubleshooting

### Common Issues

**1. MCP Server Won't Start**
```bash
# Check dependencies
pip list | grep mcp

# Verify documentation path
ls -la docs/*.md

# Check server logs
python mcp/server.py --log-level DEBUG
```

**2. No Search Results**
```bash
# Verify documentation indexing
python -c "
from mcp.server import UHCRDocumentationServer
server = UHCRDocumentationServer('docs')
print(f'Indexed {len(server.documentation_cache)} pages')
"
```

**3. AI Agent Connection Issues**
```json
// Check MCP configuration syntax
{
  "mcpServers": {
    "uhcr-docs": {
      "command": "python",
      "args": ["full/path/to/mcp/server.py"]
    }
  }
}
```

### Performance Optimization

**Caching Documentation Index:**
```python
# Enable persistent caching
server = UHCRDocumentationServer(
    docs_path="docs",
    cache_file=".uhcr_mcp_cache.json"
)
```

**Limiting Response Size:**
```python
# Configure response limits
MAX_RESPONSE_LENGTH = 5000
MAX_CODE_EXAMPLES = 10
MAX_SEARCH_RESULTS = 5
```

---

## Security Considerations

### Access Control

```python
# Implement access control for sensitive operations
ALLOWED_OPERATIONS = {
    "search_docs": True,
    "get_code_examples": True, 
    "get_api_reference": True,
    "admin_operations": False  # Restrict admin tools
}

@app.app.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if not ALLOWED_OPERATIONS.get(name, False):
        raise PermissionError(f"Tool {name} not allowed")
```

### Rate Limiting

```python
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_requests=100, window=60):
        self.max_requests = max_requests
        self.window = window
        self.requests = defaultdict(list)
    
    def allow_request(self, client_id: str) -> bool:
        now = time.time()
        
        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < self.window
        ]
        
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        self.requests[client_id].append(now)
        return True
```

---

## Best Practices

### For AI Agent Developers

1. **Start with Navigation** - Use `get_navigation_structure` to understand the docs
2. **Use Specific Searches** - Include category filters for better results
3. **Cache Responses** - Store frequently accessed content locally
4. **Handle Errors Gracefully** - Implement fallbacks for failed queries
5. **Batch Related Queries** - Minimize MCP server calls

### For UHCR Users

1. **Keep Docs Updated** - Ensure MCP server reflects latest documentation
2. **Monitor Usage** - Track which content AI agents access most
3. **Provide Feedback** - Report issues with AI agent interactions
4. **Test Integration** - Regularly verify MCP server functionality

The MCP integration makes UHCR documentation instantly accessible to AI agents, enabling better user support and more efficient development workflows.

[Next: Quick Reference →](quick-reference){: .btn .btn-primary }
[Previous: Network Subsystem ←](network){: .btn }