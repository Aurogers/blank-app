import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import plotly.graph_objects as go

# Connect to Google Sheets (same as your scraper)
def connect_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open("My Favorite TV Shows")

# Load all show data into pandas DataFrames
def load_all_show_data():
    spreadsheet = connect_sheets()
    all_shows = {}
    
    # Get all worksheets (each sheet is a show)
    for sheet in spreadsheet.worksheets():
        try:
            # Skip empty sheets or sheets without proper headers
            if sheet.row_values(1) and 'Show Name' in sheet.row_values(1):
                data = sheet.get_all_records()
                if data:
                    all_shows[sheet.title] = pd.DataFrame(data)
        except:
            continue
    
    return all_shows

# Main dashboard
def main():
    st.title("My TV Show Dashboard")
    
    # Load data
    shows = load_all_show_data()
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Overview", "Show Details", "Episode Tracker", "Analysis"])
    
    if page == "Overview":
        display_overview(shows)
    elif page == "Show Details":
        display_show_details(shows)
    elif page == "Episode Tracker":
        display_episode_tracker(shows)
    else:
        display_analysis(shows)

# Run the app
if __name__ == "__main__":
    main()
