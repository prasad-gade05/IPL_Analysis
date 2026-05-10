"""
IPL Analytics — Step 3: Build Aggregate Parquet Files
Reads enriched ball-by-ball parquet, produces 18 aggregate parquets.

Input:  data/processed/ball_by_ball.parquet
Output: data/processed/{match_summary, player_season, matchups, venue_stats,
        powerplay_stats, dot_sequences, season_structure, player_batting_match,
        player_bowling_match, partnerships, dismissal_patterns,
        dismissal_by_phase, team_season, points_table, team_match_results,
        over_summary, innings_tags, player_season_metrics}.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT = PROJECT_ROOT / "Data" / "processed" / "ball_by_ball.parquet"
OUT_DIR = PROJECT_ROOT / "Data" / "processed"


def save(df: pd.DataFrame, name: str) -> None:
    """Save a DataFrame as parquet with a summary line."""
    path = OUT_DIR / f"{name}.parquet"
    df.to_parquet(path, index=False, engine="pyarrow")
    size_kb = path.stat().st_size / 1024
    print(f"    -> {name}.parquet ({len(df):,} rows, {size_kb:.0f} KB)")


def _first_non_null(series: pd.Series):
    """Return the first non-null value from a series, else NaN."""
    values = series.dropna()
    if values.empty:
        return np.nan
    return values.iloc[0]


def build_match_summary_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build the match summary dataframe for reuse by helper aggregates."""
    inn1 = df[df["innings"] == 1]
    inn2 = df[df["innings"] == 2]

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

    t1 = innings_totals(inn1).rename(
        columns={"score": "team1_score", "wickets": "team1_wickets", "balls": "team1_balls"}
    )
    t2 = innings_totals(inn2).rename(
        columns={"score": "team2_score", "wickets": "team2_wickets", "balls": "team2_balls"}
    )

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
            is_close_match=("is_close_match", "first"),
        )
        .reset_index()
    )

    teams = (
        inn1.groupby("match_id")
        .agg(team1=("batting_team", "first"), team2=("bowling_team", "first"))
        .reset_index()
    )

    second_innings_target = (
        inn2.groupby("match_id")["runs_target"]
        .agg(_first_non_null)
        .reset_index()
        .rename(columns={"runs_target": "stored_chase_target"})
    )

    ms = match_meta.merge(teams, on="match_id", how="left")
    ms = ms.merge(t1, on="match_id", how="left")
    ms = ms.merge(t2, on="match_id", how="left")
    ms = ms.merge(second_innings_target, on="match_id", how="left")

    has_second_innings = ms["team2_score"].notna()
    ms["actual_chase_target"] = ms["stored_chase_target"].where(
        ms["stored_chase_target"].notna(),
        np.where(has_second_innings, ms["team1_score"] + 1, np.nan),
    )

    for col in ["team2_score", "team2_wickets", "team2_balls"]:
        ms[col] = ms[col].fillna(0).astype(int)

    ms["batting_first_won"] = ms["team1"] == ms["match_won_by"]

    return ms


def build_player_batting_match_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build per-match batting innings aggregates."""
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

    return pbm


def build_player_bowling_match_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build per-match bowling innings aggregates."""
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

    return pbm


# ── 1. Match Summary ────────────────────────────────────────────────────────

def agg_match_summary(df: pd.DataFrame) -> None:
    print("  Agg 1: match_summary")
    save(build_match_summary_frame(df), "match_summary")


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
    save(build_player_batting_match_frame(df), "player_batting_match")


def agg_player_bowling_match(df: pd.DataFrame) -> None:
    print("  Agg 8b: player_bowling_match")
    save(build_player_bowling_match_frame(df), "player_bowling_match")


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


# ── 13. Team Match Results ─────────────────────────────────────────────────────

