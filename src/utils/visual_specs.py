"""Reusable control factories for configurable visual cards."""

from src.utils.constants import ALL_SEASONS
from src.utils.control_schema import ControlDefinition


def season_range_control(default: tuple[int, int] | None = None) -> ControlDefinition:
    start, end = default or (min(ALL_SEASONS), max(ALL_SEASONS))
    return ControlDefinition(
        id="season_range",
        label="Season range",
        type="range",
        default=(start, end),
        min_value=min(ALL_SEASONS),
        max_value=max(ALL_SEASONS),
        step=1,
    )


def limit_control(default: int = 15, minimum: int = 5, maximum: int = 50) -> ControlDefinition:
    return ControlDefinition(
        id="limit",
        label="Rows to show",
        type="number",
        default=default,
        min_value=minimum,
        max_value=maximum,
        step=1,
    )


def number_control(
    control_id: str,
    label: str,
    default: int,
    minimum: int,
    maximum: int,
    step: int = 1,
    help_text: str | None = None,
) -> ControlDefinition:
    return ControlDefinition(
        id=control_id,
        label=label,
        type="number",
        default=default,
        min_value=minimum,
        max_value=maximum,
        step=step,
        help_text=help_text,
    )


def select_control(control_id: str, label: str, options: list[str], default: str, help_text: str | None = None) -> ControlDefinition:
    return ControlDefinition(
        id=control_id,
        label=label,
        type="select",
        default=default,
        options=options,
        help_text=help_text,
    )


def toggle_control(control_id: str, label: str, default: bool = False, help_text: str | None = None) -> ControlDefinition:
    return ControlDefinition(
        id=control_id,
        label=label,
        type="toggle",
        default=default,
        help_text=help_text,
    )
