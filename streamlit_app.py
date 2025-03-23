import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
import gspread
import json
import os
from datetime import datetime
from google.oauth2 import service_account

# Configuration and setup
st.set_page_config(
    page_title="TV Show Dashboard",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Debug line to check credentials loading
st.write("Looking for Google credentials...")

# Get credentials from environment, secrets, or file
def get_credentials():
    # Option 1: Check for environment variable
    if os.environ.get('GOOGLE_CREDENTIALS'):
        st.success("Found credentials in environment variable")
        try:
            return json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
        except json.JSONDecodeError:
            st.error("Invalid JSON in GOOGLE_CREDENTIALS environment variable")
    
    # Option 2: Check for Streamlit secrets
    elif hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
        st.success("Found credentials in Streamlit secrets")
        return st.secrets["gcp_service_account"]
    
    # Option 3: Check for local file
    else:
        try:
            with open('credentials.json') as f:
                st.success("Found credentials in credentials.json file")
                return json.load(f)
        except FileNotFoundError:
            st.error("No Google credentials found. Please set GOOGLE_CREDENTIALS environment variable, add to Streamlit secrets, or provide a credentials.json file.")
            st.stop()

# Connect to Google Sheets
@st.cache_resource
def connect_sheets():
    try:
        # Check for secrets in Streamlit
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            st.success("Using Streamlit secrets")
            creds_dict = st.secrets["gcp_service_account"]
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            )
            client = gspread.authorize(credentials)
            return client.open("My Favorite TV Shows")
        else:
            st.error("No credentials found. Please add service account credentials to Streamlit secrets.")
            return None
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None

# Load show data with caching and error handling
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_all_show_data():
    spreadsheet = connect_sheets()
    if not spreadsheet:
        return {}, {}
        
    all_shows = {}
    show_metadata = {}
    
    with st.spinner("Loading shows from Google Sheets..."):
        # Get all worksheets (each sheet is a show)
        for sheet in spreadsheet.worksheets():
            try:
                # Skip empty sheets or sheets without proper headers
                header_row = sheet.row_values(1)
                if header_row and 'Show Name' in header_row:
                    data = sheet.get_all_records()
                    if data:
                        df = pd.DataFrame(data)
                        
                        # Extract metadata from the first row
                        first_row = df.iloc[0] if not df.empty else None
                        
                        if first_row is not None and 'Show Name' in df.columns:
                            show_name = first_row['Show Name']
                            # Store metadata for this show
                            show_metadata[sheet.title] = {
                                'title': show_name,
                                'total_episodes': len(df),
                                'seasons': df['Season'].nunique() if 'Season' in df.columns else 0,
                                'average_rating': df['Rating'].mean() if 'Rating' in df.columns and df['Rating'].notna().any() else None,
                                'longest_episode': df['Runtime'].max() if 'Runtime' in df.columns and df['Runtime'].notna().any() else None
                            }
                        
                        # Check for tracking columns, add if not present
                        if 'Watched' not in df.columns:
                            df['Watched'] = 'No'
                        if 'Personal Rating' not in df.columns:
                            df['Personal Rating'] = None
                        if 'Favorite' not in df.columns:
                            df['Favorite'] = 'No'
                        if 'Watch Date' not in df.columns:
                            df['Watch Date'] = None
                        
                        all_shows[sheet.title] = df
            except Exception as e:
                st.warning(f"Couldn't load sheet {sheet.title}: {e}")
                continue
    
    return all_shows, show_metadata

# Update a specific cell in Google Sheets
def update_sheet_cell(sheet_name, row, col, value):
    try:
        spreadsheet = connect_sheets()
        if not spreadsheet:
            return False
            
        sheet = spreadsheet.worksheet(sheet_name)
        # Convert to A1 notation
        cell = f"{chr(64 + col)}{row}"
        sheet.update(cell, value)
        return True
    except Exception as e:
        st.error(f"Failed to update cell: {e}")
        return False

# DASHBOARD COMPONENTS

