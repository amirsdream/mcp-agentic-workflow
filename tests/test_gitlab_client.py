
import pytest
from unittest.mock import Mock, patch
from src.core.gitlab_client import GitLabClientManager
from src.config.settings import GitLabConfig

class TestGitLabClientManager:
    """Test GitLab client management."""
    
    @pytest.fixture
    def gitlab_config(self):
        return GitLabConfig(
            url="https://gitlab.example.com",
            token="test-token",
            project_ids=["123"]
        )
    
    @patch('src.core.gitlab_client.gitlab.Gitlab')
    def test_client_creation_success(self, mock_gitlab_class, gitlab_config):
        """Test successful client creation."""
        mock_gitlab_instance = Mock()
        mock_gitlab_class.return_value = mock_gitlab_instance
        
        manager = GitLabClientManager(gitlab_config)
        client = manager.client
        
        mock_gitlab_class.assert_called_once_with(
            "https://gitlab.example.com",
            private_token="test-token"
        )
        mock_gitlab_instance.auth.assert_called_once()
        assert client == mock_gitlab_instance
    
    @patch('src.core.gitlab_client.gitlab.Gitlab')
    def test_client_creation_failure(self, mock_gitlab_class, gitlab_config):
        """Test client creation failure."""
        mock_gitlab_class.side_effect = Exception("Connection failed")
        
        manager = GitLabClientManager(gitlab_config)
        
        with pytest.raises(ConnectionError, match="Failed to connect to GitLab"):
            _ = manager.client
    
    @patch('src.core.gitlab_client.gitlab.Gitlab')
    def test_client_caching(self, mock_gitlab_class, gitlab_config):
        """Test that client is cached after first creation."""
        mock_gitlab_instance = Mock()
        mock_gitlab_class.return_value = mock_gitlab_instance
        
        manager = GitLabClientManager(gitlab_config)
        
        # Access client multiple times
        client1 = manager.client
        client2 = manager.client
        
        # Should only create once
        mock_gitlab_class.assert_called_once()
        assert client1 is client2
    
    @patch('src.core.gitlab_client.gitlab.Gitlab')
    def test_test_connection_success(self, mock_gitlab_class, gitlab_config):
        """Test successful connection test."""
        mock_gitlab_instance = Mock()
        mock_gitlab_instance.user = Mock()
        mock_gitlab_class.return_value = mock_gitlab_instance
        
        manager = GitLabClientManager(gitlab_config)
        result = manager.test_connection()
        
        assert result is True
    
    # @patch('src.core.gitlab_client.gitlab.Gitlab')
    # def test_test_connection_failure(self, mock_gitlab_class, gitlab_config):
    #     """Test connection test failure."""
    #     mock_gitlab_instance = Mock()
    #     mock_gitlab_instance.user = Mock(side_effect=Exception("Auth failed"))
    #     mock_gitlab_class.return_value = mock_gitlab_instance
        
    #     manager = GitLabClientManager(gitlab_config)
    #     result = manager.test_connection()
        
    #     assert result is False