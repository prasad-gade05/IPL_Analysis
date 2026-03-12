"""
IPL Analytics — Step 3: Build Aggregate Parquet Files
Reads enriched ball-by-ball parquet, produces 14 aggregate parquets.

Input:  data/processed/ball_by_ball.parquet
Output: data/processed/{match_summary, player_season, matchups, venue_stats,
        powerplay_stats, dot_sequences, season_structure, player_batting_match,
        player_bowling_match, partnerships, dismissal_patterns,
        dismissal_by_phase, team_season, points_table}.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT = PROJECT_ROOT / "data" / "processed" / "ball_by_ball.parquet"
OUT_DIR = PROJECT_ROOT / "data" / "processed"


def save(df: pd.DataFrame, name: str) -> None:
    """Save a DataFrame as parquet with a summary line."""
    path = OUT_DIR / f"{name}.parquet"
    df.to_parquet(path, index=False, engine="pyarrow")
    size_kb = path.stat().st_size / 1024
    print(f"    -> {name}.parquet ({len(df):,} rows, {size_kb:.0f} KB)")


# ── 1. Match Summary ────────────────────────────────────────────────────────

def agg_match_summary(df: pd.DataFrame) -> None:
    print("  Agg 1: match_summary")

    inn1 = df[df["innings"] == 1]
    inn2 = df[df["innings"] == 2]

    # Per-innings totals
    def innings_totals(innings_df):
        return (
            innings_df.groupby("match_id")
            .agg(
                score=("team_runs", "max"),
                wickets=("team_wicket", "max"),
                balls=("team_balls", "max"),
            )
            .reset_index()
        )

    t1 = innings_totals(inn1).rename(columns={"score": "team1_score", "wickets": "team1_wickets", "balls": "team1_balls"})
    t2 = innings_totals(inn2).rename(columns={"score": "team2_score", "wickets": "team2_wickets", "balls": "team2_balls"})

    # Match-level metadata (one row per match)
    match_meta = (
        df.groupby("match_id")
        .agg(
            date=("date", "first"),
            season=("season", "first"),
            venue=("venue", "first"),
            city=("city", "first"),
            toss_winner=("toss_winner", "first"),
            toss_decision=("toss_decision", "first"),
            match_won_by=("match_won_by", "first"),
            win_margin_value=("win_margin_value", "first"),
            win_margin_type=("win_margin_type", "first"),
            player_of_match=("player_of_match", "first"),
            stage=("stage", "first"),
            is_super_over_match=("is_super_over_match", "first"),
            result_type=("result_type", "first"),
            method=("method", "first"),
        )
        .reset_index()
    )

    # Team names from innings
    teams = (
        inn1.groupby("match_id")
        .agg(team1=("batting_team", "first"), team2=("bowling_team", "first"))
        .reset_index()
    )

    ms = match_meta.merge(teams, on="match_id", how="left")
    ms = ms.merge(t1, on="match_id", how="left")
    ms = ms.merge(t2, on="match_id", how="left")

    # Fill NaN scores for matches with no 2nd innings
    for col in ["team2_score", "team2_wickets", "team2_balls"]:
        ms[col] = ms[col].fillna(0).astype(int)

    ms["batting_first_won"] = ms["team1"] == ms["match_won_by"]

    save(ms, "match_summary")


# ── 2. Player-Season Mapping ────────────────────────────────────────────────

def agg_player_season(df: pd.DataFrame) -> None:
    print("  Agg 2: player_season")

    # Batting appearances
    bat = (
        df.groupby(["season", "batter", "batting_team"])
        .agg(balls_as_batter=("valid_ball", "sum"))
        .reset_index()
        .rename(columns={"batter": "player", "batting_team": "team"})
    )

    # Bowling appearances
    bowl = (
        df.groupby(["season", "bowler", "bowling_team"])
        .agg(balls_as_bowler=("valid_ball", "sum"))
        .reset_index()
        .rename(columns={"bowler": "player", "bowling_team": "team"})
    )

    ps = pd.merge(bat, bowl, on=["season", "player", "team"], how="outer")
    ps["balls_as_batter"] = ps["balls_as_batter"].fillna(0).astype(int)
    ps["balls_as_bowler"] = ps["balls_as_bowler"].fillna(0).astype(int)

    # Team's best stage that season
    stage_rank = {"League": 0, "Eliminator": 1, "Elimination Final": 1,
                  "3rd Place Play-Off": 2, "Qualifier 1": 2, "Semi Final": 3,
                  "Qualifier 2": 3, "Final": 4}

    team_stage = (
        df.groupby(["season", "batting_team"])["stage"]
        .apply(lambda x: x.map(stage_rank).max())
        .reset_index()
        .rename(columns={"batting_team": "team", "stage": "best_stage_rank"})
    )

    ps = ps.merge(team_stage, on=["season", "team"], how="left")

    # Did team win the title?
    champions = (
        df[df["stage"] == "Final"]
        .groupby("season")["match_won_by"]
        .first()
        .reset_index()
        .rename(columns={"match_won_by": "champion"})
    )
    ps = ps.merge(champions, on="season", how="left")
    ps["won_title"] = ps["team"] == ps["champion"]
    ps = ps.drop(columns=["champion"], errors="ignore")

    save(ps, "player_season")


# ── 3. Batter vs Bowler Matchups ─────────────────────────────────────────────

def agg_matchups(df: pd.DataFrame) -> None:
    print("  Agg 3: matchups")

    # Use ALL deliveries — batter runs on no-balls ARE credited to the batter.
    # Only ball count uses valid_ball (no-balls don't count as balls faced).
    mu = (
        df.groupby(["batter", "bowler"])
        .agg(
            balls=("valid_ball", "sum"),
            runs=("runs_batter", "sum"),
            dots=("is_dot", "sum"),
            fours=("is_four", "sum"),
            sixes=("is_six", "sum"),
            dismissals=("striker_out", "sum"),
        )
        .reset_index()
    )

    mu["strike_rate"] = (mu["runs"] / mu["balls"].clip(lower=1) * 100).round(1)
    mu["dot_pct"] = (mu["dots"] / mu["balls"].clip(lower=1) * 100).round(1)
    mu["boundary_pct"] = ((mu["fours"] + mu["sixes"]) / mu["balls"].clip(lower=1) * 100).round(1)
    mu["average"] = (mu["runs"] / mu["dismissals"].clip(lower=1)).round(1)

    save(mu, "matchups")


# ── 4. Venue Statistics ──────────────────────────────────────────────────────

def agg_venue_stats(df: pd.DataFrame) -> None:
    print("  Agg 4: venue_stats")

    # Per innings totals
    inn = (
        df.groupby(["match_id", "innings", "venue", "city"])
        .agg(
            total_runs=("team_runs", "max"),
            wickets=("team_wicket", "max"),
            valid_balls=("valid_ball", "sum"),
            boundaries=("is_boundary", "sum"),
        )
        .reset_index()
    )

    # Venue-level aggregation
    vs = (
        inn.groupby(["venue", "city"])
        .agg(
            total_matches=("match_id", "nunique"),
            avg_score=("total_runs", "mean"),
            avg_wickets=("wickets", "mean"),
            avg_boundaries=("boundaries", "mean"),
        )
        .reset_index()
    )

    # First vs second innings averages
    for label, inns_val in [("first", 1), ("second", 2)]:
        subset = inn[inn["innings"] == inns_val]
        avg = subset.groupby("venue")["total_runs"].mean().reset_index()
        avg.columns = ["venue", f"avg_{label}_innings"]
        vs = vs.merge(avg, on="venue", how="left")

    # Bat-first win %
    match_result = (
        df[df["innings"] == 1]
        .groupby(["match_id", "venue"])
        .agg(
            team1=("batting_team", "first"),
            match_won_by=("match_won_by", "first"),
        )
        .reset_index()
    )
    match_result["bat_first_won"] = match_result["team1"] == match_result["match_won_by"]
    bf_pct = (
        match_result.groupby("venue")["bat_first_won"]
        .mean()
        .mul(100).round(1)
        .reset_index()
        .rename(columns={"bat_first_won": "bat_first_win_pct"})
    )
    vs = vs.merge(bf_pct, on="venue", how="left")

    # Round float columns
    for col in ["avg_score", "avg_wickets", "avg_boundaries", "avg_first_innings", "avg_second_innings"]:
        if col in vs.columns:
            vs[col] = vs[col].round(1)

    save(vs, "venue_stats")


# ── 5. Powerplay Stats ──────────────────────────────────────────────────────

def agg_powerplay_stats(df: pd.DataFrame) -> None:
    print("  Agg 5: powerplay_stats")

    # Include ALL powerplay deliveries — batter runs on no-balls count.
    # Ball count uses valid_ball column (no-balls don't count as legal deliveries).
    pp = df[df["over"] <= 6].copy()

    pps = (
        pp.groupby(["match_id", "innings", "season", "batting_team"])
        .agg(
            pp_runs=("runs_total", "sum"),
            pp_wickets=("striker_out", "sum"),
            pp_dots=("is_dot", "sum"),
            pp_boundaries=("is_boundary", "sum"),
            pp_fours=("is_four", "sum"),
            pp_sixes=("is_six", "sum"),
            pp_balls=("valid_ball", "sum"),
        )
        .reset_index()
    )

    pps["pp_run_rate"] = (pps["pp_runs"] / pps["pp_balls"].clip(lower=1) * 6).round(2)
    pps["pp_dot_pct"] = (pps["pp_dots"] / pps["pp_balls"].clip(lower=1) * 100).round(1)
    pps["pp_boundary_pct"] = (pps["pp_boundaries"] / pps["pp_balls"].clip(lower=1) * 100).round(1)

    save(pps, "powerplay_stats")


# ── 6. Dot Ball Sequences ───────────────────────────────────────────────────

def agg_dot_sequences(df: pd.DataFrame) -> None:
    print("  Agg 6: dot_sequences")

    breakers = df[df["is_sequence_breaker"]].copy()

    ds = (
        breakers.groupby(["consecutive_dots_before", "dot_sequence_outcome"])
        .size()
        .reset_index(name="count")
    )

    # Calculate percentages within each dot-count group
    totals = ds.groupby("consecutive_dots_before")["count"].transform("sum")
    ds["pct"] = (ds["count"] / totals * 100).round(1)

    save(ds, "dot_sequences")


# ── 7. Season Structure ─────────────────────────────────────────────────────

def agg_season_structure(df: pd.DataFrame) -> None:
    print("  Agg 7: season_structure")

    # Per-season stats
    ss = (
        df.groupby("season")
        .agg(
            total_matches=("match_id", "nunique"),
            start_date=("date", "min"),
            end_date=("date", "max"),
            num_venues=("venue", "nunique"),
            num_cities=("city", "nunique"),
        )
        .reset_index()
    )

    # Number of teams
    teams_per_season = (
        df.groupby("season")["batting_team"].nunique().reset_index()
        .rename(columns={"batting_team": "num_teams"})
    )
    ss = ss.merge(teams_per_season, on="season", how="left")

    # Champion
    finals = df[df["stage"] == "Final"]
    champs = (
        finals.groupby("season")["match_won_by"].first().reset_index()
        .rename(columns={"match_won_by": "champion"})
    )
    ss = ss.merge(champs, on="season", how="left")

    # Super over matches
    so = (
        df.groupby("season")["is_super_over_match"]
        .any().reset_index()
        .rename(columns={"is_super_over_match": "has_super_over"})
    )
    ss = ss.merge(so, on="season", how="left")

    # DLS matches
    dls = (
        df[df["method"] != "no_dls"]
        .groupby("season")["match_id"].nunique().reset_index()
        .rename(columns={"match_id": "dls_matches"})
    )
    ss = ss.merge(dls, on="season", how="left")
    ss["dls_matches"] = ss["dls_matches"].fillna(0).astype(int)

    # Duration
    ss["duration_days"] = (ss["end_date"] - ss["start_date"]).dt.days

    save(ss, "season_structure")


# ── 8. Player Match Performance ──────────────────────────────────────────────

def agg_player_batting_match(df: pd.DataFrame) -> None:
    print("  Agg 8a: player_batting_match")

    # Use ALL deliveries — batter runs on no-balls ARE credited to the batter.
    # Only ball count uses valid_ball (no-balls don't count as balls faced).
    pbm = (
        df.groupby(["match_id", "season", "batter", "batting_team", "innings", "venue"])
        .agg(
            runs=("runs_batter", "sum"),
            balls=("valid_ball", "sum"),
            fours=("is_four", "sum"),
            sixes=("is_six", "sum"),
            dots_faced=("is_dot", "sum"),
            bat_position=("bat_pos", "first"),
            was_out=("striker_out", "max"),
        )
        .reset_index()
    )

    pbm["strike_rate"] = (pbm["runs"] / pbm["balls"].clip(lower=1) * 100).round(1)
    pbm["dot_pct"] = (pbm["dots_faced"] / pbm["balls"].clip(lower=1) * 100).round(1)
    pbm["is_fifty"] = pbm["runs"] >= 50
    pbm["is_hundred"] = pbm["runs"] >= 100
    pbm["is_duck"] = (pbm["runs"] == 0) & (pbm["was_out"] == 1)

    save(pbm, "player_batting_match")


def agg_player_bowling_match(df: pd.DataFrame) -> None:
    print("  Agg 8b: player_bowling_match")

    # Use ALL deliveries — bowler is charged runs on no-balls too.
    # Only ball count uses valid_ball (no-balls don't count as legal deliveries).
    pbm = (
        df.groupby(["match_id", "season", "bowler", "bowling_team", "innings", "venue"])
        .agg(
            runs_conceded=("runs_bowler", "sum"),
            balls_bowled=("valid_ball", "sum"),
            wickets=("bowler_wicket", "sum"),
            dots_bowled=("is_dot", "sum"),
            boundaries_conceded=("is_boundary", "sum"),
        )
        .reset_index()
    )

    # Maidens: count overs with is_maiden=True for this bowler in this match/innings
    maiden_overs = (
        df[df["is_maiden"] == True]
        .groupby(["match_id", "innings", "bowler"])["over"]
        .nunique()
        .reset_index()
        .rename(columns={"over": "maidens"})
    )
    pbm = pbm.merge(maiden_overs, on=["match_id", "innings", "bowler"], how="left")
    pbm["maidens"] = pbm["maidens"].fillna(0).astype(int)

    pbm["economy"] = (pbm["runs_conceded"] / pbm["balls_bowled"].clip(lower=1) * 6).round(2)
    pbm["bowling_sr"] = np.where(
        pbm["wickets"] > 0,
        (pbm["balls_bowled"] / pbm["wickets"]).round(1),
        np.nan,
    )
    pbm["dot_pct"] = (pbm["dots_bowled"] / pbm["balls_bowled"].clip(lower=1) * 100).round(1)

    save(pbm, "player_bowling_match")


# ── 9. Partnership Summary ──────────────────────────────────────────────────

def agg_partnerships(df: pd.DataFrame) -> None:
    print("  Agg 9: partnerships")

    ps = (
        df.groupby(["match_id", "innings", "season", "batting_team", "partnership_id", "batting_partners"])
        .agg(
            runs=("runs_total", "sum"),
            balls=("valid_ball", "sum"),
            boundaries=("is_boundary", "sum"),
            team_wicket_at_start=("team_wicket", "first"),
        )
        .reset_index()
    )

    ps["run_rate"] = (ps["runs"] / ps["balls"].clip(lower=1) * 6).round(2)
    ps["wicket_number"] = ps["team_wicket_at_start"] + 1

    save(ps, "partnerships")


# ── 10. Dismissal Patterns ───────────────────────────────────────────────────

def agg_dismissals(df: pd.DataFrame) -> None:
    print("  Agg 10: dismissal_patterns + dismissal_by_phase")

    dismissed = df[df["wicket_kind"] != "not_out"].copy()

    # Overall
    dp = (
        dismissed.groupby(["player_out", "wicket_kind"])
        .size()
        .reset_index(name="count")
    )
    save(dp, "dismissal_patterns")

    # By phase
    dbp = (
        dismissed.groupby(["player_out", "wicket_kind", "match_phase"])
        .size()
        .reset_index(name="count")
    )
    save(dbp, "dismissal_by_phase")


# ── 11. Team-Season Stats ───────────────────────────────────────────────────

def agg_team_season(df: pd.DataFrame) -> None:
    print("  Agg 11: team_season")

    # Get match results per team
    # A team participates as either batting_team in innings 1 or bowling_team in innings 1
    inn1 = df[df["innings"] == 1].groupby("match_id").first().reset_index()

    records = []
    for _, row in inn1.iterrows():
        mid = row["match_id"]
        season = row["season"]
        t1, t2 = row["batting_team"], row["bowling_team"]
        winner = row["match_won_by"]

        for team in [t1, t2]:
            if winner == team:
                result = "won"
            elif winner and str(winner) not in ("None", "nan", ""):
                result = "lost"
            else:
                result = "no_result"
            records.append({"match_id": mid, "season": season, "team": team, "result": result})

    tr = pd.DataFrame(records)

    ts = (
        tr.groupby(["season", "team"])
        .agg(
            matches_played=("result", "count"),
            wins=("result", lambda x: (x == "won").sum()),
            losses=("result", lambda x: (x == "lost").sum()),
            no_results=("result", lambda x: (x == "no_result").sum()),
        )
        .reset_index()
    )

    ts["win_pct"] = (ts["wins"] / ts["matches_played"].clip(lower=1) * 100).round(1)

    save(ts, "team_season")


# ── 12. Points Table ─────────────────────────────────────────────────────────

def agg_points_table(df: pd.DataFrame) -> None:
    print("  Agg 12: points_table")

    # Filter to league stage only for points table
    league = df[df["stage"] == "League"].copy()

    inn1 = league[league["innings"] == 1].groupby("match_id").first().reset_index()

    records = []
    for _, row in inn1.iterrows():
        mid = row["match_id"]
        season = row["season"]
        t1, t2 = row["batting_team"], row["bowling_team"]
        winner = row["match_won_by"]

        for team in [t1, t2]:
            if winner == team:
                result = "won"
                points = 2
            elif winner and str(winner) not in ("None", "nan", ""):
                result = "lost"
                points = 0
            else:
                result = "no_result"
                points = 1
            records.append({
                "match_id": mid, "season": season, "team": team,
                "result": result, "points": points,
            })

    tr = pd.DataFrame(records)

    pt = (
        tr.groupby(["season", "team"])
        .agg(
            played=("result", "count"),
            won=("result", lambda x: (x == "won").sum()),
            lost=("result", lambda x: (x == "lost").sum()),
            nr=("result", lambda x: (x == "no_result").sum()),
            points=("points", "sum"),
        )
        .reset_index()
    )

    # Net Run Rate calculation
    # For each team-season, compute total runs scored / overs faced - total runs conceded / overs bowled
    nrr_records = []
    for (season, team), grp in league.groupby(["season", "batting_team"]):
        # Runs scored and balls faced
        runs_scored = grp.groupby("match_id")["team_runs"].max().sum()
        balls_faced = grp.groupby("match_id")["team_balls"].max().sum()
        overs_faced = balls_faced / 6

        # Runs conceded = runs scored against this team (when they're bowling)
        bowling = league[(league["season"] == season) & (league["bowling_team"] == team)]
        runs_conceded = bowling.groupby("match_id")["team_runs"].max().sum()
        balls_bowled = bowling.groupby("match_id")["team_balls"].max().sum()
        overs_bowled = balls_bowled / 6

        nrr = 0.0
        if overs_faced > 0 and overs_bowled > 0:
            nrr = round(runs_scored / overs_faced - runs_conceded / overs_bowled, 3)

        nrr_records.append({"season": season, "team": team, "nrr": nrr})

    nrr_df = pd.DataFrame(nrr_records)
    pt = pt.merge(nrr_df, on=["season", "team"], how="left")
    pt["nrr"] = pt["nrr"].fillna(0.0)

    # Sort by season, points desc, nrr desc
    pt = pt.sort_values(["season", "points", "nrr"], ascending=[True, False, False])
    pt["position"] = pt.groupby("season").cumcount() + 1

    save(pt, "points_table")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading enriched ball-by-ball data...")
    df = pd.read_parquet(INPUT)
    print(f"  Loaded: {df.shape[0]:,} rows x {df.shape[1]} columns\n")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    agg_match_summary(df)
    agg_player_season(df)
    agg_matchups(df)
    agg_venue_stats(df)
    agg_powerplay_stats(df)
    agg_dot_sequences(df)
    agg_season_structure(df)
    agg_player_batting_match(df)
    agg_player_bowling_match(df)
    agg_partnerships(df)
    agg_dismissals(df)
    agg_team_season(df)
    agg_points_table(df)

    print("\nAGGREGATION COMPLETE")
    total_files = len(list(OUT_DIR.glob("*.parquet")))
    total_size = sum(f.stat().st_size for f in OUT_DIR.glob("*.parquet")) / (1024 * 1024)
    print(f"  {total_files} parquet files, {total_size:.1f} MB total")


if __name__ == "__main__":
    main()
