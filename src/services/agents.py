import json
import asyncio
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from openai import AsyncOpenAI
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field

from ..models.gitlab import GitLabIssueFilter, AgentState
from ..core.mcp_client import MCPClientManager
from ..config.settings import AppConfig


class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def process(self, *args, **kwargs) -> Dict[str, Any]:
        """Process agent-specific logic"""
        pass


class GitLabAgent(BaseAgent):
    """Specialized agent for GitLab operations"""
    
    def __init__(self, mcp_client: MCPClientManager):
        super().__init__("GitLabAgent")
        self.mcp_client = mcp_client
        
    async def list_gitlab_issues(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """List GitLab issues with filtering options"""
        try:
            # Filter out None values and ensure proper format
            clean_filters = {k: v for k, v in filters.items() if v is not None}
            result = await self.mcp_client.call_tool("list_gitlab_issues", clean_filters)
            return {
                "success": True,
                "data": result,
                "message": "Successfully retrieved GitLab issues"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error retrieving GitLab issues: {str(e)}"
            }
    
    async def process(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Process GitLab operations"""
        return await self.list_gitlab_issues(filters)
    
    def get_tools(self):
        """Get all available tools for this agent"""
        # Return LangChain tools with proper schema
        @tool
        async def gitlab_issues_tool(
            month: str = None,
            year: str = None, 
            state: str = "opened",
            labels: str = None,
            assignee: str = None,
            limit: int = 100
        ) -> Dict[str, Any]:
            """List GitLab issues with filtering options.
            
            Args:
                month: Month filter like 'January', 'Feb 2024', 'this month', 'last month'
                year: Year filter like '2024', 'this year', 'last year'
                state: Issue state - 'opened', 'closed', or 'all'
                labels: Comma-separated labels to filter by
                assignee: Filter by assignee name
                limit: Maximum number of issues to return
            """
            filters = {
                "month": month,
                "year": year,
                "state": state,
                "labels": labels,
                "assignee": assignee,
                "limit": limit
            }
            return await self.list_gitlab_issues(filters)
        
        return [gitlab_issues_tool]


class UserProxyAgent(BaseAgent):
    """User-facing agent that handles human interaction"""
    
    def __init__(self, openai_client: AsyncOpenAI, gitlab_agent: GitLabAgent):
        super().__init__("UserProxyAgent")
        self.openai_client = openai_client
        self.gitlab_agent = gitlab_agent
        
    def create_system_message(self) -> str:
        return """You are a helpful User Proxy Agent that assists users with GitLab issues management.

Your role is to:
1. Understand user queries about GitLab issues
2. Determine when GitLab operations are needed
3. Communicate with the GitLab agent to perform operations
4. Present results in a user-friendly format

When users ask about GitLab issues, analyze their request and determine:
- What specific information they need
- What filters should be applied (month, year, state, labels, assignee, etc.)
- How to present the results clearly

Common query patterns:
- "show me issues" → ask for month specification or use current month
- "January bugs" → filter by month="January" and labels="bug"
- "this month high priority" → filter by month="this month" and labels="high-priority"
- "closed issues last month" → filter by month="last month" and state="closed"

Always be helpful, concise, and ask clarifying questions when needed."""

    async def analyze_user_query(self, query: str) -> Dict[str, Any]:
        """Analyze user query to determine intent and required actions"""
        try:
            # Simple keyword-based analysis for reliability
            query_lower = query.lower()
            
            # Check if this is a GitLab-related query
            gitlab_keywords = ['issue', 'bug', 'feature', 'enhancement', 'show', 'list', 'get', 'find', 'gitlab']
            needs_gitlab = any(keyword in query_lower for keyword in gitlab_keywords)
            
            if not needs_gitlab:
                return {
                    "needs_gitlab_tool": False,
                    "filters": {},
                    "intent": "non-gitlab query",
                    "clarification_needed": "I can help you with GitLab issues. Please ask about issues, bugs, or features."
                }
            
            # Extract filters using pattern matching
            filters = self._extract_filters_from_query(query_lower)
            
            # Determine intent
            intent = "list issues"
            if "summary" in query_lower or "statistics" in query_lower or "breakdown" in query_lower:
                intent = "summary"
            
            return {
                "needs_gitlab_tool": True,
                "filters": filters,
                "intent": intent,
                "clarification_needed": None
            }
            
        except Exception as e:
            return {
                "needs_gitlab_tool": False,
                "filters": {},
                "intent": "error in analysis",
                "clarification_needed": f"I had trouble understanding your request: {str(e)}"
            }
    
    def _extract_filters_from_query(self, query_lower: str) -> Dict[str, Any]:
        """Extract filters from user query using pattern matching"""
        filters = {
            "state": "opened",  # default
            "limit": 100
        }
        
        # Extract month
        if "this month" in query_lower:
            filters["month"] = "this month"
        elif "last month" in query_lower:
            filters["month"] = "last month"
        elif any(month in query_lower for month in ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]):
            months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
            for month in months:
                if month in query_lower:
                    filters["month"] = month.title()
                    break
        
        # Extract state
        if "closed" in query_lower:
            filters["state"] = "closed"
        elif "all" in query_lower:
            filters["state"] = "all"
        
        # Extract labels
        label_keywords = {
            "bug": "bug",
            "feature": "feature,enhancement",
            "enhancement": "enhancement",
            "high priority": "high-priority",
            "critical": "critical",
            "documentation": "documentation"
        }
        
        for keyword, label in label_keywords.items():
            if keyword in query_lower:
                filters["labels"] = label
                break
        
        # Extract assignee
        if "my issues" in query_lower or "assigned to me" in query_lower:
            filters["assignee"] = "me"
        
        return filters
    
    async def process(self, query: str) -> Dict[str, Any]:
        """Process user query and return analysis"""
        return await self.analyze_user_query(query)


class AgentOrchestrator:
    """Orchestrates communication between agents"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.openai_client = AsyncOpenAI(api_key=config.openai.api_key)
        self.mcp_client = MCPClientManager(config)
        
        # Initialize agents
        self.gitlab_agent = GitLabAgent(self.mcp_client)
        self.user_proxy = UserProxyAgent(self.openai_client, self.gitlab_agent)
        
    async def process_user_request(self, user_message: str) -> Dict[str, Any]:
        """Process user request through the agent pipeline"""
        try:
            # Step 1: User proxy analyzes the query
            analysis = await self.user_proxy.process(user_message)
            
            if analysis.get("clarification_needed"):
                return {
                    "type": "clarification",
                    "content": analysis["clarification_needed"],
                    "tokens_used": 50  # Estimate
                }
            
            if not analysis.get("needs_gitlab_tool"):
                return {
                    "type": "text",
                    "content": "I can help you with GitLab issues. Please specify what you'd like to see.",
                    "tokens_used": 25
                }
            
            # Step 2: GitLab agent processes the request
            filters = analysis.get("filters", {})
            # Ensure filters have default values to avoid missing field errors
            clean_filters = {
                "month": filters.get("month"),
                "year": filters.get("year"),
                "state": filters.get("state", "opened"),
                "labels": filters.get("labels"),
                "assignee": filters.get("assignee"),
                "limit": filters.get("limit", 100)
            }
            
            gitlab_result = await self.gitlab_agent.process(clean_filters)
            
            # Step 3: Format response based on user intent
            intent = analysis.get("intent", "list")
            formatted_response = self._format_response(gitlab_result, intent)
            
            return {
                "type": "agent_response",
                "content": formatted_response,
                "gitlab_response": gitlab_result,
                "tokens_used": 200  # Estimate
            }
            
        except Exception as e:
            return {
                "type": "error",
                "content": f"Error processing request: {str(e)}",
                "tokens_used": 0
            }
    
    def _format_response(self, gitlab_result: Dict[str, Any], intent: str) -> str:
        """Format the response based on user intent"""
        if not gitlab_result or not gitlab_result.get("success"):
            error_msg = gitlab_result.get("error", "Unknown error") if gitlab_result else "No response from GitLab"
            return f"❌ Error retrieving GitLab issues: {error_msg}"
        
        data = gitlab_result.get("data", {})
        issues = data.get("issues", [])
        
        if not issues:
            return "No issues match your criteria."
        
        if intent == "summary":
            return f"""📊 **GitLab Issues Summary**

{data.get('summary', 'Issues found')}

**Total Issues Found:** {len(issues)}

Use the table below to explore the detailed results."""
        else:
            return f"""✅ **Found {len(issues)} GitLab issues**

{data.get('summary', 'Here are the matching issues:')}

📋 **Details available in the table and expandable sections below.**"""
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all agents and connections"""
        try:
            mcp_health = await self.mcp_client.health_check()
            
            return {
                "user_proxy_agent": "healthy",
                "gitlab_agent": "healthy",
                "mcp_connection": mcp_health.get("success", False),
                "gitlab_connection": mcp_health.get("gitlab_connection", False),
                "openai_client": hasattr(self, 'openai_client'),
                "overall_status": "healthy" if mcp_health.get("success") else "degraded"
            }
        except Exception as e:
            return {
                "user_proxy_agent": "error",
                "gitlab_agent": "error", 
                "error": str(e),
                "overall_status": "unhealthy"
            }