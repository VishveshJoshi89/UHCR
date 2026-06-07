#!/usr/bin/env python3
"""
UHCR Documentation MCP Server

Provides AI agents with structured access to UHCR documentation,
code examples, and API references through the Model Context Protocol.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio
import argparse
import logging

# MCP SDK imports
try:
    from mcp import server, types
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
except ImportError:
    print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Documentation processing imports
import re
import yaml
from datetime import datetime

logger = logging.getLogger(__name__)

class UHCRDocumentationServer:
    """MCP Server for UHCR Documentation Access"""
    
    def __init__(self, docs_path: str = "docs"):
        self.docs_path = Path(docs_path)
        self.app = Server("uhcr-docs")
        self.documentation_cache = {}
        self.api_index = {}
        self.code_examples = {}
        
        # Initialize documentation index
        self._build_documentation_index()
        
    def _build_documentation_index(self):
        """Build searchable index of all documentation"""
        
        if not self.docs_path.exists():
            logger.warning(f"Documentation path {self.docs_path} not found")
            return
            
        for md_file in self.docs_path.glob("**/*.md"):
            if md_file.name.startswith("_"):
                continue
                
            content = self._parse_markdown_file(md_file)
            if content:
                self.documentation_cache[content['slug']] = content
                
        logger.info(f"Indexed {len(self.documentation_cache)} documentation pages")
    
    def _parse_markdown_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse markdown file and extract structured content"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract frontmatter
            frontmatter = {}
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1])
                        content = parts[2].strip()
                    except yaml.YAMLError:
                        pass
            
            # Extract code examples
            code_blocks = re.findall(r'```(\w+)?\n(.*?)```', content, re.DOTALL)
            
            # Extract headings for navigation
            headings = re.findall(r'^#{1,6}\s+(.+)$', content, re.MULTILINE)
            
            # Extract API references
            api_refs = re.findall(r'`([a-zA-Z_][a-zA-Z0-9_.]+\([^)]*\))`', content)
            
            slug = file_path.stem
            
            return {
                'slug': slug,
                'title': frontmatter.get('title', slug.replace('-', ' ').title()),
                'description': frontmatter.get('description', ''),
                'nav_order': frontmatter.get('nav_order', 999),
                'parent': frontmatter.get('parent'),
                'file_path': str(file_path),
                'content': content,
                'headings': headings,
                'code_blocks': code_blocks,
                'api_refs': api_refs,
                'word_count': len(content.split()),
                'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None

# MCP Server Setup
app = UHCRDocumentationServer()

@app.app.list_resources()
async def handle_list_resources() -> List[types.Resource]:
    """List all available documentation resources"""
    
    resources = []
    
    for slug, doc in app.documentation_cache.items():
        resources.append(
            types.Resource(
                uri=f"uhcr://docs/{slug}",
                name=f"UHCR Documentation: {doc['title']}",
                description=doc['description'] or f"Documentation for {doc['title']}",
                mimeType="text/markdown"
            )
        )
    
    return resources

@app.app.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a specific documentation resource"""
    
    if not uri.startswith("uhcr://docs/"):
        raise ValueError(f"Unknown resource URI: {uri}")
    
    slug = uri.replace("uhcr://docs/", "")
    
    if slug not in app.documentation_cache:
        raise ValueError(f"Documentation page '{slug}' not found")
    
    doc = app.documentation_cache[slug]
    
    # Return structured documentation with metadata
    return f"""# {doc['title']}

**File**: {doc['file_path']}  
**Last Modified**: {doc['last_modified']}  
**Word Count**: {doc['word_count']}  
**Navigation Order**: {doc['nav_order']}  
{f"**Parent Section**: {doc['parent']}" if doc['parent'] else ""}

{doc['content']}

---

## Available Code Examples

{chr(10).join([f"**{lang or 'text'}:**{chr(10)}```{lang or 'text'}{chr(10)}{code}{chr(10)}```{chr(10)}" for lang, code in doc['code_blocks'][:3]])}

## API References Found
{', '.join(doc['api_refs'][:10])}
"""

