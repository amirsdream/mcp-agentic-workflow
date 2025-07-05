
#!/usr/bin/env python3
"""
GitLab Issues MCP Server Runner with multiple transport options
"""

import sys
import os
import argparse
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.config.settings import AppConfig
from src.gitlabmcp.server import GitLabMCPServer

def main():
    """Main entry point for MCP server."""
    parser = argparse.ArgumentParser(description="GitLab Issues MCP Server")
    parser.add_argument(
        "--transport", 
        choices=["stdio", "http"], 
        default="stdio",
        help="Transport protocol to use"
    )
    parser.add_argument(
        "--host", 
        default="0.0.0.0",
        help="Host to bind to (HTTP transport only)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="Port to bind to (HTTP transport only)"
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = AppConfig.from_env()
        
        # Create server
        server = GitLabMCPServer(config)
        
        # Run with selected transport
        if args.transport == "stdio":
            server.run_stdio()
        else:
            server.run_http(host=args.host, port=args.port)
        
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("\nRequired environment variables:")
        print("- OPENAI_API_KEY")
        print("- GITLAB_TOKEN") 
        print("- GITLAB_PROJECT_IDS (comma-separated)")
        print("- GITLAB_URL (optional, defaults to https://gitlab.com)")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()