"""
Head-to-Head — Deep matchup comparisons: Batter vs Bowler & Team vs Team.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import (apply_ipl_style, styled_bar, styled_pie,
                                       get_team_color, big_number_style, IPL_COLORWAY)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS
from src.utils.formatters import format_number, format_strike_rate, format_average

st.markdown(big_number_style(), unsafe_allow_html=True)
st.title("Head-to-Head")
st.caption("Deep matchup comparisons — Batter vs Bowler or Team vs Team")

# ─── Cached loaders ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_batter_list():
    return query("SELECT DISTINCT batter FROM matchups ORDER BY batter")["batter"].tolist()

@st.cache_data(ttl=3600)
def load_bowler_list():
    return query("SELECT DISTINCT bowler FROM matchups ORDER BY bowler")["bowler"].tolist()

@st.cache_data(ttl=3600)
def load_team_list():
    return query("""
        SELECT DISTINCT team FROM (
            SELECT team1 AS team FROM matches
            UNION
            SELECT team2 AS team FROM matches
        ) ORDER BY team
    """)["team"].tolist()

@st.cache_data(ttl=3600)
def load_matchup_summary(batter, bowler):
    return query(
        "SELECT * FROM matchups WHERE batter = ? AND bowler = ?",
        [batter, bowler],
    )

@st.cache_data(ttl=3600)
def load_matchup_balls(batter, bowler):
    return query(
        """
        SELECT b.*, m.season
        FROM balls b
        JOIN matches m ON b.match_id = m.match_id
        WHERE b.batter = ? AND b.bowler = ?
        ORDER BY m.date
        """,
        [batter, bowler],
    )

@st.cache_data(ttl=3600)
def load_matchup_dismissals(batter, bowler):
    return query(
        """
        SELECT m.date, m.season, m.venue, b.wicket_kind, b.innings,
               b.batting_team, b.bowling_team, m.match_won_by
        FROM balls b
        JOIN matches m ON b.match_id = m.match_id
        WHERE b.batter = ? AND b.bowler = ? AND b.player_out = ?
        ORDER BY m.date
        """,
        [batter, bowler, batter],
    )

@st.cache_data(ttl=3600)
def load_h2h_matches(team_a, team_b):
    return query(
        """
        SELECT match_id, date, season, venue, city,
               team1, team1_score, team1_wickets,
               team2, team2_score, team2_wickets,
               match_won_by, toss_winner, toss_decision,
               win_margin_value, win_margin_type, stage
        FROM matches
        WHERE (team1 = ? AND team2 = ?) OR (team1 = ? AND team2 = ?)
        ORDER BY date
        """,
        [team_a, team_b, team_b, team_a],
    )

@st.cache_data(ttl=3600)
def load_top_run_scorers(team_a, team_b, limit=10):
    return query(
        """
        SELECT pb.batter AS player, pb.batting_team AS team,
               COUNT(DISTINCT pb.match_id) AS matches,
               SUM(pb.runs) AS runs,
               SUM(pb.balls) AS balls,
               SUM(pb.fours) AS fours,
               SUM(pb.sixes) AS sixes,
               ROUND(SUM(pb.runs) * 100.0 / NULLIF(SUM(pb.balls), 0), 1) AS strike_rate
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE ((m.team1 = ? AND m.team2 = ?) OR (m.team1 = ? AND m.team2 = ?))
        GROUP BY pb.batter, pb.batting_team
        ORDER BY runs DESC
        LIMIT ?
        """,
        [team_a, team_b, team_b, team_a, limit],
    )

@st.cache_data(ttl=3600)
def load_top_wicket_takers(team_a, team_b, limit=10):
    return query(
        """
        SELECT b.bowler AS player, b.bowling_team AS team,
               COUNT(DISTINCT b.match_id) AS matches,
               COUNT(CASE WHEN b.wicket_kind IS NOT NULL
                         AND b.wicket_kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
                    THEN 1 END) AS wickets,
               SUM(b.runs_batter) AS runs_conceded,
               SUM(CASE WHEN b.valid_ball = 1 THEN 1 ELSE 0 END) AS balls_bowled,
               ROUND(SUM(b.runs_batter) * 6.0 / NULLIF(SUM(CASE WHEN b.valid_ball = 1 THEN 1 ELSE 0 END), 0), 2) AS economy
        FROM balls b
        JOIN matches m ON b.match_id = m.match_id
        WHERE ((m.team1 = ? AND m.team2 = ?) OR (m.team1 = ? AND m.team2 = ?))
        GROUP BY b.bowler, b.bowling_team
        HAVING wickets > 0
        ORDER BY wickets DESC
        LIMIT ?
        """,
        [team_a, team_b, team_b, team_a, limit],
    )


# ─── Mode selector ───────────────────────────────────────────────────────────

mode = st.radio("Select Mode", ["Batter vs Bowler", "Team vs Team"],
                horizontal=True, label_visibility="collapsed")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# MODE 1: BATTER vs BOWLER
# ═══════════════════════════════════════════════════════════════════════════════

if mode == "Batter vs Bowler":
    col_bat, col_bowl = st.columns(2)
    batters = load_batter_list()
    bowlers = load_bowler_list()

    with col_bat:
        batter = st.selectbox("Select Batter", batters,
                              index=batters.index("V Kohli") if "V Kohli" in batters else 0)
    with col_bowl:
        bowler = st.selectbox("Select Bowler", bowlers,
                              index=bowlers.index("JJ Bumrah") if "JJ Bumrah" in bowlers else 0)

    if batter and bowler:
        summary_df = load_matchup_summary(batter, bowler)

        if summary_df.empty:
            st.warning(f"No matchup data found between **{batter}** and **{bowler}**.")
            st.stop()

        row = summary_df.iloc[0]
        balls_count = int(row["balls"])
        runs_scored = int(row["runs"])
        dismissals = int(row["dismissals"])
        sr = row.get("strike_rate")
        avg = row.get("average")
        dot_pct = row.get("dot_pct")
        boundary_pct = row.get("boundary_pct")

        # ── Matchup Summary card ──
        st.subheader(f"{batter} vs {bowler}")

        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        c1.metric("Balls", format_number(balls_count))
        c2.metric("Runs", format_number(runs_scored))
        c3.metric("Dismissals", format_number(dismissals))
        c4.metric("Strike Rate", format_strike_rate(sr))
        c5.metric("Average", format_average(avg))
        c6.metric("Dot %", f"{dot_pct:.1f}%" if dot_pct is not None else "N/A")
        c7.metric("Boundary %", f"{boundary_pct:.1f}%" if boundary_pct is not None else "N/A")

        # ── Verdict badge ──
        balls_per_dismissal = balls_count / dismissals if dismissals > 0 else float("inf")
        if sr is not None and sr > 140 and balls_per_dismissal > 30:
            verdict = "Batter Dominates"
            verdict_color = "#4ECDC4"
        elif sr is not None and sr < 110 and balls_per_dismissal < 20:
            verdict = "Bowler Dominates"
            verdict_color = "#FF6B6B"
        else:
            verdict = "Even Contest"
            verdict_color = "#FFEAA7"

        st.markdown(
            f'<div style="text-align:center; margin:12px 0;">'
            f'<span style="background:{verdict_color}; color:#1A1D23; padding:8px 24px; '
            f'border-radius:20px; font-weight:700; font-size:1.1rem;">{verdict}</span></div>',
            unsafe_allow_html=True,
        )

        # ── Load ball-by-ball data ──
        balls_df = load_matchup_balls(batter, bowler)

        if not balls_df.empty:
            st.divider()

            # ── Run scoring breakdown ──
            st.subheader("Run Scoring Breakdown")
            run_counts = balls_df[balls_df["valid_ball"] == 1]["runs_batter"].value_counts().sort_index()
            run_labels = {0: "Dots", 1: "Singles", 2: "Twos", 3: "Threes", 4: "Fours", 6: "Sixes"}
            breakdown_df = pd.DataFrame({
                "Runs": [run_labels.get(r, f"{r}s") for r in run_counts.index],
                "Count": run_counts.values,
            })

            colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD"]
            fig = go.Figure(go.Bar(
                x=breakdown_df["Runs"], y=breakdown_df["Count"],
                marker_color=colors[:len(breakdown_df)],
                text=breakdown_df["Count"], textposition="outside",
            ))
            fig.update_layout(title="Runs Scored per Ball", xaxis_title="", yaxis_title="Count")
            st.plotly_chart(apply_ipl_style(fig, height=380, show_legend=False), width='stretch')

            st.divider()

            # ── Phase-wise breakdown ──
            st.subheader("Phase-wise Breakdown")
            phase_df = balls_df[balls_df["valid_ball"] == 1].copy()
            if "match_phase" in phase_df.columns and not phase_df["match_phase"].isna().all():
                phase_stats = phase_df.groupby("match_phase").agg(
                    Balls=("runs_batter", "count"),
                    Runs=("runs_batter", "sum"),
                    Dismissals=("wicket_kind", lambda x: x.notna().sum()),
                ).reset_index()
                phase_stats.rename(columns={"match_phase": "Phase"}, inplace=True)
                phase_stats["SR"] = (phase_stats["Runs"] * 100.0 / phase_stats["Balls"]).round(1)
                phase_order = {"powerplay": 0, "Powerplay": 0, "middle": 1, "Middle": 1, "death": 2, "Death": 2}
                phase_stats["_order"] = phase_stats["Phase"].map(phase_order).fillna(9)
                phase_stats = phase_stats.sort_values("_order").drop(columns=["_order"])
                phase_stats["Phase"] = phase_stats["Phase"].str.capitalize()
                st.dataframe(phase_stats[["Phase", "Balls", "Runs", "SR", "Dismissals"]],
                             width='stretch', hide_index=True)
            else:
                st.info("Phase data not available for this matchup.")

            st.divider()

            # ── Season-wise trend ──
            st.subheader("Season-wise Trend")
            valid_balls = balls_df[balls_df["valid_ball"] == 1].copy()
            season_stats = valid_balls.groupby("season").agg(
                Balls=("runs_batter", "count"),
                Runs=("runs_batter", "sum"),
                Dismissals=("wicket_kind", lambda x: x.notna().sum()),
            ).reset_index()
            season_stats.rename(columns={"season": "Season"}, inplace=True)
            season_stats["SR"] = (season_stats["Runs"] * 100.0 / season_stats["Balls"]).round(1)
            season_stats = season_stats.sort_values("Season")
            st.dataframe(season_stats[["Season", "Balls", "Runs", "SR", "Dismissals"]],
                         width='stretch', hide_index=True)

        # ── Dismissal details ──
        dismissals_df = load_matchup_dismissals(batter, bowler)
        if not dismissals_df.empty:
            st.divider()
            st.subheader("Dismissal Details")
            disp = dismissals_df.copy()
            disp["date"] = pd.to_datetime(disp["date"]).dt.strftime("%d %b %Y")
            disp.rename(columns={
                "date": "Date", "season": "Season", "venue": "Venue",
                "wicket_kind": "Dismissal Type", "innings": "Inn",
                "batting_team": "Batting Team", "match_won_by": "Match Winner",
            }, inplace=True)
            st.dataframe(
                disp[["Date", "Season", "Venue", "Dismissal Type", "Inn", "Batting Team", "Match Winner"]],
                width='stretch', hide_index=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# MODE 2: TEAM vs TEAM
# ═══════════════════════════════════════════════════════════════════════════════

else:
    teams = load_team_list()
    col_a, col_b = st.columns(2)
    with col_a:
        team_a = st.selectbox("Select Team A", teams,
                              index=teams.index("Chennai Super Kings") if "Chennai Super Kings" in teams else 0)
    with col_b:
        remaining = [t for t in teams if t != team_a]
        team_b = st.selectbox("Select Team B", remaining,
                              index=remaining.index("Mumbai Indians") if "Mumbai Indians" in remaining else 0)

    if team_a and team_b:
        h2h_df = load_h2h_matches(team_a, team_b)

        if h2h_df.empty:
            st.warning(f"No matches found between **{team_a}** and **{team_b}**.")
            st.stop()

        total_matches = len(h2h_df)
        a_wins = int((h2h_df["match_won_by"] == team_a).sum())
        b_wins = int((h2h_df["match_won_by"] == team_b).sum())
        no_results = total_matches - a_wins - b_wins

        # ── Rivalry Summary ──
        st.subheader(f"{team_a} vs {team_b}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Matches", format_number(total_matches))
        m2.metric(f"{team_a} Wins", format_number(a_wins))
        m3.metric(f"{team_b} Wins", format_number(b_wins))
        m4.metric("No Result / Tied", format_number(no_results))

        st.divider()

        # ── Win % Donut + Cumulative wins chart ──
        chart_left, chart_right = st.columns(2)

        with chart_left:
            st.subheader("Win Distribution")
            win_data = pd.DataFrame({
                "Team": [team_a, team_b] + (["No Result"] if no_results > 0 else []),
                "Wins": [a_wins, b_wins] + ([no_results] if no_results > 0 else []),
            })
            color_map = {
                team_a: get_team_color(team_a),
                team_b: get_team_color(team_b),
                "No Result": "#888888",
            }
            fig = px.pie(win_data, names="Team", values="Wins", hole=0.45,
                         color="Team", color_discrete_map=color_map)
            fig.update_traces(textinfo="percent+label+value", textfont_size=12)
            st.plotly_chart(apply_ipl_style(fig, height=400, show_legend=False),
                           width='stretch')

        with chart_right:
            st.subheader("Cumulative Wins Over Time")
            cum_df = h2h_df[["date", "match_won_by"]].copy()
            cum_df["date"] = pd.to_datetime(cum_df["date"])
            cum_df[team_a] = (cum_df["match_won_by"] == team_a).cumsum()
            cum_df[team_b] = (cum_df["match_won_by"] == team_b).cumsum()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=cum_df["date"], y=cum_df[team_a], name=team_a,
                mode="lines+markers", marker=dict(size=5),
                line=dict(color=get_team_color(team_a), width=3),
            ))
            fig.add_trace(go.Scatter(
                x=cum_df["date"], y=cum_df[team_b], name=team_b,
                mode="lines+markers", marker=dict(size=5),
                line=dict(color=get_team_color(team_b), width=3),
            ))
            fig.update_layout(title="", xaxis_title="", yaxis_title="Cumulative Wins")
            st.plotly_chart(apply_ipl_style(fig, height=400), width='stretch')

        st.divider()

        # ── Season-by-season results ──
        st.subheader("Season-by-Season Results")
        season_h2h = h2h_df.groupby("season").agg(
            Matches=("match_id", "count"),
            **{f"{team_a} Wins": ("match_won_by", lambda x: (x == team_a).sum())},
            **{f"{team_b} Wins": ("match_won_by", lambda x: (x == team_b).sum())},
        ).reset_index()
        season_h2h.rename(columns={"season": "Season"}, inplace=True)
        season_h2h = season_h2h.sort_values("Season")

        # Build a scores summary per season
        score_summaries = []
        for _, match in h2h_df.iterrows():
            t1s = f"{match['team1']} {int(match['team1_score']) if pd.notna(match['team1_score']) else '?'}/{int(match['team1_wickets']) if pd.notna(match['team1_wickets']) else '?'}"
            t2s = f"{match['team2']} {int(match['team2_score']) if pd.notna(match['team2_score']) else '?'}/{int(match['team2_wickets']) if pd.notna(match['team2_wickets']) else '?'}"
            score_summaries.append({
                "season": match["season"],
                "score": f"{t1s} vs {t2s}",
            })
        scores_df = pd.DataFrame(score_summaries)
        scores_by_season = scores_df.groupby("season")["score"].apply(lambda x: " | ".join(x)).reset_index()
        scores_by_season.rename(columns={"season": "Season", "score": "Scores"}, inplace=True)

        season_display = season_h2h.merge(scores_by_season, on="Season", how="left")
        st.dataframe(season_display, width='stretch', hide_index=True)

        st.divider()

        # ── Venue-wise H2H ──
        st.subheader("Venue-wise Record")
        venue_h2h = h2h_df.groupby("venue").agg(
            Matches=("match_id", "count"),
            **{f"{team_a} Wins": ("match_won_by", lambda x: (x == team_a).sum())},
            **{f"{team_b} Wins": ("match_won_by", lambda x: (x == team_b).sum())},
        ).reset_index()
        venue_h2h.rename(columns={"venue": "Venue"}, inplace=True)
        venue_h2h = venue_h2h.sort_values("Matches", ascending=False)
        st.dataframe(venue_h2h, width='stretch', hide_index=True)

        st.divider()

        # ── Toss impact ──
        st.subheader("Toss Impact")
        toss_a = h2h_df[h2h_df["toss_winner"] == team_a]
        toss_b = h2h_df[h2h_df["toss_winner"] == team_b]

        toss_a_matches = len(toss_a)
        toss_b_matches = len(toss_b)
        toss_a_wins = int((toss_a["match_won_by"] == team_a).sum()) if toss_a_matches > 0 else 0
        toss_b_wins = int((toss_b["match_won_by"] == team_b).sum()) if toss_b_matches > 0 else 0
        toss_a_pct = round(toss_a_wins * 100.0 / toss_a_matches, 1) if toss_a_matches > 0 else 0
        toss_b_pct = round(toss_b_wins * 100.0 / toss_b_matches, 1) if toss_b_matches > 0 else 0

        t1, t2 = st.columns(2)
        t1.metric(f"{team_a} win % when winning toss",
                  f"{toss_a_pct}%",
                  delta=f"{toss_a_wins}/{toss_a_matches} matches")
        t2.metric(f"{team_b} win % when winning toss",
                  f"{toss_b_pct}%",
                  delta=f"{toss_b_wins}/{toss_b_matches} matches")

        st.divider()

        # ── Top performers ──
        st.subheader("Top Performers in this Rivalry")
        perf_left, perf_right = st.columns(2)

        with perf_left:
            st.markdown("**Top Run Scorers**")
            top_bat = load_top_run_scorers(team_a, team_b)
            if not top_bat.empty:
                top_bat_display = top_bat.rename(columns={
                    "player": "Player", "team": "Team", "matches": "Mat",
                    "runs": "Runs", "balls": "Balls", "fours": "4s",
                    "sixes": "6s", "strike_rate": "SR",
                })
                st.dataframe(top_bat_display, width='stretch', hide_index=True)
            else:
                st.info("No batting data available.")

        with perf_right:
            st.markdown("**Top Wicket Takers**")
            top_bowl = load_top_wicket_takers(team_a, team_b)
            if not top_bowl.empty:
                top_bowl_display = top_bowl.rename(columns={
                    "player": "Player", "team": "Team", "matches": "Mat",
                    "wickets": "Wkts", "runs_conceded": "Runs",
                    "balls_bowled": "Balls", "economy": "Econ",
                })
                st.dataframe(top_bowl_display, width='stretch', hide_index=True)
            else:
                st.info("No bowling data available.")

        st.divider()

        # ── Scoring patterns ──
        st.subheader("Scoring Patterns")

        # Compute first innings (target) and second innings (chase) stats
        first_inn = h2h_df.copy()
        # team1 always bats first in this dataset structure
        first_inn["target"] = first_inn["team1_score"]
        second_inn_scores = first_inn["team2_score"]

        avg_target = first_inn["team1_score"].mean()
        successful_chases = 0
        total_chases = 0
        for _, m in h2h_df.iterrows():
            if pd.notna(m["team1_score"]) and pd.notna(m["team2_score"]):
                total_chases += 1
                # team2 chases; they win if match_won_by == team2
                if m["match_won_by"] == m["team2"]:
                    successful_chases += 1

        chase_success = round(successful_chases * 100.0 / total_chases, 1) if total_chases > 0 else 0

        sp1, sp2 = st.columns(2)
        sp1.metric("Avg 1st Innings Score", format_number(round(avg_target)) if pd.notna(avg_target) else "N/A")
        sp2.metric("Chase Success Rate", f"{chase_success}%",
                   delta=f"{successful_chases}/{total_chases} chases won")

        st.divider()

        # ── Close matches ──
        st.subheader("Close Matches")
        st.caption("Matches decided by ≤10 runs or ≤2 wickets")

        close = h2h_df[
            ((h2h_df["win_margin_type"] == "runs") & (h2h_df["win_margin_value"] <= 10)) |
            ((h2h_df["win_margin_type"] == "wickets") & (h2h_df["win_margin_value"] <= 2))
        ].copy()

        if not close.empty:
            close_display = close.copy()
            close_display["date"] = pd.to_datetime(close_display["date"]).dt.strftime("%d %b %Y")
            close_display["Margin"] = close_display.apply(
                lambda r: f"{int(r['win_margin_value'])} {r['win_margin_type']}"
                if pd.notna(r["win_margin_value"]) else "N/A", axis=1
            )
            close_display["Score"] = close_display.apply(
                lambda r: (
                    f"{r['team1']} {int(r['team1_score']) if pd.notna(r['team1_score']) else '?'}"
                    f"/{int(r['team1_wickets']) if pd.notna(r['team1_wickets']) else '?'} vs "
                    f"{r['team2']} {int(r['team2_score']) if pd.notna(r['team2_score']) else '?'}"
                    f"/{int(r['team2_wickets']) if pd.notna(r['team2_wickets']) else '?'}"
                ), axis=1
            )
            close_display.rename(columns={
                "date": "Date", "season": "Season", "venue": "Venue",
                "match_won_by": "Winner", "stage": "Stage",
            }, inplace=True)
            st.dataframe(
                close_display[["Date", "Season", "Venue", "Score", "Winner", "Margin", "Stage"]],
                width='stretch', hide_index=True,
            )
        else:
            st.info("No close matches found in this rivalry.")
