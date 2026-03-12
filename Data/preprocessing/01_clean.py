"""
IPL Analytics — Step 1: Data Cleaning
Reads raw CSV, applies 10 cleaning steps, outputs cleaned parquet.

Input:  data/raw/ipl_ball_by_ball.csv  (278,205 rows × 64 columns)
Output: data/processed/ball_by_ball_cleaned.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_CSV = PROJECT_ROOT / "Data" / "raw" / "ipl_ball_by_ball.csv"
OUTPUT = PROJECT_ROOT / "Data" / "processed" / "ball_by_ball_cleaned.parquet"

# ── Constants ────────────────────────────────────────────────────────────────

COLUMNS_TO_DROP = [
    "Unnamed: 0", "match_type", "event_name", "gender",
    "team_type", "balls_per_over", "overs", "match_number",
]

SEASON_MAP = {
    "2007/08": 2008, "2009": 2009, "2009/10": 2010,
    "2011": 2011, "2012": 2012, "2013": 2013, "2014": 2014,
    "2015": 2015, "2016": 2016, "2017": 2017, "2018": 2018,
    "2019": 2019, "2020/21": 2020, "2021": 2021,
    "2022": 2022, "2023": 2023, "2024": 2024, "2025": 2025,
}

TEAM_NAME_MAP = {
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Rising Pune Supergiant": "Rising Pune Supergiants",
    "Pune Warriors": "Pune Warriors India",
}

VENUE_MAP = {
    # Wankhede
    "Wankhede Stadium, Mumbai": "Wankhede Stadium",
    # Chinnaswamy
    "M Chinnaswamy Stadium, Bengaluru": "M Chinnaswamy Stadium",
    "M.Chinnaswamy Stadium": "M Chinnaswamy Stadium",
    # Eden Gardens
    "Eden Gardens, Kolkata": "Eden Gardens",
    # Delhi — Feroz Shah Kotla was renamed Arun Jaitley Stadium
    "Arun Jaitley Stadium, Delhi": "Arun Jaitley Stadium",
    "Feroz Shah Kotla": "Arun Jaitley Stadium",
    # Brabourne
    "Brabourne Stadium, Mumbai": "Brabourne Stadium",
    # DY Patil
    "Dr DY Patil Sports Academy, Mumbai": "Dr DY Patil Sports Academy",
    # ACA-VDCA
    "Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium": "ACA-VDCA Stadium",
    "Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium, Visakhapatnam": "ACA-VDCA Stadium",
    # Rajiv Gandhi
    "Rajiv Gandhi International Stadium, Uppal": "Rajiv Gandhi International Stadium",
    "Rajiv Gandhi International Stadium, Uppal, Hyderabad": "Rajiv Gandhi International Stadium",
    # Narendra Modi (formerly Sardar Patel / Motera)
    "Narendra Modi Stadium, Ahmedabad": "Narendra Modi Stadium",
    "Sardar Patel Stadium, Motera": "Narendra Modi Stadium",
    # Sawai Mansingh
    "Sawai Mansingh Stadium, Jaipur": "Sawai Mansingh Stadium",
    # MA Chidambaram
    "MA Chidambaram Stadium, Chepauk": "MA Chidambaram Stadium",
    "MA Chidambaram Stadium, Chepauk, Chennai": "MA Chidambaram Stadium",
    # HPCA Dharamsala
    "Himachal Pradesh Cricket Association Stadium, Dharamsala": "Himachal Pradesh Cricket Association Stadium",
    # PCA Mohali
    "Punjab Cricket Association IS Bindra Stadium, Mohali": "Punjab Cricket Association IS Bindra Stadium",
    "Punjab Cricket Association IS Bindra Stadium, Mohali, Chandigarh": "Punjab Cricket Association IS Bindra Stadium",
    "Punjab Cricket Association Stadium, Mohali": "Punjab Cricket Association IS Bindra Stadium",
    # MCA Pune
    "Maharashtra Cricket Association Stadium, Pune": "Maharashtra Cricket Association Stadium",
    "Subrata Roy Sahara Stadium": "Maharashtra Cricket Association Stadium",
    # Ekana Lucknow
    "Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow": "Ekana Cricket Stadium",
    # Barsapara
    "Barsapara Cricket Stadium, Guwahati": "Barsapara Cricket Stadium",
    # Mullanpur / New Chandigarh
    "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur": "Maharaja Yadavindra Singh International Cricket Stadium",
    "Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh": "Maharaja Yadavindra Singh International Cricket Stadium",
    # Vidarbha
    "Vidarbha Cricket Association Stadium, Jamtha": "Vidarbha Cricket Association Stadium",
}


# ── Cleaning Steps ───────────────────────────────────────────────────────────

def step_01_drop_constants(df: pd.DataFrame) -> pd.DataFrame:
    """Drop 8 constant / useless columns."""
    existing = [c for c in COLUMNS_TO_DROP if c in df.columns]
    df = df.drop(columns=existing)
    print(f"  Step 1: Dropped {len(existing)} constant columns -> {df.shape[1]} cols")
    return df


def step_02_fix_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Fix data types: date, season, over index, booleans, numerics."""
    # Date
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")

    # Season: string -> standardized int
    df["season"] = df["season"].astype(str).map(SEASON_MAP).astype("int16")

    # Over: 0-indexed -> 1-indexed
    df["over"] = (df["over"] + 1).astype("int8")

    # Recalculate ball_no to match 1-indexed over
    df["ball_no"] = df["over"] + df["ball"] / 10.0

    # Innings
    df["innings"] = df["innings"].astype("int8")

    # Booleans
    for col in ["valid_ball", "striker_out"]:
        if col in df.columns:
            df[col] = df[col].astype(bool)
    if "umpires_call" in df.columns:
        df["umpires_call"] = df["umpires_call"].fillna(False).astype(bool)

    # Downcast numeric columns
    int_cols = [
        "ball", "bat_pos", "runs_batter", "balls_faced", "runs_extras",
        "runs_total", "runs_bowler", "runs_not_boundary", "non_striker_pos",
        "team_runs", "team_balls", "team_wicket", "batter_runs",
        "batter_balls", "bowler_wicket",
    ]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int16")

    # event_match_no
    if "event_match_no" in df.columns:
        df["event_match_no"] = pd.to_numeric(df["event_match_no"], errors="coerce")

    print("  Step 2: Data types fixed, season standardized, over 1-indexed")
    return df


