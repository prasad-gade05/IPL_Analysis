"""
IPL Analytics Platform — Home Page
"""

import streamlit as st
import plotly.graph_objects as go

from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style,
    styled_bar,
    get_team_color,
    big_number_style,
    IPL_COLORWAY,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS
from src.utils.formatters import format_number


# --- Session State ---

def init_session_state():
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


# --- Cached Data Loaders ---

@st.cache_data(ttl=3600)
def load_headline_metrics(s_start: int, s_end: int) -> dict:
    df = query("""
        SELECT
            COUNT(DISTINCT match_id)    AS total_matches,
            SUM(runs_batter)            AS total_runs,
            COUNT(*) FILTER (WHERE wicket_kind IS NOT NULL
                             AND wicket_kind NOT IN ('', 'not_out'))  AS total_wickets,
            SUM(is_six)                 AS total_sixes,
            SUM(is_four)               AS total_fours,
            COUNT(DISTINCT batter)      AS unique_players
        FROM balls
        WHERE season BETWEEN ? AND ?
    """, [s_start, s_end])
    return df.iloc[0].to_dict()


@st.cache_data(ttl=3600)
def load_season_evolution(s_start: int, s_end: int):
    return query("""
        SELECT season, total_matches, num_teams
        FROM season_meta
        WHERE season BETWEEN ? AND ?
        ORDER BY season
    """, [s_start, s_end])


@st.cache_data(ttl=3600)
def load_champions(s_start: int, s_end: int):
    return query("""
        SELECT champion AS team, COUNT(*) AS titles
        FROM season_meta
        WHERE season BETWEEN ? AND ?
          AND champion IS NOT NULL
        GROUP BY champion
        ORDER BY titles DESC
    """, [s_start, s_end])


@st.cache_data(ttl=3600)
def load_latest_season_info(s_end: int):
    return query("""
        SELECT season, total_matches, champion
        FROM season_meta
        WHERE season = ?
    """, [s_end])


@st.cache_data(ttl=3600)
def load_top_batters_season(season: int, limit: int = 5):
    return query("""
        SELECT batter, SUM(runs) AS total_runs, SUM(balls) AS total_balls,
               SUM(fours) AS fours, SUM(sixes) AS sixes
        FROM player_batting
        WHERE season = ?
        GROUP BY batter
        ORDER BY total_runs DESC
        LIMIT ?
    """, [season, limit])


@st.cache_data(ttl=3600)
def load_top_bowlers_season(season: int, limit: int = 5):
    return query("""
        SELECT bowler, SUM(wickets) AS total_wickets,
               SUM(runs_conceded) AS runs_conceded,
               SUM(balls_bowled) AS balls_bowled
        FROM player_bowling
        WHERE season = ?
        GROUP BY bowler
        ORDER BY total_wickets DESC, runs_conceded ASC
        LIMIT ?
    """, [season, limit])


@st.cache_data(ttl=3600)
def load_alltime_top_batters(s_start: int, s_end: int, limit: int = 10):
    return query("""
        SELECT batter, SUM(runs) AS total_runs, COUNT(*) AS innings,
               SUM(fours) AS fours, SUM(sixes) AS sixes
        FROM player_batting
        WHERE season BETWEEN ? AND ?
        GROUP BY batter
        ORDER BY total_runs DESC
        LIMIT ?
    """, [s_start, s_end, limit])


@st.cache_data(ttl=3600)
def load_alltime_top_bowlers(s_start: int, s_end: int, limit: int = 10):
    return query("""
        SELECT bowler, SUM(wickets) AS total_wickets,
               SUM(runs_conceded) AS runs_conceded,
               SUM(balls_bowled) AS balls_bowled
        FROM player_bowling
        WHERE season BETWEEN ? AND ?
        GROUP BY bowler
        ORDER BY total_wickets DESC, runs_conceded ASC
        LIMIT ?
    """, [s_start, s_end, limit])


