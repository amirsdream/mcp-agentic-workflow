from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..core.sharepoint_client import SharePointClient, MockSharePointClient, SHAREPOINT_AVAILABLE
from ..models.sharepoint import SharePointFormFilters, SharePointForm
from ..config.settings import AppConfig


@dataclass
class SharePointSearchResult:
    """Search result container for SharePoint operations"""
    success: bool
    forms: List[SharePointForm] = None
    form: SharePointForm = None
    lists: List[Dict[str, Any]] = None
    total_forms: int = 0
    total_lists: int = 0
    error: str = None


class SharePointService:
    """Service layer for SharePoint operations"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        
        # Initialize SharePoint client
        if SHAREPOINT_AVAILABLE:
            self.client = SharePointClient(config)
        else:
            self.client = MockSharePointClient(config)
        
        # Connection settings
        self.site_url = config.get("sharepoint_site_url", "https://your-tenant.sharepoint.com/sites/your-site")
        self.username = config.get("sharepoint_username", "")
        self.password = config.get("sharepoint_password", "")
        self.connected = False
    
    async def ensure_connection(self, site_url: Optional[str] = None) -> bool:
        """Ensure SharePoint connection is established"""
        target_url = site_url or self.site_url
        
        if not self.connected:
            self.connected = await self.client.connect(target_url, self.username, self.password)
        
        return self.connected
    
    def search_forms(self, filters: SharePointFormFilters) -> SharePointSearchResult:
        """Search for SharePoint forms with filters"""
        try:
            # Ensure connection
            if not self.ensure_connection(filters.site_url):
                return SharePointSearchResult(
                    success=False,
                    error="Failed to connect to SharePoint"
                )
            
            # Handle specific form ID
            if filters.form_id:
                return self.get_form_by_id(filters.list_name, filters.form_id, filters.site_url)
            
            # Build filter dictionary
            filter_dict = {}
            if filters.date_from:
                filter_dict["date_from"] = filters.date_from
            if filters.date_to:
                filter_dict["date_to"] = filters.date_to
            if filters.status:
                filter_dict["status"] = filters.status
            if filters.created_by:
                filter_dict["created_by"] = filters.created_by
            
            # Get forms from SharePoint
            result = self.client.get_forms(filters.list_name, filter_dict)
            
            if not result.get("success"):
                return SharePointSearchResult(
                    success=False,
                    error=result.get("error", "Unknown error")
                )
            
            # Convert to SharePointForm objects
            forms = []
            for form_data in result.get("forms", []):
                form = SharePointForm(
                    id=form_data["id"],
                    title=form_data["title"],
                    fields=form_data["fields"],
                    created_date=form_data["created_date"],
                    modified_date=form_data["modified_date"],
                    created_by=form_data["created_by"],
                    modified_by=form_data["modified_by"],
                    status=form_data.get("status", "Active"),
                    list_name=form_data["list_name"],
                    site_url=self.site_url,
                    web_url=form_data["web_url"]
                )
                forms.append(form)
            
            # Apply limit
            if filters.limit and len(forms) > filters.limit:
                forms = forms[:filters.limit]
            
            return SharePointSearchResult(
                success=True,
                forms=forms,
                total_forms=len(forms)
            )
            
        except Exception as e:
            return SharePointSearchResult(
                success=False,
                error=str(e)
            )
    
    def get_form_by_id(self, list_name: str, form_id: str, site_url: Optional[str] = None) -> SharePointSearchResult:
        """Get a specific form by ID"""
        try:
            if not self.ensure_connection(site_url):
                return SharePointSearchResult(
                    success=False,
                    error="Failed to connect to SharePoint"
                )
            
            result = self.client.get_form_by_id(list_name, form_id)
            
            if not result.get("success"):
                return SharePointSearchResult(
                    success=False,
                    error=result.get("error", "Form not found")
                )
            
            form_data = result["form"]
            form = SharePointForm(
                id=form_data["id"],
                title=form_data["title"],
                fields=form_data["fields"],
                created_date=form_data["created_date"],
                modified_date=form_data["modified_date"],
                created_by=form_data["created_by"],
                modified_by=form_data["modified_by"],
                status=form_data.get("status", "Active"),
                list_name=form_data["list_name"],
                site_url=site_url or self.site_url,
                web_url=form_data["web_url"]
            )
            
            return SharePointSearchResult(
                success=True,
                form=form,
                total_forms=1
            )
            
        except Exception as e:
            return SharePointSearchResult(
                success=False,
                error=str(e)
            )
    
    def get_site_lists(self, site_url: Optional[str] = None) -> SharePointSearchResult:
        """Get all lists from SharePoint site"""
        try:
            if not self.ensure_connection(site_url):
                return SharePointSearchResult(
                    success=False,
                    error="Failed to connect to SharePoint"
                )
            
            result = self.client.get_lists()
            
            if not result.get("success"):
                return SharePointSearchResult(
                    success=False,
                    error=result.get("error", "Failed to retrieve lists")
                )
            
            return SharePointSearchResult(
                success=True,
                lists=result["lists"],
                total_lists=len(result["lists"])
            )
            
        except Exception as e:
            return SharePointSearchResult(
                success=False,
                error=str(e)
            )
    
    def search_forms_by_text(self, query: str, list_name: str, site_url: Optional[str] = None, limit: int = 20) -> SharePointSearchResult:
        """Search forms by text query (simplified implementation)"""
        try:
            # For now, get all forms and filter by text
            filters = SharePointFormFilters(
                site_url=site_url,
                list_name=list_name,
                limit=limit * 2  # Get more to filter
            )
            
            search_result = self.search_forms(filters)
            
            if not search_result.success:
                return search_result
            
            # Filter forms by query text
            query_lower = query.lower()
            matching_forms = []
            
            for form in search_result.forms:
                # Search in title and fields
                if (query_lower in form.title.lower() or
                    any(query_lower in str(value).lower() for value in form.fields.values() if value)):
                    matching_forms.append(form)
                
                if len(matching_forms) >= limit:
                    break
            
            return SharePointSearchResult(
                success=True,
                forms=matching_forms,
                total_forms=len(matching_forms)
            )
            
        except Exception as e:
            return SharePointSearchResult(
                success=False,
                error=str(e)
            )
    
    def test_connection(self) -> bool:
        """Test SharePoint connection"""
        try:
            return self.ensure_connection()
        except Exception:
            return False
    
    def test_site_connection(self, site_url: str) -> Dict[str, Any]:
        """Test connection to a specific SharePoint site"""
        try:
            temp_client = SharePointClient(self.config) if SHAREPOINT_AVAILABLE else MockSharePointClient(self.config)
            connected = temp_client.connect(site_url, self.username, self.password)
            
            if connected:
                health = temp_client.health_check()
                return health
            else:
                return {"success": False, "error": "Connection failed"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_form_summary(self, forms: List[SharePointForm], filters: Optional[SharePointFormFilters]) -> Dict[str, Any]:
        """Create summary data for forms"""
        if not forms:
            return {
                "summary": "No forms found matching the criteria.",
                "table_data": [],
                "list_breakdown": {},
                "status_breakdown": {}
            }
        
        # Create table data
        table_data = []
        list_breakdown = {}
        status_breakdown = {}
        
        for form in forms:
            table_data.append({
                "ID": form.id,
                "Title": form.title,
                "Created By": form.created_by,
                "Created Date": form.created_date[:10] if form.created_date else "",
                "List": form.list_name,
                "Status": form.status
            })
            
            # Count by list
            list_breakdown[form.list_name] = list_breakdown.get(form.list_name, 0) + 1
            
            # Count by status
            status_breakdown[form.status] = status_breakdown.get(form.status, 0) + 1
        
        # Create summary text
        total_forms = len(forms)
        lists_count = len(list_breakdown)
        
        summary_parts = [f"Found {total_forms} forms"]
        
        if filters:
            if filters.list_name and filters.list_name != "Forms":
                summary_parts.append(f"from '{filters.list_name}' list")
            if filters.created_by:
                summary_parts.append(f"created by {filters.created_by}")
            if filters.date_from:
                summary_parts.append(f"from {filters.date_from}")
            if filters.status:
                summary_parts.append(f"with status '{filters.status}'")
        
        if lists_count > 1:
            summary_parts.append(f"across {lists_count} lists")
        
        summary = " ".join(summary_parts) + "."
        
        return {
            "summary": summary,
            "table_data": table_data,
            "list_breakdown": list_breakdown,
            "status_breakdown": status_breakdown
        }