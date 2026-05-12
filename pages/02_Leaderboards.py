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
from src.utils.control_renderer import render_visual_controls, active_control_chips
from src.utils.control_schema import VisualSpec
from src.utils.visual_specs import limit_control, number_control, season_range_control, select_control
from src.visualizations.card_renderer import render_active_filters

st.title("Leaderboards")
st.markdown(big_number_style(), unsafe_allow_html=True)

DEFAULT_SEASON_RANGE = (min(ALL_SEASONS), max(ALL_SEASONS))


# ═══════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def _sanitize_season_range(season_range: tuple[int, int] | None = None) -> tuple[int, int]:
    if season_range is None:
        return DEFAULT_SEASON_RANGE
    start, end = season_range
    start = max(DEFAULT_SEASON_RANGE[0], int(start))
    end = min(DEFAULT_SEASON_RANGE[1], int(end))
    return (start, end) if start <= end else (end, start)


def _season_condition(column: str, season_range: tuple[int, int] | None = None) -> str:
    start, end = _sanitize_season_range(season_range)
    return f"{column} BETWEEN {start} AND {end}"


def _sanitize_limit(limit: int | None, default: int) -> int:
    return max(1, int(limit or default))


def _sanitize_minimum(value: int | None, default: int, minimum: int = 1) -> int:
    return max(minimum, int(default if value is None else value))


def _team_filter_clause(team: str | None) -> str:
    return f"AND batting_team = '{team}'" if team else ""


def _team_filter_clause_bowling(team: str | None) -> str:
    return f"AND bowling_team = '{team}'" if team else ""


def _visual_spec(
    visual_id: str,
    title: str,
    *,
    description: str = "",
    default_limit: int | None = None,
    extra_controls: list | None = None,
    empty_state_help: str = "No data found for the selected filters.",
) -> VisualSpec:
    controls = [season_range_control()]
    if default_limit is not None:
        controls.append(limit_control(default=default_limit, minimum=1, maximum=max(50, default_limit)))
    if extra_controls:
        controls.extend(extra_controls)
    return VisualSpec(
        id=visual_id,
        title=title,
        description=description,
        controls=controls,
        empty_state_help=empty_state_help,
    )


# ═══════════════════════════════════════════════════════════════════════
#  CACHED QUERY HELPERS
# ═══════════════════════════════════════════════════════════════════════

