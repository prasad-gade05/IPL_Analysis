"""Plotly theme and chart configuration for IPL Analytics."""

import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from src.utils.constants import TEAM_COLORS, PHASE_COLORS

IPL_COLORWAY = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
    "#DDA0DD", "#98D8C8", "#F7DC6F", "#82E0AA", "#F0B27A",
    "#AED6F1", "#F5B7B1", "#D7BDE2", "#A9DFBF", "#FAD7A0",
]

IPL_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, sans-serif", color="#FAFAFA", size=12),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        colorway=IPL_COLORWAY,
        xaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.2)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.2)"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        hoverlabel=dict(bgcolor="#1A1D23", font_color="#FAFAFA", font_size=12),
        title=dict(font=dict(size=16)),
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


def get_team_colors_list(teams):
    """Return list of colors for a list of team names."""
    return [get_team_color(t) for t in teams]


def apply_ipl_style(fig, height=450, show_legend=True):
    """Apply consistent IPL styling to a plotly figure."""
    fig.update_layout(
        template="ipl",
        margin=dict(l=20, r=20, t=50, b=20),
        height=height,
        showlegend=show_legend,
    )
    return fig


def styled_bar(df, x, y, title="", color=None, color_map=None,
               horizontal=False, text_auto=True, height=450):
    """Create a styled bar chart."""
    kwargs = dict(title=title, text_auto=text_auto)
    if color and color_map:
        kwargs["color"] = color
        kwargs["color_discrete_map"] = color_map
    elif color:
        kwargs["color"] = color

    if horizontal:
        fig = px.bar(df, x=y, y=x, orientation="h", **kwargs)
    else:
        fig = px.bar(df, x=x, y=y, **kwargs)

    return apply_ipl_style(fig, height=height)


def styled_line(df, x, y, title="", color=None, markers=True, height=450):
    """Create a styled line chart."""
    fig = px.line(df, x=x, y=y, title=title, color=color, markers=markers)
    return apply_ipl_style(fig, height=height)


def styled_scatter(df, x, y, title="", color=None, size=None,
                   hover_name=None, text=None, height=450):
    """Create a styled scatter plot."""
    fig = px.scatter(df, x=x, y=y, title=title, color=color, size=size,
                     hover_name=hover_name, text=text)
    return apply_ipl_style(fig, height=height)


def styled_pie(df, names, values, title="", hole=0.4, height=400):
    """Create a styled donut/pie chart."""
    fig = px.pie(df, names=names, values=values, title=title, hole=hole)
    fig.update_traces(textinfo="percent+label", textfont_size=11)
    return apply_ipl_style(fig, height=height, show_legend=False)


def styled_heatmap(df, x, y, z, title="", height=500):
    """Create a styled heatmap."""
    fig = px.density_heatmap(df, x=x, y=y, z=z, title=title,
                              color_continuous_scale="YlOrRd")
    return apply_ipl_style(fig, height=height)


def metric_card(label, value, delta=None, help_text=None):
    """Return kwargs dict for st.metric (convenience wrapper)."""
    return dict(label=label, value=value, delta=delta, help=help_text)


def big_number_style():
    """Return CSS for styled metric cards."""
    return """
    <style>
    [data-testid="stMetric"] {
        background-color: rgba(28, 31, 42, 0.6);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem; }
    </style>
    """
