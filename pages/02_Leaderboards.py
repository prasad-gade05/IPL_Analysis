"""
Leaderboards — Every ranking across batting, bowling, teams, and all-rounders.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from src.db.connection import query
from src.visualizations.theme import (
    apply_ipl_style, styled_bar, styled_scatter,
    get_team_color, big_number_style, IPL_COLORWAY,
)
from src.utils.constants import TEAM_COLORS, ALL_SEASONS
from src.utils.formatters import (
    format_number, format_strike_rate, format_economy,
    format_average, format_overs,
)

st.title("Leaderboards")
st.markdown(big_number_style(), unsafe_allow_html=True)

# ── Filters ────────────────────────────────────────────────────────────
fc1, fc2 = st.columns([2, 1])
with fc1:
    s1, s2 = st.slider(
        "Season range",
        min_value=min(ALL_SEASONS),
        max_value=max(ALL_SEASONS),
        value=(min(ALL_SEASONS), max(ALL_SEASONS)),
        key="lb_season_range",
    )
with fc2:
    teams_df = query("SELECT DISTINCT team FROM team_season ORDER BY team")
    team_options = ["All Teams"] + teams_df["team"].tolist()
    selected_team = st.selectbox("Team (optional)", team_options, key="lb_team")

team_filter = selected_team if selected_team != "All Teams" else None


# ═══════════════════════════════════════════════════════════════════════
#  CACHED QUERY HELPERS
# ═══════════════════════════════════════════════════════════════════════

# ── Batting ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _career_runs(s1, s2, team=None):
    tf = f"AND batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT batter,
               SUM(runs)::INT                                                         AS total_runs,
               COUNT(*)::INT                                                           AS innings,
               SUM(CASE WHEN was_out THEN 1 ELSE 0 END)::INT                          AS dismissals,
               ROUND(SUM(runs)*1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0), 2) AS avg,
               ROUND(SUM(runs)*100.0 / NULLIF(SUM(balls),0), 1)                       AS sr,
               SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END)::INT                       AS hundreds,
               SUM(CASE WHEN is_fifty   THEN 1 ELSE 0 END)::INT                       AS fifties,
               SUM(fours)::INT                                                         AS fours,
               SUM(sixes)::INT                                                         AS sixes
        FROM player_batting
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY batter
        ORDER BY total_runs DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_centuries(s1, s2, team=None):
    tf = f"AND batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT batter,
               SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END)::INT AS hundreds
        FROM player_batting
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY batter
        HAVING hundreds > 0
        ORDER BY hundreds DESC
        LIMIT 10
    """)


@st.cache_data(ttl=3600)
def _most_fifties(s1, s2, team=None):
    tf = f"AND batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT batter,
               SUM(CASE WHEN is_fifty THEN 1 ELSE 0 END)::INT AS fifties
        FROM player_batting
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY batter
        HAVING fifties > 0
        ORDER BY fifties DESC
        LIMIT 10
    """)


@st.cache_data(ttl=3600)
def _highest_scores(s1, s2, team=None):
    tf = f"AND pb.batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT pb.batter,
               pb.runs::INT                                                     AS score,
               pb.balls::INT                                                    AS balls_faced,
               pb.fours::INT                                                    AS fours,
               pb.sixes::INT                                                    AS sixes,
               ROUND(pb.strike_rate, 1)                                         AS sr,
               CASE WHEN pb.batting_team = m.team1 THEN m.team2 ELSE m.team1 END AS vs_team,
               pb.venue,
               pb.season
        FROM player_batting pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE pb.season BETWEEN {s1} AND {s2} {tf}
        ORDER BY pb.runs DESC, pb.balls ASC
        LIMIT 20
    """)


