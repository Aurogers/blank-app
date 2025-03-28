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

st.set_page_config(
    page_title="TV Show Dashboard",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.write("Checking for credentials...")
if hasattr(st, 'secrets'):
    if 'gcp_service_account' in st.secrets:
        st.success("Found credentials in Streamlit secrets!")
        email = st.secrets["gcp_service_account"].get("client_email", "Unknown")
        st.write(f"Service account email: {email}")
    else:
        st.error("No 'gcp_service_account' section found in Streamlit secrets")
        st.write(f"Available secrets sections: {list(st.secrets.keys())}")
else:
    st.warning("No Streamlit secrets configured")

def get_credentials():
    if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
        return st.secrets["gcp_service_account"]
    elif os.environ.get('GOOGLE_CREDENTIALS'):
        try:
            return json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
        except json.JSONDecodeError:
            st.error("Invalid JSON in GOOGLE_CREDENTIALS environment variable")
    else:
        try:
            with open('credentials.json') as f:
                return json.load(f)
        except FileNotFoundError:
            st.error("No Google credentials found.")
            return None

@st.cache_resource
def connect_sheets():
    try:
        creds_dict = get_credentials()
        if not creds_dict:
            st.error("Failed to get credentials")
            return None

        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
        client = gspread.authorize(credentials)

        try:
            all_sheets = [sheet.title for sheet in client.openall()]
            st.write(f"Connected to Google Sheets. Available spreadsheets: {all_sheets}")
        except Exception as e:
            st.warning(f"Connected but couldn't list spreadsheets: {e}")

        return client.open("My Favorite TV Shows")
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None

@st.cache_data(ttl=300)
def load_all_show_data():
    spreadsheet = connect_sheets()
    if not spreadsheet:
        return {}, {}

    all_shows = {}
    show_metadata = {}

    with st.spinner("Loading shows from Google Sheets..."):
        for sheet in spreadsheet.worksheets():
            try:
                header_row = sheet.row_values(1)
                if header_row and 'Show Name' in header_row:
                    data = sheet.get_all_records()
                    if data:
                        df = pd.DataFrame(data)
                        first_row = df.iloc[0] if not df.empty else None

                        if first_row is not None and 'Show Name' in df.columns:
                            show_name = first_row['Show Name']
                            show_metadata[sheet.title] = {
                                'title': show_name,
                                'total_episodes': len(df),
                                'seasons': df['Season'].nunique() if 'Season' in df.columns else 0,
                            }

                            if 'Rating' in df.columns:
                                numeric_ratings = pd.to_numeric(df['Rating'], errors='coerce')
                                show_metadata[sheet.title]['average_rating'] = numeric_ratings.mean() if not numeric_ratings.isna().all() else None
                            else:
                                show_metadata[sheet.title]['average_rating'] = None

                            if 'Runtime' in df.columns:
                                try:
                                    runtime_values = df['Runtime'].astype(str).str.extract('(\d+)').astype(float)
                                    show_metadata[sheet.title]['longest_episode'] = runtime_values.max().max() if not runtime_values.isna().all().all() else None
                                except:
                                    show_metadata[sheet.title]['longest_episode'] = None

                        for col in ['Watched', 'Personal Rating', 'Favorite', 'Watch Date']:
                            if col not in df.columns:
                                df[col] = 'No' if col in ['Watched', 'Favorite'] else None

                        all_shows[sheet.title] = df
            except Exception as e:
                st.warning(f"Couldn't load sheet {sheet.title}: {e}")

    return all_shows, show_metadata
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
            # Handle different "Yes" values
            watched_count = sum(1 for watched in df['Watched'] if 
                (watched == 'Yes' or 
                str(watched).upper() in ['TRUE', 'YES', '1'] or
                watched is True))
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
                if 'Rating' in df.columns:
                    # Convert to numeric, handling non-numeric values
                    numeric_ratings = pd.to_numeric(df['Rating'], errors='coerce')
                    if numeric_ratings.notna().any():
                        avg_rating = numeric_ratings.mean()
                        st.write(f"Average Rating: {avg_rating:.1f}/10")
                
                # Quick stat columns
                stat_col1, stat_col2 = st.columns(2)
                with stat_col1:
                    st.write(f"Seasons: {df['Season'].nunique() if 'Season' in df.columns else 'N/A'}")
                    if 'Personal Rating' in df.columns:
                        # Convert to numeric, handling non-numeric values
                        numeric_personal = pd.to_numeric(df['Personal Rating'], errors='coerce')
                        if numeric_personal.notna().any():
                            avg_personal = numeric_personal.mean()
                            st.write(f"Your Average Rating: {avg_personal:.1f}/10")
                with stat_col2:
                    st.write(f"Episodes Remaining: {total_count - watched_count}")
                    st.write(f"Completion: {progress_pct:.1f}%")
            # Handle different "Yes" values
            watched_count = sum(1 for watched in df['Watched'] if 
                (watched == 'Yes' or 
                str(watched).upper() in ['TRUE', 'YES', '1'] or
                watched is True))
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
                if 'Rating' in df.columns:
                    # Convert to numeric, handling non-numeric values
                    numeric_ratings = pd.to_numeric(df['Rating'], errors='coerce')
                    if numeric_ratings.notna().any():
                        avg_rating = numeric_ratings.mean()
                        st.write(f"Average Rating: {avg_rating:.1f}/10")
                
                # Quick stat columns
                stat_col1, stat_col2 = st.columns(2)
                with stat_col1:
                    st.write(f"Seasons: {df['Season'].nunique() if 'Season' in df.columns else 'N/A'}")
                    if 'Personal Rating' in df.columns:
                        # Convert to numeric, handling non-numeric values
                        numeric_personal = pd.to_numeric(df['Personal Rating'], errors='coerce')
                        if numeric_personal.notna().any():
                            avg_personal = numeric_personal.mean()
                            st.write(f"Your Average Rating: {avg_personal:.1f}/10")
                with stat_col2:
                    st.write(f"Episodes Remaining: {total_count - watched_count}")
                    st.write(f"Completion: {progress_pct:.1f}%")
    
    # Ratings visualization (if we have ratings)
    st.subheader("Show Ratings")
    
    # Create a DataFrame with average ratings by show
    ratings_data = []
    for show_name, df in shows.items():
        if 'Rating' in df.columns:
            # Convert to numeric, handling non-numeric values
            numeric_ratings = pd.to_numeric(df['Rating'], errors='coerce')
            if numeric_ratings.notna().any():
                avg_rating = numeric_ratings.mean()
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
    # Ensure metadata is used
    pass
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
            if 'Rating' in df.columns:
                # Convert to numeric, handling non-numeric values
                numeric_ratings = pd.to_numeric(df['Rating'], errors='coerce')
                if numeric_ratings.notna().any():
                    avg_rating = numeric_ratings.mean()
                    st.metric("Average Rating", f"{avg_rating:.1f}")
                else:
                    st.metric("Average Rating", "N/A")
            else:
                st.metric("Average Rating", "N/A")
        
        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["Season Ratings", "Episode List", "Runtime Analysis"])
        
        with tab1:
            if 'Rating' in df.columns and 'Season' in df.columns:
                # Convert to numeric, handling non-numeric values
                df['Numeric_Rating'] = pd.to_numeric(df['Rating'], errors='coerce')
                
                if df['Numeric_Rating'].notna().any():
                    # Calculate average rating by season
                    season_ratings = df.groupby('Season')['Numeric_Rating'].mean().reset_index()
                    
                    # Create visualization
                    fig = px.line(
                        season_ratings, 
                        x='Season', 
                        y='Numeric_Rating',
                        markers=True,
                        title=f"Average Rating by Season for {selected_show}"
                    )
                    fig.update_layout(xaxis_title="Season", yaxis_title="Rating")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Top episodes
                    st.subheader("Top Rated Episodes")
                    top_episodes = df.sort_values('Numeric_Rating', ascending=False).head(5)
                    for _, row in top_episodes.iterrows():
                        st.write(f"S{row['Season']}E{row['Episode']} - {row['Episode Title']}: {row['Rating']}/10")
                else:
                    st.info("No valid rating data available for this show.")
            else:
                st.info("No rating data available for this show.")
        
        with tab2:
            # Create a dataframe view with season, episode, title, and rating
            display_cols = ['Season', 'Episode', 'Episode Title', 'Rating', 'Release Date']
            tracking_cols = ['Watched', 'Personal Rating', 'Favorite', 'Watch Date']
            
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
            if 'Runtime' in df.columns:
                # Clean runtime data (extract numbers if strings like "30 min")
                try:
                    df['Runtime_Minutes'] = df['Runtime'].str.extract('(\d+)').astype(float, errors='coerce')
                    
                    if df['Runtime_Minutes'].notna().any():
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
                        st.info("Could not extract valid runtime data for analysis.")
                except Exception as e:
                    st.warning(f"Could not parse runtime data: {e}")
                    st.info("No valid runtime data available for this show.")
            else:
                st.info("No runtime data available for this show.")
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
        if 'Watch Date' not in df.columns:
            df['Watch Date'] = None
        
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
        if watch_status != "All":
            if watch_status == "Watched":
                # Create a mask for different "Yes" values
                watched_mask = (filtered_df['Watched'] == 'Yes') | \
                               (filtered_df['Watched'].astype(str).str.upper().isin(['TRUE', 'YES', '1'])) | \
                               (filtered_df['Watched'] == True)
                filtered_df = filtered_df[watched_mask]
            elif watch_status == "Unwatched":
                # Create a mask for different "No" values
                unwatched_mask = (filtered_df['Watched'] == 'No') | \
                                 (filtered_df['Watched'].astype(str).str.upper().isin(['FALSE', 'NO', '0'])) | \
                                 (filtered_df['Watched'] == False)
                filtered_df = filtered_df[unwatched_mask]
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
            watched_count = sum(1 for watched in filtered_df['Watched'] if 
                                (watched == 'Yes' or 
                                 str(watched).upper() in ['TRUE', 'YES', '1'] or
                                 watched is True))
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
                in_progress = (filtered_df['Watched'] == 'In Progress').sum()
                st.metric("In Progress", in_progress)
