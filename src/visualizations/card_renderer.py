"""Helpers for rendering configurable result cards."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.visualizations.theme import apply_ipl_style


def render_active_filters(chips: list[str]) -> None:
    """Render active filter chips for a visual."""
    if chips:
        st.caption("Active filters: " + " · ".join(f"`{chip}`" for chip in chips))


def render_dataframe(df, empty_state_help: str, **dataframe_kwargs) -> None:
    """Render a dataframe with a standard empty state."""
    if df.empty:
        st.info(empty_state_help)
    else:
        kwargs = {"width": "stretch", "hide_index": True}
        kwargs.update(dataframe_kwargs)
        st.dataframe(df, **kwargs)


def render_bar_chart(df, x: str, y: str, title: str, horizontal: bool = True, height: int = 420) -> None:
    """Render a simple bar chart when the required columns are present."""
    if df.empty or x not in df.columns or y not in df.columns:
        return

    chart_df = df.copy()
    if horizontal:
        chart_df = chart_df.sort_values(y, ascending=True)
        fig = px.bar(chart_df, x=y, y=x, orientation="h", title=title)
    else:
        fig = px.bar(chart_df, x=x, y=y, title=title)
    fig = apply_ipl_style(fig, height=height, show_legend=False)
    st.plotly_chart(fig, width="stretch")
