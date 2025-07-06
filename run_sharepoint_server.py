#!/usr/bin/env python3
"""
SharePoint Forms MCP Server Runner
"""

import sys
import os
import argparse
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Main entry point for SharePoint MCP server."""
    parser = argparse.ArgumentParser(description="SharePoint Forms MCP Server")
    parser.add_argument(
        "--transport", 
        choices=["stdio", "http", "websocket"], 
        default="stdio",
        help="Transport type (default: stdio)"
    )
    parser.add_argument(
        "--host", 
        default="0.0.0.0",
        help="Host to bind to for HTTP/WebSocket transport (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8001,
        help="Port to bind to for HTTP transport (default: 8001)"
    )
    parser.add_argument(
        "--ws-port", 
        type=int, 
        default=8002,
        help="Port to bind to for WebSocket transport (default: 8002)"
    )
    
    args = parser.parse_args()
    
    try:
        from src.config.settings import AppConfig
        from src.mcp.sharepoint_server import SharePointMCPServer
        
        # Load configuration
        try:
            config = AppConfig.from_env()
        except ValueError as e:
            print(f"❌ Configuration error: {e}")
            print("\n📋 Required environment variables for SharePoint:")
            print("- SHAREPOINT_SITE_URL: SharePoint site URL")
            print("- SHAREPOINT_USERNAME: SharePoint username")
            print("- SHAREPOINT_PASSWORD: SharePoint password")
            print("\n💡 Optional:")
            print("- SHAREPOINT_PRIMARY_SITE: Primary site URL")
            print("- SHAREPOINT_SECONDARY_SITE: Secondary site URL")
            return 1
        
        # Create and run server
        server = SharePointMCPServer(config)
        
        print(f"🚀 Starting SharePoint Forms MCP Server...")
        print(f"📋 Site URL: {config.get('sharepoint_site_url', 'Not configured')}")
        print(f"👤 Username: {config.get('sharepoint_username', 'Not configured')}")
        print(f"🔗 Transport: {args.transport}")
        
        if args.transport == "stdio":
            server.run_stdio()
        elif args.transport == "http":
            print(f"🌐 HTTP Server: http://{args.host}:{args.port}")
            server.run_http(args.host, args.port)
        elif args.transport == "websocket":
            print(f"🔌 WebSocket Server: ws://{args.host}:{args.ws_port}")
            server.run_websocket(args.host, args.ws_port)
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\n📦 Missing dependencies. Install with:")
        print("pip install fastmcp Office365-REST-Python-Client")
        return 1
    except KeyboardInterrupt:
        print("\n👋 SharePoint MCP Server stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Server error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())