"""
Tests for the IPL Analytics Platform.
Run with: pytest tests/ -v
"""

import ast
import re
from pathlib import Path

import duckdb
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "Data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "Data" / "processed"


class TestProjectStructure:
    """Verify the project directory is set up correctly."""

    def test_raw_data_exists(self):
        assert (DATA_RAW / "ipl_ball_by_ball.csv").exists(), "Raw CSV not found"

    def test_directories_exist(self):
        assert (PROJECT_ROOT / "src").is_dir()
        assert (PROJECT_ROOT / "pages").is_dir()
        assert (PROJECT_ROOT / "Data" / "preprocessing").is_dir()
        assert (PROJECT_ROOT / ".streamlit").is_dir()

    def test_app_entry_point_exists(self):
        assert (PROJECT_ROOT / "app.py").exists()

    def test_requirements_exists(self):
        assert (PROJECT_ROOT / "requirements.txt").exists()

    def test_streamlit_config_exists(self):
        assert (PROJECT_ROOT / ".streamlit" / "config.toml").exists()

    def test_all_page_files_exist(self):
        pages = list((PROJECT_ROOT / "pages").glob("*.py"))
        assert len(pages) >= 13, f"Expected 13+ pages, found {len(pages)}"


class TestImports:
    """Verify all Python modules can be imported without errors."""

    def test_import_constants(self):
        from src.utils.constants import TEAM_COLORS, PHASE_COLORS, ALL_SEASONS
        assert len(TEAM_COLORS) > 0
        assert len(PHASE_COLORS) == 3
        assert len(ALL_SEASONS) == 18

    def test_import_formatters(self):
        from src.utils.formatters import format_number, format_strike_rate, format_overs
        assert format_number(1234) == "1,234"
        assert format_strike_rate(156.78) == "156.8"
        assert format_overs(24) == "4.0"
        assert format_overs(25) == "4.1"

    def test_import_connection_module(self):
        from src.db.connection import PARQUET_VIEWS
        assert "balls" in PARQUET_VIEWS
        assert "matches" in PARQUET_VIEWS
        assert "team_match_results" in PARQUET_VIEWS
        assert "over_summary" in PARQUET_VIEWS
        assert "innings_tags" in PARQUET_VIEWS
        assert "player_season_metrics" in PARQUET_VIEWS

    def test_import_semantic_engine(self):
        from src.semantic import SUPPORTED_EXAMPLES, run_semantic_query
        assert len(SUPPORTED_EXAMPLES) >= 10
        result = run_semantic_query("Who has the most 49s?")
        assert result["supported"] is True

    def test_query_supports_parameterized_sql(self):
        from src.db.connection import query

        df = query("SELECT ? AS team, ? AS season", ["Chennai Super Kings", 2025])
        assert df.iloc[0]["team"] == "Chennai Super Kings"
        assert int(df.iloc[0]["season"]) == 2025

    def test_query_does_not_retry_non_retryable_sql_errors(self, monkeypatch):
        from src.db import connection

        calls = {"get_connection": 0, "close": 0}

        class FakeConnection:
            def execute(self, sql, params=None):
                raise duckdb.BinderException("broken sql")

            def close(self):
                calls["close"] += 1

        def fake_get_connection():
            calls["get_connection"] += 1
            return FakeConnection()

        monkeypatch.setattr(connection, "get_connection", fake_get_connection)

        with pytest.raises(duckdb.BinderException):
            connection.query("SELECT nope")

        assert calls["get_connection"] == 1
        assert calls["close"] == 1

    def test_query_retries_retryable_duckdb_errors_once(self, monkeypatch):
        from src.db import connection

        calls = {"get_connection": 0, "execute": 0, "close": 0}

        class FakeResult:
            def df(self):
                return pd.DataFrame([{"value": 1}])

        class FakeConnection:
            def execute(self, sql, params=None):
                calls["execute"] += 1
                if calls["execute"] == 1:
                    raise duckdb.ConnectionException("temporary connection issue")
                return FakeResult()

            def close(self):
                calls["close"] += 1

        def fake_get_connection():
            calls["get_connection"] += 1
            return FakeConnection()

        monkeypatch.setattr(connection, "get_connection", fake_get_connection)

        df = connection.query("SELECT 1 AS value")

        assert int(df.iloc[0]["value"]) == 1
        assert calls["get_connection"] == 2
        assert calls["execute"] == 2
        assert calls["close"] == 2

    def test_matches_view_resolves_super_over_winner(self):
        from src.db.connection import query

        df = query(
            """
            SELECT match_id, team1, match_won_by, batting_first_won
            FROM matches
            WHERE match_id = 392190
            """
        )
        assert df.iloc[0]["team1"] == "Rajasthan Royals"
        assert df.iloc[0]["match_won_by"] == "Rajasthan Royals"
        assert bool(df.iloc[0]["batting_first_won"]) is True

    def test_completed_team_innings_excludes_partial_no_result_chase(self):
        from src.db.connection import query

        df = query(
            """
            SELECT innings, innings_complete
            FROM completed_team_innings
            WHERE match_id = 829813
            ORDER BY innings
            """
        )
        assert bool(df.iloc[0]["innings_complete"]) is True
        assert bool(df.iloc[1]["innings_complete"]) is False

    def test_completed_team_innings_keeps_finished_early_successful_chase(self):
        from src.db.connection import query

        df = query(
            """
            SELECT innings_complete, score, target_to_win
            FROM completed_team_innings
            WHERE match_id = 335984 AND innings = 2
            """
        )
        assert bool(df.iloc[0]["innings_complete"]) is True
        assert int(df.iloc[0]["score"]) >= int(df.iloc[0]["target_to_win"])

    def test_successful_chases_are_true_target_chases(self):
        from src.db.connection import query

        df = query(
            """
            SELECT COUNT(*) AS invalid_rows
            FROM team_match_results
            WHERE successful_chase
              AND (target_to_win IS NULL OR runs_scored < target_to_win)
            """
        )
        assert int(df.iloc[0]["invalid_rows"]) == 0

    def test_records_page_team_result_queries_execute_with_plain_season_filter(self):
        from src.db.connection import query

        highest_chases = query(
            """
            SELECT team,
                   runs_scored::INT AS score,
                   wickets_lost::INT AS wickets,
                   opponent,
                   target_to_win::INT AS target,
                   venue,
                   season
            FROM team_match_results
            WHERE successful_chase
              AND season BETWEEN 2008 AND 2025
            ORDER BY score DESC
            LIMIT 5
            """
        )
        lowest_defenses = query(
            """
            SELECT team,
                   runs_scored::INT AS score,
                   opponent,
                   win_margin_value::INT AS margin,
                   venue,
                   season
            FROM team_match_results
            WHERE successful_defense
              AND season BETWEEN 2008 AND 2025
            ORDER BY score ASC
            LIMIT 5
            """
        )

        assert not highest_chases.empty
        assert not lowest_defenses.empty

    def test_runtime_player_views_exclude_super_over_innings(self):
        from src.db.connection import query

        df = query(
            """
            SELECT
                (SELECT COUNT(*) FROM player_batting WHERE innings > 2) AS batting_rows,
                (SELECT COUNT(*) FROM player_bowling WHERE innings > 2) AS bowling_rows,
                (SELECT COUNT(*) FROM powerplay WHERE innings > 2) AS powerplay_rows,
                (SELECT COUNT(*) FROM over_summary WHERE innings > 2) AS over_rows
            """
        )
        row = df.iloc[0]
        assert int(row["batting_rows"]) == 0
        assert int(row["bowling_rows"]) == 0
        assert int(row["powerplay_rows"]) == 0
        assert int(row["over_rows"]) == 0

    def test_matchups_use_bowler_credited_dismissals(self):
        from src.db.connection import query

        df = query(
            """
            SELECT
                (SELECT COALESCE(SUM(dismissals), 0) FROM matchups) AS matchup_dismissals,
                (
                    SELECT COALESCE(
                        SUM(
                            CASE
                                WHEN innings IN (1, 2)
                                     AND player_out = batter
                                     AND bowler_wicket
                                    THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    )
                    FROM balls
                ) AS expected_dismissals
            """
        )
        assert int(df.iloc[0]["matchup_dismissals"]) == int(df.iloc[0]["expected_dismissals"])

    def test_matchups_leave_zero_denominator_rates_null(self):
        from src.db.connection import query

        df = query(
            """
            SELECT
                SUM(CASE WHEN dismissals = 0 AND average IS NOT NULL THEN 1 ELSE 0 END) AS bad_average_rows,
                SUM(CASE WHEN balls = 0 AND strike_rate IS NOT NULL THEN 1 ELSE 0 END) AS bad_sr_rows,
                SUM(CASE WHEN balls = 0 AND dot_pct IS NOT NULL THEN 1 ELSE 0 END) AS bad_dot_rows,
                SUM(CASE WHEN balls = 0 AND boundary_pct IS NOT NULL THEN 1 ELSE 0 END) AS bad_boundary_rows
            FROM matchups
            """
        )
        row = df.iloc[0]
        assert int(row["bad_average_rows"]) == 0
        assert int(row["bad_sr_rows"]) == 0
        assert int(row["bad_dot_rows"]) == 0
        assert int(row["bad_boundary_rows"]) == 0

    def test_leaderboard_expensive_overs_uses_bowler_runs(self):
        source = (PROJECT_ROOT / "pages" / "02_Leaderboards.py").read_text(encoding="utf-8")
        assert "SUM(b.runs_bowler)::INT                     AS runs_conceded" in source

    def test_runtime_cricket_views_register_on_fresh_connection(self):
        from src.db.connection import get_connection

        conn = get_connection()
        try:
            completed = conn.execute(
                "SELECT COUNT(*) AS c FROM completed_team_innings WHERE innings_complete"
            ).df()
            team_results = conn.execute(
                "SELECT COUNT(*) AS c FROM team_match_results WHERE innings_complete"
            ).df()
        finally:
            conn.close()

        assert int(completed.iloc[0]["c"]) > 0
        assert int(team_results.iloc[0]["c"]) > 0

    def test_low_total_records_exclude_short_reduced_over_chases(self):
        from src.db.connection import query

        df = query(
            """
            SELECT team, score, wickets, season
            FROM completed_team_innings
            WHERE low_total_record_eligible
            ORDER BY score ASC
            LIMIT 5
            """
        )

        first_row = df.iloc[0]
        assert first_row["team"] == "Royal Challengers Bengaluru"
        assert int(first_row["score"]) == 49
        assert int(first_row["wickets"]) == 10
        assert int(first_row["season"]) == 2017

        excluded = query(
            """
            SELECT COUNT(*) AS c
            FROM completed_team_innings
            WHERE low_total_record_eligible
              AND team = 'Sunrisers Hyderabad'
              AND score = 44
              AND wickets = 2
              AND season = 2014
            """
        )
        assert int(excluded.iloc[0]["c"]) == 0

    def test_head_to_head_match_query_includes_result_type(self):
        source = (PROJECT_ROOT / "pages" / "06_Head_to_Head.py").read_text(encoding="utf-8")
        assert "win_margin_value, win_margin_type, stage, result_type" in source

    def test_pressure_chase_bucket_label_matches_bucket_logic(self):
        source = (PROJECT_ROOT / "pages" / "08_Pressure_Momentum.py").read_text(encoding="utf-8")
        assert "WHEN target <= 120 THEN '≤120'" in source

    def test_records_page_visual_render_has_error_boundary(self):
        source = (PROJECT_ROOT / "pages" / "10_Records_Anomalies.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        render_fn = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_render_record_visual"
        )
        try_nodes = [node for node in ast.walk(render_fn) if isinstance(node, ast.Try)]
        assert try_nodes, "_render_record_visual should guard fetch/render failures"

        st_calls = {
            node.func.attr
            for node in ast.walk(render_fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st"
        }
        assert "error" in st_calls

        except_returns = [
            node
            for handler in try_nodes[0].handlers
            for node in ast.walk(handler)
            if isinstance(node, ast.Return)
        ]
        assert any(
            isinstance(ret.value, ast.Call)
            and isinstance(ret.value.func, ast.Attribute)
            and isinstance(ret.value.func.value, ast.Name)
            and ret.value.func.value.id == "pd"
            and ret.value.func.attr == "DataFrame"
            for ret in except_returns
        )

    def test_player_profile_matches_include_bowling_only_appearances(self):
        from src.db.connection import query

        df = query(
            """
            WITH batting AS (
                SELECT COUNT(DISTINCT match_id) AS matches
                FROM player_batting
                WHERE batter = 'YS Chahal'
            ),
            combined AS (
                SELECT COUNT(DISTINCT match_id) AS matches
                FROM (
                    SELECT match_id FROM player_batting WHERE batter = 'YS Chahal'
                    UNION
                    SELECT match_id FROM player_bowling WHERE bowler = 'YS Chahal'
                ) appearances
            )
            SELECT batting.matches AS batting_matches, combined.matches AS combined_matches
            FROM batting, combined
            """
        )

        assert int(df.iloc[0]["combined_matches"]) > int(df.iloc[0]["batting_matches"])

        source = (PROJECT_ROOT / "pages" / "03_Player_Profile.py").read_text(encoding="utf-8")
        assert "get_player_match_count(player)" in source


class TestConstants:
    """Validate constant definitions."""

    def test_all_current_teams_have_colors(self):
        from src.utils.constants import TEAM_COLORS
        current_teams = [
            "Chennai Super Kings", "Mumbai Indians", "Royal Challengers Bengaluru",
            "Kolkata Knight Riders", "Delhi Capitals", "Rajasthan Royals",
            "Sunrisers Hyderabad", "Punjab Kings", "Gujarat Titans", "Lucknow Super Giants",
        ]
        for team in current_teams:
            assert team in TEAM_COLORS, f"Missing color for {team}"

    def test_phase_over_ranges_cover_all_overs(self):
        from src.utils.constants import PHASE_OVER_RANGES
        all_overs = set()
        for phase, (start, end) in PHASE_OVER_RANGES.items():
            all_overs.update(range(start, end + 1))
        assert all_overs == set(range(1, 21)), "Phase ranges don't cover overs 1-20"

    def test_stage_order_complete(self):
        from src.utils.constants import STAGE_ORDER
        assert "League" in STAGE_ORDER
        assert "Final" in STAGE_ORDER
        assert STAGE_ORDER["Final"] > STAGE_ORDER["League"]


class TestFormatters:
    """Test formatting utility functions."""

    def test_format_number_with_commas(self):
        from src.utils.formatters import format_number
        assert format_number(1000) == "1,000"
        assert format_number(1000000) == "1,000,000"
        assert format_number(None) == "N/A"

    def test_format_percentage(self):
        from src.utils.formatters import format_percentage
        assert format_percentage(56.789) == "56.8%"
        assert format_percentage(None) == "N/A"

    def test_format_overs_edge_cases(self):
        from src.utils.formatters import format_overs
        assert format_overs(0) == "0.0"
        assert format_overs(6) == "1.0"
        assert format_overs(7) == "1.1"
        assert format_overs(120) == "20.0"
        assert format_overs(None) == "N/A"


class TestParquetData:
    """Validate processed parquet files for data integrity."""

    EXPECTED_FILES = [
        "ball_by_ball.parquet", "match_summary.parquet", "player_season.parquet",
        "matchups.parquet", "venue_stats.parquet", "powerplay_stats.parquet",
        "dot_sequences.parquet", "season_structure.parquet", "player_batting_match.parquet",
        "player_bowling_match.parquet", "partnerships.parquet", "dismissal_patterns.parquet",
        "dismissal_by_phase.parquet", "team_season.parquet", "points_table.parquet",
        "team_match_results.parquet", "over_summary.parquet", "innings_tags.parquet",
        "player_season_metrics.parquet",
    ]

    def test_all_parquet_files_exist(self):
        for fname in self.EXPECTED_FILES:
            assert (DATA_PROCESSED / fname).exists(), f"Missing: {fname}"

    def test_ball_by_ball_shape(self):
        import pandas as pd
        bb = pd.read_parquet(DATA_PROCESSED / "ball_by_ball.parquet")
        assert bb.shape[0] == 278205, f"Expected 278205 rows, got {bb.shape[0]}"
        assert bb.shape[1] >= 85, f"Expected 85+ cols, got {bb.shape[1]}"

    def test_no_unknown_stages(self):
        import pandas as pd
        bb = pd.read_parquet(DATA_PROCESSED / "ball_by_ball.parquet", columns=["stage"])
        assert (bb["stage"] == "Unknown").sum() == 0, "Found Unknown stages"

    def test_seasons_range(self):
        import pandas as pd
        bb = pd.read_parquet(DATA_PROCESSED / "ball_by_ball.parquet", columns=["season"])
        seasons = sorted(bb["season"].unique())
        assert seasons[0] == 2008
        assert seasons[-1] == 2025
        assert len(seasons) == 18

    def test_overs_are_1_indexed(self):
        import pandas as pd
        bb = pd.read_parquet(DATA_PROCESSED / "ball_by_ball.parquet", columns=["over"])
        assert bb["over"].min() == 1, "Overs should start at 1"
        assert bb["over"].max() == 20, "Overs should go up to 20"

    def test_no_nulls_in_derived_columns(self):
        import pandas as pd
        bb = pd.read_parquet(DATA_PROCESSED / "ball_by_ball.parquet",
                             columns=["is_maiden", "over_runs", "match_phase", "is_dot", "is_four", "is_six"])
        for col in ["is_maiden", "over_runs", "match_phase", "is_dot", "is_four", "is_six"]:
            assert bb[col].isna().sum() == 0, f"Found nulls in {col}"

    def test_team_names_standardized(self):
        import pandas as pd
        bb = pd.read_parquet(DATA_PROCESSED / "ball_by_ball.parquet", columns=["batting_team", "bowling_team"])
        old_names = {"Royal Challengers Bangalore", "Delhi Daredevils", "Kings XI Punjab"}
        all_teams = set(bb["batting_team"].unique()) | set(bb["bowling_team"].unique())
        for old in old_names:
            assert old not in all_teams, f"Old team name still present: {old}"

    def test_match_summary_has_all_matches(self):
        import pandas as pd
        ms = pd.read_parquet(DATA_PROCESSED / "match_summary.parquet")
        bb = pd.read_parquet(DATA_PROCESSED / "ball_by_ball.parquet", columns=["match_id"])
        assert ms.shape[0] == bb["match_id"].nunique()

    def test_points_table_per_season(self):
        import pandas as pd
        pt = pd.read_parquet(DATA_PROCESSED / "points_table.parquet")
        for season in pt["season"].unique():
            spt = pt[pt["season"] == season]
            assert spt["played"].sum() % 2 == 0, f"Odd total played in {season}"

    def test_season_structure_champions(self):
        import pandas as pd
        ss = pd.read_parquet(DATA_PROCESSED / "season_structure.parquet")
        assert ss.shape[0] == 18, "Should have 18 seasons"
        assert ss["champion"].notna().all(), "Every season should have a champion"

    def test_team_match_results_shape(self):
        import pandas as pd
        tmr = pd.read_parquet(DATA_PROCESSED / "team_match_results.parquet")
        ms = pd.read_parquet(DATA_PROCESSED / "match_summary.parquet")
        assert tmr.shape[0] == ms.shape[0] * 2
        assert set(tmr["result"].unique()) <= {"won", "lost", "no_result"}

    def test_over_summary_has_expected_columns(self):
        import pandas as pd
        over = pd.read_parquet(DATA_PROCESSED / "over_summary.parquet")
        expected = {"deliveries_total", "legal_balls", "runs_total", "wides", "no_balls"}
        assert expected.issubset(set(over.columns))
        assert over["deliveries_total"].max() >= 6

    def test_innings_tags_flags_are_present(self):
        import pandas as pd
        tags = pd.read_parquet(DATA_PROCESSED / "innings_tags.parquet")
        expected = {"is_score_49", "is_score_99", "is_score_20_plus", "boundary_pct"}
        assert expected.issubset(set(tags.columns))
        assert tags["is_score_49"].dtype == bool


class TestSemanticQueries:
    """Golden tests for deterministic semantic query support."""

    def test_most_49s(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has the most 49s?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "AD Russell"
        assert int(df.iloc[0]["Innings"]) == 4

    def test_longest_over(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("What is the longest over ever bowled?")
        df = result["data"]
        assert result["supported"] is True
        assert int(df.iloc[0]["Deliveries"]) == 11

    def test_team_winning_streak(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Which teams have the longest winning streaks?")
        df = result["data"]
        assert result["supported"] is True
        assert "Kolkata Knight Riders" in set(df["team"] if "team" in df.columns else df["Player"])
        streak_col = "Streak Length"
        assert int(df[streak_col].max()) == 10

    def test_team_winning_streak_season_overlap(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Which teams have the longest winning streaks in 2024?")
        df = result["data"]
        assert result["supported"] is True
        csk = df[df["team"] == "Chennai Super Kings"]
        assert not csk.empty
        assert int(csk.iloc[0]["Streak Length"]) == 5
        assert int(csk.iloc[0]["From Season"]) == 2023
        assert int(csk.iloc[0]["To Season"]) == 2024

    def test_consecutive_400_run_seasons(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has the most consecutive seasons with 400+ runs?")
        df = result["data"]
        assert result["supported"] is True
        shubman = df[df["Player"] == "Shubman Gill"]
        assert not shubman.empty
        assert int(shubman.iloc[0]["Streak Length"]) == 6

    def test_most_hat_tricks(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Which bowlers have the most hat-tricks?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "A Mishra"
        assert int(df.iloc[0]["Hat-Tricks"]) == 3

    def test_three_consecutive_wickets_phrase_maps(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Bowler with most three consecutive wickets")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "A Mishra"
        assert int(df.iloc[0]["Hat-Tricks"]) == 3

    def test_all_hat_tricks(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Show all hat-tricks in IPL history.")
        df = result["data"]
        assert result["supported"] is True
        assert len(df) == 23

    def test_most_maidens(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Which bowlers have the most maidens?")
        df = result["data"]
        assert result["supported"] is True
        assert int(df["Maidens"].max()) == 14

    def test_most_ducks(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has the most ducks?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "GJ Maxwell"
        assert int(df.iloc[0]["Ducks"]) == 19

    def test_most_golden_ducks(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has the most golden ducks?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "Rashid Khan"
        assert int(df.iloc[0]["Golden Ducks"]) == 12

    def test_most_balls_in_innings(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who faced the most balls in an IPL innings?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "BB McCullum"
        assert int(df.iloc[0]["Balls"]) == 73

    def test_most_perfect_overs(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Which bowlers have the most perfect overs?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "P Kumar"
        assert int(df.iloc[0]["Perfect Overs"]) == 12

    def test_wicket_streak(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Which bowlers have the longest wicket streaks?")
        df = result["data"]
        assert result["supported"] is True
        assert int(df.iloc[0]["Streak Length"]) == 3

    def test_batter_dot_streak(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has the longest dot-ball streak as a batter?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "G Gambhir"
        assert int(df.iloc[0]["Streak Length"]) == 17

    def test_batter_dot_streak_season_overlap(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has the longest dot-ball streak as a batter in 2024?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "JC Buttler"
        assert int(df.iloc[0]["Streak Length"]) == 10
        assert int(df.iloc[0]["From Season"]) == 2023
        assert int(df.iloc[0]["To Season"]) == 2024

    def test_boundary_streak(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has the longest boundary streak?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "YK Pathan"
        assert int(df.iloc[0]["Streak Length"]) == 11

    def test_scoring_streak(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has the longest scoring-shot streak?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "Shubman Gill"
        assert int(df.iloc[0]["Streak Length"]) == 39

    def test_most_extras_in_over(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Which overs had the most extras?")
        df = result["data"]
        assert result["supported"] is True
        assert int(df.iloc[0]["Extras"]) == 12

    def test_most_sixes_in_over(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Which overs had the most sixes?")
        df = result["data"]
        assert result["supported"] is True
        assert int(df.iloc[0]["Sixes"]) == 5

    def test_batter_dismissal_type(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has been caught the most?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "RG Sharma"
        assert int(df.iloc[0]["Caught Dismissals"]) == 168

    def test_bowler_dismissal_type(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Which bowlers have the most LBWs?")
        df = result["data"]
        assert result["supported"] is True
        assert df.iloc[0]["Player"] == "Rashid Khan"
        assert int(df.iloc[0]["LBWs"]) == 37

    def test_year_for_prompt_does_not_match_four_fors(self):
        from src.semantic import run_semantic_query
        result = run_semantic_query("Who has the most consecutive 20+ scores in 2024 for V Kohli?")
        df = result["data"]
        assert result["supported"] is True
        assert result["plan"].intent_id == "twenty-plus-streak"
        assert df.iloc[0]["Player"] == "V Kohli"
        assert int(df.iloc[0]["Streak Length"]) == 9
        assert int(df.iloc[0]["From Season"]) == 2024
        assert int(df.iloc[0]["To Season"]) == 2025


class TestPageReliability:
    """Catch page-local helper regressions before deployment."""

    def test_called_spec_helpers_are_defined_in_page_modules(self):
        for path in (PROJECT_ROOT / "pages").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            defined = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            called = set(re.findall(r"(_[A-Za-z0-9_]+_spec)\(", source))
            missing = sorted(name for name in called if name not in defined)
            assert not missing, f"{path.name} missing spec helpers: {', '.join(missing)}"
