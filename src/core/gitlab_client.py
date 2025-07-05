import gitlab
from typing import Optional
from ..config.settings import GitLabConfig

class GitLabClientManager:
    """Manages GitLab client connection."""
    
    def __init__(self, config: GitLabConfig):
        self.config = config
        self._client: Optional[gitlab.Gitlab] = None
    
    @property
    def client(self) -> gitlab.Gitlab:
        """Get authenticated GitLab client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    def _create_client(self) -> gitlab.Gitlab:
        """Create and authenticate GitLab client."""
        try:
            gl = gitlab.Gitlab(self.config.url, private_token=self.config.token)
            gl.auth()
            return gl
        except Exception as e:
            raise ConnectionError(f"Failed to connect to GitLab: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test GitLab connection."""
        try:
            _ = self.client.user
            return True
        except Exception:
            return False
