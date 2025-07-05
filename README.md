# GitLab Issues MCP

Professional GitLab Issues Management with FastMCP and Streamlit.

## Features

- 🦊 **GitLab Integration** - Connect to any GitLab instance
- 🤖 **AI-Powered** - Natural language queries with OpenAI
- 📊 **Smart Filtering** - Filter by month, labels, assignee, state
- 📋 **Professional Tables** - Clean, formatted issue displays
- 🏗️ **Modular Architecture** - Clean, testable, maintainable code
- ⚡ **FastMCP Powered** - Efficient MCP server implementation

## Project Structure

```
gitlab-issues-mcp/
├── src/
│   ├── config/          # Configuration management
│   ├── core/            # Core utilities (GitLab client, date parsing)
│   ├── models/          # Data models
│   ├── services/        # Business logic
│   ├── mcp/             # FastMCP server
│   └── ui/              # Streamlit interface
├── tests/               # Unit tests
├── run_server.py        # MCP server runner
├── run_app.py          # Streamlit app runner
└── requirements.txt     # Dependencies
```

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. **Run MCP server:**
```bash
python run_server.py
```

4. **Run Streamlit app:**
```bash
streamlit run run_app.py
```

## Usage

### Natural Language Queries:
- "Show me issues from January"
- "What bugs do we have this month?"
- "Last month's high priority issues"
- "Show me closed issues assigned to John"

### Development:

```bash
# Run tests
pytest

# Format code
black src/ tests/

# Type checking
mypy src/

# Install in development mode
pip install -e .[dev]
```

## Configuration

Required environment variables:

- `OPENAI_API_KEY` - Your OpenAI API key
- `GITLAB_TOKEN` - GitLab personal access token
- `GITLAB_PROJECT_IDS` - Comma-separated project IDs/paths
- `GITLAB_URL` - GitLab instance URL (optional, defaults to gitlab.com)

## Architecture

- **Configuration Layer** - Environment-based configuration management
- **Core Layer** - GitLab client and utility functions
- **Model Layer** - Type-safe data models
- **Service Layer** - Business logic and API interactions
- **MCP Layer** - FastMCP server implementation
- **UI Layer** - Streamlit web interface

## License

MIT License