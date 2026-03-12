"""Matchup-related DuckDB queries."""

from src.db.connection import query


def get_batter_vs_bowler(batter, bowler):
    """Complete matchup between a specific batter and bowler."""
    return query(
        """
        SELECT *
        FROM matchups
        WHERE batter = ? AND bowler = ?
        """,
        [batter, bowler],
    )


def get_top_rivalries(min_balls=30, limit=50):
    """Most contested batter-bowler matchups by balls faced."""
    return query(
        """
        SELECT batter, bowler, balls, runs, dismissals, strike_rate,
               dot_pct, boundary_pct, dominance
        FROM matchups
        WHERE balls >= ?
        ORDER BY balls DESC
        LIMIT ?
        """,
        [min_balls, limit],
    )
