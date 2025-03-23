import streamlit as st
import pandas as pd
# Import visualization libraries only if they're used in a function
# import matplotlib.pyplot as plt 
# import seaborn as sns
# import plotly.express as px
# import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# Configuration and setup
st.set_page_config(
    page_title="TV Show Dashboard",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Check if running on Streamlit Cloud or locally
def is_streamlit_cloud():
    return 'STREAMLIT_SHARING' in os.environ or 'STREAMLIT_RUN_ON_SAVE' in os.environ

# Create a placeholder for Google Sheets credentials
def get_credentials():
    if is_streamlit_cloud():
        # Use secrets in Streamlit Cloud
        return st.secrets["gcp_service_account"]
    else:
        # Use local credentials file
        try:
            with open('credentials.json') as f:
                return json.load(f)
        except FileNotFoundError:
            st.error("credentials.json file not found. Please upload your Google API credentials.")
            st.stop()

# Connect to Google Sheets with proper error handling
@st.cache_resource
def connect_sheets():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Handle credentials based on environment
        if is_streamlit_cloud():
            creds_dict = get_credentials()
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
        client = gspread.authorize(creds)
        return client.open("My Favorite TV Shows")
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None

# Load show data with caching and error handling
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_all_show_data():
    spreadsheet = connect_sheets()
    if not spreadsheet:
        return {}
        
    all_shows = {}
    
    with st.spinner("Loading shows from Google Sheets..."):
        # Get all worksheets (each sheet is a show)
        for sheet in spreadsheet.worksheets():
            try:
                # Skip empty sheets or sheets without proper headers
                if sheet.row_values(1) and 'Show Name' in sheet.row_values(1):
                    data = sheet.get_all_records()
                    if data:
                        all_shows[sheet.title] = pd.DataFrame(data)
            except Exception as e:
                st.warning(f"Couldn't load sheet {sheet.title}: {e}")
                continue
    
    return all_shows

# Simple overview display function (no visualization libraries required)
def display_overview(shows):
    st.header("TV Shows Overview")
    
    if not shows:
        st.warning("No show data available. Please check your Google Sheets connection.")
        return
    
    # Basic statistics
    total_shows = len(shows)
    total_episodes = sum(len(df) for df in shows.values())
    
    # Display in columns
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Shows", total_shows)
    with col2:
        st.metric("Total Episodes", total_episodes)
    
    # Show list
    st.subheader("Your Shows")
    for show_name, df in shows.items():
        with st.expander(f"{show_name} ({len(df)} episodes)"):
            st.dataframe(df.head())

# Main app function
def main():
    st.title("📺 My TV Show Dashboard")
    
    # Show a loading message while checking connection
    with st.spinner("Connecting to Google Sheets..."):
        # Try to load data
        shows = load_all_show_data()
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Overview", "Show Details", "Episode Tracker", "Analysis"])
    
    # Simple display based on navigation
    if page == "Overview":
        display_overview(shows)
    elif page == "Show Details":
        st.info("Show Details page will be implemented next")
        # display_show_details(shows)  # Uncomment when implemented
    elif page == "Episode Tracker":
        st.info("Episode Tracker page will be implemented next") 
        # display_episode_tracker(shows)  # Uncomment when implemented
    else:
        st.info("Analysis page will be implemented next")
        # display_analysis(shows)  # Uncomment when implemented

# Run the app
if __name__ == "__main__":
    main()
