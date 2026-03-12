"""
Season Hub — Complete story of a single IPL season.

Points table, team performance, batting & bowling leaders, and match analysis
all scoped to a single chosen season.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style, styled_bar, styled_line, styled_pie,
    get_team_color, get_team_colors_list, big_number_style, IPL_COLORWAY,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS, STAGE_ORDER
from src.utils.formatters import (
    format_number, format_strike_rate, format_economy,
    format_average, format_overs,
)

# ── Cached data loaders ────────────────────────────────────────────


@st.cache_data(ttl=3600)
def _season_meta(season: int) -> pd.DataFrame:
    return query("SELECT * FROM season_meta WHERE season = ?", [season])


@st.cache_data(ttl=3600)
def _points_table(season: int) -> pd.DataFrame:
    return query(
        """
        SELECT position, team, played, won, lost, nr, points,
               ROUND(nrr, 3) AS nrr
        FROM   points_table
        WHERE  season = ?
        ORDER  BY position
        """,
        [season],
    )


@st.cache_data(ttl=3600)
def _season_progression(season: int) -> pd.DataFrame:
    return query(
        """
        WITH team_matches AS (
            SELECT date, match_id, team1 AS team,
                   CASE WHEN match_won_by = team1 THEN 1 ELSE 0 END AS won
            FROM   matches WHERE season = ?
            UNION ALL
            SELECT date, match_id, team2 AS team,
                   CASE WHEN match_won_by = team2 THEN 1 ELSE 0 END AS won
            FROM   matches WHERE season = ?
        ),
        numbered AS (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY team
                                      ORDER BY date, match_id) AS match_num
            FROM   team_matches
        )
        SELECT team, match_num,
               SUM(won) OVER (PARTITION BY team
                              ORDER BY match_num) AS cum_wins
        FROM   numbered
        ORDER  BY team, match_num
        """,
        [season, season],
    )


@st.cache_data(ttl=3600)
def _team_performance(season: int) -> pd.DataFrame:
    return query(
        """
        SELECT team, wins, losses, no_results, matches_played,
               ROUND(win_pct, 1) AS win_pct
        FROM   team_season
        WHERE  season = ?
        ORDER  BY wins DESC, win_pct DESC
        """,
        [season],
    )


@st.cache_data(ttl=3600)
def _team_scoring(season: int) -> pd.DataFrame:
    return query(
        """
        SELECT team,
               ROUND(AVG(scored),   1) AS avg_scored,
               ROUND(AVG(conceded), 1) AS avg_conceded
        FROM (
            SELECT team1 AS team, team1_score AS scored,
                   team2_score AS conceded
            FROM   matches WHERE season = ?
            UNION ALL
            SELECT team2 AS team, team2_score AS scored,
                   team1_score AS conceded
            FROM   matches WHERE season = ?
        ) t
        GROUP BY team
        ORDER BY avg_scored DESC
        """,
        [season, season],
    )


@st.cache_data(ttl=3600)
def _top_run_scorers(season: int, limit: int = 10) -> pd.DataFrame:
    return query(
        """
        SELECT batter,
               COUNT(*)        AS innings,
               SUM(runs)       AS total_runs,
               SUM(balls)      AS total_balls,
               ROUND(SUM(runs) * 1.0
                     / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0),
                     2) AS average,
               ROUND(SUM(runs) * 100.0
                     / NULLIF(SUM(balls), 0), 2) AS strike_rate,
               SUM(CASE WHEN is_fifty   THEN 1 ELSE 0 END) AS fifties,
               SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END) AS hundreds,
               SUM(fours) AS fours,
               SUM(sixes) AS sixes
        FROM   player_batting
        WHERE  season = ?
        GROUP  BY batter
        ORDER  BY total_runs DESC
        LIMIT  ?
        """,
        [season, limit],
    )


@st.cache_data(ttl=3600)
def _top_six_hitters(season: int, limit: int = 10) -> pd.DataFrame:
    return query(
        """
        SELECT batter,
               SUM(sixes) AS total_sixes,
               SUM(runs)  AS total_runs
        FROM   player_batting
        WHERE  season = ?
        GROUP  BY batter
        ORDER  BY total_sixes DESC
        LIMIT  ?
        """,
        [season, limit],
    )


@st.cache_data(ttl=3600)
def _top_strike_rates(
    season: int, min_balls: int = 100, limit: int = 10
) -> pd.DataFrame:
    return query(
        """
        SELECT batter,
               COUNT(*)    AS innings,
               SUM(runs)   AS total_runs,
               SUM(balls)  AS total_balls,
               ROUND(SUM(runs) * 100.0 / SUM(balls), 2) AS strike_rate,
               SUM(fours)  AS fours,
               SUM(sixes)  AS sixes
        FROM   player_batting
        WHERE  season = ?
        GROUP  BY batter
        HAVING SUM(balls) >= ?
        ORDER  BY strike_rate DESC
        LIMIT  ?
        """,
        [season, min_balls, limit],
    )


@st.cache_data(ttl=3600)
def _top_wicket_takers(season: int, limit: int = 10) -> pd.DataFrame:
    return query(
        """
        SELECT bowler,
               COUNT(*)             AS innings,
               SUM(balls_bowled)    AS total_balls,
               SUM(wickets)         AS total_wickets,
               SUM(runs_conceded)   AS total_runs,
               SUM(maidens)         AS maidens,
               ROUND(SUM(runs_conceded) * 6.0
                     / NULLIF(SUM(balls_bowled), 0), 2) AS economy,
               ROUND(SUM(balls_bowled) * 1.0
                     / NULLIF(SUM(wickets), 0), 1)      AS bowling_sr,
               SUM(dots_bowled) AS dots
        FROM   player_bowling
        WHERE  season = ?
        GROUP  BY bowler
        ORDER  BY total_wickets DESC
        LIMIT  ?
        """,
        [season, limit],
    )


@st.cache_data(ttl=3600)
def _top_economy(
    season: int, min_balls: int = 50, limit: int = 10
) -> pd.DataFrame:
    return query(
        """
        SELECT bowler,
               COUNT(*)           AS innings,
               SUM(balls_bowled)  AS total_balls,
               SUM(wickets)       AS total_wickets,
               SUM(runs_conceded) AS total_runs,
               SUM(maidens)       AS maidens,
               ROUND(SUM(runs_conceded) * 6.0
                     / SUM(balls_bowled), 2) AS economy
        FROM   player_bowling
        WHERE  season = ?
        GROUP  BY bowler
        HAVING SUM(balls_bowled) >= ?
        ORDER  BY economy ASC
        LIMIT  ?
        """,
        [season, min_balls, limit],
    )


@st.cache_data(ttl=3600)
def _best_bowling_figures(season: int) -> pd.DataFrame:
    return query(
        """
        SELECT bowler, bowling_team,
               wickets, runs_conceded, balls_bowled,
               ROUND(economy, 2) AS economy
        FROM   player_bowling
        WHERE  season = ? AND wickets >= 3
        ORDER  BY wickets DESC, runs_conceded ASC
        LIMIT  15
        """,
        [season],
    )


@st.cache_data(ttl=3600)
def _toss_analysis(season: int) -> pd.DataFrame:
    return query(
        """
        SELECT toss_decision, COUNT(*) AS count
        FROM   matches
        WHERE  season = ?
        GROUP  BY toss_decision
        """,
        [season],
    )


@st.cache_data(ttl=3600)
def _batting_first_stats(season: int) -> pd.DataFrame:
    return query(
        """
        SELECT
            SUM(CASE WHEN batting_first_won     THEN 1 ELSE 0 END) AS bat_first_wins,
            SUM(CASE WHEN NOT batting_first_won THEN 1 ELSE 0 END) AS chase_wins,
            COUNT(*) AS total
        FROM   matches
        WHERE  season = ?
          AND  match_won_by IS NOT NULL
          AND  match_won_by != ''
        """,
        [season],
    )


@st.cache_data(ttl=3600)
def _avg_score_progression(season: int) -> pd.DataFrame:
    return query(
        """
        WITH numbered AS (
            SELECT *,
                   ROW_NUMBER() OVER (ORDER BY date, match_id) AS match_num
            FROM   matches
            WHERE  season = ?
        )
        SELECT match_num,
               ROUND((COALESCE(team1_score, 0)
                    + COALESCE(team2_score, 0)) / 2.0, 1) AS avg_score,
               ROUND(
                 AVG((COALESCE(team1_score, 0)
                    + COALESCE(team2_score, 0)) / 2.0)
                 OVER (ORDER BY match_num
                       ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
               1) AS rolling_avg
        FROM   numbered
        ORDER  BY match_num
        """,
        [season],
    )


# ── Page chrome ────────────────────────────────────────────────────

st.markdown(big_number_style(), unsafe_allow_html=True)
st.title("Season Hub")
st.caption(
    "The complete story of a single IPL season — standings, stars, and storylines"
)

# Season selector at top of page
sel_col, _ = st.columns([1, 3])
with sel_col:
    selected_season = st.selectbox(
        "Select Season",
        options=ALL_SEASONS,
        index=len(ALL_SEASONS) - 1,
        key="season_hub_selector",
    )

# ── Season Identity Card ──────────────────────────────────────────

meta_df = _season_meta(selected_season)
if meta_df.empty:
    st.warning(f"No data available for IPL {selected_season}.")
    st.stop()

m = meta_df.iloc[0].to_dict()

# Count super-over matches from the source table (meta only stores boolean)
_so = query(
    "SELECT COUNT(*) AS cnt FROM matches WHERE season = ? AND is_super_over_match",
    [selected_season],
)
super_over_count = int(_so.iloc[0]["cnt"]) if not _so.empty else 0

st.subheader(f"IPL {selected_season}")
id_row1 = st.columns(3)
id_row1[0].metric("Total Matches", format_number(int(m.get("total_matches", 0))))
id_row1[1].metric("Teams", int(m.get("num_teams", 0)))
id_row1[2].metric("Champion", str(m.get("champion", "—")) or "—")

id_row2 = st.columns(3)
id_row2[0].metric("Duration", f"{int(m.get('duration_days', 0))} days")
id_row2[1].metric("Super Overs", super_over_count)
id_row2[2].metric("DLS Matches", int(m.get("dls_matches", 0)))

dt1, dt2 = st.columns(2)
dt1.caption(f"Start: **{m.get('start_date', '—')}**")
dt2.caption(f"End: **{m.get('end_date', '—')}**")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────

tab_pts, tab_team, tab_bat, tab_bowl, tab_match = st.tabs(
    [
        "Points Table",
        "Team Performance",
        "Batting Leaders",
        "Bowling Leaders",
        "Match Analysis",
    ]
)

# ── Points Table Tab ──────────────────────────────────────────────

with tab_pts:
    pts = _points_table(selected_season)
    if pts.empty:
        st.info("Points table data not available for this season.")
    else:
        st.subheader("League Standings")

        display_pts = pts.rename(
            columns={
                "position": "Pos",
                "team": "Team",
                "played": "P",
                "won": "W",
                "lost": "L",
                "nr": "NR",
                "points": "Pts",
                "nrr": "NRR",
            }
        )

        def _highlight_qualifiers(row):
            css = "background-color: rgba(76, 175, 80, 0.15)"
            return [css if row["Pos"] <= 4 else ""] * len(row)

        styled_pts = (
            display_pts.style
            .apply(_highlight_qualifiers, axis=1)
            .format({"NRR": lambda v: f"{v:+.3f}" if pd.notna(v) else "—"})
        )
        st.dataframe(
            styled_pts, width='stretch', hide_index=True, height=420
        )
        st.caption("Top 4 teams qualify for the playoffs")

    # Bump chart – cumulative wins
    progression = _season_progression(selected_season)
    if not progression.empty:
        st.subheader("Season Progression — Cumulative Wins by Match")

        fig = go.Figure()
        for team in sorted(progression["team"].unique()):
            td = progression[progression["team"] == team]
            fig.add_trace(
                go.Scatter(
                    x=td["match_num"],
                    y=td["cum_wins"],
                    mode="lines+markers",
                    name=team,
                    line=dict(color=get_team_color(team), width=2.5),
                    marker=dict(size=4),
                    hovertemplate=(
                        f"<b>{team}</b><br>"
                        "Match %{x}<br>Wins: %{y}<extra></extra>"
                    ),
                )
            )

        fig = apply_ipl_style(fig, height=500)
        fig.update_layout(
            xaxis_title="Team's Match Number",
            yaxis_title="Cumulative Wins",
            hovermode="closest",
        )
        st.plotly_chart(fig, width='stretch')

# ── Team Performance Tab ──────────────────────────────────────────

with tab_team:
    team_perf = _team_performance(selected_season)
    team_score = _team_scoring(selected_season)

    left, right = st.columns(2)

    with left:
        st.subheader("Win-Loss Record")
        if not team_perf.empty:
            tp = team_perf.sort_values("wins", ascending=True)
            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    y=tp["team"],
                    x=tp["wins"],
                    name="Wins",
                    orientation="h",
                    marker_color="#4ECDC4",
                    text=tp["wins"],
                    textposition="inside",
                )
            )
            fig.add_trace(
                go.Bar(
                    y=tp["team"],
                    x=tp["losses"],
                    name="Losses",
                    orientation="h",
                    marker_color="#FF6B6B",
                    text=tp["losses"],
                    textposition="inside",
                )
            )
            if tp["no_results"].sum() > 0:
                fig.add_trace(
                    go.Bar(
                        y=tp["team"],
                        x=tp["no_results"],
                        name="No Result",
                        orientation="h",
                        marker_color="#888888",
                        text=tp["no_results"],
                        textposition="inside",
                    )
                )
            fig.update_layout(barmode="stack")
            fig = apply_ipl_style(fig, height=450)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Team performance data not available.")

    with right:
        st.subheader("Avg Scored vs Avg Conceded")
        if not team_score.empty:
            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=team_score["team"],
                    y=team_score["avg_scored"],
                    name="Avg Scored",
                    marker_color="#4ECDC4",
                    text=team_score["avg_scored"],
                    textposition="outside",
                )
            )
            fig.add_trace(
                go.Bar(
                    x=team_score["team"],
                    y=team_score["avg_conceded"],
                    name="Avg Conceded",
                    marker_color="#FF6B6B",
                    text=team_score["avg_conceded"],
                    textposition="outside",
                )
            )
            fig.update_layout(barmode="group", xaxis_tickangle=-45)
            fig = apply_ipl_style(fig, height=450)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Team scoring data not available.")

# ── Batting Leaders Tab ───────────────────────────────────────────

with tab_bat:
    top_scorers = _top_run_scorers(selected_season)

    if not top_scorers.empty:
        st.subheader("Top 10 Run Scorers")

        chart_df = top_scorers.sort_values("total_runs", ascending=True)
        fig = styled_bar(
            chart_df,
            x="batter",
            y="total_runs",
            title=f"Top Run Scorers — IPL {selected_season}",
            horizontal=True,
            height=400,
        )
        st.plotly_chart(fig, width='stretch')

        # Stats table
        disp = top_scorers[
            [
                "batter", "innings", "total_runs", "total_balls",
                "average", "strike_rate", "fifties", "hundreds",
            ]
        ].copy()
        disp.columns = ["Batter", "Inn", "Runs", "Balls", "Avg", "SR", "50s", "100s"]
        disp["Avg"] = disp["Avg"].apply(
            lambda v: format_average(v) if pd.notna(v) else "—"
        )
        disp["SR"] = disp["SR"].apply(
            lambda v: format_strike_rate(v) if pd.notna(v) else "—"
        )
        st.dataframe(disp, width='stretch', hide_index=True)
    else:
        st.info("Batting data not available for this season.")

    col_six, col_sr = st.columns(2)

    with col_six:
        st.subheader("Top Six Hitters")
        six_df = _top_six_hitters(selected_season)
        if not six_df.empty:
            chart_df = six_df.sort_values("total_sixes", ascending=True)
            fig = styled_bar(
                chart_df,
                x="batter",
                y="total_sixes",
                title="Most Sixes",
                horizontal=True,
                height=400,
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No data available.")

    with col_sr:
        st.subheader("Best Strike Rate (min 100 balls)")
        sr_df = _top_strike_rates(selected_season)
        if not sr_df.empty:
            disp = sr_df[
                [
                    "batter", "innings", "total_runs",
                    "total_balls", "strike_rate", "fours", "sixes",
                ]
            ].copy()
            disp.columns = ["Batter", "Inn", "Runs", "Balls", "SR", "4s", "6s"]
            disp["SR"] = disp["SR"].apply(
                lambda v: format_strike_rate(v) if pd.notna(v) else "—"
            )
            st.dataframe(disp, width='stretch', hide_index=True)
        else:
            st.info("No qualifying batters (min 100 balls).")

# ── Bowling Leaders Tab ───────────────────────────────────────────

with tab_bowl:
    top_bowlers = _top_wicket_takers(selected_season)

    if not top_bowlers.empty:
        st.subheader("Top 10 Wicket Takers")

        chart_df = top_bowlers.sort_values("total_wickets", ascending=True)
        fig = styled_bar(
            chart_df,
            x="bowler",
            y="total_wickets",
            title=f"Top Wicket Takers — IPL {selected_season}",
            horizontal=True,
            height=400,
        )
        st.plotly_chart(fig, width='stretch')

        disp = top_bowlers[
            [
                "bowler", "innings", "total_wickets", "total_balls",
                "total_runs", "economy", "bowling_sr", "maidens",
            ]
        ].copy()
        disp.columns = [
            "Bowler", "Inn", "Wkts", "Balls", "Runs", "Econ", "SR", "Maidens",
        ]
        disp.insert(
            3,
            "Overs",
            disp["Balls"].apply(
                lambda b: format_overs(int(b)) if pd.notna(b) else "—"
            ),
        )
        disp["Econ"] = disp["Econ"].apply(
            lambda v: format_economy(v) if pd.notna(v) else "—"
        )
        disp["SR"] = disp["SR"].apply(
            lambda v: format_strike_rate(v) if pd.notna(v) else "—"
        )
        disp = disp[
            ["Bowler", "Inn", "Wkts", "Overs", "Runs", "Econ", "SR", "Maidens"]
        ]
        st.dataframe(disp, width='stretch', hide_index=True)
    else:
        st.info("Bowling data not available for this season.")

    col_econ, col_fig = st.columns(2)

    with col_econ:
        st.subheader("Best Economy (min 50 balls)")
        econ_df = _top_economy(selected_season)
        if not econ_df.empty:
            disp = econ_df[
                [
                    "bowler", "innings", "total_balls", "total_wickets",
                    "total_runs", "economy", "maidens",
                ]
            ].copy()
            disp.columns = ["Bowler", "Inn", "Balls", "Wkts", "Runs", "Econ", "Maidens"]
            disp.insert(
                2,
                "Overs",
                disp["Balls"].apply(
                    lambda b: format_overs(int(b)) if pd.notna(b) else "—"
                ),
            )
            disp["Econ"] = disp["Econ"].apply(
                lambda v: format_economy(v) if pd.notna(v) else "—"
            )
            disp = disp[
                ["Bowler", "Inn", "Overs", "Wkts", "Runs", "Econ", "Maidens"]
            ]
            st.dataframe(disp, width='stretch', hide_index=True)
        else:
            st.info("No qualifying bowlers (min 50 balls).")

    with col_fig:
        st.subheader("Best Figures (3+ wickets)")
        bf_df = _best_bowling_figures(selected_season)
        if not bf_df.empty:
            disp = bf_df.copy()
            disp["Figures"] = (
                disp["wickets"].astype(int).astype(str)
                + "/"
                + disp["runs_conceded"].astype(int).astype(str)
            )
            disp["Overs"] = disp["balls_bowled"].apply(
                lambda b: format_overs(int(b)) if pd.notna(b) else "—"
            )
            disp["Econ"] = disp["economy"].apply(
                lambda v: format_economy(v) if pd.notna(v) else "—"
            )
            disp = disp.rename(
                columns={"bowler": "Bowler", "bowling_team": "Team"}
            )
            disp = disp[["Bowler", "Team", "Figures", "Overs", "Econ"]]
            st.dataframe(disp, width='stretch', hide_index=True)
        else:
            st.info("No 3+ wicket hauls this season.")

# ── Match Analysis Tab ────────────────────────────────────────────

with tab_match:
    col_toss, col_bf = st.columns([3, 2])

    with col_toss:
        st.subheader("Toss Decisions")
        toss = _toss_analysis(selected_season)
        if not toss.empty:
            fig = styled_pie(
                toss,
                names="toss_decision",
                values="count",
                title=f"Toss Decisions — IPL {selected_season}",
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Toss data not available.")

    with col_bf:
        st.subheader("Batting First vs Chasing")
        bf = _batting_first_stats(selected_season)
        if not bf.empty:
            row = bf.iloc[0]
            total = int(row["total"])
            bf_wins = int(row["bat_first_wins"])
            ch_wins = int(row["chase_wins"])

            if total > 0:
                bf_pct = round(bf_wins * 100 / total, 1)
                ch_pct = round(ch_wins * 100 / total, 1)

                m1, m2 = st.columns(2)
                m1.metric(
                    "Bat First Win %",
                    f"{bf_pct}%",
                    delta=f"{bf_wins}/{total}",
                )
                m2.metric(
                    "Chase Win %",
                    f"{ch_pct}%",
                    delta=f"{ch_wins}/{total}",
                )

                outcome = pd.DataFrame(
                    {
                        "outcome": ["Bat First Won", "Chasing Won"],
                        "count": [bf_wins, ch_wins],
                    }
                )
                fig = styled_pie(
                    outcome,
                    names="outcome",
                    values="count",
                    title="Wins by Innings",
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No decisive results recorded.")
        else:
            st.info("Match outcome data not available.")

    st.subheader("Average Score Progression")
    score_prog = _avg_score_progression(selected_season)
    if not score_prog.empty:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=score_prog["match_num"],
                y=score_prog["avg_score"],
                mode="markers",
                name="Match Avg",
                marker=dict(color="rgba(78, 205, 196, 0.5)", size=6),
                hovertemplate="Match %{x}<br>Avg: %{y}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=score_prog["match_num"],
                y=score_prog["rolling_avg"],
                mode="lines",
                name="5-Match Rolling Avg",
                line=dict(color="#FF6B6B", width=3),
                hovertemplate="Match %{x}<br>Rolling: %{y}<extra></extra>",
            )
        )
        fig = apply_ipl_style(fig, height=400)
        fig.update_layout(
            xaxis_title="Match Number (chronological)",
            yaxis_title="Average Score per Innings",
            hovermode="x unified",
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("Score progression data not available.")
