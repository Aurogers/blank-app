import streamlit as st
import pandas as pd
import gspread
import json
import os
from google.oauth2 import service_account

# Configuration and setup
st.set_page_config(
    page_title="TV Show Dashboard",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Get credentials from environment, secrets, or file
def get_credentials():
    # Option 1: Check for environment variable
    if os.environ.get('GOOGLE_CREDENTIALS'):
        try:
            return json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
        except json.JSONDecodeError:
            st.error("Invalid JSON in GOOGLE_CREDENTIALS environment variable")
    
    # Option 2: Check for Streamlit secrets
    elif hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
        return st.secrets["gcp_service_account"]
    
    # Option 3: Check for local file
    else:
        try:
            with open('credentials.json') as f:
                return json.load(f)
        except FileNotFoundError:
            st.error("No Google credentials found. Please set GOOGLE_CREDENTIALS environment variable, add to Streamlit secrets, or provide a credentials.json file.")
            st.stop()

# Connect to Google Sheets
def connect_sheets():
    try:
        creds_dict = get_credentials()
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
        client = gspread.authorize(credentials)
        return client.open("My Favorite TV Shows")
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None
