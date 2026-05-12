"""Deterministic semantic planner for supported IPL stat questions."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import re

from src.db.connection import query
from src.semantic.aliases import PHASE_ALIASES, STAGE_ALIASES, UNSUPPORTED_KEYWORDS
from src.semantic.examples import related_prompts


@dataclass
class ResolvedFilters:
    season_from: int | None = None
    season_to: int | None = None
    top_n: int | None = None
    ranking_mode: str = "top"
    team: str | None = None
    opponent: str | None = None
    venue: str | None = None
    player: str | None = None
    bowler: str | None = None
    phase: str | None = None
    result: str | None = None
    stage_values: list[str] | None = None
    reference_player: str | None = None


@dataclass
class SemanticPlan:
    question: str
    supported: bool
    intent_id: str = ""
    title: str = ""
    question_understood_as: str = ""
    metric_label: str = ""
    grouping_label: str = ""
    active_filters: list[str] = field(default_factory=list)
    sample_constraints: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    related_prompts: list[str] = field(default_factory=list)
    chart_type: str = "bar"
    chart_x: str = ""
    chart_y: str = ""
    sql_override: str | None = None
    unsupported_reason: str | None = None


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _word_boundary_contains(text: str, value: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(value.lower()) + r"(?!\w)"
    return re.search(pattern, text) is not None


@lru_cache(maxsize=1)
def _teams() -> tuple[str, ...]:
    df = query("SELECT DISTINCT team FROM team_match_results ORDER BY team")
    return tuple(df["team"].dropna().tolist())


@lru_cache(maxsize=1)
def _venues() -> tuple[str, ...]:
    df = query("SELECT DISTINCT venue FROM matches ORDER BY venue")
    return tuple(df["venue"].dropna().tolist())


@lru_cache(maxsize=1)
def _batters() -> tuple[str, ...]:
    df = query("SELECT DISTINCT batter FROM innings_tags ORDER BY batter")
    return tuple(df["batter"].dropna().tolist())


@lru_cache(maxsize=1)
def _bowlers() -> tuple[str, ...]:
    df = query("SELECT DISTINCT bowler FROM player_bowling ORDER BY bowler")
    return tuple(df["bowler"].dropna().tolist())


def _extract_named_candidate(question: str, candidates: tuple[str, ...]) -> str | None:
    normalized = " " + _normalize(re.sub(r"[^a-zA-Z0-9 ]+", " ", question)) + " "
    matches = []
    for candidate in candidates:
        candidate_norm = " " + _normalize(re.sub(r"[^a-zA-Z0-9 ]+", " ", candidate)) + " "
        if candidate_norm.strip() and candidate_norm in normalized:
            matches.append(candidate)
    if not matches:
        return None
    return max(matches, key=len)


def _extract_seasons(question: str) -> tuple[int | None, int | None]:
    if match := re.search(r"\bbetween\s+(20\d{2})\s+and\s+(20\d{2})\b", question):
        start, end = int(match.group(1)), int(match.group(2))
        return min(start, end), max(start, end)
    if match := re.search(r"\bfrom\s+(20\d{2})\s+to\s+(20\d{2})\b", question):
        start, end = int(match.group(1)), int(match.group(2))
        return min(start, end), max(start, end)
    if match := re.search(r"\b(20\d{2})\s*[-/]\s*(20\d{2})\b", question):
        start, end = int(match.group(1)), int(match.group(2))
        return min(start, end), max(start, end)
    if match := re.search(r"\bsince\s+(20\d{2})\b", question):
        return int(match.group(1)), None
    if match := re.search(r"\bafter\s+(20\d{2})\b", question):
        return int(match.group(1)) + 1, None
    if match := re.search(r"\bin\s+(20\d{2})\b", question):
        year = int(match.group(1))
        return year, year
    return None, None


def _extract_top_n(question: str, default: int) -> tuple[str, int]:
    if match := re.search(r"\bbottom\s+(\d+)\b", question):
        return "bottom", int(match.group(1))
    if match := re.search(r"\btop\s+(\d+)\b", question):
        return "top", int(match.group(1))
    return "top", default


def _extract_phase(question: str) -> str | None:
    for alias, canonical in PHASE_ALIASES.items():
        if alias in question:
            return canonical
    return None


def _extract_result_context(question: str) -> str | None:
    if "losing cause" in question or "in losses" in question or "in defeat" in question:
        return "lost"
    if "in wins" in question or "winning cause" in question:
        return "won"
    return None


def _extract_stage_values(question: str) -> list[str] | None:
    for alias, values in STAGE_ALIASES.items():
        if _word_boundary_contains(question, alias):
            return values
    return None


def _extract_runs_threshold(question: str, default: int = 400) -> int:
    if match := re.search(r"\b(\d+)\s*\+\s*runs\b", question):
        return int(match.group(1))
    return default


def _extract_min_length(question: str, default: int = 1) -> int:
    if match := re.search(r"\b(\d+)\s+(?:straight|consecutive)\s+seasons\b", question):
        return int(match.group(1))
    if match := re.search(r"\b(\d+)\s+(?:straight|consecutive)\s+innings\b", question):
        return int(match.group(1))
    if match := re.search(r"\b(\d+)\s+(?:straight|consecutive)\s+matches\b", question):
        return int(match.group(1))
    return default


def _common_filters(question: str, default_limit: int = 15) -> ResolvedFilters:
    season_from, season_to = _extract_seasons(question)
    ranking_mode, top_n = _extract_top_n(question, default_limit)
    return ResolvedFilters(
        season_from=season_from,
        season_to=season_to,
        top_n=top_n,
        ranking_mode=ranking_mode,
        team=_extract_named_candidate(question, _teams()),
        venue=_extract_named_candidate(question, _venues()),
        player=_extract_named_candidate(question, _batters()),
        bowler=_extract_named_candidate(question, _bowlers()),
        phase=_extract_phase(question),
        result=_extract_result_context(question),
        stage_values=_extract_stage_values(question),
        reference_player=_extract_named_candidate(question, _batters()) if "who else" in question else None,
    )


def _filter_labels(filters: ResolvedFilters) -> list[str]:
    labels = []
    if filters.season_from and filters.season_to:
        if filters.season_from == filters.season_to:
            labels.append(f"Season = {filters.season_from}")
        else:
            labels.append(f"Season {filters.season_from}-{filters.season_to}")
    elif filters.season_from:
        labels.append(f"Season >= {filters.season_from}")
    if filters.team:
        labels.append(f"Team = {filters.team}")
    if filters.venue:
        labels.append(f"Venue = {filters.venue}")
    if filters.player:
        labels.append(f"Batter = {filters.player}")
    if filters.bowler:
        labels.append(f"Bowler = {filters.bowler}")
    if filters.phase:
        labels.append(f"Phase = {filters.phase.title()}")
    if filters.result:
        labels.append(f"Result = {filters.result}")
    if filters.stage_values:
        labels.append(
            "Stage = Playoffs" if len(filters.stage_values) > 1 else f"Stage = {filters.stage_values[0]}"
        )
    return labels


def _season_clause(filters: ResolvedFilters, column: str = "season") -> list[str]:
    clauses = []
    if filters.season_from and filters.season_to:
        clauses.append(f"{column} BETWEEN {filters.season_from} AND {filters.season_to}")
    elif filters.season_from:
        clauses.append(f"{column} >= {filters.season_from}")
    return clauses


def _apply_innings_tag_filters(filters: ResolvedFilters) -> list[str]:
    clauses = _season_clause(filters)
    if filters.team:
        clauses.append(f"batting_team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.player:
        clauses.append(f"batter = {_sql_quote(filters.player)}")
    if filters.result:
        clauses.append(f"result = {_sql_quote(filters.result)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    return clauses


def _apply_over_filters(filters: ResolvedFilters) -> list[str]:
    clauses = _season_clause(filters)
    if filters.team:
        clauses.append(
            "("
            f"batting_team = {_sql_quote(filters.team)} OR bowling_team = {_sql_quote(filters.team)}"
            ")"
        )
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.phase:
        clauses.append(f"match_phase = {_sql_quote(filters.phase)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    return clauses


def _apply_team_match_filters(filters: ResolvedFilters) -> list[str]:
    clauses = _season_clause(filters)
    if filters.team:
        clauses.append(f"team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    return clauses


def _apply_bowler_ball_filters(filters: ResolvedFilters) -> list[str]:
    clauses = _season_clause(filters)
    if filters.team:
        clauses.append(f"bowling_team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.bowler:
        clauses.append(f"bowler = {_sql_quote(filters.bowler)}")
    if filters.phase:
        clauses.append(f"match_phase = {_sql_quote(filters.phase)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    return clauses


def _sequence_phase_unsupported(question: str, filters: ResolvedFilters) -> SemanticPlan | None:
    if filters.phase:
        return _unsupported_plan(
            question,
            "Phase filters are not supported for cross-ball streak queries because clipping to a phase can break consecutive-ball semantics.",
        )
    return None


def _apply_batting_streak_ball_filters(filters: ResolvedFilters) -> list[str]:
    clauses = _season_clause(filters)
    if filters.team:
        clauses.append(f"batting_team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.player:
        clauses.append(f"batter = {_sql_quote(filters.player)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    return clauses


def _extract_dismissal_kind(question: str) -> str | None:
    dismissal_aliases = {
        "lbw": "lbw",
        "leg before wicket": "lbw",
        "bowled": "bowled",
        "caught": "caught",
        "stumped": "stumped",
        "run out": "run out",
        "hit wicket": "hit wicket",
    }
    for alias, kind in dismissal_aliases.items():
        if alias in question:
            return kind
    return None


def _season_overlap_condition(filters: ResolvedFilters, from_col: str, to_col: str) -> str:
    if filters.season_from and filters.season_to:
        return f"{to_col} >= {filters.season_from} AND {from_col} <= {filters.season_to}"
    if filters.season_from:
        return f"{to_col} >= {filters.season_from}"
    return "1=1"


def _mentions_four_fors(question: str) -> bool:
    return bool(
        re.search(r"\b4[- ]?for(?:s)?\b", question)
        or re.search(r"\bfour[- ]?for(?:s)?\b", question)
    )


def _build_simple_plan(
    question: str,
    intent_id: str,
    title: str,
    metric_label: str,
    grouping_label: str,
    sql: str,
    filters: ResolvedFilters,
    sample_constraints: list[str] | None = None,
    assumptions: list[str] | None = None,
    warnings: list[str] | None = None,
    chart_x: str = "",
    chart_y: str = "",
    chart_type: str = "bar",
) -> SemanticPlan:
    return SemanticPlan(
        question=question,
        supported=True,
        intent_id=intent_id,
        title=title,
        question_understood_as=title,
        metric_label=metric_label,
        grouping_label=grouping_label,
        active_filters=_filter_labels(filters),
        sample_constraints=sample_constraints or [],
        assumptions=assumptions or [],
        warnings=warnings or [],
        related_prompts=related_prompts(intent_id),
        chart_type=chart_type,
        chart_x=chart_x,
        chart_y=chart_y,
        sql_override=sql,
    )


def _unsupported_plan(question: str, reason: str) -> SemanticPlan:
    return SemanticPlan(
        question=question,
        supported=False,
        question_understood_as="Unsupported question",
        unsupported_reason=reason,
        warnings=[reason],
    )


def _most_near_miss_plan(question: str, filters: ResolvedFilters, score: int, label: str, intent_id: str) -> SemanticPlan:
    clauses = _apply_innings_tag_filters(filters)
    clauses.append(f"runs = {score}")
    where_sql = " AND ".join(clauses)
    sql = f"""
