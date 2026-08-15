"""
Trends & Evolution — How IPL cricket has changed from 2008 to 2026.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style, styled_line, styled_bar, big_number_style, IPL_COLORWAY,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS, PHASE_COLORS
from src.utils.formatters import format_number, format_strike_rate, format_economy
from src.utils.control_renderer import render_visual_controls, active_control_chips
from src.utils.control_schema import VisualSpec
from src.utils.visual_specs import season_range_control
from src.visualizations.card_renderer import render_active_filters

# ── Helper functions ───────────────────────────────────────────────

DEFAULT_SEASON_RANGE = (min(ALL_SEASONS), max(ALL_SEASONS))


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


# ── Cached data loaders ────────────────────────────────────────────


@st.cache_data(ttl=3600)
def _scoring_trends(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """Avg match aggregate and per-innings averages per season."""
    season_filter = _season_condition("season", season_range)
    return query(f"""
        SELECT season,
               ROUND(AVG(COALESCE(team1_score, 0)
                       + COALESCE(team2_score, 0)), 1) AS avg_aggregate,
               ROUND(AVG(team1_score), 1)              AS avg_first_innings,
               ROUND(AVG(team2_score), 1)              AS avg_second_innings
        FROM   matches
        WHERE  result_type != 'no result'
          AND  {season_filter}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _extreme_scores(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """200+ and sub-130 team innings counts per season."""
    season_filter = _season_condition("season", season_range)
    return query(f"""
        WITH innings AS (
            SELECT season, team1_score AS score
            FROM   matches WHERE result_type != 'no result' AND {season_filter}
            UNION ALL
            SELECT season, team2_score AS score
            FROM   matches WHERE result_type != 'no result' AND {season_filter}
        )
        SELECT season,
               SUM(CASE WHEN score >= 200 THEN 1 ELSE 0 END) AS scores_200_plus,
               SUM(CASE WHEN score <  130 THEN 1 ELSE 0 END) AS scores_sub_130
        FROM   innings
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _score_distribution(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """All team innings scores for box-plot distribution."""
    season_filter = _season_condition("season", season_range)
    return query(f"""
        SELECT season, team1_score AS score
        FROM   matches WHERE result_type != 'no result' AND {season_filter}
        UNION ALL
        SELECT season, team2_score AS score
        FROM   matches WHERE result_type != 'no result' AND {season_filter}
    """)


@st.cache_data(ttl=3600)
def _batting_evolution(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """Strike rate, boundary counts, dot %, boundary composition."""
    season_filter = _season_condition("b.season", season_range)
    return query(f"""
        WITH season_matches AS (
            SELECT season, COUNT(*) AS total_matches
            FROM   matches
            WHERE  result_type != 'no result'
              AND  {_season_condition("season", season_range)}
            GROUP  BY season
        )
        SELECT b.season,
               ROUND(SUM(b.runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN b.valid_ball THEN 1 ELSE 0 END), 0),
                     2) AS avg_strike_rate,
               ROUND(SUM(CASE WHEN b.is_six  THEN 1 ELSE 0 END) * 1.0
                     / sm.total_matches, 2) AS sixes_per_match,
               ROUND(SUM(CASE WHEN b.is_four THEN 1 ELSE 0 END) * 1.0
                     / sm.total_matches, 2) AS fours_per_match,
               ROUND(SUM(CASE WHEN b.is_dot AND b.valid_ball THEN 1 ELSE 0 END)
                     * 100.0
                     / NULLIF(SUM(CASE WHEN b.valid_ball THEN 1 ELSE 0 END), 0),
                     2) AS dot_ball_pct,
               ROUND(SUM(CASE WHEN b.is_four THEN 4 ELSE 0 END) * 100.0
                     / NULLIF(SUM(b.runs_batter), 0), 1) AS pct_runs_fours,
               ROUND(SUM(CASE WHEN b.is_six  THEN 6 ELSE 0 END) * 100.0
                     / NULLIF(SUM(b.runs_batter), 0), 1) AS pct_runs_sixes
        FROM   balls b
        JOIN   season_matches sm ON b.season = sm.season
        WHERE  NOT b.is_super_over
          AND  {season_filter}
        GROUP  BY b.season, sm.total_matches
        ORDER  BY b.season
    """)


@st.cache_data(ttl=3600)
def _bowling_evolution(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """Overall bowling economy and wickets per match per season."""
    season_filter = _season_condition("b.season", season_range)
    return query(f"""
        WITH season_matches AS (
            SELECT season, COUNT(*) AS total_matches
            FROM   matches
            WHERE  result_type != 'no result'
              AND  {_season_condition("season", season_range)}
            GROUP  BY season
        )
        SELECT b.season,
               ROUND(SUM(b.runs_bowler) * 6.0
                     / NULLIF(SUM(CASE WHEN b.valid_ball THEN 1 ELSE 0 END), 0),
                     2) AS avg_economy,
               ROUND(
                 SUM(CASE WHEN b.wicket_kind IS NOT NULL
                           AND b.wicket_kind NOT IN (
                               'not_out','retired hurt','retired out')
                          THEN 1 ELSE 0 END) * 1.0
                 / sm.total_matches, 2) AS wickets_per_match
        FROM   balls b
        JOIN   season_matches sm ON b.season = sm.season
        WHERE  NOT b.is_super_over
          AND  {season_filter}
        GROUP  BY b.season, sm.total_matches
        ORDER  BY b.season
    """)


@st.cache_data(ttl=3600)
def _dismissal_evolution(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """Dismissal type counts per season for stacked area."""
    season_filter = _season_condition("season", season_range)
    return query(f"""
        SELECT season,
               CASE
                   WHEN wicket_kind IN ('caught', 'caught and bowled') THEN 'Caught'
                   WHEN wicket_kind = 'bowled'  THEN 'Bowled'
                   WHEN wicket_kind = 'lbw'     THEN 'LBW'
                   WHEN wicket_kind = 'stumped' THEN 'Stumped'
                   WHEN wicket_kind = 'run out' THEN 'Run Out'
                   ELSE 'Other'
               END AS dismissal_type,
               COUNT(*) AS count
        FROM   balls
        WHERE  wicket_kind IS NOT NULL
          AND  wicket_kind NOT IN ('not_out', 'retired hurt', 'retired out')
          AND  NOT is_super_over
          AND  {season_filter}
        GROUP  BY season, dismissal_type
        ORDER  BY season, dismissal_type
    """)


@st.cache_data(ttl=3600)
def _death_economy(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """Economy rate in death overs (16-20) per season."""
    season_filter = _season_condition("season", season_range)
    return query(f"""
        SELECT season,
               ROUND(SUM(runs_bowler) * 6.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0),
                     2) AS death_economy
        FROM   balls
        WHERE  match_phase = 'death'
          AND  NOT is_super_over
          AND  {season_filter}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _maiden_overs(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """Maiden overs per season."""
    season_filter = _season_condition("season", season_range)
    return query(f"""
        SELECT season, COUNT(*) AS maiden_overs
        FROM (
            SELECT DISTINCT season, match_id, innings, over
            FROM   balls
            WHERE  is_maiden
              AND  valid_ball
              AND  NOT is_super_over
              AND  {season_filter}
        ) t
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _strategy_trends(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """Toss decision trend and bat-first / chase win rates per season."""
    season_filter = _season_condition("season", season_range)
    return query(f"""
        SELECT season,
               ROUND(SUM(CASE WHEN toss_decision = 'field' THEN 1 ELSE 0 END)
                     * 100.0 / COUNT(*), 1) AS pct_field_first,
               ROUND(
                 SUM(CASE WHEN batting_first_won
                           AND match_won_by IS NOT NULL
                           AND match_won_by != ''
                          THEN 1 ELSE 0 END) * 100.0
                 / NULLIF(SUM(CASE WHEN match_won_by IS NOT NULL
                                    AND match_won_by != ''
                              THEN 1 ELSE 0 END), 0),
                 1) AS bat_first_win_pct,
               ROUND(
                 SUM(CASE WHEN NOT batting_first_won
                           AND match_won_by IS NOT NULL
                           AND match_won_by != ''
                          THEN 1 ELSE 0 END) * 100.0
                 / NULLIF(SUM(CASE WHEN match_won_by IS NOT NULL
                                    AND match_won_by != ''
                              THEN 1 ELSE 0 END), 0),
                 1) AS chase_win_pct
        FROM   matches
        WHERE  {season_filter}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _phase_run_rates(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """Run rate per match phase per season."""
    season_filter = _season_condition("season", season_range)
    return query(f"""
        SELECT season,
               match_phase,
               ROUND(SUM((runs_batter + runs_extras)) * 6.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0),
                     2) AS run_rate
        FROM   balls
        WHERE  match_phase IS NOT NULL
          AND  NOT is_super_over
          AND  {season_filter}
        GROUP  BY season, match_phase
        ORDER  BY season, match_phase
    """)


@st.cache_data(ttl=3600)
def _match_dynamics(season_range: tuple[int, int] = DEFAULT_SEASON_RANGE):
    """Close matches, super overs, DLS matches, and season duration."""
    season_filter = _season_condition("m.season", season_range)
    return query(f"""
        SELECT m.season,
               ROUND(
                 SUM(CASE
                   WHEN (m.win_margin_type = 'runs'    AND m.win_margin_value <= 10)
                     OR (m.win_margin_type = 'wickets' AND m.win_margin_value <= 2)
                   THEN 1 ELSE 0
                 END) * 100.0
                 / NULLIF(SUM(CASE WHEN m.match_won_by IS NOT NULL
                                    AND m.match_won_by != ''
                              THEN 1 ELSE 0 END), 0),
                 1) AS close_match_pct,
               SUM(CASE WHEN m.is_super_over_match THEN 1 ELSE 0 END)
                   AS super_over_count,
               sm.dls_matches,
               sm.duration_days
        FROM   matches m
        JOIN   season_meta sm ON m.season = sm.season
        WHERE  {season_filter}
        GROUP  BY m.season, sm.dls_matches, sm.duration_days
        ORDER  BY m.season
    """)


# ── Page chrome ────────────────────────────────────────────────────

st.markdown(big_number_style(), unsafe_allow_html=True)
st.title("Trends & Evolution")
st.caption(
    "How IPL cricket has evolved from 2008 to 2026 — scoring, batting, "
    "bowling, strategy, and match dynamics"
)

# ── Tabs ───────────────────────────────────────────────────────────

tab_scoring, tab_batting, tab_bowling, tab_strategy, tab_dynamics = st.tabs([
    "Scoring Trends",
    "Batting Style Evolution",
    "Bowling Evolution",
    "Strategy Evolution",
    "Match Dynamics",
])

# ── Tab 1: Scoring Trends ─────────────────────────────────────────

with tab_scoring:
    # Average Match Aggregate
    spec_agg = VisualSpec(
        id="trends_avg_aggregate",
        title="Average Match Aggregate",
        controls=[season_range_control()],
    )
    st.markdown(f"#### {spec_agg.title}")
    controls_agg = render_visual_controls(spec_agg)
    render_active_filters(active_control_chips(spec_agg, controls_agg))
    
    scoring = _scoring_trends(controls_agg.get("season_range", DEFAULT_SEASON_RANGE))
    
    if scoring.empty:
        st.info("No scoring data available.")
    else:
        st.plotly_chart(
            styled_line(scoring, x="season", y="avg_aggregate",
                        title="Average Match Aggregate per Season"),
            width="stretch",
        )

        innings_melted = scoring.melt(
            id_vars="season",
            value_vars=["avg_first_innings", "avg_second_innings"],
            var_name="Innings", value_name="Avg Score",
        )
        innings_melted["Innings"] = innings_melted["Innings"].map({
            "avg_first_innings": "1st Innings",
            "avg_second_innings": "2nd Innings",
        })
        st.plotly_chart(
            styled_line(innings_melted, x="season", y="Avg Score",
                        title="Average 1st vs 2nd Innings Score",
                        color="Innings"),
            width="stretch",
        )

    # Extreme Scores
    spec_extreme = VisualSpec(
        id="trends_extreme_scores",
        title="Extreme Scores",
        controls=[season_range_control()],
    )
    st.markdown(f"#### {spec_extreme.title}")
    controls_extreme = render_visual_controls(spec_extreme)
    render_active_filters(active_control_chips(spec_extreme, controls_extreme))
    
    extreme = _extreme_scores(controls_extreme.get("season_range", DEFAULT_SEASON_RANGE))

    if not extreme.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_bar(extreme, x="season", y="scores_200_plus",
                           title="200+ Scores per Season"),
                width="stretch",
            )
        with c2:
            st.plotly_chart(
                styled_bar(extreme, x="season", y="scores_sub_130",
                           title="Sub-130 Scores per Season"),
                width="stretch",
            )

    # Score Distribution
    spec_dist = VisualSpec(
        id="trends_score_distribution",
        title="Score Distribution",
        controls=[season_range_control()],
    )
    st.markdown(f"#### {spec_dist.title}")
    controls_dist = render_visual_controls(spec_dist)
    render_active_filters(active_control_chips(spec_dist, controls_dist))
    
    dist = _score_distribution(controls_dist.get("season_range", DEFAULT_SEASON_RANGE))

    if not dist.empty:
        dist_plot = dist.copy()
        dist_plot["season"] = dist_plot["season"].astype(str)
        fig_box = px.box(dist_plot, x="season", y="score",
                         title="Score Distribution Shift across Seasons")
        apply_ipl_style(fig_box, height=500)
        st.plotly_chart(fig_box, width="stretch")

# ── Tab 2: Batting Style Evolution ─────────────────────────────────

with tab_batting:
    spec_batting = VisualSpec(
        id="trends_batting_evolution",
        title="Batting Style Evolution",
        controls=[season_range_control()],
    )
    st.markdown(f"#### {spec_batting.title}")
    controls_batting = render_visual_controls(spec_batting)
    render_active_filters(active_control_chips(spec_batting, controls_batting))
    
    batting = _batting_evolution(controls_batting.get("season_range", DEFAULT_SEASON_RANGE))

    if batting.empty:
        st.info("No batting data available.")
    else:
        st.plotly_chart(
            styled_line(batting, x="season", y="avg_strike_rate",
                        title="Average Strike Rate per Season"),
            width="stretch",
        )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_line(batting, x="season", y="sixes_per_match",
                            title="Sixes per Match"),
                width="stretch",
            )
        with c2:
            st.plotly_chart(
                styled_line(batting, x="season", y="fours_per_match",
                            title="Fours per Match"),
                width="stretch",
            )

        st.plotly_chart(
            styled_line(batting, x="season", y="dot_ball_pct",
                        title="Dot Ball % per Season"),
            width="stretch",
        )

        batting = batting.copy()
        batting["pct_runs_running"] = (
            100.0 - batting["pct_runs_fours"] - batting["pct_runs_sixes"]
        )
        comp = batting.melt(
            id_vars="season",
            value_vars=["pct_runs_running", "pct_runs_fours", "pct_runs_sixes"],
            var_name="Source", value_name="Percentage",
        )
        comp["Source"] = comp["Source"].map({
            "pct_runs_running": "Running",
            "pct_runs_fours": "Fours",
            "pct_runs_sixes": "Sixes",
        })
        fig_comp = px.area(
            comp, x="season", y="Percentage", color="Source",
            title="Boundary Composition — % Runs by Source",
            color_discrete_map={
                "Running": IPL_COLORWAY[2],
                "Fours": IPL_COLORWAY[0],
                "Sixes": IPL_COLORWAY[1],
            },
            category_orders={"Source": ["Running", "Fours", "Sixes"]},
        )
        apply_ipl_style(fig_comp, height=500)
        st.plotly_chart(fig_comp, width="stretch")

# ── Tab 3: Bowling Evolution ──────────────────────────────────────

with tab_bowling:
    spec_bowling = VisualSpec(
        id="trends_bowling_evolution",
        title="Bowling Evolution",
        controls=[season_range_control()],
    )
    st.markdown(f"#### {spec_bowling.title}")
    controls_bowling = render_visual_controls(spec_bowling)
    render_active_filters(active_control_chips(spec_bowling, controls_bowling))
    
    bowling = _bowling_evolution(controls_bowling.get("season_range", DEFAULT_SEASON_RANGE))
    dismissals = _dismissal_evolution(controls_bowling.get("season_range", DEFAULT_SEASON_RANGE))
    death_econ = _death_economy(controls_bowling.get("season_range", DEFAULT_SEASON_RANGE))
    maidens = _maiden_overs(controls_bowling.get("season_range", DEFAULT_SEASON_RANGE))

    if bowling.empty:
        st.info("No bowling data available.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_line(bowling, x="season", y="avg_economy",
                            title="Average Economy Rate per Season"),
                width="stretch",
            )
        with c2:
            st.plotly_chart(
                styled_line(bowling, x="season", y="wickets_per_match",
                            title="Wickets per Match"),
                width="stretch",
            )

        if not dismissals.empty:
            totals = dismissals.groupby("season")["count"].transform("sum")
            dismissals = dismissals.copy()
            dismissals["pct"] = round(dismissals["count"] * 100.0 / totals, 1)
            type_order = ["Caught", "Bowled", "Run Out", "LBW", "Stumped", "Other"]
            fig_dismiss = px.area(
                dismissals, x="season", y="pct", color="dismissal_type",
                title="Dismissal Type Evolution (% Share)",
                color_discrete_sequence=IPL_COLORWAY,
                category_orders={"dismissal_type": type_order},
            )
            apply_ipl_style(fig_dismiss, height=500)
            st.plotly_chart(fig_dismiss, width="stretch")

        c1, c2 = st.columns(2)
        with c1:
            if not death_econ.empty:
                st.plotly_chart(
                    styled_line(death_econ, x="season", y="death_economy",
                                title="Death Over Economy (Overs 16–20)"),
                    width="stretch",
                )
        with c2:
            if not maidens.empty:
                st.plotly_chart(
                    styled_bar(maidens, x="season", y="maiden_overs",
                               title="Maiden Overs per Season"),
                    width="stretch",
                )

