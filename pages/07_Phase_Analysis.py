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

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(big_number_style(), unsafe_allow_html=True)
st.title("Phase Analysis")
st.caption("Deep-dive into Powerplay (overs 1–6), Middle (7–15), and Death (16–20) overs")

# ═══════════════════════════════════════════════════════════════════════════════
#  FILTERS
# ═══════════════════════════════════════════════════════════════════════════════

fc1, fc2 = st.columns([2, 1])
with fc1:
    s1, s2 = st.slider(
        "Season range",
        min_value=min(ALL_SEASONS),
        max_value=max(ALL_SEASONS),
        value=(min(ALL_SEASONS), max(ALL_SEASONS)),
        key="phase_season_range",
    )
with fc2:
    innings_choice = st.radio(
        "Innings",
        ["Both", "1st Innings", "2nd Innings"],
        key="phase_innings",
        horizontal=True,
    )

inn_filter = ""
if innings_choice == "1st Innings":
    inn_filter = "AND innings = 1"
elif innings_choice == "2nd Innings":
    inn_filter = "AND innings = 2"


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — POWERPLAY (precomputed view)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _pp_avg_trend(_s1, _s2, _inn):
    df = query(f"""
        SELECT season, innings, ROUND(AVG(pp_runs), 2) AS avg_runs
        FROM   powerplay
        WHERE  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY season, innings
        ORDER  BY season, innings
    """)
    df["innings"] = df["innings"].map({1: "1st Innings", 2: "2nd Innings"})
    return df


@st.cache_data(ttl=3600)
def _pp_distribution(_s1, _s2, _inn):
    return query(f"""
        SELECT pp_runs AS runs
        FROM   powerplay
        WHERE  season BETWEEN {_s1} AND {_s2} {_inn}
    """)


@st.cache_data(ttl=3600)
def _pp_team_avg(_s1, _s2, _inn):
    return query(f"""
        SELECT batting_team AS team,
               ROUND(AVG(pp_runs), 2) AS avg_runs,
               COUNT(*) AS innings_count
        FROM   powerplay
        WHERE  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY batting_team
        HAVING COUNT(*) >= 5
        ORDER  BY avg_runs DESC
    """)


