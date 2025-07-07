import streamlit as st
import asyncio
import json
import pandas as pd
from typing import Dict, Any, Optional
import os 
from datetime import datetime, timedelta
import requests
import urllib.parse
import secrets
import time

from openai import AsyncOpenAI
from ..config.settings import AppConfig
from ..core.mcp_client import MCPClientManager


class GitLabEventsApp:
    """Streamlit application for GitLab events processing with LLM integration."""
    
    def __init__(self):
        # Load config first
        self.config = self._load_config()
        
        # Initialize session state for auth
        self._init_session_state()
        
        # Handle GitLab authentication
        self.gitlab_token = self._handle_gitlab_auth()
        
        # Only initialize other components if authenticated
        if self.gitlab_token:
            self.openai_client = AsyncOpenAI(api_key=self.config.openai.api_key)
            self.mcp_client = MCPClientManager(self.config, user_token=self.gitlab_token)
    
    def _load_config(self) -> AppConfig:
        """Load application configuration."""
        try:
            return AppConfig.from_env()
        except ValueError as e:
            st.error(f"Configuration error: {e}")
            st.stop()
    
    def _init_session_state(self):
        """Initialize session state variables."""
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'access_token' not in st.session_state:
            st.session_state.access_token = None
        if 'current_user_id' not in st.session_state:
            st.session_state.current_user_id = None
        if "total_tokens_used" not in st.session_state:
            st.session_state.total_tokens_used = 0
        if "session_cost" not in st.session_state:
            st.session_state.session_cost = 0.0
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "pending_query" not in st.session_state:
            st.session_state.pending_query = None
        if "timed_messages" not in st.session_state:
            st.session_state.timed_messages = []
    
    def _handle_gitlab_auth(self) -> Optional[str]:
        """Handle GitLab OAuth2 authentication flow."""
        # Check for OAuth callback (code parameter)
        query_params = st.query_params
        if 'code' in query_params and not st.session_state.authenticated:
            return self._complete_oauth_flow(query_params['code'])
        
        # Main authentication logic
        if st.session_state.authenticated:
            return st.session_state.access_token
        else:
            self._show_login_page()
            return None
    
    def _complete_oauth_flow(self, code: str) -> Optional[str]:
        """Complete the OAuth2 flow with the authorization code."""
        with st.spinner("🔄 Completing authentication..."):
            token_data = {
                'client_id': self.config.gitlab.client_id,
                'client_secret': self.config.gitlab.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': self.config.gitlab.redirect_uri
            }
            
            try:
                response = requests.post(f"{self.config.gitlab.url}/oauth/token", data=token_data)
                if response.status_code == 200:
                    token_info = response.json()
                    st.session_state.access_token = token_info['access_token']
                    st.session_state.authenticated = True
                    
                    # Clear URL parameters
                    st.query_params.clear()
                    self._show_timed_message("✅ Authentication successful!", "success", 3)
                    st.rerun()
                    return token_info['access_token']
                else:
                    self._show_timed_message(f"❌ Token exchange failed: {response.status_code}", "error", 5)
                    return None
            except Exception as e:
                self._show_timed_message(f"❌ Authentication failed: {e}", "error", 5)
                return None
    
    def _show_login_page(self):
        """Show the GitLab login page."""
        st.warning("Please authenticate with GitLab to continue")
        
        if st.button("🔑 Login with GitLab"):
            state = secrets.token_urlsafe(16)
            auth_url = (
                f"{self.config.gitlab.url}/oauth/authorize?"
                f"client_id={self.config.gitlab.client_id}&"
                f"redirect_uri={self.config.gitlab.redirect_uri}&"
                f"response_type=code&"
                f"scope=read_api read_user&"
                f"state={state}"
            )
            
            # Simple redirect to GitLab
            st.markdown(f'<meta http-equiv="refresh" content="0; url={auth_url}">', unsafe_allow_html=True)
        
        st.stop()  # Stop execution until authenticated
    
    def _logout(self):
        """Handle user logout."""
        st.session_state.authenticated = False
        st.session_state.access_token = None
        st.session_state.current_user_id = None  # Clear user ID
        st.session_state.messages = []  # Clear chat history
        st.rerun()
    
    def _show_timed_message(self, message: str, message_type: str = "success", duration: int = 3):
        """Show a message that automatically disappears after specified duration."""
        message_id = f"{message_type}_{len(st.session_state.timed_messages)}"
        message_data = {
            "id": message_id,
            "message": message,
            "type": message_type,
            "timestamp": time.time(),
            "duration": duration
        }
        st.session_state.timed_messages.append(message_data)
        
        # Display the message
        if message_type == "success":
            st.success(message)
        elif message_type == "error":
            st.error(message)
        elif message_type == "warning":
            st.warning(message)
        elif message_type == "info":
            st.info(message)
        
        # Schedule removal
        self._schedule_message_removal(message_id, duration)
    
    def _schedule_message_removal(self, message_id: str, duration: int):
        """Schedule automatic removal of timed message."""
        # Use JavaScript to auto-refresh after duration
        st.markdown(f"""
        <script>
        setTimeout(function() {{
            window.location.reload();
        }}, {duration * 1000});
        </script>
        """, unsafe_allow_html=True)
    
    def _cleanup_expired_messages(self):
        """Remove expired timed messages."""
        current_time = time.time()
        st.session_state.timed_messages = [
            msg for msg in st.session_state.timed_messages
            if current_time - msg["timestamp"] < msg["duration"]
        ]
    
    def _get_current_user_info(self) -> Optional[Dict[str, Any]]:
        """Get current user information from GitLab."""
        if not self.gitlab_token:
            return None
        
        try:
            headers = {'Authorization': f'Bearer {self.gitlab_token}'}
            response = requests.get(f"{self.config.gitlab.url}/api/v4/user", headers=headers)
            if response.status_code == 200:
                user_data = response.json()
                # Store user ID in session state for tool calls
                st.session_state.current_user_id = str(user_data.get('id'))
                return user_data
        except Exception:
            pass  # Silently handle API errors
        return None
    
    def calculate_cost(self, tokens: int, model: str) -> float:
        """Calculate approximate cost based on tokens and model."""
        pricing = {
            "gpt-3.5-turbo": 0.002 / 1000, 
            "gpt-4o": 0.03 / 1000,         
            "gpt-4": 0.03 / 1000,
        }
        return tokens * pricing.get(model, 0.002 / 1000)
    
    async def process_message(self, user_message: str, model: str) -> Dict[str, Any]:
        """Process user message using new event-based tools."""
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_user_events",
                    "description": "Get GitLab events for current user with filtering, classification, and LLM summarization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "month": {
                                "type": "string",
                                "description": "Month filter like 'January', 'Feb 2024', 'this month', 'last month'"
                            },
                            "year": {
                                "type": "string",
                                "description": "Year filter like '2024', 'this year', 'last year'"
                            },
                            "event_types": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by event types: 'pushed', 'merged', 'committed', etc."
                            },
                            "project_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by specific project IDs"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of events to process",
                                "default": 200
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "classify_work_events",
                    "description": "Classify user's GitLab events into work categories with detailed analysis.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "month": {
                                "type": "string",
                                "description": "Month filter like 'January', 'this month', 'last month'"
                            },
                            "project_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by specific project IDs"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_work_summaries",
                    "description": "Get LLM-generated work summaries with time estimations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "month": {
                                "type": "string",
                                "description": "Month filter like 'January', 'this month', 'last month'"
                            },
                            "work_type": {
                                "type": "string",
                                "description": "Filter by work type: 'feature', 'bugfix', 'documentation', etc."
                            },
                            "min_hours": {
                                "type": "number",
                                "description": "Minimum hours threshold for filtering work items"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_productivity",
                    "description": "Analyze productivity metrics from GitLab events and work summaries.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "month": {
                                "type": "string",
                                "description": "Month filter like 'January', 'this month', 'last month'"
                            },
                            "compare_previous": {
                                "type": "boolean",
                                "description": "Whether to compare with previous period",
                                "default": False
                            }
                        }
                    }
                }
            }
        ]
        
        system_message = {
            "role": "system",
            "content": """You are an AI assistant that helps users analyze their GitLab development activity.

You can help users with:
- Analyzing their GitLab events (commits, pushes, merges) for any time period
- Classifying work into categories (features, bugfixes, documentation, etc.)
- Getting AI-generated summaries of work with time estimations
- Productivity analysis and insights

When users ask about their activity WITHOUT specifying a month, ask them which time period they want to analyze.
When users mention a specific time period, use the appropriate tool with the month parameter.

Examples:
- "show me my activity" → ask for time period specification
- "January work summary" → use get_work_summaries with month="January"
- "this month commits" → use get_user_events with month="this month"
- "analyze my productivity last month" → use analyze_productivity with month="last month"
- "classify my work this month" → use classify_work_events with month="this month"
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
                tool_name = tool_call.function.name
                if tool_name in ["get_user_events", "classify_work_events", "get_work_summaries", "analyze_productivity"]:
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        mcp_result = await self.mcp_client.call_tool(tool_name, arguments)
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
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
        """Render quick filter buttons for common event queries."""
        st.subheader("🚀 Quick Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📅 This Month Activity", use_container_width=True, key="btn_this_month"):
                st.session_state.pending_query = "show me my GitLab activity this month with work summaries"
                st.rerun()
            if st.button("🎯 Work Classification", use_container_width=True, key="btn_classify"):
                st.session_state.pending_query = "classify my work events this month by type"
                st.rerun()
            if st.button("⏱️ Time Analysis", use_container_width=True, key="btn_time"):
                st.session_state.pending_query = "analyze time spent on different work this month"
                st.rerun()
            if st.button("🔧 Feature Work Only", use_container_width=True, key="btn_features"):
                st.session_state.pending_query = "show me only feature work from this month"
                st.rerun()
        
        with col2:
            if st.button("📊 Productivity Analysis", use_container_width=True, key="btn_productivity"):
                st.session_state.pending_query = "analyze my productivity metrics this month"
                st.rerun()
            if st.button("🐛 Bug Fixes", use_container_width=True, key="btn_bugs"):
                st.session_state.pending_query = "show me bugfix work from this month with time estimates"
                st.rerun()
            if st.button("📈 Last Month Comparison", use_container_width=True, key="btn_last_month"):
                st.session_state.pending_query = "compare my activity this month vs last month"
                st.rerun()
            if st.button("📝 Work Summaries", use_container_width=True, key="btn_summaries"):
                st.session_state.pending_query = "get detailed work summaries for this month"
                st.rerun()
        
        # Custom quick queries
        st.markdown("**💡 Example Queries:**")
        examples = [
            "Show me all my commits from January with AI summaries",
            "What type of work did I do most this month?",
            "How many hours did I spend on features vs bugfixes?",
            "Analyze my merge request activity this month",
            "Show me work that took more than 5 hours"
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
            self._show_timed_message("📊 Usage stats reset", "info", 2)
            st.rerun()
        
        pricing_info = {
            "gpt-3.5-turbo": "$0.002/1K tokens",
            "gpt-4o": "$0.030/1K tokens",
            "gpt-4": "$0.030/1K tokens"
        }
        st.info(f"📋 Current model: {model} ({pricing_info.get(model, 'Pricing unknown')})")
    
    def render_sidebar(self):
        """Render application sidebar with connection status and controls."""
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # GitLab Authentication Status
            st.markdown("**🔐 GitLab Authentication:**")
            if st.session_state.authenticated:
                user_info = self._get_current_user_info()
                if user_info:
                    st.success(f"✅ Authenticated as {user_info.get('name', 'User')}")
                else:
                    st.success("✅ Authenticated")
                
                if st.button("🚪 Logout from GitLab"):
                    self._logout()
            else:
                st.error("❌ Not authenticated")
            
            st.markdown("---")
            
            model = st.selectbox("🤖 Model", ["gpt-3.5-turbo", "gpt-4o"], index=0)
            
            st.success("✅ GitLab Events API configured")
            st.success("✅ OpenAI LLM configured")
            
            if st.button("🔍 Test MCP Connection"):
                with st.spinner("Testing MCP connection..."):
                    health_result = asyncio.run(self.mcp_client.health_check())
                    if health_result.get("success"):
                        self._show_timed_message("✅ MCP Server connected", "success", 3)
                        if health_result.get("gitlab_connection"):
                            self._show_timed_message("✅ GitLab connection healthy", "success", 3)
                        if health_result.get("user_events_access"):
                            self._show_timed_message("✅ User events accessible", "success", 3)
                        if health_result.get("openai_connection"):
                            self._show_timed_message("✅ OpenAI LLM connected", "success", 3)
                        
                        # Show capabilities
                        capabilities = health_result.get("capabilities", {})
                        if capabilities.get("llm_summarization"):
                            self._show_timed_message("✅ AI Summarization available", "success", 3)
                        if capabilities.get("time_estimation"):
                            self._show_timed_message("✅ Time estimation available", "success", 3)
                    else:
                        self._show_timed_message(f"❌ MCP Server: {health_result.get('error', 'Connection failed')}", "error", 5)
            
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
            
            with st.expander("🎯 New Features"):
                st.markdown("""
                **Event Processing:**
                - 📊 GitLab events analysis
                - 🔄 Work classification
                - 🤖 AI-generated summaries
                - ⏱️ Time estimation
                - 📈 Productivity metrics
                """)
            
            return model
        
    def render_mcp_results(self, mcp_result: Dict[str, Any]):
        """Render MCP tool results for event-based data."""
        if mcp_result.get("summary"):
            st.markdown(mcp_result["summary"])

        # Render work summaries if available
        if mcp_result.get("summaries"):
            st.markdown("### 🤖 AI-Generated Work Summaries")
            for summary in mcp_result["summaries"][:10]:  # Limit display
                with st.expander(f"🎯 {summary['name']} ({summary['estimated_hours']}h)", expanded=False):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Description:** {summary['description']}")
                        st.write(f"**Work Type:** {summary['work_type'].title()}")
                        
                        if summary.get('key_achievements'):
                            st.write("**Key Achievements:**")
                            for achievement in summary['key_achievements']:
                                st.write(f"• {achievement}")
                        
                        if summary.get('technical_details'):
                            st.write("**Technical Details:**")
                            for detail in summary['technical_details']:
                                st.write(f"• {detail}")
                    
                    with col2:
                        st.metric("Estimated Hours", f"{summary['estimated_hours']:.1f}h")
                        st.metric("Confidence", f"{summary['confidence']:.0%}")

        # Render classifications if available
        if mcp_result.get("classifications"):
            st.markdown("### 📋 Work Classifications")
            
            # Create a summary table
            class_data = []
            for classification in mcp_result["classifications"][:15]:  # Limit display
                class_data.append({
                    "Work Type": classification['work_type'].title(),
                    "Branch": classification.get('branch_name', 'N/A'),
                    "Commits": classification['total_commits'],
                    "MR": f"#{classification['merge_request_id']}" if classification.get('merge_request_id') else "N/A",
                    "Confidence": f"{classification['confidence']:.0%}"
                })
            
            if class_data:
                df = pd.DataFrame(class_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

        # Render main table data
        if mcp_result.get("table_data"):
            st.markdown("### 📊 Activity Overview")
            df = pd.DataFrame(mcp_result["table_data"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Render productivity metrics if available
        if mcp_result.get("metrics"):
            st.markdown("### 📈 Productivity Metrics")
            metrics = mcp_result["metrics"]
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Events", metrics.get("total_events", 0))
                st.metric("Total Commits", metrics.get("total_commits", 0))
            
            with col2:
                st.metric("Work Hours", f"{metrics.get('total_work_hours', 0):.1f}h")
                st.metric("Projects", metrics.get("unique_projects", 0))
            
            with col3:
                st.metric("Merge Requests", metrics.get("merge_requests", 0))
                st.metric("Unique Branches", metrics.get("unique_branches", 0))
            
            with col4:
                st.metric("Avg Commits/Work", f"{metrics.get('avg_commits_per_work', 0):.1f}")
                st.metric("Avg Hours/Work", f"{metrics.get('avg_hours_per_work', 0):.1f}h")
        
        # Render work type breakdown
        if mcp_result.get("work_breakdown") or mcp_result.get("work_type_breakdown"):
            breakdown = mcp_result.get("work_breakdown") or mcp_result.get("work_type_breakdown")
            st.markdown("### 🎨 Work Type Breakdown")
            
            breakdown_data = []
            for work_type, data in breakdown.items():
                if isinstance(data, dict):
                    breakdown_data.append({
                        "Work Type": work_type.title(),
                        "Count": data.get("count", 0),
                        "Hours": f"{data.get('hours', 0):.1f}h" if 'hours' in data else "N/A"
                    })
                else:
                    breakdown_data.append({
                        "Work Type": work_type.title(),
                        "Count": data,
                        "Hours": "N/A"
                    })
            
            if breakdown_data:
                df = pd.DataFrame(breakdown_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Render insights if available
        if mcp_result.get("insights"):
            st.markdown("### 💡 Insights")
            for insight in mcp_result["insights"]:
                st.info(insight)
        
        # Show some raw events for context
        if mcp_result.get("events"):
            with st.expander("🔍 Recent Events Details", expanded=False):
                for event in mcp_result["events"][:5]:  # Show first 5
                    st.write(f"**{event['event_type'].title()}** - {event['project_name']}")
                    st.write(f"Date: {event['created_date']} | Commits: {event.get('commits_count', 0)}")
                    if event.get('branch_name'):
                        st.write(f"Branch: {event['branch_name']}")
                    st.write("---")
    
    def process_pending_query(self, model: str):
        """Process any pending query from quick filters."""
        if st.session_state.get("pending_query"):
            query = st.session_state.pending_query
            st.session_state.pending_query = None  # Clear the pending query
            
            st.session_state.messages.append({"role": "user", "content": query})
            
            with st.spinner("Processing activity analysis..."):
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
            page_title="GitLab Activity Analyzer (AI-Powered)",
            page_icon="🦊",
            layout="wide"
        )
        
        # Clean up expired messages
        self._cleanup_expired_messages()
        
        st.title("🦊 GitLab Activity Analyzer")
        st.markdown("AI-powered GitLab events processing with work classification and time estimation")
        
        # Show authenticated user info
        if self.gitlab_token:
            user_info = self._get_current_user_info()
            if user_info:
                st.success(f"👋 Welcome, {user_info.get('name', 'User')}! Analyzing your GitLab activity...")
        
        # Only proceed if authenticated
        if not self.gitlab_token:
            return
        
        model = self.render_sidebar()
        
        self.process_pending_query(model)
        
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                if message.get("mcp_result"):
                    self.render_mcp_results(message["mcp_result"])
                
                if message.get("tokens_used"):
                    st.info(f"🔢 Tokens used: {message['tokens_used']:,} | Cost: ${message.get('cost', 0):.4f}")
        
        if prompt := st.chat_input("Ask about your GitLab activity..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing your GitLab activity..."):
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