import pytest
import os
from unittest.mock import patch
from src.config.settings import GitLabConfig, OpenAIConfig, AppConfig

class TestConfig:
    """Test configuration management."""
    
    def test_gitlab_config_from_env_success(self):
        """Test successful GitLab config creation."""
        with patch.dict(os.environ, {
            'GITLAB_URL': 'https://gitlab.example.com',
            'GITLAB_TOKEN': 'test-token',
            'GITLAB_PROJECT_IDS': '123,456,789'
        }):
            config = GitLabConfig.from_env()
            
            assert config.url == 'https://gitlab.example.com'
            assert config.token == 'test-token'
            assert config.project_ids == ['123', '456', '789']
    
    def test_gitlab_config_default_url(self):
        """Test GitLab config with default URL."""
        with patch.dict(os.environ, {
            'GITLAB_TOKEN': 'test-token',
            'GITLAB_PROJECT_IDS': '123'
        }, clear=True):
            config = GitLabConfig.from_env()
            assert config.url == 'https://gitlab.com'
    
    def test_gitlab_config_missing_token(self):
        """Test GitLab config fails without token."""
        with patch.dict(os.environ, {
            'GITLAB_PROJECT_IDS': '123'
        }, clear=True):
            with pytest.raises(ValueError, match="GITLAB_TOKEN"):
                GitLabConfig.from_env()
    
    def test_gitlab_config_missing_projects(self):
        """Test GitLab config fails without projects."""
        with patch.dict(os.environ, {
            'GITLAB_TOKEN': 'test-token'
        }, clear=True):
            with pytest.raises(ValueError, match="GITLAB_PROJECT_IDS"):
                GitLabConfig.from_env()
    
    def test_gitlab_config_empty_projects(self):
        """Test GitLab config fails with empty projects."""
        with patch.dict(os.environ, {
            'GITLAB_TOKEN': 'test-token',
            'GITLAB_PROJECT_IDS': '   ,  , '
        }):
            with pytest.raises(ValueError, match="GITLAB_PROJECT_IDS"):
                GitLabConfig.from_env()
    
    def test_openai_config_success(self):
        """Test successful OpenAI config creation."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test-key'
        }):
            config = OpenAIConfig.from_env()
            assert config.api_key == 'sk-test-key'
    
    def test_openai_config_missing_key(self):
        """Test OpenAI config fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIConfig.from_env()
    
    def test_app_config_success(self):
        """Test successful app config creation."""
        with patch.dict(os.environ, {
            'GITLAB_TOKEN': 'test-token',
            'GITLAB_PROJECT_IDS': '123',
            'OPENAI_API_KEY': 'sk-test-key'
        }):
            config = AppConfig.from_env()
            
            assert config.gitlab.token == 'test-token'
            assert config.openai.api_key == 'sk-test-key'