WITH scoped AS (
    SELECT *
    FROM innings_tags
    WHERE {where_sql}
)
SELECT batter AS Player,
       COUNT(*)::INT AS Innings,
       MIN(season)::INT AS "First Season",
       MAX(season)::INT AS "Last Season"
FROM scoped
GROUP BY batter
ORDER BY Innings DESC, Player
LIMIT {filters.top_n}
""".strip()
    understood = f"Batters with the most innings ending on {score}"
    return _build_simple_plan(
        question,
        intent_id,
        understood,
        "Innings Count",
        "Batter",
        sql,
        filters,
        chart_x="Player",
        chart_y="Innings",
    )


def _most_nineties_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _apply_innings_tag_filters(filters)
    clauses.append("runs BETWEEN 90 AND 99")
    where_sql = " AND ".join(clauses)
    sql = f"""
WITH scoped AS (
    SELECT *
    FROM innings_tags
    WHERE {where_sql}
)
SELECT batter AS Player,
       COUNT(*)::INT AS Innings,
       MAX(runs)::INT AS "Best Score"
FROM scoped
GROUP BY batter
ORDER BY Innings DESC, "Best Score" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-90s",
        "Batters with the most 90s without a hundred",
        "Innings Count",
        "Batter",
        sql,
        filters,
        chart_x="Player",
        chart_y="Innings",
    )


