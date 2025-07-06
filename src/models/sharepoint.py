"""
SharePoint data models similar to GitLab issue models
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SharePointFormFilters:
    """Filters for SharePoint form searches - similar to IssueFilters"""
    site_url: Optional[str] = None
    list_name: str = "Forms"
    form_id: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    status: Optional[str] = None
    created_by: Optional[str] = None
    modified_by: Optional[str] = None
    limit: int = 50
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert filters to dictionary"""
        return {
            "site_url": self.site_url,
            "list_name": self.list_name,
            "form_id": self.form_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "status": self.status,
            "created_by": self.created_by,
            "modified_by": self.modified_by,
            "limit": self.limit
        }


@dataclass
class SharePointForm:
    """SharePoint form data model - similar to GitLab Issue"""
    id: str
    title: str
    fields: Dict[str, Any]
    created_date: str
    modified_date: str
    created_by: str
    modified_by: str
    status: str
    list_name: str
    site_url: str
    web_url: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert form to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "fields": self.fields,
            "created_date": self.created_date,
            "modified_date": self.modified_date,
            "created_by": self.created_by,
            "modified_by": self.modified_by,
            "status": self.status,
            "list_name": self.list_name,
            "site_url": self.site_url,
            "web_url": self.web_url
        }
    
    @property
    def field_count(self) -> int:
        """Number of non-empty fields"""
        return len([v for v in self.fields.values() if v])
    
    @property
    def has_attachments(self) -> bool:
        """Check if form has attachments"""
        return any("attachment" in str(v).lower() for v in self.fields.values() if v)
    
    def get_field_value(self, field_name: str, default: Any = None) -> Any:
        """Get specific field value with default"""
        return self.fields.get(field_name, default)
    
    def search_fields(self, query: str) -> bool:
        """Search for text in form fields"""
        query_lower = query.lower()
        
        # Search in title
        if query_lower in self.title.lower():
            return True
        
        # Search in field values
        for value in self.fields.values():
            if value and query_lower in str(value).lower():
                return True
        
        return False


@dataclass
class SharePointList:
    """SharePoint list metadata"""
    title: str
    description: str
    item_count: int
    created: str
    list_template: int
    url: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert list to dictionary"""
        return {
            "title": self.title,
            "description": self.description,
            "item_count": self.item_count,
            "created": self.created,
            "list_template": self.list_template,
            "url": self.url
        }


@dataclass
class SharePointSite:
    """SharePoint site information"""
    url: str
    title: str
    description: str
    created: str
    web_template: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert site to dictionary"""
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "created": self.created,
            "web_template": self.web_template
        }


class SharePointFormProcessor:
    """Utility class for processing SharePoint forms - similar to GitLab issue processing"""
    
    @staticmethod
    def group_by_list(forms: List[SharePointForm]) -> Dict[str, List[SharePointForm]]:
        """Group forms by list name"""
        groups = {}
        for form in forms:
            if form.list_name not in groups:
                groups[form.list_name] = []
            groups[form.list_name].append(form)
        return groups
    
    @staticmethod
    def group_by_status(forms: List[SharePointForm]) -> Dict[str, List[SharePointForm]]:
        """Group forms by status"""
        groups = {}
        for form in forms:
            if form.status not in groups:
                groups[form.status] = []
            groups[form.status].append(form)
        return groups
    
    @staticmethod
    def group_by_creator(forms: List[SharePointForm]) -> Dict[str, List[SharePointForm]]:
        """Group forms by creator"""
        groups = {}
        for form in forms:
            if form.created_by not in groups:
                groups[form.created_by] = []
            groups[form.created_by].append(form)
        return groups
    
    @staticmethod
    def filter_by_date_range(forms: List[SharePointForm], date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[SharePointForm]:
        """Filter forms by date range"""
        if not date_from and not date_to:
            return forms
        
        filtered = []
        for form in forms:
            try:
                form_date = datetime.fromisoformat(form.created_date.replace('Z', '+00:00'))
                
                if date_from:
                    from_date = datetime.fromisoformat(date_from)
                    if form_date < from_date:
                        continue
                
                if date_to:
                    to_date = datetime.fromisoformat(date_to)
                    if form_date > to_date:
                        continue
                
                filtered.append(form)
            except (ValueError, AttributeError):
                # Include forms with invalid dates
                filtered.append(form)
        
        return filtered
    
    @staticmethod
    def get_recent_forms(forms: List[SharePointForm], days: int = 7) -> List[SharePointForm]:
        """Get forms created in the last N days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent = []
        for form in forms:
            try:
                form_date = datetime.fromisoformat(form.created_date.replace('Z', '+00:00'))
                if form_date >= cutoff_date:
                    recent.append(form)
            except (ValueError, AttributeError):
                continue
        
        return recent
    
    @staticmethod
    def create_summary_stats(forms: List[SharePointForm]) -> Dict[str, Any]:
        """Create summary statistics for forms"""
        if not forms:
            return {
                "total_forms": 0,
                "lists": {},
                "statuses": {},
                "creators": {},
                "date_range": {}
            }
        
        stats = {
            "total_forms": len(forms),
            "lists": {},
            "statuses": {},
            "creators": {},
            "date_range": {}
        }
        
        # Count by list
        for form in forms:
            stats["lists"][form.list_name] = stats["lists"].get(form.list_name, 0) + 1
            stats["statuses"][form.status] = stats["statuses"].get(form.status, 0) + 1
            stats["creators"][form.created_by] = stats["creators"].get(form.created_by, 0) + 1
        
        # Date range
        dates = []
        for form in forms:
            try:
                form_date = datetime.fromisoformat(form.created_date.replace('Z', '+00:00'))
                dates.append(form_date)
            except (ValueError, AttributeError):
                continue
        
        if dates:
            stats["date_range"] = {
                "earliest": min(dates).isoformat(),
                "latest": max(dates).isoformat(),
                "span_days": (max(dates) - min(dates)).days
            }
        
        return stats