"""
Combined GitLab + SharePoint FastMCP Server
"""

from typing import Optional, Dict, Any
from fastmcp import FastMCP

from src.config.settings import AppConfig
from src.services.issue import IssueService
from src.services.sharepoint import SharePointService
from src.models.issue import IssueFilters
from src.models.sharepoint import SharePointFormFilters


class CombinedMCPServer:
    """Combined FastMCP server for both GitLab issues and SharePoint forms."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        
        # Initialize services
        try:
            self.gitlab_service = IssueService(config.gitlab)
            self.gitlab_available = True
        except Exception as e:
            print(f"⚠️ GitLab service unavailable: {e}")
            self.gitlab_service = None
            self.gitlab_available = False
        
        try:
            self.sharepoint_service = SharePointService(config)
            self.sharepoint_available = True
        except Exception as e:
            print(f"⚠️ SharePoint service unavailable: {e}")
            self.sharepoint_service = None
            self.sharepoint_available = False
        
        self.mcp = FastMCP("Combined GitLab + SharePoint Server")
        self._register_tools()
    
    def _register_tools(self):
        """Register MCP tools for both GitLab and SharePoint."""
        
        # ================================================================
        # GITLAB TOOLS
        # ================================================================
        
        if self.gitlab_available:
            @self.mcp.tool()
            def list_gitlab_issues(
                month: Optional[str] = None,
                year: Optional[str] = None,
                state: str = "opened",
                labels: Optional[str] = None,
                assignee: Optional[str] = None,
                limit: int = 100
            ) -> Dict[str, Any]:
                """List GitLab issues from configured projects with filtering options."""
                try:
                    filters = IssueFilters(
                        month=month, year=year, state=state, labels=labels,
                        assignee=assignee, limit=limit
                    )
                    search_result = self.gitlab_service.search_issues(filters)
                    
                    if not search_result.success:
                        return {
                            "success": False,
                            "error": search_result.error,
                            "total_issues": 0,
                            "source": "gitlab"
                        }
                    
                    summary_data = self.gitlab_service.create_issue_summary(search_result, filters)
                    return {
                        "success": True,
                        "source": "gitlab",
                        "total_issues": search_result.total_issues,
                        "summary": summary_data["summary"],
                        "table_data": summary_data["table_data"],
                        "project_breakdown": summary_data["project_breakdown"],
                        "state_breakdown": summary_data["state_breakdown"],
                        "issues": [issue.to_dict() for issue in search_result.issues[:10]]
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"GitLab service error: {str(e)}",
                        "source": "gitlab"
                    }
        
        # ================================================================
        # SHAREPOINT TOOLS
        # ================================================================
        
        if self.sharepoint_available:
            @self.mcp.tool()
            def list_sharepoint_forms(
                site_url: Optional[str] = None,
                list_name: str = "Forms",
                form_id: Optional[str] = None,
                date_from: Optional[str] = None,
                date_to: Optional[str] = None,
                status: Optional[str] = None,
                created_by: Optional[str] = None,
                limit: int = 50
            ) -> Dict[str, Any]:
                """List SharePoint forms from specified list with filtering options."""
                try:
                    filters = SharePointFormFilters(
                        site_url=site_url,
                        list_name=list_name,
                        form_id=form_id,
                        date_from=date_from,
                        date_to=date_to,
                        status=status,
                        created_by=created_by,
                        limit=limit
                    )
                    
                    search_result = self.sharepoint_service.search_forms(filters)
                    
                    if not search_result.success:
                        return {
                            "success": False,
                            "error": search_result.error,
                            "total_forms": 0,
                            "source": "sharepoint"
                        }
                    
                    # Handle single form vs multiple forms
                    if search_result.form:
                        summary_data = self.sharepoint_service.create_form_summary([search_result.form], filters)
                        return {
                            "success": True,
                            "source": "sharepoint",
                            "total_forms": 1,
                            "summary": summary_data["summary"],
                            "table_data": summary_data["table_data"],
                            "form": search_result.form.to_dict(),
                            "forms": [search_result.form.to_dict()]
                        }
                    else:
                        summary_data = self.sharepoint_service.create_form_summary(search_result.forms, filters)
                        return {
                            "success": True,
                            "source": "sharepoint",
                            "total_forms": search_result.total_forms,
                            "summary": summary_data["summary"],
                            "table_data": summary_data["table_data"],
                            "list_breakdown": summary_data.get("list_breakdown", {}),
                            "status_breakdown": summary_data.get("status_breakdown", {}),
                            "forms": [form.to_dict() for form in search_result.forms[:limit]]
                        }
                        
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"SharePoint service error: {str(e)}",
                        "source": "sharepoint"
                    }
            
            @self.mcp.tool()
            def get_sharepoint_lists(
                site_url: Optional[str] = None
            ) -> Dict[str, Any]:
                """Get all SharePoint lists from the specified site."""
                try:
                    lists_result = self.sharepoint_service.get_site_lists(site_url)
                    
                    if not lists_result.success:
                        return {
                            "success": False,
                            "error": lists_result.error,
                            "total_lists": 0,
                            "source": "sharepoint"
                        }
                    
                    table_data = []
                    for lst in lists_result.lists:
                        table_data.append({
                            "Title": lst.get("title", ""),
                            "Description": lst.get("description", ""),
                            "Item Count": lst.get("item_count", 0),
                            "Created": lst.get("created", ""),
                            "Template Type": lst.get("list_template", "")
                        })
                    
                    return {
                        "success": True,
                        "source": "sharepoint",
                        "total_lists": len(lists_result.lists),
                        "summary": f"Found {len(lists_result.lists)} lists on SharePoint site",
                        "table_data": table_data,
                        "lists": lists_result.lists
                    }
                    
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"SharePoint lists error: {str(e)}",
                        "source": "sharepoint"
                    }
        
        # ================================================================
        # COMBINED TOOLS
        # ================================================================
        
        @self.mcp.tool()
        def get_combined_data(
            # GitLab parameters
            gitlab_month: Optional[str] = None,
            gitlab_state: str = "opened",
            gitlab_labels: Optional[str] = None,
            gitlab_limit: int = 50,
            # SharePoint parameters
            sharepoint_list: str = "Forms",
            sharepoint_date_from: Optional[str] = None,
            sharepoint_created_by: Optional[str] = None,
            sharepoint_limit: int = 25
        ) -> Dict[str, Any]:
            """Get data from both GitLab and SharePoint in a single call."""
            
            result = {
                "success": True,
                "source": "combined",
                "gitlab": None,
                "sharepoint": None,
                "summary": ""
            }
            
            # Get GitLab data
            if self.gitlab_available:
                try:
                    gitlab_result = list_gitlab_issues(
                        month=gitlab_month,
                        state=gitlab_state,
                        labels=gitlab_labels,
                        limit=gitlab_limit
                    )
                    result["gitlab"] = gitlab_result
                except Exception as e:
                    result["gitlab"] = {
                        "success": False,
                        "error": f"GitLab error: {str(e)}"
                    }
            
            # Get SharePoint data
            if self.sharepoint_available:
                try:
                    sharepoint_result = list_sharepoint_forms(
                        list_name=sharepoint_list,
                        date_from=sharepoint_date_from,
                        created_by=sharepoint_created_by,
                        limit=sharepoint_limit
                    )
                    result["sharepoint"] = sharepoint_result
                except Exception as e:
                    result["sharepoint"] = {
                        "success": False,
                        "error": f"SharePoint error: {str(e)}"
                    }
            
            # Create combined summary
            summary_parts = []
            if result["gitlab"] and result["gitlab"].get("success"):
                gitlab_count = result["gitlab"].get("total_issues", 0)
                summary_parts.append(f"{gitlab_count} GitLab issues")
            
            if result["sharepoint"] and result["sharepoint"].get("success"):
                sharepoint_count = result["sharepoint"].get("total_forms", 0)
                summary_parts.append(f"{sharepoint_count} SharePoint forms")
            
            if summary_parts:
                result["summary"] = f"Retrieved {' and '.join(summary_parts)}"
            else:
                result["summary"] = "No data retrieved from either system"
                result["success"] = False
            
            return result
        
        # ================================================================
        # HEALTH CHECK
        # ================================================================
        
        @self.mcp.tool()
        def health_check() -> Dict[str, Any]:
            """Check the health of both GitLab and SharePoint connections."""
            
            health_status = {
                "success": True,
                "gitlab": {"available": self.gitlab_available},
                "sharepoint": {"available": self.sharepoint_available},
                "overall_status": "healthy"
            }
            
            # Test GitLab
            if self.gitlab_available:
                try:
                    gitlab_healthy = self.gitlab_service.gitlab_manager.test_connection()
                    health_status["gitlab"]["connection"] = gitlab_healthy
                    health_status["gitlab"]["projects"] = len(self.config.gitlab.project_ids)
                except Exception as e:
                    health_status["gitlab"]["connection"] = False
                    health_status["gitlab"]["error"] = str(e)
            
            # Test SharePoint
            if self.sharepoint_available:
                try:
                    sharepoint_healthy = self.sharepoint_service.test_connection()
                    health_status["sharepoint"]["connection"] = sharepoint_healthy
                    health_status["sharepoint"]["site_url"] = self.config.get("sharepoint_site_url", "Not configured")
                except Exception as e:
                    health_status["sharepoint"]["connection"] = False
                    health_status["sharepoint"]["error"] = str(e)
            
            # Determine overall status
            gitlab_ok = health_status["gitlab"].get("connection", False) if self.gitlab_available else True
            sharepoint_ok = health_status["sharepoint"].get("connection", False) if self.sharepoint_available else True
            
            if not gitlab_ok and not sharepoint_ok:
                health_status["overall_status"] = "unhealthy"
                health_status["success"] = False
            elif not gitlab_ok or not sharepoint_ok:
                health_status["overall_status"] = "degraded"
            
            return health_status
    
    def run_stdio(self):
        """Run server with stdio transport (development)."""
        services = []
        if self.gitlab_available:
            services.append("GitLab")
        if self.sharepoint_available:
            services.append("SharePoint")
        
        print(f"🚀 Starting Combined MCP Server (stdio) with {' + '.join(services)}...")
        self.mcp.run(transport="stdio")
    
    def run_http(self, host: str = "0.0.0.0", port: int = 8000):
        """Run server with HTTP/SSE transport (production)."""
        services = []
        if self.gitlab_available:
            services.append("GitLab")
        if self.sharepoint_available:
            services.append("SharePoint")
        
        print(f"🚀 Starting Combined MCP Server (HTTP) with {' + '.join(services)} on {host}:{port}...")
        self.mcp.run(transport="sse", host=host, port=port)