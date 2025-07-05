from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class GitLabIssue:
    """GitLab issue model."""
    project_id: str
    project_name: str
    iid: int
    title: str
    description: str
    state: str
    author: str
    assignee: Optional[str]
    labels: List[str]
    created_at: datetime
    updated_at: datetime
    web_url: str
    
    @property
    def created_date(self) -> str:
        """Get formatted creation date."""
        return self.created_at.strftime("%Y-%m-%d")
    
    @property
    def priority(self) -> str:
        """Extract priority from labels."""
        priority_labels = ['critical', 'high', 'medium', 'low', 'urgent', 
                          'priority-high', 'priority-medium', 'priority-low']
        for label in self.labels:
            if any(p in label.lower() for p in priority_labels):
                return label
        return 'normal'
    
    def to_dict(self) -> dict:
        """Convert issue to dictionary."""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "iid": self.iid,
            "title": self.title,
            "description": self.description,
            "state": self.state,
            "author": self.author,
            "assignee": self.assignee,
            "labels": self.labels,
            "created_date": self.created_date,
            "priority": self.priority,
            "web_url": self.web_url
        }

@dataclass
class IssueFilters:
    """Issue filtering parameters."""
    month: Optional[str] = None
    state: str = "opened"
    labels: Optional[str] = None
    assignee: Optional[str] = None
    limit: int = 100

@dataclass
class IssueSearchResult:
    """Result of issue search."""
    success: bool
    total_issues: int
    issues: List[GitLabIssue]
    project_names: List[str]
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "total_issues": self.total_issues,
            "issues": [issue.to_dict() for issue in self.issues],
            "project_names": self.project_names,
            "error": self.error
        }