@st.cache_data(ttl=3600)
def load_latest_top_scorer(season: int):
    df = query("""
        SELECT batter, SUM(runs) AS total_runs
        FROM player_batting
        WHERE season = ?
        GROUP BY batter
        ORDER BY total_runs DESC
        LIMIT 1
    """, [season])
    if df.empty:
        return "N/A", 0
    return df.iloc[0]["batter"], int(df.iloc[0]["total_runs"])


@st.cache_data(ttl=3600)
def load_latest_top_wicket_taker(season: int):
    df = query("""
        SELECT bowler, SUM(wickets) AS total_wickets
        FROM player_bowling
        WHERE season = ?
        GROUP BY bowler
        ORDER BY total_wickets DESC
        LIMIT 1
    """, [season])
    if df.empty:
        return "N/A", 0
    return df.iloc[0]["bowler"], int(df.iloc[0]["total_wickets"])


# --- Chart Builders ---

def build_evolution_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["season"], y=df["total_matches"], name="Matches",
        marker_color=IPL_COLORWAY[0], opacity=0.85,
        text=df["total_matches"], textposition="outside", textfont=dict(size=10),
    ))
    fig.add_trace(go.Scatter(
        x=df["season"], y=df["num_teams"], name="Teams",
        mode="lines+markers+text",
        marker=dict(size=8, color=IPL_COLORWAY[1]),
        line=dict(width=3, color=IPL_COLORWAY[1]),
        text=df["num_teams"], textposition="top center",
        textfont=dict(size=10, color=IPL_COLORWAY[1]),
        yaxis="y2",
    ))
    fig.update_layout(
        title="IPL Evolution Timeline",
        xaxis=dict(title="Season", dtick=1),
        yaxis=dict(title="Matches", showgrid=False),
        yaxis2=dict(title="Teams", overlaying="y", side="right",
                    showgrid=False, range=[0, df["num_teams"].max() + 4]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        barmode="group",
    )
    return apply_ipl_style(fig, height=480)


def build_champions_chart(df):
    df = df.sort_values("titles", ascending=True)
    colors = [get_team_color(t) for t in df["team"]]
    fig = go.Figure(go.Bar(
        x=df["titles"], y=df["team"], orientation="h",
        marker_color=colors, text=df["titles"],
        textposition="outside", textfont=dict(size=13, color="#FAFAFA"),
    ))
    fig.update_layout(
        title="Champion Roll of Honor",
        xaxis=dict(title="Titles Won", dtick=1),
        yaxis=dict(title=""),
    )
    height = max(350, len(df) * 45)
    return apply_ipl_style(fig, height=height, show_legend=False)


def build_horizontal_bar(df, x_col, y_col, title, color=None, height=350):
    df_sorted = df.sort_values(x_col, ascending=True)
    bar_color = color or IPL_COLORWAY[0]
    fig = go.Figure(go.Bar(
        x=df_sorted[x_col], y=df_sorted[y_col], orientation="h",
        marker_color=bar_color, text=df_sorted[x_col],
        textposition="outside", textfont=dict(size=12),
    ))
    fig.update_layout(title=title, xaxis=dict(title=""), yaxis=dict(title=""))
    return apply_ipl_style(fig, height=height, show_legend=False)


# --- Main ---

def main():
    init_session_state()
    st.markdown(big_number_style(), unsafe_allow_html=True)

    # Header
    st.markdown("""
        <h1 style='text-align:center; margin-bottom:0;'>
            The Definitive IPL Analytics Platform
        </h1>
        <p style='text-align:center; font-size:1.15rem; color:#AAAAAA;
                  margin-top:4px; margin-bottom:28px;'>
            <b>18 Seasons</b> &nbsp;|&nbsp; <b>1,200+ Matches</b> &nbsp;|&nbsp;
            <b>700+ Players</b> &nbsp;|&nbsp; <b>40+ Venues</b><br/>
            <em>Every stat. Every matchup. Every record. One platform.</em>
        </p>
    """, unsafe_allow_html=True)

    # Season range filter (inline)
    fc1, fc2, fc3 = st.columns([1, 2, 1])
    with fc2:
        season_range = st.slider(
            "Season Range",
            min_value=2008,
            max_value=2025,
            value=st.session_state["season_range"],
            key="global_season_range",
        )
        st.session_state["season_range"] = season_range

    s_start, s_end = season_range

    # Headline Metrics
    metrics = load_headline_metrics(s_start, s_end)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Matches", format_number(metrics["total_matches"]))
    m2.metric("Total Runs", format_number(metrics["total_runs"]))
    m3.metric("Total Wickets", format_number(metrics["total_wickets"]))
    m4.metric("Total Sixes", format_number(metrics["total_sixes"]))
    m5.metric("Total Fours", format_number(metrics["total_fours"]))
    m6.metric("Unique Players", format_number(metrics["unique_players"]))

    st.divider()

    # Evolution Timeline
    evo_df = load_season_evolution(s_start, s_end)
    if not evo_df.empty:
        st.plotly_chart(build_evolution_chart(evo_df), width='stretch')

    st.divider()

    # Champion Roll of Honor
    champs_df = load_champions(s_start, s_end)
    if not champs_df.empty:
        st.plotly_chart(build_champions_chart(champs_df), width='stretch')

    st.divider()

    # Latest Season Highlights
    latest_info = load_latest_season_info(s_end)
    st.subheader(f"Season {s_end} Highlights")

    if not latest_info.empty:
        row = latest_info.iloc[0]
        champion = row.get("champion", "N/A") or "N/A"
        total_m = int(row.get("total_matches", 0))
        top_scorer, top_runs = load_latest_top_scorer(s_end)
        top_bowler, top_wkts = load_latest_top_wicket_taker(s_end)

        h1, h2 = st.columns(2)
        h1.metric("Champion", champion)
        h2.metric("Matches Played", format_number(total_m))

        h3, h4 = st.columns(2)
        h3.metric("Top Run-Scorer", top_scorer, delta=f"{format_number(top_runs)} runs")
        h4.metric("Top Wicket-Taker", top_bowler, delta=f"{top_wkts} wkts")
    else:
        st.info(f"No data available for season {s_end}.")

    st.divider()

    # Latest Season Top 5
    col_bat, col_bowl = st.columns(2)
    top_bat = load_top_batters_season(s_end)
    top_bowl = load_top_bowlers_season(s_end)

    with col_bat:
        if not top_bat.empty:
            fig = build_horizontal_bar(
                top_bat, x_col="total_runs", y_col="batter",
                title=f"Top 5 Run-Scorers -- {s_end}", color=IPL_COLORWAY[3],
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No batting data for this season.")

    with col_bowl:
        if not top_bowl.empty:
            fig = build_horizontal_bar(
                top_bowl, x_col="total_wickets", y_col="bowler",
                title=f"Top 5 Wicket-Takers -- {s_end}", color=IPL_COLORWAY[2],
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No bowling data for this season.")

    st.divider()

    # All-Time Leaders
    st.subheader(f"All-Time Leaders ({s_start} - {s_end})")
    col_at_bat, col_at_bowl = st.columns(2)
    at_bat = load_alltime_top_batters(s_start, s_end)
    at_bowl = load_alltime_top_bowlers(s_start, s_end)

    with col_at_bat:
        if not at_bat.empty:
            fig = build_horizontal_bar(
                at_bat, x_col="total_runs", y_col="batter",
                title="All-Time Top 10 Run-Scorers", color=IPL_COLORWAY[0], height=420,
            )
            st.plotly_chart(fig, width='stretch')

    with col_at_bowl:
        if not at_bowl.empty:
            fig = build_horizontal_bar(
                at_bowl, x_col="total_wickets", y_col="bowler",
                title="All-Time Top 10 Wicket-Takers", color=IPL_COLORWAY[1], height=420,
            )
            st.plotly_chart(fig, width='stretch')



main()
