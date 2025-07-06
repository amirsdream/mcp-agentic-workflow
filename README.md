# GitLab + SharePoint Multi-Agent Assistant

Professional GitLab Issues and SharePoint Forms Management with FastMCP, LangGraph Multi-Agents, and Streamlit.

## Features

### 🤖 **Multi-Agent Architecture**
- **User Proxy Agent** - Intelligent query analysis and user interaction
- **GitLab Agent** - Specialized GitLab issues management
- **SharePoint Agent** - SharePoint forms and lists management
- **LangGraph Workflow** - Orchestrated agent communication

### 🦊 **GitLab Integration**
- Connect to any GitLab instance
- Natural language issue queries
- Smart filtering by month, labels, assignee, state
- Professional issue displays and summaries

### 📋 **SharePoint Integration**
- Connect to SharePoint Online sites
- Browse forms and lists with filtering
- User-based and date-based queries
- Rich form field displays

### ⚡ **AI-Powered Experience**
- OpenAI GPT-4o for intelligent query processing
- Natural language understanding
- Multi-system queries ("show me issues and forms from this month")
- Smart agent routing and fallback mechanisms

### 🏗️ **Professional Architecture**
- Clean, modular, testable code
- FastMCP server implementation
- Multiple deployment options
- Comprehensive error handling

## Project Structure

```
gitlab-issues-mcp/
├── src/
│   ├── config/              # Configuration management
│   │   ├── settings.py      # Main app configuration
│   │   └── sharepoint_settings.py  # SharePoint-specific config
│   ├── core/                # Core utilities and clients
│   │   ├── mcp_client.py    # Enhanced MCP client with multi-server support
│   │   ├── sharepoint_manager.py   # SharePoint client manager
│   │   └── sharepoint_client.py    # SharePoint operations client
│   ├── models/              # Data models
│   │   ├── gitlab_models.py # GitLab and multi-agent models
│   │   └── sharepoint_models.py    # SharePoint-specific models
│   ├── services/            # Business logic
│   │   ├── agents.py        # Multi-agent implementations
│   │   ├── workflow.py      # LangGraph workflow service
│   │   ├── tools.py         # OpenAI tools service (fallback)
│   │   └── sharepoint_service.py   # SharePoint service layer
│   ├── mcp/                 # FastMCP servers
│   │   ├── sharepoint_server.py    # SharePoint MCP server
│   │   └── combined_server.py      # Combined GitLab + SharePoint server
│   └── ui/                  # Streamlit interface
│       └── streamlit_app.py # Multi-agent UI with dual system support
├── tests/                   # Unit tests
├── run_server.py           # GitLab MCP server runner
├── run_sharepoint_server.py # SharePoint MCP server runner
├── run_combined_server.py  # Combined MCP server runner
├── run_app.py              # Streamlit multi-agent app runner
└── requirements.txt         # Dependencies (updated with SharePoint libs)
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials (see Configuration section)
```

### 3. Choose Your Deployment

#### Option A: Combined Server (Recommended)
```bash
# Terminal 1: Start combined server
python run_combined_server.py --transport http --port 8002

# Terminal 2: Start the app
python run_app.py
```

#### Option B: Separate Servers
```bash
# Terminal 1: GitLab server
python run_server.py --transport http --port 8000

# Terminal 2: SharePoint server
python run_sharepoint_server.py --transport http --port 8001

# Terminal 3: Start the app
python run_app.py
```

### 4. Open Your Browser
Navigate to the Streamlit URL (typically `http://localhost:8501`)

## Usage Examples

### 🎯 **Quick Actions (UI Buttons)**
- **GitLab**: "This Month Issues", "High Priority", "Bugs", "My Issues"
- **SharePoint**: "Recent Forms", "Forms This Month", "All Lists", "My Forms"
- **Combined**: "Both Systems" - queries both GitLab and SharePoint

### 💬 **Natural Language Queries**

#### GitLab Queries:
```
"Show me issues from January"
"What bugs do we have this month?"
"Last month's high priority issues"
"Show me closed issues assigned to John"
```

#### SharePoint Queries:
```
"Show me recent SharePoint forms"
"Forms from this month"
"Show me all SharePoint lists"
"Form 123 from SharePoint"
"Forms created by John"
```

#### Combined Queries:
```
"Show me both GitLab issues and SharePoint forms from this month"
"Issues and forms from last week"
"Give me a summary of issues and forms"
```

## Configuration

### Required Environment Variables

#### Core Settings
```env
OPENAI_API_KEY=your_openai_api_key_here
```

