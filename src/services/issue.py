from typing import List, Dict, Any
from datetime import datetime

from ..core.gitlab_client import GitLabClientManager
from ..core.date_parser import DateParser
from ..models.issue import GitLabIssue, IssueFilters, IssueSearchResult
from ..config.settings import GitLabConfig

class IssueService:
    """Service for GitLab issue operations."""
    
    def __init__(self, config: GitLabConfig):
        self.gitlab_manager = GitLabClientManager(config)
        self.config = config
    
    def search_issues(self, filters: IssueFilters) -> IssueSearchResult:
        """Search for issues based on filters."""
        try:
            gl = self.gitlab_manager.client
            start_date, end_date = DateParser.parse_month(filters.month)
            
            all_issues = []
            project_names = []
            
            for project_id in self.config.project_ids:
                try:
                    project = gl.projects.get(project_id)
                    project_names.append(project.name)
                    
                    # Build GitLab API parameters
                    params = {
                        'state': filters.state,
                        'order_by': 'created_at',
                        'sort': 'desc',
                        'get_all': True
                    }
                    
                    if filters.labels:
                        params['labels'] = filters.labels
                    
                    if start_date:
                        params['created_after'] = start_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                    if end_date:
                        params['created_before'] = end_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                    
                    # Get issues from GitLab
                    gitlab_issues = project.issues.list(**params)
                    
                    # Convert to our model
                    for issue in gitlab_issues:
                        # Filter by assignee if specified
                        if filters.assignee:
                            issue_assignee = issue.assignee.get('name', '').lower() if issue.assignee else ''
                            if filters.assignee.lower() not in issue_assignee:
                                continue
                        
                        gitlab_issue = self._convert_gitlab_issue(issue, project_id, project.name)
                        all_issues.append(gitlab_issue)
                        # Apply limit
                        if len(all_issues) >= filters.limit:
                            break
                            
                except Exception:
                    # Skip problematic projects
                    continue
            
            # Sort by creation date
            all_issues.sort(key=lambda x: x.created_at, reverse=True)
            
            return IssueSearchResult(
                success=True,
                total_issues=len(all_issues),
                issues=all_issues,
                project_names=project_names
            )
            
        except Exception as e:
            return IssueSearchResult(
                success=False,
                total_issues=0,
                issues=[],
                project_names=[],
                error=str(e)
            )
    
    def _convert_gitlab_issue(self, gitlab_issue, project_id: str, project_name: str) -> GitLabIssue:
        """Convert GitLab API issue to our model."""
        created_at = datetime.fromisoformat(gitlab_issue.created_at.replace('Z', '+00:00'))
        updated_at = datetime.fromisoformat(gitlab_issue.updated_at.replace('Z', '+00:00'))
        
        description = gitlab_issue.description or ""
        if len(description) > 200:
            description = description[:200] + "..."
        
        return GitLabIssue(
            project_id=project_id,
            project_name=project_name,
            iid=gitlab_issue.iid,
            title=gitlab_issue.title,
            description=description,
            state=gitlab_issue.state,
            author=gitlab_issue.author.get('name', 'Unknown') if gitlab_issue.author else 'Unknown',
            assignee=gitlab_issue.assignee.get('name') if gitlab_issue.assignee else None,
            labels=gitlab_issue.labels,
            created_at=created_at,
            updated_at=updated_at,
            web_url=gitlab_issue.web_url
        )
    
    def create_issue_summary(self, result: IssueSearchResult, filters: IssueFilters) -> Dict[str, Any]:
        """Create summary table from search results."""
        if not result.success or not result.issues:
            return {
                "summary": "No issues found for the specified criteria.",
                "table_data": [],
                "project_breakdown": {},
                "state_breakdown": {}
            }
        
        # Create table data
        table_data = []
        for issue in result.issues:
            table_data.append({
                'ID': f"#{issue.iid}",
                'Title': issue.title[:50] + '...' if len(issue.title) > 50 else issue.title,
                'Project': issue.project_name,
                'State': issue.state,
                'Author': issue.author,
                'Assignee': issue.assignee or 'Unassigned',
                'Created': issue.created_date,
                'Labels': ', '.join(issue.labels[:2]) if issue.labels else 'None'
            })
        
        # Create breakdowns
        project_breakdown = {}
        state_breakdown = {}
        
        for issue in result.issues:
            project_breakdown[issue.project_name] = project_breakdown.get(issue.project_name, 0) + 1
            state_breakdown[issue.state] = state_breakdown.get(issue.state, 0) + 1
        
        # Create summary text
        summary = f"""
## Issues Summary

**Filters Applied:**
- Month: {filters.month or 'All time'}
- State: {filters.state}
- Labels: {filters.labels or 'All labels'}
- Total Issues: {result.total_issues}

**Projects searched:** {', '.join(result.project_names)}

**Breakdown by Project:**
{chr(10).join(f"- {project}: {count} issues" for project, count in project_breakdown.items())}

**Breakdown by State:**
{chr(10).join(f"- {state}: {count} issues" for state, count in state_breakdown.items())}
"""
        
        return {
            "summary": summary,
            "table_data": table_data,
            "project_breakdown": project_breakdown,
            "state_breakdown": state_breakdown
        }