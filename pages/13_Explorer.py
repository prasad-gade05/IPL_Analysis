"""
Explorer — Free-form custom query builder for power users.
Build dynamic queries across all IPL datasets with interactive filters,
auto-generated charts, and one-click preset queries.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import apply_ipl_style, IPL_COLORWAY, big_number_style
from src.utils.constants import ALL_SEASONS
from src.utils.formatters import format_number

# ─── Page Config ────────────────────────────────────────────────────────
st.markdown(big_number_style(), unsafe_allow_html=True)

# ─── Cached helpers ─────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def run_query(sql: str, params: list | None = None) -> pd.DataFrame:
    """Execute SQL and return DataFrame (cached)."""
    return query(sql, params)


@st.cache_data(ttl=3600)
def get_all_batters() -> list[str]:
    df = query("SELECT DISTINCT batter FROM player_batting ORDER BY batter")
    return df["batter"].tolist()


@st.cache_data(ttl=3600)
def get_all_bowlers() -> list[str]:
    df = query("SELECT DISTINCT bowler FROM player_bowling ORDER BY bowler")
    return df["bowler"].tolist()


@st.cache_data(ttl=3600)
def get_all_teams() -> list[str]:
    df = query(
        "SELECT DISTINCT team FROM ("
        "  SELECT DISTINCT batting_team AS team FROM player_batting"
        "  UNION"
        "  SELECT DISTINCT bowling_team AS team FROM player_bowling"
        ") ORDER BY team"
    )
    return df["team"].tolist()


@st.cache_data(ttl=3600)
def get_all_venues() -> list[str]:
    df = query("SELECT DISTINCT venue FROM matches ORDER BY venue")
    return df["venue"].tolist()


@st.cache_data(ttl=3600)
def get_all_stages() -> list[str]:
    df = query("SELECT DISTINCT stage FROM matches WHERE stage IS NOT NULL ORDER BY stage")
    return df["stage"].tolist()


@st.cache_data(ttl=3600)
def get_view_columns(view_name: str) -> pd.DataFrame:
    df = query(f"SELECT * FROM {view_name} LIMIT 0")
    return pd.DataFrame({
        "Column": df.columns,
        "Type": [str(df[c].dtype) for c in df.columns],
    })


@st.cache_data(ttl=3600)
def get_view_sample(view_name: str) -> pd.DataFrame:
    return query(f"SELECT * FROM {view_name} LIMIT 5")


# ─── Preset query definitions ──────────────────────────────────────────

PRESET_QUERIES: dict[str, dict] = {
    "Top 10 All-Time Run Scorers": {
        "sql": """
            SELECT batter AS Player,
                   SUM(runs) AS Runs,
                   SUM(balls) AS Balls,
                   COUNT(*) AS Innings,
                   SUM(fours) AS Fours,
                   SUM(sixes) AS Sixes,
                   ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 2) AS SR
            FROM player_batting
            GROUP BY batter
            ORDER BY Runs DESC
            LIMIT 10
        """,
        "chart": "bar",
        "x": "Player",
        "y": "Runs",
    },
    "1000+ Runs & 100+ Sixes": {
        "sql": """
            SELECT batter AS Player,
                   SUM(runs) AS Runs,
                   SUM(sixes) AS Sixes,
                   SUM(balls) AS Balls,
                   ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 2) AS SR
            FROM player_batting
            GROUP BY batter
            HAVING SUM(runs) >= 1000 AND SUM(sixes) >= 100
            ORDER BY Sixes DESC
        """,
        "chart": "bar",
        "x": "Player",
        "y": "Sixes",
    },
    "200+ Scores That Lost": {
        "sql": """
            SELECT m.match_id, m.season AS Season, m.venue AS Venue,
                   m.team1 AS Team1, m.team1_score AS T1_Score,
                   m.team2 AS Team2, m.team2_score AS T2_Score,
                   m.match_won_by AS Winner
            FROM matches m
            WHERE (m.team1_score >= 200 AND m.match_won_by = m.team2)
               OR (m.team2_score >= 200 AND m.match_won_by = m.team1)
            ORDER BY GREATEST(m.team1_score, m.team2_score) DESC
        """,
        "chart": "none",
        "x": "",
        "y": "",
    },
    "Best Death Economy (min 200 balls)": {
        "sql": """
            SELECT b.bowler AS Bowler,
                   COUNT(*) AS Balls,
                   SUM((b.runs_batter + b.runs_extras)) AS Runs,
                   SUM(CASE WHEN b.player_out IS NOT NULL THEN 1 ELSE 0 END) AS Wickets,
                   ROUND(SUM((b.runs_batter + b.runs_extras)) * 6.0 / COUNT(*), 2) AS Economy
            FROM balls b
            WHERE b.match_phase = 'death' AND b.valid_ball = true
            GROUP BY b.bowler
            HAVING COUNT(*) >= 200
            ORDER BY Economy ASC
            LIMIT 15
        """,
        "chart": "bar",
        "x": "Bowler",
        "y": "Economy",
    },
    "Players for 5+ Teams": {
        "sql": """
            SELECT batter AS Player,
                   COUNT(DISTINCT batting_team) AS Teams,
                   SUM(runs) AS Runs,
                   LIST(DISTINCT batting_team) AS Team_List
            FROM player_batting
            GROUP BY batter
            HAVING COUNT(DISTINCT batting_team) >= 5
            ORDER BY Teams DESC, Runs DESC
        """,
        "chart": "bar",
        "x": "Player",
        "y": "Teams",
    },
    "Highest Partnership Stands": {
        "sql": """
            SELECT p.batting_partners AS Partners,
                   p.runs AS Runs,
                   p.balls AS Balls,
                   p.batting_team AS Team,
                   p.season AS Season,
                   p.wicket_number AS Wicket
            FROM partnerships p
            ORDER BY p.runs DESC
            LIMIT 15
        """,
        "chart": "bar",
        "x": "Partners",
        "y": "Runs",
    },
    "Most Expensive Overs (20+ runs)": {
        "sql": """
            SELECT b.bowler AS Bowler,
                   b.batter AS Batter,
                   b.batting_team AS Batting_Team,
                   b.over AS Over_No,
                   b.season AS Season,
                   b.venue AS Venue,
                   SUM((b.runs_batter + b.runs_extras)) AS Over_Runs
            FROM balls b
            GROUP BY b.match_id, b.innings, b.over,
                     b.bowler, b.batter, b.batting_team, b.season, b.venue
            HAVING SUM((b.runs_batter + b.runs_extras)) >= 20
            ORDER BY Over_Runs DESC
            LIMIT 20
        """,
        "chart": "bar",
        "x": "Bowler",
        "y": "Over_Runs",
    },
    "Super Over Results": {
        "sql": """
            SELECT m.match_id, m.season AS Season,
                   m.team1 AS Team1, m.team1_score AS T1_Score,
                   m.team2 AS Team2, m.team2_score AS T2_Score,
                   m.match_won_by AS Winner,
                   m.venue AS Venue
            FROM matches m
            WHERE m.is_super_over_match = true
            ORDER BY m.season DESC
        """,
        "chart": "none",
        "x": "",
        "y": "",
    },
}

# ─── View metadata for Data Dictionary ──────────────────────────────────

VIEW_DESCRIPTIONS: dict[str, str] = {
    "balls": "Ball-by-ball event log — every delivery bowled (90 cols, ~278K rows)",
    "matches": "Match-level summaries with scores, result, toss (24 cols, ~1.2K rows)",
    "player_batting": "Per-match batting scorecard for each batter (18 cols, ~17.7K rows)",
    "player_bowling": "Per-match bowling figures for each bowler (15 cols, ~13.9K rows)",
    "matchups": "Head-to-head batter vs bowler aggregated stats (12 cols, ~29.5K rows)",
    "venues": "Venue-level aggregate statistics (9 cols, 42 rows)",
    "partnerships": "Batting partnership data per innings (12 cols, ~15.7K rows)",
    "powerplay": "Powerplay (overs 1-6) stats per innings (14 cols, ~2.4K rows)",
    "season_meta": "Season-level metadata — dates, champion, team count (11 cols, 18 rows)",
    "team_season": "Team seasonal win/loss summary (7 cols, 156 rows)",
    "points_table": "League standings with NRR and positions (9 cols, 156 rows)",
    "dismissals": "Dismissal type counts per player (3 cols, ~2.1K rows)",
    "dismissals_phase": "Dismissal types broken down by match phase (4 cols, ~3.4K rows)",
    "dot_sequences": "Consecutive dot ball sequence outcomes (4 cols, 34 rows)",
}

# ─── SQL builder functions ──────────────────────────────────────────────

def _build_batting_query(
    players: list[str],
    season_range: tuple[int, int],
    teams: list[str],
    min_runs: int,
    min_balls: int,
    group_by: str,
    sort_col: str,
    limit: int,
) -> tuple[str, list]:
    group_map = {
        "Player": "batter",
        "Season": "season",
        "Team": "batting_team",
        "Venue": "venue",
        "Player + Season": "batter, season",
    }
    gb_cols = group_map.get(group_by, "batter")

    select_cols = f"{gb_cols}"
    agg = (
        "SUM(runs) AS total_runs, SUM(balls) AS total_balls, "
        "COUNT(*) AS innings, "
        "SUM(fours) AS fours, SUM(sixes) AS sixes, "
        "SUM(CASE WHEN was_out THEN 1 ELSE 0 END) AS outs, "
        "ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 2) AS strike_rate, "
        "ROUND(SUM(runs) * 1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0), 2) AS average"
    )

    where_parts: list[str] = []
    params: list = []

    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if players:
        placeholders = ", ".join(["?"] * len(players))
        where_parts.append(f"batter IN ({placeholders})")
        params.extend(players)

    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"batting_team IN ({placeholders})")
        params.extend(teams)

    where_clause = " AND ".join(where_parts)

    having_parts: list[str] = []
    if min_runs > 0:
        having_parts.append(f"SUM(runs) >= {min_runs}")
    if min_balls > 0:
        having_parts.append(f"SUM(balls) >= {min_balls}")
    having_clause = (" HAVING " + " AND ".join(having_parts)) if having_parts else ""

    valid_sort_cols = {
        "total_runs", "total_balls", "innings", "fours", "sixes",
        "outs", "strike_rate", "average",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "total_runs"

    sql = (
        f"SELECT {select_cols}, {agg} "
        f"FROM player_batting "
        f"WHERE {where_clause} "
        f"GROUP BY {gb_cols}"
        f"{having_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_bowling_query(
    bowlers: list[str],
    season_range: tuple[int, int],
    teams: list[str],
    min_wickets: int,
    min_balls: int,
    group_by: str,
    sort_col: str,
    limit: int,
) -> tuple[str, list]:
    group_map = {
        "Player": "bowler",
        "Season": "season",
        "Team": "bowling_team",
        "Venue": "venue",
        "Player + Season": "bowler, season",
    }
    gb_cols = group_map.get(group_by, "bowler")

    agg = (
        "SUM(balls_bowled) AS total_balls, "
        "SUM(wickets) AS total_wickets, "
        "SUM(runs_conceded) AS runs_conceded, "
        "COUNT(*) AS innings, "
        "SUM(maidens) AS maidens, "
        "SUM(dots_bowled) AS dots, "
        "ROUND(SUM(runs_conceded) * 6.0 / NULLIF(SUM(balls_bowled), 0), 2) AS economy, "
        "ROUND(SUM(balls_bowled) * 1.0 / NULLIF(SUM(wickets), 0), 2) AS bowling_sr"
    )

    where_parts: list[str] = []
    params: list = []

    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if bowlers:
        placeholders = ", ".join(["?"] * len(bowlers))
        where_parts.append(f"bowler IN ({placeholders})")
        params.extend(bowlers)

    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"bowling_team IN ({placeholders})")
        params.extend(teams)

    where_clause = " AND ".join(where_parts)

    having_parts: list[str] = []
    if min_wickets > 0:
        having_parts.append(f"SUM(wickets) >= {min_wickets}")
    if min_balls > 0:
        having_parts.append(f"SUM(balls_bowled) >= {min_balls}")
    having_clause = (" HAVING " + " AND ".join(having_parts)) if having_parts else ""

    valid_sort_cols = {
        "total_balls", "total_wickets", "runs_conceded", "innings",
        "maidens", "dots", "economy", "bowling_sr",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "total_wickets"

    sql = (
        f"SELECT {gb_cols}, {agg} "
        f"FROM player_bowling "
        f"WHERE {where_clause} "
        f"GROUP BY {gb_cols}"
        f"{having_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_team_query(
    teams: list[str],
    season_range: tuple[int, int],
    group_by: str,
    sort_col: str,
    limit: int,
) -> tuple[str, list]:
    group_map = {
        "Team": "team",
        "Season": "season",
        "Team + Season": "team, season",
    }
    gb_cols = group_map.get(group_by, "team")

    agg = (
        "SUM(matches_played) AS matches, "
        "SUM(wins) AS wins, "
        "SUM(losses) AS losses, "
        "ROUND(SUM(wins) * 100.0 / NULLIF(SUM(matches_played), 0), 2) AS win_pct"
    )

    where_parts: list[str] = []
    params: list = []

    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"team IN ({placeholders})")
        params.extend(teams)

    where_clause = " AND ".join(where_parts)

    valid_sort_cols = {"matches", "wins", "losses", "win_pct"}
    if sort_col not in valid_sort_cols:
        sort_col = "wins"

    sql = (
        f"SELECT {gb_cols}, {agg} "
        f"FROM team_season "
        f"WHERE {where_clause} "
        f"GROUP BY {gb_cols} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_match_query(
    season_range: tuple[int, int],
    stages: list[str],
    venues: list[str],
    sort_col: str,
    limit: int,
) -> tuple[str, list]:
    where_parts: list[str] = []
    params: list = []

    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if stages:
        placeholders = ", ".join(["?"] * len(stages))
        where_parts.append(f"stage IN ({placeholders})")
        params.extend(stages)

    if venues:
        placeholders = ", ".join(["?"] * len(venues))
        where_parts.append(f"venue IN ({placeholders})")
        params.extend(venues)

    where_clause = " AND ".join(where_parts)

    valid_sort_cols = {
        "season", "date", "team1_score", "team2_score", "win_margin_value",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "date"

    sql = (
        "SELECT match_id, season, date, venue, team1, team2, "
        "team1_score, team1_wickets, team2_score, team2_wickets, "
        "match_won_by, win_margin_value, win_margin_type, stage, "
        "toss_winner, toss_decision, player_of_match "
        f"FROM matches "
        f"WHERE {where_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_ball_query(
    season_range: tuple[int, int],
    teams: list[str],
    batters: list[str],
    bowlers: list[str],
    phases: list[str],
    over_range: tuple[int, int],
    sort_col: str,
    limit: int,
) -> tuple[str, list]:
    where_parts: list[str] = []
    params: list = []

    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    where_parts.append("over BETWEEN ? AND ?")
    params.extend([over_range[0], over_range[1]])

    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"batting_team IN ({placeholders})")
        params.extend(teams)

    if batters:
        placeholders = ", ".join(["?"] * len(batters))
        where_parts.append(f"batter IN ({placeholders})")
        params.extend(batters)

    if bowlers:
        placeholders = ", ".join(["?"] * len(bowlers))
        where_parts.append(f"bowler IN ({placeholders})")
        params.extend(bowlers)

    if phases:
        placeholders = ", ".join(["?"] * len(phases))
        where_parts.append(f"match_phase IN ({placeholders})")
        params.extend(phases)

    where_clause = " AND ".join(where_parts)

    valid_sort_cols = {
        "(runs_batter + runs_extras)", "over", "ball", "season", "runs_batter",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "(runs_batter + runs_extras)"

    sql = (
        "SELECT match_id, season, innings, over, ball, "
        "batter, bowler, batting_team, bowling_team, "
        "runs_batter, (runs_batter + runs_extras), is_four, is_six, is_dot, "
        "wicket_kind, player_out, match_phase, venue "
        f"FROM balls "
        f"WHERE {where_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


# ─── Auto-chart logic ───────────────────────────────────────────────────

def _auto_chart(df: pd.DataFrame, group_by: str, entity_type: str):
    """Generate an appropriate chart based on grouping and entity type."""
    if df.empty or len(df) < 2:
        return

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        return

    # Pick best y-axis metric
    y_col = numeric_cols[0]
    priority_batting = ["total_runs", "strike_rate", "average", "Runs"]
    priority_bowling = ["total_wickets", "economy", "bowling_sr"]
    priority_team = ["wins", "win_pct"]
    if entity_type == "Batting Stats":
        for c in priority_batting:
            if c in numeric_cols:
                y_col = c
                break
    elif entity_type == "Bowling Stats":
        for c in priority_bowling:
            if c in numeric_cols:
                y_col = c
                break
    elif entity_type == "Team Stats":
        for c in priority_team:
            if c in numeric_cols:
                y_col = c
                break

    non_numeric = df.select_dtypes(exclude="number").columns.tolist()
    x_col = non_numeric[0] if non_numeric else df.columns[0]

    if group_by in ("Season", "Player + Season", "Team + Season"):
        x_col = "season" if "season" in df.columns else x_col
        fig = px.line(
            df.sort_values(x_col) if x_col in df.columns else df,
            x=x_col, y=y_col,
            title=f"{y_col.replace('_', ' ').title()} by {group_by}",
            markers=True,
        )
    elif group_by in ("Player", "Team"):
        label_col = {
            "Player": next((c for c in ["batter", "bowler", "Player"] if c in df.columns), x_col),
            "Team": next((c for c in ["team", "batting_team", "bowling_team", "Team"] if c in df.columns), x_col),
        }.get(group_by, x_col)
        chart_df = df.sort_values(y_col, ascending=True).tail(30)
        fig = px.bar(
            chart_df, x=y_col, y=label_col,
            orientation="h",
            title=f"{y_col.replace('_', ' ').title()} by {group_by}",
            text_auto=True,
        )
    else:
        return

    apply_ipl_style(fig, height=450)
    st.plotly_chart(fig, width='stretch')


def _show_summary_stats(df: pd.DataFrame):
    """Display summary statistics for numeric columns."""
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.empty:
        return
    stats = numeric_df.describe().loc[["count", "mean", "min", "50%", "max"]].T
    stats.columns = ["Count", "Mean", "Min", "Median", "Max"]
    stats["Mean"] = stats["Mean"].round(2)
    stats["Median"] = stats["Median"].round(2)
    st.dataframe(stats, width='stretch')


# ─── Page UI ────────────────────────────────────────────────────────────

st.title("Explorer")
st.caption("Power-user query builder — slice and dice IPL data with custom filters, presets, and instant charts.")

# ── Preset Queries ──────────────────────────────────────────────────────
st.subheader("Quick Presets")

preset_names = list(PRESET_QUERIES.keys())
cols = st.columns(4)
preset_clicked: str | None = None

for i, name in enumerate(preset_names):
    with cols[i % 4]:
        if st.button(name, key=f"preset_{i}", width='stretch'):
            preset_clicked = name

if preset_clicked:
    preset = PRESET_QUERIES[preset_clicked]
    st.markdown(f"### {preset_clicked}")
    with st.expander("SQL Query", expanded=False):
        st.code(preset["sql"].strip(), language="sql")

    try:
        preset_df = run_query(preset["sql"])
        if preset_df.empty:
            st.info("No results found for this query.")
        else:
            if preset["chart"] == "bar" and preset["x"] and preset["y"]:
                chart_df = preset_df.sort_values(preset["y"], ascending=True)
                fig = px.bar(
                    chart_df,
                    x=preset["y"], y=preset["x"],
                    orientation="h",
                    title=preset_clicked,
                    text_auto=True,
                )
                apply_ipl_style(fig, height=max(400, len(chart_df) * 28))
                st.plotly_chart(fig, width='stretch')

            st.dataframe(preset_df, width='stretch', hide_index=True)

            csv = preset_df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                file_name="explorer_preset_results.csv",
                mime="text/csv",
                key="preset_download",
            )
    except Exception as e:
        st.error(f"Query error: {e}")

    st.divider()

# ── Custom Query Builder ────────────────────────────────────────────────
st.subheader("Custom Query Builder")

entity_type = st.radio(
    "Select entity type",
    ["Batting Stats", "Bowling Stats", "Team Stats", "Match Stats", "Ball-by-Ball"],
    horizontal=True,
    key="entity_type",
)

with st.form("query_builder_form"):
    # ── Common filters ──
    season_col1, season_col2, limit_col = st.columns([1, 1, 1])
    with season_col1:
        season_start = st.selectbox(
            "Season from",
            ALL_SEASONS,
            index=0,
            key="season_start",
        )
    with season_col2:
        season_end = st.selectbox(
            "Season to",
            ALL_SEASONS,
            index=len(ALL_SEASONS) - 1,
            key="season_end",
        )
    with limit_col:
        limit = st.slider("Result limit", 10, 100, 25, key="limit_slider")

    # ── Entity-specific filters ──
    sql_to_run: str = ""
    sql_params: list = []
    current_group_by: str = "Player"

    if entity_type == "Batting Stats":
        fc1, fc2 = st.columns(2)
        with fc1:
            sel_players = st.multiselect("Filter batters (optional)", get_all_batters(), key="bat_players")
            sel_teams = st.multiselect("Filter teams (optional)", get_all_teams(), key="bat_teams")
        with fc2:
            current_group_by = st.selectbox(
                "Group by",
                ["Player", "Season", "Team", "Venue", "Player + Season"],
                key="bat_group",
            )
            sort_by = st.selectbox(
                "Sort by",
                ["total_runs", "strike_rate", "average", "innings", "sixes", "fours"],
                key="bat_sort",
            )
        mc1, mc2 = st.columns(2)
        with mc1:
            min_runs = st.slider("Min total runs", 0, 1000, 0, step=50, key="bat_min_runs")
        with mc2:
            min_balls = st.slider("Min total balls", 0, 500, 0, step=25, key="bat_min_balls")

    elif entity_type == "Bowling Stats":
        fc1, fc2 = st.columns(2)
        with fc1:
            sel_bowlers = st.multiselect("Filter bowlers (optional)", get_all_bowlers(), key="bowl_players")
            sel_teams = st.multiselect("Filter teams (optional)", get_all_teams(), key="bowl_teams")
        with fc2:
            current_group_by = st.selectbox(
                "Group by",
                ["Player", "Season", "Team", "Venue", "Player + Season"],
                key="bowl_group",
            )
            sort_by = st.selectbox(
                "Sort by",
                ["total_wickets", "economy", "bowling_sr", "innings", "dots", "maidens"],
                key="bowl_sort",
            )
        mc1, mc2 = st.columns(2)
        with mc1:
            min_wickets = st.slider("Min total wickets", 0, 100, 0, step=5, key="bowl_min_wkts")
        with mc2:
            min_balls = st.slider("Min total balls bowled", 0, 500, 0, step=25, key="bowl_min_balls")

    elif entity_type == "Team Stats":
        fc1, fc2 = st.columns(2)
        with fc1:
            sel_teams = st.multiselect("Filter teams (optional)", get_all_teams(), key="team_filter")
        with fc2:
            current_group_by = st.selectbox(
                "Group by",
                ["Team", "Season", "Team + Season"],
                key="team_group",
            )
            sort_by = st.selectbox(
                "Sort by",
                ["wins", "win_pct", "matches", "losses"],
                key="team_sort",
            )

    elif entity_type == "Match Stats":
        fc1, fc2 = st.columns(2)
        with fc1:
            sel_stages = st.multiselect("Stage filter (optional)", get_all_stages(), key="match_stages")
        with fc2:
            sel_venues = st.multiselect("Venue filter (optional)", get_all_venues(), key="match_venues")
        sort_by = st.selectbox(
            "Sort by",
            ["date", "team1_score", "team2_score", "win_margin_value", "season"],
            key="match_sort",
        )

    elif entity_type == "Ball-by-Ball":
        fc1, fc2 = st.columns(2)
        with fc1:
            sel_teams = st.multiselect("Team filter (optional)", get_all_teams(), key="bbb_teams")
            sel_batters = st.multiselect("Batter filter (optional)", get_all_batters(), key="bbb_batters")
        with fc2:
            sel_bowlers_bbb = st.multiselect("Bowler filter (optional)", get_all_bowlers(), key="bbb_bowlers")
            sel_phases = st.multiselect("Phase filter", ["powerplay", "middle", "death"], key="bbb_phases")
        oc1, oc2 = st.columns(2)
        with oc1:
            over_start = st.number_input("Over from", 1, 20, 1, key="over_start")
        with oc2:
            over_end = st.number_input("Over to", 1, 20, 20, key="over_end")
        sort_by = st.selectbox(
            "Sort by",
            ["(runs_batter + runs_extras)", "runs_batter", "over", "season"],
            key="bbb_sort",
        )

    submitted = st.form_submit_button("Run Query", width='stretch', type="primary")

# ── Execute query after form submission ─────────────────────────────────
if submitted:
    season_range = (
        min(season_start, season_end),
        max(season_start, season_end),
    )

    try:
        if entity_type == "Batting Stats":
            sql_to_run, sql_params = _build_batting_query(
                sel_players, season_range, sel_teams,
                min_runs, min_balls, current_group_by, sort_by, limit,
            )
        elif entity_type == "Bowling Stats":
            sql_to_run, sql_params = _build_bowling_query(
                sel_bowlers, season_range, sel_teams,
                min_wickets, min_balls, current_group_by, sort_by, limit,
            )
        elif entity_type == "Team Stats":
            sql_to_run, sql_params = _build_team_query(
                sel_teams, season_range, current_group_by, sort_by, limit,
            )
        elif entity_type == "Match Stats":
            sql_to_run, sql_params = _build_match_query(
                season_range, sel_stages, sel_venues, sort_by, limit,
            )
        elif entity_type == "Ball-by-Ball":
            sql_to_run, sql_params = _build_ball_query(
                season_range, sel_teams, sel_batters, sel_bowlers_bbb,
                sel_phases, (int(over_start), int(over_end)), sort_by, limit,
            )

        with st.expander("Generated SQL", expanded=False):
            st.code(sql_to_run.strip(), language="sql")
            if sql_params:
                st.caption(f"Parameters: `{sql_params}`")

        result_df = run_query(sql_to_run, sql_params)

        if result_df.empty:
            st.warning("No results found. Try broadening your filters.")
        else:
            st.success(f"{format_number(len(result_df))} rows returned")

            # Summary metrics
            m1, m2, m3, m4 = st.columns(4)
            numeric_cols = result_df.select_dtypes(include="number").columns.tolist()
            if numeric_cols:
                primary = numeric_cols[0]
                m1.metric("Rows", format_number(len(result_df)))
                m2.metric(f"Σ {primary}", format_number(result_df[primary].sum()))
                m3.metric(f"Avg {primary}", format_number(result_df[primary].mean(), decimals=1))
                m4.metric(f"Max {primary}", format_number(result_df[primary].max()))

            # Auto-chart
            if entity_type in ("Batting Stats", "Bowling Stats", "Team Stats"):
                _auto_chart(result_df, current_group_by, entity_type)

            # Result table
            st.dataframe(result_df, width='stretch', hide_index=True)

            # Summary statistics
            with st.expander("Summary Statistics"):
                _show_summary_stats(result_df)

            # Export
            csv = result_df.to_csv(index=False)
            st.download_button(
                "Download Results as CSV",
                csv,
                file_name="explorer_results.csv",
                mime="text/csv",
                key="custom_download",
            )

    except Exception as e:
        st.error(f"Query error: {e}")
        st.exception(e)

# ── Data Dictionary ─────────────────────────────────────────────────────
st.divider()
st.subheader("Data Dictionary")

with st.expander("Browse available views and their schemas", expanded=False):
    selected_view = st.selectbox(
        "Select a view",
        list(VIEW_DESCRIPTIONS.keys()),
        key="dict_view",
    )

    st.markdown(f"**{selected_view}** — {VIEW_DESCRIPTIONS.get(selected_view, '')}")

    tab_schema, tab_sample = st.tabs(["Schema", "Sample Data"])

    with tab_schema:
        try:
            col_df = get_view_columns(selected_view)
            st.dataframe(col_df, width='stretch', hide_index=True)
        except Exception as e:
            st.error(f"Could not load schema: {e}")

    with tab_sample:
        try:
            sample_df = get_view_sample(selected_view)
            st.dataframe(sample_df, width='stretch', hide_index=True)
        except Exception as e:
            st.error(f"Could not load sample: {e}")