@app.app.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List all available tools for interacting with UHCR documentation"""
    
    return [
        types.Tool(
            name="search_docs",
            description="Search UHCR documentation by keywords, topics, or code examples",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keywords, API names, concepts)"
                    },
                    "category": {
                        "type": "string", 
                        "enum": ["all", "guides", "reference", "api", "examples"],
                        "description": "Limit search to specific category"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_code_examples", 
            description="Get code examples for specific UHCR features or APIs",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic or API to find examples for (e.g., 'jit', 'tensor', 'backend')"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "bash", "dockerfile", "yaml", "toml", "all"],
                        "description": "Programming language filter",
                        "default": "python"
                    }
                },
                "required": ["topic"]
            }
        ),
        types.Tool(
            name="get_api_reference",
            description="Get detailed API reference for UHCR classes and methods", 
            inputSchema={
                "type": "object",
                "properties": {
                    "api_name": {
                        "type": "string",
                        "description": "API name (e.g., 'uhcr.jit', 'Tensor.matmul', 'detect')"
                    }
                },
                "required": ["api_name"]
            }
        ),
        types.Tool(
            name="get_navigation_structure",
            description="Get the complete documentation navigation structure",
            inputSchema={
                "type": "object", 
                "properties": {}
            }
        ),
        types.Tool(
            name="get_quick_reference",
            description="Get a quick reference card for common UHCR operations",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["installation", "jit", "tensors", "backends", "plugins", "deployment"],
                        "description": "Category of quick reference"
                    }
                },
                "required": ["category"]
            }
        )
    ]

@app.app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    """Handle tool calls for documentation interaction"""
    
    if name == "search_docs":
        return await _search_documentation(arguments)
    elif name == "get_code_examples":
        return await _get_code_examples(arguments) 
    elif name == "get_api_reference":
        return await _get_api_reference(arguments)
    elif name == "get_navigation_structure":
        return await _get_navigation_structure(arguments)
    elif name == "get_quick_reference":
        return await _get_quick_reference(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")

async def _search_documentation(args: dict) -> List[types.TextContent]:
    """Search through documentation content"""
    
    query = args["query"].lower()
    category = args.get("category", "all")
    max_results = args.get("max_results", 5)
    
    results = []
    
    for slug, doc in app.documentation_cache.items():
        score = 0
        
        # Category filtering
        if category != "all":
            if category == "guides" and doc.get("parent") != "Guides":
                continue
            elif category == "reference" and doc.get("parent") != "Reference":
                continue
            elif category == "api" and "api" not in slug and "reference" not in slug:
                continue
            elif category == "examples" and not doc["code_blocks"]:
                continue
        
        # Title match (highest priority)
        if query in doc["title"].lower():
            score += 10
            
        # Content match
        if query in doc["content"].lower():
            score += 5
            
        # API reference match
        for api_ref in doc["api_refs"]:
            if query in api_ref.lower():
                score += 8
                
        # Code example match
        for lang, code in doc["code_blocks"]:
            if query in code.lower():
                score += 6
        
        if score > 0:
            results.append((score, doc))
    
    # Sort by relevance and limit results
    results.sort(key=lambda x: x[0], reverse=True)
    results = results[:max_results]
    
    if not results:
        return [types.TextContent(
            type="text",
            text=f"No documentation found for query: '{query}'"
        )]
    
    response = f"# Search Results for '{query}'\n\nFound {len(results)} relevant documentation pages:\n\n"
    
    for score, doc in results:
        response += f"## {doc['title']} (Score: {score})\n"
        response += f"**File**: {doc['slug']}.md\n"
        if doc['parent']:
            response += f"**Section**: {doc['parent']}\n"
        response += f"**Word Count**: {doc['word_count']}\n"
        
        # Add relevant excerpt
        content_lower = doc['content'].lower()
        query_pos = content_lower.find(query)
        if query_pos != -1:
            start = max(0, query_pos - 100)
            end = min(len(doc['content']), query_pos + 200)
            excerpt = doc['content'][start:end].strip()
            response += f"**Excerpt**: ...{excerpt}...\n"
        
        response += f"**Resource URI**: uhcr://docs/{doc['slug']}\n\n"
    
    return [types.TextContent(type="text", text=response)]

async def _get_code_examples(args: dict) -> List[types.TextContent]:
    """Get code examples for a specific topic"""
    
    topic = args["topic"].lower()
    language = args.get("language", "python")
    
    examples = []
    
    for slug, doc in app.documentation_cache.items():
        for lang, code in doc["code_blocks"]:
            # Language filter
            if language != "all" and lang and lang.lower() != language:
                continue
                
            # Topic relevance check
            if (topic in code.lower() or 
                topic in doc["title"].lower() or
                topic in slug.lower()):
                
                examples.append({
                    'source': doc['title'],
                    'language': lang or 'text',
                    'code': code,
                    'context': slug
                })
    
    if not examples:
        return [types.TextContent(
            type="text",
            text=f"No code examples found for topic: '{topic}'"
        )]
    
    response = f"# Code Examples for '{topic}'\n\nFound {len(examples)} relevant examples:\n\n"
    
    for i, example in enumerate(examples[:10], 1):  # Limit to 10 examples
        response += f"## Example {i}: {example['source']}\n"
        response += f"**Language**: {example['language']}\n"
        response += f"**Source**: {example['context']}.md\n\n"
        response += f"```{example['language']}\n{example['code']}\n```\n\n"
    
    return [types.TextContent(type="text", text=response)]

async def _get_api_reference(args: dict) -> List[types.TextContent]:
    """Get API reference for specific UHCR API"""
    
    api_name = args["api_name"]
    
    # Search for API documentation
    api_docs = []
    
    for slug, doc in app.documentation_cache.items():
        if "api" in slug or "reference" in slug:
            # Look for the API in content
            if api_name.lower() in doc["content"].lower():
                api_docs.append(doc)
                continue
                
            # Look in API references
            for api_ref in doc["api_refs"]:
                if api_name.lower() in api_ref.lower():
                    api_docs.append(doc)
                    break
    
    if not api_docs:
        return [types.TextContent(
            type="text", 
            text=f"API reference not found for: '{api_name}'\n\nTry searching the general documentation with the search_docs tool."
        )]
    
    response = f"# API Reference: {api_name}\n\n"
    
    for doc in api_docs[:3]:  # Limit to most relevant docs
        response += f"## From {doc['title']}\n"
        response += f"**Source**: {doc['slug']}.md\n\n"
        
        # Extract relevant sections
        lines = doc["content"].split('\n')
        relevant_lines = []
        
        for i, line in enumerate(lines):
            if api_name.lower() in line.lower():
                # Include context around the match
                start = max(0, i - 3)
                end = min(len(lines), i + 10)
                relevant_lines.extend(lines[start:end])
                relevant_lines.append("---")
        
        if relevant_lines:
            response += '\n'.join(relevant_lines[:50])  # Limit output
            response += "\n\n"
    
    return [types.TextContent(type="text", text=response)]

async def _get_navigation_structure(args: dict) -> List[types.TextContent]:
    """Get the complete documentation navigation structure"""
    
    # Group documents by parent
    structure = {
        "root": [],
        "Guides": [],
        "Reference": []
    }
    
    for slug, doc in app.documentation_cache.items():
        parent = doc.get("parent")
        if parent in structure:
            structure[parent].append(doc)
        else:
            structure["root"].append(doc)
    
    # Sort by nav_order
    for category in structure.values():
        category.sort(key=lambda x: x.get("nav_order", 999))
    
    response = "# UHCR Documentation Navigation\n\n"
    
    # Root level pages
    response += "## Main Pages\n\n"
    for doc in structure["root"]:
        response += f"- **{doc['title']}** (`{doc['slug']}`) - {doc.get('description', 'No description')}\n"
    
    # Guides section
    response += "\n## Guides\n\n"
    for doc in structure["Guides"]:
        response += f"- **{doc['title']}** (`{doc['slug']}`) - {doc.get('description', 'No description')}\n"
    
    # Reference section  
    response += "\n## Reference\n\n"
    for doc in structure["Reference"]:
        response += f"- **{doc['title']}** (`{doc['slug']}`) - {doc.get('description', 'No description')}\n"
    
    response += "\n## Resource Access\n\n"
    response += "To read any page, use the resource URI format: `uhcr://docs/{slug}`\n\n"
    response += "**Example**: `uhcr://docs/jit-guide` to read the JIT Guide documentation.\n"
    
    return [types.TextContent(type="text", text=response)]

async def _get_quick_reference(args: dict) -> List[types.TextContent]:
    """Get quick reference for common UHCR operations"""
    
    category = args["category"]
    
    quick_refs = {
        "installation": """# UHCR Installation Quick Reference