def _four_fors_without_five_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _season_clause(filters)
    if filters.team:
        clauses.append(f"bowling_team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
WITH scoped AS (
    SELECT *
    FROM player_bowling
    WHERE {where_sql}
)
SELECT bowler AS Player,
       SUM(CASE WHEN wickets >= 4 THEN 1 ELSE 0 END)::INT AS "Four-Fors",
       MAX(wickets)::INT AS "Best Figures"
FROM scoped
GROUP BY bowler
HAVING SUM(CASE WHEN wickets >= 4 THEN 1 ELSE 0 END) > 0
   AND SUM(CASE WHEN wickets >= 5 THEN 1 ELSE 0 END) = 0
ORDER BY "Four-Fors" DESC, "Best Figures" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "four-fors-no-five",
        "Bowlers with the most 4-fors but no 5-for",
        "Four-Fors",
        "Bowler",
        sql,
        filters,
        chart_x="Player",
        chart_y="Four-Fors",
    )


def _over_record_plan(question: str, filters: ResolvedFilters, intent_id: str, metric_column: str, title: str, sort_direction: str, y_field: str) -> SemanticPlan:
    clauses = _apply_over_filters(filters)
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    metric_select = f'{metric_column} AS "{y_field}"'
    deliveries_select = 'deliveries_total AS Deliveries,'
    if metric_column == "deliveries_total":
        metric_select = 'deliveries_total AS Deliveries'
        deliveries_select = ""
    sql = f"""
SELECT season AS Season,
       batting_team AS "Batting Team",
       bowling_team AS "Bowling Team",
       bowler AS Bowler,
       venue AS Venue,
       over AS Over,
       {deliveries_select}
       runs_total AS Runs,
       wides AS Wides,
       no_balls AS "No Balls",
       {metric_select}
FROM over_summary
WHERE {where_sql}
ORDER BY "{y_field}" {sort_direction}, Deliveries DESC, Season DESC
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        intent_id,
        title,
        y_field,
        "Over",
        sql,
        filters,
        chart_x="Over",
        chart_y=y_field,
    )


def _no_balls_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _apply_bowler_ball_filters(filters)
    clauses.append("extra_type = 'noballs'")
    where_sql = " AND ".join(clauses)
    sql = f"""
SELECT bowler AS Player,
       COUNT(*)::INT AS "No Balls",
       COUNT(DISTINCT match_id)::INT AS Matches
FROM balls
WHERE {where_sql}
GROUP BY bowler
ORDER BY "No Balls" DESC, Matches DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-no-balls",
        "Bowlers with the most no-balls",
        "No Balls",
        "Bowler",
        sql,
        filters,
        chart_x="Player",
        chart_y="No Balls",
    )


def _team_winning_streak_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = []
    if filters.team:
        clauses.append(f"team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    clauses.append("no_result = FALSE")
    where_sql = " AND ".join(clauses)
    overlap_sql = _season_overlap_condition(filters, '"From Season"', '"To Season"')
    sql = f"""
WITH base AS (
    SELECT team,
           season,
           date,
           match_id,
           won,
           ROW_NUMBER() OVER (PARTITION BY team ORDER BY date, match_id, innings) AS seq_all,
           ROW_NUMBER() OVER (PARTITION BY team, won ORDER BY date, match_id, innings) AS seq_state
    FROM team_match_results
    WHERE {where_sql}
),
streaks AS (
    SELECT team,
           COUNT(*)::INT AS "Streak Length",
           MIN(season)::INT AS "From Season",
           MAX(season)::INT AS "To Season"
    FROM base
    WHERE won = TRUE
    GROUP BY team, seq_all - seq_state
),
eligible AS (
    SELECT *
    FROM streaks
    WHERE {overlap_sql}
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY team
               ORDER BY "Streak Length" DESC, "To Season" DESC, "From Season" DESC
           ) AS streak_rank
    FROM eligible
)
SELECT team, "Streak Length", "From Season", "To Season"
FROM ranked
WHERE streak_rank = 1
ORDER BY "Streak Length" DESC, team
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "team-winning-streak",
        "Teams with the longest winning streaks",
        "Streak Length",
        "Team",
        sql,
        filters,
        sample_constraints=["No-result matches are excluded from streak boundaries."],
        assumptions=(
            ["Season filters are applied after streak detection, so full streaks that overlap the selected seasons are preserved."]
            if filters.season_from
            else None
        ),
        chart_x="team",
        chart_y="Streak Length",
    )


def _batting_streak_plan(question: str, filters: ResolvedFilters, intent_id: str, title: str, condition_sql: str, y_field: str) -> SemanticPlan:
    clauses = []
    if filters.team:
        clauses.append(f"batting_team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.player:
        clauses.append(f"batter = {_sql_quote(filters.player)}")
    if filters.result:
        clauses.append(f"result = {_sql_quote(filters.result)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    overlap_sql = _season_overlap_condition(filters, '"From Season"', '"To Season"')
    sql = f"""
WITH scoped AS (
    SELECT batter,
           season,
           date,
           match_id,
           innings,
           {condition_sql} AS qualifies
    FROM innings_tags
    WHERE {where_sql}
),
numbered AS (
    SELECT batter,
           season,
           date,
           match_id,
           innings,
           qualifies,
           ROW_NUMBER() OVER (PARTITION BY batter ORDER BY date, match_id, innings) AS seq_all,
           ROW_NUMBER() OVER (PARTITION BY batter, qualifies ORDER BY date, match_id, innings) AS seq_state
    FROM scoped
),
streaks AS (
    SELECT batter AS Player,
           COUNT(*)::INT AS "{y_field}",
           MIN(season)::INT AS "From Season",
           MAX(season)::INT AS "To Season"
    FROM numbered
    WHERE qualifies = TRUE
    GROUP BY batter, seq_all - seq_state
),
eligible AS (
    SELECT *
    FROM streaks
    WHERE {overlap_sql}
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY Player
               ORDER BY "{y_field}" DESC, "To Season" DESC, "From Season" DESC
           ) AS streak_rank
    FROM eligible
)
SELECT Player, "{y_field}", "From Season", "To Season"
FROM ranked
WHERE streak_rank = 1
ORDER BY "{y_field}" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        intent_id,
        title,
        y_field,
        "Batter",
        sql,
        filters,
        assumptions=(
            ["Season filters are applied after streak detection, so full streaks that overlap the selected seasons are preserved."]
            if filters.season_from
            else None
        ),
        chart_x="Player",
        chart_y=y_field,
    )


