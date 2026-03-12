"""
Pressure & Momentum — Dot ball cascades, chase dynamics, clutch performances.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style, styled_bar, styled_line, styled_scatter,
    get_team_color, big_number_style, IPL_COLORWAY,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS, PHASE_COLORS
from src.utils.formatters import format_number, format_strike_rate

st.title("Pressure & Momentum")
st.markdown(big_number_style(), unsafe_allow_html=True)

# ── Filters ────────────────────────────────────────────────────────────
s1, s2 = st.slider(
    "Season range",
    min_value=min(ALL_SEASONS),
    max_value=max(ALL_SEASONS),
    value=(min(ALL_SEASONS), max(ALL_SEASONS)),
    key="pm_season_range",
)

# Outcome colors for dot sequence charts
OUTCOME_COLORS = {
    "boundary": "#FF6B6B",
    "scoring_shot": "#4ECDC4",
    "wicket": "#FFEAA7",
    "other": "#AED6F1",
}


# ═══════════════════════════════════════════════════════════════════════
#  CACHED QUERY HELPERS
# ═══════════════════════════════════════════════════════════════════════

# ── DOT BALL PRESSURE ─────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _dot_cascade(s1, s2):
    """Stacked outcome distribution after N consecutive dots."""
    return query(f"""
        SELECT consecutive_dots_before          AS dots,
               dot_sequence_outcome             AS outcome,
               COUNT(*)::INT                    AS cnt
        FROM   balls
        WHERE  is_sequence_breaker = true
               AND season BETWEEN {s1} AND {s2}
        GROUP  BY dots, outcome
        ORDER  BY dots, outcome
    """)


@st.cache_data(ttl=3600)
def _dismissal_prob_after_dots(s1, s2):
    """Wicket probability after N consecutive dots."""
    return query(f"""
        SELECT consecutive_dots_before          AS dots,
               COUNT(*)::INT                    AS total_balls,
               SUM(CASE WHEN wicket_kind IS NOT NULL
                         AND wicket_kind != 'not_out'
                    THEN 1 ELSE 0 END)::INT     AS wickets,
               ROUND(SUM(CASE WHEN wicket_kind IS NOT NULL
                               AND wicket_kind != 'not_out'
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 2)  AS wicket_pct
        FROM   balls
        WHERE  season BETWEEN {s1} AND {s2}
               AND valid_ball = true
        GROUP  BY dots
        HAVING total_balls >= 100
        ORDER  BY dots
    """)


@st.cache_data(ttl=3600)
def _team_dot_resilience(s1, s2):
    """Per-team outcomes after 3+ consecutive dots."""
    return query(f"""
        SELECT batting_team                     AS team,
               COUNT(*)::INT                    AS pressure_balls,
               ROUND(SUM(CASE WHEN dot_sequence_outcome = 'boundary'
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS boundary_pct,
               ROUND(SUM(CASE WHEN dot_sequence_outcome = 'wicket'
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS wicket_pct,
               ROUND(SUM(CASE WHEN dot_sequence_outcome = 'scoring_shot'
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS scoring_pct
        FROM   balls
        WHERE  is_sequence_breaker = true
               AND consecutive_dots_before >= 3
               AND season BETWEEN {s1} AND {s2}
        GROUP  BY team
        HAVING pressure_balls >= 50
        ORDER  BY boundary_pct DESC
    """)


@st.cache_data(ttl=3600)
def _dot_ball_creators(s1, s2):
    """Top 15 bowlers by dot balls bowled."""
    return query(f"""
        SELECT bowler,
               SUM(CASE WHEN is_dot THEN 1 ELSE 0 END)::INT    AS total_dots,
               COUNT(*)::INT                                     AS total_balls,
               ROUND(SUM(CASE WHEN is_dot THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)                   AS dot_pct,
               ROUND(AVG(CASE WHEN is_dot THEN consecutive_dots_before + 1
                              ELSE NULL END), 2)                 AS avg_consec_dots
        FROM   balls
        WHERE  valid_ball = true
               AND season BETWEEN {s1} AND {s2}
        GROUP  BY bowler
        HAVING total_balls >= 300
        ORDER  BY total_dots DESC
        LIMIT  15
    """)


@st.cache_data(ttl=3600)
def _phase_dot_pct(s1, s2):
    """Dot ball percentage by match phase."""
    return query(f"""
        SELECT match_phase                      AS phase,
               COUNT(*)::INT                    AS total_balls,
               SUM(CASE WHEN is_dot THEN 1 ELSE 0 END)::INT AS dots,
               ROUND(SUM(CASE WHEN is_dot THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS dot_pct
        FROM   balls
        WHERE  valid_ball = true
               AND match_phase IS NOT NULL
               AND season BETWEEN {s1} AND {s2}
        GROUP  BY phase
        ORDER  BY CASE phase
                    WHEN 'powerplay' THEN 1
                    WHEN 'middle'    THEN 2
                    WHEN 'death'     THEN 3
                  END
    """)


# ── CHASE DYNAMICS ────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _chase_success_by_target(s1, s2):
    """Chase win % by target run buckets."""
    return query(f"""
        WITH chase AS (
            SELECT match_id,
                   team1_score + 1                              AS target,
                   CASE WHEN batting_first_won = false THEN 1 ELSE 0 END AS chase_won
            FROM   matches
            WHERE  season BETWEEN {s1} AND {s2}
                   AND team1_score IS NOT NULL
                   AND team2_score IS NOT NULL
                   AND result_type = 'normal'
        )
        SELECT CASE
                 WHEN target <= 120 THEN '100-120'
                 WHEN target <= 140 THEN '121-140'
                 WHEN target <= 160 THEN '141-160'
                 WHEN target <= 180 THEN '161-180'
                 WHEN target <= 200 THEN '181-200'
                 ELSE '201+'
               END                                              AS target_range,
               COUNT(*)::INT                                    AS matches,
               SUM(chase_won)::INT                              AS chase_wins,
               ROUND(SUM(chase_won) * 100.0
                     / NULLIF(COUNT(*), 0), 1)                  AS chase_win_pct
        FROM   chase
        GROUP  BY target_range
        ORDER  BY MIN(target)
    """)


@st.cache_data(ttl=3600)
def _chase_success_by_season(s1, s2):
    """Season-wise chase win %."""
    return query(f"""
        SELECT season,
               COUNT(*)::INT                                    AS matches,
               SUM(CASE WHEN batting_first_won = false
                    THEN 1 ELSE 0 END)::INT                     AS chase_wins,
               ROUND(SUM(CASE WHEN batting_first_won = false
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)                  AS chase_win_pct
        FROM   matches
        WHERE  season BETWEEN {s1} AND {s2}
               AND team1_score IS NOT NULL
               AND team2_score IS NOT NULL
               AND result_type = 'normal'
        GROUP  BY season
        ORDER  BY season
    """)


@st.cache_data(ttl=3600)
def _highest_successful_chases(s1, s2):
    """Top 15 highest successful chases."""
    return query(f"""
        SELECT match_won_by                     AS team,
               team1_score + 1                  AS target,
               team2_score::INT                 AS score,
               season,
               venue,
               CAST(win_margin_value AS INT)    AS margin_wickets
        FROM   matches
        WHERE  season BETWEEN {s1} AND {s2}
               AND batting_first_won = false
               AND win_margin_type = 'wickets'
               AND result_type = 'normal'
        ORDER  BY target DESC
        LIMIT  15
    """)


@st.cache_data(ttl=3600)
def _lowest_totals_defended(s1, s2):
    """Top 15 lowest totals successfully defended."""
    return query(f"""
        SELECT team1                            AS defending_team,
               team1_score::INT                 AS total_defended,
               team2                            AS chasing_team,
               team2_score::INT                 AS chaser_score,
               season,
               venue,
               CAST(win_margin_value AS INT)    AS margin_runs
        FROM   matches
        WHERE  season BETWEEN {s1} AND {s2}
               AND batting_first_won = true
               AND win_margin_type = 'runs'
               AND result_type = 'normal'
        ORDER  BY total_defended ASC
        LIMIT  15
    """)


@st.cache_data(ttl=3600)
def _best_chase_innings(s1, s2):
    """Top 15 individual batting performances in successful chases."""
    return query(f"""
        SELECT b.batter,
               SUM(b.runs_batter)::INT                         AS runs,
               SUM(CASE WHEN b.valid_ball THEN 1 ELSE 0 END)::INT AS balls,
               ROUND(SUM(b.runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN b.valid_ball
                                  THEN 1 ELSE 0 END), 0), 1)   AS sr,
               (m.team1_score + 1)::INT                         AS target,
               b.season,
               b.batting_team                                   AS team
        FROM   balls b
        JOIN   matches m ON b.match_id = m.match_id
        WHERE  b.innings = 2
               AND b.season BETWEEN {s1} AND {s2}
               AND m.batting_first_won = false
               AND b.batting_team = m.match_won_by
               AND m.result_type = 'normal'
        GROUP  BY b.match_id, b.batter, b.season, b.batting_team,
                  m.team1_score
        HAVING runs >= 30
        ORDER  BY runs DESC, sr DESC
        LIMIT  15
    """)


@st.cache_data(ttl=3600)
def _teams_best_at_chasing(s1, s2):
    """Team chase records."""
    return query(f"""
        SELECT team2                            AS team,
               COUNT(*)::INT                    AS chase_matches,
               SUM(CASE WHEN batting_first_won = false
                    THEN 1 ELSE 0 END)::INT     AS chase_wins,
               ROUND(SUM(CASE WHEN batting_first_won = false
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS chase_win_pct,
               ROUND(AVG(CASE WHEN batting_first_won = false
                               AND win_margin_type = 'wickets'
                          THEN win_margin_value
                          ELSE NULL END), 1)    AS avg_chase_margin_wkts
        FROM   matches
        WHERE  season BETWEEN {s1} AND {s2}
               AND team1_score IS NOT NULL
               AND team2_score IS NOT NULL
               AND result_type = 'normal'
        GROUP  BY team
        HAVING chase_matches >= 10
        ORDER  BY chase_win_pct DESC
    """)


# ── PARTNERSHIPS UNDER PRESSURE ───────────────────────────────────────

@st.cache_data(ttl=3600)
def _partnership_rr_by_wicket(s1, s2):
    """Average partnership run rate by wicket number."""
    return query(f"""
        SELECT wicket_number,
               ROUND(AVG(run_rate), 2)          AS avg_rr,
               COUNT(*)::INT                    AS partnerships
        FROM   partnerships
        WHERE  season BETWEEN {s1} AND {s2}
               AND wicket_number BETWEEN 1 AND 10
               AND balls >= 6
        GROUP  BY wicket_number
        ORDER  BY wicket_number
    """)


@st.cache_data(ttl=3600)
def _recovery_partnerships(s1, s2):
    """50+ run partnerships when 3+ wickets down in first 10 overs."""
    return query(f"""
        SELECT p.batting_partners,
               p.runs::INT                      AS runs,
               p.balls::INT                     AS balls,
               ROUND(p.run_rate, 2)             AS rr,
               p.batting_team                   AS team,
               p.season,
               p.team_wicket_at_start::INT      AS wkts_down
        FROM   partnerships p
        WHERE  p.season BETWEEN {s1} AND {s2}
               AND p.runs >= 50
               AND p.team_wicket_at_start >= 3
               AND p.wicket_number <= 6
        ORDER  BY p.runs DESC
        LIMIT  20
    """)


@st.cache_data(ttl=3600)
def _biggest_partnerships(s1, s2):
    """Top 20 partnerships by runs."""
    return query(f"""
        SELECT p.batting_partners,
               p.runs::INT                      AS runs,
               p.balls::INT                     AS balls,
               ROUND(p.run_rate, 2)             AS rr,
               p.batting_team                   AS team,
               p.season,
               p.boundaries::INT                AS boundaries
        FROM   partnerships p
        WHERE  p.season BETWEEN {s1} AND {s2}
        ORDER  BY p.runs DESC
        LIMIT  20
    """)


@st.cache_data(ttl=3600)
def _most_impactful_partnerships(s1, s2):
    """Top 20 partnerships by runs × run_rate (impact score)."""
    return query(f"""
        SELECT p.batting_partners,
               p.runs::INT                      AS runs,
               p.balls::INT                     AS balls,
               ROUND(p.run_rate, 2)             AS rr,
               ROUND(p.runs * p.run_rate, 1)    AS impact_score,
               p.batting_team                   AS team,
               p.season
        FROM   partnerships p
        WHERE  p.season BETWEEN {s1} AND {s2}
               AND p.balls >= 12
        ORDER  BY impact_score DESC
        LIMIT  20
    """)


# ── CLUTCH PERFORMANCES ──────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _close_match_heroes(s1, s2):
    """Top 15 players by avg runs in close matches (min 10 matches)."""
    return query(f"""
        SELECT batter,
               COUNT(DISTINCT match_id)::INT    AS matches,
               SUM(runs_batter)::INT            AS total_runs,
               ROUND(SUM(runs_batter) * 1.0
                     / NULLIF(COUNT(DISTINCT match_id), 0), 2) AS avg_runs,
               ROUND(SUM(runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball
                                  THEN 1 ELSE 0 END), 0), 1)   AS sr
        FROM   balls
        WHERE  is_close_match = true
               AND season BETWEEN {s1} AND {s2}
        GROUP  BY batter
        HAVING matches >= 10
        ORDER  BY avg_runs DESC
        LIMIT  15
    """)


@st.cache_data(ttl=3600)
def _playoff_performance(s1, s2):
    """Top 15 players by runs in playoffs."""
    return query(f"""
        SELECT batter,
               COUNT(DISTINCT match_id)::INT    AS matches,
               SUM(runs_batter)::INT            AS total_runs,
               ROUND(SUM(runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball
                                  THEN 1 ELSE 0 END), 0), 1)   AS sr,
               SUM(CASE WHEN is_four THEN 1 ELSE 0 END)::INT   AS fours,
               SUM(CASE WHEN is_six  THEN 1 ELSE 0 END)::INT   AS sixes
        FROM   balls
        WHERE  stage != 'League'
               AND stage IS NOT NULL
               AND season BETWEEN {s1} AND {s2}
        GROUP  BY batter
        HAVING total_runs >= 50
        ORDER  BY total_runs DESC
        LIMIT  15
    """)


@st.cache_data(ttl=3600)
def _final_heroes(s1, s2):
    """Player of the Match in Finals."""
    return query(f"""
        SELECT player_of_match                  AS player,
               match_won_by                     AS winning_team,
               season,
               team1_score::INT                 AS team1_score,
               team2_score::INT                 AS team2_score,
               venue
        FROM   matches
        WHERE  stage = 'Final'
               AND season BETWEEN {s1} AND {s2}
               AND player_of_match IS NOT NULL
        ORDER  BY season DESC
    """)


@st.cache_data(ttl=3600)
def _death_over_pressure_batting(s1, s2):
    """Top 15 players by SR in death overs of close matches."""
    return query(f"""
        SELECT batter,
               COUNT(DISTINCT match_id)::INT    AS matches,
               SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS balls,
               SUM(runs_batter)::INT            AS runs,
               ROUND(SUM(runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball
                                  THEN 1 ELSE 0 END), 0), 1)   AS sr,
               SUM(CASE WHEN is_six THEN 1 ELSE 0 END)::INT    AS sixes
        FROM   balls
        WHERE  match_phase = 'death'
               AND is_close_match = true
               AND season BETWEEN {s1} AND {s2}
        GROUP  BY batter
        HAVING balls >= 60
        ORDER  BY sr DESC
        LIMIT  15
    """)


# ═══════════════════════════════════════════════════════════════════════
#  PAGE LAYOUT — TABS
# ═══════════════════════════════════════════════════════════════════════

tab_dots, tab_chase, tab_partner, tab_clutch = st.tabs([
    "Dot Ball Pressure",
    "Chase Dynamics",
    "Partnerships Under Pressure",
    "Clutch Performances",
])

# ── TAB 1: DOT BALL PRESSURE ─────────────────────────────────────────
with tab_dots:
    st.header("Dot Ball Pressure Analysis")

    # 1. Dot cascade stacked bar
    cascade_df = _dot_cascade(s1, s2)
    if not cascade_df.empty:
        cascade_df["dots"] = cascade_df["dots"].clip(upper=6)
        cascade_agg = (
            cascade_df.groupby(["dots", "outcome"], as_index=False)["cnt"].sum()
        )
        cascade_agg["dots_label"] = cascade_agg["dots"].apply(
            lambda d: f"{d}+" if d == 6 else str(d)
        )
        fig_cascade = px.bar(
            cascade_agg,
            x="dots_label",
            y="cnt",
            color="outcome",
            title="Dot Ball Cascade — What Happens After N Consecutive Dots?",
            color_discrete_map=OUTCOME_COLORS,
            barmode="stack",
            labels={"dots_label": "Consecutive Dots Before", "cnt": "Count"},
        )
        fig_cascade = apply_ipl_style(fig_cascade, height=480)
        st.plotly_chart(fig_cascade, width='stretch')
    else:
        st.info("No dot cascade data available for the selected range.")

    st.divider()

    # 2. Dismissal probability after N dots
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Dismissal Probability After N Dots")
        prob_df = _dismissal_prob_after_dots(s1, s2)
        if not prob_df.empty:
            disp = prob_df[["dots", "total_balls", "wickets", "wicket_pct"]].copy()
            disp.columns = ["Consecutive Dots", "Total Balls", "Wickets", "Wicket %"]
            st.dataframe(disp, width='stretch', hide_index=True)

    # 3. Team dot ball resilience
    with col_b:
        st.subheader("Team Dot Ball Resilience (After 3+ Dots)")
        resil_df = _team_dot_resilience(s1, s2)
        if not resil_df.empty:
            disp = resil_df[["team", "pressure_balls", "boundary_pct",
                             "wicket_pct", "scoring_pct"]].copy()
            disp.columns = ["Team", "Pressure Balls", "Boundary %",
                            "Wicket %", "Scoring Shot %"]
            st.dataframe(disp, width='stretch', hide_index=True)

    st.divider()

    col_c, col_d = st.columns(2)

    # 4. Dot ball creators
    with col_c:
        st.subheader("Top Dot Ball Creators")
        creators_df = _dot_ball_creators(s1, s2)
        if not creators_df.empty:
            disp = creators_df[["bowler", "total_dots", "total_balls",
                                "dot_pct", "avg_consec_dots"]].copy()
            disp.columns = ["Bowler", "Dot Balls", "Total Balls",
                            "Dot %", "Avg Consec Dots"]
            st.dataframe(disp, width='stretch', hide_index=True)

    # 5. Phase-wise dot analysis
    with col_d:
        st.subheader("Dot Ball % by Match Phase")
        phase_df = _phase_dot_pct(s1, s2)
        if not phase_df.empty:
            phase_df["phase_label"] = phase_df["phase"].str.capitalize()
            phase_colors = [PHASE_COLORS.get(p, "#888888") for p in phase_df["phase"]]
            fig_phase = go.Figure(go.Bar(
                x=phase_df["phase_label"],
                y=phase_df["dot_pct"],
                marker_color=phase_colors,
                text=phase_df["dot_pct"].apply(lambda v: f"{v}%"),
                textposition="outside",
            ))
            fig_phase.update_layout(
                title="Dot Ball % — Powerplay vs Middle vs Death",
                yaxis_title="Dot %",
                xaxis_title="Phase",
            )
            fig_phase = apply_ipl_style(fig_phase, height=400, show_legend=False)
            st.plotly_chart(fig_phase, width='stretch')


# ── TAB 2: CHASE DYNAMICS ────────────────────────────────────────────
with tab_chase:
    st.header("Chase Dynamics")

    # 1. Chase success rate by target range
    chase_target_df = _chase_success_by_target(s1, s2)
    if not chase_target_df.empty:
        fig_chase = go.Figure(go.Bar(
            x=chase_target_df["target_range"],
            y=chase_target_df["chase_win_pct"],
            marker_color=IPL_COLORWAY[:len(chase_target_df)],
            text=chase_target_df.apply(
                lambda r: f"{r['chase_win_pct']}%<br>({r['chase_wins']}/{r['matches']})",
                axis=1,
            ),
            textposition="outside",
        ))
        fig_chase.update_layout(
            title="Chase Success Rate by Target Range",
            xaxis_title="Target Runs",
            yaxis_title="Chase Win %",
            yaxis_range=[0, 100],
        )
        fig_chase = apply_ipl_style(fig_chase, height=450, show_legend=False)
        st.plotly_chart(fig_chase, width='stretch')

    st.divider()

    # 2. Chase success rate over seasons
    chase_season_df = _chase_success_by_season(s1, s2)
    if not chase_season_df.empty:
        fig_season = styled_line(
            chase_season_df,
            x="season",
            y="chase_win_pct",
            title="Chase Success Rate Over Seasons",
        )
        fig_season.update_layout(
            yaxis_title="Chase Win %",
            xaxis_title="Season",
            yaxis_range=[0, 100],
        )
        st.plotly_chart(fig_season, width='stretch')

    st.divider()

    col_e, col_f = st.columns(2)

    # 3. Highest successful chases
    with col_e:
        st.subheader("Highest Successful Chases")
        high_chase_df = _highest_successful_chases(s1, s2)
        if not high_chase_df.empty:
            disp = high_chase_df[["team", "target", "score", "season",
                                  "venue", "margin_wickets"]].copy()
            disp.columns = ["Team", "Target", "Score", "Season",
                            "Venue", "Margin (wkts)"]
            st.dataframe(disp, width='stretch', hide_index=True)

    # 4. Lowest totals defended
    with col_f:
        st.subheader("Lowest Totals Defended")
        low_defend_df = _lowest_totals_defended(s1, s2)
        if not low_defend_df.empty:
            disp = low_defend_df[["defending_team", "total_defended",
                                  "chasing_team", "chaser_score",
                                  "season", "venue", "margin_runs"]].copy()
            disp.columns = ["Defending Team", "Total", "Chasing Team",
                            "Chaser Score", "Season", "Venue", "Margin (runs)"]
            st.dataframe(disp, width='stretch', hide_index=True)

    st.divider()

    col_g, col_h = st.columns(2)

    # 5. Best chase innings
    with col_g:
        st.subheader("Best Individual Chase Innings")
        best_chase_df = _best_chase_innings(s1, s2)
        if not best_chase_df.empty:
            disp = best_chase_df[["batter", "runs", "balls", "sr",
                                  "target", "season", "team"]].copy()
            disp.columns = ["Batter", "Runs", "Balls", "SR",
                            "Target", "Season", "Team"]
            disp["SR"] = disp["SR"].apply(
                lambda v: format_strike_rate(v) if pd.notna(v) else "—"
            )
            st.dataframe(disp, width='stretch', hide_index=True)

    # 6. Teams best at chasing
    with col_h:
        st.subheader("Teams Best at Chasing")
        team_chase_df = _teams_best_at_chasing(s1, s2)
        if not team_chase_df.empty:
            disp = team_chase_df[["team", "chase_matches", "chase_wins",
                                  "chase_win_pct",
                                  "avg_chase_margin_wkts"]].copy()
            disp.columns = ["Team", "Chase Matches", "Wins",
                            "Chase Win %", "Avg Margin (wkts)"]
            st.dataframe(disp, width='stretch', hide_index=True)


# ── TAB 3: PARTNERSHIPS UNDER PRESSURE ───────────────────────────────
with tab_partner:
    st.header("Partnerships Under Pressure")

    # 1. Partnership run rate by wicket number
    rr_wkt_df = _partnership_rr_by_wicket(s1, s2)
    if not rr_wkt_df.empty:
        fig_rr = go.Figure(go.Scatter(
            x=rr_wkt_df["wicket_number"],
            y=rr_wkt_df["avg_rr"],
            mode="lines+markers+text",
            text=rr_wkt_df["avg_rr"].apply(lambda v: f"{v:.2f}"),
            textposition="top center",
            line=dict(color=IPL_COLORWAY[0], width=3),
            marker=dict(size=10),
        ))
        fig_rr.update_layout(
            title="Average Partnership Run Rate by Wicket Number",
            xaxis_title="Wicket Number",
            yaxis_title="Avg Run Rate",
            xaxis=dict(dtick=1),
        )
        fig_rr = apply_ipl_style(fig_rr, height=420, show_legend=False)
        st.plotly_chart(fig_rr, width='stretch')

    st.divider()

    # 2. Recovery partnerships
    st.subheader("Recovery Partnerships (50+ Runs When 3+ Wickets Down)")
    recovery_df = _recovery_partnerships(s1, s2)
    if not recovery_df.empty:
        disp = recovery_df[["batting_partners", "runs", "balls", "rr",
                            "team", "season", "wkts_down"]].copy()
        disp.columns = ["Partners", "Runs", "Balls", "RR",
                        "Team", "Season", "Wickets Down"]
        st.dataframe(disp, width='stretch', hide_index=True)
    else:
        st.info("No recovery partnerships found for the selected range.")

    st.divider()

    col_i, col_j = st.columns(2)

    # 3. Biggest partnerships
    with col_i:
        st.subheader("Biggest Partnerships (Top 20)")
        big_df = _biggest_partnerships(s1, s2)
        if not big_df.empty:
            disp = big_df[["batting_partners", "runs", "balls", "rr",
                           "boundaries", "team", "season"]].copy()
            disp.columns = ["Partners", "Runs", "Balls", "RR",
                            "Boundaries", "Team", "Season"]
            st.dataframe(disp, width='stretch', hide_index=True)

    # 4. Most impactful partnerships
    with col_j:
        st.subheader("Most Impactful Partnerships (Top 20)")
        impact_df = _most_impactful_partnerships(s1, s2)
        if not impact_df.empty:
            disp = impact_df[["batting_partners", "runs", "balls", "rr",
                              "impact_score", "team", "season"]].copy()
            disp.columns = ["Partners", "Runs", "Balls", "RR",
                            "Impact Score", "Team", "Season"]
            st.dataframe(disp, width='stretch', hide_index=True)


# ── TAB 4: CLUTCH PERFORMANCES ───────────────────────────────────────
with tab_clutch:
    st.header("Clutch Performances")

    col_k, col_l = st.columns(2)

    # 1. Close match heroes
    with col_k:
        st.subheader("Close Match Heroes")
        st.caption("Min 10 close matches · Avg runs per match")
        heroes_df = _close_match_heroes(s1, s2)
        if not heroes_df.empty:
            disp = heroes_df[["batter", "matches", "total_runs",
                              "avg_runs", "sr"]].copy()
            disp.columns = ["Batter", "Matches", "Total Runs",
                            "Avg Runs/Match", "SR"]
            disp["SR"] = disp["SR"].apply(
                lambda v: format_strike_rate(v) if pd.notna(v) else "—"
            )
            st.dataframe(disp, width='stretch', hide_index=True)

    # 2. Playoff performance
    with col_l:
        st.subheader("Playoff Run Scorers")
        playoff_df = _playoff_performance(s1, s2)
        if not playoff_df.empty:
            disp = playoff_df[["batter", "matches", "total_runs",
                               "sr", "fours", "sixes"]].copy()
            disp.columns = ["Batter", "Matches", "Runs", "SR", "4s", "6s"]
            disp["SR"] = disp["SR"].apply(
                lambda v: format_strike_rate(v) if pd.notna(v) else "—"
            )
            st.dataframe(disp, width='stretch', hide_index=True)

    st.divider()

    col_m, col_n = st.columns(2)

    # 3. Final heroes
    with col_m:
        st.subheader("Final — Player of the Match")
        final_df = _final_heroes(s1, s2)
        if not final_df.empty:
            disp = final_df[["player", "winning_team", "season",
                             "team1_score", "team2_score", "venue"]].copy()
            disp.columns = ["Player", "Winning Team", "Season",
                            "1st Inn Score", "2nd Inn Score", "Venue"]
            st.dataframe(disp, width='stretch', hide_index=True)

    # 4. Death over pressure batting
    with col_n:
        st.subheader("Death Over Batting Under Pressure")
        st.caption("Close matches · Death overs · Min 60 balls")
        death_df = _death_over_pressure_batting(s1, s2)
        if not death_df.empty:
            disp = death_df[["batter", "matches", "balls", "runs",
                             "sr", "sixes"]].copy()
            disp.columns = ["Batter", "Matches", "Balls", "Runs", "SR", "6s"]
            disp["SR"] = disp["SR"].apply(
                lambda v: format_strike_rate(v) if pd.notna(v) else "—"
            )
            st.dataframe(disp, width='stretch', hide_index=True)