def agg_team_match_results(df: pd.DataFrame) -> None:
    print("  Agg 13: team_match_results")

    ms = build_match_summary_frame(df)

    team1 = ms[
        [
            "match_id", "date", "season", "venue", "city", "stage", "result_type",
            "method", "is_super_over_match", "is_close_match", "toss_winner",
            "toss_decision", "match_won_by", "win_margin_value", "win_margin_type",
            "team1", "team2", "team1_score", "team1_wickets", "team1_balls",
            "team2_score", "team2_wickets", "team2_balls",
        ]
    ].copy()
    team1 = team1.rename(
        columns={
            "team1": "team",
            "team2": "opponent",
            "team1_score": "runs_scored",
            "team1_wickets": "wickets_lost",
            "team1_balls": "balls_faced",
            "team2_score": "runs_conceded",
            "team2_wickets": "wickets_taken",
            "team2_balls": "balls_bowled",
        }
    )
    team1["innings"] = 1
    team1["batting_first"] = True
    team1["chasing"] = False
    team1["target_to_win"] = np.nan
    team1["total_to_defend"] = team1["runs_scored"] + 1

    team2 = ms[
        [
            "match_id", "date", "season", "venue", "city", "stage", "result_type",
            "method", "is_super_over_match", "is_close_match", "toss_winner",
            "toss_decision", "match_won_by", "win_margin_value", "win_margin_type",
            "actual_chase_target", "team1", "team2", "team1_score", "team1_wickets",
            "team1_balls", "team2_score", "team2_wickets", "team2_balls",
        ]
    ].copy()
    team2 = team2.rename(
        columns={
            "team2": "team",
            "team1": "opponent",
            "team2_score": "runs_scored",
            "team2_wickets": "wickets_lost",
            "team2_balls": "balls_faced",
            "team1_score": "runs_conceded",
            "team1_wickets": "wickets_taken",
            "team1_balls": "balls_bowled",
            "actual_chase_target": "target_to_win",
        }
    )
    team2["innings"] = 2
    team2["batting_first"] = False
    team2["chasing"] = True
    team2["total_to_defend"] = np.nan

    team_matches = pd.concat([team1, team2], ignore_index=True)

    winner = team_matches["match_won_by"].fillna("").astype(str)
    has_winner = ~winner.isin(["", "None", "nan"])
    team_matches["result"] = np.where(
        team_matches["team"] == winner,
        "won",
        np.where(has_winner, "lost", "no_result"),
    )
    team_matches["won"] = team_matches["result"] == "won"
    team_matches["lost"] = team_matches["result"] == "lost"
    team_matches["no_result"] = team_matches["result"] == "no_result"
    team_matches["toss_won"] = team_matches["toss_winner"] == team_matches["team"]
    team_matches["successful_chase"] = team_matches["chasing"] & team_matches["won"]
    team_matches["successful_defense"] = team_matches["batting_first"] & team_matches["won"]

    save(team_matches, "team_match_results")


# ── 14. Over Summary ───────────────────────────────────────────────────────────

def agg_over_summary(df: pd.DataFrame) -> None:
    print("  Agg 14: over_summary")

    extra_type = df["extra_type"].fillna("")
    over = (
        df.groupby(
            [
                "match_id", "season", "date", "venue", "stage", "innings",
                "match_phase", "batting_team", "bowling_team", "over", "bowler",
            ]
        )
        .agg(
            deliveries_total=("ball", "size"),
            legal_balls=("valid_ball", "sum"),
            runs_total=("runs_total", "sum"),
            runs_batter=("runs_batter", "sum"),
            runs_bowler=("runs_bowler", "sum"),
            extras=("runs_extras", "sum"),
            wickets=("bowler_wicket", "sum"),
            striker_wickets=("striker_out", "sum"),
            dots=("is_dot", "sum"),
            boundaries=("is_boundary", "sum"),
            fours=("is_four", "sum"),
            sixes=("is_six", "sum"),
            wides=("extra_type", lambda s: (s == "wide").sum()),
            no_balls=("extra_type", lambda s: (s == "noballs").sum()),
            byes=("extra_type", lambda s: (s == "byes").sum()),
            leg_byes=("extra_type", lambda s: (s == "legbyes").sum()),
            is_maiden=("is_maiden", "max"),
        )
        .reset_index()
    )

    over["economy"] = (over["runs_bowler"] / over["legal_balls"].clip(lower=1) * 6).round(2)
    over["run_rate"] = (over["runs_total"] / over["legal_balls"].clip(lower=1) * 6).round(2)
    over["is_long_over"] = over["deliveries_total"] > 6

    save(over, "over_summary")


# ── 15. Batting Innings Tags ───────────────────────────────────────────────────

