"""
Trends & Evolution — How IPL cricket has changed from 2008 to 2025.
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

# ── Cached data loaders ────────────────────────────────────────────


@st.cache_data(ttl=3600)
def _scoring_trends():
    """Avg match aggregate and per-innings averages per season."""
    return query("""
        SELECT season,
               ROUND(AVG(COALESCE(team1_score, 0)
                       + COALESCE(team2_score, 0)), 1) AS avg_aggregate,
               ROUND(AVG(team1_score), 1)              AS avg_first_innings,
               ROUND(AVG(team2_score), 1)              AS avg_second_innings
        FROM   matches
        WHERE  result_type != 'no result'
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _extreme_scores():
    """200+ and sub-130 team innings counts per season."""
    return query("""
        WITH innings AS (
            SELECT season, team1_score AS score
            FROM   matches WHERE result_type != 'no result'
            UNION ALL
            SELECT season, team2_score AS score
            FROM   matches WHERE result_type != 'no result'
        )
        SELECT season,
               SUM(CASE WHEN score >= 200 THEN 1 ELSE 0 END) AS scores_200_plus,
               SUM(CASE WHEN score <  130 THEN 1 ELSE 0 END) AS scores_sub_130
        FROM   innings
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _score_distribution():
    """All team innings scores for box-plot distribution."""
    return query("""
        SELECT season, team1_score AS score
        FROM   matches WHERE result_type != 'no result'
        UNION ALL
        SELECT season, team2_score AS score
        FROM   matches WHERE result_type != 'no result'
    """)


@st.cache_data(ttl=3600)
def _batting_evolution():
    """Strike rate, boundary counts, dot %, boundary composition."""
    return query("""
        WITH season_matches AS (
            SELECT season, COUNT(*) AS total_matches
            FROM   matches
            WHERE  result_type != 'no result'
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
        GROUP  BY b.season, sm.total_matches
        ORDER  BY b.season
    """)


@st.cache_data(ttl=3600)
def _bowling_evolution():
    """Overall bowling economy and wickets per match per season."""
    return query("""
        WITH season_matches AS (
            SELECT season, COUNT(*) AS total_matches
            FROM   matches
            WHERE  result_type != 'no result'
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
        GROUP  BY b.season, sm.total_matches
        ORDER  BY b.season
    """)


@st.cache_data(ttl=3600)
def _dismissal_evolution():
    """Dismissal type counts per season for stacked area."""
    return query("""
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
        GROUP  BY season, dismissal_type
        ORDER  BY season, dismissal_type
    """)


@st.cache_data(ttl=3600)
def _death_economy():
    """Economy rate in death overs (16-20) per season."""
    return query("""
        SELECT season,
               ROUND(SUM(runs_bowler) * 6.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0),
                     2) AS death_economy
        FROM   balls
        WHERE  match_phase = 'death'
          AND  NOT is_super_over
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _maiden_overs():
    """Maiden overs per season."""
    return query("""
        SELECT season, COUNT(*) AS maiden_overs
        FROM (
            SELECT DISTINCT season, match_id, innings, over
            FROM   balls
            WHERE  is_maiden
              AND  valid_ball
              AND  NOT is_super_over
        ) t
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _strategy_trends():
    """Toss decision trend and bat-first / chase win rates per season."""
    return query("""
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
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _phase_run_rates():
    """Run rate per match phase per season."""
    return query("""
        SELECT season,
               match_phase,
               ROUND(SUM((runs_batter + runs_extras)) * 6.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0),
                     2) AS run_rate
        FROM   balls
        WHERE  match_phase IS NOT NULL
          AND  NOT is_super_over
        GROUP  BY season, match_phase
        ORDER  BY season, match_phase
    """)


@st.cache_data(ttl=3600)
def _match_dynamics():
    """Close matches, super overs, DLS matches, and season duration."""
    return query("""
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
        GROUP  BY m.season, sm.dls_matches, sm.duration_days
        ORDER  BY m.season
    """)


# ── Page chrome ────────────────────────────────────────────────────

st.markdown(big_number_style(), unsafe_allow_html=True)
st.title("Trends & Evolution")
st.caption(
    "How IPL cricket has evolved from 2008 to 2025 — scoring, batting, "
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
    scoring = _scoring_trends()
    extreme = _extreme_scores()
    dist = _score_distribution()

    if scoring.empty:
        st.info("No scoring data available.")
    else:
        st.plotly_chart(
            styled_line(scoring, x="season", y="avg_aggregate",
                        title="Average Match Aggregate per Season"),
            width='stretch',
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
            width='stretch',
        )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_bar(extreme, x="season", y="scores_200_plus",
                           title="200+ Scores per Season"),
                width='stretch',
            )
        with c2:
            st.plotly_chart(
                styled_bar(extreme, x="season", y="scores_sub_130",
                           title="Sub-130 Scores per Season"),
                width='stretch',
            )

        dist_plot = dist.copy()
        dist_plot["season"] = dist_plot["season"].astype(str)
        fig_box = px.box(dist_plot, x="season", y="score",
                         title="Score Distribution Shift across Seasons")
        apply_ipl_style(fig_box, height=500)
        st.plotly_chart(fig_box, width='stretch')

# ── Tab 2: Batting Style Evolution ─────────────────────────────────

with tab_batting:
    batting = _batting_evolution()

    if batting.empty:
        st.info("No batting data available.")
    else:
        st.plotly_chart(
            styled_line(batting, x="season", y="avg_strike_rate",
                        title="Average Strike Rate per Season"),
            width='stretch',
        )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_line(batting, x="season", y="sixes_per_match",
                            title="Sixes per Match"),
                width='stretch',
            )
        with c2:
            st.plotly_chart(
                styled_line(batting, x="season", y="fours_per_match",
                            title="Fours per Match"),
                width='stretch',
            )

        st.plotly_chart(
            styled_line(batting, x="season", y="dot_ball_pct",
                        title="Dot Ball % per Season"),
            width='stretch',
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
        st.plotly_chart(fig_comp, width='stretch')

# ── Tab 3: Bowling Evolution ──────────────────────────────────────

with tab_bowling:
    bowling = _bowling_evolution()
    dismissals = _dismissal_evolution()
    death_econ = _death_economy()
    maidens = _maiden_overs()

    if bowling.empty:
        st.info("No bowling data available.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_line(bowling, x="season", y="avg_economy",
                            title="Average Economy Rate per Season"),
                width='stretch',
            )
        with c2:
            st.plotly_chart(
                styled_line(bowling, x="season", y="wickets_per_match",
                            title="Wickets per Match"),
                width='stretch',
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
            st.plotly_chart(fig_dismiss, width='stretch')

        c1, c2 = st.columns(2)
        with c1:
            if not death_econ.empty:
                st.plotly_chart(
                    styled_line(death_econ, x="season", y="death_economy",
                                title="Death Over Economy (Overs 16–20)"),
                    width='stretch',
                )
        with c2:
            if not maidens.empty:
                st.plotly_chart(
                    styled_bar(maidens, x="season", y="maiden_overs",
                               title="Maiden Overs per Season"),
                    width='stretch',
                )

# ── Tab 4: Strategy Evolution ─────────────────────────────────────

with tab_strategy:
    strategy = _strategy_trends()
    phases = _phase_run_rates()

    if strategy.empty:
        st.info("No strategy data available.")
    else:
        st.plotly_chart(
            styled_line(strategy, x="season", y="pct_field_first",
                        title="% Teams Choosing to Field First after Toss"),
            width='stretch',
        )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_line(strategy, x="season", y="bat_first_win_pct",
                            title="Bat-First Win % per Season"),
                width='stretch',
            )
        with c2:
            st.plotly_chart(
                styled_line(strategy, x="season", y="chase_win_pct",
                            title="Chasing Success Rate per Season"),
                width='stretch',
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
                width='stretch',
            )

            accel = pp.merge(death, on="season", how="inner")
            accel["acceleration"] = round(accel["death_rr"] / accel["pp_rr"], 3)
            st.plotly_chart(
                styled_line(accel, x="season", y="acceleration",
                            title="Death Over Acceleration (Death RR ÷ PP RR)"),
                width='stretch',
            )

# ── Tab 5: Match Dynamics ─────────────────────────────────────────

with tab_dynamics:
    dynamics = _match_dynamics()

    if dynamics.empty:
        st.info("No match dynamics data available.")
    else:
        st.plotly_chart(
            styled_line(dynamics, x="season", y="close_match_pct",
                        title="Close Matches % per Season "
                              "(Won by ≤10 Runs or ≤2 Wickets)"),
            width='stretch',
        )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                styled_bar(dynamics, x="season", y="super_over_count",
                           title="Super Overs per Season"),
                width='stretch',
            )
        with c2:
            st.plotly_chart(
                styled_bar(dynamics, x="season", y="dls_matches",
                           title="DLS-Affected Matches per Season"),
                width='stretch',
            )

        st.plotly_chart(
            styled_line(dynamics, x="season", y="duration_days",
                        title="Season Duration (Days)"),
            width='stretch',
        )
