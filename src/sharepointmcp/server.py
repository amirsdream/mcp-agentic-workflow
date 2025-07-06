from typing import Optional, Dict, Any, List
from fastmcp import FastMCP

from ..config.settings import AppConfig
from ..services.sharepoint_service import SharePointService
from ..models.sharepoint_models import SharePointFormFilters


class SharePointMCPServer:
    """FastMCP server for SharePoint forms with multiple transport support."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.sharepoint = SharePointService(config)
        self.mcp = FastMCP("SharePoint Forms Server")
        self._register_tools()
    
    def _register_tools(self):
        """Register MCP tools."""
        
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
            
            search_result = self.sharepoint.search_forms(filters)
            
            if not search_result.success:
                return {
                    "success": False,
                    "error": search_result.error,
                    "total_forms": 0,
                    "table_data": [],
                    "forms": []
                }
            
            # Handle single form vs multiple forms
            if search_result.form:
                # Single form response
                summary_data = self.sharepoint.create_form_summary([search_result.form], filters)
                return {
                    "success": True,
                    "total_forms": 1,
                    "summary": summary_data["summary"],
                    "table_data": summary_data["table_data"],
                    "form": search_result.form.to_dict(),
                    "forms": [search_result.form.to_dict()]
                }
            else:
                # Multiple forms response
                summary_data = self.sharepoint.create_form_summary(search_result.forms, filters)
                return {
                    "success": True,
                    "total_forms": search_result.total_forms,
                    "summary": summary_data["summary"],
                    "table_data": summary_data["table_data"],
                    "list_breakdown": summary_data.get("list_breakdown", {}),
                    "status_breakdown": summary_data.get("status_breakdown", {}),
                    "forms": [form.to_dict() for form in search_result.forms[:limit]]
                }
        
        @self.mcp.tool()
        def get_sharepoint_lists(
            site_url: Optional[str] = None
        ) -> Dict[str, Any]:
            """Get all SharePoint lists from the specified site."""
            
            try:
                lists_result = self.sharepoint.get_site_lists(site_url)
                
                if not lists_result.success:
                    return {
                        "success": False,
                        "error": lists_result.error,
                        "total_lists": 0,
                        "lists": []
                    }
                
                # Create table data for lists
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
                    "total_lists": len(lists_result.lists),
                    "summary": f"Found {len(lists_result.lists)} lists on SharePoint site",
                    "table_data": table_data,
                    "lists": lists_result.lists
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "total_lists": 0,
                    "lists": []
                }
        
        @self.mcp.tool()
        def get_sharepoint_form_by_id(
            list_name: str,
            form_id: str,
            site_url: Optional[str] = None
        ) -> Dict[str, Any]:
            """Get a specific SharePoint form by ID."""
            
            try:
                form_result = self.sharepoint.get_form_by_id(list_name, form_id, site_url)
                
                if not form_result.success:
                    return {
                        "success": False,
                        "error": form_result.error,
                        "form": None
                    }
                
                return {
                    "success": True,
                    "summary": f"Retrieved form {form_id} from {list_name}",
                    "form": form_result.form.to_dict() if form_result.form else None
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "form": None
                }
        
        @self.mcp.tool()
        def search_sharepoint_forms(
            query: str,
            list_name: str = "Forms",
            site_url: Optional[str] = None,
            limit: int = 20
        ) -> Dict[str, Any]:
            """Search SharePoint forms by text query."""
            
            try:
                search_result = self.sharepoint.search_forms_by_text(query, list_name, site_url, limit)
                
                if not search_result.success:
                    return {
                        "success": False,
                        "error": search_result.error,
                        "total_forms": 0,
                        "forms": []
                    }
                
                summary_data = self.sharepoint.create_form_summary(search_result.forms, None)
                
                return {
                    "success": True,
                    "total_forms": search_result.total_forms,
                    "summary": f"Found {len(search_result.forms)} forms matching '{query}'",
                    "table_data": summary_data["table_data"],
                    "forms": [form.to_dict() for form in search_result.forms]
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "total_forms": 0,
                    "forms": []
                }
        
        @self.mcp.tool()
        def health_check() -> Dict[str, Any]:
            """Check the health of SharePoint connection and configured sites."""
            
            try:
                sharepoint_healthy = self.sharepoint.test_connection()
                
                # Test configured sites
                accessible_sites = []
                site_urls = [
                    self.config.get("sharepoint_site_url"),
                    self.config.get("sharepoint_primary_site"),
                    self.config.get("sharepoint_secondary_site")
                ]
                
                for site_url in site_urls:
                    if site_url:
                        try:
                            site_health = self.sharepoint.test_site_connection(site_url)
                            accessible_sites.append({
                                "url": site_url,
                                "accessible": site_health.get("success", False),
                                "site_title": site_health.get("site_title", "Unknown")
                            })
                        except Exception:
                            accessible_sites.append({
                                "url": site_url,
                                "accessible": False,
                                "site_title": "Connection Failed"
                            })
                
                return {
                    "success": True,
                    "sharepoint_connection": sharepoint_healthy,
                    "total_sites": len(accessible_sites),
                    "accessible_sites": len([s for s in accessible_sites if s["accessible"]]),
                    "sites": accessible_sites,
                    "connection_type": "Office365-REST-Python-Client" if sharepoint_healthy else "Mock"
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "sharepoint_connection": False
                }
        
        @self.mcp.tool()
        def get_sharepoint_user_forms(
            username: str,
            list_name: str = "Forms",
            site_url: Optional[str] = None,
            limit: int = 50
        ) -> Dict[str, Any]:
            """Get SharePoint forms created or modified by a specific user."""
            
            filters = SharePointFormFilters(
                site_url=site_url,
                list_name=list_name,
                created_by=username,
                limit=limit
            )
            
            search_result = self.sharepoint.search_forms(filters)
            
            if not search_result.success:
                return {
                    "success": False,
                    "error": search_result.error,
                    "total_forms": 0,
                    "forms": []
                }
            
            summary_data = self.sharepoint.create_form_summary(search_result.forms, filters)
            
            return {
                "success": True,
                "total_forms": search_result.total_forms,
                "summary": f"Found {len(search_result.forms)} forms by {username}",
                "table_data": summary_data["table_data"],
                "user": username,
                "forms": [form.to_dict() for form in search_result.forms]
            }
    
    def run_stdio(self):
        """Run server with stdio transport (development)."""
        print("🚀 Starting SharePoint Forms MCP Server (stdio)...")
        self.mcp.run(transport="stdio")
    
    def run_http(self, host: str = "0.0.0.0", port: int = 8001):
        """Run server with HTTP/SSE transport (production)."""
        print(f"🚀 Starting SharePoint Forms MCP Server (HTTP) on {host}:{port}...")
        self.mcp.run(transport="sse", host=host, port=port)
    