def _season_threshold_plan(question: str, filters: ResolvedFilters, consecutive: bool) -> SemanticPlan:
    threshold = _extract_runs_threshold(question, default=400)
    min_length = _extract_min_length(question, default=1)
    clauses = _season_clause(filters)
    if filters.team:
        clauses.append(f"team = {_sql_quote(filters.team)}")
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    if consecutive:
        sql = f"""
WITH qualified AS (
    SELECT player, season, runs
    FROM player_season_metrics
    WHERE {where_sql}
      AND runs >= {threshold}
),
numbered AS (
    SELECT player,
           season,
           season - ROW_NUMBER() OVER (PARTITION BY player ORDER BY season) AS grp
    FROM qualified
),
streaks AS (
    SELECT player AS Player,
           COUNT(*)::INT AS "Streak Length",
           MIN(season)::INT AS "From Season",
           MAX(season)::INT AS "To Season"
    FROM numbered
    GROUP BY player, grp
)
SELECT *
FROM streaks
WHERE "Streak Length" >= {min_length}
ORDER BY "Streak Length" DESC, Player
LIMIT {filters.top_n}
""".strip()
        title = f"Players with the most consecutive seasons of {threshold}+ runs"
        intent_id = "consecutive-seasons-runs-threshold"
        metric = "Streak Length"
    else:
        sql = f"""
WITH qualified AS (
    SELECT *
    FROM player_season_metrics
    WHERE {where_sql}
      AND runs >= {threshold}
)
SELECT player AS Player,
       COUNT(*)::INT AS "Qualified Seasons",
       MIN(season)::INT AS "First Season",
       MAX(season)::INT AS "Last Season"
FROM qualified
GROUP BY player
ORDER BY "Qualified Seasons" DESC, Player
LIMIT {filters.top_n}
""".strip()
        title = f"Players with the most seasons of {threshold}+ runs"
        intent_id = "seasons-with-runs-threshold"
        metric = "Qualified Seasons"

    assumptions = []
    if filters.reference_player:
        assumptions.append(
            f"Detected reference player {filters.reference_player}; returning the full leaderboard for the same threshold."
        )

    return _build_simple_plan(
        question,
        intent_id,
        title,
        metric,
        "Player",
        sql,
        filters,
        assumptions=assumptions,
        chart_x="Player",
        chart_y=metric,
    )


def _batting_leaderboard_plan(question: str, filters: ResolvedFilters, intent_id: str, title: str, metric_sql: str, metric_label: str, having_sql: str | None = None) -> SemanticPlan:
    clauses = _apply_innings_tag_filters(filters)
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    having_clause = f"\nHAVING {having_sql}" if having_sql else ""
    sql = f"""
SELECT batter AS Player,
       {metric_sql} AS "{metric_label}"
FROM innings_tags
WHERE {where_sql}
GROUP BY batter{having_clause}
ORDER BY "{metric_label}" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        intent_id,
        title,
        metric_label,
        "Batter",
        sql,
        filters,
        chart_x="Player",
        chart_y=metric_label,
    )


def _wickets_leaderboard_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _apply_bowler_ball_filters(filters)
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
SELECT bowler AS Player,
       SUM(bowler_wicket)::INT AS Wickets,
       ROUND(SUM(runs_bowler) * 6.0 / NULLIF(SUM(valid_ball), 0), 2) AS Economy
FROM balls
WHERE {where_sql}
GROUP BY bowler
HAVING SUM(bowler_wicket) > 0
ORDER BY Wickets DESC, Economy ASC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-wickets",
        "Bowlers with the most wickets",
        "Wickets",
        "Bowler",
        sql,
        filters,
        chart_x="Player",
        chart_y="Wickets",
    )


def _ducks_plan(question: str, filters: ResolvedFilters, golden: bool) -> SemanticPlan:
    clauses = _apply_innings_tag_filters(filters)
    clauses.append("is_duck = TRUE")
    if golden:
        clauses.append("balls = 1")
    where_sql = " AND ".join(clauses)
    metric_label = "Golden Ducks" if golden else "Ducks"
    intent_id = "most-golden-ducks" if golden else "most-ducks"
    title = "Batters with the most golden ducks" if golden else "Batters with the most ducks"
    sql = f"""
SELECT batter AS Player,
       COUNT(*)::INT AS "{metric_label}",
       MIN(season)::INT AS "First Season",
       MAX(season)::INT AS "Last Season"
FROM innings_tags
WHERE {where_sql}
GROUP BY batter
ORDER BY "{metric_label}" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        intent_id,
        title,
        metric_label,
        "Batter",
        sql,
        filters,
        chart_x="Player",
        chart_y=metric_label,
    )


def _most_balls_in_innings_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _apply_innings_tag_filters(filters)
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
SELECT batter AS Player,
       runs::INT AS Runs,
       balls::INT AS Balls,
       season AS Season,
       venue AS Venue
FROM innings_tags
WHERE {where_sql}
ORDER BY Balls DESC, Runs DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-balls-in-innings",
        "Batters who faced the most balls in a single innings",
        "Balls",
        "Innings",
        sql,
        filters,
        chart_x="Player",
        chart_y="Balls",
    )


def _most_extras_in_over_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _apply_over_filters(filters)
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
SELECT season AS Season,
       bowler AS Bowler,
       bowling_team AS Team,
       batting_team AS Opponent,
       venue AS Venue,
       over AS Over,
       extras::INT AS Extras,
       wides::INT AS Wides,
       no_balls::INT AS "No Balls",
       runs_total::INT AS Runs
FROM over_summary
WHERE {where_sql}
ORDER BY Extras DESC, Wides DESC, "No Balls" DESC, Season DESC
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-extras-over",
        "Overs with the most extras",
        "Extras",
        "Over",
        sql,
        filters,
        chart_x="Over",
        chart_y="Extras",
    )


def _most_sixes_in_over_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _apply_over_filters(filters)
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
SELECT season AS Season,
       bowler AS Bowler,
       batting_team AS Batting,
       venue AS Venue,
       over AS Over,
       sixes::INT AS Sixes,
       runs_total::INT AS Runs
