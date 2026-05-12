"""DuckDB query helpers for the IPL Analytics Platform."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).parent.parent.parent / "Data" / "processed"
LOGGER = logging.getLogger(__name__)

PARQUET_VIEWS = {
    "balls": "ball_by_ball.parquet",
    "matches": "match_summary.parquet",
    "player_season": "player_season.parquet",
    "player_batting": "player_batting_match.parquet",
    "player_bowling": "player_bowling_match.parquet",
    "team_match_results": "team_match_results.parquet",
    "over_summary": "over_summary.parquet",
    "innings_tags": "innings_tags.parquet",
    "player_season_metrics": "player_season_metrics.parquet",
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


def get_connection():
    """Return a fresh DuckDB connection with all parquet views registered."""
    conn = duckdb.connect()
    for statement in _view_statements():
        conn.execute(statement)
    return conn


def query(sql: str, params: list = None):
    """Execute a SQL query against a fresh DuckDB connection."""
    normalized_params = tuple(params) if params is not None else None
    last_error: duckdb.Error | None = None

    for attempt in range(1, 3):
        conn = get_connection()
        try:
            if normalized_params is None:
                return conn.execute(sql).df()
            return conn.execute(sql, normalized_params).df()
        except duckdb.Error as exc:
            last_error = exc
            LOGGER.exception("DuckDB query failed on attempt %s/2", attempt)
        finally:
            conn.close()

    if last_error is not None:
        raise last_error
    raise RuntimeError("DuckDB query failed without raising a DuckDB error.")


@lru_cache(maxsize=1)
def _view_statements() -> tuple[str, ...]:
    """Build view registration SQL once and log missing parquet files once."""
    statements: list[str] = []
    missing: list[str] = []

    for view_name, filename in PARQUET_VIEWS.items():
        filepath = DATA_DIR / filename
        if filepath.exists():
            statements.append(
                f"CREATE VIEW {view_name} AS SELECT * FROM '{filepath}'"
            )
        else:
            missing.append(f"{view_name} -> {filepath}")

    if missing:
        LOGGER.warning(
            "Missing parquet files (views not created):\n  " + "\n  ".join(missing)
        )

    return tuple(statements)
