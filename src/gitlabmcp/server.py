
from typing import Optional, Dict, Any
from fastmcp import FastMCP

from ..config.settings import AppConfig
from ..services.issue import IssueService
from ..models.issue import IssueFilters

class GitLabMCPServer:
    """FastMCP server for GitLab issues with multiple transport support."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.issue = IssueService(config.gitlab)
        self.mcp = FastMCP("GitLab Issues Server")
        self._register_tools()
    
    def _register_tools(self):
        """Register MCP tools."""
        
        @self.mcp.tool()
        def list_gitlab_issues(
            month: Optional[str] = None,
            year: Optional[str] = None,  # Added year filter
            state: str = "opened", 
            labels: Optional[str] = None,
            assignee: Optional[str] = None,
            limit: int = 100
        ) -> Dict[str, Any]:
            """List GitLab issues from configured projects with filtering options."""
            filters = IssueFilters(
                month=month, state=state, labels=labels, 
                assignee=assignee, limit=limit
            )
            search_result = self.issue.search_issues(filters)
            
            if not search_result.success:
                return {
                    "success": False,
                    "error": search_result.error,
                    "total_issues": 0,
                    "table_data": [],
                    "issues": []
                }
            
            summary_data = self.issue.create_issue_summary(search_result, filters)
            return {
                "success": True,
                "total_issues": search_result.total_issues,
                "summary": summary_data["summary"],
                "table_data": summary_data["table_data"],
                "project_breakdown": summary_data["project_breakdown"],
                "state_breakdown": summary_data["state_breakdown"],
                "issues": [issue.to_dict() for issue in search_result.issues[:10]]
            }
        
        @self.mcp.tool()
        def health_check() -> Dict[str, Any]:
            """Check the health of GitLab connection and configured projects."""
            try:
                gitlab_healthy = self.issue.gitlab_manager.test_connection()
                
                accessible_projects = []
                for project_id in self.config.gitlab.project_ids:
                    try:
                        project = self.issue.gitlab_manager.client.projects.get(project_id)
                        accessible_projects.append({
                            "id": project_id,
                            "name": project.name,
                            "accessible": True
                        })
                    except Exception:
                        accessible_projects.append({
                            "id": project_id,
                            "name": f"Project {project_id}",
                            "accessible": False
                        })
                
                return {
                    "success": True,
                    "gitlab_connection": gitlab_healthy,
                    "total_projects": len(self.config.gitlab.project_ids),
                    "accessible_projects": len([p for p in accessible_projects if p["accessible"]]),
                    "projects": accessible_projects
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "gitlab_connection": False
                }
    
    def run_stdio(self):
        """Run server with stdio transport (development)."""
        print("🚀 Starting GitLab Issues MCP Server (stdio)...")
        self.mcp.run(transport="stdio")
    
    def run_http(self, host: str = "0.0.0.0", port: int = 8000):
        """Run server with HTTP/SSE transport (production)."""
        print(f"🚀 Starting GitLab Issues MCP Server (HTTP) on {host}:{port}...")
        self.mcp.run(transport="sse", host=host, port=port)