FROM over_summary
WHERE {where_sql}
ORDER BY Sixes DESC, Runs DESC, Season DESC
LIMIT {filters.top_n}
""".strip()
    assumptions = []
    if "six sixes" in _normalize(question) or "6 sixes" in _normalize(question):
        assumptions.append("This query ranks overs by sixes hit. If no row reaches 6 sixes, the dataset does not contain a six-sixes over.")
    return _build_simple_plan(
        question,
        "most-sixes-over",
        "Overs with the most sixes",
        "Sixes",
        "Over",
        sql,
        filters,
        assumptions=assumptions,
        chart_x="Over",
        chart_y="Sixes",
    )


def _dismissal_type_plan(question: str, filters: ResolvedFilters, dismissal_kind: str, by_bowler: bool) -> SemanticPlan:
    if dismissal_kind == "run out" and by_bowler:
        return _unsupported_plan(question, "Run-outs are not credited to the bowler, so bowler leaderboards for run-outs would be inaccurate.")

    clauses = _season_clause(filters)
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.phase:
        clauses.append(f"match_phase = {_sql_quote(filters.phase)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    clauses.append(f"wicket_kind = {_sql_quote(dismissal_kind)}")

    if by_bowler:
        if filters.team:
            clauses.append(f"bowling_team = {_sql_quote(filters.team)}")
        if filters.bowler:
            clauses.append(f"bowler = {_sql_quote(filters.bowler)}")
        clauses.append("bowler_wicket = 1")
        select_col = "bowler"
        metric_label = dismissal_kind.upper() + "s" if dismissal_kind == "lbw" else dismissal_kind.title() + "s"
        title = f"Bowlers with the most {dismissal_kind} dismissals"
        intent_id = "bowler-dismissal-type"
        group_label = "Bowler"
    else:
        if filters.team:
            clauses.append(f"batting_team = {_sql_quote(filters.team)}")
        if filters.player:
            clauses.append(f"player_out = {_sql_quote(filters.player)}")
        select_col = "player_out"
        metric_label = dismissal_kind.title() + " Dismissals"
        if dismissal_kind == "lbw":
            metric_label = "LBW Dismissals"
        title = f"Batters dismissed by {dismissal_kind} most often"
        intent_id = "batter-dismissal-type"
        group_label = "Batter"

    where_sql = " AND ".join(clauses)
    sql = f"""
SELECT {select_col} AS Player,
       COUNT(*)::INT AS "{metric_label}"
FROM balls
WHERE {where_sql}
GROUP BY {select_col}
ORDER BY "{metric_label}" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        intent_id,
        title,
        metric_label,
        group_label,
        sql,
        filters,
        chart_x="Player",
        chart_y=metric_label,
    )


def _cap_history_plan(question: str, filters: ResolvedFilters, cap_type: str) -> SemanticPlan:
    metric_column = "runs" if cap_type == "orange" else "wickets"
    order_dir = "DESC"
    sql = f"""
WITH ranked AS (
    SELECT season,
           player,
           team,
           {metric_column},
           ROW_NUMBER() OVER (PARTITION BY season ORDER BY {metric_column} {order_dir}, player) AS rk
    FROM player_season_metrics
)
SELECT season AS Season,
       player AS Player,
       team AS Team,
       {metric_column} AS "{metric_column.title()}"
FROM ranked
WHERE rk = 1
ORDER BY Season
""".strip()
    intent_id = "orange-cap-history" if cap_type == "orange" else "purple-cap-history"
    title = "Orange Cap history" if cap_type == "orange" else "Purple Cap history"
    metric = metric_column.title()
    return _build_simple_plan(
        question,
        intent_id,
        title,
        metric,
        "Season",
        sql,
        filters,
        chart_x="Season",
        chart_y=metric,
        chart_type="line",
    )


def _chase_records_plan(question: str, filters: ResolvedFilters, chasing: bool) -> SemanticPlan:
    clauses = _apply_team_match_filters(filters)
    if chasing:
        clauses.append("successful_chase = TRUE")
        title = "Highest successful chases"
        metric_column = '"Target"'
        sql = f"""
SELECT team AS Team,
       opponent AS Opponent,
       CAST(target_to_win AS INT) AS "Target",
       CAST(runs_scored AS INT) AS Score,
       season AS Season,
       venue AS Venue
FROM team_match_results
WHERE {' AND '.join(clauses)}
ORDER BY "Target" DESC, Score DESC, Season DESC
LIMIT {filters.top_n}
""".strip()
        intent_id = "highest-successful-chase"
    else:
        clauses.append("successful_defense = TRUE")
        title = "Lowest totals defended"
        metric_column = '"Total Defended"'
        sql = f"""
SELECT team AS Team,
       opponent AS Opponent,
       CAST(runs_scored AS INT) AS "Total Defended",
       CAST(runs_conceded AS INT) AS "Opponent Score",
       season AS Season,
       venue AS Venue
FROM team_match_results
WHERE {' AND '.join(clauses)}
ORDER BY "Total Defended" ASC, Season DESC
LIMIT {filters.top_n}
""".strip()
        intent_id = "lowest-defended-total"

    return _build_simple_plan(
        question,
        intent_id,
        title,
        metric_column.replace('"', ""),
        "Match",
        sql,
        filters,
        chart_x="Team",
        chart_y=metric_column.replace('"', ""),
    )


def _hat_trick_counts_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    if unsupported := _sequence_phase_unsupported(question, filters):
        return unsupported

    clauses = _apply_bowler_ball_filters(filters)
    if filters.phase:
        clauses = [clause for clause in clauses if not clause.startswith("match_phase = ")]
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
WITH legal AS (
    SELECT match_id,
           season,
           innings,
           bowler,
           ROW_NUMBER() OVER (
               PARTITION BY match_id, innings, bowler
               ORDER BY over, legal_ball_number, delivery_number
           ) AS rn,
           bowler_wicket
    FROM balls
    WHERE valid_ball = TRUE
      AND {where_sql}
),
hat_tricks AS (
    SELECT match_id,
           season,
           innings,
           bowler
    FROM (
        SELECT *,
               COALESCE(LAG(bowler_wicket, 2) OVER (PARTITION BY match_id, innings, bowler ORDER BY rn), 0)
             + COALESCE(LAG(bowler_wicket, 1) OVER (PARTITION BY match_id, innings, bowler ORDER BY rn), 0)
             + bowler_wicket AS wicket3
        FROM legal
    ) s
    WHERE wicket3 = 3
)
SELECT bowler AS Player,
       COUNT(*)::INT AS "Hat-Tricks",
       MIN(season)::INT AS "First Season",
       MAX(season)::INT AS "Last Season"
FROM hat_tricks
GROUP BY bowler
ORDER BY "Hat-Tricks" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-hat-tricks",
        "Bowlers with the most hat-tricks",
        "Hat-Tricks",
        "Bowler",
        sql,
        filters,
        sample_constraints=["Only bowler wickets on legal balls count toward a hat-trick; run-outs are excluded."],
        chart_x="Player",
        chart_y="Hat-Tricks",
    )


