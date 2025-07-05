
import streamlit as st
import asyncio
import json
import pandas as pd
from typing import Dict, Any
import os 

from openai import AsyncOpenAI
from ..config.settings import AppConfig
from ..core.mcp_client import MCPClientManager

class GitLabIssuesApp:
    """Streamlit application for GitLab issues with proper MCP connection."""
    
    def __init__(self):
        self.config = self._load_config()
        self.openai_client = AsyncOpenAI(api_key=self.config.openai.api_key)
        self.mcp_client = MCPClientManager(self.config)
    
    def _load_config(self) -> AppConfig:
        """Load application configuration."""
        try:
            return AppConfig.from_env()
        except ValueError as e:
            st.error(f"Configuration error: {e}")
            st.stop()
    
    async def process_message(self, user_message: str, model: str) -> Dict[str, Any]:
        """Process user message using proper OpenAI tool calling."""
        
        tools = [
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
        
        system_message = {
            "role": "system",
            "content": """You are an AI assistant that helps users with GitLab issues.

When users ask about issues WITHOUT specifying a month , ask them which month they want we dont need year so do not ask year to see issues from.
When users specify a month or time period, use the list_gitlab_issues tool with appropriate parameters.

Examples:
- "show me issues" → ask for month specification
- "January bugs" → use tool with month="January", labels="bug"
- "this month high priority" → use tool with month="this month", labels="high-priority"
- "last month closed issues" → use tool with month="last month", state="closed"
"""
        }
        
        messages = [system_message, {"role": "user", "content": user_message}]
        
        try:
            # OpenAI call with tool availability
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            # If no tool calls, return regular response
            if not tool_calls:
                return {
                    "type": "text",
                    "content": response_message.content,
                    "tokens_used": response.usage.total_tokens
                }
            
            # Execute tool calls
            messages.append(response_message)
            mcp_result = None
            
            for tool_call in tool_calls:
                if tool_call.function.name == "list_gitlab_issues":
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        # Use proper MCP client connection
                        print(f"Calling MCP tool: {tool_call.function.name} with arguments: {arguments}")
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
                            "content": f"Error calling MCP tool: {str(e)}"
                        }
            
            # Get final response from OpenAI
            final_response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages
            )
            
            return {
                "type": "mcp_response",
                "content": final_response.choices[0].message.content,
                "mcp_result": mcp_result,
                "tokens_used": response.usage.total_tokens + final_response.usage.total_tokens
            }
            
        except Exception as e:
            return {
                "type": "error",
                "content": f"Error processing request: {str(e)}"
            }
    
    def render_sidebar(self):
        """Render application sidebar with connection status."""
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # Show configuration status
            st.success(f"✅ GitLab: {len(self.config.gitlab.project_ids)} projects")
            st.success("✅ OpenAI configured")
            
            # MCP Server connection status
            if st.button("🔍 Test MCP Connection"):
                with st.spinner("Testing MCP connection..."):
                    health_result = asyncio.run(self.mcp_client.health_check())
                    if health_result.get("success"):
                        st.success("✅ MCP Server connected")
                        if health_result.get("gitlab_connection"):
                            st.success("✅ GitLab connection healthy")
                    else:
                        st.error(f"❌ MCP Server: {health_result.get('error', 'Connection failed')}")
            
            # Show connection method
            server_url = os.getenv("MCP_SERVER_URL")
            if server_url:
                st.info(f"🌐 Remote server: {server_url}")
            else:
                st.info("🖥️ Local server connection")
            
            # Show projects
            with st.expander("📋 Configured Projects"):
                for project_id in self.config.gitlab.project_ids:
                    st.code(project_id)
            
            st.markdown("---")
            
            model = st.selectbox("🤖 Model", ["gpt-3.5-turbo", "gpt-4o"], index=0)
            
            return model
        
    def render_mcp_results(self, mcp_result: Dict[str, Any]):
        """Render MCP tool results."""
        if mcp_result.get("summary"):
            st.markdown(mcp_result["summary"])
        
        # Show table
        if mcp_result.get("table_data"):
            st.markdown("### Issues Table")
            df = pd.DataFrame(mcp_result["table_data"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Show detailed issues
        if mcp_result.get("issues"):
            st.markdown("### Issue Details")
            for issue in mcp_result["issues"][:5]:  # Show first 5
                with st.expander(f"#{issue['iid']} - {issue['title']}", expanded=False):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Project:** {issue['project_name']}")
                        st.write(f"**Author:** {issue['author']}")
                        if issue['assignee']:
                            st.write(f"**Assignee:** {issue['assignee']}")
                        if issue.get('description'):
                            st.write(f"**Description:** {issue['description']}")
                    
                    with col2:
                        state_color = "🟢" if issue['state'] == 'opened' else "🔴"
                        st.write(f"**State:** {state_color} {issue['state']}")
                        st.write(f"**Created:** {issue['created_date']}")
                        st.write(f"**Priority:** {issue.get('priority', 'normal')}")
                        
                        if issue['labels']:
                            st.write("**Labels:**")
                            for label in issue['labels'][:3]:
                                st.badge(label)
                        
                        st.markdown(f"[🔗 View in GitLab]({issue['web_url']})")
    
    def run(self):
        """Run the Streamlit application."""
        st.set_page_config(
            page_title="GitLab Issues Assistant (Professional)",
            page_icon="🦊",
            layout="wide"
        )
        
        st.title("🦊 GitLab Issues Assistant")
        st.markdown("Professional FastMCP-powered GitLab issues management")
        
        # Render sidebar
        model = self.render_sidebar()
        
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask about GitLab issues..."):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Processing..."):
                    response = asyncio.run(self.process_message(prompt, model))
                    
                    if response["type"] == "error":
                        st.error(response["content"])
                    
                    elif response["type"] == "mcp_response":
                        st.markdown(response["content"])
                        self.render_mcp_results(response["mcp_result"])
                    
                    else:
                        st.markdown(response["content"])
            
            # Add to chat history
            st.session_state.messages.append({
                "role": "assistant",
                "content": response["content"]
            })
            