import pytest
from unittest.mock import Mock, patch
from src.services.issue_service import IssueService
from src.models.issue import IssueFilters
from src.config.settings import GitLabConfig

class TestIssueService:
    """Test cases for IssueService."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock GitLab configuration."""
        return GitLabConfig(
            url="https://gitlab.example.com",
            token="test-token",
            project_ids=["123", "456"]
        )
    
    @pytest.fixture
    def issue_service(self, mock_config):
        """Create IssueService with mocked dependencies."""
        with patch('src.services.issue_service.GitLabClientManager'):
            return IssueService(mock_config)
    
    def test_search_issues_success(self, issue_service):
        """Test successful issue search."""
        # Mock GitLab client and responses
        mock_project = Mock()
        mock_project.name = "Test Project"
        mock_project.issues.list.return_value = []
        
        issue_service.gitlab_manager.client.projects.get.return_value = mock_project
        
        filters = IssueFilters(month="January", state="opened")
        result = issue_service.search_issues(filters)
        
        assert result.success is True
        assert result.total_issues == 0
        assert len(result.issues) == 0


    def test_search_issues_all_projects_fail(self, issue_service):
        """Test when all project access fails but GitLab client works."""
        
        issue_service.gitlab_manager.client.projects.get.side_effect = Exception("Project access denied")
        
        filters = IssueFilters()
        result = issue_service.search_issues(filters)
        
        assert result.success is True
        assert result.total_issues == 0
        assert len(result.issues) == 0