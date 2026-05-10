"""Schema objects for per-visual controls."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ControlDefinition:
    id: str
    label: str
    type: str
    default: Any
    options: list[Any] | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    step: int | float | None = None
    help_text: str | None = None


@dataclass(frozen=True)
class VisualSpec:
    id: str
    title: str
    description: str = ""
    controls: list[ControlDefinition] = field(default_factory=list)
    empty_state_help: str = "No data found for the selected filters."
