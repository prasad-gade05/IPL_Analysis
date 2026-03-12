"""
👥 Team Profile — Complete franchise analytics.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style,
    styled_bar,
    styled_line,
    styled_pie,
    get_team_color,
    big_number_style,
    IPL_COLORWAY,
    metric_card,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS
from src.utils.formatters import (
    format_number,
    format_strike_rate,
    format_economy,
    format_average,
)

st.set_page_config(
    page_title="Team Profile | IPL Analytics",
    page_icon="👥",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Cached query helpers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600)
def get_team_list():
    return query("SELECT DISTINCT team FROM team_season ORDER BY team")[
        "team"
    ].tolist()


@st.cache_data(ttl=3600)
def get_team_summary(team):
    return query(
        """
        SELECT
            SUM(matches_played)  AS total_matches,
            SUM(wins)            AS total_wins,
            ROUND(SUM(wins) * 100.0 / NULLIF(SUM(matches_played), 0), 1)
                                 AS overall_win_pct
        FROM team_season
        WHERE team = ?
        """,
        [team],
    )


@st.cache_data(ttl=3600)
def get_titles(team):
    return query(
        "SELECT COUNT(*) AS titles FROM season_meta WHERE champion = ?", [team]
    )


@st.cache_data(ttl=3600)
def get_finals_count(team):
    return query(
        """
        SELECT COUNT(*) AS finals
        FROM matches
        WHERE stage = 'Final' AND (team1 = ? OR team2 = ?)
        """,
        [team, team],
    )


@st.cache_data(ttl=3600)
def get_highest_team_score(team):
    return query(
        """
        SELECT MAX(score) AS highest
        FROM (
            SELECT team1_score AS score FROM matches
              WHERE team1 = ? AND team1_score IS NOT NULL
            UNION ALL
            SELECT team2_score AS score FROM matches
              WHERE team2 = ? AND team2_score IS NOT NULL
        )
        """,
        [team, team],
    )


# ---- Overview helpers ----


@st.cache_data(ttl=3600)
def get_season_record(team):
    return query(
        """
        SELECT season, matches_played, wins, losses, no_results, win_pct
        FROM team_season
        WHERE team = ?
        ORDER BY season
        """,
        [team],
    )


@st.cache_data(ttl=3600)
def get_stage_reached(team):
    return query(
        """
        SELECT season,
               CASE max_stage
                   WHEN 5 THEN '🏆 Champion'
                   WHEN 4 THEN 'Runner-up'
                   WHEN 3 THEN 'Playoff'
                   ELSE 'League'
               END AS stage_reached,
               max_stage
        FROM (
            SELECT season,
                   MAX(CASE
                       WHEN stage = 'Final' AND match_won_by = ? THEN 5
                       WHEN stage = 'Final' THEN 4
                       WHEN stage IN ('Qualifier 1','Qualifier 2',
                                      'Eliminator','Semi Final') THEN 3
                       ELSE 1
                   END) AS max_stage
            FROM matches
            WHERE (team1 = ? OR team2 = ?)
            GROUP BY season
        ) sub
        ORDER BY season
        """,
        [team, team, team],
    )


# ---- Batting helpers ----


@st.cache_data(ttl=3600)
def get_avg_team_score_by_season(team):
    return query(
        """
        SELECT season, ROUND(AVG(score), 1) AS avg_score
        FROM (
            SELECT season, team1_score AS score FROM matches
              WHERE team1 = ? AND team1_score IS NOT NULL
            UNION ALL
            SELECT season, team2_score AS score FROM matches
              WHERE team2 = ? AND team2_score IS NOT NULL
        )
        GROUP BY season
        ORDER BY season
        """,
        [team, team],
    )


@st.cache_data(ttl=3600)
def get_league_avg_score_by_season():
    return query(
        """
        SELECT season, ROUND(AVG(score), 1) AS avg_score
        FROM (
            SELECT season, team1_score AS score FROM matches
              WHERE team1_score IS NOT NULL
            UNION ALL
            SELECT season, team2_score AS score FROM matches
              WHERE team2_score IS NOT NULL
        )
        GROUP BY season
        ORDER BY season
        """
    )


@st.cache_data(ttl=3600)
def get_top_run_scorers(team, limit=10):
    return query(
        """
        SELECT batter,
               SUM(runs)                  AS total_runs,
               COUNT(DISTINCT match_id)   AS matches,
               SUM(fours)                 AS fours,
               SUM(sixes)                 AS sixes,
               MAX(runs)                  AS highest_score,
               ROUND(SUM(runs) * 100.0
                     / NULLIF(SUM(balls), 0), 1) AS strike_rate,
               ROUND(SUM(runs) * 1.0
                     / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0),
                     2) AS average
        FROM player_batting
        WHERE batting_team = ?
        GROUP BY batter
        ORDER BY total_runs DESC
        LIMIT ?
        """,
        [team, limit],
    )


@st.cache_data(ttl=3600)
def get_highest_team_totals(team, limit=10):
    return query(
        """
        SELECT score, wickets, season, opponent
        FROM (
            SELECT team1_score AS score, team1_wickets AS wickets,
                   season, team2 AS opponent
            FROM matches WHERE team1 = ? AND team1_score IS NOT NULL
            UNION ALL
            SELECT team2_score AS score, team2_wickets AS wickets,
                   season, team1 AS opponent
            FROM matches WHERE team2 = ? AND team2_score IS NOT NULL
        )
        ORDER BY score DESC
        LIMIT ?
        """,
        [team, team, limit],
    )


@st.cache_data(ttl=3600)
def get_lowest_team_totals(team, limit=10):
    return query(
        """
        SELECT score, wickets, season, opponent
        FROM (
            SELECT team1_score AS score, team1_wickets AS wickets,
                   season, team2 AS opponent
            FROM matches WHERE team1 = ? AND team1_score IS NOT NULL
            UNION ALL
            SELECT team2_score AS score, team2_wickets AS wickets,
                   season, team1 AS opponent
            FROM matches WHERE team2 = ? AND team2_score IS NOT NULL
        )
        ORDER BY score ASC
        LIMIT ?
        """,
        [team, team, limit],
    )


# ---- Bowling helpers ----


@st.cache_data(ttl=3600)
def get_avg_conceded_by_season(team):
    return query(
        """
        SELECT season, ROUND(AVG(conceded), 1) AS avg_conceded
        FROM (
            SELECT season, team2_score AS conceded FROM matches
              WHERE team1 = ? AND team2_score IS NOT NULL
            UNION ALL
            SELECT season, team1_score AS conceded FROM matches
              WHERE team2 = ? AND team1_score IS NOT NULL
        )
        GROUP BY season
        ORDER BY season
        """,
        [team, team],
    )


@st.cache_data(ttl=3600)
def get_top_wicket_takers(team, limit=10):
    return query(
        """
        SELECT bowler,
               SUM(wickets)               AS total_wickets,
               COUNT(DISTINCT match_id)   AS matches,
               ROUND(SUM(runs_conceded) * 6.0
                     / NULLIF(SUM(balls_bowled), 0), 2) AS economy,
               ROUND(SUM(balls_bowled) * 1.0
                     / NULLIF(SUM(wickets), 0), 1) AS bowling_sr
        FROM player_bowling
        WHERE bowling_team = ?
        GROUP BY bowler
        ORDER BY total_wickets DESC
        LIMIT ?
        """,
        [team, limit],
    )


@st.cache_data(ttl=3600)
def get_best_bowling_figures(team, limit=10):
    return query(
        """
        SELECT pb.bowler, pb.wickets, pb.runs_conceded,
               pb.balls_bowled, pb.economy, pb.season,
               CASE WHEN m.team1 = pb.bowling_team
                    THEN m.team2 ELSE m.team1
               END AS vs_team
        FROM player_bowling pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE pb.bowling_team = ?
        ORDER BY pb.wickets DESC, pb.runs_conceded ASC
        LIMIT ?
        """,
        [team, limit],
    )


# ---- Vs Teams helpers ----


@st.cache_data(ttl=3600)
def get_head_to_head(team):
    return query(
        """
        SELECT opponent                           AS vs_team,
               COUNT(*)                            AS played,
               SUM(CASE WHEN match_won_by = ?
                        THEN 1 ELSE 0 END)         AS won,
               SUM(CASE WHEN match_won_by IS NOT NULL
                             AND match_won_by != ?
                        THEN 1 ELSE 0 END)          AS lost,
               ROUND(SUM(CASE WHEN match_won_by = ?
                              THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)      AS win_pct
        FROM (
            SELECT CASE WHEN team1 = ? THEN team2 ELSE team1 END AS opponent,
                   match_won_by
            FROM matches
            WHERE (team1 = ? OR team2 = ?)
        ) sub
        GROUP BY opponent
        ORDER BY played DESC
        """,
        [team, team, team, team, team, team],
    )


# ---- Venues helpers ----


@st.cache_data(ttl=3600)
def get_venue_performance(team):
    return query(
        """
        SELECT venue,
               COUNT(*)                                     AS matches,
               SUM(CASE WHEN match_won_by = ?
                        THEN 1 ELSE 0 END)                  AS wins,
               SUM(CASE WHEN match_won_by IS NOT NULL
                             AND match_won_by != ?
                        THEN 1 ELSE 0 END)                   AS losses,
               ROUND(SUM(CASE WHEN match_won_by = ?
                              THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)               AS win_pct
        FROM matches
        WHERE (team1 = ? OR team2 = ?)
        GROUP BY venue
        HAVING COUNT(*) >= 3
        ORDER BY matches DESC
        """,
        [team, team, team, team, team],
    )


@st.cache_data(ttl=3600)
def get_home_away_winpct(team):
    return query(
        """
        WITH home_city AS (
            SELECT city
            FROM (
                SELECT city, COUNT(*) AS cnt
                FROM matches
                WHERE (team1 = ? OR team2 = ?) AND city IS NOT NULL
                GROUP BY city
                ORDER BY cnt DESC
                LIMIT 1
            )
        ),
        team_matches AS (
            SELECT
                CASE WHEN m.city = (SELECT city FROM home_city)
                     THEN 'Home' ELSE 'Away'
                END AS location,
                CASE WHEN m.match_won_by = ? THEN 1 ELSE 0 END AS won
            FROM matches m
            WHERE (m.team1 = ? OR m.team2 = ?)
              AND m.match_won_by IS NOT NULL
        )
        SELECT location,
               COUNT(*)                            AS matches,
               SUM(won)                             AS wins,
               ROUND(SUM(won) * 100.0 / COUNT(*), 1) AS win_pct
        FROM team_matches
        GROUP BY location
        """,
        [team, team, team, team, team],
    )


# ---- Toss & Chasing helpers ----


@st.cache_data(ttl=3600)
def get_toss_record(team):
    return query(
        """
        SELECT
            CASE WHEN toss_winner = ? THEN 'Won' ELSE 'Lost' END AS toss_result,
            COUNT(*) AS count
        FROM matches
        WHERE (team1 = ? OR team2 = ?)
          AND toss_winner IS NOT NULL
        GROUP BY toss_result
        """,
        [team, team, team],
    )


@st.cache_data(ttl=3600)
def get_toss_decision_trend(team):
    return query(
        """
        SELECT season,
               COUNT(*) AS toss_wins,
               ROUND(
                   SUM(CASE WHEN toss_decision = 'field'
                            THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1
               ) AS field_first_pct
        FROM matches
        WHERE toss_winner = ?
        GROUP BY season
        ORDER BY season
        """,
        [team],
    )


@st.cache_data(ttl=3600)
def get_bat_first_vs_chase_winpct(team):
    return query(
        """
        SELECT 'Batting First' AS scenario,
               COUNT(*)         AS matches,
               SUM(CASE WHEN match_won_by = ? THEN 1 ELSE 0 END) AS wins,
               ROUND(SUM(CASE WHEN match_won_by = ? THEN 1 ELSE 0 END)
                     * 100.0 / NULLIF(COUNT(*), 0), 1) AS win_pct
        FROM matches
        WHERE team1 = ? AND match_won_by IS NOT NULL
        UNION ALL
        SELECT 'Chasing' AS scenario,
               COUNT(*)   AS matches,
               SUM(CASE WHEN match_won_by = ? THEN 1 ELSE 0 END) AS wins,
               ROUND(SUM(CASE WHEN match_won_by = ? THEN 1 ELSE 0 END)
                     * 100.0 / NULLIF(COUNT(*), 0), 1) AS win_pct
        FROM matches
        WHERE team2 = ? AND match_won_by IS NOT NULL
        """,
        [team, team, team, team, team, team],
    )


@st.cache_data(ttl=3600)
def get_chase_success_by_target(team):
    return query(
        """
        SELECT target_range,
               COUNT(*)  AS total_chases,
               SUM(CASE WHEN match_won_by = ? THEN 1 ELSE 0 END) AS successful,
               ROUND(
                   SUM(CASE WHEN match_won_by = ? THEN 1 ELSE 0 END)
                   * 100.0 / NULLIF(COUNT(*), 0), 1
               ) AS success_pct
        FROM (
            SELECT match_id, match_won_by,
                   CASE
                       WHEN team1_score + 1 <  130 THEN '< 130'
                       WHEN team1_score + 1 <= 149  THEN '130-149'
                       WHEN team1_score + 1 <= 169  THEN '150-169'
                       WHEN team1_score + 1 <= 189  THEN '170-189'
                       WHEN team1_score + 1 <= 209  THEN '190-209'
                       ELSE '210+'
                   END AS target_range
            FROM matches
            WHERE team2 = ?
              AND team1_score IS NOT NULL
              AND match_won_by IS NOT NULL
        ) sub
        GROUP BY target_range
        ORDER BY CASE target_range
            WHEN '< 130'   THEN 1
            WHEN '130-149' THEN 2
            WHEN '150-169' THEN 3
            WHEN '170-189' THEN 4
            WHEN '190-209' THEN 5
            ELSE 6
        END
        """,
        [team, team, team],
    )


@st.cache_data(ttl=3600)
def get_highest_successful_chases(team, limit=5):
    return query(
        """
        SELECT team2_score       AS chase_score,
               team1_score       AS target_score,
               team1             AS opponent,
               season, venue,
               win_margin_value  AS margin
        FROM matches
        WHERE team2 = ? AND match_won_by = ?
          AND team2_score IS NOT NULL
        ORDER BY team2_score DESC
        LIMIT ?
        """,
        [team, team, limit],
    )


@st.cache_data(ttl=3600)
def get_lowest_totals_defended(team, limit=5):
    return query(
        """
        SELECT team1_score       AS defended_score,
               team2_score       AS opponent_score,
               team2             AS opponent,
               season, venue,
               win_margin_value  AS margin
        FROM matches
        WHERE team1 = ? AND match_won_by = ?
          AND team1_score IS NOT NULL
        ORDER BY team1_score ASC
        LIMIT ?
        """,
        [team, team, limit],
    )


# ---------------------------------------------------------------------------
# Page header & team selector
# ---------------------------------------------------------------------------

st.title("👥 Team Profile")
st.caption("Complete franchise analytics — performance, players & match-ups.")

teams = get_team_list()
if not teams:
    st.warning("No team data available. Please ensure the data pipeline has run.")
    st.stop()

selected_team = st.selectbox("Select Team", teams, key="team_selector")
team_color = get_team_color(selected_team)

st.divider()

# ---- Header with team color accent ----
st.markdown(
    f'<h2 style="color:{team_color}; margin-bottom:0;">{selected_team}</h2>',
    unsafe_allow_html=True,
)

# ---- Summary metric cards ----
summary = get_team_summary(selected_team)
titles_df = get_titles(selected_team)
finals_df = get_finals_count(selected_team)
highest_df = get_highest_team_score(selected_team)

if summary.empty:
    st.warning("No data found for this team.")
    st.stop()

s = summary.iloc[0]
titles = int(titles_df.iloc[0]["titles"]) if not titles_df.empty else 0
finals = int(finals_df.iloc[0]["finals"]) if not finals_df.empty else 0
highest = (
    int(highest_df.iloc[0]["highest"])
    if not highest_df.empty and pd.notna(highest_df.iloc[0]["highest"])
    else None
)

st.markdown(big_number_style(), unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.metric(**metric_card("Total Matches", format_number(s["total_matches"])))
with c2:
    st.metric(**metric_card("Wins", format_number(s["total_wins"])))
with c3:
    st.metric(**metric_card("Win %", f"{s['overall_win_pct']:.1f}%"))
with c4:
    st.metric(**metric_card("🏆 Titles", str(titles)))
with c5:
    st.metric(**metric_card("Finals", str(finals)))
with c6:
    st.metric(
        **metric_card(
            "Highest Score",
            format_number(highest) if highest is not None else "N/A",
        )
    )

st.divider()

# ===================================================================
# TABS
# ===================================================================

tab_overview, tab_batting, tab_bowling, tab_vs, tab_venues, tab_toss = st.tabs(
    [
        "📊 Overview",
        "🏏 Batting",
        "🎳 Bowling",
        "⚔️ vs Teams",
        "🏟️ Venues",
        "🪙 Toss & Chasing",
    ]
)

# -------------------------------------------------------------------
# OVERVIEW TAB
# -------------------------------------------------------------------
with tab_overview:
    season_df = get_season_record(selected_team)

    if season_df.empty:
        st.info("No season data available for this team.")
    else:
        # ---- Season wins/losses + Win % trend ----
        left, right = st.columns(2)

        with left:
            st.subheader("📊 Season Record")
            melted = season_df.melt(
                id_vars=["season"],
                value_vars=["wins", "losses"],
                var_name="Result",
                value_name="Count",
            )
            melted["Result"] = melted["Result"].map(
                {"wins": "Wins", "losses": "Losses"}
            )
            fig = styled_bar(
                melted,
                x="season",
                y="Count",
                title="Wins & Losses by Season",
                color="Result",
                color_map={"Wins": "#2ecc71", "Losses": "#e74c3c"},
            )
            fig.update_layout(
                barmode="group", xaxis_title="Season", yaxis_title="Matches"
            )
            st.plotly_chart(fig, use_container_width=True)

        with right:
            st.subheader("📈 Win % Trend")
            fig = styled_line(
                season_df,
                x="season",
                y="win_pct",
                title="Win Percentage Over Seasons",
            )
            fig.update_traces(line_color=team_color, marker_color=team_color)
            fig.update_layout(xaxis_title="Season", yaxis_title="Win %")
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # ---- Stage reached + Cumulative wins ----
        stage_df = get_stage_reached(selected_team)
        left, right = st.columns(2)

        with left:
            st.subheader("🏆 Season Journey")
            if not stage_df.empty:
                stage_color_map = {
                    "🏆 Champion": "#FFD700",
                    "Runner-up": "#C0C0C0",
                    "Playoff": "#4ECDC4",
                    "League": "#888888",
                }
                fig = styled_bar(
                    stage_df,
                    x="season",
                    y="max_stage",
                    title="Stage Reached Each Season",
                    color="stage_reached",
                    color_map=stage_color_map,
                )
                fig.update_layout(
                    yaxis=dict(
                        tickvals=[1, 3, 4, 5],
                        ticktext=["League", "Playoff", "Final", "Champion"],
                        title="Stage",
                    ),
                    xaxis_title="Season",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No stage data available.")

        with right:
            st.subheader("📈 Cumulative Wins")
            cum_df = season_df.copy()
            cum_df["cumulative_wins"] = cum_df["wins"].cumsum()
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=cum_df["season"],
                    y=cum_df["cumulative_wins"],
                    mode="lines+markers",
                    fill="tozeroy",
                    line=dict(color=team_color, width=2),
                    marker=dict(color=team_color, size=6),
                    name="Cumulative Wins",
                )
            )
            fig.update_layout(
                title="Cumulative Wins Over Seasons",
                xaxis_title="Season",
                yaxis_title="Total Wins",
            )
            apply_ipl_style(fig)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # ---- Season-wise performance table ----
        st.subheader("📋 Season-wise Performance")
        if not stage_df.empty:
            display_df = season_df.merge(
                stage_df[["season", "stage_reached"]], on="season", how="left"
            )
        else:
            display_df = season_df.copy()
            display_df["stage_reached"] = "—"
        display_df = display_df.rename(
            columns={
                "season": "Season",
                "matches_played": "Played",
                "wins": "Won",
                "losses": "Lost",
                "no_results": "NR",
                "win_pct": "Win%",
                "stage_reached": "Stage",
            }
        )
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Win%": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

# -------------------------------------------------------------------
# BATTING TAB
# -------------------------------------------------------------------
with tab_batting:
    team_avg_df = get_avg_team_score_by_season(selected_team)
    league_avg_df = get_league_avg_score_by_season()
    batters_df = get_top_run_scorers(selected_team)

    # ---- Avg team total + Top run scorers chart ----
    left, right = st.columns(2)

    with left:
        st.subheader("📈 Average Team Total by Season")
        if not team_avg_df.empty:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=team_avg_df["season"],
                    y=team_avg_df["avg_score"],
                    mode="lines+markers",
                    name=selected_team,
                    line=dict(color=team_color, width=2),
                    marker=dict(color=team_color, size=7),
                )
            )
            if not league_avg_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=league_avg_df["season"],
                        y=league_avg_df["avg_score"],
                        mode="lines",
                        name="League Avg",
                        line=dict(color="#888888", width=2, dash="dash"),
                    )
                )
            fig.update_layout(
                title="Average Team Total vs League Average",
                xaxis_title="Season",
                yaxis_title="Avg Score",
            )
            apply_ipl_style(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No batting data available.")

    with right:
        st.subheader("🏏 Top 10 All-Time Run Scorers")
        if not batters_df.empty:
            fig = styled_bar(
                batters_df,
                x="total_runs",
                y="batter",
                title="Top Run Scorers",
                horizontal=True,
            )
            fig.update_traces(marker_color=team_color)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No batting data available.")

    # ---- Batters detail table ----
    if not batters_df.empty:
        st.subheader("📋 Top Run Scorers — Detail")
        bat_display = batters_df.rename(
            columns={
                "batter": "Batter",
                "total_runs": "Runs",
                "matches": "Matches",
                "fours": "4s",
                "sixes": "6s",
                "highest_score": "HS",
                "strike_rate": "SR",
                "average": "Avg",
            }
        )
        st.dataframe(
            bat_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "SR": st.column_config.NumberColumn(format="%.1f"),
                "Avg": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    st.divider()

    # ---- Highest / Lowest team totals ----
    left, right = st.columns(2)

    with left:
        st.subheader("🔝 Highest Team Totals")
        high_df = get_highest_team_totals(selected_team)
        if not high_df.empty:
            high_display = high_df.rename(
                columns={
                    "score": "Score",
                    "wickets": "Wkts",
                    "season": "Season",
                    "opponent": "vs Team",
                }
            )[["Score", "Wkts", "vs Team", "Season"]]
            st.dataframe(high_display, use_container_width=True, hide_index=True)
        else:
            st.info("No data available.")

    with right:
        st.subheader("🔻 Lowest Team Totals")
        low_df = get_lowest_team_totals(selected_team)
        if not low_df.empty:
            low_display = low_df.rename(
                columns={
                    "score": "Score",
                    "wickets": "Wkts",
                    "season": "Season",
                    "opponent": "vs Team",
                }
            )[["Score", "Wkts", "vs Team", "Season"]]
            st.dataframe(low_display, use_container_width=True, hide_index=True)
        else:
            st.info("No data available.")

# -------------------------------------------------------------------
# BOWLING TAB
# -------------------------------------------------------------------
with tab_bowling:
    conceded_df = get_avg_conceded_by_season(selected_team)
    bowlers_df = get_top_wicket_takers(selected_team)

    # ---- Avg conceded + Top wicket takers chart ----
    left, right = st.columns(2)

    with left:
        st.subheader("📈 Avg Runs Conceded per Season")
        if not conceded_df.empty:
            fig = styled_line(
                conceded_df,
                x="season",
                y="avg_conceded",
                title="Average Runs Conceded by Season",
            )
            fig.update_traces(line_color=team_color, marker_color=team_color)
            fig.update_layout(xaxis_title="Season", yaxis_title="Avg Conceded")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No bowling data available.")

    with right:
        st.subheader("🎳 Top 10 All-Time Wicket Takers")
        if not bowlers_df.empty:
            fig = styled_bar(
                bowlers_df,
                x="total_wickets",
                y="bowler",
                title="Top Wicket Takers",
                horizontal=True,
            )
            fig.update_traces(marker_color=team_color)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No bowling data available.")

    # ---- Bowlers detail table ----
    if not bowlers_df.empty:
        st.subheader("📋 Top Wicket Takers — Detail")
        bowl_display = bowlers_df.rename(
            columns={
                "bowler": "Bowler",
                "total_wickets": "Wickets",
                "matches": "Matches",
                "economy": "Economy",
                "bowling_sr": "SR",
            }
        )
        st.dataframe(
            bowl_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Economy": st.column_config.NumberColumn(format="%.2f"),
                "SR": st.column_config.NumberColumn(format="%.1f"),
            },
        )

    st.divider()

    # ---- Best bowling figures ----
    st.subheader("🏆 Best Bowling Figures")
    figures_df = get_best_bowling_figures(selected_team)
    if not figures_df.empty:
        fig_display = figures_df.copy()
        fig_display["figures"] = (
            fig_display["wickets"].astype(int).astype(str)
            + "/"
            + fig_display["runs_conceded"].astype(int).astype(str)
        )
        fig_display = fig_display.rename(
            columns={
                "bowler": "Bowler",
                "figures": "Figures",
                "economy": "Economy",
                "season": "Season",
                "vs_team": "vs Team",
            }
        )[["Bowler", "Figures", "Economy", "vs Team", "Season"]]
        st.dataframe(
            fig_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Economy": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    else:
        st.info("No bowling figures data available.")

# -------------------------------------------------------------------
# VS TEAMS TAB
# -------------------------------------------------------------------
with tab_vs:
    st.subheader("⚔️ Head-to-Head Record")
    h2h_df = get_head_to_head(selected_team)

    if h2h_df.empty:
        st.info("No head-to-head data available.")
    else:
        h2h_display = h2h_df.rename(
            columns={
                "vs_team": "vs Team",
                "played": "Played",
                "won": "Won",
                "lost": "Lost",
                "win_pct": "Win%",
            }
        )
        st.dataframe(
            h2h_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Win%": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

        st.divider()

        # ---- Win % bar chart (green > 50%, red < 50%) ----
        st.subheader("📊 Head-to-Head Win %")
        chart_df = h2h_df.sort_values("win_pct", ascending=True).copy()
        bar_colors = [
            "#2ecc71" if pct >= 50 else "#e74c3c" for pct in chart_df["win_pct"]
        ]

        fig = go.Figure(
            go.Bar(
                x=chart_df["win_pct"],
                y=chart_df["vs_team"],
                orientation="h",
                marker_color=bar_colors,
                text=chart_df["win_pct"].apply(lambda x: f"{x:.1f}%"),
                textposition="auto",
            )
        )
        fig.update_layout(
            title="Win % Against Each Team",
            xaxis_title="Win %",
            yaxis_title="",
        )
        fig.add_vline(x=50, line_dash="dash", line_color="white", opacity=0.5)
        apply_ipl_style(fig, height=max(400, len(chart_df) * 35))
        st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------------
# VENUES TAB
# -------------------------------------------------------------------
with tab_venues:
    st.subheader("🏟️ Performance by Venue")
    venue_df = get_venue_performance(selected_team)

    if not venue_df.empty:
        venue_display = venue_df.rename(
            columns={
                "venue": "Venue",
                "matches": "Matches",
                "wins": "Wins",
                "losses": "Losses",
                "win_pct": "Win%",
            }
        )
        st.dataframe(
            venue_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Win%": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
    else:
        st.info("No venue data available.")

    st.divider()

    # ---- Home vs Away ----
    st.subheader("🏠 Home vs Away")
    ha_df = get_home_away_winpct(selected_team)
    if not ha_df.empty:
        home_row = ha_df[ha_df["location"] == "Home"]
        away_row = ha_df[ha_df["location"] == "Away"]

        c1, c2 = st.columns(2)
        with c1:
            if not home_row.empty:
                h = home_row.iloc[0]
                st.metric(
                    **metric_card(
                        "🏠 Home Win%",
                        f"{h['win_pct']:.1f}%",
                        help_text=f"{int(h['wins'])} wins in {int(h['matches'])} matches",
                    )
                )
            else:
                st.metric(**metric_card("🏠 Home Win%", "N/A"))

        with c2:
            if not away_row.empty:
                a = away_row.iloc[0]
                st.metric(
                    **metric_card(
                        "✈️ Away Win%",
                        f"{a['win_pct']:.1f}%",
                        help_text=f"{int(a['wins'])} wins in {int(a['matches'])} matches",
                    )
                )
            else:
                st.metric(**metric_card("✈️ Away Win%", "N/A"))
    else:
        st.info("No home/away data available.")

# -------------------------------------------------------------------
# TOSS & CHASING TAB
# -------------------------------------------------------------------
with tab_toss:
    # ---- Toss pie + decision trend ----
    left, right = st.columns(2)

    with left:
        st.subheader("🪙 Toss Record")
        toss_df = get_toss_record(selected_team)
        if not toss_df.empty:
            fig = styled_pie(
                toss_df,
                names="toss_result",
                values="count",
                title="Toss Wins vs Losses",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No toss data available.")

    with right:
        st.subheader("📈 Toss Decision Trend")
        decision_df = get_toss_decision_trend(selected_team)
        if not decision_df.empty:
            fig = styled_line(
                decision_df,
                x="season",
                y="field_first_pct",
                title="% Choosing to Field First (when toss won)",
            )
            fig.update_traces(line_color=team_color, marker_color=team_color)
            fig.update_layout(xaxis_title="Season", yaxis_title="Field First %")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No toss decision data available.")

    st.divider()

    # ---- Batting first vs Chasing win % ----
    st.subheader("📊 Batting First vs Chasing")
    bf_chase_df = get_bat_first_vs_chase_winpct(selected_team)
    if not bf_chase_df.empty:
        bat_row = bf_chase_df[bf_chase_df["scenario"] == "Batting First"]
        chase_row = bf_chase_df[bf_chase_df["scenario"] == "Chasing"]

        c1, c2 = st.columns(2)
        with c1:
            if not bat_row.empty:
                b = bat_row.iloc[0]
                st.metric(
                    **metric_card(
                        "Batting First Win%",
                        f"{b['win_pct']:.1f}%",
                        help_text=f"{int(b['wins'])} wins in {int(b['matches'])} matches",
                    )
                )
        with c2:
            if not chase_row.empty:
                ch = chase_row.iloc[0]
                st.metric(
                    **metric_card(
                        "Chasing Win%",
                        f"{ch['win_pct']:.1f}%",
                        help_text=f"{int(ch['wins'])} wins in {int(ch['matches'])} matches",
                    )
                )

    st.divider()

    # ---- Chase success by target range ----
    st.subheader("🎯 Chase Success by Target Range")
    chase_df = get_chase_success_by_target(selected_team)
    if not chase_df.empty:
        fig = styled_bar(
            chase_df,
            x="target_range",
            y="success_pct",
            title="Chase Success Rate by Target Range",
            text_auto=False,
        )
        fig.update_traces(
            marker_color=team_color,
            text=chase_df.apply(
                lambda r: f"{r['success_pct']:.0f}% ({int(r['successful'])}/{int(r['total_chases'])})",
                axis=1,
            ),
            textposition="outside",
        )
        fig.update_layout(xaxis_title="Target Range", yaxis_title="Success %")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No chase data available.")

    st.divider()

    # ---- Highest chases & lowest defended ----
    left, right = st.columns(2)

    with left:
        st.subheader("🏆 Highest Successful Chases")
        chase_high_df = get_highest_successful_chases(selected_team)
        if not chase_high_df.empty:
            ch_display = chase_high_df.rename(
                columns={
                    "chase_score": "Score",
                    "target_score": "Target",
                    "opponent": "vs Team",
                    "season": "Season",
                    "venue": "Venue",
                    "margin": "Margin",
                }
            )
            st.dataframe(ch_display, use_container_width=True, hide_index=True)
        else:
            st.info("No successful chase data.")

    with right:
        st.subheader("🛡️ Lowest Totals Defended")
        defend_df = get_lowest_totals_defended(selected_team)
        if not defend_df.empty:
            def_display = defend_df.rename(
                columns={
                    "defended_score": "Defended",
                    "opponent_score": "Opp Score",
                    "opponent": "vs Team",
                    "season": "Season",
                    "venue": "Venue",
                    "margin": "Margin",
                }
            )
            st.dataframe(def_display, use_container_width=True, hide_index=True)
        else:
            st.info("No defence data available.")