def agg_innings_tags(df: pd.DataFrame) -> None:
    print("  Agg 15: innings_tags")

    batting = build_player_batting_match_frame(df)
    ms = build_match_summary_frame(df)[
        [
            "match_id", "date", "season", "venue", "city", "stage", "team1", "team2",
            "match_won_by", "result_type", "method", "actual_chase_target",
        ]
    ]

    tags = batting.merge(ms, on=["match_id", "season", "venue"], how="left")
    tags["opposition"] = np.where(tags["batting_team"] == tags["team1"], tags["team2"], tags["team1"])

    winner = tags["match_won_by"].fillna("").astype(str)
    has_winner = ~winner.isin(["", "None", "nan"])
    tags["result"] = np.where(
        tags["batting_team"] == winner,
        "won",
        np.where(has_winner, "lost", "no_result"),
    )
    tags["won"] = tags["result"] == "won"
    tags["lost"] = tags["result"] == "lost"
    tags["no_result"] = tags["result"] == "no_result"
    tags["batting_first"] = tags["innings"] == 1
    tags["chasing"] = tags["innings"] == 2
    tags["target_to_win"] = np.where(tags["innings"] == 2, tags["actual_chase_target"], np.nan)

    tags["is_not_out"] = tags["was_out"] == 0
    tags["is_score_20_plus"] = tags["runs"] >= 20
    tags["is_score_30_plus"] = tags["runs"] >= 30
    tags["is_score_40_plus"] = tags["runs"] >= 40
    tags["is_score_50_plus"] = tags["runs"] >= 50
    tags["is_score_90s"] = tags["runs"].between(90, 99)
    tags["is_score_49"] = tags["runs"] == 49
    tags["is_score_99"] = tags["runs"] == 99
    tags["boundary_pct"] = (
        (tags["fours"] + tags["sixes"]) / tags["balls"].clip(lower=1) * 100
    ).round(1)

    tags = tags[
        [
            "match_id", "date", "season", "venue", "city", "stage", "batter", "batting_team",
            "opposition", "innings", "batting_first", "chasing", "target_to_win", "result",
            "won", "lost", "no_result", "runs", "balls", "fours", "sixes", "dots_faced",
            "bat_position", "was_out", "is_not_out", "strike_rate", "dot_pct", "boundary_pct",
            "is_duck", "is_fifty", "is_hundred", "is_score_20_plus", "is_score_30_plus",
            "is_score_40_plus", "is_score_50_plus", "is_score_90s", "is_score_49", "is_score_99",
        ]
    ]

    save(tags, "innings_tags")


# ── 16. Player Season Metrics ──────────────────────────────────────────────────