## Basic Installation
```bash
pip install uhcr
```

## Development Installation
```bash
git clone https://github.com/VishveshJoshi89/UHCR.git
cd UHCR
pip install -e .
```

## Verify Installation
```python
import uhcr
print(uhcr.__version__)
profile = uhcr.detect()
print(f"CPU: {profile.cpu.brand}")
```

## System Requirements
- Python 3.10+
- Windows, Linux, or macOS
- Optional: NVIDIA GPU with CUDA for GPU acceleration
""",

        "jit": """# UHCR JIT Compilation Quick Reference

## Basic JIT Decorator
```python
import uhcr

@uhcr.jit
def compute(a, b):
    return a + b * 2

result = compute(10, 5)  # Compiles on 3rd call
```

## Eager Compilation
```python
@uhcr.jit(eager=True)
def fast_compute(x, y):
    return x * y + x

result = fast_compute(7, 6)  # Compiles immediately
```

## Verbose Mode
```python
@uhcr.jit(eager=True, verbose=True)
def debug_compute(a, b):
    return (a + b) * 2

# Shows: [uhcr.jit] Compiled 'debug_compute' for signature...
```

## Check Compilation Status
```python
print(f"Is compiled: {compute.is_compiled}")
print(f"Cache size: {len(compute.compiled_versions)}")
```
""",

        "tensors": """# UHCR Tensor Operations Quick Reference

