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

RUNTIME_REBUILT_VIEWS = {
    "matches",
    "matchups",
    "over_summary",
    "player_batting",
    "player_bowling",
    "powerplay",
    "team_match_results",
    "team_season",
    "points_table",
    "venues",
}

NON_RETRYABLE_QUERY_ERRORS = (
    duckdb.BinderException,
    duckdb.CatalogException,
    duckdb.ConversionException,
    duckdb.InvalidInputException,
    duckdb.InvalidTypeException,
    duckdb.NotImplementedException,
    duckdb.OutOfRangeException,
    duckdb.ParserException,
    duckdb.PermissionException,
    duckdb.SyntaxException,
    duckdb.TypeMismatchException,
)


def get_connection():
    """Return a fresh DuckDB connection with all parquet views registered."""
    conn = duckdb.connect()
    try:
        for statement in _view_statements():
            try:
                conn.execute(statement)
            except duckdb.Error:
                LOGGER.exception(
                    "DuckDB view registration failed for statement: %s",
                    statement.strip().splitlines()[0],
                )
                raise
        return conn
    except duckdb.Error:
        conn.close()
        raise


def query(sql: str, params: list = None):
    """Execute a SQL query against a fresh DuckDB connection."""
    normalized_params = tuple(params) if params is not None else None

    for attempt in range(1, 3):
        conn = get_connection()
        try:
            if normalized_params is None:
                return conn.execute(sql).df()
            return conn.execute(sql, normalized_params).df()
        except duckdb.Error as exc:
            if isinstance(exc, NON_RETRYABLE_QUERY_ERRORS):
                LOGGER.exception("DuckDB query failed with non-retryable SQL error")
                raise

            LOGGER.exception("DuckDB query failed on attempt %s/2", attempt)
            if attempt == 2:
                raise
        finally:
            conn.close()

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
                f"CREATE VIEW {_source_view_name(view_name)} AS SELECT * FROM '{filepath}'"
            )
        else:
            missing.append(f"{view_name} -> {filepath}")

    statements.extend(_derived_view_statements())

    if missing:
        LOGGER.warning(
            "Missing parquet files (views not created):\n  " + "\n  ".join(missing)
        )

    return tuple(statements)


def _source_view_name(view_name: str) -> str:
    """Return the parquet-backed source view name for a logical runtime view."""
    if view_name in RUNTIME_REBUILT_VIEWS:
        return f"{view_name}_source"
    return view_name


