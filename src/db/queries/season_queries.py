"""Season-related DuckDB queries."""

from src.db.connection import query


def get_season_overview():
    """Get overview stats for all seasons."""
    return query("SELECT * FROM season_meta ORDER BY season")


def get_season_matches(season):
    """Get all matches in a specific season."""
    return query(
        """
        SELECT * FROM matches
        WHERE season = ?
        ORDER BY date
        """,
        [season],
    )


def get_season_top_batters(season, limit=10):
    """Top run scorers in a specific season."""
    return query(
        """
        SELECT
            batter AS player,
            batting_team AS team,
            COUNT(DISTINCT match_id) AS matches,
            SUM(runs) AS total_runs,
            ROUND(SUM(runs) * 1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END), 0), 2) AS average,
            ROUND(SUM(runs) * 100.0 / NULLIF(SUM(balls), 0), 2) AS strike_rate,
            SUM(sixes) AS sixes,
            SUM(fours) AS fours
        FROM player_batting
        WHERE season = ?
        GROUP BY batter, batting_team
        ORDER BY total_runs DESC
        LIMIT ?
        """,
        [season, limit],
    )