@st.cache_data(ttl=3600)
def _pp_dot_trend(_s1, _s2, _inn):
    return query(f"""
        SELECT season,
               ROUND(SUM(pp_dots) * 100.0
                     / NULLIF(SUM(pp_balls), 0), 2) AS dot_pct
        FROM   powerplay
        WHERE  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _pp_boundary_trend(_s1, _s2, _inn):
    return query(f"""
        SELECT season,
               ROUND(SUM(pp_boundaries) * 100.0
                     / NULLIF(SUM(pp_balls), 0), 2) AS boundary_pct
        FROM   powerplay
        WHERE  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _pp_best_scores(_s1, _s2, _inn):
    return query(f"""
        SELECT p.batting_team AS team,
               p.pp_runs      AS runs,
               p.pp_wickets   AS wickets,
               CASE WHEN m.team1 = p.batting_team
                    THEN m.team2 ELSE m.team1 END AS vs,
               p.season
        FROM   powerplay p
        JOIN   matches   m ON p.match_id = m.match_id
        WHERE  p.season BETWEEN {_s1} AND {_s2} {_inn}
        ORDER  BY p.pp_runs DESC
        LIMIT  15
    """)


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — GENERIC PHASE (middle / death, from balls)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _phase_avg_trend(phase, _s1, _s2, _inn):
    df = query(f"""
        SELECT season, innings, ROUND(AVG(phase_runs), 2) AS avg_runs
        FROM (
            SELECT match_id, innings, season,
                   SUM((runs_batter + runs_extras)) AS phase_runs
            FROM   balls
            WHERE  match_phase = '{phase}'
              AND  season BETWEEN {_s1} AND {_s2} {_inn}
            GROUP  BY match_id, innings, season
        ) sub
        GROUP BY season, innings
        ORDER BY season, innings
    """)
    df["innings"] = df["innings"].map({1: "1st Innings", 2: "2nd Innings"})
    return df


@st.cache_data(ttl=3600)
def _phase_distribution(phase, _s1, _s2, _inn):
    return query(f"""
        SELECT SUM((runs_batter + runs_extras)) AS runs
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY match_id, innings
    """)


@st.cache_data(ttl=3600)
def _phase_team_avg(phase, _s1, _s2, _inn):
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
              AND  season BETWEEN {_s1} AND {_s2} {_inn}
            GROUP  BY match_id, innings
        ) sub
        GROUP  BY team
        HAVING COUNT(*) >= 5
        ORDER  BY avg_runs DESC
    """)


@st.cache_data(ttl=3600)
def _phase_dot_trend(phase, _s1, _s2, _inn):
    return query(f"""
        SELECT season,
               ROUND(SUM(CASE WHEN is_dot THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 2)
                     AS dot_pct
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _phase_boundary_trend(phase, _s1, _s2, _inn):
    return query(f"""
        SELECT season,
               ROUND(SUM(CASE WHEN is_boundary THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 2)
                     AS boundary_pct
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _phase_best_scores(phase, _s1, _s2, _inn):
    return query(f"""
        SELECT team, phase_runs AS runs,
               phase_wickets AS wickets, vs, season
        FROM (
            SELECT match_id, innings, season,
                   MAX(batting_team) AS team,
                   MAX(bowling_team) AS vs,
                   SUM((runs_batter + runs_extras))   AS phase_runs,
                   SUM(CASE WHEN wicket_kind IS NOT NULL THEN 1 ELSE 0 END)
                       AS phase_wickets
            FROM   balls
            WHERE  match_phase = '{phase}'
              AND  season BETWEEN {_s1} AND {_s2} {_inn}
            GROUP  BY match_id, innings, season
        ) sub
        ORDER BY phase_runs DESC
        LIMIT 15
    """)


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — BATTER / BOWLER (any phase, from balls)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _phase_top_batters(phase, _s1, _s2, _inn):
    return query(f"""
        SELECT batter,
               SUM(runs_batter)::INT AS runs,
               SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS balls,
               ROUND(SUM(runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 2) AS sr,
               (SUM(CASE WHEN is_four THEN 1 ELSE 0 END)
                + SUM(CASE WHEN is_six THEN 1 ELSE 0 END))::INT AS boundaries,
               ROUND(SUM(runs_batter) * 1.0
                     / NULLIF(SUM(CASE WHEN wicket_kind IS NOT NULL
                                       AND player_out = batter
                                  THEN 1 ELSE 0 END), 0), 2) AS avg
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY batter
        HAVING SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) >= 100
        ORDER  BY runs DESC
        LIMIT  15
    """)


@st.cache_data(ttl=3600)
def _phase_top_bowlers(phase, _s1, _s2, _inn):
    return query(f"""
        SELECT bowler,
               SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS balls,
               SUM(runs_bowler)::INT AS runs,
               SUM(CASE WHEN wicket_kind IS NOT NULL
                         AND wicket_kind NOT IN ('run out', 'retired hurt',
                                                 'retired out', 'obstructing the field')
                    THEN 1 ELSE 0 END)::INT AS wickets,
               ROUND(SUM(runs_bowler) * 6.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 2) AS economy,
               ROUND(SUM(CASE WHEN is_dot THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0), 1) AS dot_pct
        FROM   balls
        WHERE  match_phase = '{phase}'
          AND  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY bowler
        HAVING SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) >= 100
        ORDER  BY wickets DESC
        LIMIT  15
    """)


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — DEATH EXTRAS
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _death_sixes_trend(_s1, _s2, _inn):
    return query(f"""
        SELECT season,
               ROUND(
                   SUM(CASE WHEN is_six THEN 1 ELSE 0 END) * 1.0
                   / COUNT(DISTINCT match_id || '-' || CAST(innings AS VARCHAR)),
               2) AS avg_sixes
        FROM   balls
        WHERE  match_phase = 'death'
          AND  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY season
        ORDER  BY season
    """)


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS — PHASE COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _phase_rr_evolution(_s1, _s2, _inn):
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
              AND  season BETWEEN {_s1} AND {_s2} {_inn}
            GROUP  BY match_id, innings, season, match_phase
        ) sub
        GROUP BY season, match_phase
        ORDER BY season
    """)
    df["match_phase"] = df["match_phase"].str.capitalize()
    return df


