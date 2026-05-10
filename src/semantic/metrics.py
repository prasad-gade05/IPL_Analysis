"""Metric metadata used by semantic explanations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    label: str
    description: str


METRICS = {
    "innings_count": MetricDefinition("innings_count", "Innings Count", "Counts innings matching the requested condition."),
    "runs": MetricDefinition("runs", "Runs", "Aggregates batter runs from tagged batting innings."),
    "wickets": MetricDefinition("wickets", "Wickets", "Aggregates real bowler wickets."),
    "sixes": MetricDefinition("sixes", "Sixes", "Aggregates sixes from tagged batting innings."),
    "centuries": MetricDefinition("centuries", "Centuries", "Counts innings with 100 or more runs."),
    "deliveries_total": MetricDefinition("deliveries_total", "Deliveries in Over", "Counts all deliveries in an over, including wides and no-balls."),
    "streak_length": MetricDefinition("streak_length", "Streak Length", "Counts the longest consecutive run of qualifying rows."),
    "season_count": MetricDefinition("season_count", "Qualified Seasons", "Counts seasons that meet the requested threshold."),
    "target": MetricDefinition("target", "Target", "Uses the stored chase target when available."),
}
