"""Team-related DuckDB queries."""

from src.db.connection import query


def get_team_all_time_record(season_range=(2008, 2025)):
    """All-time win/loss record for every team."""
    return query(
        """
        SELECT
            team,
            SUM(matches) AS matches,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(no_results) AS no_results,
            ROUND(SUM(wins) * 100.0 / NULLIF(SUM(matches), 0), 1) AS win_pct
        FROM team_season
        WHERE season BETWEEN ? AND ?
        GROUP BY team
        ORDER BY win_pct DESC
        """,
        [season_range[0], season_range[1]],
    )


def get_team_season_stats(team_name, season_range=(2008, 2025)):
    """Season-by-season stats for a specific team."""
    return query(
        """
        SELECT *
        FROM team_season
        WHERE team = ? AND season BETWEEN ? AND ?
        ORDER BY season
        """,
        [team_name, season_range[0], season_range[1]],
    )


def get_head_to_head(team1, team2, season_range=(2008, 2025)):
    """Head-to-head record between two teams."""
    return query(
        """
        SELECT
            season, date, venue,
            team1, team1_score, team1_wickets,
            team2, team2_score, team2_wickets,
            match_won_by, win_margin_value, win_margin_type,
            stage
        FROM matches
        WHERE season BETWEEN ? AND ?
          AND ((team1 = ? AND team2 = ?) OR (team1 = ? AND team2 = ?))
        ORDER BY date
        """,
        [season_range[0], season_range[1], team1, team2, team2, team1],
    )
