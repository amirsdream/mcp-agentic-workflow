"""
Streamlit UI for GitLab Multi-Agent Assistant
"""

import streamlit as st
import asyncio
import pandas as pd
from typing import Dict, Any
import os

from ..config.settings import AppConfig
from ..services.agents import AgentOrchestrator
from ..services.workflow import WorkflowService
from ..services.tools import ToolsService
from ..models.gitlab import ChatMessage, AgentConfig


class GitLabIssuesApp:
    """Main Streamlit application with multi-agent architecture"""
    
    def __init__(self):
        self.config = self._load_config()
        
        # Initialize services
        self.orchestrator = AgentOrchestrator(self.config)
        self.workflow_service = WorkflowService(self.orchestrator)
        self.tools_service = ToolsService(
            self.orchestrator.openai_client, 
            self.orchestrator.mcp_client
        )
        
        # Initialize session state
        self._initialize_session_state()
    
    def _load_config(self) -> AppConfig:
        """Load application configuration."""
        try:
            return AppConfig.from_env()
        except ValueError as e:
            st.error(f"Configuration error: {e}")
            st.stop()
    
    def _initialize_session_state(self):
        """Initialize Streamlit session state"""
        if "total_tokens_used" not in st.session_state:
            st.session_state.total_tokens_used = 0
        if "session_cost" not in st.session_state:
            st.session_state.session_cost = 0.0
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "pending_query" not in st.session_state:
            st.session_state.pending_query = None

    # ========================================================================
    # MESSAGE PROCESSING
    # ========================================================================
    
    async def process_message(self, user_message: str, model: str) -> Dict[str, Any]:
        """Process user message through multi-agent system or tools"""
        try:
            # Detect if this is a GitLab-related query
            if self._is_gitlab_query(user_message):
                # Try workflow first
                try:
                    print(f"Processing GitLab query: {user_message}")
                    return await self.workflow_service.process_workflow(user_message)
                except Exception as workflow_error:
                    # Fallback to tools
                    print(f"Workflow processing failed: {workflow_error}")
                    return await self.tools_service.process_with_tools(user_message, model)
            else:
                # Use direct tool calling for non-GitLab queries
                return await self.tools_service.process_with_tools(user_message, model)
            
        except Exception as e:
            return {
                "type": "error",
                "content": f"Error processing request: {str(e)}",
                "tokens_used": 0
            }
    
    def _is_gitlab_query(self, message: str) -> bool:
        """Check if message is GitLab-related"""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in AgentConfig.GITLAB_KEYWORDS)
    
    def calculate_cost(self, tokens: int, model: str) -> float:
        """Calculate approximate cost based on tokens and model."""
        return tokens * AgentConfig.PRICING.get(model, 0.002 / 1000)

    # ========================================================================
    # UI COMPONENTS
    # ========================================================================
    
    def render_quick_filters(self):
        """Render quick filter buttons"""
        st.subheader("🚀 Quick Actions")
        
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
        
        # Agent status
        st.markdown("---")
        st.markdown("**🤖 Agent Status:**")
        st.success("✅ User Proxy Agent: Active")
        st.success("✅ GitLab Agent: Connected")
        
        # Example queries
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
        """Render token usage and cost tracking"""
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
        """Render application sidebar"""
        with st.sidebar:
            st.header("⚙️ Multi-Agent Configuration")
            
            model = st.selectbox("🤖 Model", ["gpt-3.5-turbo", "gpt-4o"], index=1)
            
            st.markdown("**🔗 Agent Connections:**")
            st.success(f"✅ GitLab: {len(self.config.gitlab.project_ids)} projects")
            st.success("✅ OpenAI configured")
            st.success("✅ User Proxy Agent ready")
            st.success("✅ GitLab Agent ready")
            
            if st.button("🔍 Test All Connections"):
                with st.spinner("Testing connections..."):
                    health_result = asyncio.run(self.orchestrator.health_check())
                    
                    if health_result.get("overall_status") == "healthy":
                        st.success("✅ All systems operational")
                    else:
                        st.error(f"❌ System status: {health_result.get('overall_status')}")
                        if health_result.get("error"):
                            st.error(f"Error: {health_result['error']}")
            
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
            
            with st.expander("🔧 Agent Architecture"):
                st.markdown("""
                **User Proxy Agent:**
                - Handles human interaction
                - Analyzes user queries
                - Manages conversation flow
                
                **GitLab Agent:**
                - Executes GitLab operations
                - Manages tool interactions
                - Processes GitLab data
                
                **Workflow:**
                User → Proxy → GitLab Agent → Response
                """)
            
            return model
    
    def render_gitlab_results(self, gitlab_response: Dict[str, Any]):
        """Render GitLab results"""
        if not gitlab_response:
            return
            
        # Handle both direct gitlab_response and nested data structure
        data = gitlab_response.get("data", gitlab_response) if gitlab_response.get("success") else gitlab_response
        
        if data.get("table_data"):
            st.markdown("### 📋 Issues Table")
            df = pd.DataFrame(data["table_data"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        if data.get("issues"):
            st.markdown("### 📝 Issue Details")
            for issue in data["issues"][:5]:  # Show first 5
                with st.expander(f"#{issue['iid']} - {issue['title']}", expanded=False):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Project:** {issue['project_name']}")
                        st.write(f"**Author:** {issue['author']}")
                        if issue.get('assignee'):
                            st.write(f"**Assignee:** {issue['assignee']}")
                        if issue.get('description'):
                            st.write(f"**Description:** {issue['description']}")
                    
                    with col2:
                        state_color = "🟢" if issue['state'] == 'opened' else "🔴"
                        st.write(f"**State:** {state_color} {issue['state']}")
                        st.write(f"**Created:** {issue['created_date']}")
                        st.write(f"**Priority:** {issue.get('priority', 'normal')}")
                        
                        if issue.get('labels'):
                            st.write("**Labels:**")
                            for label in issue['labels'][:3]:
                                st.badge(label)
                        
                        st.markdown(f"[🔗 View in GitLab]({issue['web_url']})")
    
    def process_pending_query(self, model: str):
        """Process any pending query from quick filters"""
        if st.session_state.get("pending_query"):
            query = st.session_state.pending_query
            st.session_state.pending_query = None
            
            st.session_state.messages.append({"role": "user", "content": query})
            
            with st.spinner("🤖 Agents processing query..."):
                response = asyncio.run(self.process_message(query, model))
                
                tokens_used = response.get("tokens_used", 0)
                cost = self.calculate_cost(tokens_used, model)
                st.session_state.total_tokens_used += tokens_used
                st.session_state.session_cost += cost
                
                # Create chat message
                chat_message = ChatMessage(
                    role="assistant",
                    content=response["content"],
                    gitlab_response=response.get("gitlab_response") or response.get("mcp_result"),
                    tokens_used=tokens_used,
                    cost=cost
                )
                
                st.session_state.messages.append(chat_message.to_dict())

    # ========================================================================
    # MAIN APP RUNNER
    # ========================================================================
    
    def run(self):
        """Run the Streamlit application"""
        st.set_page_config(
            page_title="GitLab Multi-Agent Assistant",
            page_icon="🤖",
            layout="wide"
        )
        
        st.title("🤖 GitLab Multi-Agent Assistant")
        st.markdown("**User Proxy Agent** + **GitLab Agent** powered by LangGraph")
        
        model = self.render_sidebar()
        
        # Process any pending queries
        self.process_pending_query(model)
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                if message.get("gitlab_response"):
                    self.render_gitlab_results(message["gitlab_response"])
                
                if message.get("tokens_used"):
                    st.info(f"🔢 Tokens used: {message['tokens_used']:,} | Cost: ${message.get('cost', 0):.4f}")
        
        # Chat input
        if prompt := st.chat_input("Ask about GitLab issues..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("🤖 Multi-agent processing..."):
                    response = asyncio.run(self.process_message(prompt, model))
                    
                    tokens_used = response.get("tokens_used", 0)
                    cost = self.calculate_cost(tokens_used, model)
                    st.session_state.total_tokens_used += tokens_used
                    st.session_state.session_cost += cost
                    
                    if response["type"] == "error":
                        st.error(response["content"])
                    elif response["type"] in ["mcp_response", "workflow_response"]:
                        st.markdown(response["content"])
                        
                        # Handle both response types for GitLab data
                        gitlab_data = response.get("gitlab_response") or response.get("mcp_result")
                        if gitlab_data:
                            self.render_gitlab_results(gitlab_data)
                    else:
                        st.markdown(response["content"])
                    
                    st.info(f"🔢 Tokens used: {tokens_used:,} | Cost: ${cost:.4f}")
            
            # Store the response
            chat_message = ChatMessage(
                role="assistant",
                content=response["content"],
                gitlab_response=response.get("gitlab_response") or response.get("mcp_result"),
                tokens_used=tokens_used,
                cost=cost
            )
            
            st.session_state.messages.append(chat_message.to_dict())


if __name__ == "__main__":
    app = GitLabIssuesApp()
    app.run()