@st.cache_data(ttl=3600)
def _phase_boundary_dist(_s1, _s2, _inn):
    df = query(f"""
        SELECT match_phase,
               SUM(CASE WHEN is_boundary THEN 1 ELSE 0 END)::INT AS boundaries
        FROM   balls
        WHERE  match_phase IS NOT NULL
          AND  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY match_phase
    """)
    df["match_phase"] = df["match_phase"].str.capitalize()
    return df


@st.cache_data(ttl=3600)
def _phase_wicket_dist(_s1, _s2, _inn):
    df = query(f"""
        SELECT match_phase,
               SUM(CASE WHEN wicket_kind IS NOT NULL THEN 1 ELSE 0 END)::INT AS wickets
        FROM   balls
        WHERE  match_phase IS NOT NULL
          AND  season BETWEEN {_s1} AND {_s2} {_inn}
        GROUP  BY match_phase
    """)
    df["match_phase"] = df["match_phase"].str.capitalize()
    return df


@st.cache_data(ttl=3600)
def _phase_contribution(_s1, _s2, _inn):
    df = query(f"""
        SELECT season, match_phase,
               ROUND(AVG(phase_runs), 2) AS avg_runs
        FROM (
            SELECT match_id, innings, season, match_phase,
                   SUM((runs_batter + runs_extras)) AS phase_runs
            FROM   balls
            WHERE  match_phase IS NOT NULL
              AND  season BETWEEN {_s1} AND {_s2} {_inn}
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
def _over_by_over(_s1, _s2, _inn):
    return query(f"""
        SELECT over_num AS over,
               match_phase, avg_runs, wicket_pct, boundary_pct, dot_pct
        FROM (
            SELECT over                                              AS over_num,
                   MAX(match_phase)                                  AS match_phase,
                   ROUND(SUM((runs_batter + runs_extras)) * 1.0
                         / COUNT(DISTINCT match_id || '-'
                                 || CAST(innings AS VARCHAR)), 2)    AS avg_runs,
                   ROUND(SUM(CASE WHEN wicket_kind IS NOT NULL
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
              AND  season BETWEEN {_s1} AND {_s2} {_inn}
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


def _render_phase_tab(phase, trend_df, dist_df, team_df, dot_df, boundary_df,
                      best_df, batters_df, bowlers_df, extra_widget=None):
    """Render a complete phase analysis tab with charts and tables."""
    label = PHASE_LABELS[phase]
    phase_clr = PHASE_COLORS[phase]

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

    # ── Extra widget slot (e.g. death-overs sixes trend) ─────────
    if extra_widget is not None:
        extra_widget()

    # ── Row 4: Best scores table ─────────────────────────────────
    st.subheader(f"Top 15 {label} Scores")
    if not best_df.empty:
        disp = best_df.rename(columns={
            "team": "Team", "runs": "Runs", "wickets": "Wkts Lost",
            "vs": "Vs", "season": "Season",
        })
        st.dataframe(disp, width='stretch', hide_index=True)
    else:
        st.info("No data available.")

    # ── Row 5: Top batters | Top bowlers ─────────────────────────
    col5, col6 = st.columns(2)
    with col5:
        st.subheader(f"Top {label} Batters")
        if not batters_df.empty:
            disp = batters_df.rename(columns={
                "batter": "Batter", "runs": "Runs", "balls": "Balls",
                "sr": "SR", "boundaries": "Boundaries", "avg": "Avg",
            })
            st.dataframe(disp, width='stretch', hide_index=True)
        else:
            st.info("No batter data (min 100 balls).")

    with col6:
        st.subheader(f"Top {label} Bowlers")
        if not bowlers_df.empty:
            disp = bowlers_df.rename(columns={
                "bowler": "Bowler", "balls": "Balls", "runs": "Runs",
                "wickets": "Wkts", "economy": "Econ", "dot_pct": "Dot %",
            })
            st.dataframe(disp, width='stretch', hide_index=True)
        else:
            st.info("No bowler data (min 100 balls).")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN LAYOUT — 5 TABS
# ═══════════════════════════════════════════════════════════════════════════════

tab_pp, tab_mid, tab_death, tab_compare, tab_obo = st.tabs([
    "Powerplay", "Middle Overs", "Death Overs",
    "Phase Comparison", "Over-by-Over",
])

# ─── TAB 1: POWERPLAY ────────────────────────────────────────────────────────
with tab_pp:
    _render_phase_tab(
        phase="powerplay",
        trend_df=_pp_avg_trend(s1, s2, inn_filter),
        dist_df=_pp_distribution(s1, s2, inn_filter),
        team_df=_pp_team_avg(s1, s2, inn_filter),
        dot_df=_pp_dot_trend(s1, s2, inn_filter),
        boundary_df=_pp_boundary_trend(s1, s2, inn_filter),
        best_df=_pp_best_scores(s1, s2, inn_filter),
        batters_df=_phase_top_batters("powerplay", s1, s2, inn_filter),
        bowlers_df=_phase_top_bowlers("powerplay", s1, s2, inn_filter),
    )

# ─── TAB 2: MIDDLE OVERS ─────────────────────────────────────────────────────
with tab_mid:
    _render_phase_tab(
        phase="middle",
        trend_df=_phase_avg_trend("middle", s1, s2, inn_filter),
        dist_df=_phase_distribution("middle", s1, s2, inn_filter),
        team_df=_phase_team_avg("middle", s1, s2, inn_filter),
        dot_df=_phase_dot_trend("middle", s1, s2, inn_filter),
        boundary_df=_phase_boundary_trend("middle", s1, s2, inn_filter),
        best_df=_phase_best_scores("middle", s1, s2, inn_filter),
        batters_df=_phase_top_batters("middle", s1, s2, inn_filter),
        bowlers_df=_phase_top_bowlers("middle", s1, s2, inn_filter),
    )

# ─── TAB 3: DEATH OVERS ──────────────────────────────────────────────────────
with tab_death:
    def _death_sixes_widget():
        sixes_df = _death_sixes_trend(s1, s2, inn_filter)
        if not sixes_df.empty:
            fig = styled_line(
                sixes_df, x="season", y="avg_sixes",
                title="Avg Sixes per Innings in Death Overs",
            )
            fig.update_layout(yaxis_title="Avg Sixes")
            st.plotly_chart(fig, width='stretch')

    _render_phase_tab(
        phase="death",
        trend_df=_phase_avg_trend("death", s1, s2, inn_filter),
        dist_df=_phase_distribution("death", s1, s2, inn_filter),
        team_df=_phase_team_avg("death", s1, s2, inn_filter),
        dot_df=_phase_dot_trend("death", s1, s2, inn_filter),
        boundary_df=_phase_boundary_trend("death", s1, s2, inn_filter),
        best_df=_phase_best_scores("death", s1, s2, inn_filter),
        batters_df=_phase_top_batters("death", s1, s2, inn_filter),
        bowlers_df=_phase_top_bowlers("death", s1, s2, inn_filter),
        extra_widget=_death_sixes_widget,
    )

# ─── TAB 4: PHASE COMPARISON ─────────────────────────────────────────────────
with tab_compare:
    st.subheader("Phase Comparison")
    phase_cmap = {p.capitalize(): c for p, c in PHASE_COLORS.items()}

    # Run-rate evolution
    rr_df = _phase_rr_evolution(s1, s2, inn_filter)
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
        bd_df = _phase_boundary_dist(s1, s2, inn_filter)
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
        wk_df = _phase_wicket_dist(s1, s2, inn_filter)
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
    contrib_df = _phase_contribution(s1, s2, inn_filter)
    if not contrib_df.empty:
        fig = px.bar(
            contrib_df, x="season", y="avg_runs", color="match_phase",
            title="Phase Contribution to Total Score",
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
    st.subheader("Over-by-Over Analysis")

    obo_df = _over_by_over(s1, s2, inn_filter)
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
