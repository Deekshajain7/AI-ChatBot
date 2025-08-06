#!/usr/bin/env python3
"""
Test script for MCP News Server
"""

import requests
import os
import sys
import subprocess
import json
from datetime import datetime, timedelta

# Test the basic API first
def test_news_api():
    """Test the NewsAPI directly"""
    print("Testing NewsAPI directly...")
    
    NEWS_API_KEY = "9830fcd69f284b8e8c0a093da8d165f8"
    NEWS_API_BASE_URL = "https://newsapi.org/v2/everything"
    
    # Calculate date range
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    params = {
        "q": "technology",
        "from": from_date,
        "sortBy": "publishedAt",
        "apiKey": NEWS_API_KEY,
        "language": "en",
        "pageSize": 3
    }
    
    try:
        response = requests.get(NEWS_API_BASE_URL, params=params, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"API Status: {data.get('status')}")
            print(f"Total Results: {data.get('totalResults')}")
            print(f"Articles Found: {len(data.get('articles', []))}")
            
            if data.get('articles'):
                print(f"First article title: {data['articles'][0].get('title', 'No title')}")
                return True
            else:
                print("No articles found")
                return False
        else:
            print(f"API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_mcp_server_syntax():
    """Test if the MCP server script has syntax errors"""
    print("\nTesting MCP server syntax...")
    
    script_path = "C:/NewsAPI/mcp_news_server.py"
    
    try:
        # Try to compile the script
        with open(script_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        compile(code, script_path, 'exec')
        print("✓ MCP server syntax is valid")
        return True
    
    except SyntaxError as e:
        print(f"✗ Syntax error in MCP server: {e}")
        return False
    except FileNotFoundError:
        print(f"✗ MCP server file not found: {script_path}")
        return False
    except Exception as e:
        print(f"✗ Error checking MCP server: {e}")
        return False

def test_mcp_dependencies():
    """Test if MCP dependencies are installed"""
    print("\nTesting MCP dependencies...")
    
    try:
        import mcp
        print("✓ mcp package is installed")
        
        from mcp.server import NotificationOptions, Server # type: ignore
        from mcp.server.models import InitializationOptions # type: ignore
        from mcp.server.stdio import stdio_server # type: ignore
        from mcp.types import Tool, TextContent # type: ignore
        print("✓ All MCP imports are working")
        
        return True
    
    except ImportError as e:
        print(f"✗ MCP dependency error: {e}")
        print("Install with: pip install mcp")
        return False

def test_environment():
    """Test environment setup"""
    print("\nTesting environment...")
    
    # Test Python version
    print(f"Python version: {sys.version}")
    
    # Test encoding
    print(f"Default encoding: {sys.getdefaultencoding()}")
    print(f"Stdout encoding: {sys.stdout.encoding}")
    print(f"Stderr encoding: {sys.stderr.encoding}")
    
    # Test environment variable
    news_api_key = os.getenv("NEWS_API_KEY", "9830fcd69f284b8e8c0a093da8d165f8")
    print(f"NEWS_API_KEY: {'*' * (len(news_api_key) - 4) + news_api_key[-4:]}")
    
    return True

def create_minimal_test_server():
    """Create a minimal MCP server for testing"""
    print("\nCreating minimal test server...")
    
    test_server_code = '''#!/usr/bin/env python3
import asyncio
import sys
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent

# Simple test server
server = Server("test-server")

@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="test_tool",
            description="A simple test tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Test message"}
                },
                "required": ["message"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name, arguments):
    if name == "test_tool":
        message = arguments.get("message", "Hello World")
        return [TextContent(type="text", text=f"Test response: {message}")]
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="test-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities()
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    with open("test_mcp_server.py", "w", encoding="utf-8") as f:
        f.write(test_server_code)
    
    print("✓ Minimal test server created: test_mcp_server.py")
    print("You can test it with:")
    print('{"mcpServers": {"test": {"command": "python", "args": ["test_mcp_server.py"]}}}')

def main():
    """Run all tests"""
    print("=== MCP News Server Diagnostic ===\n")
    
    tests = [
        ("Environment", test_environment),
        ("MCP Dependencies", test_mcp_dependencies),
        ("MCP Server Syntax", test_mcp_server_syntax),
        ("NewsAPI Connection", test_news_api),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n=== Test Results ===")
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    # Create minimal test server regardless
    create_minimal_test_server()
    
    print("\n=== Troubleshooting Steps ===")
    print("1. If NewsAPI fails: Check your API key and internet connection")
    print("2. If MCP dependencies fail: Run 'pip install mcp'")
    print("3. If syntax fails: Check the MCP server file for errors")
    print("4. Try the minimal test server first")
    print("5. Check the log file: mcp_news_server.log")

if __name__ == "__main__":
    main()