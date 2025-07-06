import streamlit as st
import requests
import urllib.parse
import secrets

# GitLab OAuth2 Config - UPDATE THESE VALUES

GITLAB_URL = "https://gitlab.com"  # or your GitLab instance URL
REDIRECT_URI = "http://localhost:8501"

def gitlab_auth():
    """Simple GitLab OAuth2 authentication - redirects and grabs token"""
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    
    # Check for OAuth callback (code parameter)
    query_params = st.query_params
    if 'code' in query_params and not st.session_state.authenticated:
        code = query_params['code']
        
        with st.spinner("🔄 Completing authentication..."):
            # Exchange code for token
            token_data = {
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': REDIRECT_URI
            }
            
            try:
                response = requests.post(f"{GITLAB_URL}/oauth/token", data=token_data)
                if response.status_code == 200:
                    token_info = response.json()
                    st.session_state.access_token = token_info['access_token']
                    st.session_state.authenticated = True
                    
                    # Clear URL parameters
                    st.query_params.clear()
                    st.success("✅ Authentication successful!")
                    st.rerun()
                else:
                    st.error(f"Token exchange failed: {response.status_code}")
            except Exception as e:
                st.error(f"Authentication failed: {e}")
    
    # Main UI
    if st.session_state.authenticated:
        # Show authenticated state
        col1, col2 = st.columns([3, 1])
        with col1:
            st.success("✅ Authenticated with GitLab")
        with col2:
            if st.button("🚪 Logout"):
                st.session_state.authenticated = False
                st.session_state.access_token = None
                st.rerun()
        
        # Return token for use in app
        return st.session_state.access_token
    
    else:
        # Show login page
        st.warning("Please authenticate with GitLab to continue")
        
        if st.button("🔑 Login with GitLab"):
            state = secrets.token_urlsafe(16)
            auth_url = f"{GITLAB_URL}/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read_api read_user&state={state}"
            
            # Simple redirect to GitLab
            st.markdown(f'<meta http-equiv="refresh" content="0; url={auth_url}">', unsafe_allow_html=True)
        
        st.stop()  # Stop execution until authenticated

# Usage example - put this at the top of your existing app
if __name__ == "__main__":
    token = gitlab_auth()  # Get token after authentication
    
    # Your existing app code goes here
    st.title("Your App Title")
    st.write("🎉 This content only shows after authentication")
    
    if token:
        st.write(f"**Access token:** `{token[:20]}...`")
        st.write("You can now make GitLab API calls!")
        
        # Example: Get user info
        if st.button("Test API - Get My Profile"):
            headers = {'Authorization': f'Bearer {token}'}
            try:
                response = requests.get(f"{GITLAB_URL}/api/v4/user", headers=headers)
                if response.status_code == 200:
                    user_info = response.json()
                    st.json(user_info)
                else:
                    st.error(f"API call failed: {response.status_code}")
            except Exception as e:
                st.error(f"API error: {e}")