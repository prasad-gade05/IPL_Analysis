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

# Hide the default sidebar and inject global styles
st.markdown(
    """
    <style>
    /* Hide sidebar completely */
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stSidebarCollapsedControl"] { display: none; }

    /* Force metric values, labels and deltas to wrap instead of overflow.
       Streamlit's React component hardcodes truncate:true which generates
       CSS-in-JS rules (overflow:hidden, white-space:nowrap, text-overflow:ellipsis)
       on deeply nested inner elements via Emotion. Override with * wildcard. */
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] *,
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] *,
    [data-testid="stMetricDelta"],
    [data-testid="stMetricDelta"] * {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        overflow-wrap: break-word !important;
        word-wrap: break-word !important;
        word-break: break-word !important;
    }
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {
        line-height: 1.3 !important;
    }

    /* Also target the metric container and its parent column */
    [data-testid="stMetric"] {
        overflow: visible !important;
    }

    /* Prevent column content from overflowing */
    [data-testid="column"] > div {
        overflow-wrap: break-word;
        word-wrap: break-word;
        min-width: 0;
    }

    /* Top navigation buttons — larger and clearer.
       Nav link component also uses CSS-in-JS truncation on inner elements. */
    [data-testid="stPageLink"],
    [data-testid="stPageLink"] div,
    [data-testid="stPageLink"] span {
        overflow: visible !important;
        text-overflow: unset !important;
        white-space: normal !important;
    }
    [data-testid="stPageLink"] p {
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        line-height: 1.35;
        padding: 0.25rem 0;
    }

    /* Ensure headings and captions wrap */
    .stMarkdown h2, .stMarkdown h3, .stMarkdown h4,
    .stCaption, .stMarkdown p {
        overflow-wrap: break-word;
        word-wrap: break-word;
    }

    /* Compact top nav row spacing */
    div[data-testid="stHorizontalBlock"]:first-of-type {
        gap: 0.25rem;
    }
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
venue_intel = st.Page("pages/05_Venue_Intelligence.py", title="Venue")
head_to_head = st.Page("pages/06_Head_to_Head.py", title="Head to Head")
phase_analysis = st.Page("pages/07_Phase_Analysis.py", title="Phase Analysis")
pressure = st.Page("pages/08_Pressure_Momentum.py", title="Pressure")
trends = st.Page("pages/09_Trends_Evolution.py", title="Trends")
records = st.Page("pages/10_Records_Anomalies.py", title="Records")
match_center = st.Page("pages/11_Match_Center.py", title="Match Center")
tournament = st.Page("pages/12_Tournament_Structure.py", title="Tournament")
explorer = st.Page("pages/13_Explorer.py", title="Explorer")

ALL_PAGES = [
    home, season_hub, leaderboards, player_profile, team_profile,
    venue_intel, head_to_head, phase_analysis, pressure, trends,
    records, match_center, tournament, explorer,
]

pg = st.navigation(ALL_PAGES, position="hidden")

# --- Top Navigation Bar (2 rows of 7) ---
ROW_SIZE = 7
for row_start in range(0, len(ALL_PAGES), ROW_SIZE):
    row_pages = ALL_PAGES[row_start : row_start + ROW_SIZE]
    cols = st.columns(ROW_SIZE)
    for i, page in enumerate(row_pages):
        with cols[i]:
            st.page_link(page, label=page.title, use_container_width=True)

st.divider()

# --- Run the selected page ---
pg.run()