# Overview dashboard
def display_overview(shows, metadata):
    st.header("📊 TV Shows Overview")
    
    if not shows:
        st.warning("No show data available. Please check your Google Sheets connection.")
        return
    
    # Basic statistics
    total_shows = len(shows)
    total_episodes = sum(len(df) for df in shows.values())
    total_seasons = sum(meta.get('seasons', 0) for meta in metadata.values())
    
    # Display metrics in columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Shows", total_shows)
    with col2:
        st.metric("Total Episodes", total_episodes)
    with col3:
        st.metric("Total Seasons", total_seasons)
    
    # Show list with progress bars
    st.subheader("Your Shows")
    
    # Calculate watching progress
    for show_name, df in shows.items():
        if 'Watched' in df.columns:
            watched_count = (df['Watched'] == 'Yes').sum()
            in_progress = (df['Watched'] == 'In Progress').sum()
            total_count = len(df)
            
            # Calculate progress percentage
            if total_count > 0:
                progress_pct = (watched_count / total_count) * 100
            else:
                progress_pct = 0
                
            # Display in expander with progress bar
            with st.expander(f"{show_name} ({watched_count}/{total_count} episodes watched)"):
                st.progress(progress_pct / 100)
                
                # Show ratings if available
                if 'Rating' in df.columns and df['Rating'].notna().any():
                    avg_rating = df['Rating'].mean()
                    st.write(f"Average Rating: {avg_rating:.1f}/10")
                
                # Quick stat columns
                stat_col1, stat_col2 = st.columns(2)
                with stat_col1:
                    st.write(f"Seasons: {df['Season'].nunique() if 'Season' in df.columns else 'N/A'}")
                    if 'Personal Rating' in df.columns and df['Personal Rating'].notna().any():
                        st.write(f"Your Average Rating: {df['Personal Rating'].mean():.1f}/10")
                with stat_col2:
                    st.write(f"Episodes Remaining: {total_count - watched_count}")
                    st.write(f"Completion: {progress_pct:.1f}%")
    
    # Ratings visualization (if we have ratings)
    st.subheader("Show Ratings")
    
    # Create a DataFrame with average ratings by show
    ratings_data = []
    for show_name, df in shows.items():
        if 'Rating' in df.columns and df['Rating'].notna().any():
            avg_rating = df['Rating'].mean()
            ratings_data.append({
                'Show': show_name,
                'Average Rating': avg_rating
            })
    
    if ratings_data:
        ratings_df = pd.DataFrame(ratings_data)
        ratings_df = ratings_df.sort_values('Average Rating', ascending=False)
        
        # Create a bar chart with Plotly
        fig = px.bar(
            ratings_df, 
            x='Show', 
            y='Average Rating',
            color='Average Rating',
            color_continuous_scale='RdYlGn',
            text_auto='.1f'
        )
        fig.update_layout(title='Average Ratings by Show')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No rating data available for visualization.")

