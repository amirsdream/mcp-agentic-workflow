
#!/usr/bin/env python3
"""
GitLab Issues Streamlit App Runner
"""

import sys
import os
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Main entry point for Streamlit app."""
    try:
        from src.ui.streamlit_app import GitLabIssuesApp
        
        # Create and run app
        app = GitLabIssuesApp()
        app.run()
        
    except ValueError as e:
        import streamlit as st
        st.error(f"Configuration error: {e}")
        st.markdown("""
        ### Required Environment Variables:
        - `OPENAI_API_KEY`
        - `GITLAB_TOKEN`
        - `GITLAB_PROJECT_IDS` (comma-separated)
        - `GITLAB_URL` (optional, defaults to https://gitlab.com)
        """)
        st.stop()
    except Exception as e:
        import streamlit as st
        st.error(f"Application error: {e}")
        st.stop()

if __name__ == "__main__":
    main()