def step_03_structural_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """Fill structural NaNs with meaningful defaults, parse win_outcome."""
    fill_map = {
        "extra_type": "no_extra",
        "wicket_kind": "not_out",
        "player_out": "none",
        "fielders": "none",
        "result_type": "normal",
        "method": "no_dls",
    }
    for col, fill_val in fill_map.items():
        if col in df.columns:
            df[col] = df[col].fillna(fill_val)

    # Parse win_outcome -> win_margin_value + win_margin_type
    if "win_outcome" in df.columns:
        df["win_margin_value"] = (
            df["win_outcome"]
            .str.extract(r"(\d+)", expand=False)
            .astype(float)
        )
        df["win_margin_type"] = (
            df["win_outcome"]
            .str.extract(r"\d+\s+(\w+)", expand=False)
        )
        df["win_margin_type"] = df["win_margin_type"].replace("wicket", "wickets")

    # Derived structural flags
    df["is_chasing"] = df["innings"] == 2
    df["has_review"] = df["review_batter"].notna()
    df["is_super_over_match"] = df["superover_winner"].notna()

    print("  Step 3: Structural nulls handled, win_outcome parsed, flags added")
    return df


def step_04_team_names(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize team names across all team columns."""
    team_cols = ["batting_team", "bowling_team", "match_won_by", "toss_winner"]
    for col in team_cols:
        if col in df.columns:
            df[col] = df[col].replace(TEAM_NAME_MAP)
    print(f"  Step 4: Team names standardized ({len(TEAM_NAME_MAP)} mappings)")
    return df


def step_05_over_indexing(df: pd.DataFrame) -> pd.DataFrame:
    """Add delivery_number and legal_ball_number columns."""
    df["delivery_number"] = (
        df.groupby(["match_id", "innings"]).cumcount() + 1
    )
    df["legal_ball_number"] = (
        df.groupby(["match_id", "innings"])["valid_ball"]
        .cumsum()
        .astype("int16")
    )
    print("  Step 5: delivery_number and legal_ball_number added")
    return df


def step_06_venues(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize venue names."""
    if "venue" in df.columns:
        before = df["venue"].nunique()
        df["venue"] = df["venue"].replace(VENUE_MAP)
        after = df["venue"].nunique()
        print(f"  Step 6: Venues standardized ({before} -> {after} unique)")
    return df


def step_07_stage_classification(df: pd.DataFrame) -> pd.DataFrame:
    """Classify Unknown stages as League or derive playoff stages."""
    match_info = (
        df.groupby("match_id")
        .agg(season=("season", "first"), date=("date", "first"), stage=("stage", "first"))
        .reset_index()
    )

    updated_stages = {}
    for season, grp in match_info.groupby("season"):
        grp = grp.sort_values("date")
        known = grp[grp["stage"] != "Unknown"]
        unknown = grp[grp["stage"] == "Unknown"]

        if len(unknown) == 0:
            continue

        if len(known) > 0:
            # Some stages known — fill unknowns as League
            for mid in unknown["match_id"]:
                updated_stages[mid] = "League"
        else:
            # All unknown — derive from match sequence
            match_ids = grp["match_id"].tolist()
            n = len(match_ids)
            if season <= 2009:
                # 2008-2009: Final + 2 Semi Finals
                if n >= 1:
                    updated_stages[match_ids[-1]] = "Final"
                if n >= 2:
                    updated_stages[match_ids[-2]] = "Semi Final"
                if n >= 3:
                    updated_stages[match_ids[-3]] = "Semi Final"
                for mid in match_ids[:-3]:
                    updated_stages[mid] = "League"
            else:
                # 2010+: Q1, Eliminator, Q2, Final
                if n >= 1:
                    updated_stages[match_ids[-1]] = "Final"
                if n >= 2:
                    updated_stages[match_ids[-2]] = "Qualifier 2"
                if n >= 3:
                    updated_stages[match_ids[-3]] = "Eliminator"
                if n >= 4:
                    updated_stages[match_ids[-4]] = "Qualifier 1"
                for mid in match_ids[:-4]:
                    updated_stages[mid] = "League"

    if updated_stages:
        stage_map = df["match_id"].map(updated_stages)
        mask = stage_map.notna()
        df.loc[mask, "stage"] = stage_map[mask]

    unknown_left = (df.groupby("match_id")["stage"].first() == "Unknown").sum()
    print(f"  Step 7: Stage classification complete ({unknown_left} Unknown remaining)")
    return df


def step_08_player_names(df: pd.DataFrame) -> pd.DataFrame:
    """Light player name standardization. Cricsheet data is generally clean."""
    player_cols = ["batter", "bowler", "non_striker", "player_out", "player_of_match"]
    for col in player_cols:
        if col in df.columns:
            df[col] = df[col].str.strip()
    print("  Step 8: Player names trimmed")
    return df


def step_09_validate(df: pd.DataFrame) -> pd.DataFrame:
    """Run data integrity checks."""
    issues = []

    # Over range: 1-20
    bad_overs = df[(df["over"] < 1) | (df["over"] > 20)]
    if len(bad_overs) > 0:
        issues.append(f"Over out of range [1-20]: {len(bad_overs)} rows")

    # bat_pos range: 1-11
    if "bat_pos" in df.columns:
        bad_pos = df[(df["bat_pos"] < 1) | (df["bat_pos"] > 11)]
        if len(bad_pos) > 0:
            issues.append(f"bat_pos out of range [1-11]: {len(bad_pos)} rows")

    # team_wicket max: 10
    if "team_wicket" in df.columns:
        bad_wkt = df[df["team_wicket"] > 10]
        if len(bad_wkt) > 0:
            issues.append(f"team_wicket > 10: {len(bad_wkt)} rows")

    # runs_total = runs_batter + runs_extras
    if all(c in df.columns for c in ["runs_total", "runs_batter", "runs_extras"]):
        bad_runs = df[df["runs_total"] != df["runs_batter"] + df["runs_extras"]]
        if len(bad_runs) > 0:
            issues.append(f"runs_total != runs_batter + runs_extras: {len(bad_runs)} rows")

    if issues:
        print("  Step 9: Validation warnings:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  Step 9: All validation checks passed")
    return df


def step_10_save(df: pd.DataFrame) -> pd.DataFrame:
    """Save cleaned data as parquet."""
    # Ensure string columns for parquet compatibility
    str_cols = [
        "batting_team", "bowling_team", "batter", "bowler", "non_striker",
        "player_out", "player_of_match", "match_won_by", "toss_winner",
        "toss_decision", "venue", "city", "wicket_kind", "extra_type",
        "stage", "win_margin_type", "fielders", "result_type", "method",
        "review_batter", "team_reviewed", "review_decision", "umpire",
        "superover_winner", "new_batter", "next_batter", "batting_partners",
        "win_outcome",
    ]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).replace("nan", None)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT, index=False, engine="pyarrow")
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"  Step 10: Saved {OUTPUT.name} ({size_mb:.1f} MB, {df.shape[0]:,} rows x {df.shape[1]} cols)")
    return df


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading raw CSV...")
    df = pd.read_csv(RAW_CSV, low_memory=False)
    print(f"  Loaded: {df.shape[0]:,} rows x {df.shape[1]} columns\n")

    df = step_01_drop_constants(df)
    df = step_02_fix_dtypes(df)
    df = step_03_structural_nulls(df)
    df = step_04_team_names(df)
    df = step_05_over_indexing(df)
    df = step_06_venues(df)
    df = step_07_stage_classification(df)
    df = step_08_player_names(df)
    df = step_09_validate(df)
    df = step_10_save(df)

    print("\nCLEANING COMPLETE")


if __name__ == "__main__":
    main()
