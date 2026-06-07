# UHCR Documentation MCP Server

This directory contains the Model Context Protocol (MCP) server that provides AI agents with structured access to UHCR documentation.

## What is MCP?

The Model Context Protocol (MCP) is a standard for connecting AI assistants to external data sources and tools. This MCP server allows any compatible AI agent to:

- 📚 **Search Documentation** - Find relevant UHCR docs by keywords or topics
- 🔍 **Browse API References** - Get detailed API documentation and examples  
- 💻 **Extract Code Examples** - Find working code snippets for specific features
- 🗺️ **Navigate Structure** - Understand the complete documentation hierarchy
- ⚡ **Quick Reference** - Get instant cheat sheets for common operations

## Installation

### 1. Install Dependencies

```bash
cd mcp/
pip install -r requirements.txt
```

### 2. Verify MCP Server

```bash
python server.py --docs-path ../docs
```

### 3. Test with MCP Client

```bash
# Using the MCP CLI tool (if installed)
mcp connect stdio python server.py --docs-path ../docs
```

## Usage Examples

### For AI Agents

AI agents can connect to this MCP server to access UHCR documentation:

```python
# Example: AI agent searching for JIT compilation info
{
  "method": "tools/call",
  "params": {
    "name": "search_docs", 
    "arguments": {
      "query": "jit compilation optimization",
      "category": "guides",
      "max_results": 3
    }
  }
}
```

### Available Tools

The MCP server provides these tools for AI agents:

1. **`search_docs`** - Search all documentation
2. **`get_code_examples`** - Find code examples by topic
3. **`get_api_reference`** - Get API documentation
4. **`get_navigation_structure`** - Get site navigation
5. **`get_quick_reference`** - Get cheat sheets

### Available Resources

Access documentation pages directly:

- `uhcr://docs/jit-guide` - JIT compilation guide
- `uhcr://docs/api-reference` - Complete API reference
- `uhcr://docs/containerization` - Container deployment guide
- `uhcr://docs/plugins` - Plugin development guide

## Configuration

### MCP Server Configuration

Add to your MCP configuration file:

```json
{
  "mcpServers": {
    "uhcr-docs": {
      "command": "python",
      "args": ["path/to/uhcr/mcp/server.py"],
      "env": {
        "UHCR_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Claude Desktop Configuration

For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "uhcr-docs": {
      "command": "python",
      "args": ["/path/to/uhcr/mcp/server.py", "--docs-path", "/path/to/uhcr/docs"],
      "env": {}
    }
  }
}
```

## Server Options

```bash
python server.py --help

options:
  --docs-path DOCS_PATH  Path to documentation directory (default: docs)
  --port PORT           Server port (default: 8000)
  --host HOST           Server host (default: localhost) 
  --log-level LEVEL     Logging level (default: INFO)
```

## Example Interactions

### 1. Search for Installation Instructions

**Query:**
```json
{
  "name": "search_docs",
  "arguments": {
    "query": "installation pip install",
    "max_results": 2
  }
}
```

**Response:** Returns quickstart and installation documentation.

### 2. Get JIT Compilation Examples

**Query:**
```json
{
  "name": "get_code_examples", 
  "arguments": {
    "topic": "jit decorator",
    "language": "python"
  }
}
```

**Response:** Returns Python code examples showing `@uhcr.jit` usage.

### 3. Find API Documentation

**Query:**
```json
{
  "name": "get_api_reference",
  "arguments": {
    "api_name": "uhcr.tensor"
  }
}
```

**Response:** Returns tensor API documentation with methods and examples.

## Development

### Adding New Tools

To add new MCP tools, edit `server.py`:

1. Add tool definition in `handle_list_tools()`
2. Implement tool logic in `handle_call_tool()`
3. Update this documentation

### Testing

```bash
# Test documentation indexing
python -c "from server import UHCRDocumentationServer; s = UHCRDocumentationServer('../docs'); print(f'Indexed {len(s.documentation_cache)} pages')"

# Test specific tool
python server.py --docs-path ../docs
# Then use MCP client to test tools
```

### Debugging

Enable debug logging:

```bash
python server.py --docs-path ../docs --log-level DEBUG
```

## Integration Examples

### With Kiro (AI Assistant)

```javascript
// Add UHCR docs to Kiro configuration
{
  "mcpServers": {
    "uhcr-docs": {
      "command": "uvx",
      "args": ["uhcr-docs-mcp@latest"],
      "autoApprove": ["search_docs", "get_code_examples"]
    }
  }
}
```

### With Custom AI Agent

```python
import asyncio
from mcp import ClientSession

async def query_uhcr_docs():
    async with ClientSession("python", ["mcp/server.py"]) as session:
        # Search for containerization info
        result = await session.call_tool(
            "search_docs",
            {"query": "docker kubernetes", "category": "guides"}
        )
        print(result)

asyncio.run(query_uhcr_docs())
```

## Troubleshooting

### Common Issues

1. **Module not found**: Install MCP dependencies with `pip install -r requirements.txt`
2. **Documentation not indexed**: Check `--docs-path` points to correct directory
3. **No search results**: Verify documentation files are valid Markdown with frontmatter

### Support

- 📖 **Documentation**: https://vishveshjoshi89.github.io/UHCR/
- 🐛 **Issues**: https://github.com/VishveshJoshi89/UHCR/issues
- 💬 **Discussions**: https://github.com/VishveshJoshi89/UHCR/discussions

## License

This MCP server is part of the UHCR project and is licensed under the Apache-2.0 License.