# ── Tab 4: Strategy Evolution ─────────────────────────────────────

with tab_strategy:
    spec_strategy = VisualSpec(
        id="trends_strategy_evolution",
        title="Strategy Evolution",
        controls=[season_range_control()],
    )
    st.markdown(f"#### {spec_strategy.title}")
    controls_strategy = render_visual_controls(spec_strategy)
    render_active_filters(active_control_chips(spec_strategy, controls_strategy))
    
    strategy = _strategy_trends(controls_strategy.get("season_range", DEFAULT_SEASON_RANGE))
    phases = _phase_run_rates(controls_strategy.get("season_range", DEFAULT_SEASON_RANGE))

    if strategy.empty:
        st.info("No strategy data available.")
    else:
        st.plotly_chart(
            styled_line(strategy, x="season", y="pct_field_first",
                        title="% Teams Choosing to Field First after Toss"),
            width="stretch",
        )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_line(strategy, x="season", y="bat_first_win_pct",
                            title="Bat-First Win % per Season"),
                width="stretch",
            )
        with c2:
            st.plotly_chart(
                styled_line(strategy, x="season", y="chase_win_pct",
                            title="Chasing Success Rate per Season"),
                width="stretch",
            )

        if not phases.empty:
            pp = phases[phases["match_phase"] == "powerplay"][
                ["season", "run_rate"]
            ].rename(columns={"run_rate": "pp_rr"})
            death = phases[phases["match_phase"] == "death"][
                ["season", "run_rate"]
            ].rename(columns={"run_rate": "death_rr"})

            st.plotly_chart(
                styled_line(pp, x="season", y="pp_rr",
                            title="Powerplay Run Rate per Season"),
                width="stretch",
            )

            accel = pp.merge(death, on="season", how="inner")
            accel["acceleration"] = round(accel["death_rr"] / accel["pp_rr"], 3)
            st.plotly_chart(
                styled_line(accel, x="season", y="acceleration",
                            title="Death Over Acceleration (Death RR ÷ PP RR)"),
                width="stretch",
            )

