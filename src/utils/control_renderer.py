"""Streamlit rendering helpers for scoped visual controls."""

from __future__ import annotations

import streamlit as st

from src.utils.control_schema import ControlDefinition, VisualSpec


def _control_key(spec: VisualSpec, control: ControlDefinition) -> str:
    return f"{spec.id}.{control.id}"


def render_visual_controls(spec: VisualSpec) -> dict:
    """Render an expander of local controls and return their values."""
    values = {}
    if not spec.controls:
        return values

    with st.expander(f"Customize {spec.title}", expanded=False):
        for control in spec.controls:
            key = _control_key(spec, control)
            if control.type == "range":
                values[control.id] = st.slider(
                    control.label,
                    min_value=int(control.min_value),
                    max_value=int(control.max_value),
                    value=tuple(control.default),
                    step=int(control.step or 1),
                    key=key,
                    help=control.help_text,
                )
            elif control.type == "number":
                values[control.id] = int(
                    st.number_input(
                        control.label,
                        min_value=int(control.min_value),
                        max_value=int(control.max_value),
                        value=int(control.default),
                        step=int(control.step or 1),
                        key=key,
                        help=control.help_text,
                    )
                )
            elif control.type == "select":
                default_index = 0
                if control.options and control.default in control.options:
                    default_index = control.options.index(control.default)
                values[control.id] = st.selectbox(
                    control.label,
                    control.options or [],
                    index=default_index,
                    key=key,
                    help=control.help_text,
                )
            elif control.type == "toggle":
                values[control.id] = st.toggle(
                    control.label,
                    value=bool(control.default),
                    key=key,
                    help=control.help_text,
                )

    return values


def active_control_chips(spec: VisualSpec, values: dict) -> list[str]:
    """Return compact labels for controls that differ from defaults."""
    chips = []
    for control in spec.controls:
        value = values.get(control.id, control.default)
        if value == control.default:
            continue
        if control.type == "range":
            chips.append(f"{control.label}: {value[0]}-{value[1]}")
        elif control.type == "number":
            chips.append(f"{control.label}: {value}")
        elif control.type == "select":
            chips.append(f"{control.label}: {value}")
        elif control.type == "toggle":
            chips.append(control.label if value else f"{control.label}: Off")
    return chips
