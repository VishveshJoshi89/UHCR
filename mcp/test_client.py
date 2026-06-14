#!/usr/bin/env python3
"""
Test client for UHCR Documentation MCP Server

This script demonstrates how AI agents can interact with the UHCR documentation
through the MCP protocol.
"""

import asyncio
import json
import sys
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
except ImportError:
    print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

class UHCRDocsTester:
    """Test client for UHCR Documentation MCP Server"""
    
    def __init__(self, server_path: str = "server.py"):
        self.server_path = Path(server_path)
        
    async def run_tests(self):
        """Run comprehensive tests of the MCP server"""
        
        print("🚀 Starting UHCR Documentation MCP Server Tests")
        print("=" * 60)
        
        # Start MCP server session
        server_params = StdioServerParameters(
            command="python",
            args=[str(self.server_path), "--docs-path", "../docs"]
        )
        
        async with ClientSession(server_params) as session:
            await self._test_list_resources(session)
            await self._test_search_docs(session)
            await self._test_code_examples(session)
            await self._test_api_reference(session)
            await self._test_navigation(session)
            await self._test_quick_reference(session)
            
        print("\n✅ All tests completed!")
        
    async def _test_list_resources(self, session):
        """Test listing available documentation resources"""
        
        print("\n📚 Testing: List Resources")
        print("-" * 30)
        
        try:
            resources = await session.list_resources()
            
            print(f"Found {len(resources)} documentation resources:")
            
            for resource in resources[:5]:  # Show first 5
                print(f"  • {resource.name}")
                print(f"    URI: {resource.uri}")
                print(f"    Type: {resource.mimeType}")
                
            if len(resources) > 5:
                print(f"  ... and {len(resources) - 5} more")
                
        except Exception as e:
            print(f"❌ Error listing resources: {e}")
            
    async def _test_search_docs(self, session):
        """Test documentation search functionality"""
        
        print("\n🔍 Testing: Search Documentation")
        print("-" * 30)
        
        test_queries = [
            {"query": "jit compilation", "category": "guides"},
            {"query": "tensor operations", "category": "api"},
            {"query": "docker deployment", "max_results": 3}
        ]
        
        for query_args in test_queries:
            try:
                print(f"\nQuery: {json.dumps(query_args, indent=2)}")
                
                result = await session.call_tool("search_docs", query_args)
                
                if result and len(result) > 0:
                    content = result[0].text[:300]  # First 300 chars
                    print(f"✅ Result preview: {content}...")
                else:
                    print("❌ No results returned")
                    
            except Exception as e:
                print(f"❌ Search error: {e}")
                
    async def _test_code_examples(self, session):
        """Test code example retrieval"""
        
        print("\n💻 Testing: Code Examples")
        print("-" * 30)
        
        test_topics = ["jit", "tensor", "backend"]
        
        for topic in test_topics:
            try:
                print(f"\nSearching examples for: {topic}")
                
                result = await session.call_tool("get_code_examples", {
                    "topic": topic,
                    "language": "python"
                })
                
                if result and len(result) > 0:
                    # Count code blocks in response
                    code_blocks = result[0].text.count("```")
                    print(f"✅ Found {code_blocks // 2} code examples")
                else:
                    print("❌ No code examples found")
                    
            except Exception as e:
                print(f"❌ Code example error: {e}")
                
    async def _test_api_reference(self, session):
        """Test API reference lookup"""
        
        print("\n📖 Testing: API Reference")
        print("-" * 30)
        
        test_apis = ["uhcr.jit", "Tensor.matmul", "detect"]
        
        for api_name in test_apis:
            try:
                print(f"\nLooking up API: {api_name}")
                
                result = await session.call_tool("get_api_reference", {
                    "api_name": api_name
                })
                
                if result and len(result) > 0:
                    if "not found" in result[0].text.lower():
                        print("⚠️ API documentation not found")
                    else:
                        print("✅ API documentation retrieved")
                else:
                    print("❌ No API reference returned")
                    
            except Exception as e:
                print(f"❌ API reference error: {e}")
                
    async def _test_navigation(self, session):
        """Test navigation structure retrieval"""
        
        print("\n🗺️ Testing: Navigation Structure")
        print("-" * 30)
        
        try:
            result = await session.call_tool("get_navigation_structure", {})
            
            if result and len(result) > 0:
                nav_content = result[0].text
                
                # Count sections
                main_pages = nav_content.count("## Main Pages")
                guides_section = nav_content.count("## Guides")
                reference_section = nav_content.count("## Reference")
                
                print(f"✅ Navigation structure retrieved:")
                print(f"  • Has main pages section: {main_pages > 0}")
                print(f"  • Has guides section: {guides_section > 0}")
                print(f"  • Has reference section: {reference_section > 0}")
            else:
                print("❌ No navigation structure returned")
                
        except Exception as e:
            print(f"❌ Navigation error: {e}")
            
    async def _test_quick_reference(self, session):
        """Test quick reference retrieval"""
        
        print("\n⚡ Testing: Quick Reference")
        print("-" * 30)
        
        categories = ["installation", "jit", "tensors", "deployment"]
        
        for category in categories:
            try:
                print(f"\nGetting quick reference for: {category}")
                
                result = await session.call_tool("get_quick_reference", {
                    "category": category
                })
                
                if result and len(result) > 0:
                    ref_content = result[0].text
                    code_blocks = ref_content.count("```")
                    print(f"✅ Quick reference retrieved ({code_blocks // 2} examples)")
                else:
                    print("❌ No quick reference returned")
                    
            except Exception as e:
                print(f"❌ Quick reference error: {e}")

async def main():
    """Main test runner"""
    
    print("UHCR Documentation MCP Server Test Suite")
    print("=========================================")
    
    tester = UHCRDocsTester()
    await tester.run_tests()

if __name__ == "__main__":
    asyncio.run(main())