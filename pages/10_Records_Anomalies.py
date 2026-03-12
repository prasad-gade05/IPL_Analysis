"""
Records & Anomalies — The complete IPL record book.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import apply_ipl_style, styled_bar, big_number_style, IPL_COLORWAY
from src.utils.constants import TEAM_COLORS, ALL_SEASONS
from src.utils.formatters import format_number, format_strike_rate, format_economy, format_overs

st.title("Records & Anomalies")
st.caption("The complete IPL record book — every milestone, extreme and anomaly.")
st.markdown(big_number_style(), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  BATTING RECORD QUERIES
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _highest_individual_scores():
    return query("""
        SELECT pb.batter                                                      AS Player,
               pb.runs::INT                                                   AS Runs,
               pb.balls::INT                                                  AS Balls,
               pb.fours::INT                                                  AS "4s",
               pb.sixes::INT                                                  AS "6s",
               ROUND(pb.strike_rate, 1)                                       AS SR,
               CASE WHEN pb.batting_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.venue                                                       AS Venue,
               pb.season                                                      AS Season
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        ORDER BY pb.runs DESC, pb.balls ASC
        LIMIT 25
    """)


@st.cache_data(ttl=3600)
def _fastest_fifties():
    return query("""
        SELECT pb.batter                                                      AS Player,
               pb.runs::INT                                                   AS Runs,
               pb.balls::INT                                                  AS Balls,
               pb.fours::INT                                                  AS "4s",
               pb.sixes::INT                                                  AS "6s",
               ROUND(pb.strike_rate, 1)                                       AS SR,
               CASE WHEN pb.batting_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.season                                                      AS Season
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE pb.is_fifty = true
        ORDER BY pb.balls ASC, pb.runs DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _fastest_centuries():
    return query("""
        SELECT pb.batter                                                      AS Player,
               pb.runs::INT                                                   AS Runs,
               pb.balls::INT                                                  AS Balls,
               pb.fours::INT                                                  AS "4s",
               pb.sixes::INT                                                  AS "6s",
               ROUND(pb.strike_rate, 1)                                       AS SR,
               CASE WHEN pb.batting_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.season                                                      AS Season
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE pb.is_hundred = true
        ORDER BY pb.balls ASC, pb.runs DESC
        LIMIT 10
    """)


@st.cache_data(ttl=3600)
def _most_sixes_innings():
    return query("""
        SELECT pb.batter                                                      AS Player,
               pb.sixes::INT                                                  AS Sixes,
               pb.runs::INT                                                   AS Runs,
               pb.balls::INT                                                  AS Balls,
               ROUND(pb.strike_rate, 1)                                       AS SR,
               CASE WHEN pb.batting_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.season                                                      AS Season
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        ORDER BY pb.sixes DESC, pb.runs DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_fours_innings():
    return query("""
        SELECT pb.batter                                                      AS Player,
               pb.fours::INT                                                  AS Fours,
               pb.runs::INT                                                   AS Runs,
               pb.balls::INT                                                  AS Balls,
               ROUND(pb.strike_rate, 1)                                       AS SR,
               CASE WHEN pb.batting_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.season                                                      AS Season
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        ORDER BY pb.fours DESC, pb.runs DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _highest_sr_innings():
    return query("""
        SELECT pb.batter                                                      AS Player,
               ROUND(pb.strike_rate, 1)                                       AS SR,
               pb.runs::INT                                                   AS Runs,
               pb.balls::INT                                                  AS Balls,
               pb.fours::INT                                                  AS "4s",
               pb.sixes::INT                                                  AS "6s",
               CASE WHEN pb.batting_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.season                                                      AS Season
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE pb.balls >= 20
        ORDER BY pb.strike_rate DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _slowest_fifties():
    return query("""
        SELECT pb.batter                                                      AS Player,
               pb.runs::INT                                                   AS Runs,
               pb.balls::INT                                                  AS Balls,
               ROUND(pb.strike_rate, 1)                                       AS SR,
               pb.fours::INT                                                  AS "4s",
               pb.sixes::INT                                                  AS "6s",
               CASE WHEN pb.batting_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.season                                                      AS Season
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE pb.is_fifty = true
        ORDER BY pb.balls DESC, pb.runs ASC
        LIMIT 10
    """)


@st.cache_data(ttl=3600)
def _most_runs_single_season():
    return query("""
        SELECT batter                                                         AS Player,
               season                                                         AS Season,
               SUM(runs)::INT                                                 AS Runs,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs) * 1.0
                     / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0), 2) AS Avg,
               ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 1)           AS SR
        FROM player_batting
        GROUP BY batter, season
        ORDER BY Runs DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_consecutive_ducks():
    return query("""
        WITH numbered AS (
            SELECT batter, match_id, season, is_duck,
                   ROW_NUMBER() OVER (PARTITION BY batter ORDER BY match_id) AS rn
            FROM player_batting
        ),
        grouped AS (
            SELECT batter, match_id, season, is_duck, rn,
                   rn - ROW_NUMBER() OVER (PARTITION BY batter, is_duck ORDER BY rn) AS grp
            FROM numbered
        ),
        streaks AS (
            SELECT batter,
                   COUNT(*)::INT AS streak,
                   MIN(season)   AS from_season,
                   MAX(season)   AS to_season
            FROM grouped
            WHERE is_duck = true
            GROUP BY batter, grp
        )
        SELECT batter            AS Player,
               streak            AS "Consecutive Ducks",
               from_season       AS "From Season",
               to_season         AS "To Season"
        FROM streaks
        WHERE streak >= 3
        ORDER BY streak DESC, Player
        LIMIT 15
    """)


