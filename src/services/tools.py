"""
OpenAI Tools Service for Direct Tool Calling (Fallback)
"""

import json
from typing import Dict, Any
from openai import AsyncOpenAI

from ..core.mcp_client import MCPClientManager


class ToolsService:
    """Service for direct OpenAI tool calling"""
    
    def __init__(self, openai_client: AsyncOpenAI, mcp_client: MCPClientManager):
        self.openai_client = openai_client
        self.mcp_client = mcp_client
        
    def get_tools_definition(self) -> list:
        """Get OpenAI tools definition"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_gitlab_issues",
                    "description": "List GitLab issues from configured projects with filtering options.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "month": {
                                "type": "string",
                                "description": "Month filter like 'January', 'Feb 2024', 'this month', 'last month'"
                            },
                            "year": {
                                "type": "string",
                                "description": "year filter like '2024', 'this year', 'last year'"
                            },
                            "state": {
                                "type": "string",
                                "description": "Issue state: 'opened', 'closed', or 'all'",
                                "enum": ["opened", "closed", "all"],
                                "default": "opened"
                            },
                            "labels": {
                                "type": "string",
                                "description": "Comma-separated labels to filter by"
                            },
                            "assignee": {
                                "type": "string",
                                "description": "Filter by assignee name"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of issues to return",
                                "default": 100
                            }
                        }
                    }
                }
            }
        ]
    
    def get_system_message(self) -> Dict[str, str]:
        """Get system message for tool calling"""
        return {
            "role": "system",
            "content": """You are an AI assistant that helps users with GitLab issues.

When users ask about issues WITHOUT specifying a month, ask them which month they want to see issues from.
When users specify a month or time period, use the list_gitlab_issues tool with appropriate parameters.

Examples:
- "show me issues" → ask for month specification
- "January bugs" → use tool with month="January", labels="bug"
- "this month high priority" → use tool with month="this month", labels="high-priority"
- "last month closed issues" → use tool with month="last month", state="closed"
"""
        }
    
    async def process_with_tools(self, user_message: str, model: str) -> Dict[str, Any]:
        """Process user message using OpenAI tool calling"""
        tools = self.get_tools_definition()
        system_message = self.get_system_message()
        
        messages = [system_message, {"role": "user", "content": user_message}]
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            total_tokens = response.usage.total_tokens
            
            if not tool_calls:
                return {
                    "type": "text",
                    "content": response_message.content,
                    "tokens_used": total_tokens
                }
            
            messages.append(response_message)
            mcp_result = None
            
            for tool_call in tool_calls:
                if tool_call.function.name == "list_gitlab_issues":
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        mcp_result = await self.mcp_client.call_tool("list_gitlab_issues", arguments)
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": "list_gitlab_issues",
                            "content": json.dumps(mcp_result)
                        })
                    except Exception as e:
                        return {
                            "type": "error",
                            "content": f"Error calling MCP tool: {str(e)}",
                            "tokens_used": total_tokens
                        }
            
            final_response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages
            )
            
            final_tokens = total_tokens + final_response.usage.total_tokens
            
            return {
                "type": "mcp_response",
                "content": final_response.choices[0].message.content,
                "mcp_result": mcp_result,
                "tokens_used": final_tokens
            }
            
        except Exception as e:
            return {
                "type": "error",
                "content": f"Error processing request: {str(e)}",
                "tokens_used": 0
            }