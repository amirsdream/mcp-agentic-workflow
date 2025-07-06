import streamlit as st
import asyncio
import json
import pandas as pd
from typing import Dict, Any
import os 
from datetime import datetime, timedelta
import requests
import urllib.parse
import secrets

from openai import AsyncOpenAI
from ..config.settings import AppConfig
from ..core.mcp_client import MCPClientManager

# GitLab OAuth2 Config - UPDATE THESE VALUES
CLIENT_ID = os.getenv("GITLAB_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GITLAB_CLIENT_SECRET", "")
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com")
REDIRECT_URI = "http://localhost:8501"

def gitlab_auth():
    """Simple GitLab OAuth2 authentication - redirects and grabs token"""
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    
    # Check for OAuth callback (code parameter)
    query_params = st.query_params
    if 'code' in query_params and not st.session_state.authenticated:
        code = query_params['code']
        
        with st.spinner("🔄 Completing authentication..."):
            # Exchange code for token
            token_data = {
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': REDIRECT_URI
            }
            
            try:
                response = requests.post(f"{GITLAB_URL}/oauth/token", data=token_data)
                if response.status_code == 200:
                    token_info = response.json()
                    st.session_state.access_token = token_info['access_token']
                    st.session_state.authenticated = True
                    
                    # Clear URL parameters
                    st.query_params.clear()
                    st.success("✅ Authentication successful!")
                    st.rerun()
                else:
                    st.error(f"Token exchange failed: {response.status_code}")
            except Exception as e:
                st.error(f"Authentication failed: {e}")
    
    # Main UI
    if st.session_state.authenticated:
        # Return token for use in app
        return st.session_state.access_token
    
    else:
        # Show login page
        st.warning("Please authenticate with GitLab to continue")
        
        if st.button("🔑 Login with GitLab"):
            state = secrets.token_urlsafe(16)
            auth_url = f"{GITLAB_URL}/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read_api read_user&state={state}"
            
            # Simple redirect to GitLab
            st.markdown(f'<meta http-equiv="refresh" content="0; url={auth_url}">', unsafe_allow_html=True)
        
        st.stop()  # Stop execution until authenticated


class GitLabIssuesApp:
    """Streamlit application for GitLab issues with proper MCP connection."""
    
    def __init__(self):
        # First authenticate with GitLab
        self.gitlab_token = gitlab_auth()
        
        self.config = self._load_config()
        self.openai_client = AsyncOpenAI(api_key=self.config.openai.api_key)
        self.mcp_client = MCPClientManager(self.config)
        
        if "total_tokens_used" not in st.session_state:
            st.session_state.total_tokens_used = 0
        if "session_cost" not in st.session_state:
            st.session_state.session_cost = 0.0
    
    def _load_config(self) -> AppConfig:
        """Load application configuration."""
        try:
            return AppConfig.from_env()
        except ValueError as e:
            st.error(f"Configuration error: {e}")
            st.stop()
    
    def calculate_cost(self, tokens: int, model: str) -> float:
        """Calculate approximate cost based on tokens and model."""
        pricing = {
            "gpt-3.5-turbo": 0.002 / 1000, 
            "gpt-4o": 0.03 / 1000,         
            "gpt-4": 0.03 / 1000,
        }
        return tokens * pricing.get(model, 0.002 / 1000)
    
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

