from setuptools import setup, find_packages

setup(
    name="gitlab-issues-mcp",
    version="1.0.0",
    description="Professional GitLab Issues Management with FastMCP",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=[
        "fastmcp>=2.0.0",
        "openai>=1.0.0", 
        "python-gitlab>=4.0.0",
        "python-dotenv>=0.19.0",
        "streamlit>=1.28.0",
        "pandas>=1.5.0"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=1.0.0"
        ]
    },
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "gitlab-mcp-server=run_server:main",
            "gitlab-mcp-app=run_app:main"
        ]
    }
)