def _all_hat_tricks_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    if unsupported := _sequence_phase_unsupported(question, filters):
        return unsupported

    clauses = _apply_bowler_ball_filters(filters)
    if filters.phase:
        clauses = [clause for clause in clauses if not clause.startswith("match_phase = ")]
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
WITH legal AS (
    SELECT match_id,
           season,
           innings,
           bowler,
           bowling_team,
           batting_team,
           over,
           player_out,
           ROW_NUMBER() OVER (
               PARTITION BY match_id, innings, bowler
               ORDER BY over, legal_ball_number, delivery_number
           ) AS rn,
           bowler_wicket
    FROM balls
    WHERE valid_ball = TRUE
      AND {where_sql}
),
hat_tricks AS (
    SELECT match_id,
           season,
           innings,
           bowler,
           bowling_team,
           batting_team,
           over,
           LAG(player_out, 2) OVER (PARTITION BY match_id, innings, bowler ORDER BY rn) AS wicket1_player,
           LAG(player_out, 1) OVER (PARTITION BY match_id, innings, bowler ORDER BY rn) AS wicket2_player,
           player_out AS wicket3_player,
           COALESCE(LAG(bowler_wicket, 2) OVER (PARTITION BY match_id, innings, bowler ORDER BY rn), 0)
         + COALESCE(LAG(bowler_wicket, 1) OVER (PARTITION BY match_id, innings, bowler ORDER BY rn), 0)
         + bowler_wicket AS wicket3
    FROM legal
)
SELECT ht.season AS Season,
       ht.bowler AS Bowler,
       ht.bowling_team AS Team,
       ht.batting_team AS Opponent,
       ht.over AS Over,
       ht.wicket1_player AS "1st Wicket",
       ht.wicket2_player AS "2nd Wicket",
       ht.wicket3_player AS "3rd Wicket",
       m.venue AS Venue
FROM hat_tricks ht
JOIN matches m ON ht.match_id = m.match_id
WHERE ht.wicket3 = 3
ORDER BY Season, Bowler
LIMIT 1000
""".strip()
    return _build_simple_plan(
        question,
        "all-hat-tricks",
        "All IPL hat-tricks",
        "Hat-Trick Event",
        "Match",
        sql,
        filters,
        sample_constraints=["Only bowler wickets on legal balls count toward a hat-trick; run-outs are excluded."],
        chart_x="Bowler",
        chart_y="Season",
    )


def _most_wickets_in_over_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _apply_over_filters(filters)
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
SELECT season AS Season,
       bowler AS Bowler,
       bowling_team AS Team,
       batting_team AS Opponent,
       venue AS Venue,
       over AS Over,
       wickets::INT AS Wickets,
       runs_total::INT AS Runs
FROM over_summary
WHERE {where_sql}
ORDER BY Wickets DESC, Season DESC, Bowler
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-wickets-in-over",
        "Overs with the most wickets",
        "Wickets",
        "Over",
        sql,
        filters,
        chart_x="Over",
        chart_y="Wickets",
    )


def _maidens_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _season_clause(filters)
    if filters.team:
        clauses.append(f"bowling_team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.bowler:
        clauses.append(f"bowler = {_sql_quote(filters.bowler)}")
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
SELECT bowler AS Player,
       SUM(maidens)::INT AS Maidens,
       COUNT(*)::INT AS Innings,
       SUM(wickets)::INT AS Wickets
FROM player_bowling
WHERE {where_sql}
GROUP BY bowler
HAVING SUM(maidens) > 0
ORDER BY Maidens DESC, Wickets DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-maidens",
        "Bowlers with the most maidens",
        "Maidens",
        "Bowler",
        sql,
        filters,
        chart_x="Player",
        chart_y="Maidens",
    )


def _wicket_maidens_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _apply_over_filters(filters)
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
SELECT bowler AS Player,
       COUNT(*)::INT AS "Wicket Maidens",
       SUM(wickets)::INT AS Wickets
FROM over_summary
WHERE {where_sql}
  AND legal_balls = 6
  AND runs_bowler = 0
  AND wickets > 0
GROUP BY bowler
ORDER BY "Wicket Maidens" DESC, Wickets DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-wicket-maidens",
        "Bowlers with the most wicket maidens",
        "Wicket Maidens",
        "Bowler",
        sql,
        filters,
        chart_x="Player",
        chart_y="Wicket Maidens",
    )


def _perfect_overs_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    clauses = _apply_over_filters(filters)
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
SELECT bowler AS Player,
       COUNT(*)::INT AS "Perfect Overs",
       SUM(wickets)::INT AS Wickets
FROM over_summary
WHERE {where_sql}
  AND is_maiden = TRUE
  AND legal_balls = 6
  AND dots = 6
  AND boundaries = 0
  AND extras = 0
GROUP BY bowler
ORDER BY "Perfect Overs" DESC, Wickets DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "most-perfect-overs",
        "Bowlers with the most perfect overs",
        "Perfect Overs",
        "Bowler",
        sql,
        filters,
        sample_constraints=["A perfect over is treated as 6 legal dot balls, 0 extras, and 0 runs conceded."],
        chart_x="Player",
        chart_y="Perfect Overs",
    )


def _wicket_streak_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    if unsupported := _sequence_phase_unsupported(question, filters):
        return unsupported

    clauses = []
    if filters.team:
        clauses.append(f"bowling_team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.bowler:
        clauses.append(f"bowler = {_sql_quote(filters.bowler)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    if filters.phase:
        clauses = [clause for clause in clauses if not clause.startswith("match_phase = ")]
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    overlap_sql = _season_overlap_condition(filters, '"From Season"', '"To Season"')
    sql = f"""
WITH legal AS (
    SELECT bowler,
           season,
           match_id,
           innings,
           ROW_NUMBER() OVER (
               PARTITION BY bowler
               ORDER BY season, match_id, innings, over, legal_ball_number, delivery_number
           ) AS rn_all,
           ROW_NUMBER() OVER (
               PARTITION BY bowler, bowler_wicket
               ORDER BY season, match_id, innings, over, legal_ball_number, delivery_number
           ) AS rn_state,
           bowler_wicket AS qualifies
    FROM balls
    WHERE valid_ball = TRUE
      AND {where_sql}
),
streaks AS (
    SELECT bowler AS Player,
           COUNT(*)::INT AS "Streak Length",
           MIN(season)::INT AS "From Season",
           MAX(season)::INT AS "To Season"
    FROM legal
    WHERE qualifies = 1
    GROUP BY bowler, rn_all - rn_state
),
eligible AS (
    SELECT *
    FROM streaks
    WHERE {overlap_sql}
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY Player
               ORDER BY "Streak Length" DESC, "To Season" DESC, "From Season" DESC
           ) AS streak_rank
    FROM eligible
)
SELECT Player, "Streak Length", "From Season", "To Season"
FROM ranked
WHERE streak_rank = 1
ORDER BY "Streak Length" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "wicket-streak",
        "Bowlers with the longest wicket streaks on consecutive legal balls",
        "Streak Length",
        "Bowler",
        sql,
        filters,
        sample_constraints=["Only bowler wickets on legal balls count toward the streak."],
        assumptions=(
            ["Season filters are applied after streak detection, so full streaks that overlap the selected seasons are preserved."]
            if filters.season_from
            else None
        ),
        chart_x="Player",
        chart_y="Streak Length",
    )


