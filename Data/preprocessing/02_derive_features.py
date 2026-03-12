"""
IPL Analytics — Step 2: Feature Engineering
Reads cleaned parquet, applies 11 feature blocks, outputs enriched parquet.

Input:  data/processed/ball_by_ball_cleaned.parquet
Output: data/processed/ball_by_ball.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT = PROJECT_ROOT / "Data" / "processed" / "ball_by_ball_cleaned.parquet"
OUTPUT = PROJECT_ROOT / "Data" / "processed" / "ball_by_ball.parquet"


# ── Block 1: Match Phase ─────────────────────────────────────────────────────

def block_01_match_phase(df: pd.DataFrame) -> pd.DataFrame:
    conditions = [
        df["over"] <= 6,
        df["over"] <= 15,
    ]
    choices = ["powerplay", "middle"]
    df["match_phase"] = np.select(conditions, choices, default="death")
    print("  Block 1: match_phase added")
    return df


# ── Block 2: Boundary & Dot Flags ────────────────────────────────────────────

def block_02_boundary_flags(df: pd.DataFrame) -> pd.DataFrame:
    df["is_four"] = (df["runs_batter"] == 4) & (df["runs_not_boundary"] == 0)
    df["is_six"] = (df["runs_batter"] == 6) & (df["runs_not_boundary"] == 0)
    df["is_boundary"] = df["is_four"] | df["is_six"]
    df["is_dot"] = (df["runs_total"] == 0) & (df["valid_ball"])
    print("  Block 2: is_four, is_six, is_boundary, is_dot added")
    return df


# ── Block 3: Consecutive Dot Ball Sequences ──────────────────────────────────

def _compute_dot_sequences(group: pd.DataFrame) -> pd.DataFrame:
    group = group.copy()
    # For each ball, count consecutive dots immediately preceding it
    is_dot = group["is_dot"].values
    n = len(is_dot)
    consec = np.zeros(n, dtype=np.int32)
    running = 0
    for i in range(n):
        consec[i] = running
        if is_dot[i]:
            running += 1
        else:
            running = 0
    group["consecutive_dots_before"] = consec
    return group


def block_03_dot_sequences(df: pd.DataFrame) -> pd.DataFrame:
    df = df.groupby(["match_id", "innings"], group_keys=False).apply(
        _compute_dot_sequences
    )

    # Sequence-breaking ball = non-dot ball following at least 1 dot
    df["is_sequence_breaker"] = (df["consecutive_dots_before"] > 0) & (~df["is_dot"])

    # Classify what broke the sequence
    df["dot_sequence_outcome"] = None
    mask_break = df["is_sequence_breaker"]
    df.loc[mask_break & (df["wicket_kind"] != "not_out"), "dot_sequence_outcome"] = "wicket"
    df.loc[mask_break & (df["wicket_kind"] == "not_out") & df["is_boundary"], "dot_sequence_outcome"] = "boundary"
    df.loc[
        mask_break
        & (df["wicket_kind"] == "not_out")
        & (~df["is_boundary"])
        & (df["runs_total"] > 0),
        "dot_sequence_outcome",
    ] = "scoring_shot"
    # Remaining breakers are 'other' (e.g., extras with 0 batter runs but runs_total > 0)
    df.loc[
        mask_break & df["dot_sequence_outcome"].isna(),
        "dot_sequence_outcome",
    ] = "other"

    print("  Block 3: consecutive_dots_before, is_sequence_breaker, dot_sequence_outcome added")
    return df


# ── Block 4: Partnership Tracking ────────────────────────────────────────────

def _compute_partnerships(group: pd.DataFrame) -> pd.DataFrame:
    group = group.copy()
    # Partnership changes when batting_partners changes
    group["partnership_id"] = (
        group["batting_partners"] != group["batting_partners"].shift()
    ).cumsum()
    # Cumulative runs and balls within partnership
    group["partnership_runs"] = group.groupby("partnership_id")["runs_total"].cumsum()
    group["partnership_balls"] = group.groupby("partnership_id")["valid_ball"].cumsum()
    return group


def block_04_partnerships(df: pd.DataFrame) -> pd.DataFrame:
    df = df.groupby(["match_id", "innings"], group_keys=False).apply(
        _compute_partnerships
    )
    print("  Block 4: partnership_id, partnership_runs, partnership_balls added")
    return df


# ── Block 5: Chase Metrics (2nd Innings) ─────────────────────────────────────

def _compute_chase_metrics(group: pd.DataFrame) -> pd.DataFrame:
    group = group.copy()
    innings_val = group["innings"].iloc[0]
    target = group["runs_target"].iloc[0]

    if innings_val not in (2, 4) or pd.isna(target):
        group["balls_remaining"] = np.nan
        group["runs_needed"] = np.nan
        group["required_run_rate"] = np.nan
        group["current_run_rate"] = np.nan
        group["run_rate_pressure"] = np.nan
        return group

    target = int(target)
    max_balls = 120 if innings_val == 2 else 6  # super over = 1 over

    group["balls_remaining"] = (max_balls - group["legal_ball_number"]).clip(lower=1)
    group["runs_needed"] = target - group["team_runs"]
    group["required_run_rate"] = (
        group["runs_needed"] / group["balls_remaining"] * 6
    ).round(2)
    group["current_run_rate"] = (
        group["team_runs"] / group["legal_ball_number"].clip(lower=1) * 6
    ).round(2)
    group["run_rate_pressure"] = (
        group["required_run_rate"] - group["current_run_rate"]
    ).round(2)

    return group


def block_05_chase_metrics(df: pd.DataFrame) -> pd.DataFrame:
    # Convert runs_target to float to handle None/NaN
    if "runs_target" in df.columns:
        df["runs_target"] = pd.to_numeric(df["runs_target"], errors="coerce")

    df = df.groupby(["match_id", "innings"], group_keys=False).apply(
        _compute_chase_metrics
    )
    print("  Block 5: chase metrics (RRR, CRR, pressure) added for 2nd innings")
    return df


# ── Block 6: Batting Position Bucket ─────────────────────────────────────────

def block_06_bat_position_bucket(df: pd.DataFrame) -> pd.DataFrame:
    conditions = [
        df["bat_pos"] <= 3,
        df["bat_pos"] <= 5,
        df["bat_pos"] <= 7,
    ]
    choices = ["top_order", "middle_order", "lower_middle"]
    df["batting_position_bucket"] = np.select(conditions, choices, default="tail")
    print("  Block 6: batting_position_bucket added")
    return df


# ── Block 7: Maiden Over & Over-Level Stats ──────────────────────────────────

def block_07_maiden_over(df: pd.DataFrame) -> pd.DataFrame:
    # Compute over-level stats on valid balls only
    valid = df[df["valid_ball"]].copy()
    over_stats = (
        valid.groupby(["match_id", "innings", "over", "bowler"])
        .agg(
            over_runs=("runs_total", "sum"),
            over_valid_balls=("valid_ball", "sum"),
            over_wickets=("striker_out", "sum"),
            over_dots=("is_dot", "sum"),
            over_boundaries=("is_boundary", "sum"),
        )
        .reset_index()
    )

    # Maiden: 0 runs scored off 6 legal balls
    over_stats["is_maiden"] = (
        (over_stats["over_runs"] == 0) & (over_stats["over_valid_balls"] >= 6)
    )

    # Cast types
    for col in ["over_runs", "over_dots", "over_boundaries", "over_wickets"]:
        over_stats[col] = over_stats[col].astype("int16")

    # Merge back
    df = df.merge(
        over_stats[["match_id", "innings", "over", "bowler", "is_maiden",
                     "over_runs", "over_dots", "over_boundaries", "over_wickets"]],
        on=["match_id", "innings", "over", "bowler"],
        how="left",
    )
    # Fill unmatched rows (extras-only deliveries with no valid balls from that bowler)
    df["is_maiden"] = df["is_maiden"].fillna(False)
    for col in ["over_runs", "over_dots", "over_boundaries", "over_wickets"]:
        df[col] = df[col].fillna(0).astype("int16")
    print("  Block 7: is_maiden, over_runs, over_dots, over_boundaries, over_wickets added")
    return df


# ── Block 8: Super Over Flag ─────────────────────────────────────────────────

def block_08_super_over(df: pd.DataFrame) -> pd.DataFrame:
    df["is_super_over"] = df["innings"].isin([3, 4])
    print("  Block 8: is_super_over added")
    return df


# ── Block 9: Bowler Spell Tracking ───────────────────────────────────────────

def _compute_bowler_spells(group: pd.DataFrame) -> pd.DataFrame:
    group = group.copy()
    group["bowler_changed"] = group["bowler"] != group["bowler"].shift()
    group["bowling_stint"] = group["bowler_changed"].cumsum()
    # Spell number per bowler (how many separate stints)
    group["spell_number"] = (
        group.groupby("bowler")["bowling_stint"]
        .transform(lambda x: (x != x.shift()).cumsum())
    )
    group = group.drop(columns=["bowler_changed"])
    return group


def block_09_bowler_spells(df: pd.DataFrame) -> pd.DataFrame:
    df = df.groupby(["match_id", "innings"], group_keys=False).apply(
        _compute_bowler_spells
    )
    print("  Block 9: bowling_stint, spell_number added")
    return df


# ── Block 10: Match Result Context ───────────────────────────────────────────

def block_10_match_context(df: pd.DataFrame) -> pd.DataFrame:
    # Close match: margin <= 10 runs or <= 2 wickets
    df["is_close_match"] = False
    runs_close = (df["win_margin_type"] == "runs") & (df["win_margin_value"] <= 10)
    wkt_close = (df["win_margin_type"] == "wickets") & (df["win_margin_value"] <= 2)
    df.loc[runs_close | wkt_close, "is_close_match"] = True

    # Toss winner chose to bat
    df["toss_winner_is_batting"] = (
        ((df["toss_winner"] == df["batting_team"]) & (df["toss_decision"] == "bat")) |
        ((df["toss_winner"] == df["bowling_team"]) & (df["toss_decision"] == "field"))
    )
    print("  Block 10: is_close_match, toss_winner_is_batting added")
    return df


# ── Block 11: Save Enriched Dataset ──────────────────────────────────────────

def block_11_save(df: pd.DataFrame) -> pd.DataFrame:
    # Ensure string columns don't have Python None serialization issues
    obj_cols = df.select_dtypes(include=["object"]).columns
    for col in obj_cols:
        df[col] = df[col].where(df[col].notna(), None)

    df.to_parquet(OUTPUT, index=False, engine="pyarrow")
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    new_cols = df.shape[1] - 63  # approximate original cleaned col count
    print(f"  Block 11: Saved {OUTPUT.name} ({size_mb:.1f} MB, {df.shape[0]:,} rows x {df.shape[1]} cols, ~{new_cols} new features)")
    return df


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading cleaned parquet...")
    df = pd.read_parquet(INPUT)
    print(f"  Loaded: {df.shape[0]:,} rows x {df.shape[1]} columns\n")

    df = block_01_match_phase(df)
    df = block_02_boundary_flags(df)
    df = block_03_dot_sequences(df)
    df = block_04_partnerships(df)
    df = block_05_chase_metrics(df)
    df = block_06_bat_position_bucket(df)
    df = block_07_maiden_over(df)
    df = block_08_super_over(df)
    df = block_09_bowler_spells(df)
    df = block_10_match_context(df)
    df = block_11_save(df)

    print("\nFEATURE ENGINEERING COMPLETE")


if __name__ == "__main__":
    main()