When users ask about issues WITHOUT specifying a month, ask them which month they want to see issues from.
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
    
    def render_quick_filters(self):
        """Render quick filter buttons that add queries to session state."""
        st.subheader("🚀 Quick Actions")
        
        if "pending_query" not in st.session_state:
            st.session_state.pending_query = None
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📅 This Month Issues", use_container_width=True, key="btn_this_month"):
                st.session_state.pending_query = "show me all issues from this month"
                st.rerun()
            if st.button("🔥 High Priority", use_container_width=True, key="btn_high_priority"):
                st.session_state.pending_query = "show me high priority issues from this month"
                st.rerun()
            if st.button("🐛 Bugs This Month", use_container_width=True, key="btn_bugs"):
                st.session_state.pending_query = "show me bug issues from this month"
                st.rerun()
            if st.button("✅ Closed Issues", use_container_width=True, key="btn_closed"):
                st.session_state.pending_query = "show me closed issues from this month"
                st.rerun()
        
        with col2:
            if st.button("📆 Last Month", use_container_width=True, key="btn_last_month"):
                st.session_state.pending_query = "show me all issues from last month"
                st.rerun()
            if st.button("🔴 Critical Issues", use_container_width=True, key="btn_critical"):
                st.session_state.pending_query = "show me critical issues from this month"
                st.rerun()
            if st.button("👤 My Issues", use_container_width=True, key="btn_my_issues"):
                st.session_state.pending_query = "show me issues assigned to me this month"
                st.rerun()
            if st.button("📊 Issue Summary", use_container_width=True, key="btn_summary"):
                st.session_state.pending_query = "give me a summary of all issues from this month with statistics"
                st.rerun()
        
        # Custom quick queries
        st.markdown("**💡 Example Queries:**")
        examples = [
            "Show me all enhancement requests from January",
            "What are the oldest open issues?",
            "Show me issues labeled 'documentation'",
            "Give me a breakdown of issues by project",
            "Show me issues created by John Doe"
        ]
        
        for i, example in enumerate(examples):
            if st.button(f"💬 {example}", key=f"example_{i}", use_container_width=True):
                st.session_state.pending_query = example
                st.rerun()
    
    def render_token_usage(self, model: str):
        """Render token usage and cost tracking."""
        st.subheader("💰 Usage Tracking")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                label="Total Tokens",
                value=f"{st.session_state.total_tokens_used:,}",
                delta=None
            )
        
        with col2:
            st.metric(
                label="Session Cost",
                value=f"${st.session_state.session_cost:.4f}",
                delta=None
            )
        
        if st.session_state.total_tokens_used > 50000:
            st.warning("⚠️ High token usage detected")
        elif st.session_state.total_tokens_used > 100000:
            st.error("🚨 Very high token usage!")
        
        if st.button("🔄 Reset Usage Stats"):
            st.session_state.total_tokens_used = 0
            st.session_state.session_cost = 0.0
            st.rerun()
        
        pricing_info = {
            "gpt-3.5-turbo": "$0.002/1K tokens",
            "gpt-4o": "$0.030/1K tokens",
            "gpt-4": "$0.030/1K tokens"
        }
        st.info(f"📋 Current model: {model} ({pricing_info.get(model, 'Pricing unknown')})")
    
    def render_sidebar(self):
        """Render application sidebar with connection status and filters."""
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # GitLab Authentication Status
            st.markdown("**🔐 GitLab Authentication:**")
            if st.session_state.authenticated:
                st.success("✅ Authenticated")
                if st.button("🚪 Logout from GitLab"):
                    st.session_state.authenticated = False
                    st.session_state.access_token = None
                    st.rerun()
            else:
                st.error("❌ Not authenticated")
            
            st.markdown("---")
            
            model = st.selectbox("🤖 Model", ["gpt-3.5-turbo", "gpt-4o"], index=0)
            
            st.success(f"✅ GitLab: {len(self.config.gitlab.project_ids)} projects")
            st.success("✅ OpenAI configured")
            
            if st.button("🔍 Test MCP Connection"):
                with st.spinner("Testing MCP connection..."):
                    health_result = asyncio.run(self.mcp_client.health_check())
                    if health_result.get("success"):
                        st.success("✅ MCP Server connected")
                        if health_result.get("gitlab_connection"):
                            st.success("✅ GitLab connection healthy")
                    else:
                        st.error(f"❌ MCP Server: {health_result.get('error', 'Connection failed')}")
            
            st.markdown("---")
            
            self.render_token_usage(model)
            
            st.markdown("---")
            
            self.render_quick_filters()
            
            st.markdown("---")
            
            server_url = os.getenv("MCP_SERVER_URL")
            if server_url:
                st.info(f"🌐 Remote server: {server_url}")
            else:
                st.info("🖥️ Local server connection")
            
            with st.expander("📋 Configured Projects"):
                for project_id in self.config.gitlab.project_ids:
                    st.code(project_id)
            
            return model
        
    def render_mcp_results(self, mcp_result: Dict[str, Any]):
        """Render MCP tool results."""
        if mcp_result.get("summary"):
            st.markdown(mcp_result["summary"])

        if mcp_result.get("table_data"):
            st.markdown("### Issues Table")
            df = pd.DataFrame(mcp_result["table_data"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        
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
    
    def process_pending_query(self, model: str):
        """Process any pending query from quick filters."""
        if st.session_state.get("pending_query"):
            query = st.session_state.pending_query
            st.session_state.pending_query = None  # Clear the pending query
            
            st.session_state.messages.append({"role": "user", "content": query})
            
            with st.spinner("Processing quick query..."):
                response = asyncio.run(self.process_message(query, model))
                
                tokens_used = response.get("tokens_used", 0)
                cost = self.calculate_cost(tokens_used, model)
                st.session_state.total_tokens_used += tokens_used
                st.session_state.session_cost += cost
                

                assistant_content = response["content"]
                if response["type"] == "mcp_response" and response.get("mcp_result"):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": assistant_content,
                        "mcp_result": response["mcp_result"],
                        "tokens_used": tokens_used,
                        "cost": cost
                    })
                else:
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": assistant_content,
                        "tokens_used": tokens_used,
                        "cost": cost
                    })
    
    def run(self):
        """Run the Streamlit application."""
        st.set_page_config(
            page_title="GitLab Issues Assistant (Professional)",
            page_icon="🦊",
            layout="wide"
        )
        
        st.title("🦊 GitLab Issues Assistant")
        st.markdown("Professional FastMCP-powered GitLab issues management")
        
        if self.gitlab_token:
            try:
                headers = {'Authorization': f'Bearer {self.gitlab_token}'}
                response = requests.get(f"{GITLAB_URL}/api/v4/user", headers=headers)
                if response.status_code == 200:
                    user_info = response.json()
                    st.success(f"👋 Welcome, {user_info.get('name', 'User')}! Connected to {GITLAB_URL}")
            except:
                pass 
        
        model = self.render_sidebar()
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        self.process_pending_query(model)
        
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                if message.get("mcp_result"):
                    self.render_mcp_results(message["mcp_result"])
                
                if message.get("tokens_used"):
                    st.info(f"🔢 Tokens used: {message['tokens_used']:,} | Cost: ${message.get('cost', 0):.4f}")
        
        if prompt := st.chat_input("Ask about GitLab issues..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Processing..."):
                    response = asyncio.run(self.process_message(prompt, model))
                    
                    tokens_used = response.get("tokens_used", 0)
                    cost = self.calculate_cost(tokens_used, model)
                    st.session_state.total_tokens_used += tokens_used
                    st.session_state.session_cost += cost
                    
                    if response["type"] == "error":
                        st.error(response["content"])
                    elif response["type"] == "mcp_response":
                        st.markdown(response["content"])
                        self.render_mcp_results(response["mcp_result"])
                    else:
                        st.markdown(response["content"])
                    
                    st.info(f"🔢 Tokens used: {tokens_used:,} | Cost: ${cost:.4f}")
            
            assistant_content = response["content"]
            if response["type"] == "mcp_response" and response.get("mcp_result"):
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                    "mcp_result": response["mcp_result"],
                    "tokens_used": tokens_used,
                    "cost": cost
                })
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                    "tokens_used": tokens_used,
                    "cost": cost
                })