# ── Tab 5: Match Dynamics ─────────────────────────────────────────

with tab_dynamics:
    spec_dynamics = VisualSpec(
        id="trends_match_dynamics",
        title="Match Dynamics",
        controls=[season_range_control()],
    )
    st.markdown(f"#### {spec_dynamics.title}")
    controls_dynamics = render_visual_controls(spec_dynamics)
    render_active_filters(active_control_chips(spec_dynamics, controls_dynamics))
    
    dynamics = _match_dynamics(controls_dynamics.get("season_range", DEFAULT_SEASON_RANGE))

    if dynamics.empty:
        st.info("No match dynamics data available.")
    else:
        st.plotly_chart(
            styled_line(dynamics, x="season", y="close_match_pct",
                        title="Close Matches % per Season "
                              "(Won by ≤10 Runs or ≤2 Wickets)"),
            width="stretch",
        )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_bar(dynamics, x="season", y="super_over_count",
                           title="Super Overs per Season"),
                width="stretch",
            )
        with c2:
            st.plotly_chart(
                styled_bar(dynamics, x="season", y="dls_matches",
                           title="DLS-Affected Matches per Season"),
                width="stretch",
            )

        st.plotly_chart(
            styled_line(dynamics, x="season", y="duration_days",
                        title="Season Duration (Days)"),
            width="stretch",
        )
