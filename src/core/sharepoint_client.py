
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ..core.sharepoint_manager import SharePointClientManager
from ..config.settings import SharePointConfig

try:
    from office365.runtime.client_request_exception import ClientRequestException
except ImportError:
    ClientRequestException = Exception


class SharePointClient:
    """Client for SharePoint operations using the manager pattern."""
    
    def __init__(self, config: SharePointConfig):
        self.config = config
        self.manager = SharePointClientManager(config)
        self.connected = False
    
    async def connect(self, site_url: str = None, username: str = None, password: str = None) -> bool:
        """Connect to SharePoint site."""
        try:
            # Use provided credentials or fall back to config
            if site_url and site_url != self.config.site_url:
                # Handle different site URL - would need new config
                temp_config = SharePointConfig(
                    site_url=site_url,
                    username=username or self.config.username,
                    password=password or self.config.password,
                    client_id=self.config.client_id,
                    client_secret=self.config.client_secret
                )
                self.manager = SharePointClientManager(temp_config)
            
            # Test connection
            self.connected = self.manager.test_connection()
            return self.connected
            
        except Exception as e:
            print(f"SharePoint connection failed: {e}")
            return False
    
    async def get_forms(self, list_name: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get forms/items from SharePoint list."""
        if not self.connected and not await self.connect():
            return {"success": False, "error": "Not connected to SharePoint"}
        
        try:
            # Get the list
            target_list = self.manager.client.web.lists.get_by_title(list_name)
            
            # Build query
            query = target_list.items
            
            if filters:
                # Apply filters using CAML query
                caml_query = self._build_caml_query(filters)
                if caml_query:
                    query = target_list.get_items(caml_query)
            
            # Load items
            self.manager.client.load(query)
            self.manager.client.execute_query()
            
            # Process results
            forms = []
            for item in query:
                form_data = {
                    'id': str(item.id),
                    'title': getattr(item, 'Title', ''),
                    'created_date': str(getattr(item, 'Created', '')),
                    'modified_date': str(getattr(item, 'Modified', '')),
                    'created_by': str(getattr(item, 'Author', {}).get('Title', '')),
                    'modified_by': str(getattr(item, 'Editor', {}).get('Title', '')),
                    'status': getattr(item, 'Status', 'Active'),
                    'fields': {},
                    'list_name': list_name,
                    'web_url': f"{self.manager.client.web.url}/Lists/{list_name}/DispForm.aspx?ID={item.id}"
                }
                
                # Extract all fields
                for field_name in item.properties:
                    if not field_name.startswith('__') and field_name not in ['Id', 'Title', 'Created', 'Modified', 'Author', 'Editor', 'Status']:
                        form_data['fields'][field_name] = item.properties.get(field_name)
                
                forms.append(form_data)
            
            return {
                "success": True,
                "forms": forms,
                "count": len(forms),
                "list_name": list_name,
                "summary": f"Found {len(forms)} forms in {list_name}"
            }
            
        except ClientRequestException as e:
            return {"success": False, "error": f"SharePoint API error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Error retrieving forms: {str(e)}"}
    
    def _build_caml_query(self, filters: Dict[str, Any]) -> Optional[str]:
        """Build CAML query from filters."""
        conditions = []
        
        # Date filters
        if filters.get('date_from'):
            conditions.append(f"<Geq><FieldRef Name='Created'/><Value Type='DateTime'>{filters['date_from']}</Value></Geq>")
        
        if filters.get('date_to'):
            conditions.append(f"<Leq><FieldRef Name='Created'/><Value Type='DateTime'>{filters['date_to']}</Value></Leq>")
        
        # Creator filter
        if filters.get('created_by'):
            conditions.append(f"<Eq><FieldRef Name='Author'/><Value Type='User'>{filters['created_by']}</Value></Eq>")
        
        # Status filter
        if filters.get('status'):
            conditions.append(f"<Eq><FieldRef Name='Status'/><Value Type='Text'>{filters['status']}</Value></Eq>")
        
        if not conditions:
            return None
        
        # Build query
        if len(conditions) == 1:
            where_clause = conditions[0]
        else:
            where_clause = "<And>" + "".join(conditions) + "</And>"
        
        return f"<View><Query><Where>{where_clause}</Where></Query></View>"
    
    async def get_form_by_id(self, list_name: str, form_id: str) -> Dict[str, Any]:
        """Get specific form by ID."""
        if not self.connected and not await self.connect():
            return {"success": False, "error": "Not connected to SharePoint"}
        
        try:
            target_list = self.manager.client.web.lists.get_by_title(list_name)
            item = target_list.get_item_by_id(int(form_id))
            self.manager.client.load(item)
            self.manager.client.execute_query()
            
            form_data = {
                'id': str(item.id),
                'title': getattr(item, 'Title', ''),
                'created_date': str(getattr(item, 'Created', '')),
                'modified_date': str(getattr(item, 'Modified', '')),
                'created_by': str(getattr(item, 'Author', {}).get('Title', '')),
                'modified_by': str(getattr(item, 'Editor', {}).get('Title', '')),
                'status': getattr(item, 'Status', 'Active'),
                'fields': {},
                'list_name': list_name,
                'web_url': f"{self.manager.client.web.url}/Lists/{list_name}/DispForm.aspx?ID={item.id}"
            }
            
            # Extract all fields
            for field_name in item.properties:
                if not field_name.startswith('__') and field_name not in ['Id', 'Title', 'Created', 'Modified', 'Author', 'Editor', 'Status']:
                    form_data['fields'][field_name] = item.properties.get(field_name)
            
            return {
                "success": True,
                "form": form_data,
                "summary": f"Retrieved form {form_id} from {list_name}"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error retrieving form: {str(e)}"}
    
    async def get_lists(self) -> Dict[str, Any]:
        """Get all lists from SharePoint site."""
        if not self.connected and not await self.connect():
            return {"success": False, "error": "Not connected to SharePoint"}
        
        try:
            lists = self.manager.client.web.lists
            self.manager.client.load(lists)
            self.manager.client.execute_query()
            
            list_info = []
            for lst in lists:
                list_info.append({
                    'title': lst.title,
                    'description': lst.description,
                    'item_count': lst.item_count,
                    'created': str(lst.created),
                    'list_template': lst.template_type
                })
            
            return {
                "success": True,
                "lists": list_info,
                "count": len(list_info),
                "summary": f"Found {len(list_info)} lists on SharePoint site"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error retrieving lists: {str(e)}"}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check SharePoint connection health."""
        try:
            if not self.connected and not await self.connect():
                return {"success": False, "error": "Connection failed"}
            
            site_info = self.manager.get_site_info()
            if "error" in site_info:
                return {"success": False, "error": site_info["error"]}
            
            return {
                "success": True,
                "site_title": site_info.get("title", "Unknown"),
                "site_url": site_info.get("url", self.config.site_url),
                "connection": "healthy",
                "auth_type": self.config.get_auth_type()
            }
        except Exception as e:
            return {"success": False, "error": f"Health check failed: {str(e)}"}