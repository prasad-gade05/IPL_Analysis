"""DuckDB connection singleton for the IPL Analytics Platform."""

import duckdb
import streamlit as st
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "Data" / "processed"

PARQUET_VIEWS = {
    "balls": "ball_by_ball.parquet",
    "matches": "match_summary.parquet",
    "player_season": "player_season.parquet",
    "player_batting": "player_batting_match.parquet",
    "player_bowling": "player_bowling_match.parquet",
    "matchups": "matchups.parquet",
    "venues": "venue_stats.parquet",
    "partnerships": "partnerships.parquet",
    "dot_sequences": "dot_sequences.parquet",
    "powerplay": "powerplay_stats.parquet",
    "season_meta": "season_structure.parquet",
    "dismissals": "dismissal_patterns.parquet",
    "dismissals_phase": "dismissal_by_phase.parquet",
    "team_season": "team_season.parquet",
    "points_table": "points_table.parquet",
}


@st.cache_resource
def get_connection():
    """Return a singleton DuckDB connection with all parquet views registered."""
    conn = duckdb.connect()

    missing = []
    for view_name, filename in PARQUET_VIEWS.items():
        filepath = DATA_DIR / filename
        if filepath.exists():
            conn.execute(
                f"CREATE VIEW IF NOT EXISTS {view_name} AS SELECT * FROM '{filepath}'"
            )
        else:
            missing.append(f"{view_name} -> {filepath}")

    if missing:
        import logging
        logging.warning(
            "Missing parquet files (views not created):\n  " + "\n  ".join(missing)
        )

    return conn


def query(sql: str, params: list = None):
    """Execute a SQL query and return a pandas DataFrame."""
    conn = get_connection()
    if params:
        return conn.execute(sql, params).df()
    return conn.execute(sql).df()
