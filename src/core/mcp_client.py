import os
import asyncio
from typing import Dict, Any, Optional
from fastmcp import Client
from fastmcp.client.transports import SSETransport
from ..config.settings import AppConfig

class MCPClientManager:
    """Manages MCP client connections to running servers."""
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config
        self._client: Optional[Client] = None
        
    async def get_client(self) -> Client:
        """Get MCP client with appropriate transport."""
        if self._client is None:
            self._client = await self._create_client()
        return self._client
    
    async def _create_client(self) -> Client:
        """Create MCP client based on configuration."""
        # Check for server URL first (production)
        server_url = os.getenv("MCP_SERVER_URL")
        if server_url:
            return await self._create_sse_client(server_url)
        
        # Check for server host/port (docker/kubernetes)
        server_host = os.getenv("MCP_SERVER_HOST", "localhost")
        server_port = os.getenv("MCP_SERVER_PORT")
        if server_port:
            url = f"http://{server_host}:{server_port}/mcp/sse"
            return await self._create_sse_client(url)
        
        # Fallback to local command (development)
        return await self._create_stdio_client()
    
    async def _create_sse_client(self, url: str) -> Client:
        """Create SSE transport client for remote server."""
        transport = SSETransport(url)
        return Client(transport)
    
    async def _create_stdio_client(self) -> Client:
        """Create stdio transport client for local server."""
        # This assumes the server is running separately
        # In production, you'd never use this approach
        # not working 
        # server_command = ["python", "run_server.py"]
        # return Client(server_command)
        pass
        raise NotImplementedError("stdio transport is not implemented in this context.")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> Dict[str, Any]:
        """Call MCP tool with proper connection management."""
        try:
            client = await self.get_client()
            async with client:
                result = await client.call_tool(tool_name, arguments)
                return result
        except Exception as e:
            return {
                "success": False, 
                "error": f"MCP connection failed: {str(e)}"
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check MCP server health."""
        try:
            return await self.call_tool("health_check", {})
        except Exception as e:
            return {
                "success": False,
                "error": f"Health check failed: {str(e)}"
            }