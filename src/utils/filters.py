"""Reusable Streamlit filter components."""

import streamlit as st
from src.db.connection import query


def season_range_filter(key_prefix=""):
    """Render a season range slider and return the tuple."""
    return st.session_state.get("season_range", (2008, 2025))


def team_filter(key="team_filter", label="Select Team", include_all=True):
    """Render a team selector dropdown."""
    try:
        teams_df = query("SELECT DISTINCT team FROM team_season ORDER BY team")
        teams = teams_df["team"].tolist()
    except Exception:
        teams = []

    options = ["All Teams"] + teams if include_all else teams
    return st.selectbox(label, options, key=key)


def player_filter(key="player_filter", label="Select Player"):
    """Render a player selector with search."""
    try:
        players_df = query(
            "SELECT DISTINCT batter AS player FROM player_batting ORDER BY player"
        )
        players = players_df["player"].tolist()
    except Exception:
        players = []

    return st.selectbox(label, players, key=key)


def venue_filter(key="venue_filter", label="Select Venue", include_all=True):
    """Render a venue selector dropdown."""
    try:
        venues_df = query("SELECT DISTINCT venue FROM venues ORDER BY venue")
        venues = venues_df["venue"].tolist()
    except Exception:
        venues = []

    options = ["All Venues"] + venues if include_all else venues
    return st.selectbox(label, options, key=key)


def phase_filter(key="phase_filter", label="Match Phase"):
    """Render a phase selector."""
    return st.multiselect(
        label,
        ["Powerplay", "Middle", "Death"],
        default=["Powerplay", "Middle", "Death"],
        key=key,
    )


def innings_filter(key="innings_filter", label="Innings"):
    """Render an innings selector."""
    return st.radio(label, ["Both", "1st Innings", "2nd Innings"], key=key)


def stage_filter(key="stage_filter", label="Match Stage"):
    """Render a match stage filter."""
    return st.multiselect(
        label,
        ["League", "Qualifier 1", "Qualifier 2", "Eliminator", "Semi Final", "Final"],
        default=["League", "Qualifier 1", "Qualifier 2", "Eliminator", "Semi Final", "Final"],
        key=key,
    )
