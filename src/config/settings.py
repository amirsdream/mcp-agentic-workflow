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
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: str = "http://localhost:8501"
    
    @classmethod
    def from_env(cls) -> 'GitLabConfig':
        """Create configuration from environment variables."""
        url = os.getenv("GITLAB_URL", "https://gitlab.com")
        token = os.getenv("GITLAB_TOKEN", "")
        project_ids_str = os.getenv("GITLAB_PROJECT_IDS", "")
        client_id = os.getenv("GITLAB_CLIENT_ID")
        client_secret = os.getenv("GITLAB_CLIENT_SECRET")
        redirect_uri = os.getenv("GITLAB_REDIRECT_URI", "http://localhost:8501")
        
        if not token:
            raise ValueError("GITLAB_TOKEN environment variable is required")
        
        project_ids = [
            pid.strip() 
            for pid in project_ids_str.split(",") 
            if pid.strip()
        ]
        
        if not project_ids:
            raise ValueError("GITLAB_PROJECT_IDS environment variable is required")
        
        return cls(
            url=url, 
            token=token, 
            project_ids=project_ids,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )

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
class AppConfig:
    """Application configuration."""
    gitlab: GitLabConfig
    openai: OpenAIConfig
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Create application configuration from environment variables."""
        return cls(
            gitlab=GitLabConfig.from_env(),
            openai=OpenAIConfig.from_env()
        )