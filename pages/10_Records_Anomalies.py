"""
Records & Anomalies — The complete IPL record book.
"""

import logging

import pandas as pd
import streamlit as st

from src.db.connection import query
from src.utils.constants import ALL_SEASONS
from src.utils.control_renderer import active_control_chips, render_visual_controls
from src.utils.control_schema import VisualSpec
from src.utils.visual_specs import limit_control, number_control, season_range_control
from src.visualizations.card_renderer import render_active_filters, render_bar_chart, render_dataframe
from src.visualizations.theme import big_number_style

st.title("Records & Anomalies")
st.caption("The complete IPL record book — every milestone, extreme and anomaly.")
st.markdown(big_number_style(), unsafe_allow_html=True)

DEFAULT_SEASON_RANGE = (min(ALL_SEASONS), max(ALL_SEASONS))
LOGGER = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════
#  BATTING RECORD QUERIES
# ═══════════════════════════════════════════════════════════════════════


def _milestone_scores(
    milestone: int,
    balls_label: str,
    limit: int,
    fastest: bool,
    season_range: tuple[int, int] | None = None,
) -> pd.DataFrame:
    order_dir = "ASC" if fastest else "DESC"
    tie_break_dir = "DESC" if fastest else "ASC"
    season_filter_balls = _season_condition("season", season_range)
    season_filter_batting = _season_condition("pb.season", season_range)
    limit = _sanitize_limit(limit, limit)

    return query(
        f"""
        WITH milestone_marks AS (
            SELECT match_id,
                   innings,
                   batter,
                   MIN(batter_balls)::INT AS milestone_balls
            FROM balls
            WHERE batter_runs >= {milestone}
              AND {season_filter_balls}
            GROUP BY match_id, innings, batter
        )
        SELECT pb.batter                                                      AS Player,
               pb.runs::INT                                                   AS Runs,
               mm.milestone_balls                                             AS "{balls_label}",
               pb.balls::INT                                                  AS "Final Balls",
               pb.fours::INT                                                  AS "4s",
               pb.sixes::INT                                                  AS "6s",
               ROUND(pb.strike_rate, 1)                                       AS "Final SR",
               CASE WHEN pb.batting_team = m.team1 THEN m.team2
                    ELSE m.team1 END                                          AS "Vs",
               pb.season                                                      AS Season
        FROM player_batting pb
        JOIN milestone_marks mm
          ON pb.match_id = mm.match_id
         AND pb.innings = mm.innings
         AND pb.batter = mm.batter
        JOIN matches m ON pb.match_id = m.match_id
        WHERE {season_filter_batting}
        ORDER BY mm.milestone_balls {order_dir}, pb.runs {tie_break_dir}
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _highest_individual_scores(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 25,
) -> pd.DataFrame:
    season_filter = _season_condition("pb.season", season_range)
    limit = _sanitize_limit(limit, 25)
    return query(
        f"""
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
        WHERE {season_filter}
        ORDER BY pb.runs DESC, pb.balls ASC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _fastest_fifties(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    return _milestone_scores(50, "Balls to 50", limit, fastest=True, season_range=season_range)


@st.cache_data(ttl=3600)
def _fastest_centuries(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 10,
) -> pd.DataFrame:
    return _milestone_scores(100, "Balls to 100", limit, fastest=True, season_range=season_range)


@st.cache_data(ttl=3600)
def _most_sixes_innings(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("pb.season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
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
        WHERE {season_filter}
        ORDER BY pb.sixes DESC, pb.runs DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_fours_innings(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("pb.season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
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
        WHERE {season_filter}
        ORDER BY pb.fours DESC, pb.runs DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _highest_sr_innings(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_balls: int = 20,
) -> pd.DataFrame:
    season_filter = _season_condition("pb.season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_balls = max(1, int(min_balls))
    return query(
        f"""
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
        WHERE {season_filter}
          AND pb.balls >= {min_balls}
        ORDER BY pb.strike_rate DESC, pb.runs DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _slowest_fifties(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 10,
) -> pd.DataFrame:
    return _milestone_scores(50, "Balls to 50", limit, fastest=False, season_range=season_range)


@st.cache_data(ttl=3600)
def _most_runs_single_season(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT batter                                                         AS Player,
               season                                                         AS Season,
               SUM(runs)::INT                                                 AS Runs,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs) * 1.0
                     / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0), 2) AS Avg,
               ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 1)           AS SR
        FROM player_batting
        WHERE {season_filter}
        GROUP BY batter, season
        ORDER BY Runs DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_consecutive_ducks(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_streak: int = 3,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_streak = max(2, int(min_streak))
    return query(
        f"""
        WITH numbered AS (
            SELECT batter,
                   match_id,
                   season,
                   is_duck,
                   ROW_NUMBER() OVER (PARTITION BY batter ORDER BY match_id) AS rn
            FROM player_batting
            WHERE {season_filter}
        ),
        grouped AS (
            SELECT batter,
                   match_id,
                   season,
                   is_duck,
                   rn,
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
        WHERE streak >= {min_streak}
        ORDER BY streak DESC, Player
        LIMIT {limit}
        """
    )


# ═══════════════════════════════════════════════════════════════════════
#  BOWLING RECORD QUERIES
# ═══════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=3600)
def _best_bowling_figures(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 25,
) -> pd.DataFrame:
    season_filter = _season_condition("pb.season", season_range)
    limit = _sanitize_limit(limit, 25)
    return query(
        f"""
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
        WHERE {season_filter}
        ORDER BY pb.wickets DESC, pb.runs_conceded ASC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_economical_spells(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_balls: int = 24,
) -> pd.DataFrame:
    season_filter = _season_condition("pb.season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_balls = max(1, int(min_balls))
    return query(
        f"""
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
        WHERE {season_filter}
          AND pb.balls_bowled >= {min_balls}
        ORDER BY pb.economy ASC, pb.wickets DESC, pb.runs_conceded ASC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_expensive_spells(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("pb.season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
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
        WHERE {season_filter}
        ORDER BY pb.runs_conceded DESC, pb.economy DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_wickets_single_season(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT bowler                                                         AS Player,
               season                                                         AS Season,
               SUM(wickets)::INT                                              AS Wickets,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs_conceded) * 6.0
                     / NULLIF(SUM(balls_bowled), 0), 2)                       AS Economy,
               ROUND(SUM(balls_bowled) * 1.0
                     / NULLIF(SUM(wickets), 0), 1)                            AS SR
        FROM player_bowling
        WHERE {season_filter}
        GROUP BY bowler, season
        ORDER BY Wickets DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_maidens_career(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT bowler                                                         AS Player,
               SUM(maidens)::INT                                              AS Maidens,
               COUNT(*)::INT                                                  AS Innings,
               SUM(wickets)::INT                                              AS Wickets,
               ROUND(SUM(runs_conceded) * 6.0
                     / NULLIF(SUM(balls_bowled), 0), 2)                       AS Economy
        FROM player_bowling
        WHERE {season_filter}
        GROUP BY bowler
        ORDER BY Maidens DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_dots_career(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT bowler                                                         AS Player,
               SUM(dots_bowled)::INT                                          AS "Dot Balls",
               COUNT(*)::INT                                                  AS Innings,
               SUM(wickets)::INT                                              AS Wickets,
               ROUND(SUM(dots_bowled) * 100.0
                     / NULLIF(SUM(balls_bowled), 0), 1)                       AS "Dot %"
        FROM player_bowling
        WHERE {season_filter}
        GROUP BY bowler
        ORDER BY "Dot Balls" DESC
        LIMIT {limit}
        """
    )


# ═══════════════════════════════════════════════════════════════════════
#  TEAM RECORD QUERIES
# ═══════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=3600)
def _highest_team_totals(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 20,
) -> pd.DataFrame:
    start, end = _sanitize_season_range(season_range)
    limit = _sanitize_limit(limit, 20)
    return query(
        f"""
        SELECT team                                      AS Team,
               score                                     AS Score,
               wickets                                   AS Wickets,
               opponent                                  AS "Vs",
               venue                                     AS Venue,
               season                                    AS Season
        FROM completed_team_innings
        WHERE innings_complete
          AND season BETWEEN {start} AND {end}
        ORDER BY Score DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _lowest_team_totals(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 20,
) -> pd.DataFrame:
    start, end = _sanitize_season_range(season_range)
    limit = _sanitize_limit(limit, 20)
    return query(
        f"""
        SELECT team                                      AS Team,
               score                                     AS Score,
               wickets                                   AS Wickets,
               opponent                                  AS "Vs",
               venue                                     AS Venue,
               season                                    AS Season
        FROM completed_team_innings
        WHERE low_total_record_eligible
          AND score > 0
          AND season BETWEEN {start} AND {end}
        ORDER BY Score ASC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _biggest_wins_by_runs(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT match_won_by                                AS Winner,
               win_margin_value::INT                       AS "Margin (Runs)",
               CASE WHEN match_won_by = team1 THEN team2
                    ELSE team1 END                         AS Loser,
               venue                                       AS Venue,
               season                                      AS Season
        FROM matches
        WHERE win_margin_type = 'runs'
          AND win_margin_value IS NOT NULL
          AND {season_filter}
        ORDER BY win_margin_value DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _biggest_wins_by_wickets(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT match_won_by                                AS Winner,
               win_margin_value::INT                       AS "Wickets Remaining",
               CASE WHEN match_won_by = team1 THEN team2
                    ELSE team1 END                         AS Loser,
               venue                                       AS Venue,
               season                                      AS Season
        FROM matches
        WHERE win_margin_type = 'wickets'
          AND win_margin_value IS NOT NULL
          AND {season_filter}
        ORDER BY win_margin_value DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _narrowest_victories(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 33,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 33)
    return query(
        f"""
        SELECT match_won_by                                AS Winner,
               win_margin_value::INT                       AS Margin,
               win_margin_type                             AS "Margin Type",
               CASE WHEN match_won_by = team1 THEN team2
                    ELSE team1 END                         AS Loser,
               venue                                       AS Venue,
               season                                      AS Season
        FROM matches
        WHERE win_margin_value IS NOT NULL
          AND {season_filter}
          AND (
                (win_margin_type = 'runs'    AND win_margin_value BETWEEN 1 AND 2)
             OR (win_margin_type = 'wickets' AND win_margin_value = 1)
          )
        ORDER BY win_margin_value ASC, season
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _highest_successful_chases(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT team                                                                AS Team,
               runs_scored::INT                                                    AS Score,
               wickets_lost::INT                                                   AS Wickets,
               opponent                                                            AS "Vs",
               target_to_win::INT                                                  AS Target,
               venue                                                               AS Venue,
               season                                                              AS Season
        FROM team_match_results
        WHERE successful_chase
          AND {season_filter}
        ORDER BY Score DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _lowest_totals_defended(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT team                                                                AS Team,
               runs_scored::INT                                                    AS Score,
               opponent                                                            AS "Vs",
               win_margin_value::INT                                               AS "Won By (Runs)",
               venue                                                               AS Venue,
               season                                                              AS Season
        FROM team_match_results
        WHERE successful_defense
          AND {season_filter}
        ORDER BY Score ASC
        LIMIT {limit}
        """
    )


# ═══════════════════════════════════════════════════════════════════════
#  MATCH RECORD QUERIES
# ═══════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=3600)
def _highest_aggregate_matches(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("m.season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT (COALESCE(m.team1_score, 0) + COALESCE(m.team2_score, 0))::INT AS "Aggregate",
               m.team1                                                         AS "Team 1",
               m.team1_score::INT                                              AS "Score 1",
               m.team2                                                         AS "Team 2",
               m.team2_score::INT                                              AS "Score 2",
               m.venue                                                         AS Venue,
               m.season                                                        AS Season
        FROM matches m
        WHERE m.team1_score IS NOT NULL
          AND m.team2_score IS NOT NULL
          AND {season_filter}
        ORDER BY "Aggregate" DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_sixes_match(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("m.season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
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
          AND {season_filter}
        GROUP BY b.match_id, m.team1, m.team1_score, m.team2, m.team2_score,
                 m.venue, m.season
        ORDER BY Sixes DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _super_over_matches(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("m.season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT m.team1                                                         AS "Team 1",
               m.team1_score::INT                                              AS "Score 1",
               m.team2                                                         AS "Team 2",
               m.team2_score::INT                                              AS "Score 2",
               m.match_won_by                                                  AS Winner,
               m.venue                                                         AS Venue,
               m.season                                                        AS Season
        FROM matches m
        WHERE m.is_super_over_match = true
          AND {season_filter}
        ORDER BY m.season DESC, m.date DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _last_ball_finishes(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 51,
) -> pd.DataFrame:
    season_filter = _season_condition("m.season", season_range)
    limit = _sanitize_limit(limit, 51)
    return query(
        f"""
        WITH decisive_last_ball AS (
            SELECT
                b.match_id,
                b.team_runs::INT                                            AS runs_after_ball,
                (b.team_runs - b.runs_total)::INT                           AS runs_before_ball,
                COALESCE(m.actual_chase_target, m.team1_score + 1)::INT     AS target_to_win,
                ROW_NUMBER() OVER (
                    PARTITION BY b.match_id
                    ORDER BY b.over DESC, b.ball DESC
                )                                                           AS ball_order
            FROM balls b
            JOIN matches m ON b.match_id = m.match_id
            WHERE b.innings = 2
              AND b.valid_ball = true
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
        JOIN decisive_last_ball lb ON m.match_id = lb.match_id
        WHERE m.match_won_by IS NOT NULL
          AND m.is_super_over_match = false
          AND m.win_margin_value IS NOT NULL
          AND lb.ball_order = 1
          AND {season_filter}
          AND (
                (
                    m.match_won_by = m.team2
                    AND lb.runs_before_ball < lb.target_to_win
                    AND lb.runs_after_ball >= lb.target_to_win
                )
             OR (
                    m.match_won_by = m.team1
                    AND lb.target_to_win - lb.runs_before_ball BETWEEN 1 AND 6
                    AND lb.runs_after_ball < lb.target_to_win
                )
          )
        ORDER BY m.season DESC, m.date DESC
        LIMIT {limit}
        """
    )


# ═══════════════════════════════════════════════════════════════════════
#  MILESTONES QUERIES
# ═══════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=3600)
def _runs_club(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 9,
    min_runs: int = 5000,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 9)
    min_runs = max(0, int(min_runs))
    return query(
        f"""
        SELECT batter                                                         AS Player,
               SUM(runs)::INT                                                 AS Runs,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs) * 1.0
                     / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0), 2) AS Avg,
               ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 1)           AS SR,
               SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END)::INT              AS "100s",
               SUM(CASE WHEN is_fifty   THEN 1 ELSE 0 END)::INT              AS "50s"
        FROM player_batting
        WHERE {season_filter}
        GROUP BY batter
        HAVING SUM(runs) >= {min_runs}
        ORDER BY Runs DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _wickets_club(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 1,
    min_wickets: int = 200,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 1)
    min_wickets = max(0, int(min_wickets))
    return query(
        f"""
        SELECT bowler                                                         AS Player,
               SUM(wickets)::INT                                              AS Wickets,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs_conceded) * 6.0
                     / NULLIF(SUM(balls_bowled), 0), 2)                       AS Economy,
               ROUND(SUM(balls_bowled) * 1.0
                     / NULLIF(SUM(wickets), 0), 1)                            AS SR
        FROM player_bowling
        WHERE {season_filter}
        GROUP BY bowler
        HAVING SUM(wickets) >= {min_wickets}
        ORDER BY Wickets DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _sixes_club(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 42,
    min_sixes: int = 100,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 42)
    min_sixes = max(0, int(min_sixes))
    return query(
        f"""
        SELECT batter                                                         AS Player,
               SUM(sixes)::INT                                                AS Sixes,
               SUM(runs)::INT                                                 AS Runs,
               COUNT(*)::INT                                                  AS Innings,
               ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 1)           AS SR
        FROM player_batting
        WHERE {season_filter}
        GROUP BY batter
        HAVING SUM(sixes) >= {min_sixes}
        ORDER BY Sixes DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _matches_club(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 8,
    min_matches: int = 200,
) -> pd.DataFrame:
    season_filter_batting = _season_condition("season", season_range)
    season_filter_bowling = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 8)
    min_matches = max(1, int(min_matches))
    return query(
        f"""
        WITH all_players AS (
            SELECT batter AS player, match_id
            FROM player_batting
            WHERE {season_filter_batting}
            UNION
            SELECT bowler AS player, match_id
            FROM player_bowling
            WHERE {season_filter_bowling}
        )
        SELECT player                                  AS Player,
               COUNT(DISTINCT match_id)::INT           AS Matches
        FROM all_players
        GROUP BY player
        HAVING COUNT(DISTINCT match_id) >= {min_matches}
        ORDER BY Matches DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _orange_cap_history(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 18,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 18)
    return query(
        f"""
        WITH season_top AS (
            SELECT season,
                   batter,
                   SUM(runs)::INT AS runs,
                   COUNT(*)::INT AS innings,
                   ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 1) AS sr,
                   ROW_NUMBER() OVER (PARTITION BY season ORDER BY SUM(runs) DESC) AS rk
            FROM player_batting
            WHERE {season_filter}
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
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _purple_cap_history(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 18,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 18)
    return query(
        f"""
        WITH season_top AS (
            SELECT season,
                   bowler,
                   SUM(wickets)::INT AS wickets,
                   COUNT(*)::INT AS innings,
                   ROUND(SUM(runs_conceded) * 6.0 / NULLIF(SUM(balls_bowled), 0), 2) AS economy,
                   ROW_NUMBER() OVER (PARTITION BY season ORDER BY SUM(wickets) DESC) AS rk
            FROM player_bowling
            WHERE {season_filter}
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
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_potm_awards(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT player_of_match                         AS Player,
               COUNT(*)::INT                           AS Awards
        FROM matches
        WHERE player_of_match IS NOT NULL
          AND {season_filter}
        GROUP BY player_of_match
        ORDER BY Awards DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=3600)
def _default_limits() -> dict[str, int]:
    return {
        "narrowest_victories": int(
            query(
                """
                SELECT COUNT(*) AS total
                FROM matches
                WHERE win_margin_value IS NOT NULL
                  AND (
                        (win_margin_type = 'runs' AND win_margin_value BETWEEN 1 AND 2)
                     OR (win_margin_type = 'wickets' AND win_margin_value = 1)
                  )
                """
            ).iloc[0]["total"]
        ),
        "super_over_matches": int(
            query("SELECT COUNT(*) AS total FROM matches WHERE is_super_over_match = true").iloc[0]["total"]
        ),
        "last_ball_finishes": int(
            query(
                """
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
                SELECT COUNT(*) AS total
                FROM matches m
                JOIN last_over lo ON m.match_id = lo.match_id
                WHERE m.match_won_by IS NOT NULL
                  AND m.win_margin_value IS NOT NULL
                  AND (
                        (m.win_margin_type = 'wickets' AND m.win_margin_value <= 2)
                     OR (m.win_margin_type = 'runs'    AND m.win_margin_value <= 3)
                  )
                """
            ).iloc[0]["total"]
        ),
        "runs_club": int(
            query(
                "SELECT COUNT(*) AS total FROM (SELECT batter FROM player_batting GROUP BY batter HAVING SUM(runs) >= 5000)"
            ).iloc[0]["total"]
        ),
        "wickets_club": int(
            query(
                "SELECT COUNT(*) AS total FROM (SELECT bowler FROM player_bowling GROUP BY bowler HAVING SUM(wickets) >= 200)"
            ).iloc[0]["total"]
        ),
        "sixes_club": int(
            query(
                "SELECT COUNT(*) AS total FROM (SELECT batter FROM player_batting GROUP BY batter HAVING SUM(sixes) >= 100)"
            ).iloc[0]["total"]
        ),
        "matches_club": int(
            query(
                """
                WITH all_players AS (
                    SELECT batter AS player, match_id FROM player_batting
                    UNION
                    SELECT bowler AS player, match_id FROM player_bowling
                )
                SELECT COUNT(*) AS total
                FROM (
                    SELECT player
                    FROM all_players
                    GROUP BY player
                    HAVING COUNT(DISTINCT match_id) >= 200
                )
                """
            ).iloc[0]["total"]
        ),
        "orange_cap_history": len(ALL_SEASONS),
        "purple_cap_history": len(ALL_SEASONS),
    }


DEFAULT_LIMITS = _default_limits()


# ═══════════════════════════════════════════════════════════════════════
#  VISUAL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════


def _visual_spec(
    visual_id: str,
    title: str,
    default_limit: int,
    extra_controls: list | None = None,
) -> VisualSpec:
    controls = [
        season_range_control(),
        limit_control(default=default_limit, minimum=1, maximum=max(100, default_limit)),
    ]
    if extra_controls:
        controls.extend(extra_controls)
    return VisualSpec(id=visual_id, title=title, controls=controls)


VISUAL_SPECS = {
    "highest_individual_scores": _visual_spec("highest_individual_scores", "Highest Individual Scores", 25),
    "fastest_fifties": _visual_spec("fastest_fifties", "Fastest Fifties", 15),
    "fastest_centuries": _visual_spec("fastest_centuries", "Fastest Centuries", 10),
    "most_sixes_innings": _visual_spec("most_sixes_innings", "Most Sixes in an Innings", 15),
    "most_fours_innings": _visual_spec("most_fours_innings", "Most Fours in an Innings", 15),
    "highest_sr_innings": _visual_spec(
        "highest_sr_innings",
        "Highest Strike Rate Innings",
        15,
        [
            number_control(
                "min_balls",
                "Minimum balls faced",
                default=20,
                minimum=1,
                maximum=120,
                help_text="Defaults to the current 20-ball qualification rule.",
            )
        ],
    ),
    "slowest_fifties": _visual_spec("slowest_fifties", "Slowest Fifties", 10),
    "most_runs_single_season": _visual_spec("most_runs_single_season", "Most Runs in a Single Season", 15),
    "most_consecutive_ducks": _visual_spec(
        "most_consecutive_ducks",
        "Most Consecutive Ducks",
        15,
        [
            number_control(
                "min_streak",
                "Minimum streak length",
                default=3,
                minimum=2,
                maximum=10,
                help_text="Defaults to the current three-duck cutoff.",
            )
        ],
    ),
    "best_bowling_figures": _visual_spec("best_bowling_figures", "Best Bowling Figures", 25),
    "most_economical_spells": _visual_spec(
        "most_economical_spells",
        "Most Economical Spells",
        15,
        [
            number_control(
                "min_balls",
                "Minimum balls bowled",
                default=24,
                minimum=1,
                maximum=24,
                help_text="24 preserves the current completed-spell record definition.",
            )
        ],
    ),
    "most_expensive_spells": _visual_spec("most_expensive_spells", "Most Expensive Spells", 15),
    "most_wickets_single_season": _visual_spec("most_wickets_single_season", "Most Wickets in a Single Season", 15),
    "most_maidens_career": _visual_spec("most_maidens_career", "Most Maiden Overs — Career", 15),
    "most_dots_career": _visual_spec("most_dots_career", "Most Dot Balls — Career", 15),
    "highest_team_totals": _visual_spec("highest_team_totals", "Highest Team Totals", 20),
    "lowest_team_totals": _visual_spec("lowest_team_totals", "Lowest Team Totals", 20),
    "biggest_wins_by_runs": _visual_spec("biggest_wins_by_runs", "Biggest Wins by Runs", 15),
    "biggest_wins_by_wickets": _visual_spec("biggest_wins_by_wickets", "Biggest Wins by Wickets", 15),
    "narrowest_victories": _visual_spec(
        "narrowest_victories",
        "Narrowest Victories",
        DEFAULT_LIMITS["narrowest_victories"],
    ),
    "highest_successful_chases": _visual_spec("highest_successful_chases", "Highest Successful Chases", 15),
    "lowest_totals_defended": _visual_spec("lowest_totals_defended", "Lowest Totals Defended", 15),
    "highest_aggregate_matches": _visual_spec("highest_aggregate_matches", "Highest Aggregate Matches", 15),
    "most_sixes_match": _visual_spec("most_sixes_match", "Most Sixes in a Single Match", 15),
    "super_over_matches": _visual_spec(
        "super_over_matches",
        "Super Over Matches",
        DEFAULT_LIMITS["super_over_matches"],
    ),
    "last_ball_finishes": _visual_spec(
        "last_ball_finishes",
        "Last-Ball Finishes",
        DEFAULT_LIMITS["last_ball_finishes"],
    ),
    "runs_club": _visual_spec(
        "runs_club",
        "Runs Club Members",
        DEFAULT_LIMITS["runs_club"],
        [
            number_control(
                "min_runs",
                "Minimum runs",
                default=5000,
                minimum=500,
                maximum=10000,
                step=100,
                help_text="Defaults to the current 5,000-run club threshold.",
            )
        ],
    ),
    "wickets_club": _visual_spec(
        "wickets_club",
        "Wickets Club Members",
        DEFAULT_LIMITS["wickets_club"],
        [
            number_control(
                "min_wickets",
                "Minimum wickets",
                default=200,
                minimum=25,
                maximum=300,
                step=5,
                help_text="Defaults to the current 200-wicket club threshold.",
            )
        ],
    ),
    "sixes_club": _visual_spec(
        "sixes_club",
        "Sixes Club Members",
        DEFAULT_LIMITS["sixes_club"],
        [
            number_control(
                "min_sixes",
                "Minimum sixes",
                default=100,
                minimum=25,
                maximum=400,
                step=5,
                help_text="Defaults to the current 100-sixes club threshold.",
            )
        ],
    ),
    "matches_club": _visual_spec(
        "matches_club",
        "Matches Club Members",
        DEFAULT_LIMITS["matches_club"],
        [
            number_control(
                "min_matches",
                "Minimum matches",
                default=200,
                minimum=25,
                maximum=300,
                step=5,
                help_text="Defaults to the current 200-match club threshold.",
            )
        ],
    ),
    "orange_cap_history": _visual_spec(
        "orange_cap_history",
        "Orange Cap History",
        DEFAULT_LIMITS["orange_cap_history"],
    ),
    "purple_cap_history": _visual_spec(
        "purple_cap_history",
        "Purple Cap History",
        DEFAULT_LIMITS["purple_cap_history"],
    ),
    "most_potm_awards": _visual_spec("most_potm_awards", "Most Player of the Match Awards", 15),
}


# ═══════════════════════════════════════════════════════════════════════
#  RENDERING
# ═══════════════════════════════════════════════════════════════════════


def _render_record_visual(
    spec: VisualSpec,
    fetcher,
    *,
    chart_x: str | None = None,
    chart_y: str | None = None,
    chart_title: str | None = None,
    chart_height: int = 420,
) -> pd.DataFrame:
    st.markdown(f"#### {spec.title}")
    control_values = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, control_values))
    try:
        df = fetcher(control_values)

        if chart_x and chart_y:
            render_bar_chart(df, x=chart_x, y=chart_y, title=chart_title or spec.title, height=chart_height)

        render_dataframe(df, spec.empty_state_help)
        return df
    except Exception as exc:
        LOGGER.exception("Failed to render records visual '%s'", spec.id)
        st.error(f"Could not load {spec.title}.")
        st.caption("This card failed, but the rest of the page is still available.")
        with st.expander("Error details"):
            st.code(f"{type(exc).__name__}: {exc}")
        return pd.DataFrame()


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
    _render_record_visual(
        VISUAL_SPECS["highest_individual_scores"],
        lambda controls: _highest_individual_scores(controls["season_range"], controls["limit"]),
    )
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["fastest_fifties"],
            lambda controls: _fastest_fifties(controls["season_range"], controls["limit"]),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["fastest_centuries"],
            lambda controls: _fastest_centuries(controls["season_range"], controls["limit"]),
        )

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["most_sixes_innings"],
            lambda controls: _most_sixes_innings(controls["season_range"], controls["limit"]),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["most_fours_innings"],
            lambda controls: _most_fours_innings(controls["season_range"], controls["limit"]),
        )

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["highest_sr_innings"],
            lambda controls: _highest_sr_innings(
                controls["season_range"],
                controls["limit"],
                controls["min_balls"],
            ),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["slowest_fifties"],
            lambda controls: _slowest_fifties(controls["season_range"], controls["limit"]),
        )

    st.divider()
    _render_record_visual(
        VISUAL_SPECS["most_runs_single_season"],
        lambda controls: _most_runs_single_season(controls["season_range"], controls["limit"]),
    )

    st.divider()
    _render_record_visual(
        VISUAL_SPECS["most_consecutive_ducks"],
        lambda controls: _most_consecutive_ducks(
            controls["season_range"],
            controls["limit"],
            controls["min_streak"],
        ),
    )


# ── BOWLING RECORDS ───────────────────────────────────────────────────
with tab_bowl:
    _render_record_visual(
        VISUAL_SPECS["best_bowling_figures"],
        lambda controls: _best_bowling_figures(controls["season_range"], controls["limit"]),
    )
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["most_economical_spells"],
            lambda controls: _most_economical_spells(
                controls["season_range"],
                controls["limit"],
                controls["min_balls"],
            ),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["most_expensive_spells"],
            lambda controls: _most_expensive_spells(controls["season_range"], controls["limit"]),
        )

    st.divider()
    _render_record_visual(
        VISUAL_SPECS["most_wickets_single_season"],
        lambda controls: _most_wickets_single_season(controls["season_range"], controls["limit"]),
    )

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["most_maidens_career"],
            lambda controls: _most_maidens_career(controls["season_range"], controls["limit"]),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["most_dots_career"],
            lambda controls: _most_dots_career(controls["season_range"], controls["limit"]),
        )


# ── TEAM RECORDS ──────────────────────────────────────────────────────
with tab_team:
    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["highest_team_totals"],
            lambda controls: _highest_team_totals(controls["season_range"], controls["limit"]),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["lowest_team_totals"],
            lambda controls: _lowest_team_totals(controls["season_range"], controls["limit"]),
        )

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["biggest_wins_by_runs"],
            lambda controls: _biggest_wins_by_runs(controls["season_range"], controls["limit"]),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["biggest_wins_by_wickets"],
            lambda controls: _biggest_wins_by_wickets(controls["season_range"], controls["limit"]),
        )

    st.divider()
    _render_record_visual(
        VISUAL_SPECS["narrowest_victories"],
        lambda controls: _narrowest_victories(controls["season_range"], controls["limit"]),
    )

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["highest_successful_chases"],
            lambda controls: _highest_successful_chases(controls["season_range"], controls["limit"]),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["lowest_totals_defended"],
            lambda controls: _lowest_totals_defended(controls["season_range"], controls["limit"]),
        )


# ── MATCH RECORDS ─────────────────────────────────────────────────────
with tab_match:
    _render_record_visual(
        VISUAL_SPECS["highest_aggregate_matches"],
        lambda controls: _highest_aggregate_matches(controls["season_range"], controls["limit"]),
    )

    st.divider()
    _render_record_visual(
        VISUAL_SPECS["most_sixes_match"],
        lambda controls: _most_sixes_match(controls["season_range"], controls["limit"]),
    )

    st.divider()
    _render_record_visual(
        VISUAL_SPECS["super_over_matches"],
        lambda controls: _super_over_matches(controls["season_range"], controls["limit"]),
    )

    st.divider()
    _render_record_visual(
        VISUAL_SPECS["last_ball_finishes"],
        lambda controls: _last_ball_finishes(controls["season_range"], controls["limit"]),
    )


# ── MILESTONES ────────────────────────────────────────────────────────
with tab_mile:
    st.subheader("Elite Club Members")
    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["runs_club"],
            lambda controls: _runs_club(
                controls["season_range"],
                controls["limit"],
                controls["min_runs"],
            ),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["wickets_club"],
            lambda controls: _wickets_club(
                controls["season_range"],
                controls["limit"],
                controls["min_wickets"],
            ),
        )

    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["sixes_club"],
            lambda controls: _sixes_club(
                controls["season_range"],
                controls["limit"],
                controls["min_sixes"],
            ),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["matches_club"],
            lambda controls: _matches_club(
                controls["season_range"],
                controls["limit"],
                controls["min_matches"],
            ),
        )

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _render_record_visual(
            VISUAL_SPECS["orange_cap_history"],
            lambda controls: _orange_cap_history(controls["season_range"], controls["limit"]),
        )
    with c2:
        _render_record_visual(
            VISUAL_SPECS["purple_cap_history"],
            lambda controls: _purple_cap_history(controls["season_range"], controls["limit"]),
        )

    st.divider()
    _render_record_visual(
        VISUAL_SPECS["most_potm_awards"],
        lambda controls: _most_potm_awards(controls["season_range"], controls["limit"]),
        chart_x="Player",
        chart_y="Awards",
        chart_title="Most Player of the Match Awards",
        chart_height=500,
    )
