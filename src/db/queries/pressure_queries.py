"""Pressure & momentum DuckDB queries."""

from src.db.connection import query


def get_dot_ball_outcomes(min_consecutive=1):
    """What happens after N consecutive dot balls?"""
    return query(
        """
        SELECT *
        FROM dot_sequences
        WHERE consecutive_dots_before >= ?
        ORDER BY consecutive_dots_before, count DESC
        """,
        [min_consecutive],
    )


def get_chase_success_by_target_range(season_range=(2008, 2026)):
    """Chase success rate bucketed by target range."""
    return query(
        """
        SELECT
            CASE
                WHEN target_to_win - 1 BETWEEN 100 AND 120 THEN '100-120'
                WHEN target_to_win - 1 BETWEEN 121 AND 140 THEN '121-140'
                WHEN target_to_win - 1 BETWEEN 141 AND 160 THEN '141-160'
                WHEN target_to_win - 1 BETWEEN 161 AND 180 THEN '161-180'
                WHEN target_to_win - 1 BETWEEN 181 AND 200 THEN '181-200'
                WHEN target_to_win - 1 > 200 THEN '200+'
                ELSE 'Below 100'
            END AS target_range,
            COUNT(*) AS total_matches,
            SUM(CASE WHEN successful_chase THEN 1 ELSE 0 END) AS chase_wins,
            ROUND(
                SUM(CASE WHEN successful_chase THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                1
            ) AS chase_win_pct
        FROM team_match_results
        WHERE season BETWEEN ? AND ?
          AND chasing
          AND innings_complete
          AND target_to_win IS NOT NULL
        GROUP BY target_range
        ORDER BY target_range
        """,
        [season_range[0], season_range[1]],
    )