# Show Details dashboard
def display_show_details(shows, metadata):
    st.header("🎬 Show Details")
    
    if not shows:
        st.warning("No show data available. Please check your Google Sheets connection.")
        return
    
    # Show selector
    show_names = list(shows.keys())
    selected_show = st.selectbox("Select a show to view details", show_names)
    
    if selected_show:
        df = shows[selected_show]
        
        # Show metadata and basic stats
        st.subheader(f"{selected_show}")
        
        # Display key metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Episodes", len(df))
        with col2:
            st.metric("Seasons", df['Season'].nunique() if 'Season' in df.columns else 0)
        with col3:
            if 'Rating' in df.columns and df['Rating'].notna().any():
                st.metric("Average Rating", f"{df['Rating'].mean():.1f}")
            else:
                st.metric("Average Rating", "N/A")
        
        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["Season Ratings", "Episode List", "Runtime Analysis"])
        
        with tab1:
            if 'Rating' in df.columns and 'Season' in df.columns and df['Rating'].notna().any():
                # Calculate average rating by season
                season_ratings = df.groupby('Season')['Rating'].mean().reset_index()
                
                # Create visualization
                fig = px.line(
                    season_ratings, 
                    x='Season', 
                    y='Rating',
                    markers=True,
                    title=f"Average Rating by Season for {selected_show}"
                )
                fig.update_layout(xaxis_title="Season", yaxis_title="Rating")
                st.plotly_chart(fig, use_container_width=True)
                
                # Top episodes
                st.subheader("Top Rated Episodes")
                top_episodes = df.sort_values('Rating', ascending=False).head(5)
                for _, row in top_episodes.iterrows():
                    st.write(f"S{row['Season']}E{row['Episode']} - {row['Episode Title']}: {row['Rating']}/10")
            else:
                st.info("No rating data available for this show.")
        
        with tab2:
            # Create a dataframe view with season, episode, title, and rating
            display_cols = ['Season', 'Episode', 'Episode Title', 'Rating', 'Release Date']
            tracking_cols = ['Watched', 'Personal Rating', 'Favorite']
            
            # Combine the columns that exist in the dataframe
            cols_to_display = [col for col in display_cols + tracking_cols if col in df.columns]
            
            # Sort by season and episode
            if 'Season' in df.columns and 'Episode' in df.columns:
                sorted_df = df.sort_values(['Season', 'Episode'])
            else:
                sorted_df = df
                
            # Display as a dataframe with sorting enabled
            st.dataframe(sorted_df[cols_to_display], use_container_width=True)
        
        with tab3:
            if 'Runtime' in df.columns and df['Runtime'].notna().any():
                # Clean runtime data (extract numbers if strings like "30 min")
                if df['Runtime'].dtype == 'object':
                    try:
                        df['Runtime_Minutes'] = df['Runtime'].str.extract('(\d+)').astype(float)
                    except Exception as e:
                        st.warning(f"Could not parse runtime data: {e}")
                        df['Runtime_Minutes'] = 0
                else:
                    df['Runtime_Minutes'] = df['Runtime']
                
                # Runtime analysis by season
                if 'Season' in df.columns:
                    runtime_by_season = df.groupby('Season')['Runtime_Minutes'].mean().reset_index()
                    
                    fig = px.bar(
                        runtime_by_season,
                        x='Season',
                        y='Runtime_Minutes',
                        title=f"Average Episode Runtime by Season for {selected_show}",
                        labels={"Runtime_Minutes": "Runtime (minutes)"}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Runtime trend over episodes
                    if 'Episode' in df.columns:
                        # Sort by season and episode
                        sorted_runtime = df.sort_values(['Season', 'Episode'])
                        
                        # Create a continuous episode number for x-axis
                        sorted_runtime['Episode_Number'] = range(1, len(sorted_runtime) + 1)
                        
                        fig = px.scatter(
                            sorted_runtime,
                            x='Episode_Number',
                            y='Runtime_Minutes',
                            color='Season',
                            hover_data=['Season', 'Episode', 'Episode Title'],
                            title=f"Episode Runtime Trend for {selected_show}",
                            labels={"Runtime_Minutes": "Runtime (minutes)", "Episode_Number": "Episode Number (Overall)"}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Season data not available for runtime analysis.")
            else:
                st.info("No runtime data available for this show.")

# Episode Tracker dashboard
def display_episode_tracker(shows, metadata):
    st.header("👁️ Episode Tracker")
    
    if not shows:
        st.warning("No show data available. Please check your Google Sheets connection.")
        return
    
    # Show selector
    show_names = list(shows.keys())
    selected_show = st.selectbox("Select a show to track episodes", show_names)
    
    if selected_show:
        df = shows[selected_show]
        
        # Add necessary columns if they don't exist
        if 'Watched' not in df.columns:
            df['Watched'] = 'No'
        if 'Personal Rating' not in df.columns:
            df['Personal Rating'] = None
        if 'Favorite' not in df.columns:
            df['Favorite'] = 'No'
        
        # Filter controls
        st.subheader("Filter Episodes")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'Season' in df.columns:
                all_seasons = sorted(df['Season'].unique())
                selected_seasons = st.multiselect(
                    "Select Seasons", 
                    options=all_seasons,
                    default=all_seasons
                )
            else:
                selected_seasons = None
                st.write("No season data available")
        
        with col2:
            watch_status = st.selectbox(
                "Watch Status",
                options=["All", "Watched", "Unwatched", "In Progress"]
            )
        
        with col3:
            if 'Favorite' in df.columns:
                favorites_only = st.checkbox("Favorites Only")
            else:
                favorites_only = False
        
        # Apply filters
        filtered_df = df.copy()
        
        if selected_seasons:
            filtered_df = filtered_df[filtered_df['Season'].isin(selected_seasons)]
        
        if watch_status != "All":
            if watch_status == "Watched":
                filtered_df = filtered_df[filtered_df['Watched'] == 'Yes']
            elif watch_status == "Unwatched":
                filtered_df = filtered_df[filtered_df['Watched'] == 'No']
            elif watch_status == "In Progress":
                filtered_df = filtered_df[filtered_df['Watched'] == 'In Progress']
        
        if favorites_only:
            filtered_df = filtered_df[filtered_df['Favorite'] == 'Yes']
        
        # Sort by season and episode
        if 'Season' in filtered_df.columns and 'Episode' in filtered_df.columns:
            filtered_df = filtered_df.sort_values(['Season', 'Episode'])
        
        # Display episode tracker
        st.subheader("Episodes")
        
        if filtered_df.empty:
            st.info("No episodes match your filters.")
        else:
            # Progress metrics
            watched_count = (filtered_df['Watched'] == 'Yes').sum()
            in_progress = (filtered_df['Watched'] == 'In Progress').sum()
            total_count = len(filtered_df)
            
            progress_col1, progress_col2, progress_col3 = st.columns(3)
            with progress_col1:
                st.metric("Episodes Watched", f"{watched_count}/{total_count}")
            with progress_col2:
                if total_count > 0:
                    progress_pct = (watched_count / total_count) * 100
                    st.metric("Progress", f"{progress_pct:.1f}%")
                else:
                    st.metric("Progress", "0%")
            with progress_col3:
                st.metric("In Progress", in_progress)
            
            # Episode list with tracking options
            for i, (idx, row) in enumerate(filtered_df.iterrows()):
                # Prepare episode info
                episode_title = row.get('Episode Title', f"Episode {row.get('Episode', '?')}")
                season_num = row.get('Season', '?')
                episode_num = row.get('Episode', '?')
                rating = row.get('Rating', 'N/A')
                synopsis = row.get('Synopsis', 'No synopsis available')
                
                # Create a unique key for each widget
                key_prefix = f"{selected_show}_S{season_num}E{episode_num}_{i}"
                
                # Create an expander for each episode
                with st.expander(f"S{season_num}E{episode_num} - {episode_title}"):
                    # Two columns - one for info, one for actions
                    info_col, action_col = st.columns([2, 1])
                    
                    with info_col:
                        st.write(f"**Synopsis:** {synopsis}")
                        st.write(f"**Rating:** {rating}")
                        if 'Release Date' in row:
                            st.write(f"**Released:** {row['Release Date']}")
                        if 'Runtime' in row:
                            st.write(f"**Runtime:** {row['Runtime']}")
                    
                    with action_col:
                        # Watch status dropdown
                        watch_options = ['No', 'Yes', 'In Progress']
                        current_status = row.get('Watched', 'No')
                        new_status = st.selectbox(
                            "Watched",
                            options=watch_options,
                            index=watch_options.index(current_status) if current_status in watch_options else 0,
                            key=f"{key_prefix}_watched"
                        )
                        
                        # Personal rating slider
                        current_rating = row.get('Personal Rating')
                        if pd.isna(current_rating):
                            current_rating = 0
                        try:
                            current_rating = int(float(current_rating))
                        except:
                            current_rating = 0
                        
                        new_rating = st.slider(
                            "Your Rating",
                            0, 10, current_rating,
                            key=f"{key_prefix}_rating"
                        )
                        
                        # Favorite checkbox
                        current_favorite = row.get('Favorite', 'No')
                        new_favorite = st.checkbox(
                            "Favorite",
                            value=(current_favorite == 'Yes'),
                            key=f"{key_prefix}_favorite"
                        )
                        
                        # Watch date picker if watched
                        if new_status == 'Yes':
                            current_date = row.get('Watch Date')
                            try:
                                if pd.notna(current_date) and current_date:
                                    current_date = datetime.strptime(current_date, '%Y-%m-%d').date()
                                else:
                                    current_date = datetime.now().date()
                            except:
                                current_date = datetime.now().date()
                            
                            new_date = st.date_input(
                                "Date Watched",
                                current_date,
                                key=f"{key_prefix}_date"
                            )
                        else:
                            new_date = None
                        
                        # Update button
                        if st.button("Update", key=f"{key_prefix}_update"):
                            # Get the worksheet
                            try:
                                spreadsheet = connect_sheets()
                                sheet = spreadsheet.worksheet(selected_show)
                                
                                # Get the row number in the sheet (add 2 to account for 0-indexing and header row)
                                sheet_row = idx + 2
                                
                                # Update the cells
                                updates = []
                                
                                # Find column indexes
                                header_row = sheet.row_values(1)
                                watched_col = header_row.index('Watched') + 1 if 'Watched' in header_row else None
                                rating_col = header_row.index('Personal Rating') + 1 if 'Personal Rating' in header_row else None
                                favorite_col = header_row.index('Favorite') + 1 if 'Favorite' in header_row else None
                                date_col = header_row.index('Watch Date') + 1 if 'Watch Date' in header_row else None
                                
                                # Update watched status
                                if watched_col:
                                    sheet.update_cell(sheet_row, watched_col, new_status)
                                    updates.append(f"Watched={new_status}")
                                
                                # Update personal rating
                                if rating_col:
                                    sheet.update_cell(sheet_row, rating_col, new_rating)
                                    updates.append(f"Rating={new_rating}")
                                
                                # Update favorite
                                if favorite_col:
                                    sheet.update_cell(sheet_row, favorite_col, 'Yes' if new_favorite else 'No')
                                    updates.append(f"Favorite={'Yes' if new_favorite else 'No'}")
                                
                                # Update watch date
                                if date_col and new_date:
                                    sheet.update_cell(sheet_row, date_col, new_date.strftime('%Y-%m-%d'))
                                    updates.append(f"Date={new_date.strftime('%Y-%m-%d')}")
                                
                                st.success(f"Episode updated! {', '.join(updates)}")
                            
                            except Exception as e:
                                st.error(f"Failed to update: {e}")

# Analysis dashboard
def display_analysis(shows, metadata):
    st.header("📈 Analysis Dashboard")
    
    if not shows:
        st.warning("No show data available. Please check your Google Sheets connection.")
        return
    
    # Create tabs for different analyses
    tab1, tab2, tab3 = st.tabs(["Rating Comparisons", "Genre Analysis", "Viewing Patterns"])
    
    with tab1:
        st.subheader("Show Comparison by Average Rating")
        
        # Create a DataFrame with average ratings by show
        ratings_data = []
        for show_name, df in shows.items():
            if 'Rating' in df.columns and df['Rating'].notna().any():
                avg_rating = df['Rating'].mean()
                ratings_data.append({
                    'Show': show_name,
                    'Average Rating': avg_rating,
                    'Episode Count': len(df)
                })
        
        if ratings_data:
            ratings_df = pd.DataFrame(ratings_data)
            
            # Create a scatter plot of ratings vs episode count
            fig = px.scatter(
                ratings_df,
                x='Episode Count',
                y='Average Rating',
                size='Episode Count',
                color='Average Rating',
                hover_name='Show',
                title='Shows by Episode Count and Average Rating',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Season-by-season rating comparison
            st.subheader("Season-by-Season Rating Comparison")
            
            # Prepare data for season comparison
            season_data = []
            for show_name, df in shows.items():
                if 'Rating' in df.columns and 'Season' in df.columns and df['Rating'].notna().any():
                    # Group by season and calculate average ratings
                    season_ratings = df.groupby('Season')['Rating'].mean().reset_index()
                    season_ratings['Show'] = show_name
                    season_data.append(season_ratings)
            
            if season_data:
                # Combine all show data
                all_season_data = pd.concat(season_data)
                
                # Create line plot comparing shows across seasons
                fig = px.line(
                    all_season_data,
                    x='Season',
                    y='Rating',
                    color='Show',
                    markers=True,
                    title='Average Ratings by Season Across Shows'
                )
                fig.update_layout(xaxis_title="Season", yaxis_title="Rating")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Not enough season rating data available for comparison.")
        else:
            st.info("No rating data available for comparison.")
    
    with tab2:
        st.subheader("Genre Analysis")
        st.info("This would use genre metadata from the TV show. To add this feature, you would need to enhance your scraper to collect genre information or add it manually.")
        
        # Placeholder for genre analysis visualization
        sample_genres = {
            'Comedy': 35,
            'Drama': 27,
            'Action': 18,
            'Sci-Fi': 12,
            'Crime': 8
        }
        
        # Create a pie chart with the sample data
        fig = px.pie(
            values=list(sample_genres.values()),
            names=list(sample_genres.keys()),
            title='Distribution of TV Shows by Genre (Sample Data)'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Viewing Patterns")
        st.info("This analysis would use your watch dates to show when you watch TV. Add viewing dates to your episodes to enable this analysis.")
        
        # Placeholder for viewing pattern analysis
        # Create some sample data for days of week viewing
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        views = [5, 3, 2, 4, 8, 12, 10]
        
        # Create a bar chart
        fig = px.bar(
            x=days, 
            y=views,
            title='Most Popular Viewing Days (Sample Data)',
            labels={'x': 'Day of Week', 'y': 'Episodes Watched'}
        )
        st.plotly_chart(fig, use_container_width=True)

# Main app function
def main():
    st.title("📺 My TV Show Dashboard")
    
    # Show a loading message while checking connection
    with st.spinner("Connecting to Google Sheets..."):
        # Try to load data
        shows, metadata = load_all_show_data()
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Overview", "Show Details", "Episode Tracker", "Analysis"])
    
    # Display based on navigation
    if page == "Overview":
        display_overview(shows, metadata)
    elif page == "Show Details":
        display_show_details(shows, metadata)
    elif page == "Episode Tracker":
        display_episode_tracker(shows, metadata)
    else:
        display_analysis(shows, metadata)
    
    # Information about the app
    with st.sidebar.expander("About"):
        st.write("This dashboard visualizes data from your TV show collection in Google Sheets.")
        st.write("Built with Streamlit and Plotly.")

# Run the app
if __name__ == "__main__":
    main()