# ═══════════════════════════════════════════════════════════════════════
#  BOWLING RECORD QUERIES
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _best_bowling_figures():
    return query("""
        SELECT pb.bowler                                                      AS Player,
               pb.wickets::INT                                                AS Wickets,
               pb.runs_conceded::INT                                          AS Runs,
               pb.balls_bowled::INT                                           AS Balls,
               ROUND(pb.economy, 2)                                           AS Economy,
               CASE WHEN pb.bowling_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.venue                                                       AS Venue,
               pb.season                                                      AS Season
        FROM player_bowling pb
        JOIN matches m ON pb.match_id = m.match_id
        ORDER BY pb.wickets DESC, pb.runs_conceded ASC
        LIMIT 25
    """)


@st.cache_data(ttl=3600)
def _most_economical_spells():
    return query("""
        SELECT pb.bowler                                                      AS Player,
               pb.runs_conceded::INT                                          AS Runs,
               pb.balls_bowled::INT                                           AS Balls,
               pb.wickets::INT                                                AS Wickets,
               ROUND(pb.economy, 2)                                           AS Economy,
               CASE WHEN pb.bowling_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.season                                                      AS Season
        FROM player_bowling pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE pb.balls_bowled = 24
        ORDER BY pb.economy ASC, pb.wickets DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_expensive_spells():
    return query("""
        SELECT pb.bowler                                                      AS Player,
               pb.runs_conceded::INT                                          AS Runs,
               pb.balls_bowled::INT                                           AS Balls,
               pb.wickets::INT                                                AS Wickets,
               ROUND(pb.economy, 2)                                           AS Economy,
               CASE WHEN pb.bowling_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.season                                                      AS Season
        FROM player_bowling pb
        JOIN matches m ON pb.match_id = m.match_id
        ORDER BY pb.runs_conceded DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_wickets_single_season():
    return query("""
        SELECT bowler                                                         AS Player,
               season                                                         AS Season,
               SUM(wickets)::INT                                              AS Wickets,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs_conceded) * 6.0
                     / NULLIF(SUM(balls_bowled), 0), 2)                       AS Economy,
               ROUND(SUM(balls_bowled) * 1.0
                     / NULLIF(SUM(wickets), 0), 1)                            AS SR
        FROM player_bowling
        GROUP BY bowler, season
        ORDER BY Wickets DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_maidens_career():
    return query("""
        SELECT bowler                                                         AS Player,
               SUM(maidens)::INT                                              AS Maidens,
               COUNT(*)::INT                                                  AS Innings,
               SUM(wickets)::INT                                              AS Wickets,
               ROUND(SUM(runs_conceded) * 6.0
                     / NULLIF(SUM(balls_bowled), 0), 2)                       AS Economy
        FROM player_bowling
        GROUP BY bowler
        ORDER BY Maidens DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_dots_career():
    return query("""
        SELECT bowler                                                         AS Player,
               SUM(dots_bowled)::INT                                          AS "Dot Balls",
               COUNT(*)::INT                                                  AS Innings,
               SUM(wickets)::INT                                              AS Wickets,
               ROUND(SUM(dots_bowled) * 100.0
                     / NULLIF(SUM(balls_bowled), 0), 1)                       AS "Dot %"
        FROM player_bowling
        GROUP BY bowler
        ORDER BY "Dot Balls" DESC
        LIMIT 15
    """)


# ═══════════════════════════════════════════════════════════════════════
#  TEAM RECORD QUERIES
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _highest_team_totals():
    return query("""
        SELECT * FROM (
            SELECT team1                                   AS Team,
                   team1_score::INT                        AS Score,
                   COALESCE(team1_wickets, 0)::INT         AS Wickets,
                   team2                                   AS "Vs",
                   venue                                   AS Venue,
                   season                                  AS Season
            FROM matches
            WHERE team1_score IS NOT NULL
            UNION ALL
            SELECT team2                                   AS Team,
                   team2_score::INT                        AS Score,
                   COALESCE(team2_wickets, 0)::INT         AS Wickets,
                   team1                                   AS "Vs",
                   venue                                   AS Venue,
                   season                                  AS Season
            FROM matches
            WHERE team2_score IS NOT NULL
        ) t
        ORDER BY Score DESC
        LIMIT 20
    """)


@st.cache_data(ttl=3600)
def _lowest_team_totals():
    return query("""
        SELECT * FROM (
            SELECT team1                                   AS Team,
                   team1_score::INT                        AS Score,
                   COALESCE(team1_wickets, 0)::INT         AS Wickets,
                   team2                                   AS "Vs",
                   venue                                   AS Venue,
                   season                                  AS Season
            FROM matches
            WHERE team1_score IS NOT NULL AND team1_score > 0
            UNION ALL
            SELECT team2                                   AS Team,
                   team2_score::INT                        AS Score,
                   COALESCE(team2_wickets, 0)::INT         AS Wickets,
                   team1                                   AS "Vs",
                   venue                                   AS Venue,
                   season                                  AS Season
            FROM matches
            WHERE team2_score IS NOT NULL AND team2_score > 0
        ) t
        ORDER BY Score ASC
        LIMIT 20
    """)


@st.cache_data(ttl=3600)
def _biggest_wins_by_runs():
    return query("""
        SELECT match_won_by                                AS Winner,
               win_margin_value::INT                       AS "Margin (Runs)",
               CASE WHEN match_won_by = team1 THEN team2
                    ELSE team1 END                         AS Loser,
               venue                                       AS Venue,
               season                                      AS Season
        FROM matches
        WHERE win_margin_type = 'runs'
          AND win_margin_value IS NOT NULL
        ORDER BY win_margin_value DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _biggest_wins_by_wickets():
    return query("""
        SELECT match_won_by                                AS Winner,
               win_margin_value::INT                       AS "Wickets Remaining",
               CASE WHEN match_won_by = team1 THEN team2
                    ELSE team1 END                         AS Loser,
               venue                                       AS Venue,
               season                                      AS Season
        FROM matches
        WHERE win_margin_type = 'wickets'
          AND win_margin_value IS NOT NULL
        ORDER BY win_margin_value DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _narrowest_victories():
    return query("""
        SELECT match_won_by                                AS Winner,
               win_margin_value::INT                       AS Margin,
               win_margin_type                             AS "Margin Type",
               CASE WHEN match_won_by = team1 THEN team2
                    ELSE team1 END                         AS Loser,
               venue                                       AS Venue,
               season                                      AS Season
        FROM matches
        WHERE win_margin_value IS NOT NULL
          AND (
                (win_margin_type = 'runs'    AND win_margin_value BETWEEN 1 AND 2)
             OR (win_margin_type = 'wickets' AND win_margin_value = 1)
          )
        ORDER BY win_margin_value ASC, season
    """)


@st.cache_data(ttl=3600)
def _highest_successful_chases():
    return query("""
        WITH chasing AS (
            SELECT DISTINCT match_id, batting_team AS chasing_team
            FROM balls WHERE innings = 2
        )
        SELECT c.chasing_team                                                    AS Team,
               (CASE WHEN c.chasing_team = m.team1 THEN m.team1_score
                     ELSE m.team2_score END)::INT                                AS Score,
               COALESCE(CASE WHEN c.chasing_team = m.team1 THEN m.team1_wickets
                             ELSE m.team2_wickets END, 0)::INT                   AS Wickets,
               CASE WHEN c.chasing_team = m.team1 THEN m.team2 ELSE m.team1 END AS "Vs",
               (CASE WHEN c.chasing_team = m.team1 THEN m.team2_score
                     ELSE m.team1_score END)::INT                                AS Target,
               m.venue                                                           AS Venue,
               m.season                                                          AS Season
        FROM matches m
        JOIN chasing c ON m.match_id = c.match_id
        WHERE m.match_won_by = c.chasing_team
        ORDER BY Score DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _lowest_totals_defended():
    return query("""
        WITH first_innings AS (
            SELECT DISTINCT match_id, batting_team AS defending_team
            FROM balls WHERE innings = 1
        )
        SELECT f.defending_team                                                  AS Team,
               (CASE WHEN f.defending_team = m.team1 THEN m.team1_score
                     ELSE m.team2_score END)::INT                                AS Score,
               CASE WHEN f.defending_team = m.team1 THEN m.team2 ELSE m.team1 END AS "Vs",
               m.win_margin_value::INT                                           AS "Won By (Runs)",
               m.venue                                                           AS Venue,
               m.season                                                          AS Season
        FROM matches m
        JOIN first_innings f ON m.match_id = f.match_id
        WHERE m.match_won_by = f.defending_team
          AND m.win_margin_type = 'runs'
        ORDER BY Score ASC
        LIMIT 15
    """)


# ═══════════════════════════════════════════════════════════════════════
#  MATCH RECORD QUERIES
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _highest_aggregate_matches():
    return query("""
        SELECT (COALESCE(m.team1_score, 0) + COALESCE(m.team2_score, 0))::INT AS "Aggregate",
               m.team1                                                         AS "Team 1",
               m.team1_score::INT                                              AS "Score 1",
               m.team2                                                         AS "Team 2",
               m.team2_score::INT                                              AS "Score 2",
               m.venue                                                         AS Venue,
               m.season                                                        AS Season
        FROM matches m
        WHERE m.team1_score IS NOT NULL AND m.team2_score IS NOT NULL
        ORDER BY "Aggregate" DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_sixes_match():
    return query("""
        SELECT b.match_id,
               COUNT(CASE WHEN b.is_six THEN 1 END)::INT                      AS Sixes,
               m.team1                                                         AS "Team 1",
               m.team1_score::INT                                              AS "Score 1",
               m.team2                                                         AS "Team 2",
               m.team2_score::INT                                              AS "Score 2",
               m.venue                                                         AS Venue,
               m.season                                                        AS Season
        FROM balls b
        JOIN matches m ON b.match_id = m.match_id
        WHERE b.is_super_over = false
        GROUP BY b.match_id, m.team1, m.team1_score, m.team2, m.team2_score,
                 m.venue, m.season
        ORDER BY Sixes DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _super_over_matches():
    return query("""
        SELECT m.team1                                                         AS "Team 1",
               m.team1_score::INT                                              AS "Score 1",
               m.team2                                                         AS "Team 2",
               m.team2_score::INT                                              AS "Score 2",
               m.match_won_by                                                  AS Winner,
               m.venue                                                         AS Venue,
               m.season                                                        AS Season
        FROM matches m
        WHERE m.is_super_over_match = true
        ORDER BY m.season DESC, m.date DESC
    """)


@st.cache_data(ttl=3600)
def _last_ball_finishes():
    return query("""
        WITH last_ball AS (
            SELECT match_id,
                   MAX(over * 6 + CASE WHEN valid_ball THEN 1 ELSE 0 END) AS last_seq
            FROM balls
            WHERE innings = 2 AND is_super_over = false
            GROUP BY match_id
        ),
        last_over AS (
            SELECT DISTINCT b.match_id
            FROM balls b
            JOIN last_ball lb ON b.match_id = lb.match_id
            WHERE b.innings = 2
              AND b.over = 20
              AND b.is_super_over = false
        )
        SELECT m.match_won_by                                                  AS Winner,
               CASE WHEN m.match_won_by = m.team1 THEN m.team2
                    ELSE m.team1 END                                           AS Loser,
               m.win_margin_value::INT                                         AS Margin,
               m.win_margin_type                                               AS "Margin Type",
               m.venue                                                         AS Venue,
               m.season                                                        AS Season
        FROM matches m
        JOIN last_over lo ON m.match_id = lo.match_id
        WHERE m.match_won_by IS NOT NULL
          AND m.win_margin_value IS NOT NULL
          AND (
                (m.win_margin_type = 'wickets' AND m.win_margin_value <= 2)
             OR (m.win_margin_type = 'runs'    AND m.win_margin_value <= 3)
          )
        ORDER BY m.season DESC, m.date DESC
    """)


# ═══════════════════════════════════════════════════════════════════════
#  MILESTONES QUERIES
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _runs_5000_club():
    return query("""
        SELECT batter                                                         AS Player,
               SUM(runs)::INT                                                 AS Runs,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs) * 1.0
                     / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0), 2) AS Avg,
               ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 1)           AS SR,
               SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END)::INT              AS "100s",
               SUM(CASE WHEN is_fifty   THEN 1 ELSE 0 END)::INT              AS "50s"
        FROM player_batting
        GROUP BY batter
        HAVING SUM(runs) >= 5000
        ORDER BY Runs DESC
    """)


@st.cache_data(ttl=3600)
def _wickets_200_club():
    return query("""
        SELECT bowler                                                         AS Player,
               SUM(wickets)::INT                                              AS Wickets,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs_conceded) * 6.0
                     / NULLIF(SUM(balls_bowled), 0), 2)                       AS Economy,
               ROUND(SUM(balls_bowled) * 1.0
                     / NULLIF(SUM(wickets), 0), 1)                            AS SR
        FROM player_bowling
        GROUP BY bowler
        HAVING SUM(wickets) >= 200
        ORDER BY Wickets DESC
    """)


@st.cache_data(ttl=3600)
def _sixes_100_club():
    return query("""
        SELECT batter                                                         AS Player,
               SUM(sixes)::INT                                                AS Sixes,
               SUM(runs)::INT                                                 AS Runs,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 1)           AS SR
        FROM player_batting
        GROUP BY batter
        HAVING SUM(sixes) >= 100
        ORDER BY Sixes DESC
    """)


@st.cache_data(ttl=3600)
def _matches_200_club():
    return query("""
        WITH all_players AS (
            SELECT batter AS player, match_id FROM player_batting
            UNION
            SELECT bowler AS player, match_id FROM player_bowling
        )
        SELECT player                                  AS Player,
               COUNT(DISTINCT match_id)::INT           AS Matches
        FROM all_players
        GROUP BY player
        HAVING Matches >= 200
        ORDER BY Matches DESC
    """)


@st.cache_data(ttl=3600)
def _orange_cap_history():
    return query("""
        WITH season_top AS (
            SELECT season, batter, SUM(runs)::INT AS runs,
                   COUNT(*)::INT AS innings,
                   ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 1) AS sr,
                   ROW_NUMBER() OVER (PARTITION BY season ORDER BY SUM(runs) DESC) AS rk
            FROM player_batting
            GROUP BY season, batter
        )
        SELECT season                                  AS Season,
               batter                                  AS Player,
               runs                                    AS Runs,
               innings                                 AS Innings,
               sr                                      AS SR
        FROM season_top
        WHERE rk = 1
        ORDER BY season
    """)


@st.cache_data(ttl=3600)
def _purple_cap_history():
    return query("""
        WITH season_top AS (
            SELECT season, bowler, SUM(wickets)::INT AS wickets,
                   COUNT(*)::INT AS innings,
                   ROUND(SUM(runs_conceded) * 6.0
                         / NULLIF(SUM(balls_bowled), 0), 2) AS economy,
                   ROW_NUMBER() OVER (PARTITION BY season ORDER BY SUM(wickets) DESC) AS rk
            FROM player_bowling
            GROUP BY season, bowler
        )
        SELECT season                                  AS Season,
               bowler                                  AS Player,
               wickets                                 AS Wickets,
               innings                                 AS Innings,
               economy                                 AS Economy
        FROM season_top
        WHERE rk = 1
        ORDER BY season
    """)


@st.cache_data(ttl=3600)
def _most_potm_awards():
    return query("""
        SELECT player_of_match                         AS Player,
               COUNT(*)::INT                           AS Awards
        FROM matches
        WHERE player_of_match IS NOT NULL
        GROUP BY player_of_match
        ORDER BY Awards DESC
        LIMIT 15
    """)


# ═══════════════════════════════════════════════════════════════════════
#  HELPER
# ═══════════════════════════════════════════════════════════════════════

def _show_table(df, title=None):
    """Display a dataframe with a subheader and empty-state guard."""
    if title:
        st.subheader(title)
    if df.empty:
        st.info("No records found.")
    else:
        st.dataframe(df, width='stretch', hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
#  TAB LAYOUT
# ═══════════════════════════════════════════════════════════════════════

tab_bat, tab_bowl, tab_team, tab_match, tab_mile = st.tabs([
    "Batting Records",
    "Bowling Records",
    "Team Records",
    "Match Records",
    "Milestones",
])


# ── BATTING RECORDS ───────────────────────────────────────────────────
with tab_bat:

    _show_table(_highest_individual_scores(), "Highest Individual Scores (Top 25)")
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _show_table(_fastest_fifties(), "Fastest Fifties (Top 15)")
    with c2:
        _show_table(_fastest_centuries(), "Fastest Centuries (Top 10)")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _show_table(_most_sixes_innings(), "Most Sixes in an Innings (Top 15)")
    with c2:
        _show_table(_most_fours_innings(), "Most Fours in an Innings (Top 15)")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _show_table(_highest_sr_innings(), "Highest SR in Innings (min 20 balls, Top 15)")
    with c2:
        _show_table(_slowest_fifties(), "Slowest Fifties (Top 10)")

    st.divider()
    _show_table(_most_runs_single_season(), "Most Runs in a Single Season (Top 15)")

    st.divider()
    _show_table(_most_consecutive_ducks(), "Most Consecutive Ducks")


# ── BOWLING RECORDS ───────────────────────────────────────────────────
with tab_bowl:

    _show_table(_best_bowling_figures(), "Best Bowling Figures (Top 25)")
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _show_table(_most_economical_spells(), "Most Economical 4-Over Spells (Top 15)")
    with c2:
        _show_table(_most_expensive_spells(), "Most Expensive Spells (Top 15)")

    st.divider()
    _show_table(_most_wickets_single_season(), "Most Wickets in a Single Season (Top 15)")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        _show_table(_most_maidens_career(), "Most Maiden Overs — Career (Top 15)")
    with c2:
        _show_table(_most_dots_career(), "Most Dot Balls — Career (Top 15)")


# ── TEAM RECORDS ──────────────────────────────────────────────────────
with tab_team:

    c1, c2 = st.columns(2)
    with c1:
        _show_table(_highest_team_totals(), "Highest Team Totals (Top 20)")
    with c2:
        _show_table(_lowest_team_totals(), "Lowest Team Totals (Top 20)")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        _show_table(_biggest_wins_by_runs(), "Biggest Wins by Runs (Top 15)")
    with c2:
        _show_table(_biggest_wins_by_wickets(), "Biggest Wins by Wickets (Top 15)")

    st.divider()
    _show_table(_narrowest_victories(), "Narrowest Victories")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        _show_table(_highest_successful_chases(), "Highest Successful Chases (Top 15)")
    with c2:
        _show_table(_lowest_totals_defended(), "Lowest Totals Defended (Top 15)")


# ── MATCH RECORDS ─────────────────────────────────────────────────────
with tab_match:

    _show_table(_highest_aggregate_matches(), "Highest Aggregate Matches (Top 15)")

    st.divider()
    _show_table(_most_sixes_match(), "Most Sixes in a Single Match (Top 15)")

    st.divider()
    _show_table(_super_over_matches(), "Super Over Matches")

    st.divider()
    _show_table(_last_ball_finishes(), "Last-Ball Finishes")


# ── MILESTONES ────────────────────────────────────────────────────────
with tab_mile:

    st.subheader("Elite Club Members")
    c1, c2 = st.columns(2)
    with c1:
        _show_table(_runs_5000_club(), "5,000+ Runs Club")
    with c2:
        _show_table(_wickets_200_club(), "200+ Wickets Club")

    c1, c2 = st.columns(2)
    with c1:
        _show_table(_sixes_100_club(), "100+ Sixes Club")
    with c2:
        _show_table(_matches_200_club(), "200+ Matches Club")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _show_table(_orange_cap_history(), "Orange Cap History (Top Run Scorer per Season)")
    with c2:
        _show_table(_purple_cap_history(), "Purple Cap History (Top Wicket Taker per Season)")

    st.divider()
    st.subheader("Most Player of the Match Awards (Top 15)")
    df_potm = _most_potm_awards()
    if not df_potm.empty:
        fig = styled_bar(
            df_potm.sort_values("Awards"),
            x="Player", y="Awards",
            title="Most Player of the Match Awards",
            horizontal=True, height=500,
        )
        st.plotly_chart(fig, width='stretch')
        st.dataframe(df_potm, width='stretch', hide_index=True)
    else:
        st.info("No data found.")