## Creating Tensors
```python
import uhcr

# From lists
a = uhcr.tensor([[1.0, 2.0], [3.0, 4.0]])

# From numpy (if available)
import numpy as np
b = uhcr.tensor(np.array([1.0, 2.0, 3.0]))
```

## Matrix Operations
```python
# Matrix multiplication
c = a.matmul(b)

# Element-wise operations
d = a + b
e = a * 2.0
```

## Tensor Properties
```python
print(f"Shape: {a.shape}")
print(f"Data type: {a.dtype}")
print(f"Memory address: {hex(a.address)}")

# Convert back to numpy
numpy_array = a.to_numpy()
```
""",

        "backends": """# UHCR Backend Selection Quick Reference

## Hardware Detection
```python
import uhcr

profile = uhcr.detect()
print(f"Optimal backend: {profile.get_optimal_backend()}")
```

## Available Backends
```python
from uhcr.backends import get_available_backends

backends = get_available_backends(profile)
for backend in backends:
    print(f"{backend.name}: priority {backend.priority}")
```

## Force Specific Backend
```python
@uhcr.jit(backend='cuda-ptx')  # Force CUDA
def gpu_compute(data):
    return sum(x * x for x in data)

@uhcr.jit(backend='cpu-avx512')  # Force AVX512
def cpu_compute(data):
    return [x * 2 for x in data]
```

## Backend Capabilities
```python
backend = uhcr.get_backend('cpu-avx2')
print(f"Supports SIMD: {backend.supports_simd()}")
print(f"Vector width: {backend.vector_width}")
```
""",

        "plugins": """# UHCR Plugin System Quick Reference

## List Available Plugins
```python
import uhcr.plugins

# Built-in plugins
builtin = uhcr.plugins.get_builtin()

# All discovered plugins
all_plugins = uhcr.plugins.discover_all()
```

## Activate Plugin
```python
uhcr.plugins.activate('custom-backend')
uhcr.plugins.activate('advanced-optimizer')
```

## Plugin Configuration
```python
uhcr.plugins.configure('custom-backend', {
    'optimization_level': 3,
    'enable_debug': True
})
```

## Create Plugin Manifest (plugin.toml)
```toml
[plugin]
name = "my-custom-plugin"
version = "1.0.0"
category = "backend"

[plugin.entry_points]
backend = "my_plugin.backend:CustomBackend"
```
""",

        "deployment": """# UHCR Deployment Quick Reference

## Docker Container
```dockerfile
FROM python:3.11-slim
RUN pip install uhcr
COPY . /app
WORKDIR /app
CMD ["python", "main.py"]
```

## Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: uhcr-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: uhcr
  template:
    spec:
      containers:
      - name: uhcr
        image: myapp:latest
        resources:
          limits:
            cpu: 4
            memory: 8Gi
```

## Configuration
```python
# Container-optimized config
uhcr.config.set('memory.pool_size', '2GB')
uhcr.config.set('scheduler.threads', 4)
uhcr.config.set('cache.persistent', False)
```
"""
    }
    
    if category not in quick_refs:
        return [types.TextContent(
            type="text",
            text=f"Unknown category: {category}. Available: {', '.join(quick_refs.keys())}"
        )]
    
    return [types.TextContent(type="text", text=quick_refs[category])]

async def main():
    """Main entry point for the MCP server"""
    
    parser = argparse.ArgumentParser(description="UHCR Documentation MCP Server")
    parser.add_argument("--docs-path", default="docs", help="Path to documentation directory")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    
    # Initialize server with documentation path
    global app
    app = UHCRDocumentationServer(args.docs_path)
    
    logger.info(f"Starting UHCR Documentation MCP Server on {args.host}:{args.port}")
    logger.info(f"Documentation path: {args.docs_path}")
    logger.info(f"Indexed {len(app.documentation_cache)} pages")
    
    # Run the MCP server
    async with server.stdio_server() as (read_stream, write_stream):
        await app.app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="uhcr-docs",
                server_version="1.0.0",
                capabilities=app.app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())