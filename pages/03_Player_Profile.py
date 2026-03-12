"""
Player Profile — Complete dossier of any IPL player.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style, styled_bar, styled_line, styled_scatter,
    styled_pie, get_team_color, big_number_style, IPL_COLORWAY,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS, PHASE_COLORS
from src.utils.formatters import (
    format_number, format_strike_rate, format_economy,
    format_average, format_overs,
)

# ── CSS for metric cards ─────────────────────────────────────────────────────
st.markdown(big_number_style(), unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def get_all_players():
    return query("""
        SELECT DISTINCT player FROM (
            SELECT DISTINCT batter AS player FROM player_batting
            UNION
            SELECT DISTINCT bowler AS player FROM player_bowling
        ) ORDER BY player
    """)["player"].tolist()


@st.cache_data(ttl=3600)
def get_player_teams(player):
    return query("""
        SELECT DISTINCT team FROM (
            SELECT DISTINCT batting_team AS team FROM player_batting WHERE batter = ?
            UNION
            SELECT DISTINCT bowling_team AS team FROM player_bowling WHERE bowler = ?
        ) ORDER BY team
    """, [player, player])["team"].tolist()


@st.cache_data(ttl=3600)
def get_career_span(player):
    return query("""
        SELECT MIN(season) AS first, MAX(season) AS last FROM (
            SELECT season FROM player_batting WHERE batter = ?
            UNION ALL
            SELECT season FROM player_bowling WHERE bowler = ?
        )
    """, [player, player]).iloc[0]


@st.cache_data(ttl=3600)
def get_batting_summary(player):
    return query("""
        SELECT
            COUNT(DISTINCT match_id) AS matches,
            COUNT(*) AS innings,
            COALESCE(SUM(runs), 0) AS runs,
            COALESCE(SUM(balls), 0) AS balls,
            CASE WHEN SUM(CASE WHEN was_out THEN 1 ELSE 0 END) > 0
                 THEN ROUND(SUM(runs) * 1.0 / SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 2)
                 ELSE NULL END AS avg,
            CASE WHEN SUM(balls) > 0
                 THEN ROUND(SUM(runs) * 100.0 / SUM(balls), 2)
                 ELSE NULL END AS sr,
            MAX(runs) AS highest,
            SUM(is_fifty) AS fifties,
            SUM(is_hundred) AS hundreds,
            SUM(fours) AS fours,
            SUM(sixes) AS sixes,
            SUM(CASE WHEN was_out AND runs = 0 THEN 1 ELSE 0 END) AS ducks
        FROM player_batting WHERE batter = ?
    """, [player]).iloc[0]


@st.cache_data(ttl=3600)
def get_bowling_summary(player):
    return query("""
        SELECT
            COUNT(DISTINCT match_id) AS matches,
            COALESCE(SUM(balls_bowled), 0) AS balls,
            COALESCE(SUM(wickets), 0) AS wickets,
            COALESCE(SUM(runs_conceded), 0) AS runs,
            CASE WHEN SUM(balls_bowled) > 0
                 THEN ROUND(SUM(runs_conceded) * 6.0 / SUM(balls_bowled), 2)
                 ELSE NULL END AS economy,
            CASE WHEN SUM(wickets) > 0
                 THEN ROUND(SUM(balls_bowled) * 1.0 / SUM(wickets), 2)
                 ELSE NULL END AS sr,
            CASE WHEN SUM(wickets) > 0
                 THEN ROUND(SUM(runs_conceded) * 1.0 / SUM(wickets), 2)
                 ELSE NULL END AS avg,
            COALESCE(SUM(maidens), 0) AS maidens
        FROM player_bowling WHERE bowler = ?
    """, [player]).iloc[0]


@st.cache_data(ttl=3600)
def get_batting_by_season(player):
    return query("""
        SELECT
            season,
            MAX(batting_team) AS team,
            COUNT(DISTINCT match_id) AS matches,
            COUNT(*) AS innings,
            SUM(runs) AS runs,
            SUM(balls) AS balls,
            CASE WHEN SUM(CASE WHEN was_out THEN 1 ELSE 0 END) > 0
                 THEN ROUND(SUM(runs) * 1.0 / SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 2)
                 ELSE NULL END AS avg,
            CASE WHEN SUM(balls) > 0
                 THEN ROUND(SUM(runs) * 100.0 / SUM(balls), 2)
                 ELSE NULL END AS sr,
            SUM(is_fifty) AS fifties,
            SUM(is_hundred) AS hundreds,
            MAX(runs) AS hs,
            SUM(fours) AS fours,
            SUM(sixes) AS sixes
        FROM player_batting WHERE batter = ?
        GROUP BY season ORDER BY season
    """, [player])


@st.cache_data(ttl=3600)
def get_innings_detail(player):
    return query("""
        SELECT
            pb.match_id, pb.season, pb.runs, pb.balls, pb.fours, pb.sixes,
            pb.strike_rate, pb.was_out, pb.batting_team,
            CASE WHEN m.match_won_by = pb.batting_team THEN 'Won' ELSE 'Lost/NR' END AS result
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE pb.batter = ?
        ORDER BY pb.season, pb.match_id
    """, [player])


@st.cache_data(ttl=3600)
def get_run_scoring_breakdown(player):
    return query("""
        SELECT
            CASE runs_batter
                WHEN 0 THEN 'Dots'
                WHEN 1 THEN '1s'
                WHEN 2 THEN '2s'
                WHEN 3 THEN '3s'
                WHEN 4 THEN '4s'
                WHEN 6 THEN '6s'
                ELSE 'Others'
            END AS run_type,
            COUNT(*) AS count
        FROM balls
        WHERE batter = ? AND valid_ball = true
        GROUP BY run_type
        ORDER BY CASE run_type
            WHEN 'Dots' THEN 0 WHEN '1s' THEN 1 WHEN '2s' THEN 2
            WHEN '3s' THEN 3 WHEN '4s' THEN 4 WHEN '6s' THEN 5 ELSE 6 END
    """, [player])


@st.cache_data(ttl=3600)
def get_batting_phase_stats(player):
    return query("""
        SELECT
            match_phase AS phase,
            SUM(runs_batter) AS runs,
            SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) AS balls,
            CASE WHEN SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) > 0
                 THEN ROUND(SUM(runs_batter) * 100.0 / SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 2)
                 ELSE NULL END AS sr,
            CASE WHEN SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) > 0
                 THEN ROUND(SUM(is_dot) * 100.0 / SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 1)
                 ELSE NULL END AS dot_pct,
            CASE WHEN SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) > 0
                 THEN ROUND((SUM(is_four) + SUM(is_six)) * 100.0 / SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 1)
                 ELSE NULL END AS boundary_pct
        FROM balls
        WHERE batter = ? AND match_phase IS NOT NULL
        GROUP BY match_phase
        ORDER BY CASE match_phase WHEN 'powerplay' THEN 1 WHEN 'middle' THEN 2 WHEN 'death' THEN 3 END
    """, [player])


@st.cache_data(ttl=3600)
def get_over_by_over_batting(player):
    return query("""
        SELECT
            over AS over_num,
            ROUND(AVG(runs_batter), 2) AS avg_runs,
            COUNT(*) AS balls_faced
        FROM balls
        WHERE batter = ? AND valid_ball = true
        GROUP BY over
        ORDER BY over
    """, [player])


@st.cache_data(ttl=3600)
def get_bowling_by_season(player):
    return query("""
        SELECT
            season,
            MAX(bowling_team) AS team,
            COUNT(DISTINCT match_id) AS matches,
            SUM(balls_bowled) AS balls,
            SUM(wickets) AS wickets,
            SUM(runs_conceded) AS runs,
            CASE WHEN SUM(balls_bowled) > 0
                 THEN ROUND(SUM(runs_conceded) * 6.0 / SUM(balls_bowled), 2)
                 ELSE NULL END AS economy,
            CASE WHEN SUM(wickets) > 0
                 THEN ROUND(SUM(balls_bowled) * 1.0 / SUM(wickets), 2)
                 ELSE NULL END AS sr,
            SUM(maidens) AS maidens
        FROM player_bowling WHERE bowler = ?
        GROUP BY season ORDER BY season
    """, [player])


@st.cache_data(ttl=3600)
def get_wicket_types(player):
    return query("""
        SELECT
            wicket_kind,
            COUNT(*) AS count
        FROM balls
        WHERE bowler = ? AND wicket_kind IS NOT NULL AND player_out IS NOT NULL
        GROUP BY wicket_kind
        ORDER BY count DESC
    """, [player])


@st.cache_data(ttl=3600)
def get_bowling_phase_stats(player):
    return query("""
        SELECT
            match_phase AS phase,
            SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) AS balls,
            SUM(CASE WHEN wicket_kind IS NOT NULL AND player_out IS NOT NULL THEN 1 ELSE 0 END) AS wickets,
            SUM(runs_batter) AS runs,
            CASE WHEN SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) > 0
                 THEN ROUND(SUM(runs_batter) * 6.0 / SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 2)
                 ELSE NULL END AS economy,
            CASE WHEN SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) > 0
                 THEN ROUND(SUM(is_dot) * 100.0 / SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 1)
                 ELSE NULL END AS dot_pct
        FROM balls
        WHERE bowler = ? AND match_phase IS NOT NULL
        GROUP BY match_phase
        ORDER BY CASE match_phase WHEN 'powerplay' THEN 1 WHEN 'middle' THEN 2 WHEN 'death' THEN 3 END
    """, [player])


@st.cache_data(ttl=3600)
def get_over_by_over_bowling(player):
    return query("""
        SELECT
            over AS over_num,
            CASE WHEN SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) > 0
                 THEN ROUND(SUM(runs_batter) * 6.0 / SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 2)
                 ELSE NULL END AS economy,
            SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END) AS balls_bowled
        FROM balls
        WHERE bowler = ? AND valid_ball = true
        GROUP BY over
        ORDER BY over
    """, [player])


@st.cache_data(ttl=3600)
def get_matchups_vs_bowlers(player):
    return query("""
        SELECT
            bowler AS Bowler, balls AS Balls, runs AS Runs,
            ROUND(strike_rate, 1) AS SR,
            dots AS Dots, dismissals AS Dismissals,
            ROUND(boundary_pct, 1) AS "Boundary%"
        FROM matchups
        WHERE batter = ?
        ORDER BY balls DESC
        LIMIT 20
    """, [player])


@st.cache_data(ttl=3600)
def get_matchups_vs_batters(player):
    return query("""
        SELECT
            batter AS Batter, balls AS Balls, runs AS Runs,
            ROUND(strike_rate, 1) AS SR,
            dots AS Dots, dismissals AS Dismissals,
            ROUND(boundary_pct, 1) AS "Boundary%"
        FROM matchups
        WHERE bowler = ?
        ORDER BY balls DESC
        LIMIT 20
    """, [player])


@st.cache_data(ttl=3600)
def get_top_dismissers(player):
    return query("""
        SELECT bowler, dismissals
        FROM matchups
        WHERE batter = ? AND dismissals > 0
        ORDER BY dismissals DESC
        LIMIT 10
    """, [player])


@st.cache_data(ttl=3600)
def get_dominated_bowlers(player):
    return query("""
        SELECT bowler, balls, runs, ROUND(strike_rate, 1) AS sr
        FROM matchups
        WHERE batter = ? AND balls >= 10
        ORDER BY strike_rate DESC
        LIMIT 10
    """, [player])


@st.cache_data(ttl=3600)
def get_top_victims(player):
    return query("""
        SELECT batter, dismissals
        FROM matchups
        WHERE bowler = ? AND dismissals > 0
        ORDER BY dismissals DESC
        LIMIT 10
    """, [player])


@st.cache_data(ttl=3600)
def get_dominated_batters(player):
    return query("""
        SELECT batter, balls, runs, ROUND(strike_rate, 1) AS sr
        FROM matchups
        WHERE bowler = ? AND balls >= 10
        ORDER BY strike_rate ASC
        LIMIT 10
    """, [player])


@st.cache_data(ttl=3600)
def get_batting_vs_opposition(player):
    return query("""
        SELECT
            CASE WHEN m.team1 = b.batting_team THEN m.team2 ELSE m.team1 END AS opposition,
            COUNT(DISTINCT b.match_id) AS matches,
            COUNT(*) AS innings,
            SUM(b.runs) AS runs,
            CASE WHEN SUM(CASE WHEN b.was_out THEN 1 ELSE 0 END) > 0
                 THEN ROUND(SUM(b.runs) * 1.0 / SUM(CASE WHEN b.was_out THEN 1 ELSE 0 END), 2)
                 ELSE NULL END AS avg,
            CASE WHEN SUM(b.balls) > 0
                 THEN ROUND(SUM(b.runs) * 100.0 / SUM(b.balls), 2)
                 ELSE NULL END AS sr
        FROM player_batting b
        JOIN matches m ON b.match_id = m.match_id
        WHERE b.batter = ?
        GROUP BY opposition
        ORDER BY runs DESC
    """, [player])


@st.cache_data(ttl=3600)
def get_batting_by_venue(player):
    return query("""
        SELECT
            venue,
            COUNT(DISTINCT match_id) AS matches,
            SUM(runs) AS runs,
            CASE WHEN SUM(CASE WHEN was_out THEN 1 ELSE 0 END) > 0
                 THEN ROUND(SUM(runs) * 1.0 / SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 2)
                 ELSE NULL END AS avg,
            CASE WHEN SUM(balls) > 0
                 THEN ROUND(SUM(runs) * 100.0 / SUM(balls), 2)
                 ELSE NULL END AS sr,
            MAX(runs) AS hs
        FROM player_batting WHERE batter = ?
        GROUP BY venue ORDER BY runs DESC
    """, [player])


@st.cache_data(ttl=3600)
def get_dismissal_types(player):
    return query("""
        SELECT wicket_kind, SUM(count) AS count
        FROM dismissals
        WHERE player_out = ?
        GROUP BY wicket_kind ORDER BY count DESC
    """, [player])


@st.cache_data(ttl=3600)
def get_dismissals_by_phase(player):
    return query("""
        SELECT match_phase, wicket_kind, SUM(count) AS count
        FROM dismissals_phase
        WHERE player_out = ?
        GROUP BY match_phase, wicket_kind
        ORDER BY CASE match_phase WHEN 'powerplay' THEN 1 WHEN 'middle' THEN 2 WHEN 'death' THEN 3 END
    """, [player])


@st.cache_data(ttl=3600)
def get_dismissals_by_over(player):
    return query("""
        SELECT over AS over_num, COUNT(*) AS count
        FROM balls
        WHERE player_out = ? AND wicket_kind IS NOT NULL
        GROUP BY over ORDER BY over
    """, [player])


# ═══════════════════════════════════════════════════════════════════════════════
#  PLAYER SELECTOR
# ═══════════════════════════════════════════════════════════════════════════════

all_players = get_all_players()

default_idx = 0
if "selected_player" in st.session_state and st.session_state["selected_player"] in all_players:
    default_idx = all_players.index(st.session_state["selected_player"])

player = st.selectbox(
    "Search & select a player",
    options=all_players,
    index=default_idx,
    placeholder="Type to search…",
)

if not player:
    st.info("Select a player above to view their complete IPL career analytics.")
    st.stop()

st.session_state["selected_player"] = player

# ═══════════════════════════════════════════════════════════════════════════════
#  HEADER — always visible
# ═══════════════════════════════════════════════════════════════════════════════

teams = get_player_teams(player)
span = get_career_span(player)
bat_summary = get_batting_summary(player)
bowl_summary = get_bowling_summary(player)

is_bowler = bowl_summary["balls"] > 0

st.markdown(f"# {player}")

team_tags = "  •  ".join([f"**{t}**" for t in teams])
career = f"{int(span['first'])} – {int(span['last'])}" if span["first"] else "N/A"
st.markdown(f"{team_tags}  &nbsp;|&nbsp;  Career: **{career}**")

# 8 metric cards
c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
c1.metric("Matches", format_number(bat_summary["matches"]))
c2.metric("Runs", format_number(bat_summary["runs"]))
c3.metric("Bat Avg", format_average(bat_summary["avg"]))
c4.metric("Strike Rate", format_strike_rate(bat_summary["sr"]))
c5.metric("Highest", format_number(bat_summary["highest"]) if bat_summary["highest"] else "N/A")
c6.metric("100s / 50s", f"{int(bat_summary['hundreds'])} / {int(bat_summary['fifties'])}")
c7.metric("Wickets", format_number(bowl_summary["wickets"]) if is_bowler else "N/A")
c8.metric("Economy", format_economy(bowl_summary["economy"]) if is_bowler else "N/A")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
#  TABS
# ═══════════════════════════════════════════════════════════════════════════════

tab_labels = ["Batting", "Bowling", "Matchups", "Venues & Opposition", "Dismissals"]
tabs = st.tabs(tab_labels)

# ─── BATTING TAB ──────────────────────────────────────────────────────────────
with tabs[0]:
    season_bat = get_batting_by_season(player)

    if season_bat.empty:
        st.info("No batting records found for this player.")
    else:
        # Season-by-season table
        st.subheader("Season-by-Season Batting")
        display_bat = season_bat.rename(columns={
            "season": "Season", "team": "Team", "matches": "Mat", "innings": "Inn",
            "runs": "Runs", "avg": "Avg", "sr": "SR", "fifties": "50s",
            "hundreds": "100s", "hs": "HS", "fours": "4s", "sixes": "6s",
        })
        st.dataframe(display_bat, hide_index=True, width='stretch')

        # Season runs bar + average line (dual axis)
        st.subheader("Runs & Average by Season")
        fig_dual = go.Figure()
        fig_dual.add_trace(go.Bar(
            x=season_bat["season"], y=season_bat["runs"],
            name="Runs", marker_color=IPL_COLORWAY[0],
            text=season_bat["runs"], textposition="outside",
        ))
        fig_dual.add_trace(go.Scatter(
            x=season_bat["season"], y=season_bat["avg"],
            name="Average", yaxis="y2", mode="lines+markers",
            line=dict(color=IPL_COLORWAY[2], width=3),
            marker=dict(size=8),
        ))
        fig_dual.update_layout(
            yaxis=dict(title="Runs"),
            yaxis2=dict(title="Average", overlaying="y", side="right",
                        showgrid=False),
            barmode="group",
        )
        apply_ipl_style(fig_dual, height=420)
        st.plotly_chart(fig_dual, width='stretch')

        # Cumulative runs area chart
        st.subheader("Cumulative Runs")
        cum_df = season_bat[["season", "runs"]].copy()
        cum_df["cumulative"] = cum_df["runs"].cumsum()
        fig_cum = px.area(cum_df, x="season", y="cumulative",
                          title="", markers=True)
        fig_cum.update_traces(line_color=IPL_COLORWAY[1],
                              fillcolor="rgba(78,205,196,0.2)")
        apply_ipl_style(fig_cum, height=380)
        st.plotly_chart(fig_cum, width='stretch')

        # Innings scatter
        st.subheader("Innings Scatter — Runs vs Balls")
        innings_df = get_innings_detail(player)
        if not innings_df.empty:
            fig_scatter = styled_scatter(
                innings_df, x="balls", y="runs",
                title="", color="result",
                hover_name=None, height=420,
            )
            fig_scatter.update_traces(marker=dict(size=9, opacity=0.75))
            st.plotly_chart(fig_scatter, width='stretch')

        # Score distribution histogram
        st.subheader("Score Distribution")
        bat_runs = get_batting_summary.__wrapped__(player)  # reuse: just need innings_df
        if not innings_df.empty:
            bins = [0, 1, 10, 20, 30, 50, 75, 100, 500]
            labels = ["0 (Duck)", "1–9", "10–19", "20–29", "30–49", "50–74", "75–99", "100+"]
            innings_df["bucket"] = pd.cut(
                innings_df["runs"], bins=bins, labels=labels,
                right=False, include_lowest=True,
            )
            bucket_counts = innings_df["bucket"].value_counts().reindex(labels).fillna(0).reset_index()
            bucket_counts.columns = ["Score Range", "Count"]
            fig_hist = styled_bar(bucket_counts, x="Score Range", y="Count",
                                  title="", height=380)
            fig_hist.update_traces(marker_color=IPL_COLORWAY[3])
            st.plotly_chart(fig_hist, width='stretch')

        col_a, col_b = st.columns(2)

        # Run scoring breakdown donut
        with col_a:
            st.subheader("Run Scoring Breakdown")
            rs_df = get_run_scoring_breakdown(player)
            if not rs_df.empty:
                fig_donut = styled_pie(rs_df, names="run_type", values="count",
                                       title="", hole=0.45, height=400)
                st.plotly_chart(fig_donut, width='stretch')

        # Phase-wise batting stats
        with col_b:
            st.subheader("Phase-wise Batting")
            phase_bat = get_batting_phase_stats(player)
            if not phase_bat.empty:
                phase_display = phase_bat.rename(columns={
                    "phase": "Phase", "runs": "Runs", "balls": "Balls",
                    "sr": "SR", "dot_pct": "Dot%", "boundary_pct": "Boundary%",
                })
                phase_display["Phase"] = phase_display["Phase"].str.capitalize()
                st.dataframe(phase_display, hide_index=True, width='stretch')

        # Over-by-over batting profile
        st.subheader("Over-by-Over Batting Profile")
        obo_bat = get_over_by_over_batting(player)
        if not obo_bat.empty:
            fig_obo = styled_bar(obo_bat, x="over_num", y="avg_runs",
                                 title="Average Runs per Over", height=380)
            fig_obo.update_traces(marker_color=IPL_COLORWAY[0])
            fig_obo.update_xaxes(title="Over", dtick=1)
            fig_obo.update_yaxes(title="Avg Runs")
            st.plotly_chart(fig_obo, width='stretch')

# ─── BOWLING TAB ──────────────────────────────────────────────────────────────
with tabs[1]:
    if not is_bowler:
        st.info(f"{player} has no bowling records in IPL.")
    else:
        season_bowl = get_bowling_by_season(player)

        # Season-by-season bowling table
        st.subheader("Season-by-Season Bowling")
        display_bowl = season_bowl.copy()
        display_bowl["overs"] = display_bowl["balls"].apply(
            lambda b: format_overs(int(b)) if pd.notna(b) else "N/A"
        )
        display_bowl = display_bowl.rename(columns={
            "season": "Season", "team": "Team", "matches": "Mat",
            "overs": "Overs", "wickets": "Wkts", "runs": "Runs",
            "economy": "Econ", "sr": "SR", "maidens": "Mdns",
        })[["Season", "Team", "Mat", "Overs", "Wkts", "Runs", "Econ", "SR", "Mdns"]]
        st.dataframe(display_bowl, hide_index=True, width='stretch')

        # Season wickets bar + economy line
        st.subheader("Wickets & Economy by Season")
        fig_bowl_dual = go.Figure()
        fig_bowl_dual.add_trace(go.Bar(
            x=season_bowl["season"], y=season_bowl["wickets"],
            name="Wickets", marker_color=IPL_COLORWAY[2],
            text=season_bowl["wickets"], textposition="outside",
        ))
        fig_bowl_dual.add_trace(go.Scatter(
            x=season_bowl["season"], y=season_bowl["economy"],
            name="Economy", yaxis="y2", mode="lines+markers",
            line=dict(color=IPL_COLORWAY[0], width=3),
            marker=dict(size=8),
        ))
        fig_bowl_dual.update_layout(
            yaxis=dict(title="Wickets"),
            yaxis2=dict(title="Economy", overlaying="y", side="right",
                        showgrid=False),
        )
        apply_ipl_style(fig_bowl_dual, height=420)
        st.plotly_chart(fig_bowl_dual, width='stretch')

        col_w, col_p = st.columns(2)

        # Wicket types donut
        with col_w:
            st.subheader("Wicket Types")
            wkt_types = get_wicket_types(player)
            if not wkt_types.empty:
                fig_wkt = styled_pie(wkt_types, names="wicket_kind", values="count",
                                     title="", hole=0.45, height=400)
                st.plotly_chart(fig_wkt, width='stretch')

        # Phase-wise bowling table
        with col_p:
            st.subheader("Phase-wise Bowling")
            phase_bowl = get_bowling_phase_stats(player)
            if not phase_bowl.empty:
                phase_bowl_display = phase_bowl.copy()
                phase_bowl_display["overs"] = phase_bowl_display["balls"].apply(
                    lambda b: format_overs(int(b)) if pd.notna(b) else "N/A"
                )
                phase_bowl_display = phase_bowl_display.rename(columns={
                    "phase": "Phase", "overs": "Overs", "wickets": "Wkts",
                    "economy": "Econ", "dot_pct": "Dot%",
                })[["Phase", "Overs", "Wkts", "Econ", "Dot%"]]
                phase_bowl_display["Phase"] = phase_bowl_display["Phase"].str.capitalize()
                st.dataframe(phase_bowl_display, hide_index=True, width='stretch')

        # Over-by-over economy bar chart
        st.subheader("Over-by-Over Economy")
        obo_bowl = get_over_by_over_bowling(player)
        if not obo_bowl.empty:
            fig_obo_bowl = styled_bar(obo_bowl, x="over_num", y="economy",
                                      title="Economy Rate per Over", height=380)
            fig_obo_bowl.update_traces(marker_color=IPL_COLORWAY[2])
            fig_obo_bowl.update_xaxes(title="Over", dtick=1)
            fig_obo_bowl.update_yaxes(title="Economy")
            st.plotly_chart(fig_obo_bowl, width='stretch')

# ─── MATCHUPS TAB ─────────────────────────────────────────────────────────────
with tabs[2]:
    # vs Bowlers section
    st.subheader("vs Bowlers (as Batter)")
    mu_bowlers = get_matchups_vs_bowlers(player)
    if mu_bowlers.empty:
        st.info("No matchup data available for this player as a batter.")
    else:
        st.dataframe(mu_bowlers, hide_index=True, width='stretch')

        col_d, col_dom = st.columns(2)

        with col_d:
            st.subheader("Top Dismissers")
            dismissers = get_top_dismissers(player)
            if not dismissers.empty:
                fig_dis = styled_bar(
                    dismissers, x="bowler", y="dismissals",
                    title="", height=380,
                )
                fig_dis.update_traces(marker_color=IPL_COLORWAY[0])
                st.plotly_chart(fig_dis, width='stretch')

        with col_dom:
            st.subheader("Dominated Bowlers (SR, min 10 balls)")
            dominated = get_dominated_bowlers(player)
            if not dominated.empty:
                fig_dom = styled_bar(
                    dominated, x="bowler", y="sr",
                    title="", height=380,
                )
                fig_dom.update_traces(marker_color=IPL_COLORWAY[1])
                st.plotly_chart(fig_dom, width='stretch')

    # vs Batters section (only if bowler)
    if is_bowler:
        st.divider()
        st.subheader("vs Batters (as Bowler)")
        mu_batters = get_matchups_vs_batters(player)
        if mu_batters.empty:
            st.info("No matchup data available for this player as a bowler.")
        else:
            st.dataframe(mu_batters, hide_index=True, width='stretch')

            col_v, col_d2 = st.columns(2)

            with col_v:
                st.subheader("Top Victims")
                victims = get_top_victims(player)
                if not victims.empty:
                    fig_vic = styled_bar(
                        victims, x="batter", y="dismissals",
                        title="", height=380,
                    )
                    fig_vic.update_traces(marker_color=IPL_COLORWAY[2])
                    st.plotly_chart(fig_vic, width='stretch')

            with col_d2:
                st.subheader("Dominated Batters (lowest SR, min 10 balls)")
                dom_bat = get_dominated_batters(player)
                if not dom_bat.empty:
                    fig_dom_bat = styled_bar(
                        dom_bat, x="batter", y="sr",
                        title="", height=380,
                    )
                    fig_dom_bat.update_traces(marker_color=IPL_COLORWAY[4])
                    st.plotly_chart(fig_dom_bat, width='stretch')

# ─── VENUES & OPPOSITION TAB ─────────────────────────────────────────────────
with tabs[3]:
    col_opp, col_ven = st.columns(2)

    with col_opp:
        st.subheader("Performance by Opposition")
        opp_df = get_batting_vs_opposition(player)
        if opp_df.empty:
            st.info("No opposition data available.")
        else:
            opp_display = opp_df.rename(columns={
                "opposition": "Opposition", "matches": "Mat", "innings": "Inn",
                "runs": "Runs", "avg": "Avg", "sr": "SR",
            })
            st.dataframe(opp_display, hide_index=True, width='stretch')

    with col_ven:
        st.subheader("Performance by Venue")
        ven_df = get_batting_by_venue(player)
        if ven_df.empty:
            st.info("No venue data available.")
        else:
            ven_display = ven_df.rename(columns={
                "venue": "Venue", "matches": "Mat",
                "runs": "Runs", "avg": "Avg", "sr": "SR", "hs": "HS",
            })
            st.dataframe(ven_display, hide_index=True, width='stretch')

# ─── DISMISSALS TAB ──────────────────────────────────────────────────────────
with tabs[4]:
    dis_types = get_dismissal_types(player)

    if dis_types.empty:
        st.info("No dismissal data found for this player.")
    else:
        col_pie, col_phase = st.columns(2)

        with col_pie:
            st.subheader("Dismissal Types")
            fig_dis_pie = styled_pie(dis_types, names="wicket_kind", values="count",
                                     title="", hole=0.45, height=420)
            st.plotly_chart(fig_dis_pie, width='stretch')

        with col_phase:
            st.subheader("Dismissals by Phase")
            dis_phase = get_dismissals_by_phase(player)
            if not dis_phase.empty:
                dis_phase["match_phase"] = dis_phase["match_phase"].str.capitalize()
                fig_phase_bar = px.bar(
                    dis_phase, x="match_phase", y="count", color="wicket_kind",
                    title="", barmode="stack",
                )
                apply_ipl_style(fig_phase_bar, height=420)
                fig_phase_bar.update_xaxes(title="Phase")
                fig_phase_bar.update_yaxes(title="Dismissals")
                st.plotly_chart(fig_phase_bar, width='stretch')

        st.subheader("Dismissals by Over")
        dis_over = get_dismissals_by_over(player)
        if not dis_over.empty:
            fig_dis_over = styled_bar(
                dis_over, x="over_num", y="count",
                title="", height=380,
            )
            fig_dis_over.update_traces(marker_color=IPL_COLORWAY[0])
            fig_dis_over.update_xaxes(title="Over", dtick=1)
            fig_dis_over.update_yaxes(title="Dismissals")
            st.plotly_chart(fig_dis_over, width='stretch')
