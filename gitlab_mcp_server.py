#!/usr/bin/env python3
"""
MCP GitLab Server - Model Context Protocol server for GitLab interactions
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urljoin

import httpx
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    CallToolResult,
    ListResourcesResult,
    ListToolsResult,
    ReadResourceResult,
)
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitLabConfig:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip('/')
        self.token = token
        self.api_url = f"{self.url}/api/v4"

class GitLabMCPServer:
    def __init__(self, config: GitLabConfig):
        self.config = config
        self.server = Server("gitlab-mcp-server")
        self.client = httpx.AsyncClient(
            headers={"Private-Token": config.token},
            timeout=30.0
        )
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up all the MCP handlers"""
        
        @self.server.list_resources()
        async def handle_list_resources() -> ListResourcesResult:
            """List available GitLab resources"""
            resources = [
                Resource(
                    uri="gitlab://projects",
                    name="GitLab Projects",
                    description="List of accessible GitLab projects",
                    mimeType="application/json"
                ),
                Resource(
                    uri="gitlab://issues",
                    name="GitLab Issues",
                    description="Issues across projects",
                    mimeType="application/json"
                ),
                Resource(
                    uri="gitlab://merge_requests",
                    name="GitLab Merge Requests",
                    description="Merge requests across projects",
                    mimeType="application/json"
                ),
            ]
            return ListResourcesResult(resources=resources)

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> ReadResourceResult:
            """Read a specific GitLab resource"""
            try:
                if uri == "gitlab://projects":
                    projects = await self._get_projects()
                    content = TextContent(
                        type="text",
                        text=json.dumps(projects, indent=2)
                    )
                elif uri == "gitlab://issues":
                    issues = await self._get_issues()
                    content = TextContent(
                        type="text",
                        text=json.dumps(issues, indent=2)
                    )
                elif uri == "gitlab://merge_requests":
                    mrs = await self._get_merge_requests()
                    content = TextContent(
                        type="text",
                        text=json.dumps(mrs, indent=2)
                    )
                else:
                    raise ValueError(f"Unknown resource URI: {uri}")
                
                return ReadResourceResult(contents=[content])
            except Exception as e:
                logger.error(f"Error reading resource {uri}: {e}")
                error_content = TextContent(
                    type="text",
                    text=f"Error reading resource: {str(e)}"
                )
                return ReadResourceResult(contents=[error_content])

        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """List available GitLab tools"""
            tools = [
                Tool(
                    name="get_project",
                    description="Get details of a specific GitLab project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "Project ID or path"
                            }
                        },
                        "required": ["project_id"]
                    }
                ),
                Tool(
                    name="list_projects",
                    description="List GitLab projects",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search": {
                                "type": "string",
                                "description": "Search term for projects"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of projects to return",
                                "default": 20
                            }
                        }
                    }
                ),
                Tool(
                    name="create_issue",
                    description="Create a new issue in a GitLab project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "Project ID or path"
                            },
                            "title": {
                                "type": "string",
                                "description": "Issue title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Issue description"
                            },
                            "labels": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Issue labels"
                            }
                        },
                        "required": ["project_id", "title"]
                    }
                ),
                Tool(
                    name="list_issues",
                    description="List issues from a GitLab project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "Project ID or path"
                            },
                            "state": {
                                "type": "string",
                                "enum": ["opened", "closed", "all"],
                                "default": "opened"
                            },
                            "limit": {
                                "type": "integer",
                                "default": 20
                            }
                        },
                        "required": ["project_id"]
                    }
                ),
                Tool(
                    name="create_merge_request",
                    description="Create a new merge request",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "title": {"type": "string"},
                            "source_branch": {"type": "string"},
                            "target_branch": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["project_id", "title", "source_branch", "target_branch"]
                    }
                ),
                Tool(
                    name="list_merge_requests",
                    description="List merge requests from a project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "state": {
                                "type": "string",
                                "enum": ["opened", "closed", "merged", "all"],
                                "default": "opened"
                            },
                            "limit": {"type": "integer", "default": 20}
                        },
                        "required": ["project_id"]
                    }
                ),
                Tool(
                    name="get_file_content",
                    description="Get content of a file from GitLab repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "file_path": {"type": "string"},
                            "ref": {"type": "string", "default": "main"}
                        },
                        "required": ["project_id", "file_path"]
                    }
                )
            ]
            return ListToolsResult(tools=tools)

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Handle tool calls"""
            try:
                if name == "get_project":
                    result = await self._get_project(arguments["project_id"])
                elif name == "list_projects":
                    result = await self._list_projects(
                        search=arguments.get("search"),
                        limit=arguments.get("limit", 20)
                    )
                elif name == "create_issue":
                    result = await self._create_issue(
                        project_id=arguments["project_id"],
                        title=arguments["title"],
                        description=arguments.get("description", ""),
                        labels=arguments.get("labels", [])
                    )
                elif name == "list_issues":
                    result = await self._list_issues(
                        project_id=arguments["project_id"],
                        state=arguments.get("state", "opened"),
                        limit=arguments.get("limit", 20)
                    )
                elif name == "create_merge_request":
                    result = await self._create_merge_request(
                        project_id=arguments["project_id"],
                        title=arguments["title"],
                        source_branch=arguments["source_branch"],
                        target_branch=arguments["target_branch"],
                        description=arguments.get("description", "")
                    )
                elif name == "list_merge_requests":
                    result = await self._list_merge_requests(
                        project_id=arguments["project_id"],
                        state=arguments.get("state", "opened"),
                        limit=arguments.get("limit", 20)
                    )
                elif name == "get_file_content":
                    result = await self._get_file_content(
                        project_id=arguments["project_id"],
                        file_path=arguments["file_path"],
                        ref=arguments.get("ref", "main")
                    )
                else:
                    raise ValueError(f"Unknown tool: {name}")

                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result, indent=2))]
                )
            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error: {str(e)}")]
                )

    async def _get_projects(self) -> List[Dict]:
        """Get all accessible projects"""
        response = await self.client.get(f"{self.config.api_url}/projects")
        response.raise_for_status()
        return response.json()

    async def _get_project(self, project_id: str) -> Dict:
        """Get specific project details"""
        response = await self.client.get(f"{self.config.api_url}/projects/{project_id}")
        response.raise_for_status()
        return response.json()

    async def _list_projects(self, search: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """List projects with optional search"""
        params = {"per_page": limit}
        if search:
            params["search"] = search
        
        response = await self.client.get(f"{self.config.api_url}/projects", params=params)
        response.raise_for_status()
        return response.json()

    async def _get_issues(self) -> List[Dict]:
        """Get issues across all projects"""
        response = await self.client.get(f"{self.config.api_url}/issues")
        response.raise_for_status()
        return response.json()

    async def _list_issues(self, project_id: str, state: str = "opened", limit: int = 20) -> List[Dict]:
        """List issues for a specific project"""
        params = {"state": state, "per_page": limit}
        response = await self.client.get(
            f"{self.config.api_url}/projects/{project_id}/issues",
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def _create_issue(self, project_id: str, title: str, description: str = "", labels: List[str] = None) -> Dict:
        """Create a new issue"""
        data = {
            "title": title,
            "description": description
        }
        if labels:
            data["labels"] = ",".join(labels)
        
        response = await self.client.post(
            f"{self.config.api_url}/projects/{project_id}/issues",
            json=data
        )
        response.raise_for_status()
        return response.json()

    async def _get_merge_requests(self) -> List[Dict]:
        """Get merge requests across all projects"""
        response = await self.client.get(f"{self.config.api_url}/merge_requests")
        response.raise_for_status()
        return response.json()

    async def _list_merge_requests(self, project_id: str, state: str = "opened", limit: int = 20) -> List[Dict]:
        """List merge requests for a specific project"""
        params = {"state": state, "per_page": limit}
        response = await self.client.get(
            f"{self.config.api_url}/projects/{project_id}/merge_requests",
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def _create_merge_request(self, project_id: str, title: str, source_branch: str, 
                                  target_branch: str, description: str = "") -> Dict:
        """Create a new merge request"""
        data = {
            "title": title,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "description": description
        }
        
        response = await self.client.post(
            f"{self.config.api_url}/projects/{project_id}/merge_requests",
            json=data
        )
        response.raise_for_status()
        return response.json()

    async def _get_file_content(self, project_id: str, file_path: str, ref: str = "main") -> Dict:
        """Get file content from repository"""
        params = {"ref": ref}
        response = await self.client.get(
            f"{self.config.api_url}/projects/{project_id}/repository/files/{file_path.replace('/', '%2F')}",
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as streams:
            await self.server.run(
                streams[0], streams[1], InitializationOptions(
                    server_name="gitlab-mcp-server",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities=None,
                    ),
                )
            )

async def main():
    """Main entry point"""
    import os
    
    gitlab_url = os.getenv("GITLAB_URL", "https://gitlab.com")
    gitlab_token = os.getenv("GITLAB_TOKEN")
    
    if not gitlab_token:
        raise ValueError("GITLAB_TOKEN environment variable is required")
    
    config = GitLabConfig(gitlab_url, gitlab_token)
    server = GitLabMCPServer(config)
    
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())