# ── Batting ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _career_runs(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause(team)
    limit = _sanitize_limit(limit, 15)
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
        WHERE {season_filter} {tf}
        GROUP BY batter
        ORDER BY total_runs DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _most_centuries(season_range=DEFAULT_SEASON_RANGE, team=None, limit=10):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause(team)
    limit = _sanitize_limit(limit, 10)
    return query(f"""
        SELECT batter,
               SUM(CASE WHEN is_hundred THEN 1 ELSE 0 END)::INT AS hundreds
        FROM player_batting
        WHERE {season_filter} {tf}
        GROUP BY batter
        HAVING hundreds > 0
        ORDER BY hundreds DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _most_fifties(season_range=DEFAULT_SEASON_RANGE, team=None, limit=10):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause(team)
    limit = _sanitize_limit(limit, 10)
    return query(f"""
        SELECT batter,
               SUM(CASE WHEN is_fifty THEN 1 ELSE 0 END)::INT AS fifties
        FROM player_batting
        WHERE {season_filter} {tf}
        GROUP BY batter
        HAVING fifties > 0
        ORDER BY fifties DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _highest_scores(season_range=DEFAULT_SEASON_RANGE, team=None, limit=20):
    season_filter = _season_condition("pb.season", season_range)
    tf = f"AND pb.batting_team = '{team}'" if team else ""
    limit = _sanitize_limit(limit, 20)
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
        WHERE {season_filter} {tf}
        ORDER BY pb.runs DESC, pb.balls ASC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _best_batting_avg(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15, min_innings=30):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause(team)
    limit = _sanitize_limit(limit, 15)
    min_innings = _sanitize_minimum(min_innings, 30, 1)
    return query(f"""
        SELECT batter,
               COUNT(*)::INT                                                           AS innings,
               SUM(runs)::INT                                                          AS total_runs,
               SUM(CASE WHEN was_out THEN 1 ELSE 0 END)::INT                          AS dismissals,
               ROUND(SUM(runs)*1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0), 2) AS avg,
               ROUND(SUM(runs)*100.0 / NULLIF(SUM(balls),0), 1)                       AS sr
        FROM player_batting
        WHERE {season_filter} {tf}
        GROUP BY batter
        HAVING COUNT(*) >= {min_innings}
        ORDER BY avg DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _best_batting_sr(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15, min_balls=500):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause(team)
    limit = _sanitize_limit(limit, 15)
    min_balls = _sanitize_minimum(min_balls, 500, 1)
    return query(f"""
        SELECT batter,
               SUM(balls)::INT   AS total_balls,
               SUM(runs)::INT    AS total_runs,
               COUNT(*)::INT     AS innings,
               ROUND(SUM(runs)*100.0 / NULLIF(SUM(balls),0), 1)                       AS sr,
               ROUND(SUM(runs)*1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0), 2) AS avg
        FROM player_batting
        WHERE {season_filter} {tf}
        GROUP BY batter
        HAVING SUM(balls) >= {min_balls}
        ORDER BY sr DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _avg_sr_scatter(season_range=DEFAULT_SEASON_RANGE, team=None, min_balls=500):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause(team)
    min_balls = _sanitize_minimum(min_balls, 500, 1)
    return query(f"""
        SELECT batter,
               SUM(runs)::INT AS total_runs,
               COUNT(*)::INT  AS innings,
               ROUND(SUM(runs)*1.0 / NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0), 2) AS avg,
               ROUND(SUM(runs)*100.0 / NULLIF(SUM(balls),0), 1)                              AS sr
        FROM player_batting
        WHERE {season_filter} {tf}
        GROUP BY batter
        HAVING SUM(balls) >= {min_balls}
               AND SUM(CASE WHEN was_out THEN 1 ELSE 0 END) > 0
    """)


@st.cache_data(ttl=3600)
def _most_sixes(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause(team)
    limit = _sanitize_limit(limit, 15)
    return query(f"""
        SELECT batter, SUM(sixes)::INT AS total_sixes
        FROM player_batting
        WHERE {season_filter} {tf}
        GROUP BY batter
        ORDER BY total_sixes DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _most_fours(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause(team)
    limit = _sanitize_limit(limit, 15)
    return query(f"""
        SELECT batter, SUM(fours)::INT AS total_fours
        FROM player_batting
        WHERE {season_filter} {tf}
        GROUP BY batter
        ORDER BY total_fours DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _most_ducks(season_range=DEFAULT_SEASON_RANGE, team=None, limit=10):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause(team)
    limit = _sanitize_limit(limit, 10)
    return query(f"""
        SELECT batter,
               SUM(CASE WHEN is_duck THEN 1 ELSE 0 END)::INT AS ducks
        FROM player_batting
        WHERE {season_filter} {tf}
        GROUP BY batter
        HAVING ducks > 0
        ORDER BY ducks DESC
        LIMIT {limit}
    """)


# ── Bowling ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _career_wickets(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause_bowling(team)
    limit = _sanitize_limit(limit, 15)
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
        WHERE {season_filter} {tf}
        GROUP BY bowler
        ORDER BY total_wickets DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _best_bowling_figures(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15):
    season_filter = _season_condition("pb.season", season_range)
    tf = f"AND pb.bowling_team = '{team}'" if team else ""
    limit = _sanitize_limit(limit, 15)
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
        WHERE {season_filter} {tf}
        ORDER BY pb.wickets DESC, pb.runs_conceded ASC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _best_economy(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15, min_balls=300):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause_bowling(team)
    limit = _sanitize_limit(limit, 15)
    min_balls = _sanitize_minimum(min_balls, 300, 1)
    return query(f"""
        SELECT bowler,
               SUM(balls_bowled)::INT                                            AS total_balls,
               SUM(runs_conceded)::INT                                           AS total_runs,
               SUM(wickets)::INT                                                 AS total_wickets,
               ROUND(SUM(runs_conceded)*6.0 / NULLIF(SUM(balls_bowled),0), 2)   AS economy
        FROM player_bowling
        WHERE {season_filter} {tf}
        GROUP BY bowler
        HAVING SUM(balls_bowled) >= {min_balls}
        ORDER BY economy ASC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _best_bowling_avg(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15, min_wickets=30):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause_bowling(team)
    limit = _sanitize_limit(limit, 15)
    min_wickets = _sanitize_minimum(min_wickets, 30, 1)
    return query(f"""
        SELECT bowler,
               SUM(wickets)::INT                                                 AS total_wickets,
               SUM(runs_conceded)::INT                                           AS total_runs,
               COUNT(DISTINCT match_id)::INT                                     AS matches,
               ROUND(SUM(runs_conceded)*1.0 / NULLIF(SUM(wickets),0), 2)        AS avg
        FROM player_bowling
        WHERE {season_filter} {tf}
        GROUP BY bowler
        HAVING SUM(wickets) >= {min_wickets}
        ORDER BY avg ASC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _best_bowling_sr(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15, min_wickets=30):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause_bowling(team)
    limit = _sanitize_limit(limit, 15)
    min_wickets = _sanitize_minimum(min_wickets, 30, 1)
    return query(f"""
        SELECT bowler,
               SUM(wickets)::INT                                                 AS total_wickets,
               SUM(balls_bowled)::INT                                            AS total_balls,
               COUNT(DISTINCT match_id)::INT                                     AS matches,
               ROUND(SUM(balls_bowled)*1.0 / NULLIF(SUM(wickets),0), 1)         AS bowling_sr
        FROM player_bowling
        WHERE {season_filter} {tf}
        GROUP BY bowler
        HAVING SUM(wickets) >= {min_wickets}
        ORDER BY bowling_sr ASC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _most_maidens(season_range=DEFAULT_SEASON_RANGE, team=None, limit=10):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause_bowling(team)
    limit = _sanitize_limit(limit, 10)
    return query(f"""
        SELECT bowler, SUM(maidens)::INT AS total_maidens
        FROM player_bowling
        WHERE {season_filter} {tf}
        GROUP BY bowler
        HAVING total_maidens > 0
        ORDER BY total_maidens DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _most_dot_balls(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15):
    season_filter = _season_condition("season", season_range)
    tf = _team_filter_clause_bowling(team)
    limit = _sanitize_limit(limit, 15)
    return query(f"""
        SELECT bowler, SUM(dots_bowled)::INT AS total_dots
        FROM player_bowling
        WHERE {season_filter} {tf}
        GROUP BY bowler
        ORDER BY total_dots DESC
        LIMIT {limit}
    """)


# ── Teams ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _team_win_pct(season_range=DEFAULT_SEASON_RANGE, team=None):
    season_filter = _season_condition("season", season_range)
    tf = f"AND team = '{team}'" if team else ""
    return query(f"""
        SELECT team,
               SUM(matches_played)::INT AS matches,
               SUM(wins)::INT           AS wins,
               SUM(losses)::INT         AS losses,
               ROUND(SUM(wins)*100.0 / NULLIF(SUM(matches_played),0), 1) AS win_pct
        FROM team_season
        WHERE {season_filter} {tf}
        GROUP BY team
        ORDER BY win_pct DESC
    """)


@st.cache_data(ttl=3600)
def _ipl_titles(season_range=DEFAULT_SEASON_RANGE):
    season_filter = _season_condition("season", season_range)
    return query(f"""
        SELECT champion AS team, COUNT(*)::INT AS titles
        FROM season_meta
        WHERE {season_filter}
          AND champion IS NOT NULL
        GROUP BY champion
        ORDER BY titles DESC
    """)


@st.cache_data(ttl=3600)
def _highest_totals(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15):
    season_filter = _season_condition("season", season_range)
    tf = f"AND team = '{team}'" if team else ""
    limit = _sanitize_limit(limit, 15)
    return query(f"""
        SELECT team,
               score,
               wickets,
               opponent,
               venue,
               season
        FROM completed_team_innings
        WHERE innings_complete
          AND score IS NOT NULL
          AND {season_filter} {tf}
        ORDER BY score DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _lowest_totals(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15):
    season_filter = _season_condition("season", season_range)
    tf = f"AND team = '{team}'" if team else ""
    limit = _sanitize_limit(limit, 15)
    return query(f"""
        SELECT team,
               score,
               wickets,
               opponent,
               venue,
               season
        FROM completed_team_innings
        WHERE low_total_record_eligible
          AND score > 0
          AND {season_filter} {tf}
        ORDER BY score ASC
        LIMIT {limit}
    """)


@st.cache_data(ttl=3600)
def _highest_chases(season_range=DEFAULT_SEASON_RANGE, team=None, limit=10):
    season_filter = _season_condition("season", season_range)
    tf = f"AND team = '{team}'" if team else ""
    limit = _sanitize_limit(limit, 10)
    return query(f"""
        SELECT
            team,
            runs_scored::INT AS score,
            wickets_lost::INT AS wickets,
            opponent,
            target_to_win::INT AS target,
            venue,
            season
        FROM team_match_results
        WHERE chasing
          AND successful_chase
          AND {season_filter} {tf}
        ORDER BY score DESC
        LIMIT {limit}
    """)


# ── All-Rounders ───────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _allrounder_scatter(season_range=DEFAULT_SEASON_RANGE, min_runs=500, min_wickets=30):
    season_filter = _season_condition("season", season_range)
    min_runs = _sanitize_minimum(min_runs, 500, 1)
    min_wickets = _sanitize_minimum(min_wickets, 30, 1)
    return query(f"""
        WITH bat AS (
            SELECT batter AS player,
                   SUM(runs)::INT              AS total_runs,
                   COUNT(DISTINCT match_id)::INT AS bat_matches
            FROM player_batting
            WHERE {season_filter}
            GROUP BY batter
            HAVING SUM(runs) >= {min_runs}
        ),
        bowl AS (
            SELECT bowler AS player,
                   SUM(wickets)::INT             AS total_wickets,
                   COUNT(DISTINCT match_id)::INT AS bowl_matches
            FROM player_bowling
            WHERE {season_filter}
            GROUP BY bowler
            HAVING SUM(wickets) >= {min_wickets}
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
def _most_potm(season_range=DEFAULT_SEASON_RANGE, team=None, limit=15):
    season_filter = _season_condition("season", season_range)
    tf = f"AND (team1 = '{team}' OR team2 = '{team}')" if team else ""
    limit = _sanitize_limit(limit, 15)
    return query(f"""
        SELECT player_of_match AS player, COUNT(*)::INT AS awards
        FROM matches
        WHERE {season_filter}
          AND player_of_match IS NOT NULL {tf}
        GROUP BY player_of_match
        ORDER BY awards DESC
        LIMIT {limit}
    """)


# ── Miscellaneous ──────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _expensive_overs(season_range=DEFAULT_SEASON_RANGE, team=None, limit=20):
    season_filter = _season_condition("b.season", season_range)
    tf = f"AND b.bowling_team = '{team}'" if team else ""
    limit = _sanitize_limit(limit, 20)
    return query(f"""
        SELECT b.bowler,
               b.batting_team                              AS vs_team,
               b.over                                      AS over_num,
               b.innings,
               SUM(b.runs_bowler)::INT                     AS runs_conceded,
               COUNT(CASE WHEN b.is_four THEN 1 END)::INT  AS fours,
               COUNT(CASE WHEN b.is_six  THEN 1 END)::INT  AS sixes,
               b.season,
               m.venue
        FROM balls b
        JOIN matches m ON b.match_id = m.match_id
        WHERE {season_filter} {tf}
        GROUP BY b.match_id, b.innings, b.over, b.bowler,
                 b.batting_team, b.bowling_team, b.season, m.venue
        ORDER BY runs_conceded DESC
        LIMIT {limit}
    """)


# ═══════════════════════════════════════════════════════════════════════
#  TAB CONTENT
# ═══════════════════════════════════════════════════════════════════════

# Get team list for team filter control
teams_df = query("SELECT DISTINCT team FROM team_season ORDER BY team")
team_options = ["All Teams"] + teams_df["team"].tolist()

tab_bat, tab_bowl, tab_team, tab_ar, tab_misc = st.tabs(
    ["Batting", "Bowling", "Teams", "All-Rounders", "Miscellaneous"]
)

# ── BATTING TAB ────────────────────────────────────────────────────────
with tab_bat:

    # --- Most Career Runs ---
    spec = _visual_spec(
        "career_runs",
        "Most Career Runs",
        default_limit=15,
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df = _career_runs(
        season_range=controls.get("season_range"),
        team=team_val,
        limit=controls.get("limit"),
    )
    if not df.empty:
        fig = styled_bar(
            df.sort_values("total_runs"), x="batter", y="total_runs",
            title="Top Run Scorers", horizontal=True, height=500,
        )
        st.plotly_chart(fig, width='stretch')

        display = df.rename(columns={
            "batter": "Player", "total_runs": "Runs", "innings": "Inn",
            "avg": "Avg", "sr": "SR", "hundreds": "100s",
            "fifties": "50s", "fours": "4s", "sixes": "6s",
        })[["Player", "Runs", "Inn", "Avg", "SR", "100s", "50s", "4s", "6s"]]
        st.dataframe(display, width='stretch', hide_index=True)
    else:
        st.info(spec.empty_state_help)

    st.divider()

    # --- Centuries & Fifties ---
    c1, c2 = st.columns(2)
    with c1:
        spec = _visual_spec(
            "most_centuries",
            "Most Centuries",
            default_limit=10,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_c = _most_centuries(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
        )
        if not df_c.empty:
            fig = styled_bar(df_c, x="batter", y="hundreds", title="Most 100s")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info(spec.empty_state_help)

    with c2:
        spec = _visual_spec(
            "most_fifties",
            "Most Fifties",
            default_limit=10,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_f = _most_fifties(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
        )
        if not df_f.empty:
            fig = styled_bar(df_f, x="batter", y="fifties", title="Most 50s")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info(spec.empty_state_help)

    st.divider()

    # --- Highest Individual Scores ---
    spec = _visual_spec(
        "highest_scores",
        "Highest Individual Scores",
        default_limit=20,
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_hs = _highest_scores(
        season_range=controls.get("season_range"),
        team=team_val,
        limit=controls.get("limit"),
    )
    if not df_hs.empty:
        st.dataframe(
            df_hs.rename(columns={
                "batter": "Player", "score": "Score", "balls_faced": "Balls",
                "fours": "4s", "sixes": "6s", "sr": "SR",
                "vs_team": "Vs", "venue": "Venue", "season": "Season",
            }),
            width='stretch', hide_index=True,
        )
    else:
        st.info(spec.empty_state_help)

    st.divider()

    # --- Best Average & SR ---
    c1, c2 = st.columns(2)
    with c1:
        spec = _visual_spec(
            "best_batting_avg",
            "Best Batting Average",
            default_limit=15,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
                number_control("min_innings", "Min innings", 30, 1, 100, help_text="Minimum innings to qualify"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_ba = _best_batting_avg(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
            min_innings=controls.get("min_innings"),
        )
        if not df_ba.empty:
            st.dataframe(
                df_ba.rename(columns={
                    "batter": "Player", "innings": "Inn", "total_runs": "Runs",
                    "dismissals": "Outs", "avg": "Avg", "sr": "SR",
                })[["Player", "Inn", "Runs", "Outs", "Avg", "SR"]],
                width='stretch', hide_index=True,
            )
        else:
            st.info(spec.empty_state_help)

    with c2:
        spec = _visual_spec(
            "best_batting_sr",
            "Best Strike Rate",
            default_limit=15,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
                number_control("min_balls", "Min balls", 500, 100, 2000, step=50, help_text="Minimum balls to qualify"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_bsr = _best_batting_sr(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
            min_balls=controls.get("min_balls"),
        )
        if not df_bsr.empty:
            st.dataframe(
                df_bsr.rename(columns={
                    "batter": "Player", "total_balls": "Balls", "total_runs": "Runs",
                    "innings": "Inn", "sr": "SR", "avg": "Avg",
                })[["Player", "Balls", "Runs", "Inn", "SR", "Avg"]],
                width='stretch', hide_index=True,
            )
        else:
            st.info(spec.empty_state_help)

    st.divider()

    # --- Average × SR Scatter ---
    spec = _visual_spec(
        "avg_sr_scatter",
        "Average × Strike Rate",
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
            number_control("min_balls", "Min balls", 500, 100, 2000, step=50, help_text="Minimum balls to qualify"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_as = _avg_sr_scatter(
        season_range=controls.get("season_range"),
        team=team_val,
        min_balls=controls.get("min_balls"),
    )
    if not df_as.empty:
        fig = styled_scatter(
            df_as, x="avg", y="sr",
            title="Batting Quality Index",
            size="total_runs", hover_name="batter", height=550,
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info(spec.empty_state_help)

    st.divider()

    # --- Sixes & Fours ---
    c1, c2 = st.columns(2)
    with c1:
        spec = _visual_spec(
            "most_sixes",
            "Most Career Sixes",
            default_limit=15,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_6 = _most_sixes(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
        )
        if not df_6.empty:
            fig = styled_bar(
                df_6.sort_values("total_sixes"), x="batter", y="total_sixes",
                title="Top Six Hitters", horizontal=True,
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info(spec.empty_state_help)

    with c2:
        spec = _visual_spec(
            "most_fours",
            "Most Career Fours",
            default_limit=15,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_4 = _most_fours(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
        )
        if not df_4.empty:
            fig = styled_bar(
                df_4.sort_values("total_fours"), x="batter", y="total_fours",
                title="Top Four Hitters", horizontal=True,
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info(spec.empty_state_help)

    st.divider()

    # --- Most Ducks ---
    spec = _visual_spec(
        "most_ducks",
        "Most Ducks",
        default_limit=10,
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_d = _most_ducks(
        season_range=controls.get("season_range"),
        team=team_val,
        limit=controls.get("limit"),
    )
    if not df_d.empty:
        fig = styled_bar(df_d, x="batter", y="ducks", title="Most Ducks")
        st.plotly_chart(fig, width='stretch')
    else:
        st.info(spec.empty_state_help)


# ── BOWLING TAB ────────────────────────────────────────────────────────
with tab_bowl:

    # --- Most Career Wickets ---
    spec = _visual_spec(
        "career_wickets",
        "Most Career Wickets",
        default_limit=15,
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_w = _career_wickets(
        season_range=controls.get("season_range"),
        team=team_val,
        limit=controls.get("limit"),
    )
    if not df_w.empty:
        fig = styled_bar(
            df_w.sort_values("total_wickets"), x="bowler", y="total_wickets",
            title="Top Wicket Takers", horizontal=True, height=500,
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
        st.info(spec.empty_state_help)

    st.divider()

    # --- Best Bowling Figures ---
    spec = _visual_spec(
        "best_bowling_figures",
        "Best Bowling Figures",
        default_limit=15,
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_bf = _best_bowling_figures(
        season_range=controls.get("season_range"),
        team=team_val,
        limit=controls.get("limit"),
    )
    if not df_bf.empty:
        st.dataframe(
            df_bf.rename(columns={
                "bowler": "Bowler", "figures": "Figures",
                "vs_team": "Vs", "venue": "Venue", "season": "Season",
            })[["Bowler", "Figures", "Vs", "Venue", "Season"]],
            width='stretch', hide_index=True,
        )
    else:
        st.info(spec.empty_state_help)

    st.divider()

    # --- Economy & Average ---
    c1, c2 = st.columns(2)
    with c1:
        spec = _visual_spec(
            "best_economy",
            "Best Economy",
            default_limit=15,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
                number_control("min_balls", "Min balls", 300, 100, 1000, step=50, help_text="Minimum balls to qualify"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_be = _best_economy(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
            min_balls=controls.get("min_balls"),
        )
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
        else:
            st.info(spec.empty_state_help)

    with c2:
        spec = _visual_spec(
            "best_bowling_avg",
            "Best Bowling Average",
            default_limit=15,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
                number_control("min_wickets", "Min wickets", 30, 1, 100, help_text="Minimum wickets to qualify"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_bba = _best_bowling_avg(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
            min_wickets=controls.get("min_wickets"),
        )
        if not df_bba.empty:
            st.dataframe(
                df_bba.rename(columns={
                    "bowler": "Bowler", "total_wickets": "Wkts",
                    "total_runs": "Runs", "matches": "Mat", "avg": "Avg",
                })[["Bowler", "Mat", "Wkts", "Runs", "Avg"]],
                width='stretch', hide_index=True,
            )
        else:
            st.info(spec.empty_state_help)

    st.divider()

    # --- Bowling Strike Rate ---
    spec = _visual_spec(
        "best_bowling_sr",
        "Best Bowling Strike Rate",
        default_limit=15,
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
            number_control("min_wickets", "Min wickets", 30, 1, 100, help_text="Minimum wickets to qualify"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_bbs = _best_bowling_sr(
        season_range=controls.get("season_range"),
        team=team_val,
        limit=controls.get("limit"),
        min_wickets=controls.get("min_wickets"),
    )
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
    else:
        st.info(spec.empty_state_help)

    st.divider()

    # --- Maidens & Dots ---
    c1, c2 = st.columns(2)
    with c1:
        spec = _visual_spec(
            "most_maidens",
            "Most Maiden Overs",
            default_limit=10,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_m = _most_maidens(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
        )
        if not df_m.empty:
            fig = styled_bar(df_m, x="bowler", y="total_maidens",
                             title="Top Maiden Bowlers")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info(spec.empty_state_help)

    with c2:
        spec = _visual_spec(
            "most_dot_balls",
            "Most Dot Balls Bowled",
            default_limit=15,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_dt = _most_dot_balls(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
        )
        if not df_dt.empty:
            fig = styled_bar(df_dt, x="bowler", y="total_dots",
                             title="Top Dot Ball Bowlers")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info(spec.empty_state_help)



# ── TEAM TAB ───────────────────────────────────────────────────────────
with tab_team:

    # --- Win Percentage ---
    spec = _visual_spec(
        "team_win_pct",
        "Win Percentage — All Teams",
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_wp = _team_win_pct(
        season_range=controls.get("season_range"),
        team=team_val,
    )
    if not df_wp.empty:
        color_map = {t: get_team_color(t) for t in df_wp["team"]}
        fig = styled_bar(
            df_wp.sort_values("win_pct"), x="team", y="win_pct",
            title="Team Win %", color="team", color_map=color_map,
            horizontal=True, height=550,
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info(spec.empty_state_help)

    st.divider()

    # --- IPL Titles ---
    spec = _visual_spec(
        "ipl_titles",
        "Most IPL Titles",
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    df_t = _ipl_titles(season_range=controls.get("season_range"))
    if not df_t.empty:
        color_map = {t: get_team_color(t) for t in df_t["team"]}
        fig = styled_bar(
            df_t, x="team", y="titles", title="IPL Championships",
            color="team", color_map=color_map,
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info(spec.empty_state_help)

    st.divider()

    # --- Highest & Lowest Totals ---
    c1, c2 = st.columns(2)
    with c1:
        spec = _visual_spec(
            "highest_totals",
            "Highest Team Totals",
            default_limit=15,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_ht = _highest_totals(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
        )
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
        else:
            st.info(spec.empty_state_help)

    with c2:
        spec = _visual_spec(
            "lowest_totals",
            "Lowest Team Totals",
            default_limit=15,
            extra_controls=[
                select_control("team", "Team (optional)", team_options, "All Teams"),
            ],
        )
        st.subheader(spec.title)
        controls = render_visual_controls(spec)
        render_active_filters(active_control_chips(spec, controls))
        team_val = None if controls.get("team") == "All Teams" else controls.get("team")
        df_lt = _lowest_totals(
            season_range=controls.get("season_range"),
            team=team_val,
            limit=controls.get("limit"),
        )
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
        else:
            st.info(spec.empty_state_help)

    st.divider()

    # --- Highest Successful Chases ---
    spec = _visual_spec(
        "highest_chases",
        "Highest Successful Chases",
        default_limit=10,
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_hc = _highest_chases(
        season_range=controls.get("season_range"),
        team=team_val,
        limit=controls.get("limit"),
    )
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
    else:
        st.info(spec.empty_state_help)


# ── ALL-ROUNDER TAB ───────────────────────────────────────────────────
with tab_ar:

    # --- Scatter ---
    spec = _visual_spec(
        "allrounder_scatter",
        "All-Rounder Impact",
        extra_controls=[
            number_control("min_runs", "Min runs", 500, 100, 2000, step=100, help_text="Minimum runs to qualify"),
            number_control("min_wickets", "Min wickets", 30, 10, 100, help_text="Minimum wickets to qualify"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    df_ar = _allrounder_scatter(
        season_range=controls.get("season_range"),
        min_runs=controls.get("min_runs"),
        min_wickets=controls.get("min_wickets"),
    )
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
        st.info(spec.empty_state_help)

    st.divider()

    # --- POTM ---
    spec = _visual_spec(
        "most_potm",
        "Most Player of the Match Awards",
        default_limit=15,
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_potm = _most_potm(
        season_range=controls.get("season_range"),
        team=team_val,
        limit=controls.get("limit"),
    )
    if not df_potm.empty:
        fig = styled_bar(df_potm, x="player", y="awards",
                         title="Top POTM Winners")
        st.plotly_chart(fig, width='stretch')
    else:
        st.info(spec.empty_state_help)


# ── MISCELLANEOUS TAB ─────────────────────────────────────────────────
with tab_misc:

    spec = _visual_spec(
        "expensive_overs",
        "Most Expensive Overs",
        default_limit=20,
        extra_controls=[
            select_control("team", "Team (optional)", team_options, "All Teams"),
        ],
    )
    st.subheader(spec.title)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    team_val = None if controls.get("team") == "All Teams" else controls.get("team")
    df_eo = _expensive_overs(
        season_range=controls.get("season_range"),
        team=team_val,
        limit=controls.get("limit"),
    )
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
        st.info(spec.empty_state_help)