def _derived_view_statements() -> tuple[str, ...]:
    """Return runtime views that correct cricket-domain outcome and innings logic."""
    return (
        """
        CREATE VIEW matches AS
        WITH super_over_winners AS (
            SELECT
                match_id,
                NULLIF(TRIM(first(superover_winner)), '') AS superover_winner
            FROM balls
            GROUP BY match_id
        ),
        resolved AS (
            SELECT
                m.*,
                CASE
                    WHEN m.result_type = 'tie' AND sow.superover_winner IS NOT NULL
                        THEN sow.superover_winner
                    WHEN TRIM(COALESCE(m.match_won_by, '')) IN ('', 'Unknown')
                        THEN NULL
                    ELSE m.match_won_by
                END AS resolved_match_won_by
            FROM matches_source m
            LEFT JOIN super_over_winners sow USING (match_id)
        )
        SELECT
            resolved.* EXCLUDE (match_won_by, batting_first_won, resolved_match_won_by),
            resolved.resolved_match_won_by AS match_won_by,
            CASE
                WHEN resolved.resolved_match_won_by IS NULL THEN NULL
                WHEN resolved.team1 = resolved.resolved_match_won_by THEN TRUE
                ELSE FALSE
            END AS batting_first_won
        FROM resolved
        """,
        """
        CREATE VIEW player_batting AS
        WITH regular_balls AS (
            SELECT *
            FROM balls
            WHERE innings IN (1, 2)
        ),
        batting AS (
            SELECT
                match_id,
                season,
                batter,
                batting_team,
                innings,
                venue,
                SUM(runs_batter)::INT AS runs,
                SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS balls,
                SUM(CASE WHEN is_four THEN 1 ELSE 0 END)::INT AS fours,
                SUM(CASE WHEN is_six THEN 1 ELSE 0 END)::INT AS sixes,
                SUM(CASE WHEN is_dot THEN 1 ELSE 0 END)::INT AS dots_faced,
                MIN(bat_pos)::INT AS bat_position,
                SUM(
                    CASE
                        WHEN player_out = batter
                             AND wicket_kind NOT IN ('not_out', 'retired hurt')
                            THEN 1
                        ELSE 0
                    END
                ) > 0 AS was_out
            FROM regular_balls
            WHERE batter IS NOT NULL
            GROUP BY match_id, season, batter, batting_team, innings, venue
        )
        SELECT
            match_id,
            season,
            batter,
            batting_team,
            innings,
            venue,
            runs,
            balls,
            fours,
            sixes,
            dots_faced,
            bat_position,
            was_out,
            CASE
                WHEN balls > 0 THEN ROUND(runs * 100.0 / balls, 1)
                ELSE NULL
            END AS strike_rate,
            CASE
                WHEN balls > 0 THEN ROUND(dots_faced * 100.0 / balls, 1)
                ELSE NULL
            END AS dot_pct,
            runs >= 50 AS is_fifty,
            runs >= 100 AS is_hundred,
            runs = 0 AND was_out AS is_duck
        FROM batting
        """,
        """
        CREATE VIEW player_bowling AS
        WITH regular_balls AS (
            SELECT *
            FROM balls
            WHERE innings IN (1, 2)
        ),
        maiden_overs AS (
            SELECT
                match_id,
                innings,
                bowler,
                COUNT(*)::INT AS maidens
            FROM (
                SELECT
                    match_id,
                    innings,
                    bowler,
                    over
                FROM regular_balls
                WHERE bowler IS NOT NULL
                GROUP BY match_id, innings, bowler, over
                HAVING BOOL_OR(is_maiden)
            ) overs
            GROUP BY match_id, innings, bowler
        ),
        bowling AS (
            SELECT
                match_id,
                season,
                bowler,
                bowling_team,
                innings,
                venue,
                SUM(runs_bowler)::INT AS runs_conceded,
                SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS balls_bowled,
                SUM(CASE WHEN bowler_wicket THEN 1 ELSE 0 END)::INT AS wickets,
                SUM(CASE WHEN is_dot THEN 1 ELSE 0 END)::INT AS dots_bowled,
                SUM(CASE WHEN is_boundary THEN 1 ELSE 0 END)::INT AS boundaries_conceded
            FROM regular_balls
            WHERE bowler IS NOT NULL
            GROUP BY match_id, season, bowler, bowling_team, innings, venue
        )
        SELECT
            bowling.match_id,
            bowling.season,
            bowling.bowler,
            bowling.bowling_team,
            bowling.innings,
            bowling.venue,
            bowling.runs_conceded,
            bowling.balls_bowled,
            bowling.wickets,
            bowling.dots_bowled,
            bowling.boundaries_conceded,
            COALESCE(maiden_overs.maidens, 0) AS maidens,
            CASE
                WHEN bowling.balls_bowled > 0
                    THEN ROUND(bowling.runs_conceded * 6.0 / bowling.balls_bowled, 2)
                ELSE NULL
            END AS economy,
            CASE
                WHEN bowling.wickets > 0
                    THEN ROUND(bowling.balls_bowled * 1.0 / bowling.wickets, 1)
                ELSE NULL
            END AS bowling_sr,
            CASE
                WHEN bowling.balls_bowled > 0
                    THEN ROUND(bowling.dots_bowled * 100.0 / bowling.balls_bowled, 1)
                ELSE NULL
            END AS dot_pct
        FROM bowling
        LEFT JOIN maiden_overs
          ON bowling.match_id = maiden_overs.match_id
         AND bowling.innings = maiden_overs.innings
         AND bowling.bowler = maiden_overs.bowler
        """,
        """
        CREATE VIEW matchups AS
        WITH regular_balls AS (
            SELECT *
            FROM balls
            WHERE innings IN (1, 2)
        ),
        matchup_base AS (
            SELECT
                batter,
                bowler,
                SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS balls,
                SUM(runs_batter)::INT AS runs,
                SUM(CASE WHEN is_dot THEN 1 ELSE 0 END)::INT AS dots,
                SUM(CASE WHEN is_four THEN 1 ELSE 0 END)::INT AS fours,
                SUM(CASE WHEN is_six THEN 1 ELSE 0 END)::INT AS sixes,
                SUM(
                    CASE
                        WHEN player_out = batter AND bowler_wicket THEN 1
                        ELSE 0
                    END
                )::INT AS dismissals
            FROM regular_balls
            WHERE batter IS NOT NULL
              AND bowler IS NOT NULL
            GROUP BY batter, bowler
        )
        SELECT
            batter,
            bowler,
            balls,
            runs,
            dots,
            fours,
            sixes,
            dismissals,
            CASE
                WHEN balls > 0 THEN ROUND(runs * 100.0 / balls, 1)
                ELSE NULL
            END AS strike_rate,
            CASE
                WHEN balls > 0 THEN ROUND(dots * 100.0 / balls, 1)
                ELSE NULL
            END AS dot_pct,
            CASE
                WHEN balls > 0 THEN ROUND((fours + sixes) * 100.0 / balls, 1)
                ELSE NULL
            END AS boundary_pct,
            CASE
                WHEN dismissals > 0 THEN ROUND(runs * 1.0 / dismissals, 1)
                ELSE NULL
            END AS average
        FROM matchup_base
        """,
        """
        CREATE VIEW venues AS
        WITH innings_totals AS (
            SELECT
                match_id,
                innings,
                MAX(venue) AS venue,
                MAX(city) AS city,
                MAX(team_runs)::INT AS total_runs,
                MAX(team_wicket)::INT AS wickets,
                SUM(CASE WHEN is_boundary THEN 1 ELSE 0 END)::INT AS boundaries
            FROM balls
            WHERE innings IN (1, 2)
            GROUP BY match_id, innings
        ),
        venue_rollup AS (
            SELECT
                venue,
                city,
                COUNT(DISTINCT match_id)::INT AS total_matches,
                ROUND(AVG(total_runs), 1) AS avg_score,
                ROUND(AVG(wickets), 1) AS avg_wickets,
                ROUND(AVG(boundaries), 1) AS avg_boundaries
            FROM innings_totals
            GROUP BY venue, city
        ),
        first_innings AS (
            SELECT
                venue,
                ROUND(AVG(total_runs), 1) AS avg_first_innings
            FROM innings_totals
            WHERE innings = 1
            GROUP BY venue
        ),
        second_innings AS (
            SELECT
                venue,
                ROUND(AVG(total_runs), 1) AS avg_second_innings
            FROM innings_totals
            WHERE innings = 2
            GROUP BY venue
        ),
        batting_first_results AS (
            SELECT
                venue,
                ROUND(AVG(CASE WHEN batting_first_won THEN 1.0 ELSE 0.0 END) * 100.0, 1) AS bat_first_win_pct
            FROM matches
            WHERE batting_first_won IS NOT NULL
            GROUP BY venue
        )
        SELECT
            venue_rollup.venue,
            venue_rollup.city,
            venue_rollup.total_matches,
            venue_rollup.avg_score,
            venue_rollup.avg_wickets,
            venue_rollup.avg_boundaries,
            first_innings.avg_first_innings,
            second_innings.avg_second_innings,
            batting_first_results.bat_first_win_pct
        FROM venue_rollup
        LEFT JOIN first_innings
          ON venue_rollup.venue = first_innings.venue
        LEFT JOIN second_innings
          ON venue_rollup.venue = second_innings.venue
        LEFT JOIN batting_first_results
          ON venue_rollup.venue = batting_first_results.venue
        """,
        """
        CREATE VIEW powerplay AS
        WITH powerplay_base AS (
            SELECT
                match_id,
                innings,
                season,
                batting_team,
                SUM(runs_total)::INT AS pp_runs,
                SUM(
                    CASE
                        WHEN wicket_kind NOT IN ('not_out', 'retired hurt') THEN 1
                        ELSE 0
                    END
                )::INT AS pp_wickets,
                SUM(CASE WHEN is_dot THEN 1 ELSE 0 END)::INT AS pp_dots,
                SUM(CASE WHEN is_boundary THEN 1 ELSE 0 END)::INT AS pp_boundaries,
                SUM(CASE WHEN is_four THEN 1 ELSE 0 END)::INT AS pp_fours,
                SUM(CASE WHEN is_six THEN 1 ELSE 0 END)::INT AS pp_sixes,
                SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS pp_balls
            FROM balls
            WHERE innings IN (1, 2)
              AND over <= 6
            GROUP BY match_id, innings, season, batting_team
        )
        SELECT
            match_id,
            innings,
            season,
            batting_team,
            pp_runs,
            pp_wickets,
            pp_dots,
            pp_boundaries,
            pp_fours,
            pp_sixes,
            pp_balls,
            CASE
                WHEN pp_balls > 0 THEN ROUND(pp_runs * 6.0 / pp_balls, 2)
                ELSE NULL
            END AS pp_run_rate,
            CASE
                WHEN pp_balls > 0 THEN ROUND(pp_dots * 100.0 / pp_balls, 1)
                ELSE NULL
            END AS pp_dot_pct,
            CASE
                WHEN pp_balls > 0 THEN ROUND(pp_boundaries * 100.0 / pp_balls, 1)
                ELSE NULL
            END AS pp_boundary_pct
        FROM powerplay_base
        """,
        """
        CREATE VIEW over_summary AS
        WITH over_base AS (
            SELECT
                match_id,
                season,
                date,
                venue,
                stage,
                innings,
                match_phase,
                batting_team,
                bowling_team,
                over,
                bowler,
                COUNT(*)::INT AS deliveries_total,
                SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS legal_balls,
                SUM(runs_total)::INT AS runs_total,
                SUM(runs_batter)::INT AS runs_batter,
                SUM(runs_bowler)::INT AS runs_bowler,
                SUM(runs_extras)::INT AS extras,
                SUM(CASE WHEN bowler_wicket THEN 1 ELSE 0 END)::INT AS wickets,
                SUM(
                    CASE
                        WHEN player_out = batter
                             AND wicket_kind NOT IN ('not_out', 'retired hurt')
                            THEN 1
                        ELSE 0
                    END
                )::INT AS striker_wickets,
                SUM(CASE WHEN is_dot THEN 1 ELSE 0 END)::INT AS dots,
                SUM(CASE WHEN is_boundary THEN 1 ELSE 0 END)::INT AS boundaries,
                SUM(CASE WHEN is_four THEN 1 ELSE 0 END)::INT AS fours,
                SUM(CASE WHEN is_six THEN 1 ELSE 0 END)::INT AS sixes,
                SUM(CASE WHEN extra_type = 'wide' THEN 1 ELSE 0 END)::INT AS wides,
                SUM(CASE WHEN extra_type = 'noballs' THEN 1 ELSE 0 END)::INT AS no_balls,
                SUM(CASE WHEN extra_type = 'byes' THEN 1 ELSE 0 END)::INT AS byes,
                SUM(CASE WHEN extra_type = 'legbyes' THEN 1 ELSE 0 END)::INT AS leg_byes,
                BOOL_OR(is_maiden) AS is_maiden
            FROM balls
            WHERE innings IN (1, 2)
            GROUP BY
                match_id, season, date, venue, stage, innings,
                match_phase, batting_team, bowling_team, over, bowler
        )
        SELECT
            match_id,
            season,
            date,
            venue,
            stage,
            innings,
            match_phase,
            batting_team,
            bowling_team,
            over,
            bowler,
            deliveries_total,
            legal_balls,
            runs_total,
            runs_batter,
            runs_bowler,
            extras,
            wickets,
            striker_wickets,
            dots,
            boundaries,
            fours,
            sixes,
            wides,
            no_balls,
            byes,
            leg_byes,
            is_maiden,
            CASE
                WHEN legal_balls > 0 THEN ROUND(runs_bowler * 6.0 / legal_balls, 2)
                ELSE NULL
            END AS economy,
            CASE
                WHEN legal_balls > 0 THEN ROUND(runs_total * 6.0 / legal_balls, 2)
                ELSE NULL
            END AS run_rate,
            deliveries_total > 6 AS is_long_over
        FROM over_base
        """,
        """
        CREATE VIEW completed_team_innings AS
        WITH innings_base AS (
            SELECT
                match_id,
                date,
                season,
                venue,
                city,
                stage,
                result_type,
                method,
                is_super_over_match,
                is_close_match,
                toss_winner,
                toss_decision,
                match_won_by,
                win_margin_value,
                win_margin_type,
                batting_first_won,
                1 AS innings,
                team1 AS team,
                team2 AS opponent,
                CAST(team1_score AS INTEGER) AS score,
                COALESCE(CAST(team1_wickets AS INTEGER), 0) AS wickets,
                COALESCE(CAST(team1_balls AS INTEGER), 0) AS balls,
                CAST(NULL AS DOUBLE) AS target_to_win,
                CASE
                    WHEN team1_score IS NULL THEN FALSE
                    WHEN COALESCE(team1_wickets, 0) >= 10 THEN TRUE
                    WHEN COALESCE(team1_balls, 0) >= 120 THEN TRUE
                    WHEN COALESCE(team2_balls, 0) > 0 THEN TRUE
                    ELSE FALSE
                END AS innings_complete
            FROM matches
            UNION ALL
            SELECT
                match_id,
                date,
                season,
                venue,
                city,
                stage,
                result_type,
                method,
                is_super_over_match,
                is_close_match,
                toss_winner,
                toss_decision,
                match_won_by,
                win_margin_value,
                win_margin_type,
                batting_first_won,
                2 AS innings,
                team2 AS team,
                team1 AS opponent,
                CAST(team2_score AS INTEGER) AS score,
                COALESCE(CAST(team2_wickets AS INTEGER), 0) AS wickets,
                COALESCE(CAST(team2_balls AS INTEGER), 0) AS balls,
                CAST(actual_chase_target AS DOUBLE) AS target_to_win,
                CASE
                    WHEN COALESCE(team2_balls, 0) = 0 THEN FALSE
                    WHEN result_type = 'tie' THEN TRUE
                    WHEN match_won_by IS NOT NULL THEN TRUE
                    WHEN COALESCE(team2_wickets, 0) >= 10 THEN TRUE
                    WHEN COALESCE(team2_balls, 0) >= 120 THEN TRUE
                    WHEN actual_chase_target IS NOT NULL AND team2_score >= actual_chase_target THEN TRUE
                    ELSE FALSE
                END AS innings_complete
            FROM matches
        )
        SELECT
            *,
            innings_complete
                AND result_type != 'no result'
                AND (wickets >= 8 OR balls >= 120) AS low_total_record_eligible
        FROM innings_base
        """,
        """
        CREATE VIEW team_match_results AS
        WITH innings_results AS (
            SELECT
                match_id,
                date,
                season,
                venue,
                city,
                stage,
                result_type,
                method,
                is_super_over_match,
                is_close_match,
                toss_winner,
                toss_decision,
                match_won_by,
                win_margin_value,
                win_margin_type,
                team1 AS team,
                team2 AS opponent,
                CAST(team1_score AS INTEGER) AS runs_scored,
                COALESCE(CAST(team1_wickets AS INTEGER), 0) AS wickets_lost,
                COALESCE(CAST(team1_balls AS INTEGER), 0) AS balls_faced,
                CAST(team2_score AS INTEGER) AS runs_conceded,
                COALESCE(CAST(team2_wickets AS INTEGER), 0) AS wickets_taken,
                COALESCE(CAST(team2_balls AS INTEGER), 0) AS balls_bowled,
                1 AS innings,
                TRUE AS batting_first,
                FALSE AS chasing,
                CAST(NULL AS DOUBLE) AS target_to_win,
                CASE
                    WHEN team1_score IS NULL THEN FALSE
                    WHEN COALESCE(team1_wickets, 0) >= 10 THEN TRUE
                    WHEN COALESCE(team1_balls, 0) >= 120 THEN TRUE
                    WHEN COALESCE(team2_balls, 0) > 0 THEN TRUE
                    ELSE FALSE
                END AS innings_complete
            FROM matches
            UNION ALL
            SELECT
                match_id,
                date,
                season,
                venue,
                city,
                stage,
                result_type,
                method,
                is_super_over_match,
                is_close_match,
                toss_winner,
                toss_decision,
                match_won_by,
                win_margin_value,
                win_margin_type,
                team2 AS team,
                team1 AS opponent,
                CAST(team2_score AS INTEGER) AS runs_scored,
                COALESCE(CAST(team2_wickets AS INTEGER), 0) AS wickets_lost,
                COALESCE(CAST(team2_balls AS INTEGER), 0) AS balls_faced,
                CAST(team1_score AS INTEGER) AS runs_conceded,
                COALESCE(CAST(team1_wickets AS INTEGER), 0) AS wickets_taken,
                COALESCE(CAST(team1_balls AS INTEGER), 0) AS balls_bowled,
                2 AS innings,
                FALSE AS batting_first,
                TRUE AS chasing,
                CAST(actual_chase_target AS DOUBLE) AS target_to_win,
                CASE
                    WHEN COALESCE(team2_balls, 0) = 0 THEN FALSE
                    WHEN result_type = 'tie' THEN TRUE
                    WHEN match_won_by IS NOT NULL THEN TRUE
                    WHEN COALESCE(team2_wickets, 0) >= 10 THEN TRUE
                    WHEN COALESCE(team2_balls, 0) >= 120 THEN TRUE
                    WHEN actual_chase_target IS NOT NULL AND team2_score >= actual_chase_target THEN TRUE
                    ELSE FALSE
                END AS innings_complete
            FROM matches
        )
        SELECT
            match_id,
            date,
            season,
            venue,
            city,
            stage,
            result_type,
            method,
            is_super_over_match,
            is_close_match,
            toss_winner,
            toss_decision,
            match_won_by,
            win_margin_value,
            win_margin_type,
            team,
            opponent,
            score AS runs_scored,
            wickets AS wickets_lost,
            balls AS balls_faced,
            runs_conceded,
            wickets_taken,
            balls_bowled,
            innings,
            innings = 1 AS batting_first,
            innings = 2 AS chasing,
            target_to_win,
            CASE WHEN innings = 1 THEN score + 1 ELSE NULL END AS total_to_defend,
            innings_complete,
            CASE
                WHEN match_won_by = team THEN 'won'
                WHEN match_won_by IS NULL THEN 'no_result'
                ELSE 'lost'
            END AS result,
            match_won_by = team AS won,
            match_won_by IS NOT NULL AND match_won_by != team AS lost,
            match_won_by IS NULL AS no_result,
            toss_winner = team AS toss_won,
            innings = 2
                AND innings_complete
                AND target_to_win IS NOT NULL
                AND score >= target_to_win AS successful_chase,
            innings = 1
                AND innings_complete
                AND match_won_by = team
                AND win_margin_type = 'runs' AS successful_defense
        FROM (
            SELECT
                match_id,
                date,
                season,
                venue,
                city,
                stage,
                result_type,
                method,
                is_super_over_match,
                is_close_match,
                toss_winner,
                toss_decision,
                match_won_by,
                win_margin_value,
                win_margin_type,
                team,
                opponent,
                runs_scored AS score,
                wickets_lost AS wickets,
                balls_faced AS balls,
                runs_conceded,
                wickets_taken,
                balls_bowled,
                innings,
                batting_first,
                chasing,
                target_to_win,
                innings_complete
            FROM innings_results
        ) paired
        """,
        """
        CREATE VIEW team_season AS
        SELECT
            season,
            team,
            COUNT(*)::INT AS matches_played,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END)::INT AS wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END)::INT AS losses,
            SUM(CASE WHEN result = 'no_result' THEN 1 ELSE 0 END)::INT AS no_results,
            ROUND(
                SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) * 100.0
                / NULLIF(COUNT(*), 0),
                1
            ) AS win_pct
        FROM team_match_results
        GROUP BY season, team
        """,
        """
        CREATE VIEW points_table AS
        WITH league_results AS (
            SELECT season, team, result
            FROM team_match_results
            WHERE stage = 'League'
        ),
        points AS (
            SELECT
                season,
                team,
                COUNT(*)::INT AS played,
                SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END)::INT AS won,
                SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END)::INT AS lost,
                SUM(CASE WHEN result = 'no_result' THEN 1 ELSE 0 END)::INT AS nr,
                SUM(
                    CASE
                        WHEN result = 'won' THEN 2
                        WHEN result = 'no_result' THEN 1
                        ELSE 0
                    END
                )::INT AS points
            FROM league_results
            GROUP BY season, team
        ),
        ranked AS (
            SELECT
                p.season,
                p.team,
                p.played,
                p.won,
                p.lost,
                p.nr,
                p.points,
                COALESCE(src.nrr, 0.0) AS nrr,
                ROW_NUMBER() OVER (
                    PARTITION BY p.season
                    ORDER BY p.points DESC, COALESCE(src.nrr, 0.0) DESC, p.team ASC
                )::INT AS position
            FROM points p
            LEFT JOIN points_table_source src
              ON p.season = src.season
             AND p.team = src.team
        )
        SELECT
            season,
            team,
            played,
            won,
            lost,
            nr,
            points,
            nrr,
            position
        FROM ranked
        """,
    )
