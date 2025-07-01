"""
Streamlit GitLab Chatbot - Web interface for GitLab interactions using AutoGen and MCP
"""

import asyncio
import os
import streamlit as st
import json
from typing import Dict, Any, List
import logging
from datetime import datetime

# Import our custom modules (ensure they're in the same directory or Python path)
from autogen_gitlab_agent import GitLabAssistant

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="GitLab Assistant",
    page_icon="🦊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #FC6D26;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
    }
    .user-message {
        background-color: #E3F2FD;
        border-left: 4px solid #2196F3;
    }
    .assistant-message {
        background-color: #F3E5F5;
        border-left: 4px solid #9C27B0;
    }
    .sidebar-section {
        background-color: #F8F9FA;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

class StreamlitGitLabChatbot:
    """Streamlit interface for GitLab chatbot"""
    
    def __init__(self):
        self.assistant = None
        self.initialize_session_state()
    
    def initialize_session_state(self):
        """Initialize Streamlit session state"""
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'assistant_initialized' not in st.session_state:
            st.session_state.assistant_initialized = False
        if 'gitlab_config' not in st.session_state:
            st.session_state.gitlab_config = {}
    
    def render_sidebar(self):
        """Render the sidebar with configuration options"""
        st.sidebar.title("🦊 GitLab Configuration")
        
        with st.sidebar.container():
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            
            # GitLab configuration
            st.subheader("Connection Settings")
            
            gitlab_url = st.text_input(
                "GitLab URL",
                value=st.session_state.gitlab_config.get("url", "https://gitlab.com"),
                help="Your GitLab instance URL"
            )
            
            gitlab_token = st.text_input(
                "GitLab Token",
                type="password",
                value=st.session_state.gitlab_config.get("token", ""),
                help="Your GitLab personal access token"
            )
            
            openai_api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                value=st.session_state.gitlab_config.get("openai_key", ""),
                help="Your OpenAI API key for the LLM"
            )
            
            # Model selection
            model_options = ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"]
            selected_model = st.selectbox(
                "LLM Model",
                options=model_options,
                index=0,
                help="Choose the language model to use"
            )
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Connection status
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.subheader("Connection Status")
            
            if st.session_state.assistant_initialized:
                st.markdown('<p class="status-success">✅ Connected</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p class="status-error">❌ Not Connected</p>', unsafe_allow_html=True)
            
            # Initialize/Update connection
            if st.button("Connect to GitLab", type="primary"):
                if gitlab_url and gitlab_token and openai_api_key:
                    with st.spinner("Connecting to GitLab..."):
                        success = asyncio.run(self.initialize_assistant(
                            gitlab_url, gitlab_token, openai_api_key, selected_model
                        ))
                        if success:
                            st.success("Connected successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to connect. Please check your credentials.")
                else:
                    st.error("Please fill in all required fields.")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Quick actions
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.subheader("Quick Actions")
            
            if st.button("📋 List Projects"):
                self.add_predefined_message("List my GitLab projects")
            
            if st.button("🐛 List Issues"):
                self.add_predefined_message("Show me recent issues across my projects")
            
            if st.button("🔄 List Merge Requests"):
                self.add_predefined_message("Show me open merge requests")
            
            if st.button("🗂️ Get Project Info"):
                project_id = st.text_input("Project ID/Path:", key="quick_project_id")
                if project_id:
                    self.add_predefined_message(f"Get details for project '{project_id}'")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Chat controls
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.subheader("Chat Controls")
            
            if st.button("🗑️ Clear Chat"):
                st.session_state.chat_history = []
                st.rerun()
            
            if st.button("💾 Export Chat"):
                self.export_chat_history()
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    async def initialize_assistant(self, gitlab_url: str, gitlab_token: str, 
                                 openai_key: str, model: str) -> bool:
        """Initialize the GitLab assistant"""
        try:
            # Set environment variables
            os.environ["GITLAB_URL"] = gitlab_url
            os.environ["GITLAB_TOKEN"] = gitlab_token
            os.environ["OPENAI_API_KEY"] = openai_key
            
            # Configure LLM
            llm_config = {
                "config_list": [
                    {
                        "model": model,
                        "api_key": openai_key,
                    }
                ],
                "temperature": 0.1,
            }
            
            # Create and initialize assistant
            self.assistant = GitLabAssistant(llm_config)
            await self.assistant.initialize()
            
            # Update session state
            st.session_state.gitlab_config = {
                "url": gitlab_url,
                "token": gitlab_token,
                "openai_key": openai_key,
                "model": model
            }
            st.session_state.assistant_initialized = True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize assistant: {e}")
            st.session_state.assistant_initialized = False
            return False
    
    def add_predefined_message(self, message: str):
        """Add a predefined message to chat"""
        if st.session_state.assistant_initialized:
            # Add user message to history
            st.session_state.chat_history.append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            st.rerun()
    
    def export_chat_history(self):
        """Export chat history as JSON"""
        if st.session_state.chat_history:
            chat_data = {
                "export_date": datetime.now().isoformat(),
                "chat_history": st.session_state.chat_history
            }
            
            st.download_button(
                label="Download Chat History",
                data=json.dumps(chat_data, indent=2),
                file_name=f"gitlab_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        else:
            st.warning("No chat history to export.")
    
    def render_chat_interface(self):
        """Render the main chat interface"""
        st.markdown('<h1 class="main-header">🦊 GitLab Assistant</h1>', unsafe_allow_html=True)
        
        if not st.session_state.assistant_initialized:
            st.warning("⚠️ Please configure and connect to GitLab using the sidebar.")
            st.info("""
            **To get started:**
            1. Enter your GitLab URL and personal access token in the sidebar
            2. Add your OpenAI API key
            3. Click 'Connect to GitLab'
            4. Start chatting with your GitLab assistant!
            
            **What you can do:**
            - List and search projects
            - Create and manage issues
            - View and create merge requests
            - Read file contents from repositories
            - Get project information and statistics
            """)
            return
        
        # Chat history display
        chat_container = st.container()
        
        with chat_container:
            if st.session_state.chat_history:
                for message in st.session_state.chat_history:
                    self.render_message(message)
            else:
                st.info("👋 Welcome! Ask me anything about your GitLab projects. Try saying 'List my projects' or 'Show me recent issues'.")
        
        # Chat input
        with st.form("chat_form", clear_on_submit=True):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                user_input = st.text_input(
                    "Ask about your GitLab projects...",
                    placeholder="e.g., 'List my projects', 'Create an issue in project X', 'Show merge requests'",
                    label_visibility="collapsed"
                )
            
            with col2:
                submit_button = st.form_submit_button("Send", type="primary")
            
            if submit_button and user_input.strip():
                # Add user message
                user_message = {
                    "role": "user",
                    "content": user_input,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                st.session_state.chat_history.append(user_message)
                
                # Get assistant response
                with st.spinner("🤖 Processing your request..."):
                    try:
                        response = asyncio.run(self.assistant.chat(user_input))
                        
                        assistant_message = {
                            "role": "assistant",
                            "content": response,
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        }
                        st.session_state.chat_history.append(assistant_message)
                        
                    except Exception as e:
                        error_message = {
                            "role": "assistant",
                            "content": f"Sorry, I encountered an error: {str(e)}",
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        }
                        st.session_state.chat_history.append(error_message)
                
                st.rerun()
    
    def render_message(self, message: Dict[str, Any]):
        """Render a single chat message"""
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")
        
        if role == "user":
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>🧑‍💻 You</strong> <small>({timestamp})</small><br>
                {content}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message assistant-message">
                <strong>🤖 GitLab Assistant</strong> <small>({timestamp})</small><br>
                {content}
            </div>
            """, unsafe_allow_html=True)
    
    def run(self):
        """Main application entry point"""
        self.render_sidebar()
        self.render_chat_interface()

# Example commands and help
def show_help_section():
    """Show help and example commands"""
    with st.expander("ℹ️ Help & Example Commands"):
        st.markdown("""
        ### 🚀 Getting Started
        1. Configure your GitLab credentials in the sidebar
        2. Connect to GitLab
        3. Start asking questions!
        
        ### 💬 Example Commands
        
        **Project Management:**
        - "List my GitLab projects"
        - "Show me details for project 'my-repo'"
        - "Search for projects containing 'api'"
        
        **Issues:**
        - "Show me open issues in project 123"
        - "Create an issue titled 'Bug fix' in project 'my-repo'"
        - "List all issues across my projects"
        
        **Merge Requests:**
        - "Show merge requests for project 'my-repo'"
        - "Create a merge request from 'feature-branch' to 'main' in project 123"
        - "List all open merge requests"
        
        **Files & Code:**
        - "Show me the content of README.md from project 'my-repo'"
        - "Get the package.json file from the main branch of project 123"
        
        ### 🔧 Tips
        - Use project IDs (numbers) or project paths (group/project-name)
        - Be specific about which project you're referring to
        - The assistant can handle multiple operations in one request
        """)

# Main application
def main():
    """Main application function"""
    try:
        chatbot = StreamlitGitLabChatbot()
        chatbot.run()
        
        # Add help section at the bottom
        show_help_section()
        
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        logger.error(f"Streamlit app error: {e}")

if __name__ == "__main__":
    main()