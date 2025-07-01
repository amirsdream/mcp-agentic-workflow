"""
AutoGen GitLab Agent - Integrates with MCP GitLab Server
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Callable
import subprocess
import tempfile
import os

from autogen import ConversableAgent, UserProxyAgent
from autogen.coding import LocalCommandLineCodeExecutor

logger = logging.getLogger(__name__)

class GitLabMCPClient:
    """Client to communicate with GitLab MCP Server"""
    
    def __init__(self, server_command: str = None):
        self.server_command = server_command or "python gitlab_mcp_server.py"
        self.process = None
    
    async def start_server(self):
        """Start the MCP server process"""
        try:
            self.process = await asyncio.create_subprocess_shell(
                self.server_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            logger.info("GitLab MCP Server started")
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict:
        """Call a tool on the MCP server"""
        if not self.process:
            await self.start_server()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            # Send request
            request_str = json.dumps(request) + "\n"
            self.process.stdin.write(request_str.encode())
            await self.process.stdin.drain()
            
            # Read response
            response_line = await self.process.stdout.readline()
            response = json.loads(response_line.decode())
            
            if "error" in response:
                raise Exception(f"MCP Error: {response['error']}")
            
            return response.get("result", {})
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            raise
    
    async def list_resources(self) -> List[Dict]:
        """List available resources"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/list"
        }
        
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str.encode())
        await self.process.stdin.drain()
        
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())
        
        return response.get("result", {}).get("resources", [])
    
    async def close(self):
        """Close the MCP server connection"""
        if self.process:
            self.process.terminate()
            await self.process.wait()

class GitLabAgent(ConversableAgent):
    """AutoGen agent that can interact with GitLab via MCP"""
    
    def __init__(self, name: str = "GitLabAgent", **kwargs):
        super().__init__(
            name=name,
            system_message="""You are a GitLab agent that can help users interact with GitLab repositories.
            You can:
            - List and search projects
            - Create and manage issues
            - Create and manage merge requests
            - Read file contents from repositories
            - Get project information
            
            When users ask for GitLab operations, use the available tools to perform the requested actions.
            Always provide clear feedback about what actions were performed.
            """,
            **kwargs
        )
        self.mcp_client = GitLabMCPClient()
        self._setup_tool_functions()
    
    def _setup_tool_functions(self):
        """Set up tool functions for AutoGen"""
        
        async def list_projects(search: str = "", limit: int = 20) -> str:
            """List GitLab projects"""
            try:
                result = await self.mcp_client.call_tool("list_projects", {
                    "search": search,
                    "limit": limit
                })
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing projects: {str(e)}"
        
        async def get_project(project_id: str) -> str:
            """Get project details"""
            try:
                result = await self.mcp_client.call_tool("get_project", {
                    "project_id": project_id
                })
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error getting project: {str(e)}"
        
        async def create_issue(project_id: str, title: str, description: str = "", labels: List[str] = None) -> str:
            """Create a new issue"""
            try:
                result = await self.mcp_client.call_tool("create_issue", {
                    "project_id": project_id,
                    "title": title,
                    "description": description,
                    "labels": labels or []
                })
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error creating issue: {str(e)}"
        
        async def list_issues(project_id: str, state: str = "opened", limit: int = 20) -> str:
            """List project issues"""
            try:
                result = await self.mcp_client.call_tool("list_issues", {
                    "project_id": project_id,
                    "state": state,
                    "limit": limit
                })
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing issues: {str(e)}"
        
        async def create_merge_request(project_id: str, title: str, source_branch: str, 
                                     target_branch: str, description: str = "") -> str:
            """Create a merge request"""
            try:
                result = await self.mcp_client.call_tool("create_merge_request", {
                    "project_id": project_id,
                    "title": title,
                    "source_branch": source_branch,
                    "target_branch": target_branch,
                    "description": description
                })
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error creating merge request: {str(e)}"
        
        async def list_merge_requests(project_id: str, state: str = "opened", limit: int = 20) -> str:
            """List merge requests"""
            try:
                result = await self.mcp_client.call_tool("list_merge_requests", {
                    "project_id": project_id,
                    "state": state,
                    "limit": limit
                })
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing merge requests: {str(e)}"
        
        async def get_file_content(project_id: str, file_path: str, ref: str = "main") -> str:
            """Get file content from repository"""
            try:
                result = await self.mcp_client.call_tool("get_file_content", {
                    "project_id": project_id,
                    "file_path": file_path,
                    "ref": ref
                })
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error getting file content: {str(e)}"
        
        # Register functions with AutoGen
        self.register_for_execution(name="list_projects")(list_projects)
        self.register_for_execution(name="get_project")(get_project)
        self.register_for_execution(name="create_issue")(create_issue)
        self.register_for_execution(name="list_issues")(list_issues)
        self.register_for_execution(name="create_merge_request")(create_merge_request)
        self.register_for_execution(name="list_merge_requests")(list_merge_requests)
        self.register_for_execution(name="get_file_content")(get_file_content)
    
    async def initialize(self):
        """Initialize the MCP client"""
        await self.mcp_client.start_server()
    
    async def cleanup(self):
        """Clean up resources"""
        await self.mcp_client.close()

class GitLabAssistant:
    """Main assistant class that coordinates AutoGen agents"""
    
    def __init__(self, llm_config: Dict[str, Any]):
        self.llm_config = llm_config
        self.gitlab_agent = None
        self.user_proxy = None
        self._setup_agents()
    
    def _setup_agents(self):
        """Set up AutoGen agents"""
        
        # Create GitLab agent
        self.gitlab_agent = GitLabAgent(
            name="gitlab_agent",
            llm_config=self.llm_config,
            code_execution_config=False,
        )
        
        # Create user proxy agent
        self.user_proxy = UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10,
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            code_execution_config={
                "executor": LocalCommandLineCodeExecutor(work_dir="./gitlab_workspace"),
            },
        )
    
    async def initialize(self):
        """Initialize the assistant"""
        await self.gitlab_agent.initialize()
    
    async def chat(self, message: str) -> str:
        """Process a chat message"""
        try:
            # Start conversation with the GitLab agent
            chat_result = self.user_proxy.initiate_chat(
                self.gitlab_agent,
                message=message,
                silent=True
            )
            
            # Extract the final response
            if chat_result and chat_result.chat_history:
                last_message = chat_result.chat_history[-1]
                return last_message.get("content", "No response generated")
            else:
                return "No response generated"
                
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"Error processing request: {str(e)}"
    
    async def cleanup(self):
        """Clean up resources"""
        if self.gitlab_agent:
            await self.gitlab_agent.cleanup()

# Example usage and testing
async def test_gitlab_assistant():
    """Test the GitLab assistant"""
    
    # Configuration for LLM (adjust as needed)
    llm_config = {
        "config_list": [
            {
                "model": "gpt-4",
                "api_key": os.getenv("OPENAI_API_KEY"),
            }
        ],
        "temperature": 0.1,
    }
    
    assistant = GitLabAssistant(llm_config)
    
    try:
        await assistant.initialize()
        
        # Test various GitLab operations
        test_messages = [
            "List my GitLab projects",
            "Show me open issues in project 'my-project'",
            "Create an issue titled 'Bug fix needed' in project '123'",
            "List merge requests for project 'my-repo'",
        ]
        
        for message in test_messages:
            print(f"\nUser: {message}")
            response = await assistant.chat(message)
            print(f"Assistant: {response}")
            
    finally:
        await assistant.cleanup()

if __name__ == "__main__":
    asyncio.run(test_gitlab_assistant())