#### GitLab Configuration
```env
GITLAB_TOKEN=your_gitlab_token_here
GITLAB_PROJECT_IDS=12345,67890,11111
GITLAB_URL=https://gitlab.com  # optional, defaults to gitlab.com
```

#### SharePoint Configuration
```env
SHAREPOINT_SITE_URL=https://your-tenant.sharepoint.com/sites/your-site
SHAREPOINT_USERNAME=your-username@your-tenant.com
SHAREPOINT_PASSWORD=your-password

# OR use app authentication (recommended for production)
SHAREPOINT_CLIENT_ID=your-app-client-id
SHAREPOINT_CLIENT_SECRET=your-app-client-secret
SHAREPOINT_TENANT_ID=your-tenant-id
```

### MCP Server Configuration (Optional)

#### For Remote Deployment:
```env
GITLAB_MCP_SERVER_URL=https://gitlab-mcp.yourcompany.com/mcp/sse
SHAREPOINT_MCP_SERVER_URL=https://sharepoint-mcp.yourcompany.com/mcp/sse
COMBINED_MCP_SERVER_URL=https://combined-mcp.yourcompany.com/mcp/sse
```

#### For Docker/Kubernetes:
```env
GITLAB_MCP_SERVER_HOST=gitlab-mcp-server
GITLAB_MCP_SERVER_PORT=8000
SHAREPOINT_MCP_SERVER_HOST=sharepoint-mcp-server
SHAREPOINT_MCP_SERVER_PORT=8001
```

## Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black src/ tests/
```

### Type Checking
```bash
mypy src/
```

### Adding New Agents
1. Create agent class in `src/services/agents.py`
2. Add to `AgentOrchestrator`
3. Update workflow in `src/services/workflow.py`
4. Add UI components in `src/ui/streamlit_app.py`

## Architecture

### 🤖 **Multi-Agent System**
- **User Proxy Agent**: Analyzes queries, routes to appropriate agents
- **GitLab Agent**: Handles GitLab operations with MCP tools
- **SharePoint Agent**: Manages SharePoint forms and lists
- **Workflow Service**: LangGraph-based agent orchestration

### 🔧 **Core Components**
- **Configuration Layer**: Environment-based configuration management
- **Client Managers**: GitLab and SharePoint client management
- **Service Layer**: Business logic and API interactions
- **MCP Layer**: FastMCP server implementations
- **UI Layer**: Multi-agent Streamlit interface

### 📊 **Data Flow**
```
User Query → User Proxy Agent → Intent Analysis
                ↓
    GitLab Agent ← Router → SharePoint Agent
         ↓                        ↓
    MCP Client            SharePoint Client
         ↓                        ↓
    GitLab API            SharePoint API
         ↓                        ↓
    Formatted Response ← Aggregator → Formatted Response
                ↓
            Streamlit UI
```

## Deployment Options

### 🏠 **Development**
- Local servers with stdio transport
- Hot reloading for rapid development
- Detailed logging and debugging

### 🐳 **Production (Docker)**
```dockerfile
FROM python:3.11-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python", "run_combined_server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
```

### ☁️ **Cloud Deployment**
- Deploy MCP servers as microservices
- Use environment variables for configuration
- Load balancing with multiple server instances

## Troubleshooting

### Common Issues

#### SharePoint Connection Issues:
```bash
# Check SharePoint package installation
pip install Office365-REST-Python-Client

# Verify credentials
python -c "from src.config.sharepoint_settings import SharePointConfig; print(SharePointConfig.from_env().validate())"
```

#### MCP Server Connection Issues:
```bash
# Check server status
curl http://localhost:8002/health

# Verify server URLs
python -c "from src.core.mcp_client import MCPClientManager; print(MCPClientManager().get_server_urls())"
```

#### Agent Workflow Issues:
- Check OpenAI API key and rate limits
- Verify LangGraph dependencies: `pip install langgraph langchain-openai langchain-core`
- Review agent logs in Streamlit interface

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure code passes linting and tests
5. Submit a pull request

## License

MIT License

## Changelog

### v2.0.0 (Latest)
- ✨ Added SharePoint Agent with forms and lists support
- ✨ Implemented LangGraph multi-agent workflow
- ✨ Added User Proxy Agent for intelligent query routing
- ✨ Combined MCP server for unified deployments
- ✨ Enhanced UI with dual-system support
- 🔧 Improved error handling and fallback mechanisms
- 📚 Comprehensive documentation and examples

### v1.0.0
- 🦊 Initial GitLab Issues management
- ⚡ FastMCP server implementation
- 🤖 OpenAI integration
- 📊 Streamlit UI