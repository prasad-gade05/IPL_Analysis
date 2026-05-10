"""
Phase Analysis — Powerplay, Middle, Death over deep-dive.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style, styled_bar, styled_line,
    get_team_color, big_number_style, IPL_COLORWAY,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS, PHASE_COLORS
from src.utils.formatters import format_number, format_strike_rate, format_economy
from src.utils.control_renderer import render_visual_controls, active_control_chips
from src.utils.control_schema import VisualSpec
from src.utils.visual_specs import limit_control, number_control, season_range_control, select_control
from src.visualizations.card_renderer import render_active_filters

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(big_number_style(), unsafe_allow_html=True)
st.title("Phase Analysis")
st.caption("Deep-dive into Powerplay (overs 1–6), Middle (7–15), and Death (16–20) overs")

DEFAULT_SEASON_RANGE = (min(ALL_SEASONS), max(ALL_SEASONS))


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _sanitize_season_range(season_range: tuple[int, int] | None = None) -> tuple[int, int]:
    if season_range is None:
        return DEFAULT_SEASON_RANGE
    start, end = season_range
    start = max(DEFAULT_SEASON_RANGE[0], int(start))
    end = min(DEFAULT_SEASON_RANGE[1], int(end))
    return (start, end) if start <= end else (end, start)


def _season_condition(column: str, season_range: tuple[int, int] | None = None) -> str:
    start, end = _sanitize_season_range(season_range)
    return f"{column} BETWEEN {start} AND {end}"


def _sanitize_limit(limit: int | None, default: int) -> int:
    return max(1, int(limit or default))


def _sanitize_minimum(value: int | None, default: int, minimum: int = 1) -> int:
    return max(minimum, int(default if value is None else value))


def _innings_filter(innings_choice: str) -> str:
    if innings_choice == "1st Innings":
        return "AND innings = 1"
    elif innings_choice == "2nd Innings":
        return "AND innings = 2"
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — POWERPLAY (precomputed view)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _pp_avg_trend(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    df = query(f"""
        SELECT season, innings, ROUND(AVG(pp_runs), 2) AS avg_runs
        FROM   powerplay
        WHERE  {season_filter} {inn_filter}
        GROUP  BY season, innings
        ORDER  BY season, innings
    """)
    df["innings"] = df["innings"].map({1: "1st Innings", 2: "2nd Innings"})
    return df


@st.cache_data(ttl=3600)
def _pp_distribution(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    return query(f"""
        SELECT pp_runs AS runs
        FROM   powerplay
        WHERE  {season_filter} {inn_filter}
    """)


@st.cache_data(ttl=3600)
def _pp_team_avg(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both", min_innings=5):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    min_innings = _sanitize_minimum(min_innings, 5, 1)
    return query(f"""
        SELECT batting_team AS team,
               ROUND(AVG(pp_runs), 2) AS avg_runs,
               COUNT(*) AS innings_count
        FROM   powerplay
        WHERE  {season_filter} {inn_filter}
        GROUP  BY batting_team
        HAVING COUNT(*) >= {min_innings}
        ORDER  BY avg_runs DESC
    """)


@st.cache_data(ttl=3600)
def _pp_dot_trend(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    return query(f"""
        SELECT season,
               ROUND(SUM(pp_dots) * 100.0
                     / NULLIF(SUM(pp_balls), 0), 2) AS dot_pct
        FROM   powerplay
        WHERE  {season_filter} {inn_filter}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _pp_boundary_trend(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    return query(f"""
        SELECT season,
               ROUND(SUM(pp_boundaries) * 100.0
                     / NULLIF(SUM(pp_balls), 0), 2) AS boundary_pct
        FROM   powerplay
        WHERE  {season_filter} {inn_filter}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _pp_best_scores(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both", limit=15):
    season_filter = _season_condition("p.season", season_range)
    inn_filter = _innings_filter(innings_choice).replace("innings", "p.innings")
    limit = _sanitize_limit(limit, 15)
    return query(f"""
        SELECT p.batting_team AS team,
               p.pp_runs      AS runs,
               p.pp_wickets   AS wickets,
               CASE WHEN m.team1 = p.batting_team
                    THEN m.team2 ELSE m.team1 END AS vs,
               p.season
        FROM   powerplay p
        JOIN   matches   m ON p.match_id = m.match_id
        WHERE  {season_filter} {inn_filter}
        ORDER  BY p.pp_runs DESC
        LIMIT  {limit}
    """)


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — GENERIC PHASE (middle / death, from balls)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _phase_avg_trend(phase, season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    df = query(f"""
        SELECT season, innings, ROUND(AVG(phase_runs), 2) AS avg_runs
        FROM (
            SELECT match_id, innings, season,
                   SUM((runs_batter + runs_extras)) AS phase_runs
            FROM   balls
            WHERE  match_phase = '{phase}'
              AND  {season_filter} {inn_filter}
            GROUP  BY match_id, innings, season
        ) sub
        GROUP BY season, innings
        ORDER BY season, innings
    """)
    df["innings"] = df["innings"].map({1: "1st Innings", 2: "2nd Innings"})
    return df


@st.cache_data(ttl=3600)
def _phase_distribution(phase, season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    return query(f"""
        SELECT SUM((runs_batter + runs_extras)) AS runs
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  {season_filter} {inn_filter}
        GROUP  BY match_id, innings
    """)


@st.cache_data(ttl=3600)
def _phase_team_avg(phase, season_range=DEFAULT_SEASON_RANGE, innings_choice="Both", min_innings=5):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    min_innings = _sanitize_minimum(min_innings, 5, 1)
    return query(f"""
        SELECT team,
               ROUND(AVG(phase_runs), 2) AS avg_runs,
               COUNT(*) AS innings_count
        FROM (
            SELECT match_id, innings,
                   MAX(batting_team) AS team,
                   SUM((runs_batter + runs_extras))   AS phase_runs
            FROM   balls
            WHERE  match_phase = '{phase}'
              AND  {season_filter} {inn_filter}
            GROUP  BY match_id, innings
        ) sub
        GROUP  BY team
        HAVING COUNT(*) >= {min_innings}
        ORDER  BY avg_runs DESC
    """)


@st.cache_data(ttl=3600)
def _phase_dot_trend(phase, season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    return query(f"""
        SELECT season,
               ROUND(SUM(CASE WHEN is_dot THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 2)
                     AS dot_pct
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  {season_filter} {inn_filter}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _phase_boundary_trend(phase, season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    return query(f"""
        SELECT season,
               ROUND(SUM(CASE WHEN is_boundary THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 2)
                     AS boundary_pct
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  {season_filter} {inn_filter}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _phase_best_scores(phase, season_range=DEFAULT_SEASON_RANGE, innings_choice="Both", limit=15):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    limit = _sanitize_limit(limit, 15)
    return query(f"""
        SELECT team, phase_runs AS runs,
               phase_wickets AS wickets, vs, season
        FROM (
            SELECT match_id, innings, season,
                   MAX(batting_team) AS team,
                   MAX(bowling_team) AS vs,
                   SUM((runs_batter + runs_extras))   AS phase_runs,
                   SUM(CASE WHEN wicket_kind NOT IN ('not_out', 'retired hurt') THEN 1 ELSE 0 END)
                       AS phase_wickets
            FROM   balls
            WHERE  match_phase = '{phase}'
              AND  {season_filter} {inn_filter}
            GROUP  BY match_id, innings, season
        ) sub
        ORDER BY phase_runs DESC
        LIMIT {limit}
    """)


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — BATTER / BOWLER (any phase, from balls)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _phase_top_batters(phase, season_range=DEFAULT_SEASON_RANGE, innings_choice="Both", limit=15, min_balls=100):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    limit = _sanitize_limit(limit, 15)
    min_balls = _sanitize_minimum(min_balls, 100, 1)
    return query(f"""
        SELECT batter,
               SUM(runs_batter)::INT AS runs,
               SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS balls,
               ROUND(SUM(runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 2) AS sr,
                (SUM(CASE WHEN is_four THEN 1 ELSE 0 END)
                 + SUM(CASE WHEN is_six THEN 1 ELSE 0 END))::INT AS boundaries,
                ROUND(SUM(runs_batter) * 1.0
                     / NULLIF(SUM(CASE WHEN player_out = batter
                                       AND wicket_kind != 'retired hurt'
                                   THEN 1 ELSE 0 END), 0), 2) AS avg
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  {season_filter} {inn_filter}
        GROUP  BY batter
        HAVING SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) >= {min_balls}
        ORDER  BY runs DESC
        LIMIT  {limit}
    """)


@st.cache_data(ttl=3600)
def _phase_top_bowlers(phase, season_range=DEFAULT_SEASON_RANGE, innings_choice="Both", limit=15, min_balls=100):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    limit = _sanitize_limit(limit, 15)
    min_balls = _sanitize_minimum(min_balls, 100, 1)
    return query(f"""
        SELECT bowler,
               SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS balls,
               SUM(runs_bowler)::INT AS runs,
               SUM(bowler_wicket)::INT AS wickets,
               ROUND(SUM(runs_bowler) * 6.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 2) AS economy,
               ROUND(SUM(CASE WHEN is_dot THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 1) AS dot_pct
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  {season_filter} {inn_filter}
        GROUP  BY bowler
        HAVING SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) >= {min_balls}
        ORDER  BY wickets DESC
        LIMIT  {limit}
    """)


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — DEATH EXTRAS
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _death_sixes_trend(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    return query(f"""
        SELECT season,
               ROUND(
                   SUM(CASE WHEN is_six THEN 1 ELSE 0 END) * 1.0
                   / COUNT(DISTINCT match_id || '-' || CAST(innings AS VARCHAR)),
               2) AS avg_sixes
        FROM   balls
        WHERE  match_phase = 'death'
          AND  {season_filter} {inn_filter}
        GROUP  BY season
        ORDER  BY season
    """)


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — PHASE COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _phase_rr_evolution(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    df = query(f"""
        SELECT season, match_phase,
               ROUND(AVG(phase_rr), 2) AS avg_rr
        FROM (
            SELECT match_id, innings, season, match_phase,
                   SUM((runs_batter + runs_extras)) * 6.0
                       / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0)
                       AS phase_rr
            FROM   balls
            WHERE  match_phase IS NOT NULL
              AND  {season_filter} {inn_filter}
            GROUP  BY match_id, innings, season, match_phase
        ) sub
        GROUP BY season, match_phase
        ORDER BY season
    """)
    df["match_phase"] = df["match_phase"].str.capitalize()
    return df


@st.cache_data(ttl=3600)
def _phase_boundary_dist(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    df = query(f"""
        SELECT match_phase,
               SUM(CASE WHEN is_boundary THEN 1 ELSE 0 END)::INT AS boundaries
        FROM   balls
        WHERE  match_phase IS NOT NULL
          AND  {season_filter} {inn_filter}
        GROUP  BY match_phase
    """)
    df["match_phase"] = df["match_phase"].str.capitalize()
    return df


@st.cache_data(ttl=3600)
def _phase_wicket_dist(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    df = query(f"""
        SELECT match_phase,
               SUM(CASE WHEN wicket_kind NOT IN ('not_out', 'retired hurt') THEN 1 ELSE 0 END)::INT AS wickets
        FROM   balls
        WHERE  match_phase IS NOT NULL
          AND  {season_filter} {inn_filter}
        GROUP  BY match_phase
    """)
    df["match_phase"] = df["match_phase"].str.capitalize()
    return df


@st.cache_data(ttl=3600)
def _phase_contribution(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    df = query(f"""
        SELECT season, match_phase,
               ROUND(AVG(phase_runs), 2) AS avg_runs
        FROM (
            SELECT match_id, innings, season, match_phase,
                   SUM((runs_batter + runs_extras)) AS phase_runs
            FROM   balls
            WHERE  match_phase IS NOT NULL
              AND  {season_filter} {inn_filter}
            GROUP  BY match_id, innings, season, match_phase
        ) sub
        GROUP  BY season, match_phase
        ORDER  BY season,
                  CASE match_phase
                      WHEN 'powerplay' THEN 1
                      WHEN 'middle'    THEN 2
                      WHEN 'death'     THEN 3 END
    """)
    df["match_phase"] = df["match_phase"].str.capitalize()
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — OVER-BY-OVER
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _over_by_over(season_range=DEFAULT_SEASON_RANGE, innings_choice="Both"):
    season_filter = _season_condition("season", season_range)
    inn_filter = _innings_filter(innings_choice)
    return query(f"""
        SELECT over_num AS over,
               match_phase, avg_runs, wicket_pct, boundary_pct, dot_pct
        FROM (
            SELECT over                                              AS over_num,
                   MAX(match_phase)                                  AS match_phase,
                   ROUND(SUM((runs_batter + runs_extras)) * 1.0
                         / COUNT(DISTINCT match_id || '-'
                                 || CAST(innings AS VARCHAR)), 2)    AS avg_runs,
                   ROUND(SUM(CASE WHEN wicket_kind NOT IN ('not_out', 'retired hurt')
                              THEN 1 ELSE 0 END) * 100.0
                          / NULLIF(SUM(CASE WHEN valid_ball
                                       THEN 1 ELSE 0 END), 0), 2)   AS wicket_pct,
                   ROUND(SUM(CASE WHEN is_boundary THEN 1 ELSE 0 END) * 100.0
                         / NULLIF(SUM(CASE WHEN valid_ball
                                      THEN 1 ELSE 0 END), 0), 2)   AS boundary_pct,
                   ROUND(SUM(CASE WHEN is_dot THEN 1 ELSE 0 END) * 100.0
                         / NULLIF(SUM(CASE WHEN valid_ball
                                      THEN 1 ELSE 0 END), 0), 2)   AS dot_pct
            FROM   balls
            WHERE  over BETWEEN 1 AND 20
              AND  match_phase IS NOT NULL
              AND  {season_filter} {inn_filter}
            GROUP  BY over
        ) sub
        ORDER BY over_num
    """)


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE TAB RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

PHASE_LABELS = {
    "powerplay": "Powerplay (Overs 1–6)",
    "middle":    "Middle Overs (7–15)",
    "death":     "Death Overs (16–20)",
}


def _render_phase_tab(phase):
    """Render a complete phase analysis tab with charts and tables."""
    label = PHASE_LABELS[phase]
    phase_clr = PHASE_COLORS[phase]
    
    # Global phase controls
    spec_global = VisualSpec(
        id=f"{phase}_global",
        title=f"{label} Filters",
        controls=[
            season_range_control(),
            select_control("innings", "Innings", ["Both", "1st Innings", "2nd Innings"], "Both"),
        ],
    )
    st.markdown(f"#### {label} Filters")
    global_controls = render_visual_controls(spec_global)
    render_active_filters(active_control_chips(spec_global, global_controls))
    
    season_range = global_controls.get("season_range")
    innings_choice = global_controls.get("innings")

    st.divider()

    # Fetch data
    if phase == "powerplay":
        trend_df = _pp_avg_trend(season_range, innings_choice)
        dist_df = _pp_distribution(season_range, innings_choice)
        dot_df = _pp_dot_trend(season_range, innings_choice)
        boundary_df = _pp_boundary_trend(season_range, innings_choice)
    else:
        trend_df = _phase_avg_trend(phase, season_range, innings_choice)
        dist_df = _phase_distribution(phase, season_range, innings_choice)
        dot_df = _phase_dot_trend(phase, season_range, innings_choice)
        boundary_df = _phase_boundary_trend(phase, season_range, innings_choice)

    # ── Row 1: Avg score trend | Score distribution ──────────────
    col1, col2 = st.columns(2)
    with col1:
        if not trend_df.empty:
            fig = styled_line(
                trend_df, x="season", y="avg_runs", color="innings",
                title=f"Avg {label} Score Trend",
            )
            fig.update_layout(yaxis_title="Avg Runs", legend_title_text="")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No trend data available.")

    with col2:
        if not dist_df.empty:
            fig = px.histogram(
                dist_df, x="runs", nbins=30,
                title=f"{label} Score Distribution",
                color_discrete_sequence=[phase_clr],
            )
            fig.update_layout(xaxis_title="Runs", yaxis_title="Frequency")
            apply_ipl_style(fig)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No distribution data available.")

    # ── Row 2: Team-wise average ─────────────────────────────────
    spec_team = VisualSpec(
        id=f"{phase}_team_avg",
        title=f"Team-wise Avg {label} Score",
        controls=[number_control("min_innings", "Min innings", 5, 1, 50, help_text="Minimum innings to qualify")],
    )
    st.subheader(spec_team.title)
    team_controls = render_visual_controls(spec_team)
    render_active_filters(active_control_chips(spec_team, team_controls))
    
    if phase == "powerplay":
        team_df = _pp_team_avg(season_range, innings_choice, team_controls.get("min_innings"))
    else:
        team_df = _phase_team_avg(phase, season_range, innings_choice, team_controls.get("min_innings"))
    
    if not team_df.empty:
        colors = [get_team_color(t) for t in team_df["team"]]
        fig = px.bar(
            team_df, x="avg_runs", y="team", orientation="h",
            title=f"Team-wise Avg {label} Score",
            text_auto=True,
        )
        fig.update_traces(marker_color=colors)
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        apply_ipl_style(fig, height=500)
        st.plotly_chart(fig, width='stretch')
    else:
        st.info(spec_team.empty_state_help)

    # ── Row 3: Dot % trend | Boundary % trend ───────────────────
    col3, col4 = st.columns(2)
    with col3:
        if not dot_df.empty:
            fig = styled_line(
                dot_df, x="season", y="dot_pct",
                title=f"{label} Dot Ball % Trend",
            )
            fig.update_layout(yaxis_title="Dot %")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No dot-ball data available.")

    with col4:
        if not boundary_df.empty:
            fig = styled_line(
                boundary_df, x="season", y="boundary_pct",
                title=f"{label} Boundary % Trend",
            )
            fig.update_layout(yaxis_title="Boundary %")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No boundary data available.")

    # ── Extra widget slot for death overs sixes ─────────
    if phase == "death":
        sixes_df = _death_sixes_trend(season_range, innings_choice)
        if not sixes_df.empty:
            fig = styled_line(
                sixes_df, x="season", y="avg_sixes",
                title="Avg Sixes per Innings in Death Overs",
            )
            fig.update_layout(yaxis_title="Avg Sixes")
            st.plotly_chart(fig, width='stretch')

    # ── Row 4: Best scores table ─────────────────────────────────
    spec_best = VisualSpec(
        id=f"{phase}_best_scores",
        title=f"Top {label} Scores",
        controls=[limit_control(default=15, minimum=5, maximum=50)],
    )
    st.subheader(spec_best.title)
    best_controls = render_visual_controls(spec_best)
    render_active_filters(active_control_chips(spec_best, best_controls))
    
    if phase == "powerplay":
        best_df = _pp_best_scores(season_range, innings_choice, best_controls.get("limit"))
    else:
        best_df = _phase_best_scores(phase, season_range, innings_choice, best_controls.get("limit"))
    
    if not best_df.empty:
        disp = best_df.rename(columns={
            "team": "Team", "runs": "Runs", "wickets": "Wkts Lost",
            "vs": "Vs", "season": "Season",
        })
        st.dataframe(disp, width='stretch', hide_index=True)
    else:
        st.info(spec_best.empty_state_help)

    # ── Row 5: Top batters | Top bowlers ─────────────────────────
    col5, col6 = st.columns(2)
    with col5:
        spec_batters = VisualSpec(
            id=f"{phase}_top_batters",
            title=f"Top {label} Batters",
            controls=[
                limit_control(default=15, minimum=5, maximum=50),
                number_control("min_balls", "Min balls", 100, 50, 500, step=50, help_text="Minimum balls to qualify"),
            ],
        )
        st.subheader(spec_batters.title)
        batter_controls = render_visual_controls(spec_batters)
        render_active_filters(active_control_chips(spec_batters, batter_controls))
        
        batters_df = _phase_top_batters(
            phase, season_range, innings_choice,
            batter_controls.get("limit"), batter_controls.get("min_balls")
        )
        if not batters_df.empty:
            disp = batters_df.rename(columns={
                "batter": "Batter", "runs": "Runs", "balls": "Balls",
                "sr": "SR", "boundaries": "Boundaries", "avg": "Avg",
            })
            st.dataframe(disp, width='stretch', hide_index=True)
        else:
            st.info(spec_batters.empty_state_help)

    with col6:
        spec_bowlers = VisualSpec(
            id=f"{phase}_top_bowlers",
            title=f"Top {label} Bowlers",
            controls=[
                limit_control(default=15, minimum=5, maximum=50),
                number_control("min_balls", "Min balls", 100, 50, 500, step=50, help_text="Minimum balls to qualify"),
            ],
        )
        st.subheader(spec_bowlers.title)
        bowler_controls = render_visual_controls(spec_bowlers)
        render_active_filters(active_control_chips(spec_bowlers, bowler_controls))
        
        bowlers_df = _phase_top_bowlers(
            phase, season_range, innings_choice,
            bowler_controls.get("limit"), bowler_controls.get("min_balls")
        )
        if not bowlers_df.empty:
            disp = bowlers_df.rename(columns={
                "bowler": "Bowler", "balls": "Balls", "runs": "Runs",
                "wickets": "Wkts", "economy": "Econ", "dot_pct": "Dot %",
            })
            st.dataframe(disp, width='stretch', hide_index=True)
        else:
            st.info(spec_bowlers.empty_state_help)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN LAYOUT — 5 TABS
# ═══════════════════════════════════════════════════════════════════════════════

tab_pp, tab_mid, tab_death, tab_compare, tab_obo = st.tabs([
    "Powerplay", "Middle Overs", "Death Overs",
    "Phase Comparison", "Over-by-Over",
])

# ─── TAB 1: POWERPLAY ────────────────────────────────────────────────────────
with tab_pp:
    _render_phase_tab("powerplay")

# ─── TAB 2: MIDDLE OVERS ─────────────────────────────────────────────────────
with tab_mid:
    _render_phase_tab("middle")

# ─── TAB 3: DEATH OVERS ──────────────────────────────────────────────────────
with tab_death:
    _render_phase_tab("death")

# ─── TAB 4: PHASE COMPARISON ─────────────────────────────────────────────────
with tab_compare:
    spec_compare = VisualSpec(
        id="phase_comparison",
        title="Phase Comparison Filters",
        controls=[
            season_range_control(),
            select_control("innings", "Innings", ["Both", "1st Innings", "2nd Innings"], "Both"),
        ],
    )
    st.subheader(spec_compare.title)
    compare_controls = render_visual_controls(spec_compare)
    render_active_filters(active_control_chips(spec_compare, compare_controls))
    
    season_range = compare_controls.get("season_range")
    innings_choice = compare_controls.get("innings")
    
    phase_cmap = {p.capitalize(): c for p, c in PHASE_COLORS.items()}

    # Run-rate evolution
    rr_df = _phase_rr_evolution(season_range, innings_choice)
    if not rr_df.empty:
        fig = styled_line(
            rr_df, x="season", y="avg_rr", color="match_phase",
            title="Run Rate by Phase — Season Evolution",
        )
        fig.update_layout(yaxis_title="Avg Run Rate", legend_title_text="Phase")
        for trace in fig.data:
            if trace.name in phase_cmap:
                trace.line.color = phase_cmap[trace.name]
                trace.marker.color = phase_cmap[trace.name]
        st.plotly_chart(fig, width='stretch')

    # Donut charts
    col1, col2 = st.columns(2)
    with col1:
        bd_df = _phase_boundary_dist(season_range, innings_choice)
        if not bd_df.empty:
            fig = px.pie(
                bd_df, names="match_phase", values="boundaries",
                title="Boundary Distribution by Phase",
                hole=0.45, color="match_phase",
                color_discrete_map=phase_cmap,
            )
            fig.update_traces(textinfo="percent+label", textfont_size=12)
            apply_ipl_style(fig, show_legend=False)
            st.plotly_chart(fig, width='stretch')

    with col2:
        wk_df = _phase_wicket_dist(season_range, innings_choice)
        if not wk_df.empty:
            fig = px.pie(
                wk_df, names="match_phase", values="wickets",
                title="Wicket Distribution by Phase",
                hole=0.45, color="match_phase",
                color_discrete_map=phase_cmap,
            )
            fig.update_traces(textinfo="percent+label", textfont_size=12)
            apply_ipl_style(fig, show_legend=False)
            st.plotly_chart(fig, width='stretch')

    # Stacked bar — phase contribution
    contrib_df = _phase_contribution(season_range, innings_choice)
    if not contrib_df.empty:
        fig = px.bar(
            contrib_df, x="season", y="avg_runs", color="match_phase",
            title="Average Phase Runs per Innings",
            color_discrete_map=phase_cmap,
            category_orders={"match_phase": ["Powerplay", "Middle", "Death"]},
            barmode="stack", text_auto=True,
        )
        fig.update_layout(
            yaxis_title="Avg Runs", legend_title_text="Phase",
            xaxis=dict(dtick=1),
        )
        apply_ipl_style(fig, height=500)
        st.plotly_chart(fig, width='stretch')

# ─── TAB 5: OVER-BY-OVER ─────────────────────────────────────────────────────
with tab_obo:
    spec_obo = VisualSpec(
        id="over_by_over",
        title="Over-by-Over Filters",
        controls=[
            season_range_control(),
            select_control("innings", "Innings", ["Both", "1st Innings", "2nd Innings"], "Both"),
        ],
    )
    st.subheader(spec_obo.title)
    obo_controls = render_visual_controls(spec_obo)
    render_active_filters(active_control_chips(spec_obo, obo_controls))
    
    season_range = obo_controls.get("season_range")
    innings_choice = obo_controls.get("innings")

    obo_df = _over_by_over(season_range, innings_choice)
    if obo_df.empty:
        st.info("No over-by-over data available.")
    else:
        obo_df["phase_label"] = obo_df["match_phase"].str.capitalize()
        phase_cmap = {p.capitalize(): c for p, c in PHASE_COLORS.items()}

        # Avg runs per over
        fig = px.bar(
            obo_df, x="over", y="avg_runs", color="phase_label",
            title="Average Runs per Over",
            color_discrete_map=phase_cmap, text_auto=True,
        )
        fig.update_layout(
            xaxis=dict(dtick=1, title="Over"),
            yaxis_title="Avg Runs", legend_title_text="Phase",
        )
        apply_ipl_style(fig, height=450)
        st.plotly_chart(fig, width='stretch')

        # Three probability charts
        col1, col2, col3 = st.columns(3)

        with col1:
            fig = px.bar(
                obo_df, x="over", y="wicket_pct", color="phase_label",
                title="Wicket Probability %",
                color_discrete_map=phase_cmap,
            )
            fig.update_layout(
                xaxis=dict(dtick=1, title="Over"),
                yaxis_title="Wicket %", showlegend=False,
            )
            apply_ipl_style(fig, height=400)
            st.plotly_chart(fig, width='stretch')

        with col2:
            fig = px.bar(
                obo_df, x="over", y="boundary_pct", color="phase_label",
                title="Boundary Probability %",
                color_discrete_map=phase_cmap,
            )
            fig.update_layout(
                xaxis=dict(dtick=1, title="Over"),
                yaxis_title="Boundary %", showlegend=False,
            )
            apply_ipl_style(fig, height=400)
            st.plotly_chart(fig, width='stretch')

        with col3:
            fig = px.bar(
                obo_df, x="over", y="dot_pct", color="phase_label",
                title="Dot Ball Probability %",
                color_discrete_map=phase_cmap,
            )
            fig.update_layout(
                xaxis=dict(dtick=1, title="Over"),
                yaxis_title="Dot %", showlegend=False,
            )
            apply_ipl_style(fig, height=400)
            st.plotly_chart(fig, width='stretch')

# ═══════════════════════════════════════════════════════════════════════════════
st.divider()
st.caption("Phase Analysis • IPL Analytics Platform")
