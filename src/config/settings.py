import os
from typing import List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class GitLabConfig:
    """GitLab configuration settings."""
    url: str
    token: str
    project_ids: List[str]
    
    @classmethod
    def from_env(cls) -> 'GitLabConfig':
        """Create configuration from environment variables."""
        url = os.getenv("GITLAB_URL", "https://gitlab.com")
        token = os.getenv("GITLAB_TOKEN", "")
        project_ids_str = os.getenv("GITLAB_PROJECT_IDS", "")
        
        if not token:
            raise ValueError("GITLAB_TOKEN environment variable is required")
        
        project_ids = [
            pid.strip() 
            for pid in project_ids_str.split(",") 
            if pid.strip()
        ]
        
        if not project_ids:
            raise ValueError("GITLAB_PROJECT_IDS environment variable is required")
        
        return cls(url=url, token=token, project_ids=project_ids)

@dataclass
class OpenAIConfig:
    """OpenAI configuration settings."""
    api_key: str
    
    @classmethod
    def from_env(cls) -> 'OpenAIConfig':
        """Create configuration from environment variables."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        return cls(api_key=api_key)

@dataclass
class SharePointConfig:
    """SharePoint configuration settings."""
    site_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None
    default_lists: List[str] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.site_url:
            raise ValueError("SharePoint site URL is required")
        
        # Ensure we have either user auth or app auth
        has_user_auth = self.username and self.password
        has_app_auth = self.client_id and self.client_secret
        
        if not has_user_auth and not has_app_auth:
            raise ValueError(
                "Either username/password or client_id/client_secret must be provided"
            )
        
        # Set default lists if not provided
        if self.default_lists is None:
            self.default_lists = ["Forms", "Documents", "Lists"]
    
    @classmethod
    def from_env(cls) -> "SharePointConfig":
        """Create configuration from environment variables."""
        site_url = os.getenv("SHAREPOINT_SITE_URL")
        if not site_url:
            raise ValueError("SHAREPOINT_SITE_URL environment variable is required")
        
        # Get authentication credentials
        username = os.getenv("SHAREPOINT_USERNAME")
        password = os.getenv("SHAREPOINT_PASSWORD")
        client_id = os.getenv("SHAREPOINT_CLIENT_ID")
        client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
        tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
        
        # Get default lists (comma-separated)
        default_lists_str = os.getenv("SHAREPOINT_DEFAULT_LISTS", "Forms,Documents,Lists")
        default_lists = [lst.strip() for lst in default_lists_str.split(",") if lst.strip()]
        
        return cls(
            site_url=site_url,
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            default_lists=default_lists
        )
    
    def get_auth_type(self) -> str:
        """Get the authentication type being used."""
        if self.client_id and self.client_secret:
            return "app_only"
        elif self.username and self.password:
            return "user_credentials"
        else:
            return "none"
    
    def validate(self) -> bool:
        """Validate the configuration."""
        try:
            # Check if site URL is properly formatted
            if not self.site_url.startswith(('http://', 'https://')):
                return False
            
            # Check authentication
            has_user_auth = bool(self.username and self.password)
            has_app_auth = bool(self.client_id and self.client_secret)
            
            return has_user_auth or has_app_auth
        except Exception:
            return False

@dataclass
class MCPConfig:
    """MCP server configuration settings."""
    gitlab_server_url: Optional[str] = None
    sharepoint_server_url: Optional[str] = None
    combined_server_url: Optional[str] = None
    gitlab_server_host: str = "localhost"
    gitlab_server_port: int = 8000
    sharepoint_server_host: str = "localhost"
    sharepoint_server_port: int = 8001
    combined_server_host: str = "localhost"
    combined_server_port: int = 8002
    
    @classmethod
    def from_env(cls) -> 'MCPConfig':
        """Create configuration from environment variables."""
        return cls(
            gitlab_server_url=os.getenv("GITLAB_MCP_SERVER_URL") or os.getenv("MCP_SERVER_URL"),
            sharepoint_server_url=os.getenv("SHAREPOINT_MCP_SERVER_URL"),
            combined_server_url=os.getenv("COMBINED_MCP_SERVER_URL"),
            gitlab_server_host=os.getenv("GITLAB_MCP_SERVER_HOST", "localhost"),
            gitlab_server_port=int(os.getenv("GITLAB_MCP_SERVER_PORT", "8000")),
            sharepoint_server_host=os.getenv("SHAREPOINT_MCP_SERVER_HOST", "localhost"),
            sharepoint_server_port=int(os.getenv("SHAREPOINT_MCP_SERVER_PORT", "8001")),
            combined_server_host=os.getenv("COMBINED_MCP_SERVER_HOST", "localhost"),
            combined_server_port=int(os.getenv("COMBINED_MCP_SERVER_PORT", "8002"))
        )
    
    def get_gitlab_url(self) -> str:
        """Get GitLab MCP server URL."""
        if self.gitlab_server_url:
            return self.gitlab_server_url
        return f"http://{self.gitlab_server_host}:{self.gitlab_server_port}/mcp/sse"
    
    def get_sharepoint_url(self) -> str:
        """Get SharePoint MCP server URL."""
        if self.sharepoint_server_url:
            return self.sharepoint_server_url
        return f"http://{self.sharepoint_server_host}:{self.sharepoint_server_port}/mcp/sse"
    
    def get_combined_url(self) -> str:
        """Get combined MCP server URL."""
        if self.combined_server_url:
            return self.combined_server_url
        return f"http://{self.combined_server_host}:{self.combined_server_port}/mcp/sse"

@dataclass
class AppConfig:
    """Application configuration."""
    gitlab: GitLabConfig
    openai: OpenAIConfig
    sharepoint: Optional[SharePointConfig] = None
    mcp: Optional[MCPConfig] = None
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Create application configuration from environment variables."""
        config = cls(
            gitlab=GitLabConfig.from_env(),
            openai=OpenAIConfig.from_env(),
            mcp=MCPConfig.from_env()
        )
        
        # SharePoint is optional - only load if configured
        try:
            config.sharepoint = SharePointConfig.from_env()
        except ValueError:
            # SharePoint not configured - that's okay
            config.sharepoint = None
        
        return config
    
    def has_sharepoint(self) -> bool:
        """Check if SharePoint is configured."""
        return self.sharepoint is not None and self.sharepoint.validate()
    
    def get(self, key: str, default=None):
        """Get configuration value by key (for backward compatibility)."""
        # Support legacy access patterns
        if key == "sharepoint_site_url" and self.sharepoint:
            return self.sharepoint.site_url
        elif key == "sharepoint_username" and self.sharepoint:
            return self.sharepoint.username
        elif key == "sharepoint_password" and self.sharepoint:
            return self.sharepoint.password
        elif key == "sharepoint_client_id" and self.sharepoint:
            return self.sharepoint.client_id
        elif key == "sharepoint_client_secret" and self.sharepoint:
            return self.sharepoint.client_secret
        
        # For any other keys, check environment variables
        return os.getenv(key.upper(), default)
    
    def validate(self) -> dict:
        """Validate all configurations."""
        results = {
            "gitlab": True,  # GitLab is required
            "openai": True,  # OpenAI is required
            "sharepoint": self.has_sharepoint(),
            "mcp": self.mcp is not None
        }
        
        return results
    
    def get_summary(self) -> dict:
        """Get configuration summary for debugging."""
        return {
            "gitlab": {
                "url": self.gitlab.url,
                "projects": len(self.gitlab.project_ids)
            },
            "openai": {
                "configured": bool(self.openai.api_key)
            },
            "sharepoint": {
                "configured": self.has_sharepoint(),
                "site_url": self.sharepoint.site_url if self.sharepoint else None,
                "auth_type": self.sharepoint.get_auth_type() if self.sharepoint else None
            },
            "mcp": {
                "gitlab_url": self.mcp.get_gitlab_url() if self.mcp else None,
                "sharepoint_url": self.mcp.get_sharepoint_url() if self.mcp else None,
                "combined_url": self.mcp.get_combined_url() if self.mcp else None
            }
        }