def display_analysis(shows, metadata):
    if not shows:
        st.warning("No show data available. Please check your Google Sheets connection.")
        return
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
            if 'Rating' in df.columns:
                # Convert to numeric, handling non-numeric values
                numeric_ratings = pd.to_numeric(df['Rating'], errors='coerce')
                if numeric_ratings.notna().any():
                    avg_rating = numeric_ratings.mean()
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
                if 'Rating' in df.columns and 'Season' in df.columns:
                    # Convert to numeric, handling non-numeric values
                    df['Numeric_Rating'] = pd.to_numeric(df['Rating'], errors='coerce')
                    
                    if df['Numeric_Rating'].notna().any():
                        # Group by season and calculate average ratings
                        season_ratings = df.groupby('Season')['Numeric_Rating'].mean().reset_index()
                        season_ratings['Show'] = show_name
                        season_data.append(season_ratings)
            
            if season_data:
                # Combine all show data
                all_season_data = pd.concat(season_data)
                
                # Create line plot comparing shows across seasons
                fig = px.line(
                    all_season_data,
                    x='Season',
                    y='Numeric_Rating',
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
        
        # Check if we have any watch date data
        has_watch_dates = False
        for show_name, df in shows.items():
            if 'Watch Date' in df.columns and df['Watch Date'].notna().any() and (df['Watch Date'] != '').any():
                has_watch_dates = True
                break
        
        if has_watch_dates:
            # Collect all watch dates across shows
            all_watch_dates = []
            for show_name, df in shows.items():
                if 'Watch Date' in df.columns:
                    # Try to parse dates
                    for date_str in df['Watch Date'].dropna():
                        if date_str and str(date_str).strip():  # Check for empty strings
                            try:
                                # Try different date formats
                                for fmt in ['%m-%d-%Y', '%Y-%m-%d', '%m/%d/%Y']:
                                    try:
                                        date = datetime.strptime(str(date_str), fmt)
                                        all_watch_dates.append(date)
                                        break
                                    except:
                                        pass
                            except:
                                pass
            
            if all_watch_dates:
                # Convert to a dataframe for analysis
                watch_df = pd.DataFrame({'date': all_watch_dates})
                
                # Add day of week
                watch_df['day_of_week'] = watch_df['date'].dt.day_name()
                watch_df['month'] = watch_df['date'].dt.month_name()
                
                # Create day of week visualization
                day_counts = watch_df['day_of_week'].value_counts()
                
                # Get days in correct order
                days_ordered = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                day_data = []
                for day in days_ordered:
                    day_data.append({'Day': day, 'Episodes Watched': day_counts.get(day, 0)})
                
                day_df = pd.DataFrame(day_data)
                
                # Create the bar chart
                fig = px.bar(
                    day_df,
                    x='Day',
                    y='Episodes Watched',
                    title='Episodes Watched by Day of Week',
                    color='Episodes Watched',
                    color_continuous_scale='Viridis'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Create month visualization
                month_counts = watch_df['month'].value_counts()
                
                # Get months in correct order
                months_ordered = ['January', 'February', 'March', 'April', 
                                 'May', 'June', 'July', 'August', 
                                 'September', 'October', 'November', 'December']
                month_data = []
                for month in months_ordered:
                    month_data.append({'Month': month, 'Episodes Watched': month_counts.get(month, 0)})
                
                month_df = pd.DataFrame(month_data)
                
                # Create the bar chart
                fig = px.bar(
                    month_df,
                    x='Month',
                    y='Episodes Watched',
                    title='Episodes Watched by Month',
                    color='Episodes Watched',
                    color_continuous_scale='Viridis'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Episodes watched over time
                watch_df['date_only'] = watch_df['date'].dt.date
                date_counts = watch_df['date_only'].value_counts().sort_index()
                
                date_data = pd.DataFrame({
                    'Date': date_counts.index,
                    'Episodes': date_counts.values
                })
                
                fig = px.line(
                    date_data,
                    x='Date',
                    y='Episodes',
                    title='TV Watching Activity Over Time',
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Could not parse any watch dates from your data.")
        else:
            st.info("Add watch dates to your episodes to see viewing patterns. Use the Episode Tracker to add dates when you watched each episode.")
            
            # Show sample data as example
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
        if 'display_analysis' in globals():
            display_analysis(shows, metadata)
    elif page == "Episode Tracker":
        display_episode_tracker(shows, metadata)
    else:
        display_analysis(shows, metadata)
    
    # Information about the app
    with st.sidebar.expander("About"):
        st.write("This dashboard visualizes data from your TV show collection in Google Sheets.")
        st.write("Built with Streamlit and Plotly.")
        st.write("Data fetched from TV Maze API and stored in Google Sheets.")

# Run the app
if __name__ == "__main__":
    main()
