"""
Tests for the IPL Analytics Platform.
Run with: pytest tests/ -v
"""

import pytest
from pathlib import Path

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