def _maiden_streak_plan(question: str, filters: ResolvedFilters) -> SemanticPlan:
    if unsupported := _sequence_phase_unsupported(question, filters):
        return unsupported

    clauses = []
    if filters.team:
        clauses.append(f"bowling_team = {_sql_quote(filters.team)}")
    if filters.venue:
        clauses.append(f"venue = {_sql_quote(filters.venue)}")
    if filters.bowler:
        clauses.append(f"bowler = {_sql_quote(filters.bowler)}")
    if filters.stage_values:
        clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    overlap_sql = _season_overlap_condition(filters, '"From Season"', '"To Season"')
    sql = f"""
WITH over_rows AS (
    SELECT bowler,
           season,
           match_id,
           innings,
           over,
           is_maiden,
           ROW_NUMBER() OVER (PARTITION BY bowler ORDER BY season, match_id, innings, over) AS rn_all,
           ROW_NUMBER() OVER (PARTITION BY bowler, is_maiden ORDER BY season, match_id, innings, over) AS rn_state
    FROM over_summary
    WHERE {where_sql}
),
streaks AS (
    SELECT bowler AS Player,
           COUNT(*)::INT AS "Streak Length",
           MIN(season)::INT AS "From Season",
           MAX(season)::INT AS "To Season"
    FROM over_rows
    WHERE is_maiden = TRUE
    GROUP BY bowler, rn_all - rn_state
),
eligible AS (
    SELECT *
    FROM streaks
    WHERE {overlap_sql}
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY Player
               ORDER BY "Streak Length" DESC, "To Season" DESC, "From Season" DESC
           ) AS streak_rank
    FROM eligible
)
SELECT Player, "Streak Length", "From Season", "To Season"
FROM ranked
WHERE streak_rank = 1
ORDER BY "Streak Length" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        "maiden-streak",
        "Bowlers with the longest consecutive maiden streaks",
        "Streak Length",
        "Bowler",
        sql,
        filters,
        assumptions=(
            ["Season filters are applied after streak detection, so full streaks that overlap the selected seasons are preserved."]
            if filters.season_from
            else None
        ),
        chart_x="Player",
        chart_y="Streak Length",
    )


def _ball_streak_plan(
    question: str,
    filters: ResolvedFilters,
    *,
    intent_id: str,
    title: str,
    entity_column: str,
    group_label: str,
    predicate_column: str,
    metric_label: str,
    batting_side: bool,
) -> SemanticPlan:
    if unsupported := _sequence_phase_unsupported(question, filters):
        return unsupported

    if batting_side:
        clauses = []
        if filters.team:
            clauses.append(f"batting_team = {_sql_quote(filters.team)}")
        if filters.venue:
            clauses.append(f"venue = {_sql_quote(filters.venue)}")
        if filters.player:
            clauses.append(f"batter = {_sql_quote(filters.player)}")
        if filters.stage_values:
            clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    else:
        clauses = []
        if filters.team:
            clauses.append(f"bowling_team = {_sql_quote(filters.team)}")
        if filters.venue:
            clauses.append(f"venue = {_sql_quote(filters.venue)}")
        if filters.bowler:
            clauses.append(f"bowler = {_sql_quote(filters.bowler)}")
        if filters.stage_values:
            clauses.append("stage IN (" + ", ".join(_sql_quote(stage) for stage in filters.stage_values) + ")")
    where_sql = " AND ".join(clauses) if clauses else "1=1"
    overlap_sql = _season_overlap_condition(filters, '"From Season"', '"To Season"')
    sql = f"""