def agg_player_season_metrics(df: pd.DataFrame) -> None:
    print("  Agg 16: player_season_metrics")

    batting = build_player_batting_match_frame(df)
    bowling = build_player_bowling_match_frame(df)

    batting["is_score_20_plus"] = batting["runs"] >= 20
    batting["is_score_30_plus"] = batting["runs"] >= 30

    bat = (
        batting.groupby(["season", "batter"])
        .agg(
            batting_innings=("match_id", "count"),
            batting_matches=("match_id", "nunique"),
            runs=("runs", "sum"),
            balls=("balls", "sum"),
            fours=("fours", "sum"),
            sixes=("sixes", "sum"),
            dots_faced=("dots_faced", "sum"),
            outs=("was_out", "sum"),
            fifties=("is_fifty", "sum"),
            hundreds=("is_hundred", "sum"),
            ducks=("is_duck", "sum"),
            scores_20_plus=("is_score_20_plus", "sum"),
            scores_30_plus=("is_score_30_plus", "sum"),
        )
        .reset_index()
        .rename(columns={"batter": "player"})
    )

    bowl = (
        bowling.groupby(["season", "bowler"])
        .agg(
            bowling_innings=("match_id", "count"),
            bowling_matches=("match_id", "nunique"),
            wickets=("wickets", "sum"),
            runs_conceded=("runs_conceded", "sum"),
            balls_bowled=("balls_bowled", "sum"),
            maidens=("maidens", "sum"),
            dots_bowled=("dots_bowled", "sum"),
            boundaries_conceded=("boundaries_conceded", "sum"),
            three_wicket_hauls=("wickets", lambda s: (s >= 3).sum()),
            four_wicket_hauls=("wickets", lambda s: (s >= 4).sum()),
            five_wicket_hauls=("wickets", lambda s: (s >= 5).sum()),
        )
        .reset_index()
        .rename(columns={"bowler": "player"})
    )

    primary_team_candidates = pd.concat(
        [
            df.groupby(["season", "batter", "batting_team"])["valid_ball"]
            .sum()
            .reset_index()
            .rename(columns={"batter": "player", "batting_team": "team", "valid_ball": "usage"}),
            df.groupby(["season", "bowler", "bowling_team"])["valid_ball"]
            .sum()
            .reset_index()
            .rename(columns={"bowler": "player", "bowling_team": "team", "valid_ball": "usage"}),
        ],
        ignore_index=True,
    )
    primary_team = (
        primary_team_candidates.groupby(["season", "player", "team"], as_index=False)["usage"]
        .sum()
        .sort_values(["season", "player", "usage", "team"], ascending=[True, True, False, True])
        .drop_duplicates(["season", "player"])
        [["season", "player", "team"]]
    )

    player_matches = pd.concat(
        [
            df[["season", "match_id", "batter"]]
            .rename(columns={"batter": "player"}),
            df[["season", "match_id", "bowler"]]
            .rename(columns={"bowler": "player"}),
        ],
        ignore_index=True,
    ).dropna()
    player_matches = (
        player_matches.drop_duplicates()
        .groupby(["season", "player"])["match_id"]
        .nunique()
        .reset_index()
        .rename(columns={"match_id": "matches"})
    )

    champions = (
        df[df["stage"] == "Final"]
        .groupby("season")["match_won_by"]
        .first()
        .reset_index()
        .rename(columns={"match_won_by": "champion"})
    )

    season_metrics = bat.merge(bowl, on=["season", "player"], how="outer")
    season_metrics = season_metrics.merge(primary_team, on=["season", "player"], how="left")
    season_metrics = season_metrics.merge(player_matches, on=["season", "player"], how="left")
    season_metrics = season_metrics.merge(champions, on="season", how="left")

    int_columns = [
        "batting_innings", "batting_matches", "runs", "balls", "fours", "sixes", "dots_faced",
        "outs", "fifties", "hundreds", "ducks", "scores_20_plus", "scores_30_plus",
        "bowling_innings", "bowling_matches", "wickets", "runs_conceded", "balls_bowled",
        "maidens", "dots_bowled", "boundaries_conceded", "three_wicket_hauls",
        "four_wicket_hauls", "five_wicket_hauls", "matches",
    ]
    for col in int_columns:
        if col in season_metrics.columns:
            season_metrics[col] = season_metrics[col].fillna(0).astype(int)

    season_metrics["batting_average"] = (
        season_metrics["runs"] / season_metrics["outs"].replace(0, np.nan)
    ).round(2)
    season_metrics["strike_rate"] = (
        season_metrics["runs"] * 100.0 / season_metrics["balls"].replace(0, np.nan)
    ).round(1)
    season_metrics["economy"] = (
        season_metrics["runs_conceded"] * 6.0 / season_metrics["balls_bowled"].replace(0, np.nan)
    ).round(2)
    season_metrics["bowling_average"] = (
        season_metrics["runs_conceded"] / season_metrics["wickets"].replace(0, np.nan)
    ).round(2)
    season_metrics["bowling_sr"] = (
        season_metrics["balls_bowled"] / season_metrics["wickets"].replace(0, np.nan)
    ).round(1)
    season_metrics["won_title"] = season_metrics["team"] == season_metrics["champion"]

    season_metrics = season_metrics.drop(columns=["champion"], errors="ignore")

    save(season_metrics, "player_season_metrics")


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
    agg_team_match_results(df)
    agg_over_summary(df)
    agg_innings_tags(df)
    agg_player_season_metrics(df)

    print("\nAGGREGATION COMPLETE")
    total_files = len(list(OUT_DIR.glob("*.parquet")))
    total_size = sum(f.stat().st_size for f in OUT_DIR.glob("*.parquet")) / (1024 * 1024)
    print(f"  {total_files} parquet files, {total_size:.1f} MB total")


if __name__ == "__main__":
    main()
