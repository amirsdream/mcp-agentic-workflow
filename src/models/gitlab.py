from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from langchain_core.pydantic_v1 import BaseModel, Field
from typing_extensions import TypedDict


class GitLabIssueFilter(BaseModel):
    """Input model for GitLab issue filtering"""
    month: Optional[str] = Field(None, description="Month filter like 'January', 'Feb 2024', 'this month', 'last month'")
    year: Optional[str] = Field(None, description="Year filter like '2024', 'this year', 'last year'")
    state: str = Field("opened", description="Issue state: 'opened', 'closed', or 'all'")
    labels: Optional[str] = Field(None, description="Comma-separated labels to filter by")
    assignee: Optional[str] = Field(None, description="Filter by assignee name")
    limit: int = Field(100, description="Maximum number of issues to return")


class AgentState(TypedDict):
    """State definition for the agent workflow"""
    messages: List[Dict[str, Any]]
    user_query: str
    gitlab_response: Optional[Dict[str, Any]]
    needs_gitlab_tool: bool
    final_response: str
    tokens_used: int
    gitlab_filters: Optional[Dict[str, Any]]
    user_intent: Optional[str]


@dataclass
class GitLabIssue:
    """GitLab issue data model"""
    iid: int
    title: str
    description: str
    state: str
    author: str
    assignee: Optional[str]
    labels: List[str]
    created_date: str
    updated_date: str
    web_url: str
    project_name: str
    priority: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'iid': self.iid,
            'title': self.title,
            'description': self.description,
            'state': self.state,
            'author': self.author,
            'assignee': self.assignee,
            'labels': self.labels,
            'created_date': self.created_date,
            'updated_date': self.updated_date,
            'web_url': self.web_url,
            'project_name': self.project_name,
            'priority': self.priority
        }


@dataclass
class AgentResponse:
    """Response from agent processing"""
    type: str  # 'success', 'error', 'clarification', 'agent_response'
    content: str
    data: Optional[Dict[str, Any]] = None
    gitlab_response: Optional[Dict[str, Any]] = None
    tokens_used: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'type': self.type,
            'content': self.content,
            'data': self.data,
            'gitlab_response': self.gitlab_response,
            'tokens_used': self.tokens_used
        }


@dataclass
class ChatMessage:
    """Chat message model"""
    role: str  # 'user', 'assistant'
    content: str
    gitlab_response: Optional[Dict[str, Any]] = None
    tokens_used: int = 0
    cost: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session state"""
        return {
            'role': self.role,
            'content': self.content,
            'gitlab_response': self.gitlab_response,
            'tokens_used': self.tokens_used,
            'cost': self.cost
        }


class AgentConfig:
    """Configuration for agent behavior"""
    
    DEFAULT_FILTERS = {
        "state": "opened",
        "limit": 100
    }
    
    LABEL_KEYWORDS = {
        "bug": "bug",
        "feature": "feature,enhancement",
        "enhancement": "enhancement",
        "high priority": "high-priority",
        "critical": "critical",
        "documentation": "documentation"
    }
    
    GITLAB_KEYWORDS = [
        'issue', 'bug', 'feature', 'enhancement', 
        'show', 'list', 'get', 'find', 'gitlab'
    ]
    
    MONTHS = [
        "january", "february", "march", "april", 
        "may", "june", "july", "august", 
        "september", "october", "november", "december"
    ]
    
    PRICING = {
        "gpt-3.5-turbo": 0.002 / 1000,
        "gpt-4o": 0.03 / 1000,
        "gpt-4": 0.03 / 1000,
    }