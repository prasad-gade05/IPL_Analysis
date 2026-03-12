"""
Tournament Structure — How each IPL season was structured.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style, styled_bar, styled_line,
    get_team_color, big_number_style, IPL_COLORWAY,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS
from src.utils.formatters import format_number

st.markdown(big_number_style(), unsafe_allow_html=True)
st.title("Tournament Structure")
st.caption("How each IPL season was structured — formats, standings, playoffs & fixtures.")

# ──────────────────────────────────────────────
# Cached query helpers
# ──────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _season_meta_all() -> pd.DataFrame:
    return query("SELECT * FROM season_meta ORDER BY season")


@st.cache_data(ttl=3600)
def _season_meta(season: int) -> pd.DataFrame:
    return query("SELECT * FROM season_meta WHERE season = ?", [season])


@st.cache_data(ttl=3600)
def _points_table(season: int) -> pd.DataFrame:
    return query("""
        SELECT position, team, played, won, lost, nr, points, nrr
        FROM points_table
        WHERE season = ?
        ORDER BY position
    """, [season])


@st.cache_data(ttl=3600)
def _playoff_matches(season: int) -> pd.DataFrame:
    return query("""
        SELECT stage, team1, team2,
               team1_score, team1_wickets,
               team2_score, team2_wickets,
               match_won_by, player_of_match
        FROM matches
        WHERE season = ?
          AND stage IN ('Qualifier 1', 'Qualifier 2', 'Eliminator', 'Final')
        ORDER BY date
    """, [season])


@st.cache_data(ttl=3600)
def _season_comparison() -> pd.DataFrame:
    return query("""
        WITH top_batters AS (
            SELECT season, batter AS player, SUM(runs) AS runs
            FROM player_batting
            GROUP BY season, batter
            QUALIFY ROW_NUMBER() OVER (PARTITION BY season ORDER BY SUM(runs) DESC) = 1
        ),
        top_bowlers AS (
            SELECT season, bowler AS player, SUM(wickets) AS wickets
            FROM player_bowling
            GROUP BY season, bowler
            QUALIFY ROW_NUMBER() OVER (PARTITION BY season ORDER BY SUM(wickets) DESC) = 1
        ),
        highest AS (
            SELECT season, MAX(team1_score) AS max1, MAX(team2_score) AS max2
            FROM matches
            GROUP BY season
        )
        SELECT sm.season,
               sm.total_matches,
               sm.num_teams,
               sm.champion,
               tb.player  AS top_scorer,
               tb.runs    AS top_scorer_runs,
               tw.player  AS top_wicket_taker,
               tw.wickets AS top_wicket_taker_wickets,
               GREATEST(h.max1, h.max2) AS highest_score,
               sm.duration_days
        FROM season_meta sm
        LEFT JOIN top_batters  tb ON sm.season = tb.season
        LEFT JOIN top_bowlers  tw ON sm.season = tw.season
        LEFT JOIN highest       h ON sm.season = h.season
        ORDER BY sm.season
    """)


@st.cache_data(ttl=3600)
def _venue_season_matrix() -> pd.DataFrame:
    return query("""
        SELECT venue, season, COUNT(*) AS match_count
        FROM matches
        GROUP BY venue, season
        ORDER BY venue, season
    """)


@st.cache_data(ttl=3600)
def _competitiveness_index() -> pd.DataFrame:
    return query("""
        SELECT season,
               STDDEV(win_pct) AS win_pct_std
        FROM team_season
        GROUP BY season
        ORDER BY season
    """)


@st.cache_data(ttl=3600)
def _venue_distribution(season: int) -> pd.DataFrame:
    return query("""
        SELECT venue, COUNT(*) AS matches
        FROM matches
        WHERE season = ?
        GROUP BY venue
        ORDER BY matches DESC
    """, [season])


@st.cache_data(ttl=3600)
def _team_venue_matrix(season: int) -> pd.DataFrame:
    return query("""
        WITH team_matches AS (
            SELECT venue, team1 AS team FROM matches WHERE season = ?
            UNION ALL
            SELECT venue, team2 AS team FROM matches WHERE season = ?
        )
        SELECT team, venue, COUNT(*) AS matches
        FROM team_matches
        GROUP BY team, venue
        ORDER BY team, venue
    """, [season, season])


# ──────────────────────────────────────────────
# Season Selector
# ──────────────────────────────────────────────

meta_all = _season_meta_all()
available_seasons = sorted(meta_all["season"].tolist(), reverse=True)

if not available_seasons:
    st.error("No season data available.")
    st.stop()

default_idx = 0
if 2025 in available_seasons:
    default_idx = available_seasons.index(2025)

selected_season = st.selectbox(
    "Select Season",
    options=available_seasons,
    index=default_idx,
    key="ts_season",
)

meta = _season_meta(selected_season)
if meta.empty:
    st.warning(f"No metadata found for season {selected_season}.")
    st.stop()

m = meta.iloc[0]

# ══════════════════════════════════════════════
# TOURNAMENT OVERVIEW
# ══════════════════════════════════════════════

st.divider()
st.markdown("## Tournament Overview")

# Season identity card
st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, rgba(28,31,42,0.8), rgba(44,47,60,0.8));
                border: 1px solid rgba(255,255,255,0.12); border-radius: 12px;
                padding: 20px 28px; margin-bottom: 16px;">
        <h2 style="margin:0 0 8px 0;">IPL {int(m['season'])}</h2>
        <p style="margin:4px 0; font-size:1.05rem;">
            <b>{m['start_date']}</b> → <b>{m['end_date']}</b>
            &nbsp;|&nbsp; <b>{int(m['duration_days'])} days</b>
            &nbsp;|&nbsp; <b>{int(m['num_teams'])} teams</b>
            &nbsp;|&nbsp; <b>{int(m['total_matches'])} matches</b>
        </p>
        <p style="margin:4px 0; font-size:1.15rem;">
            Champion: <b style="color: {get_team_color(str(m['champion']))}">{m['champion']}</b>
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# 6 metric cards
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Matches", format_number(m["total_matches"]))
c2.metric("Teams", format_number(m["num_teams"]))
c3.metric("Venues", format_number(m["num_venues"]))
c4.metric("Duration", f"{int(m['duration_days'])} days")
c5.metric("Super Overs", format_number(m["has_super_over"]))
c6.metric("DLS Matches", format_number(m["dls_matches"]))

# Timeline: matches per season with teams overlay
st.subheader("Season Timeline — Matches & Teams")

fig_timeline = go.Figure()

colors = [
    IPL_COLORWAY[0] if s != selected_season else "#FFD700"
    for s in meta_all["season"]
]

fig_timeline.add_trace(go.Bar(
    x=meta_all["season"],
    y=meta_all["total_matches"],
    name="Matches",
    marker_color=colors,
    text=meta_all["total_matches"],
    textposition="outside",
    yaxis="y",
))

fig_timeline.add_trace(go.Scatter(
    x=meta_all["season"],
    y=meta_all["num_teams"],
    name="Teams",
    mode="lines+markers",
    marker=dict(size=8, color=IPL_COLORWAY[1]),
    line=dict(width=2, color=IPL_COLORWAY[1]),
    yaxis="y2",
))

fig_timeline.update_layout(
    yaxis=dict(title="Matches", side="left"),
    yaxis2=dict(title="Teams", overlaying="y", side="right",
                range=[0, meta_all["num_teams"].max() + 4]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=dict(dtick=1),
)
apply_ipl_style(fig_timeline, height=420)
st.plotly_chart(fig_timeline, width='stretch')


# ══════════════════════════════════════════════
# POINTS TABLE
# ══════════════════════════════════════════════

st.divider()
st.markdown("## Points Table")

pts = _points_table(selected_season)

if pts.empty:
    st.info(f"No points table data available for {selected_season}.")
else:
    pts_display = pts.rename(columns={
        "position": "Pos", "team": "Team", "played": "P",
        "won": "W", "lost": "L", "nr": "NR",
        "points": "Pts", "nrr": "NRR",
    })

    def _highlight_qualifiers(row):
        if row["Pos"] <= 4:
            return ["background-color: rgba(76, 175, 80, 0.18)"] * len(row)
        return [""] * len(row)

    styled_pts = pts_display.style.apply(_highlight_qualifiers, axis=1).format(
        {"NRR": "{:+.3f}", "Pos": "{:.0f}", "P": "{:.0f}",
         "W": "{:.0f}", "L": "{:.0f}", "NR": "{:.0f}", "Pts": "{:.0f}"}
    )
    st.dataframe(styled_pts, width='stretch', hide_index=True, height=420)

    # NRR horizontal bar chart
    st.subheader("Net Run Rate")

    nrr_colors = [
        "#4CAF50" if v >= 0 else "#EF5350"
        for v in pts["nrr"]
    ]

    fig_nrr = go.Figure(go.Bar(
        y=pts["team"],
        x=pts["nrr"],
        orientation="h",
        marker_color=nrr_colors,
        text=pts["nrr"].apply(lambda v: f"{v:+.3f}"),
        textposition="outside",
    ))
    fig_nrr.update_layout(
        yaxis=dict(autorange="reversed"),
        xaxis=dict(title="Net Run Rate", zeroline=True,
                   zerolinecolor="rgba(255,255,255,0.3)", zerolinewidth=1),
    )
    apply_ipl_style(fig_nrr, height=max(350, len(pts) * 38), show_legend=False)
    st.plotly_chart(fig_nrr, width='stretch')


# ══════════════════════════════════════════════
# PLAYOFF BRACKET
# ══════════════════════════════════════════════

st.divider()
st.markdown("## Playoff Bracket")

playoffs = _playoff_matches(selected_season)

if playoffs.empty:
    st.info(f"No playoff data available for {selected_season}.")
else:
    def _format_match_card(row):
        t1, t2 = row["team1"], row["team2"]
        s1 = f"{int(row['team1_score'])}/{int(row['team1_wickets'])}" if pd.notna(row["team1_score"]) else "N/A"
        s2 = f"{int(row['team2_score'])}/{int(row['team2_wickets'])}" if pd.notna(row["team2_score"]) else "N/A"
        winner = row["match_won_by"] if pd.notna(row["match_won_by"]) else "N/A"
        winner_color = get_team_color(winner)
        stage = row["stage"]

        is_final = stage == "Final"
        icon = "" if is_final else ""
        extra = " — Champion!" if is_final else ""

        return f"""
        <div style="background: linear-gradient(135deg, rgba(28,31,42,0.7), rgba(44,47,60,0.7));
                    border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
                    padding: 14px 20px; margin-bottom: 10px;">
            <h4 style="margin:0 0 6px 0;">{icon} {stage}</h4>
            <p style="margin:2px 0; font-size:1.05rem;">
                <b style="color:{get_team_color(t1)}">{t1}</b> ({s1})
                &nbsp; vs &nbsp;
                <b style="color:{get_team_color(t2)}">{t2}</b> ({s2})
            </p>
            <p style="margin:2px 0; font-size:1rem;">
                Winner: <b style="color:{winner_color}">{winner}</b>{extra}
            </p>
        </div>
        """

    stage_order = ["Qualifier 1", "Eliminator", "Qualifier 2", "Final"]
    rendered_stages = set()

    # Try to render in canonical order
    for stage in stage_order:
        stage_rows = playoffs[playoffs["stage"] == stage]
        if not stage_rows.empty:
            row = stage_rows.iloc[0]
            st.markdown(_format_match_card(row), unsafe_allow_html=True)
            rendered_stages.add(stage)

    # Render any remaining stages not in canonical order
    remaining = playoffs[~playoffs["stage"].isin(rendered_stages)]
    for _, row in remaining.iterrows():
        st.markdown(_format_match_card(row), unsafe_allow_html=True)

    # If partial data, also show as table
    if len(playoffs) < 3:
        st.caption("Partial playoff data — showing available results as table.")
        po_display = playoffs[["stage", "team1", "team2", "team1_score", "team1_wickets",
                               "team2_score", "team2_wickets", "match_won_by"]].copy()
        po_display.columns = ["Stage", "Team 1", "Team 2", "T1 Score", "T1 Wkts",
                               "T2 Score", "T2 Wkts", "Winner"]
        st.dataframe(po_display, width='stretch', hide_index=True)


# ══════════════════════════════════════════════
# SEASON COMPARISON
# ══════════════════════════════════════════════

st.divider()
st.markdown("## Season Comparison")

comp = _season_comparison()

if comp.empty:
    st.info("No comparison data available.")
else:
    # Multi-season comparison table
    comp_display = comp.copy()
    comp_display["Top Scorer"] = comp_display.apply(
        lambda r: f"{r['top_scorer']} ({int(r['top_scorer_runs'])})"
        if pd.notna(r["top_scorer"]) else "N/A", axis=1
    )
    comp_display["Top Wicket-Taker"] = comp_display.apply(
        lambda r: f"{r['top_wicket_taker']} ({int(r['top_wicket_taker_wickets'])})"
        if pd.notna(r["top_wicket_taker"]) else "N/A", axis=1
    )

    table_df = comp_display[["season", "total_matches", "num_teams", "champion",
                              "Top Scorer", "Top Wicket-Taker",
                              "highest_score", "duration_days"]].rename(columns={
        "season": "Season", "total_matches": "Matches", "num_teams": "Teams",
        "champion": "Champion", "highest_score": "Highest Score",
        "duration_days": "Duration (days)",
    })

    def _highlight_selected(row):
        if row["Season"] == selected_season:
            return ["background-color: rgba(255, 215, 0, 0.15)"] * len(row)
        return [""] * len(row)

    styled_comp = table_df.style.apply(_highlight_selected, axis=1)
    st.dataframe(styled_comp, width='stretch', hide_index=True, height=450)

    # Two charts side by side
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Season Duration Trend")
        fig_dur = styled_line(
            meta_all, x="season", y="duration_days",
            title="Duration (days) per Season", height=400,
        )
        st.plotly_chart(fig_dur, width='stretch')

    with col_b:
        st.subheader("Competitiveness Index")
        ci = _competitiveness_index()
        if not ci.empty:
            ci["win_pct_std"] = ci["win_pct_std"].round(2)
            fig_ci = styled_line(
                ci, x="season", y="win_pct_std",
                title="Std Dev of Win% (lower = more competitive)", height=400,
            )
            st.plotly_chart(fig_ci, width='stretch')
        else:
            st.info("Not enough data for competitiveness index.")

    # Venue distribution heatmap
    st.subheader("Venue × Season Heatmap")
    vsm = _venue_season_matrix()
    if not vsm.empty:
        pivot = vsm.pivot_table(
            index="venue", columns="season", values="match_count",
            aggfunc="sum", fill_value=0,
        )
        # Only show venues that hosted ≥5 total matches to keep it readable
        pivot = pivot[pivot.sum(axis=1) >= 5]
        pivot = pivot.sort_values(by=pivot.columns.tolist(), ascending=False)

        fig_hm = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[str(c) for c in pivot.columns],
            y=pivot.index.tolist(),
            colorscale="YlOrRd",
            text=pivot.values,
            texttemplate="%{text}",
            hovertemplate="Venue: %{y}<br>Season: %{x}<br>Matches: %{z}<extra></extra>",
        ))
        fig_hm.update_layout(
            xaxis=dict(title="Season", dtick=1),
            yaxis=dict(title="", autorange="reversed"),
        )
        apply_ipl_style(fig_hm, height=max(500, len(pivot) * 24), show_legend=False)
        st.plotly_chart(fig_hm, width='stretch')
    else:
        st.info("No venue data available for heatmap.")


# ══════════════════════════════════════════════
# FIXTURE ANALYSIS
# ══════════════════════════════════════════════

st.divider()
st.markdown("## Fixture Analysis")

# Venue match distribution for selected season
venue_dist = _venue_distribution(selected_season)

if venue_dist.empty:
    st.info(f"No fixture data for {selected_season}.")
else:
    st.subheader(f"Venue Match Distribution — {selected_season}")
    fig_vd = styled_bar(
        venue_dist, x="venue", y="matches",
        title=f"Matches per Venue in {selected_season}",
        height=420,
    )
    fig_vd.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_vd, width='stretch')

    # Team × Venue matrix (home-away approximation)
    st.subheader(f"Team × Venue Matrix — {selected_season}")
    tvm = _team_venue_matrix(selected_season)

    if not tvm.empty:
        pivot_tv = tvm.pivot_table(
            index="team", columns="venue", values="matches",
            aggfunc="sum", fill_value=0,
        )

        fig_tv = go.Figure(data=go.Heatmap(
            z=pivot_tv.values,
            x=pivot_tv.columns.tolist(),
            y=pivot_tv.index.tolist(),
            colorscale="Blues",
            text=pivot_tv.values,
            texttemplate="%{text}",
            hovertemplate="Team: %{y}<br>Venue: %{x}<br>Matches: %{z}<extra></extra>",
        ))
        fig_tv.update_layout(
            xaxis=dict(title="Venue", tickangle=-45),
            yaxis=dict(title="", autorange="reversed"),
        )
        apply_ipl_style(
            fig_tv,
            height=max(450, len(pivot_tv) * 36),
            show_legend=False,
        )
        st.plotly_chart(fig_tv, width='stretch')
    else:
        st.info("No team-venue data available.")