WITH legal AS (
    SELECT {entity_column},
           season,
           match_id,
           innings,
           ROW_NUMBER() OVER (
               PARTITION BY {entity_column}
               ORDER BY season, match_id, innings, over, legal_ball_number, delivery_number
           ) AS rn_all,
           ROW_NUMBER() OVER (
               PARTITION BY {entity_column}, {predicate_column}
               ORDER BY season, match_id, innings, over, legal_ball_number, delivery_number
           ) AS rn_state,
           {predicate_column} AS qualifies
    FROM balls
    WHERE valid_ball = TRUE
      AND {where_sql}
),
streaks AS (
    SELECT {entity_column} AS Player,
           COUNT(*)::INT AS "{metric_label}",
           MIN(season)::INT AS "From Season",
           MAX(season)::INT AS "To Season"
    FROM legal
    WHERE qualifies = TRUE
    GROUP BY {entity_column}, rn_all - rn_state
),
eligible AS (
    SELECT *
    FROM streaks
    WHERE {overlap_sql}
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY Player
               ORDER BY "{metric_label}" DESC, "To Season" DESC, "From Season" DESC
           ) AS streak_rank
    FROM eligible
)
SELECT Player, "{metric_label}", "From Season", "To Season"
FROM ranked
WHERE streak_rank = 1
ORDER BY "{metric_label}" DESC, Player
LIMIT {filters.top_n}
""".strip()
    return _build_simple_plan(
        question,
        intent_id,
        title,
        metric_label,
        group_label,
        sql,
        filters,
        assumptions=(
            ["Season filters are applied after streak detection, so full streaks that overlap the selected seasons are preserved."]
            if filters.season_from
            else None
        ),
        chart_x="Player",
        chart_y=metric_label,
    )


def plan_query(question: str) -> SemanticPlan:
    """Plan a supported semantic question into a deterministic query plan."""
    normalized = _normalize(question)

    for keyword, reason in UNSUPPORTED_KEYWORDS.items():
        if keyword in normalized:
            return _unsupported_plan(question, reason)

    filters = _common_filters(normalized)
    dismissal_kind = _extract_dismissal_kind(normalized)

    if "49s" in normalized or "49 " in normalized:
        return _most_near_miss_plan(question, filters, 49, "49s", "most-49s")
    if "99s" in normalized or "99 " in normalized:
        return _most_near_miss_plan(question, filters, 99, "99s", "most-99s")
    if "90s" in normalized or "nineties" in normalized or "90 and 99" in normalized:
        return _most_nineties_plan(question, filters)
    if "golden ducks" in normalized or "golden duck" in normalized:
        return _ducks_plan(question, filters, golden=True)
    if "most ducks" in normalized or normalized.startswith("who has ducks") or "ducks in ipl" in normalized:
        return _ducks_plan(question, filters, golden=False)
    if "most balls in an innings" in normalized or "faced the most balls" in normalized or "longest innings by balls" in normalized:
        return _most_balls_in_innings_plan(question, filters)
    if _mentions_four_fors(normalized):
        return _four_fors_without_five_plan(question, filters)
    if (
        "all hat-tricks" in normalized
        or "all hat tricks" in normalized
        or "list hat-tricks" in normalized
        or "list hat tricks" in normalized
        or "show hat-tricks" in normalized
        or "show hat tricks" in normalized
    ):
        return _all_hat_tricks_plan(question, filters)
    if (
        "hat-trick" in normalized
        or "hat trick" in normalized
        or "hattrick" in normalized
        or "three consecutive wickets" in normalized
        or "3 consecutive wickets" in normalized
        or "three wickets in a row" in normalized
    ):
        return _hat_trick_counts_plan(question, filters)
    if "most wickets in an over" in normalized or "most wickets in over" in normalized or ("wickets" in normalized and "over" in normalized and "most" in normalized):
        return _most_wickets_in_over_plan(question, filters)
    if "wicket maiden" in normalized or "wicket maidens" in normalized:
        return _wicket_maidens_plan(question, filters)
    if "perfect over" in normalized or "perfect overs" in normalized:
        return _perfect_overs_plan(question, filters)
    if "wicket streak" in normalized or "consecutive wickets" in normalized or "wickets on consecutive balls" in normalized:
        return _wicket_streak_plan(question, filters)
    if "consecutive maiden" in normalized or "maiden streak" in normalized:
        return _maiden_streak_plan(question, filters)
    if "most maidens" in normalized or "most maiden overs" in normalized:
        return _maidens_plan(question, filters)
    if "dot-ball streak" in normalized or "dot ball streak" in normalized or "dots in a row" in normalized or "dot balls in a row" in normalized:
        if "bowler" in normalized or "bowlers" in normalized:
            return _ball_streak_plan(
                question,
                filters,
                intent_id="bowler-dot-streak",
                title="Bowlers with the longest dot-ball streaks",
                entity_column="bowler",
                group_label="Bowler",
                predicate_column="is_dot",
                metric_label="Streak Length",
                batting_side=False,
            )
        return _ball_streak_plan(
            question,
            filters,
            intent_id="batter-dot-streak",
            title="Batters with the longest dot-ball streaks",
            entity_column="batter",
            group_label="Batter",
            predicate_column="is_dot",
            metric_label="Streak Length",
            batting_side=True,
        )
    if "boundary streak" in normalized or "boundaries in a row" in normalized or "consecutive boundaries" in normalized:
        return _ball_streak_plan(
            question,
            filters,
            intent_id="boundary-streak",
            title="Batters with the longest boundary streaks",
            entity_column="batter",
            group_label="Batter",
            predicate_column="is_boundary",
            metric_label="Streak Length",
            batting_side=True,
        )
    if "scoring-shot streak" in normalized or "scoring shot streak" in normalized or "scoring shots in a row" in normalized or "longest scoring streak" in normalized:
        return _ball_streak_plan(
            question,
            filters,
            intent_id="scoring-streak",
            title="Batters with the longest scoring-shot streaks",
            entity_column="batter",
            group_label="Batter",
            predicate_column="NOT is_dot",
            metric_label="Streak Length",
            batting_side=True,
        )
    if "most extras" in normalized and "over" in normalized:
        return _most_extras_in_over_plan(question, filters)
    if ("most sixes" in normalized and "over" in normalized) or "six sixes" in normalized or "6 sixes" in normalized:
        return _most_sixes_in_over_plan(question, filters)
    if dismissal_kind and ("bowler" in normalized or "bowlers" in normalized):
        return _dismissal_type_plan(question, filters, dismissal_kind, by_bowler=True)
    if dismissal_kind and ("been" in normalized or "dismissed" in normalized or "batters" in normalized or "batter" in normalized or "player" in normalized or "players" in normalized or "who has" in normalized):
        return _dismissal_type_plan(question, filters, dismissal_kind, by_bowler=False)
    if "longest over" in normalized:
        return _over_record_plan(question, filters, "longest-over", "deliveries_total", "Longest overs", "DESC", "Deliveries")
    if "most expensive over" in normalized or "expensive overs" in normalized:
        return _over_record_plan(question, filters, "most-expensive-over", "runs_total", "Most expensive overs", "DESC", "Runs")
    if "most wides" in normalized and "over" in normalized:
        return _over_record_plan(question, filters, "most-wides-over", "wides", "Overs with the most wides", "DESC", "Wides")
    if "no-balls" in normalized or "no balls" in normalized:
        return _no_balls_plan(question, filters)
    if "winning streak" in normalized or "winning streaks" in normalized:
        return _team_winning_streak_plan(question, filters)
    if "20+ score" in normalized or "20+ scores" in normalized:
        return _batting_streak_plan(
            question,
            filters,
            "twenty-plus-streak",
            "Batters with the longest 20+ score streaks",
            "is_score_20_plus",
            "Streak Length",
        )
    if "no-duck streak" in normalized or "no duck streak" in normalized:
        return _batting_streak_plan(
            question,
            filters,
            "no-duck-streak",
            "Batters with the longest no-duck streaks",
            "NOT is_duck",
            "Streak Length",
        )
    if "consecutive seasons" in normalized and "runs" in normalized:
        return _season_threshold_plan(question, filters, consecutive=True)
    if "seasons with" in normalized and "runs" in normalized:
        return _season_threshold_plan(question, filters, consecutive=False)
    if "orange cap" in normalized:
        return _cap_history_plan(question, filters, cap_type="orange")
    if "purple cap" in normalized:
        return _cap_history_plan(question, filters, cap_type="purple")
    if "highest successful chase" in normalized or "highest successful chases" in normalized:
        return _chase_records_plan(question, filters, chasing=True)
    if "lowest defended total" in normalized or "lowest totals defended" in normalized:
        return _chase_records_plan(question, filters, chasing=False)
    if "most wickets" in normalized:
        return _wickets_leaderboard_plan(question, filters)
    if "most sixes" in normalized:
        return _batting_leaderboard_plan(question, filters, "most-sixes", "Batters with the most sixes", "SUM(sixes)::INT", "Sixes")
    if "most centuries" in normalized:
        return _batting_leaderboard_plan(
            question,
            filters,
            "most-centuries",
            "Batters with the most centuries",
            "SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END)::INT",
            "Centuries",
            having_sql="SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END) > 0",
        )
    if "most runs" in normalized:
        return _batting_leaderboard_plan(question, filters, "most-runs", "Batters with the most runs", "SUM(runs)::INT", "Runs")

    return _unsupported_plan(
        question,
        "This question is outside the currently supported semantic pack. Try one of the examples or rephrase using a supported stat family.",
    )
