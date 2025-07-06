from typing import Optional, Dict, Any
from ..config.sharepoint_settings import SharePointConfig

try:
    from office365.runtime.auth.authentication_context import AuthenticationContext
    from office365.sharepoint.client_context import ClientContext
    from office365.runtime.client_request_exception import ClientRequestException
except ImportError:
    raise ImportError(
        "SharePoint client requires office365-rest-python-client. "
        "Install with: pip install Office365-REST-Python-Client"
    )


class SharePointClientManager:
    """Manages SharePoint client connection - similar to GitLabClientManager."""
    
    def __init__(self, config: SharePointConfig):
        self.config = config
        self._client: Optional[ClientContext] = None
        self._auth_context: Optional[AuthenticationContext] = None
    
    @property
    def client(self) -> ClientContext:
        """Get authenticated SharePoint client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    def _create_client(self) -> ClientContext:
        """Create and authenticate SharePoint client."""
        try:
            # Create authentication context
            self._auth_context = AuthenticationContext(self.config.site_url)
            
            # Authenticate based on config
            if self.config.client_id and self.config.client_secret:
                # App-only authentication (recommended for production)
                self._auth_context.acquire_token_for_app(
                    client_id=self.config.client_id,
                    client_secret=self.config.client_secret
                )
            elif self.config.username and self.config.password:
                # User authentication
                self._auth_context.acquire_token_for_user(
                    username=self.config.username,
                    password=self.config.password
                )
            else:
                raise ValueError("Either client_id/client_secret or username/password must be provided")
            
            # Create client context
            client = ClientContext(self.config.site_url, self._auth_context)
            
            # Test the connection
            web = client.web
            client.load(web)
            client.execute_query()
            
            return client
            
        except ClientRequestException as e:
            raise ConnectionError(f"SharePoint API error: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to SharePoint: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test SharePoint connection."""
        try:
            web = self.client.web
            self.client.load(web)
            self.client.execute_query()
            return True
        except Exception:
            return False
    
    def get_site_info(self) -> Dict[str, Any]:
        """Get basic site information."""
        try:
            web = self.client.web
            self.client.load(web)
            self.client.execute_query()
            
            return {
                "title": web.title,
                "url": web.url,
                "description": web.description,
                "created": str(web.created),
                "server_relative_url": web.server_relative_url
            }
        except Exception as e:
            return {"error": str(e)}
    
    def reconnect(self) -> bool:
        """Force reconnection to SharePoint."""
        try:
            self._client = None
            self._auth_context = None
            _ = self.client  # This will trigger a new connection
            return True
        except Exception:
            return False