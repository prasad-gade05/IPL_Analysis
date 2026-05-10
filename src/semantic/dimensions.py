"""Dimension metadata used by semantic explanations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DimensionDefinition:
    id: str
    label: str
    description: str


DIMENSIONS = {
    "batter": DimensionDefinition("batter", "Batter", "Groups results by batter."),
    "bowler": DimensionDefinition("bowler", "Bowler", "Groups results by bowler."),
    "team": DimensionDefinition("team", "Team", "Groups results by team."),
    "season": DimensionDefinition("season", "Season", "Groups results by season."),
    "over": DimensionDefinition("over", "Over", "Groups results by over."),
    "match": DimensionDefinition("match", "Match", "Returns match-level records."),
}
