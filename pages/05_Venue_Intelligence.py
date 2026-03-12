"""
Venue Intelligence — Ground-specific insights.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style,
    styled_bar,
    styled_line,
    styled_scatter,
    styled_pie,
    get_team_color,
    big_number_style,
    IPL_COLORWAY,
    metric_card,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS
from src.utils.formatters import format_number, format_strike_rate, format_average

# ---------------------------------------------------------------------------
# Cached query helpers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600)
def get_all_venues():
    return query("SELECT * FROM venues ORDER BY total_matches DESC")


@st.cache_data(ttl=3600)
def get_venue_list():
    return query("SELECT DISTINCT venue FROM venues ORDER BY venue")["venue"].tolist()


@st.cache_data(ttl=3600)
def get_venue_season_usage():
    return query(
        """
        SELECT venue, season, COUNT(*) AS match_count
        FROM matches
        GROUP BY venue, season
        ORDER BY venue, season
        """
    )


@st.cache_data(ttl=3600)
def get_venue_seasons(venue):
    return query(
        "SELECT DISTINCT season FROM matches WHERE venue = ? ORDER BY season",
        [venue],
    )["season"].tolist()


@st.cache_data(ttl=3600)
def get_innings_scores(venue):
    return query(
        """
        SELECT match_id,
               team1_score  AS first_innings_score,
               team2_score  AS second_innings_score
        FROM matches
        WHERE venue = ?
          AND team1_score IS NOT NULL
          AND team2_score IS NOT NULL
        """,
        [venue],
    )


@st.cache_data(ttl=3600)
def get_avg_score_trend(venue):
    return query(
        """
        SELECT season,
               ROUND(AVG(team1_score), 1) AS avg_1st,
               ROUND(AVG(team2_score), 1) AS avg_2nd,
               ROUND((AVG(team1_score) + AVG(team2_score)) / 2.0, 1) AS avg_score
        FROM matches
        WHERE venue = ?
          AND team1_score IS NOT NULL
          AND team2_score IS NOT NULL
        GROUP BY season
        ORDER BY season
        """,
        [venue],
    )


@st.cache_data(ttl=3600)
def get_run_rate_by_phase(venue):
    return query(
        """
        SELECT match_phase,
               ROUND(
                   SUM(runs_batter) * 6.0
                   / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0),
               2) AS run_rate
        FROM balls
        WHERE venue = ? AND match_phase IS NOT NULL
        GROUP BY match_phase
        ORDER BY CASE match_phase
                     WHEN 'powerplay' THEN 1
                     WHEN 'middle'    THEN 2
                     WHEN 'death'     THEN 3
                 END
        """,
        [venue],
    )


@st.cache_data(ttl=3600)
def get_league_avg_run_rate():
    return query(
        """
        SELECT match_phase,
               ROUND(
                   SUM(runs_batter) * 6.0
                   / NULLIF(SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END), 0),
               2) AS run_rate
        FROM balls
        WHERE match_phase IS NOT NULL
        GROUP BY match_phase
        ORDER BY CASE match_phase
                     WHEN 'powerplay' THEN 1
                     WHEN 'middle'    THEN 2
                     WHEN 'death'     THEN 3
                 END
        """
    )


@st.cache_data(ttl=3600)
def get_boundary_stats(venue):
    return query(
        """
        SELECT
            ROUND(SUM(CASE WHEN is_four  THEN 1 ELSE 0 END) * 1.0
                  / NULLIF(COUNT(DISTINCT match_id), 0), 1) AS avg_fours,
            ROUND(SUM(CASE WHEN is_six   THEN 1 ELSE 0 END) * 1.0
                  / NULLIF(COUNT(DISTINCT match_id), 0), 1) AS avg_sixes
        FROM balls
        WHERE venue = ?
        """,
        [venue],
    )


@st.cache_data(ttl=3600)
def get_wicket_types(venue):
    return query(
        """
        SELECT wicket_kind AS dismissal_type,
               COUNT(*)    AS count
        FROM balls
        WHERE venue = ?
          AND wicket_kind IS NOT NULL
          AND wicket_kind != ''
        GROUP BY wicket_kind
        ORDER BY count DESC
        """,
        [venue],
    )


@st.cache_data(ttl=3600)
def get_toss_analysis(venue):
    return query(
        """
        SELECT toss_decision,
               COUNT(*) AS total,
               SUM(CASE WHEN toss_winner = match_won_by THEN 1 ELSE 0 END) AS toss_winner_won
        FROM matches
        WHERE venue = ?
          AND toss_decision IS NOT NULL
          AND match_won_by IS NOT NULL
        GROUP BY toss_decision
        """,
        [venue],
    )


@st.cache_data(ttl=3600)
def get_bat_field_win_pct(venue):
    return query(
        """
        SELECT
            SUM(CASE WHEN batting_first_won       THEN 1 ELSE 0 END) AS bat_first_wins,
            SUM(CASE WHEN NOT batting_first_won    THEN 1 ELSE 0 END) AS field_first_wins,
            COUNT(*) AS total
        FROM matches
        WHERE venue = ?
          AND batting_first_won IS NOT NULL
        """,
        [venue],
    )


@st.cache_data(ttl=3600)
def get_team_performance(venue):
    return query(
        """
        WITH team_matches AS (
            SELECT match_id, team1 AS team,
                   CASE WHEN match_won_by = team1 THEN 1 ELSE 0 END AS won
            FROM matches WHERE venue = ? AND match_won_by IS NOT NULL
            UNION ALL
            SELECT match_id, team2 AS team,
                   CASE WHEN match_won_by = team2 THEN 1 ELSE 0 END AS won
            FROM matches WHERE venue = ? AND match_won_by IS NOT NULL
        )
        SELECT team,
               COUNT(*)                AS matches,
               SUM(won)                AS wins,
               COUNT(*) - SUM(won)     AS losses,
               ROUND(SUM(won) * 100.0 / COUNT(*), 1) AS win_pct
        FROM team_matches
        GROUP BY team
        ORDER BY win_pct DESC, matches DESC
        """,
        [venue, venue],
    )


@st.cache_data(ttl=3600)
def get_top_run_scorers(venue, limit=10):
    return query(
        """
        SELECT batter,
               COUNT(DISTINCT match_id)   AS matches,
               SUM(runs)                  AS total_runs,
               MAX(runs)                  AS highest_score,
               ROUND(SUM(runs) * 100.0
                     / NULLIF(SUM(balls), 0), 1) AS strike_rate,
               SUM(fours) AS fours,
               SUM(sixes) AS sixes
        FROM player_batting
        WHERE venue = ?
        GROUP BY batter
        ORDER BY total_runs DESC
        LIMIT ?
        """,
        [venue, limit],
    )


@st.cache_data(ttl=3600)
def get_top_wicket_takers(venue, limit=10):
    return query(
        """
        SELECT bowler,
               COUNT(DISTINCT match_id)   AS matches,
               SUM(wickets)               AS total_wickets,
               ROUND(SUM(runs_conceded) * 6.0
                     / NULLIF(SUM(balls_bowled), 0), 2) AS economy,
               ROUND(SUM(balls_bowled) * 1.0
                     / NULLIF(SUM(wickets), 0), 1)      AS strike_rate
        FROM player_bowling
        WHERE venue = ?
        GROUP BY bowler
        ORDER BY total_wickets DESC
        LIMIT ?
        """,
        [venue, limit],
    )


@st.cache_data(ttl=3600)
def get_highest_scores(venue, limit=10):
    return query(
        """
        SELECT batter,
               runs,
               balls,
               fours,
               sixes,
               strike_rate,
               batting_team,
               season
        FROM player_batting
        WHERE venue = ?
        ORDER BY runs DESC
        LIMIT ?
        """,
        [venue, limit],
    )


# ---------------------------------------------------------------------------
# Page header & venue selector
# ---------------------------------------------------------------------------

st.title("Venue Intelligence")
st.caption("Ground-specific insights — pitch behaviour, scoring patterns & team performance.")

venue_options = ["All Venues"] + get_venue_list()
selected_venue = st.selectbox("Select Venue", venue_options, key="venue_selector")

st.divider()

# ===================================================================
# ALL VENUES VIEW
# ===================================================================
if selected_venue == "All Venues":
    venues_df = get_all_venues()

    # ---- summary metrics ----
    st.markdown(big_number_style(), unsafe_allow_html=True)
    m1, m2 = st.columns(2)
    with m1:
        st.metric(**metric_card("Total Venues", format_number(len(venues_df))))
    with m2:
        st.metric(**metric_card("Total Matches", format_number(int(venues_df["total_matches"].sum()))))

    st.divider()

    # ---- sortable venue table ----
    st.subheader("Venue Overview")
    display_df = venues_df[
        [
            "venue", "city", "total_matches", "avg_score",
            "avg_first_innings", "avg_second_innings",
            "bat_first_win_pct", "avg_boundaries",
        ]
    ].copy()
    display_df.columns = [
        "Venue", "City", "Matches", "Avg Score",
        "Avg 1st Inn", "Avg 2nd Inn",
        "Bat First Win%", "Avg Boundaries",
    ]
    st.dataframe(
        display_df,
        width='stretch',
        hide_index=True,
        column_config={
            "Avg Score": st.column_config.NumberColumn(format="%.1f"),
            "Avg 1st Inn": st.column_config.NumberColumn(format="%.1f"),
            "Avg 2nd Inn": st.column_config.NumberColumn(format="%.1f"),
            "Bat First Win%": st.column_config.NumberColumn(format="%.1f%%"),
            "Avg Boundaries": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    st.divider()

    # ---- Venue Clustering ----
    st.subheader("Venue Clustering")
    fig = styled_scatter(
        venues_df,
        x="avg_score",
        y="bat_first_win_pct",
        size="total_matches",
        hover_name="venue",
        title="Avg Score vs Bat-First Win %",
    )
    fig.update_layout(xaxis_title="Avg Score", yaxis_title="Bat First Win %")
    st.plotly_chart(fig, width='stretch')

    st.divider()

    # ---- Venue Usage Over Seasons (full-width) ----
    st.subheader("Venue Usage Over Seasons")
    usage_df = get_venue_season_usage()
    if not usage_df.empty:
        pivot = usage_df.pivot_table(
            index="venue", columns="season", values="match_count", fill_value=0
        )
        # keep venues with >5 total matches for readability
        pivot = pivot.loc[pivot.sum(axis=1) > 5]
        pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]

        fig = go.Figure(
            data=go.Heatmap(
                z=pivot.values,
                x=[str(s) for s in pivot.columns],
                y=pivot.index.tolist(),
                colorscale="YlOrRd",
                hoverongaps=False,
                hovertemplate=(
                    "Venue: %{y}<br>Season: %{x}<br>Matches: %{z}<extra></extra>"
                ),
            )
        )
        fig.update_layout(title="Matches Hosted by Season")
        apply_ipl_style(fig, height=max(500, len(pivot) * 24))
        st.plotly_chart(fig, width='stretch')

# ===================================================================
# SPECIFIC VENUE VIEW
# ===================================================================
else:
    venue_row = query("SELECT * FROM venues WHERE venue = ?", [selected_venue])

    if venue_row.empty:
        st.warning("No data found for this venue.")
        st.stop()

    v = venue_row.iloc[0]
    seasons = get_venue_seasons(selected_venue)

    # ---- identity card ----
    season_range_str = f"{min(seasons)}–{max(seasons)}" if seasons else "N/A"
    st.subheader(f"{selected_venue}")
    st.markdown(
        f"**City:** {v.get('city', 'N/A')}  --  "
        f"**Total Matches:** {format_number(v['total_matches'])}  --  "
        f"**Seasons Hosted:** {len(seasons)} ({season_range_str})"
    )

    # ---- metric cards ----
    st.markdown(big_number_style(), unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric(**metric_card("Matches", format_number(v["total_matches"])))
    with c2:
        st.metric(**metric_card("Avg 1st Inn", format_average(v["avg_first_innings"])))
    with c3:
        st.metric(**metric_card("Avg 2nd Inn", format_average(v["avg_second_innings"])))
    with c4:
        st.metric(**metric_card("Bat First Win%", f"{v['bat_first_win_pct']:.1f}%"))
    with c5:
        st.metric(**metric_card("Avg Boundaries", format_average(v["avg_boundaries"])))
    with c6:
        st.metric(**metric_card("Avg Wickets", format_average(v["avg_wickets"])))

    st.divider()

    # ---- Score Distribution & Avg Score Trend ----
    left, right = st.columns(2)

    with left:
        st.subheader("Score Distribution")
        scores_df = get_innings_scores(selected_venue)
        if not scores_df.empty:
            melted = pd.melt(
                scores_df,
                value_vars=["first_innings_score", "second_innings_score"],
                var_name="Innings",
                value_name="Score",
            )
            melted["Innings"] = melted["Innings"].map(
                {"first_innings_score": "1st Innings", "second_innings_score": "2nd Innings"}
            )
            fig = px.histogram(
                melted,
                x="Score",
                color="Innings",
                barmode="overlay",
                nbins=20,
                title="1st vs 2nd Innings Score Distribution",
                opacity=0.7,
                color_discrete_map={
                    "1st Innings": "#FF6B6B",
                    "2nd Innings": "#4ECDC4",
                },
            )
            apply_ipl_style(fig)
            fig.update_layout(xaxis_title="Score", yaxis_title="Frequency")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Not enough data for score distribution.")

    with right:
        st.subheader("Avg Score Trend")
        trend_df = get_avg_score_trend(selected_venue)
        if not trend_df.empty:
            fig = styled_line(
                trend_df, x="season", y="avg_score",
                title="Average Score per Season",
            )
            fig.update_layout(xaxis_title="Season", yaxis_title="Avg Score")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Not enough data for score trend.")

    st.divider()

    # ---- Run Rate by Phase & Boundary Stats ----
    left, right = st.columns(2)

    with left:
        st.subheader("Run Rate by Phase")
        phase_df = get_run_rate_by_phase(selected_venue)
        league_df = get_league_avg_run_rate()

        if not phase_df.empty and not league_df.empty:
            phase_df = phase_df.copy()
            league_df = league_df.copy()
            phase_df["type"] = "This Venue"
            league_df["type"] = "League Avg"
            combined = pd.concat([phase_df, league_df], ignore_index=True)
            combined["match_phase"] = combined["match_phase"].str.title()

            fig = styled_bar(
                combined, x="match_phase", y="run_rate",
                title="Run Rate: Venue vs League Average",
                color="type",
            )
            fig.update_layout(
                xaxis_title="Phase", yaxis_title="Run Rate",
                barmode="group",
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Not enough phase data.")

    with right:
        st.subheader("Boundary Stats")
        boundary_df = get_boundary_stats(selected_venue)
        if not boundary_df.empty:
            bd = boundary_df.iloc[0]
            bar_data = pd.DataFrame(
                {"Boundary Type": ["Avg 4s / Match", "Avg 6s / Match"],
                 "Count": [bd["avg_fours"], bd["avg_sixes"]]}
            )
            fig = styled_bar(
                bar_data, x="Boundary Type", y="Count",
                title="Average Boundaries per Match",
                color="Boundary Type",
                color_map={"Avg 4s / Match": "#4ECDC4", "Avg 6s / Match": "#FF6B6B"},
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No boundary data available.")

    st.divider()

    # ---- Wicket Types & Toss Analysis ----
    left, right = st.columns(2)

    with left:
        st.subheader("Wicket Types")
        wicket_df = get_wicket_types(selected_venue)
        if not wicket_df.empty:
            fig = styled_pie(
                wicket_df, names="dismissal_type", values="count",
                title="Dismissal Types at this Venue",
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No dismissal data available.")

    with right:
        st.subheader("Toss Analysis")
        toss_df = get_toss_analysis(selected_venue)
        bf_df = get_bat_field_win_pct(selected_venue)

        if not toss_df.empty:
            toss_display = toss_df.copy()
            toss_display["toss_decision"] = toss_display["toss_decision"].str.title()
            fig = styled_pie(
                toss_display, names="toss_decision", values="total",
                title="Toss Decision Split",
            )
            st.plotly_chart(fig, width='stretch')

        if not bf_df.empty:
            bfd = bf_df.iloc[0]
            total = int(bfd["total"])
            if total > 0:
                bat_pct = round(bfd["bat_first_wins"] * 100.0 / total, 1)
                field_pct = round(bfd["field_first_wins"] * 100.0 / total, 1)
                wc1, wc2 = st.columns(2)
                with wc1:
                    st.metric(**metric_card("Batting First Win%", f"{bat_pct}%"))
                with wc2:
                    st.metric(**metric_card("Fielding First Win%", f"{field_pct}%"))

    st.divider()

    # ---- Team Performance ----
    st.subheader("Team Performance at this Venue")
    team_df = get_team_performance(selected_venue)
    if not team_df.empty:
        team_display = team_df.rename(
            columns={
                "team": "Team", "matches": "Matches", "wins": "Wins",
                "losses": "Losses", "win_pct": "Win%",
            }
        )
        st.dataframe(
            team_display,
            width='stretch',
            hide_index=True,
            column_config={
                "Win%": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
    else:
        st.info("No team performance data available.")

    st.divider()

    # ---- Top Performers ----
    left, right = st.columns(2)

    with left:
        st.subheader("Top Run Scorers")
        batters_df = get_top_run_scorers(selected_venue)
        if not batters_df.empty:
            batters_display = batters_df.rename(
                columns={
                    "batter": "Batter", "matches": "Matches",
                    "total_runs": "Runs", "highest_score": "HS",
                    "strike_rate": "SR", "fours": "4s", "sixes": "6s",
                }
            )
            st.dataframe(
                batters_display, width='stretch', hide_index=True,
                column_config={
                    "SR": st.column_config.NumberColumn(format="%.1f"),
                },
            )
        else:
            st.info("No batting data available.")

    with right:
        st.subheader("Top Wicket Takers")
        bowlers_df = get_top_wicket_takers(selected_venue)
        if not bowlers_df.empty:
            bowlers_display = bowlers_df.rename(
                columns={
                    "bowler": "Bowler", "matches": "Matches",
                    "total_wickets": "Wickets", "economy": "Econ",
                    "strike_rate": "SR",
                }
            )
            st.dataframe(
                bowlers_display, width='stretch', hide_index=True,
                column_config={
                    "Econ": st.column_config.NumberColumn(format="%.2f"),
                    "SR": st.column_config.NumberColumn(format="%.1f"),
                },
            )
        else:
            st.info("No bowling data available.")

    st.divider()

    # ---- Highest Individual Scores ----
    st.subheader("Highest Individual Scores")
    highest_df = get_highest_scores(selected_venue)
    if not highest_df.empty:
        highest_display = highest_df.rename(
            columns={
                "batter": "Batter", "runs": "Runs", "balls": "Balls",
                "fours": "4s", "sixes": "6s", "strike_rate": "SR",
                "batting_team": "Team", "season": "Season",
            }
        )
        st.dataframe(
            highest_display, width='stretch', hide_index=True,
            column_config={
                "SR": st.column_config.NumberColumn(format="%.1f"),
            },
        )
    else:
        st.info("No individual scores data available.")
