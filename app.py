"""
IPL Analytics Platform -- Navigation Controller

Entry point for the Streamlit multi-page application.
Defines all pages and renders a horizontal top navigation bar.
"""

import streamlit as st

st.set_page_config(
    page_title="IPL Analytics Platform",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "About": "# IPL Analytics Platform\n18 Seasons | 1200+ Matches | 700+ Players | 40+ Venues",
    },
)

# Hide the default sidebar navigation completely
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stSidebarCollapsedControl"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Define all pages ---
home = st.Page("pages/00_Home.py", title="Home", default=True)
season_hub = st.Page("pages/01_Season_Hub.py", title="Season Hub")
leaderboards = st.Page("pages/02_Leaderboards.py", title="Leaderboards")
player_profile = st.Page("pages/03_Player_Profile.py", title="Player Profile")
team_profile = st.Page("pages/04_Team_Profile.py", title="Team Profile")
venue_intel = st.Page("pages/05_Venue_Intelligence.py", title="Venue Intelligence")
head_to_head = st.Page("pages/06_Head_to_Head.py", title="Head to Head")
phase_analysis = st.Page("pages/07_Phase_Analysis.py", title="Phase Analysis")
pressure = st.Page("pages/08_Pressure_Momentum.py", title="Pressure & Momentum")
trends = st.Page("pages/09_Trends_Evolution.py", title="Trends & Evolution")
records = st.Page("pages/10_Records_Anomalies.py", title="Records & Anomalies")
match_center = st.Page("pages/11_Match_Center.py", title="Match Center")
tournament = st.Page("pages/12_Tournament_Structure.py", title="Tournament Structure")
explorer = st.Page("pages/13_Explorer.py", title="Explorer")

ALL_PAGES = [
    home, season_hub, leaderboards, player_profile, team_profile,
    venue_intel, head_to_head, phase_analysis, pressure, trends,
    records, match_center, tournament, explorer,
]

pg = st.navigation(ALL_PAGES, position="hidden")

# --- Top Navigation Bar ---
nav_cols = st.columns(len(ALL_PAGES))
for i, page in enumerate(ALL_PAGES):
    with nav_cols[i]:
        st.page_link(page, label=page.title, use_container_width=True)

st.divider()

# --- Run the selected page ---
pg.run()
