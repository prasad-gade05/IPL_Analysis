"""Player-related DuckDB queries."""

from src.db.connection import query


def get_all_time_top_batters(limit=25, min_innings=10, season_range=(2008, 2025)):
    """Top run scorers of all time within season range."""
    return query(
        """
        SELECT
            batter AS player,
            COUNT(DISTINCT match_id) AS matches,
            COUNT(*) AS innings,
            SUM(runs) AS total_runs,
            MAX(runs) AS highest_score,
            ROUND(SUM(runs) * 1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0), 2) AS average,
            ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 2) AS strike_rate,
            SUM(CASE WHEN is_fifty THEN 1 ELSE 0 END) AS fifties,
            SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END) AS hundreds,
            SUM(fours) AS fours,
            SUM(sixes) AS sixes
        FROM player_batting
        WHERE season BETWEEN ? AND ?
        GROUP BY batter
        HAVING COUNT(*) >= ?
        ORDER BY total_runs DESC
        LIMIT ?
        """,
        [season_range[0], season_range[1], min_innings, limit],
    )


def get_all_time_top_bowlers(limit=25, min_overs=20, season_range=(2008, 2025)):
    """Top wicket takers of all time within season range."""
    return query(
        """
        SELECT
            bowler AS player,
            COUNT(DISTINCT match_id) AS matches,
            ROUND(SUM(balls_bowled) / 6.0, 1) AS overs,
            SUM(wickets) AS total_wickets,
            ROUND(SUM(runs_conceded) * 1.0 / NULLIF(SUM(wickets), 0), 2) AS average,
            ROUND(SUM(runs_conceded) * 6.0 / NULLIF(SUM(balls_bowled), 0), 2) AS economy,
            ROUND(SUM(balls_bowled) * 1.0 / NULLIF(SUM(wickets), 0), 2) AS bowling_sr,
            SUM(dots_bowled) AS dot_balls
        FROM player_bowling
        WHERE season BETWEEN ? AND ?
        GROUP BY bowler
        HAVING SUM(balls_bowled) / 6.0 >= ?
        ORDER BY total_wickets DESC
        LIMIT ?
        """,
        [season_range[0], season_range[1], min_overs, limit],
    )


def get_player_career_batting(player_name, season_range=(2008, 2025)):
    """Season-by-season batting stats for a player."""
    return query(
        """
        SELECT
            season,
            batting_team AS team,
            COUNT(DISTINCT match_id) AS matches,
            COUNT(*) AS innings,
            SUM(CASE WHEN NOT was_out THEN 1 ELSE 0 END) AS not_outs,
            SUM(runs) AS runs,
            MAX(runs) AS highest_score,
            ROUND(SUM(runs) * 1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0), 2) AS average,
            ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 2) AS strike_rate,
            SUM(CASE WHEN is_fifty THEN 1 ELSE 0 END) AS fifties,
            SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END) AS hundreds,
            SUM(fours) AS fours,
            SUM(sixes) AS sixes
        FROM player_batting
        WHERE batter = ? AND season BETWEEN ? AND ?
        GROUP BY season, batting_team
        ORDER BY season
        """,
        [player_name, season_range[0], season_range[1]],
    )


def get_player_matchups(player_name, min_balls=6, as_batter=True):
    """Get batter-vs-bowler matchup data for a player."""
    if as_batter:
        return query(
            """
            SELECT bowler, balls, runs, dismissals, strike_rate, dot_pct,
                   boundary_pct, average, dominance
            FROM matchups
            WHERE batter = ? AND balls >= ?
            ORDER BY balls DESC
            """,
            [player_name, min_balls],
        )
    else:
        return query(
            """
            SELECT batter, balls, runs, dismissals, strike_rate, dot_pct,
                   boundary_pct, average, dominance
            FROM matchups
            WHERE bowler = ? AND balls >= ?
            ORDER BY balls DESC
            """,
            [player_name, min_balls],
        )
