"""Plotly theme and chart configuration for IPL Analytics."""

import plotly.graph_objects as go
import plotly.io as pio
from src.utils.constants import TEAM_COLORS, PHASE_COLORS

IPL_COLORWAY = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
    "#DDA0DD", "#98D8C8", "#F7DC6F", "#82E0AA", "#F0B27A",
]

IPL_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, sans-serif", color="#FAFAFA"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        colorway=IPL_COLORWAY,
        xaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.2)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.2)"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#1A1D23", font_color="#FAFAFA"),
    )
)

pio.templates["ipl"] = IPL_TEMPLATE
pio.templates.default = "ipl"


def get_team_color(team_name):
    """Return the hex color for a team, with fallback."""
    return TEAM_COLORS.get(team_name, "#888888")


def get_phase_color(phase_name):
    """Return the hex color for a match phase."""
    return PHASE_COLORS.get(phase_name, "#888888")


def apply_ipl_style(fig):
    """Apply consistent IPL styling to a plotly figure."""
    fig.update_layout(
        template="ipl",
        margin=dict(l=20, r=20, t=40, b=20),
        height=450,
    )
    return fig
