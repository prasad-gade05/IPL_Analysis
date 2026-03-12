"""
🏏 IPL Analytics Platform — The Definitive IPL Data Hub (2008-2025)

Main entry point for the Streamlit application.
"""

import streamlit as st

st.set_page_config(
    page_title="IPL Analytics Platform",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "# IPL Analytics Platform\n18 Seasons | 1200+ Matches | 700+ Players | 40+ Venues",
    },
)


def init_session_state():
    """Initialize session state keys for cross-page navigation."""
    defaults = {
        "selected_player": None,
        "selected_team": None,
        "selected_venue": None,
        "selected_match_id": None,
        "selected_season": None,
        "selected_batter": None,
        "selected_bowler": None,
        "season_range": (2008, 2025),
        "comparison_player": None,
        "comparison_team": None,
        "comparison_venue": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main():
    init_session_state()

    # Sidebar — Global Filters
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/cricket.png", width=60)
        st.title("🏏 IPL Analytics")
        st.caption("2008 — 2025 | The Definitive IPL Data Hub")
        st.divider()

        st.subheader("Global Filters")
        season_range = st.slider(
            "Season Range",
            min_value=2008,
            max_value=2025,
            value=st.session_state["season_range"],
            key="global_season_range",
        )
        st.session_state["season_range"] = season_range

        st.divider()
        st.caption("Built with Streamlit • DuckDB • Plotly")

    # Main Content — Home Page
    st.title("🏏 The Definitive IPL Analytics Platform")
    st.markdown(
        """
        > **18 Seasons** | **1,200+ Matches** | **700+ Players** | **40+ Venues**
        >
        > Every stat. Every matchup. Every record. One platform.
        """
    )

    st.info(
        "👈 Use the sidebar to navigate between pages. "
        "The data pipeline needs to be run first — see README for setup instructions.",
        icon="ℹ️",
    )

    # Navigation Tiles
    st.subheader("Explore")
    cols = st.columns(3)
    pages = [
        ("📅 Season Hub", "Complete story of any IPL season"),
        ("🏆 Leaderboards", "All-time batting, bowling, team rankings"),
        ("🏏 Player Profile", "Deep-dive into any player's career"),
        ("👥 Team Profile", "Franchise analytics and history"),
        ("🏟️ Venue Intelligence", "Ground-specific insights"),
        ("⚔️ Head-to-Head", "Batter vs Bowler, Team vs Team"),
        ("📊 Phase Analysis", "Powerplay, Middle, Death overs"),
        ("🔥 Pressure & Momentum", "Dot ball cascades, chase dynamics"),
        ("📈 Trends & Evolution", "How IPL has changed over 18 years"),
        ("🎯 Records & Anomalies", "Every IPL record and unusual event"),
        ("📋 Match Center", "Ball-by-ball replay of any match"),
        ("🔍 Explorer", "Custom query builder"),
    ]
    for i, (title, desc) in enumerate(pages):
        with cols[i % 3]:
            st.markdown(f"**{title}**")
            st.caption(desc)


if __name__ == "__main__":
    main()