@st.cache_data(ttl=3600)
def _best_batting_avg(s1, s2, team=None):
    tf = f"AND batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT batter,
               COUNT(*)::INT                                                           AS innings,
               SUM(runs)::INT                                                          AS total_runs,
               SUM(CASE WHEN was_out THEN 1 ELSE 0 END)::INT                          AS dismissals,
               ROUND(SUM(runs)*1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0), 2) AS avg,
               ROUND(SUM(runs)*100.0 / NULLIF(SUM(balls),0), 1)                       AS sr
        FROM player_batting
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY batter
        HAVING COUNT(*) >= 30
        ORDER BY avg DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _best_batting_sr(s1, s2, team=None):
    tf = f"AND batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT batter,
               SUM(balls)::INT   AS total_balls,
               SUM(runs)::INT    AS total_runs,
               COUNT(*)::INT     AS innings,
               ROUND(SUM(runs)*100.0 / NULLIF(SUM(balls),0), 1)                       AS sr,
               ROUND(SUM(runs)*1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0), 2) AS avg
        FROM player_batting
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY batter
        HAVING SUM(balls) >= 500
        ORDER BY sr DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _avg_sr_scatter(s1, s2, team=None):
    tf = f"AND batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT batter,
               SUM(runs)::INT AS total_runs,
               COUNT(*)::INT  AS innings,
               ROUND(SUM(runs)*1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0), 2) AS avg,
               ROUND(SUM(runs)*100.0 / NULLIF(SUM(balls),0), 1)                              AS sr
        FROM player_batting
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY batter
        HAVING SUM(balls) >= 500
               AND SUM(CASE WHEN was_out THEN 1 ELSE 0 END) > 0
    """)


@st.cache_data(ttl=3600)
def _most_sixes(s1, s2, team=None):
    tf = f"AND batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT batter, SUM(sixes)::INT AS total_sixes
        FROM player_batting
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY batter
        ORDER BY total_sixes DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_fours(s1, s2, team=None):
    tf = f"AND batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT batter, SUM(fours)::INT AS total_fours
        FROM player_batting
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY batter
        ORDER BY total_fours DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_ducks(s1, s2, team=None):
    tf = f"AND batting_team = '{team}'" if team else ""
    return query(f"""
        SELECT batter,
               SUM(CASE WHEN is_duck THEN 1 ELSE 0 END)::INT AS ducks
        FROM player_batting
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY batter
        HAVING ducks > 0
        ORDER BY ducks DESC
        LIMIT 10
    """)


# ── Bowling ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _career_wickets(s1, s2, team=None):
    tf = f"AND bowling_team = '{team}'" if team else ""
    return query(f"""
        SELECT bowler,
               COUNT(DISTINCT match_id)::INT                                     AS matches,
               SUM(balls_bowled)::INT                                            AS total_balls,
               SUM(wickets)::INT                                                 AS total_wickets,
               ROUND(SUM(runs_conceded)*1.0 / NULLIF(SUM(wickets),0), 2)        AS avg,
               ROUND(SUM(runs_conceded)*6.0 / NULLIF(SUM(balls_bowled),0), 2)   AS economy,
               ROUND(SUM(balls_bowled)*1.0 / NULLIF(SUM(wickets),0), 1)         AS bowling_sr,
               SUM(dots_bowled)::INT                                             AS dots,
               SUM(maidens)::INT                                                 AS maidens
        FROM player_bowling
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY bowler
        ORDER BY total_wickets DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _best_bowling_figures(s1, s2, team=None):
    tf = f"AND pb.bowling_team = '{team}'" if team else ""
    return query(f"""
        SELECT pb.bowler,
               CAST(pb.wickets AS INT) || '/' || CAST(pb.runs_conceded AS INT) AS figures,
               pb.wickets::INT                                                 AS wkts,
               pb.runs_conceded::INT                                           AS runs,
               CASE WHEN pb.bowling_team = m.team1 THEN m.team2 ELSE m.team1 END AS vs_team,
               pb.venue,
               pb.season
        FROM player_bowling pb
        JOIN matches m ON pb.match_id = m.match_id
        WHERE pb.season BETWEEN {s1} AND {s2} {tf}
        ORDER BY pb.wickets DESC, pb.runs_conceded ASC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _best_economy(s1, s2, team=None):
    tf = f"AND bowling_team = '{team}'" if team else ""
    return query(f"""
        SELECT bowler,
               SUM(balls_bowled)::INT                                            AS total_balls,
               SUM(runs_conceded)::INT                                           AS total_runs,
               SUM(wickets)::INT                                                 AS total_wickets,
               ROUND(SUM(runs_conceded)*6.0 / NULLIF(SUM(balls_bowled),0), 2)   AS economy
        FROM player_bowling
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY bowler
        HAVING SUM(balls_bowled) >= 300
        ORDER BY economy ASC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _best_bowling_avg(s1, s2, team=None):
    tf = f"AND bowling_team = '{team}'" if team else ""
    return query(f"""
        SELECT bowler,
               SUM(wickets)::INT                                                 AS total_wickets,
               SUM(runs_conceded)::INT                                           AS total_runs,
               COUNT(DISTINCT match_id)::INT                                     AS matches,
               ROUND(SUM(runs_conceded)*1.0 / NULLIF(SUM(wickets),0), 2)        AS avg
        FROM player_bowling
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY bowler
        HAVING SUM(wickets) >= 30
        ORDER BY avg ASC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _best_bowling_sr(s1, s2, team=None):
    tf = f"AND bowling_team = '{team}'" if team else ""
    return query(f"""
        SELECT bowler,
               SUM(wickets)::INT                                                 AS total_wickets,
               SUM(balls_bowled)::INT                                            AS total_balls,
               COUNT(DISTINCT match_id)::INT                                     AS matches,
               ROUND(SUM(balls_bowled)*1.0 / NULLIF(SUM(wickets),0), 1)         AS bowling_sr
        FROM player_bowling
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY bowler
        HAVING SUM(wickets) >= 30
        ORDER BY bowling_sr ASC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _most_maidens(s1, s2, team=None):
    tf = f"AND bowling_team = '{team}'" if team else ""
    return query(f"""
        SELECT bowler, SUM(maidens)::INT AS total_maidens
        FROM player_bowling
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY bowler
        HAVING total_maidens > 0
        ORDER BY total_maidens DESC
        LIMIT 10
    """)


@st.cache_data(ttl=3600)
def _most_dot_balls(s1, s2, team=None):
    tf = f"AND bowling_team = '{team}'" if team else ""
    return query(f"""
        SELECT bowler, SUM(dots_bowled)::INT AS total_dots
        FROM player_bowling
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY bowler
        ORDER BY total_dots DESC
        LIMIT 15
    """)


# ── Teams ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _team_win_pct(s1, s2, team=None):
    tf = f"AND team = '{team}'" if team else ""
    return query(f"""
        SELECT team,
               SUM(matches_played)::INT AS matches,
               SUM(wins)::INT           AS wins,
               SUM(losses)::INT         AS losses,
               ROUND(SUM(wins)*100.0 / NULLIF(SUM(matches_played),0), 1) AS win_pct
        FROM team_season
        WHERE season BETWEEN {s1} AND {s2} {tf}
        GROUP BY team
        ORDER BY win_pct DESC
    """)


@st.cache_data(ttl=3600)
def _ipl_titles(s1, s2):
    return query(f"""
        SELECT champion AS team, COUNT(*)::INT AS titles
        FROM season_meta
        WHERE season BETWEEN {s1} AND {s2}
          AND champion IS NOT NULL
        GROUP BY champion
        ORDER BY titles DESC
    """)


@st.cache_data(ttl=3600)
def _highest_totals(s1, s2, team=None):
    tf1 = f"AND team1 = '{team}'" if team else ""
    tf2 = f"AND team2 = '{team}'" if team else ""
    return query(f"""
        SELECT * FROM (
            SELECT team1 AS team,
                   team1_score::INT                          AS score,
                   COALESCE(team1_wickets, 0)::INT           AS wickets,
                   team2 AS opponent, venue, season
            FROM matches
            WHERE season BETWEEN {s1} AND {s2} {tf1}
              AND team1_score IS NOT NULL
            UNION ALL
            SELECT team2 AS team,
                   team2_score::INT                          AS score,
                   COALESCE(team2_wickets, 0)::INT           AS wickets,
                   team1 AS opponent, venue, season
            FROM matches
            WHERE season BETWEEN {s1} AND {s2} {tf2}
              AND team2_score IS NOT NULL
        ) t
        ORDER BY score DESC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _lowest_totals(s1, s2, team=None):
    tf1 = f"AND team1 = '{team}'" if team else ""
    tf2 = f"AND team2 = '{team}'" if team else ""
    return query(f"""
        SELECT * FROM (
            SELECT team1 AS team,
                   team1_score::INT                          AS score,
                   COALESCE(team1_wickets, 0)::INT           AS wickets,
                   team2 AS opponent, venue, season
            FROM matches
            WHERE season BETWEEN {s1} AND {s2} {tf1}
              AND team1_score IS NOT NULL AND team1_score > 0
            UNION ALL
            SELECT team2 AS team,
                   team2_score::INT                          AS score,
                   COALESCE(team2_wickets, 0)::INT           AS wickets,
                   team1 AS opponent, venue, season
            FROM matches
            WHERE season BETWEEN {s1} AND {s2} {tf2}
              AND team2_score IS NOT NULL AND team2_score > 0
        ) t
        ORDER BY score ASC
        LIMIT 15
    """)


@st.cache_data(ttl=3600)
def _highest_chases(s1, s2, team=None):
    tf = f"AND c.chasing_team = '{team}'" if team else ""
    return query(f"""
        WITH chasing AS (
            SELECT DISTINCT match_id, batting_team AS chasing_team
            FROM balls
            WHERE innings = 2
        )
        SELECT
            c.chasing_team                                                          AS team,
            (CASE WHEN c.chasing_team = m.team1 THEN m.team1_score
                  ELSE m.team2_score END)::INT                                      AS score,
            COALESCE(CASE WHEN c.chasing_team = m.team1 THEN m.team1_wickets
                          ELSE m.team2_wickets END, 0)::INT                         AS wickets,
            CASE WHEN c.chasing_team = m.team1 THEN m.team2 ELSE m.team1 END       AS opponent,
            (CASE WHEN c.chasing_team = m.team1 THEN m.team2_score
                  ELSE m.team1_score END)::INT                                      AS target,
            m.venue,
            m.season
        FROM matches m
        JOIN chasing c ON m.match_id = c.match_id
        WHERE m.season BETWEEN {s1} AND {s2} {tf}
          AND m.match_won_by = c.chasing_team
        ORDER BY score DESC
        LIMIT 10
    """)


# ── All-Rounders ───────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _allrounder_scatter(s1, s2):
    return query(f"""
        WITH bat AS (
            SELECT batter AS player,
                   SUM(runs)::INT              AS total_runs,
                   COUNT(DISTINCT match_id)::INT AS bat_matches
            FROM player_batting
            WHERE season BETWEEN {s1} AND {s2}
            GROUP BY batter
            HAVING SUM(runs) >= 500
        ),
        bowl AS (
            SELECT bowler AS player,
                   SUM(wickets)::INT             AS total_wickets,
                   COUNT(DISTINCT match_id)::INT AS bowl_matches
            FROM player_bowling
            WHERE season BETWEEN {s1} AND {s2}
            GROUP BY bowler
            HAVING SUM(wickets) >= 30
        )
        SELECT bat.player,
               bat.total_runs    AS runs,
               bowl.total_wickets AS wickets,
               GREATEST(bat.bat_matches, bowl.bowl_matches)::INT AS matches
        FROM bat
        JOIN bowl ON bat.player = bowl.player
        ORDER BY runs + wickets * 20 DESC
    """)


@st.cache_data(ttl=3600)
def _most_potm(s1, s2, team=None):
    tf = f"AND (team1 = '{team}' OR team2 = '{team}')" if team else ""
    return query(f"""
        SELECT player_of_match AS player, COUNT(*)::INT AS awards
        FROM matches
        WHERE season BETWEEN {s1} AND {s2}
          AND player_of_match IS NOT NULL {tf}
        GROUP BY player_of_match
        ORDER BY awards DESC
        LIMIT 15
    """)


# ── Miscellaneous ──────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _expensive_overs(s1, s2, team=None):
    tf = f"AND b.bowling_team = '{team}'" if team else ""
    return query(f"""
        SELECT b.bowler,
               b.batting_team                              AS vs_team,
               b.over                                      AS over_num,
               b.innings,
               SUM(b.runs_batter)::INT                     AS runs_conceded,
               COUNT(CASE WHEN b.is_four THEN 1 END)::INT  AS fours,
               COUNT(CASE WHEN b.is_six  THEN 1 END)::INT  AS sixes,
               b.season,
               m.venue
        FROM balls b
        JOIN matches m ON b.match_id = m.match_id
        WHERE b.season BETWEEN {s1} AND {s2} {tf}
        GROUP BY b.match_id, b.innings, b.over, b.bowler,
                 b.batting_team, b.bowling_team, b.season, m.venue
        ORDER BY runs_conceded DESC
        LIMIT 20
    """)


# ═══════════════════════════════════════════════════════════════════════
#  TAB CONTENT
# ═══════════════════════════════════════════════════════════════════════

tab_bat, tab_bowl, tab_team, tab_ar, tab_misc = st.tabs(
    ["Batting", "Bowling", "Teams", "All-Rounders", "Miscellaneous"]
)

# ── BATTING TAB ────────────────────────────────────────────────────────
with tab_bat:

    # --- Most Career Runs ---
    st.subheader("Most Career Runs")
    df = _career_runs(s1, s2, team_filter)
    if not df.empty:
        fig = styled_bar(
            df.sort_values("total_runs"), x="batter", y="total_runs",
            title="Top 15 Run Scorers", horizontal=True, height=500,
        )
        st.plotly_chart(fig, width='stretch')

        display = df.rename(columns={
            "batter": "Player", "total_runs": "Runs", "innings": "Inn",
            "avg": "Avg", "sr": "SR", "hundreds": "100s",
            "fifties": "50s", "fours": "4s", "sixes": "6s",
        })[["Player", "Runs", "Inn", "Avg", "SR", "100s", "50s", "4s", "6s"]]
        st.dataframe(display, width='stretch', hide_index=True)
    else:
        st.info("No data for the selected filters.")

    st.divider()

    # --- Centuries & Fifties ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Most Centuries")
        df_c = _most_centuries(s1, s2, team_filter)
        if not df_c.empty:
            fig = styled_bar(df_c, x="batter", y="hundreds", title="Most 100s (Top 10)")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No centuries in selected range.")

    with c2:
        st.subheader("Most Fifties")
        df_f = _most_fifties(s1, s2, team_filter)
        if not df_f.empty:
            fig = styled_bar(df_f, x="batter", y="fifties", title="Most 50s (Top 10)")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No fifties in selected range.")

    st.divider()

    # --- Highest Individual Scores ---
    st.subheader("Highest Individual Scores")
    df_hs = _highest_scores(s1, s2, team_filter)
    if not df_hs.empty:
        st.dataframe(
            df_hs.rename(columns={
                "batter": "Player", "score": "Score", "balls_faced": "Balls",
                "fours": "4s", "sixes": "6s", "sr": "SR",
                "vs_team": "Vs", "venue": "Venue", "season": "Season",
            }),
            width='stretch', hide_index=True,
        )

    st.divider()

    # --- Best Average & SR ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Best Batting Average (min 30 inn)")
        df_ba = _best_batting_avg(s1, s2, team_filter)
        if not df_ba.empty:
            st.dataframe(
                df_ba.rename(columns={
                    "batter": "Player", "innings": "Inn", "total_runs": "Runs",
                    "dismissals": "Outs", "avg": "Avg", "sr": "SR",
                })[["Player", "Inn", "Runs", "Outs", "Avg", "SR"]],
                width='stretch', hide_index=True,
            )
        else:
            st.info("No qualifying batters.")

    with c2:
        st.subheader("Best Strike Rate (min 500 balls)")
        df_bsr = _best_batting_sr(s1, s2, team_filter)
        if not df_bsr.empty:
            st.dataframe(
                df_bsr.rename(columns={
                    "batter": "Player", "total_balls": "Balls", "total_runs": "Runs",
                    "innings": "Inn", "sr": "SR", "avg": "Avg",
                })[["Player", "Balls", "Runs", "Inn", "SR", "Avg"]],
                width='stretch', hide_index=True,
            )
        else:
            st.info("No qualifying batters.")

    st.divider()

    # --- Average × SR Scatter ---
    st.subheader("Average × Strike Rate")
    df_as = _avg_sr_scatter(s1, s2, team_filter)
    if not df_as.empty:
        fig = styled_scatter(
            df_as, x="avg", y="sr",
            title="Batting Quality Index (min 500 balls)",
            size="total_runs", hover_name="batter", height=550,
        )
        st.plotly_chart(fig, width='stretch')

    st.divider()

    # --- Sixes & Fours ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Most Career Sixes")
        df_6 = _most_sixes(s1, s2, team_filter)
        if not df_6.empty:
            fig = styled_bar(
                df_6.sort_values("total_sixes"), x="batter", y="total_sixes",
                title="Top 15 Six Hitters", horizontal=True,
            )
            st.plotly_chart(fig, width='stretch')

    with c2:
        st.subheader("Most Career Fours")
        df_4 = _most_fours(s1, s2, team_filter)
        if not df_4.empty:
            fig = styled_bar(
                df_4.sort_values("total_fours"), x="batter", y="total_fours",
                title="Top 15 Four Hitters", horizontal=True,
            )
            st.plotly_chart(fig, width='stretch')

    st.divider()

    # --- Most Ducks ---
    st.subheader("Most Ducks")
    df_d = _most_ducks(s1, s2, team_filter)
    if not df_d.empty:
        fig = styled_bar(df_d, x="batter", y="ducks", title="Most Ducks (Top 10)")
        st.plotly_chart(fig, width='stretch')


# ── BOWLING TAB ────────────────────────────────────────────────────────
with tab_bowl:

    # --- Most Career Wickets ---
    st.subheader("Most Career Wickets")
    df_w = _career_wickets(s1, s2, team_filter)
    if not df_w.empty:
        fig = styled_bar(
            df_w.sort_values("total_wickets"), x="bowler", y="total_wickets",
            title="Top 15 Wicket Takers", horizontal=True, height=500,
        )
        st.plotly_chart(fig, width='stretch')

        disp = df_w.copy()
        disp["overs"] = disp["total_balls"].apply(format_overs)
        disp = disp.rename(columns={
            "bowler": "Bowler", "matches": "Mat", "total_wickets": "Wkts",
            "overs": "Overs", "economy": "Econ", "bowling_sr": "SR",
            "avg": "Avg", "dots": "Dots", "maidens": "Mdns",
        })[["Bowler", "Wkts", "Mat", "Overs", "Econ", "SR", "Avg", "Dots", "Mdns"]]
        st.dataframe(disp, width='stretch', hide_index=True)
    else:
        st.info("No data for the selected filters.")

    st.divider()

    # --- Best Bowling Figures ---
    st.subheader("Best Bowling Figures")
    df_bf = _best_bowling_figures(s1, s2, team_filter)
    if not df_bf.empty:
        st.dataframe(
            df_bf.rename(columns={
                "bowler": "Bowler", "figures": "Figures",
                "vs_team": "Vs", "venue": "Venue", "season": "Season",
            })[["Bowler", "Figures", "Vs", "Venue", "Season"]],
            width='stretch', hide_index=True,
        )

    st.divider()

    # --- Economy & Average ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Best Economy (min 300 balls)")
        df_be = _best_economy(s1, s2, team_filter)
        if not df_be.empty:
            disp = df_be.copy()
            disp["overs"] = disp["total_balls"].apply(format_overs)
            st.dataframe(
                disp.rename(columns={
                    "bowler": "Bowler", "overs": "Overs", "total_runs": "Runs",
                    "total_wickets": "Wkts", "economy": "Econ",
                })[["Bowler", "Overs", "Runs", "Wkts", "Econ"]],
                width='stretch', hide_index=True,
            )

    with c2:
        st.subheader("Best Bowling Average (min 30 wkts)")
        df_bba = _best_bowling_avg(s1, s2, team_filter)
        if not df_bba.empty:
            st.dataframe(
                df_bba.rename(columns={
                    "bowler": "Bowler", "total_wickets": "Wkts",
                    "total_runs": "Runs", "matches": "Mat", "avg": "Avg",
                })[["Bowler", "Mat", "Wkts", "Runs", "Avg"]],
                width='stretch', hide_index=True,
            )

    st.divider()

    # --- Bowling Strike Rate ---
    st.subheader("Best Bowling Strike Rate (min 30 wkts)")
    df_bbs = _best_bowling_sr(s1, s2, team_filter)
    if not df_bbs.empty:
        disp = df_bbs.copy()
        disp["overs"] = disp["total_balls"].apply(format_overs)
        st.dataframe(
            disp.rename(columns={
                "bowler": "Bowler", "total_wickets": "Wkts",
                "overs": "Overs", "matches": "Mat", "bowling_sr": "SR",
            })[["Bowler", "Mat", "Wkts", "Overs", "SR"]],
            width='stretch', hide_index=True,
        )

    st.divider()

    # --- Maidens & Dots ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Most Maiden Overs")
        df_m = _most_maidens(s1, s2, team_filter)
        if not df_m.empty:
            fig = styled_bar(df_m, x="bowler", y="total_maidens",
                             title="Top 10 Maiden Bowlers")
            st.plotly_chart(fig, width='stretch')

    with c2:
        st.subheader("Most Dot Balls Bowled")
        df_dt = _most_dot_balls(s1, s2, team_filter)
        if not df_dt.empty:
            fig = styled_bar(df_dt, x="bowler", y="total_dots",
                             title="Top 15 Dot Ball Bowlers")
            st.plotly_chart(fig, width='stretch')


# ── TEAM TAB ───────────────────────────────────────────────────────────
with tab_team:

    # --- Win Percentage ---
    st.subheader("Win Percentage — All Teams")
    df_wp = _team_win_pct(s1, s2, team_filter)
    if not df_wp.empty:
        color_map = {t: get_team_color(t) for t in df_wp["team"]}
        fig = styled_bar(
            df_wp.sort_values("win_pct"), x="team", y="win_pct",
            title="Team Win %", color="team", color_map=color_map,
            horizontal=True, height=550,
        )
        st.plotly_chart(fig, width='stretch')

    st.divider()

    # --- IPL Titles ---
    st.subheader("Most IPL Titles")
    df_t = _ipl_titles(s1, s2)
    if not df_t.empty:
        color_map = {t: get_team_color(t) for t in df_t["team"]}
        fig = styled_bar(
            df_t, x="team", y="titles", title="IPL Championships",
            color="team", color_map=color_map,
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No title data in selected range.")

    st.divider()

    # --- Highest & Lowest Totals ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Highest Team Totals")
        df_ht = _highest_totals(s1, s2, team_filter)
        if not df_ht.empty:
            disp = df_ht.copy()
            disp["score_wkt"] = disp["score"].astype(str) + "/" + disp["wickets"].astype(str)
            st.dataframe(
                disp.rename(columns={
                    "team": "Team", "score_wkt": "Score", "opponent": "Vs",
                    "venue": "Venue", "season": "Season",
                })[["Team", "Score", "Vs", "Venue", "Season"]],
                width='stretch', hide_index=True,
            )

    with c2:
        st.subheader("Lowest Team Totals")
        df_lt = _lowest_totals(s1, s2, team_filter)
        if not df_lt.empty:
            disp = df_lt.copy()
            disp["score_wkt"] = disp["score"].astype(str) + "/" + disp["wickets"].astype(str)
            st.dataframe(
                disp.rename(columns={
                    "team": "Team", "score_wkt": "Score", "opponent": "Vs",
                    "venue": "Venue", "season": "Season",
                })[["Team", "Score", "Vs", "Venue", "Season"]],
                width='stretch', hide_index=True,
            )

    st.divider()

    # --- Highest Successful Chases ---
    st.subheader("Highest Successful Chases")
    df_hc = _highest_chases(s1, s2, team_filter)
    if not df_hc.empty:
        disp = df_hc.copy()
        disp["score_wkt"] = disp["score"].astype(str) + "/" + disp["wickets"].astype(str)
        st.dataframe(
            disp.rename(columns={
                "team": "Team", "score_wkt": "Score", "target": "Target",
                "opponent": "Vs", "venue": "Venue", "season": "Season",
            })[["Team", "Score", "Target", "Vs", "Venue", "Season"]],
            width='stretch', hide_index=True,
        )


# ── ALL-ROUNDER TAB ───────────────────────────────────────────────────
with tab_ar:

    # --- Scatter ---
    st.subheader("All-Rounder Impact (500+ runs & 30+ wickets)")
    df_ar = _allrounder_scatter(s1, s2)
    if not df_ar.empty:
        fig = styled_scatter(
            df_ar, x="runs", y="wickets",
            title="All-Rounder Scatter",
            size="matches", hover_name="player", height=550,
        )
        st.plotly_chart(fig, width='stretch')

        st.dataframe(
            df_ar.rename(columns={
                "player": "Player", "runs": "Runs",
                "wickets": "Wickets", "matches": "Matches",
            }),
            width='stretch', hide_index=True,
        )
    else:
        st.info("No qualifying all-rounders for the selected range.")

    st.divider()

    # --- POTM ---
    st.subheader("Most Player of the Match Awards")
    df_potm = _most_potm(s1, s2, team_filter)
    if not df_potm.empty:
        fig = styled_bar(df_potm, x="player", y="awards",
                         title="Top 15 POTM Winners")
        st.plotly_chart(fig, width='stretch')


# ── MISCELLANEOUS TAB ─────────────────────────────────────────────────
with tab_misc:

    st.subheader("Most Expensive Overs")
    df_eo = _expensive_overs(s1, s2, team_filter)
    if not df_eo.empty:
        st.dataframe(
            df_eo.rename(columns={
                "bowler": "Bowler", "vs_team": "Vs Team", "over_num": "Over",
                "innings": "Inn", "runs_conceded": "Runs", "fours": "4s",
                "sixes": "6s", "season": "Season", "venue": "Venue",
            })[["Bowler", "Over", "Runs", "4s", "6s", "Vs Team", "Inn", "Venue", "Season"]],
            width='stretch', hide_index=True,
        )
    else:
        st.info("No data for the selected filters.")
