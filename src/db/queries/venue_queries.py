"""Venue-related DuckDB queries."""

from src.db.connection import query


def get_all_venues():
    """Get summary stats for all venues."""
    return query("SELECT * FROM venues ORDER BY total_matches DESC")


def get_venue_detail(venue_name):
    """Get detailed stats for a specific venue."""
    return query("SELECT * FROM venues WHERE venue = ?", [venue_name])
