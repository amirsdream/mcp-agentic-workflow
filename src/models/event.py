from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class EventType(Enum):
    """GitLab event types."""
    PUSH = "pushed"
    MERGE = "merged"
    COMMIT = "committed"
    BRANCH_CREATE = "created_branch"
    BRANCH_DELETE = "deleted_branch"
    TAG_CREATE = "created_tag"
    ISSUE_CREATE = "opened_issue"
    ISSUE_CLOSE = "closed_issue"
    COMMENT = "commented"
    OTHER = "other"

class WorkType(Enum):
    """Classification of work types."""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    HOTFIX = "hotfix"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    MAINTENANCE = "maintenance"
    EXPERIMENT = "experiment"
    UNKNOWN = "unknown"

@dataclass
class GitLabCommit:
    """Individual commit data."""
    id: str
    title: str
    message: str
    author_name: str
    author_email: str
    created_at: datetime
    web_url: str
    project_id: str
    project_name: str
    
    @property
    def short_id(self) -> str:
        """Get short commit ID."""
        return self.id[:8]
    
    @property
    def clean_title(self) -> str:
        """Get clean commit title without prefixes."""
        # Remove common prefixes like "feat:", "fix:", etc.
        prefixes = ["feat:", "fix:", "docs:", "style:", "refactor:", "test:", "chore:"]
        title = self.title.strip()
        for prefix in prefixes:
            if title.lower().startswith(prefix):
                title = title[len(prefix):].strip()
                break
        return title

@dataclass
class GitLabEvent:
    """GitLab user event data."""
    id: int
    event_type: EventType
    created_at: datetime
    author_name: str
    project_id: str
    project_name: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_title: Optional[str] = None
    push_data: Optional[Dict[str, Any]] = None
    note_data: Optional[Dict[str, Any]] = None
    merge_request_id: Optional[int] = None
    branch_name: Optional[str] = None
    commits: List[GitLabCommit] = field(default_factory=list)
    
    @property
    def created_date(self) -> str:
        """Get formatted creation date."""
        return self.created_at.strftime("%Y-%m-%d")
    
    @property
    def is_merge_related(self) -> bool:
        """Check if event is related to merge request."""
        return self.merge_request_id is not None or (
            self.push_data and self.push_data.get("ref_type") == "branch"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "created_at": self.created_at.isoformat(),
            "created_date": self.created_date,
            "author_name": self.author_name,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "target_title": self.target_title,
            "merge_request_id": self.merge_request_id,
            "branch_name": self.branch_name,
            "commits_count": len(self.commits),
            "is_merge_related": self.is_merge_related
        }

@dataclass
class WorkClassification:
    """Classification of work based on events and commits."""
    work_type: WorkType
    confidence: float  # 0.0 to 1.0
    branch_name: Optional[str] = None
    merge_request_id: Optional[int] = None
    merge_request_title: Optional[str] = None
    commits: List[GitLabCommit] = field(default_factory=list)
    events: List[GitLabEvent] = field(default_factory=list)
    
    @property
    def commit_titles(self) -> List[str]:
        """Get list of commit titles for LLM processing."""
        return [commit.clean_title for commit in self.commits]
    
    @property
    def total_commits(self) -> int:
        """Get total number of commits."""
        return len(self.commits)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert classification to dictionary."""
        return {
            "work_type": self.work_type.value,
            "confidence": self.confidence,
            "branch_name": self.branch_name,
            "merge_request_id": self.merge_request_id,
            "merge_request_title": self.merge_request_title,
            "total_commits": self.total_commits,
            "commit_titles": self.commit_titles,
            "events_count": len(self.events)
        }

@dataclass
class WorkSummary:
    """LLM-generated summary of work."""
    name: str
    description: str
    estimated_hours: float
    confidence: float
    work_type: WorkType
    key_achievements: List[str] = field(default_factory=list)
    technical_details: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "estimated_hours": self.estimated_hours,
            "confidence": self.confidence,
            "work_type": self.work_type.value,
            "key_achievements": self.key_achievements,
            "technical_details": self.technical_details
        }

@dataclass
class EventFilters:
    """Event filtering parameters."""
    month: Optional[str] = None
    year: Optional[str] = None
    event_types: Optional[List[EventType]] = None
    project_ids: Optional[List[str]] = None
    limit: int = 200
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert filters to dictionary."""
        return {
            "month": self.month,
            "year": self.year,
            "event_types": [et.value for et in self.event_types] if self.event_types else None,
            "project_ids": self.project_ids,
            "limit": self.limit
        }

@dataclass
class EventSearchResult:
    """Result of event search."""
    success: bool
    total_events: int
    events: List[GitLabEvent]
    classifications: List[WorkClassification]
    summaries: List[WorkSummary]
    month_filter: Optional[str] = None
    error: Optional[str] = None
    
    @property
    def total_commits(self) -> int:
        """Get total commits across all events."""
        return sum(len(event.commits) for event in self.events)
    
    @property
    def total_work_hours(self) -> float:
        """Get total estimated work hours."""
        return sum(summary.estimated_hours for summary in self.summaries)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "total_events": self.total_events,
            "total_commits": self.total_commits,
            "total_work_hours": self.total_work_hours,
            "month_filter": self.month_filter,
            "events": [event.to_dict() for event in self.events],
            "classifications": [classification.to_dict() for classification in self.classifications],
            "summaries": [summary.to_dict() for summary in self.summaries],
            "error": self.error
        }