"""
Pressure & Momentum — Dot ball cascades, chase dynamics, clutch performances.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.db.connection import query
from src.utils.constants import ALL_SEASONS, PHASE_COLORS
from src.utils.control_renderer import active_control_chips, render_visual_controls
from src.utils.control_schema import VisualSpec
from src.utils.formatters import format_strike_rate
from src.utils.visual_specs import limit_control, number_control, season_range_control
from src.visualizations.card_renderer import render_active_filters, render_bar_chart, render_dataframe
from src.visualizations.theme import IPL_COLORWAY, apply_ipl_style, big_number_style, styled_line

st.title("Pressure & Momentum")
st.markdown(big_number_style(), unsafe_allow_html=True)

DEFAULT_SEASON_RANGE = (min(ALL_SEASONS), max(ALL_SEASONS))

# Outcome colors for dot sequence charts
OUTCOME_COLORS = {
    "boundary": "#FF6B6B",
    "scoring_shot": "#4ECDC4",
    "wicket": "#FFEAA7",
    "other": "#AED6F1",
}


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS
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
    return max(1, int(default if limit is None else limit))


def _sanitize_minimum(value: int | None, default: int, minimum: int = 1) -> int:
    return max(minimum, int(default if value is None else value))


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


def _render_visual(spec: VisualSpec, fetcher):
    st.markdown(f"#### {spec.title}")
    if spec.description:
        st.caption(spec.description)
    controls = render_visual_controls(spec)
    render_active_filters(active_control_chips(spec, controls))
    return controls, fetcher(controls)


def _render_display_dataframe(
    spec: VisualSpec,
    df: pd.DataFrame,
    column_map: dict[str, str],
    *,
    strike_rate_columns: list[str] | None = None,
) -> None:
    if df.empty:
        render_dataframe(df, spec.empty_state_help)
        return

    display_df = df[list(column_map.keys())].copy()
    display_df.columns = list(column_map.values())

    for column in strike_rate_columns or []:
        if column in display_df.columns:
            display_df[column] = display_df[column].apply(
                lambda value: format_strike_rate(value) if pd.notna(value) else "—"
            )

    render_dataframe(display_df, spec.empty_state_help)


# ═══════════════════════════════════════════════════════════════════════
#  CACHED QUERY HELPERS
# ═══════════════════════════════════════════════════════════════════════

# ── DOT BALL PRESSURE ─────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _dot_cascade(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
) -> pd.DataFrame:
    """Stacked outcome distribution after N consecutive dots."""
    season_filter = _season_condition("season", season_range)
    return query(
        f"""
        SELECT consecutive_dots_before          AS dots,
               dot_sequence_outcome             AS outcome,
               COUNT(*)::INT                    AS cnt
        FROM   balls
        WHERE  is_sequence_breaker = true
               AND {season_filter}
        GROUP  BY dots, outcome
        ORDER  BY dots, outcome
        """
    )


@st.cache_data(ttl=3600)
def _dismissal_prob_after_dots(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    min_balls: int = 100,
) -> pd.DataFrame:
    """Wicket probability after N consecutive dots."""
    season_filter = _season_condition("season", season_range)
    min_balls = _sanitize_minimum(min_balls, 100)
    return query(
        f"""
        SELECT consecutive_dots_before          AS dots,
               COUNT(*)::INT                    AS total_balls,
               SUM(CASE WHEN wicket_kind NOT IN ('not_out', 'retired hurt')
                    THEN 1 ELSE 0 END)::INT     AS wickets,
               ROUND(SUM(CASE WHEN wicket_kind NOT IN ('not_out', 'retired hurt')
                           THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 2)  AS wicket_pct
        FROM   balls
        WHERE  {season_filter}
               AND valid_ball = true
        GROUP  BY dots
        HAVING total_balls >= {min_balls}
        ORDER  BY dots
        """
    )


@st.cache_data(ttl=3600)
def _team_dot_resilience(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    min_pressure_dots: int = 3,
    min_pressure_balls: int = 50,
    limit: int = 20,
) -> pd.DataFrame:
    """Per-team outcomes after pressure dot streaks."""
    season_filter = _season_condition("season", season_range)
    min_pressure_dots = _sanitize_minimum(min_pressure_dots, 3)
    min_pressure_balls = _sanitize_minimum(min_pressure_balls, 50)
    limit = _sanitize_limit(limit, 20)
    return query(
        f"""
        SELECT batting_team                     AS team,
               COUNT(*)::INT                    AS pressure_balls,
               ROUND(SUM(CASE WHEN dot_sequence_outcome = 'boundary'
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS boundary_pct,
               ROUND(SUM(CASE WHEN dot_sequence_outcome = 'wicket'
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS wicket_pct,
               ROUND(SUM(CASE WHEN dot_sequence_outcome = 'scoring_shot'
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS scoring_pct
        FROM   balls
        WHERE  is_sequence_breaker = true
               AND consecutive_dots_before >= {min_pressure_dots}
               AND {season_filter}
        GROUP  BY team
        HAVING pressure_balls >= {min_pressure_balls}
        ORDER  BY boundary_pct DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _dot_ball_creators(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_balls: int = 300,
) -> pd.DataFrame:
    """Top bowlers by dot balls bowled."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_balls = _sanitize_minimum(min_balls, 300)
    return query(
        f"""
        SELECT bowler,
               SUM(CASE WHEN is_dot THEN 1 ELSE 0 END)::INT    AS total_dots,
               COUNT(*)::INT                                   AS total_balls,
               ROUND(SUM(CASE WHEN is_dot THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)                 AS dot_pct,
               ROUND(AVG(CASE WHEN is_dot THEN consecutive_dots_before + 1
                              ELSE NULL END), 2)               AS avg_consec_dots
        FROM   balls
        WHERE  valid_ball = true
               AND {season_filter}
        GROUP  BY bowler
        HAVING total_balls >= {min_balls}
        ORDER  BY total_dots DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _top_dot_ball_victims(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_balls: int = 300,
) -> pd.DataFrame:
    """Batters who face the most dot balls."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_balls = _sanitize_minimum(min_balls, 300)
    return query(
        f"""
        SELECT batter,
               SUM(dots_faced)::INT                           AS total_dots,
               SUM(balls)::INT                                AS total_balls,
               ROUND(SUM(dots_faced) * 100.0
                     / NULLIF(SUM(balls), 0), 1)              AS dot_pct,
               SUM(runs)::INT                                 AS runs,
               ROUND(SUM(runs) * 100.0
                     / NULLIF(SUM(balls), 0), 1)              AS strike_rate
        FROM   player_batting
        WHERE  {season_filter}
        GROUP  BY batter
        HAVING total_balls >= {min_balls}
        ORDER  BY total_dots DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _best_dot_ball_avoiders(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_balls: int = 500,
) -> pd.DataFrame:
    """Batters with the lowest dot ball percentage."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_balls = _sanitize_minimum(min_balls, 500)
    return query(
        f"""
        SELECT batter,
               SUM(dots_faced)::INT                           AS total_dots,
               SUM(balls)::INT                                AS total_balls,
               ROUND(SUM(dots_faced) * 100.0
                     / NULLIF(SUM(balls), 0), 1)              AS dot_pct,
               SUM(runs)::INT                                 AS runs,
               ROUND(SUM(runs) * 100.0
                     / NULLIF(SUM(balls), 0), 1)              AS strike_rate
        FROM   player_batting
        WHERE  {season_filter}
        GROUP  BY batter
        HAVING total_balls >= {min_balls}
        ORDER  BY dot_pct ASC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _phase_dot_pct(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
) -> pd.DataFrame:
    """Dot ball percentage by match phase."""
    season_filter = _season_condition("season", season_range)
    return query(
        f"""
        SELECT match_phase                      AS phase,
               COUNT(*)::INT                    AS total_balls,
               SUM(CASE WHEN is_dot THEN 1 ELSE 0 END)::INT AS dots,
               ROUND(SUM(CASE WHEN is_dot THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS dot_pct
        FROM   balls
        WHERE  valid_ball = true
               AND match_phase IS NOT NULL
               AND {season_filter}
        GROUP  BY phase
        ORDER  BY CASE phase
                    WHEN 'powerplay' THEN 1
                    WHEN 'middle'    THEN 2
                    WHEN 'death'     THEN 3
                  END
        """
    )


# ── CHASE DYNAMICS ────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _chase_success_by_target(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
) -> pd.DataFrame:
    """Chase win % by target run buckets."""
    season_filter = _season_condition("season", season_range)
    return query(
        f"""
        WITH chase AS (
            SELECT match_id,
                   team1_score + 1                              AS target,
                   CASE WHEN batting_first_won = false THEN 1 ELSE 0 END AS chase_won
            FROM   matches
            WHERE  {season_filter}
                   AND team1_score IS NOT NULL
                   AND team2_score IS NOT NULL
                   AND result_type = 'normal'
        )
        SELECT CASE
                 WHEN target <= 120 THEN '100-120'
                 WHEN target <= 140 THEN '121-140'
                 WHEN target <= 160 THEN '141-160'
                 WHEN target <= 180 THEN '161-180'
                 WHEN target <= 200 THEN '181-200'
                 ELSE '201+'
               END                                              AS target_range,
               COUNT(*)::INT                                    AS matches,
               SUM(chase_won)::INT                              AS chase_wins,
               ROUND(SUM(chase_won) * 100.0
                     / NULLIF(COUNT(*), 0), 1)                  AS chase_win_pct
        FROM   chase
        GROUP  BY target_range
        ORDER  BY MIN(target)
        """
    )


@st.cache_data(ttl=3600)
def _chase_success_by_season(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
) -> pd.DataFrame:
    """Season-wise chase win %."""
    season_filter = _season_condition("season", season_range)
    return query(
        f"""
        SELECT season,
               COUNT(*)::INT                                    AS matches,
               SUM(CASE WHEN batting_first_won = false
                    THEN 1 ELSE 0 END)::INT                     AS chase_wins,
               ROUND(SUM(CASE WHEN batting_first_won = false
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)                  AS chase_win_pct
        FROM   matches
        WHERE  {season_filter}
               AND team1_score IS NOT NULL
               AND team2_score IS NOT NULL
               AND result_type = 'normal'
        GROUP  BY season
        ORDER  BY season
        """
    )


@st.cache_data(ttl=3600)
def _highest_successful_chases(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    """Highest successful chases."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT match_won_by                     AS team,
               team1_score + 1                  AS target,
               team2_score::INT                 AS score,
               season,
               venue,
               CAST(win_margin_value AS INT)    AS margin_wickets
        FROM   matches
        WHERE  {season_filter}
               AND batting_first_won = false
               AND win_margin_type = 'wickets'
               AND result_type = 'normal'
        ORDER  BY target DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _lowest_totals_defended(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
) -> pd.DataFrame:
    """Lowest totals successfully defended."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT team1                            AS defending_team,
               team1_score::INT                 AS total_defended,
               team2                            AS chasing_team,
               team2_score::INT                 AS chaser_score,
               season,
               venue,
               CAST(win_margin_value AS INT)    AS margin_runs
        FROM   matches
        WHERE  {season_filter}
               AND batting_first_won = true
               AND win_margin_type = 'runs'
               AND result_type = 'normal'
        ORDER  BY total_defended ASC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _best_chase_innings(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_runs: int = 30,
) -> pd.DataFrame:
    """Individual batting performances in successful chases."""
    season_filter_balls = _season_condition("b.season", season_range)
    min_runs = _sanitize_minimum(min_runs, 30)
    limit = _sanitize_limit(limit, 15)
    return query(
        f"""
        SELECT b.batter,
               SUM(b.runs_batter)::INT                         AS runs,
               SUM(CASE WHEN b.valid_ball THEN 1 ELSE 0 END)::INT AS balls,
               ROUND(SUM(b.runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN b.valid_ball
                                  THEN 1 ELSE 0 END), 0), 1)   AS sr,
               (m.team1_score + 1)::INT                         AS target,
               b.season,
               b.batting_team                                   AS team
        FROM   balls b
        JOIN   matches m ON b.match_id = m.match_id
        WHERE  b.innings = 2
               AND {season_filter_balls}
               AND m.batting_first_won = false
               AND b.batting_team = m.match_won_by
               AND m.result_type = 'normal'
        GROUP  BY b.match_id, b.batter, b.season, b.batting_team,
                  m.team1_score
        HAVING runs >= {min_runs}
        ORDER  BY runs DESC, sr DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _teams_best_at_chasing(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_chase_matches: int = 10,
) -> pd.DataFrame:
    """Team chase records."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_chase_matches = _sanitize_minimum(min_chase_matches, 10)
    return query(
        f"""
        SELECT team2                            AS team,
               COUNT(*)::INT                    AS chase_matches,
               SUM(CASE WHEN batting_first_won = false
                    THEN 1 ELSE 0 END)::INT     AS chase_wins,
               ROUND(SUM(CASE WHEN batting_first_won = false
                          THEN 1 ELSE 0 END) * 100.0
                     / NULLIF(COUNT(*), 0), 1)  AS chase_win_pct,
               ROUND(AVG(CASE WHEN batting_first_won = false
                               AND win_margin_type = 'wickets'
                          THEN win_margin_value
                          ELSE NULL END), 1)    AS avg_chase_margin_wkts
        FROM   matches
        WHERE  {season_filter}
               AND team1_score IS NOT NULL
               AND team2_score IS NOT NULL
               AND result_type = 'normal'
        GROUP  BY team
        HAVING chase_matches >= {min_chase_matches}
        ORDER  BY chase_win_pct DESC
        LIMIT  {limit}
        """
    )


# ── PARTNERSHIPS UNDER PRESSURE ───────────────────────────────────────

@st.cache_data(ttl=3600)
def _partnership_rr_by_wicket(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    min_balls: int = 6,
) -> pd.DataFrame:
    """Average partnership run rate by wicket number."""
    season_filter = _season_condition("season", season_range)
    min_balls = _sanitize_minimum(min_balls, 6)
    return query(
        f"""
        SELECT wicket_number,
               ROUND(AVG(run_rate), 2)          AS avg_rr,
               COUNT(*)::INT                    AS partnerships
        FROM   partnerships
        WHERE  {season_filter}
               AND wicket_number BETWEEN 1 AND 10
               AND balls >= {min_balls}
        GROUP  BY wicket_number
        ORDER  BY wicket_number
        """
    )


@st.cache_data(ttl=3600)
def _recovery_partnerships(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 20,
    min_runs: int = 50,
    min_wickets_down: int = 3,
) -> pd.DataFrame:
    """Run-heavy recovery partnerships from pressure starts."""
    season_filter = _season_condition("p.season", season_range)
    limit = _sanitize_limit(limit, 20)
    min_runs = _sanitize_minimum(min_runs, 50)
    min_wickets_down = _sanitize_minimum(min_wickets_down, 3)
    return query(
        f"""
        SELECT p.batting_partners,
               p.runs::INT                      AS runs,
               p.balls::INT                     AS balls,
               ROUND(p.run_rate, 2)             AS rr,
               p.batting_team                   AS team,
               p.season,
               p.team_wicket_at_start::INT      AS wkts_down
        FROM   partnerships p
        WHERE  {season_filter}
               AND p.runs >= {min_runs}
               AND p.team_wicket_at_start >= {min_wickets_down}
               AND p.wicket_number <= 6
        ORDER  BY p.runs DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _biggest_partnerships(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 20,
) -> pd.DataFrame:
    """Top partnerships by runs."""
    season_filter = _season_condition("p.season", season_range)
    limit = _sanitize_limit(limit, 20)
    return query(
        f"""
        SELECT p.batting_partners,
               p.runs::INT                      AS runs,
               p.balls::INT                     AS balls,
               ROUND(p.run_rate, 2)             AS rr,
               p.batting_team                   AS team,
               p.season,
               p.boundaries::INT                AS boundaries
        FROM   partnerships p
        WHERE  {season_filter}
        ORDER  BY p.runs DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _most_impactful_partnerships(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 20,
    min_balls: int = 12,
) -> pd.DataFrame:
    """Partnerships ranked by runs × run rate."""
    season_filter = _season_condition("p.season", season_range)
    limit = _sanitize_limit(limit, 20)
    min_balls = _sanitize_minimum(min_balls, 12)
    return query(
        f"""
        SELECT p.batting_partners,
               p.runs::INT                      AS runs,
               p.balls::INT                     AS balls,
               ROUND(p.run_rate, 2)             AS rr,
               ROUND(p.runs * p.run_rate, 1)    AS impact_score,
               p.batting_team                   AS team,
               p.season
        FROM   partnerships p
        WHERE  {season_filter}
               AND p.balls >= {min_balls}
        ORDER  BY impact_score DESC
        LIMIT  {limit}
        """
    )


# ── CLUTCH PERFORMANCES ──────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _close_match_heroes(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_matches: int = 10,
) -> pd.DataFrame:
    """Players with the best average runs in close matches."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_matches = _sanitize_minimum(min_matches, 10)
    return query(
        f"""
        SELECT batter,
               COUNT(DISTINCT match_id)::INT    AS matches,
               SUM(runs_batter)::INT            AS total_runs,
               ROUND(SUM(runs_batter) * 1.0
                     / NULLIF(COUNT(DISTINCT match_id), 0), 2) AS avg_runs,
               ROUND(SUM(runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball
                                  THEN 1 ELSE 0 END), 0), 1)   AS sr
        FROM   balls
        WHERE  is_close_match = true
               AND {season_filter}
        GROUP  BY batter
        HAVING matches >= {min_matches}
        ORDER  BY avg_runs DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _playoff_performance(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_runs: int = 50,
) -> pd.DataFrame:
    """Top players by runs in playoffs."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_runs = _sanitize_minimum(min_runs, 50)
    return query(
        f"""
        SELECT batter,
               COUNT(DISTINCT match_id)::INT    AS matches,
               SUM(runs_batter)::INT            AS total_runs,
               ROUND(SUM(runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball
                                  THEN 1 ELSE 0 END), 0), 1)   AS sr,
               SUM(CASE WHEN is_four THEN 1 ELSE 0 END)::INT    AS fours,
               SUM(CASE WHEN is_six  THEN 1 ELSE 0 END)::INT    AS sixes
        FROM   balls
        WHERE  stage != 'League'
               AND stage IS NOT NULL
               AND {season_filter}
        GROUP  BY batter
        HAVING total_runs >= {min_runs}
        ORDER  BY total_runs DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _final_heroes(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = len(ALL_SEASONS),
) -> pd.DataFrame:
    """Player of the Match awards in finals."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, len(ALL_SEASONS))
    return query(
        f"""
        SELECT player_of_match                  AS player,
               match_won_by                     AS winning_team,
               season,
               team1_score::INT                 AS team1_score,
               team2_score::INT                 AS team2_score,
               venue
        FROM   matches
        WHERE  stage = 'Final'
               AND {season_filter}
               AND player_of_match IS NOT NULL
        ORDER  BY season DESC
        LIMIT  {limit}
        """
    )


@st.cache_data(ttl=3600)
def _death_over_pressure_batting(
    season_range: tuple[int, int] = DEFAULT_SEASON_RANGE,
    limit: int = 15,
    min_balls: int = 60,
) -> pd.DataFrame:
    """Strike rate leaders in death overs of close matches."""
    season_filter = _season_condition("season", season_range)
    limit = _sanitize_limit(limit, 15)
    min_balls = _sanitize_minimum(min_balls, 60)
    return query(
        f"""
        SELECT batter,
               COUNT(DISTINCT match_id)::INT    AS matches,
               SUM(CASE WHEN valid_ball THEN 1 ELSE 0 END)::INT AS balls,
               SUM(runs_batter)::INT            AS runs,
               ROUND(SUM(runs_batter) * 100.0
                     / NULLIF(SUM(CASE WHEN valid_ball
                                  THEN 1 ELSE 0 END), 0), 1)   AS sr,
               SUM(CASE WHEN is_six THEN 1 ELSE 0 END)::INT     AS sixes
        FROM   balls
        WHERE  match_phase = 'death'
               AND is_close_match = true
               AND {season_filter}
        GROUP  BY batter
        HAVING balls >= {min_balls}
        ORDER  BY sr DESC
        LIMIT  {limit}
        """
    )


# ═══════════════════════════════════════════════════════════════════════
#  VISUAL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

VISUAL_SPECS = {
    "dot_cascade": _visual_spec(
        "dot_cascade",
        "Dot Ball Cascade",
        description="Outcome mix after a dot-ball streak ends.",
        extra_controls=[
            number_control(
                "max_dots_bucket",
                "Maximum dots bucket",
                default=6,
                minimum=2,
                maximum=12,
                help_text="All streaks at or above this value are grouped into one final bucket.",
            )
        ],
        empty_state_help="No dot-sequence breaker data found for the selected filters.",
    ),
    "dismissal_prob_after_dots": _visual_spec(
        "dismissal_prob_after_dots",
        "Dismissal Probability After N Dots",
        extra_controls=[
            number_control(
                "min_balls",
                "Minimum sample balls",
                default=100,
                minimum=1,
                maximum=1000,
                help_text="Defaults to the current 100-ball sample filter.",
            )
        ],
    ),
    "team_dot_resilience": _visual_spec(
        "team_dot_resilience",
        "Team Dot Ball Resilience",
        description="How teams respond when a dot-ball streak reaches pressure level.",
        default_limit=20,
        extra_controls=[
            number_control(
                "min_pressure_dots",
                "Minimum dots before pressure",
                default=3,
                minimum=1,
                maximum=10,
                help_text="Defaults to the current 3-dot pressure definition.",
            ),
            number_control(
                "min_pressure_balls",
                "Minimum pressure balls",
                default=50,
                minimum=1,
                maximum=500,
                help_text="Defaults to the current 50-ball qualification rule.",
            ),
        ],
    ),
    "dot_ball_creators": _visual_spec(
        "dot_ball_creators",
        "Top Dot Ball Creators",
        default_limit=15,
        extra_controls=[
            number_control(
                "min_balls",
                "Minimum balls bowled",
                default=300,
                minimum=1,
                maximum=2000,
                help_text="Defaults to the current 300-ball qualification rule.",
            )
        ],
    ),
    "phase_dot_pct": _visual_spec(
        "phase_dot_pct",
        "Dot Ball % by Match Phase",
    ),
    "top_dot_ball_victims": _visual_spec(
        "top_dot_ball_victims",
        "Most Dot Balls Faced",
        default_limit=15,
        extra_controls=[
            number_control(
                "min_balls",
                "Minimum balls faced",
                default=300,
                minimum=1,
                maximum=3000,
                help_text="Defaults to the current 300-ball qualification rule.",
            )
        ],
    ),
    "best_dot_ball_avoiders": _visual_spec(
        "best_dot_ball_avoiders",
        "Best Dot Ball Avoidance",
        description="Lowest dot-ball share among qualified batters.",
        default_limit=15,
        extra_controls=[
            number_control(
                "min_balls",
                "Minimum balls faced",
                default=500,
                minimum=1,
                maximum=3000,
                help_text="Defaults to the current 500-ball qualification rule.",
            )
        ],
    ),
    "chase_success_by_target": _visual_spec(
        "chase_success_by_target",
        "Chase Success Rate by Target Range",
    ),
    "chase_success_by_season": _visual_spec(
        "chase_success_by_season",
        "Chase Success Rate Over Seasons",
    ),
    "highest_successful_chases": _visual_spec(
        "highest_successful_chases",
        "Highest Successful Chases",
        default_limit=15,
    ),
    "lowest_totals_defended": _visual_spec(
        "lowest_totals_defended",
        "Lowest Totals Defended",
        default_limit=15,
    ),
    "best_chase_innings": _visual_spec(
        "best_chase_innings",
        "Best Individual Chase Innings",
        default_limit=15,
        extra_controls=[
            number_control(
                "min_runs",
                "Minimum runs",
                default=30,
                minimum=1,
                maximum=150,
                help_text="Defaults to the current 30-run qualification rule.",
            )
        ],
    ),
    "teams_best_at_chasing": _visual_spec(
        "teams_best_at_chasing",
        "Teams Best at Chasing",
        default_limit=15,
        extra_controls=[
            number_control(
                "min_chase_matches",
                "Minimum chase matches",
                default=10,
                minimum=1,
                maximum=100,
                help_text="Defaults to the current 10-match qualification rule.",
            )
        ],
    ),
    "partnership_rr_by_wicket": _visual_spec(
        "partnership_rr_by_wicket",
        "Average Partnership Run Rate by Wicket Number",
        extra_controls=[
            number_control(
                "min_balls",
                "Minimum partnership balls",
                default=6,
                minimum=1,
                maximum=120,
                help_text="Defaults to the current 6-ball partnership filter.",
            )
        ],
    ),
    "recovery_partnerships": _visual_spec(
        "recovery_partnerships",
        "Recovery Partnerships",
        description="Partnerships of at least the chosen runs from teams already this many wickets down.",
        default_limit=20,
        extra_controls=[
            number_control(
                "min_runs",
                "Minimum partnership runs",
                default=50,
                minimum=1,
                maximum=200,
                help_text="Defaults to the current 50-run recovery cutoff.",
            ),
            number_control(
                "min_wickets_down",
                "Minimum wickets down at start",
                default=3,
                minimum=1,
                maximum=9,
                help_text="Defaults to the current 3-wickets-down recovery cutoff.",
            ),
        ],
        empty_state_help="No recovery partnerships found for the selected filters.",
    ),
    "biggest_partnerships": _visual_spec(
        "biggest_partnerships",
        "Biggest Partnerships",
        default_limit=20,
    ),
    "most_impactful_partnerships": _visual_spec(
        "most_impactful_partnerships",
        "Most Impactful Partnerships",
        default_limit=20,
        extra_controls=[
            number_control(
                "min_balls",
                "Minimum partnership balls",
                default=12,
                minimum=1,
                maximum=120,
                help_text="Defaults to the current 12-ball impact filter.",
            )
        ],
    ),
    "close_match_heroes": _visual_spec(
        "close_match_heroes",
        "Close Match Heroes",
        description="Average runs per close match.",
        default_limit=15,
        extra_controls=[
            number_control(
                "min_matches",
                "Minimum close matches",
                default=10,
                minimum=1,
                maximum=100,
                help_text="Defaults to the current 10-match qualification rule.",
            )
        ],
    ),
    "playoff_performance": _visual_spec(
        "playoff_performance",
        "Playoff Run Scorers",
        default_limit=15,
        extra_controls=[
            number_control(
                "min_runs",
                "Minimum playoff runs",
                default=50,
                minimum=1,
                maximum=500,
                help_text="Defaults to the current 50-run qualification rule.",
            )
        ],
    ),
    "final_heroes": _visual_spec(
        "final_heroes",
        "Final — Player of the Match",
        default_limit=len(ALL_SEASONS),
    ),
    "death_over_pressure_batting": _visual_spec(
        "death_over_pressure_batting",
        "Death Over Batting Under Pressure",
        description="Close-match death-over strike rates.",
        default_limit=15,
        extra_controls=[
            number_control(
                "min_balls",
                "Minimum death-over balls",
                default=60,
                minimum=1,
                maximum=500,
                help_text="Defaults to the current 60-ball qualification rule.",
            )
        ],
    ),
}


# ═══════════════════════════════════════════════════════════════════════
#  PAGE LAYOUT — TABS
# ═══════════════════════════════════════════════════════════════════════

tab_dots, tab_chase, tab_partner, tab_clutch = st.tabs([
    "Dot Ball Pressure",
    "Chase Dynamics",
    "Partnerships Under Pressure",
    "Clutch Performances",
])


# ── TAB 1: DOT BALL PRESSURE ─────────────────────────────────────────
with tab_dots:
    st.header("Dot Ball Pressure Analysis")

    dot_cascade_spec = VISUAL_SPECS["dot_cascade"]
    dot_cascade_controls, cascade_df = _render_visual(
        dot_cascade_spec,
        lambda controls: _dot_cascade(controls["season_range"]),
    )
    if not cascade_df.empty:
        max_dots_bucket = _sanitize_minimum(dot_cascade_controls["max_dots_bucket"], 6)
        cascade_chart_df = cascade_df.copy()
        cascade_chart_df["dots"] = cascade_chart_df["dots"].clip(upper=max_dots_bucket)
        cascade_chart_df = cascade_chart_df.groupby(["dots", "outcome"], as_index=False)["cnt"].sum()
        cascade_chart_df["dots_label"] = cascade_chart_df["dots"].apply(
            lambda dots: f"{max_dots_bucket}+" if dots == max_dots_bucket else str(dots)
        )
        fig_cascade = px.bar(
            cascade_chart_df,
            x="dots_label",
            y="cnt",
            color="outcome",
            title="Dot Ball Cascade — What Happens After N Consecutive Dots?",
            color_discrete_map=OUTCOME_COLORS,
            barmode="stack",
            labels={"dots_label": "Consecutive Dots Before", "cnt": "Count"},
        )
        fig_cascade = apply_ipl_style(fig_cascade, height=480)
        st.plotly_chart(fig_cascade, width="stretch")
    else:
        st.info(dot_cascade_spec.empty_state_help)

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        dismissal_spec = VISUAL_SPECS["dismissal_prob_after_dots"]
        _, prob_df = _render_visual(
            dismissal_spec,
            lambda controls: _dismissal_prob_after_dots(
                controls["season_range"],
                controls["min_balls"],
            ),
        )
        _render_display_dataframe(
            dismissal_spec,
            prob_df,
            {
                "dots": "Consecutive Dots",
                "total_balls": "Total Balls",
                "wickets": "Wickets",
                "wicket_pct": "Wicket %",
            },
        )

    with col_b:
        resilience_spec = VISUAL_SPECS["team_dot_resilience"]
        _, resil_df = _render_visual(
            resilience_spec,
            lambda controls: _team_dot_resilience(
                controls["season_range"],
                controls["min_pressure_dots"],
                controls["min_pressure_balls"],
                controls["limit"],
            ),
        )
        _render_display_dataframe(
            resilience_spec,
            resil_df,
            {
                "team": "Team",
                "pressure_balls": "Pressure Balls",
                "boundary_pct": "Boundary %",
                "wicket_pct": "Wicket %",
                "scoring_pct": "Scoring Shot %",
            },
        )

    st.divider()

    col_c, col_d = st.columns(2)
    with col_c:
        creators_spec = VISUAL_SPECS["dot_ball_creators"]
        _, creators_df = _render_visual(
            creators_spec,
            lambda controls: _dot_ball_creators(
                controls["season_range"],
                controls["limit"],
                controls["min_balls"],
            ),
        )
        _render_display_dataframe(
            creators_spec,
            creators_df,
            {
                "bowler": "Bowler",
                "total_dots": "Dot Balls",
                "total_balls": "Total Balls",
                "dot_pct": "Dot %",
                "avg_consec_dots": "Avg Consec Dots",
            },
        )

    with col_d:
        phase_spec = VISUAL_SPECS["phase_dot_pct"]
        _, phase_df = _render_visual(
            phase_spec,
            lambda controls: _phase_dot_pct(controls["season_range"]),
        )
        if not phase_df.empty:
            phase_chart_df = phase_df.copy()
            phase_chart_df["phase_label"] = phase_chart_df["phase"].str.capitalize()
            phase_colors = [PHASE_COLORS.get(phase, "#888888") for phase in phase_chart_df["phase"]]
            fig_phase = go.Figure(
                go.Bar(
                    x=phase_chart_df["phase_label"],
                    y=phase_chart_df["dot_pct"],
                    marker_color=phase_colors,
                    text=phase_chart_df["dot_pct"].apply(lambda value: f"{value}%"),
                    textposition="outside",
                )
            )
            fig_phase.update_layout(
                title="Dot Ball % — Powerplay vs Middle vs Death",
                yaxis_title="Dot %",
                xaxis_title="Phase",
            )
            fig_phase = apply_ipl_style(fig_phase, height=400, show_legend=False)
            st.plotly_chart(fig_phase, width="stretch")
        else:
            st.info(phase_spec.empty_state_help)

    st.divider()
    st.subheader("Top Dot Ball Players")
    st.caption("Batters who face the most dots and those who avoid them best.")

    col_e, col_f = st.columns(2)
    with col_e:
        victims_spec = VISUAL_SPECS["top_dot_ball_victims"]
        _, victims_df = _render_visual(
            victims_spec,
            lambda controls: _top_dot_ball_victims(
                controls["season_range"],
                controls["limit"],
                controls["min_balls"],
            ),
        )
        _render_display_dataframe(
            victims_spec,
            victims_df,
            {
                "batter": "Batter",
                "total_dots": "Dots Faced",
                "total_balls": "Balls",
                "dot_pct": "Dot %",
                "runs": "Runs",
                "strike_rate": "SR",
            },
            strike_rate_columns=["SR"],
        )
        render_bar_chart(
            victims_df,
            x="batter",
            y="total_dots",
            title=f"Top {len(victims_df)} — Most Dot Balls Faced",
            height=450,
        )

    with col_f:
        avoiders_spec = VISUAL_SPECS["best_dot_ball_avoiders"]
        _, avoiders_df = _render_visual(
            avoiders_spec,
            lambda controls: _best_dot_ball_avoiders(
                controls["season_range"],
                controls["limit"],
                controls["min_balls"],
            ),
        )
        _render_display_dataframe(
            avoiders_spec,
            avoiders_df,
            {
                "batter": "Batter",
                "total_dots": "Dots Faced",
                "total_balls": "Balls",
                "dot_pct": "Dot %",
                "runs": "Runs",
                "strike_rate": "SR",
            },
            strike_rate_columns=["SR"],
        )
        render_bar_chart(
            avoiders_df,
            x="batter",
            y="dot_pct",
            title=f"Top {len(avoiders_df)} — Lowest Dot Ball %",
            height=450,
        )


# ── TAB 2: CHASE DYNAMICS ────────────────────────────────────────────
with tab_chase:
    st.header("Chase Dynamics")

    chase_target_spec = VISUAL_SPECS["chase_success_by_target"]
    _, chase_target_df = _render_visual(
        chase_target_spec,
        lambda controls: _chase_success_by_target(controls["season_range"]),
    )
    if not chase_target_df.empty:
        fig_chase = go.Figure(
            go.Bar(
                x=chase_target_df["target_range"],
                y=chase_target_df["chase_win_pct"],
                marker_color=IPL_COLORWAY[: len(chase_target_df)],
                text=chase_target_df.apply(
                    lambda row: f"{row['chase_win_pct']}%<br>({row['chase_wins']}/{row['matches']})",
                    axis=1,
                ),
                textposition="outside",
            )
        )
        fig_chase.update_layout(
            title="Chase Success Rate by Target Range",
            xaxis_title="Target Runs",
            yaxis_title="Chase Win %",
            yaxis_range=[0, 100],
        )
        fig_chase = apply_ipl_style(fig_chase, height=450, show_legend=False)
        st.plotly_chart(fig_chase, width="stretch")
    else:
        st.info(chase_target_spec.empty_state_help)

    st.divider()

    chase_season_spec = VISUAL_SPECS["chase_success_by_season"]
    _, chase_season_df = _render_visual(
        chase_season_spec,
        lambda controls: _chase_success_by_season(controls["season_range"]),
    )
    if not chase_season_df.empty:
        fig_season = styled_line(
            chase_season_df,
            x="season",
            y="chase_win_pct",
            title="Chase Success Rate Over Seasons",
        )
        fig_season.update_layout(
            yaxis_title="Chase Win %",
            xaxis_title="Season",
            yaxis_range=[0, 100],
        )
        st.plotly_chart(fig_season, width="stretch")
    else:
        st.info(chase_season_spec.empty_state_help)

    st.divider()

    col_g, col_h = st.columns(2)
    with col_g:
        high_chase_spec = VISUAL_SPECS["highest_successful_chases"]
        _, high_chase_df = _render_visual(
            high_chase_spec,
            lambda controls: _highest_successful_chases(
                controls["season_range"],
                controls["limit"],
            ),
        )
        _render_display_dataframe(
            high_chase_spec,
            high_chase_df,
            {
                "team": "Team",
                "target": "Target",
                "score": "Score",
                "season": "Season",
                "venue": "Venue",
                "margin_wickets": "Margin (wkts)",
            },
        )

    with col_h:
        low_defend_spec = VISUAL_SPECS["lowest_totals_defended"]
        _, low_defend_df = _render_visual(
            low_defend_spec,
            lambda controls: _lowest_totals_defended(
                controls["season_range"],
                controls["limit"],
            ),
        )
        _render_display_dataframe(
            low_defend_spec,
            low_defend_df,
            {
                "defending_team": "Defending Team",
                "total_defended": "Total",
                "chasing_team": "Chasing Team",
                "chaser_score": "Chaser Score",
                "season": "Season",
                "venue": "Venue",
                "margin_runs": "Margin (runs)",
            },
        )

    st.divider()

    col_i, col_j = st.columns(2)
    with col_i:
        best_chase_spec = VISUAL_SPECS["best_chase_innings"]
        _, best_chase_df = _render_visual(
            best_chase_spec,
            lambda controls: _best_chase_innings(
                controls["season_range"],
                controls["limit"],
                controls["min_runs"],
            ),
        )
        _render_display_dataframe(
            best_chase_spec,
            best_chase_df,
            {
                "batter": "Batter",
                "runs": "Runs",
                "balls": "Balls",
                "sr": "SR",
                "target": "Target",
                "season": "Season",
                "team": "Team",
            },
            strike_rate_columns=["SR"],
        )

    with col_j:
        team_chase_spec = VISUAL_SPECS["teams_best_at_chasing"]
        _, team_chase_df = _render_visual(
            team_chase_spec,
            lambda controls: _teams_best_at_chasing(
                controls["season_range"],
                controls["limit"],
                controls["min_chase_matches"],
            ),
        )
        _render_display_dataframe(
            team_chase_spec,
            team_chase_df,
            {
                "team": "Team",
                "chase_matches": "Chase Matches",
                "chase_wins": "Wins",
                "chase_win_pct": "Chase Win %",
                "avg_chase_margin_wkts": "Avg Margin (wkts)",
            },
        )


# ── TAB 3: PARTNERSHIPS UNDER PRESSURE ───────────────────────────────
with tab_partner:
    st.header("Partnerships Under Pressure")

    rr_spec = VISUAL_SPECS["partnership_rr_by_wicket"]
    _, rr_wkt_df = _render_visual(
        rr_spec,
        lambda controls: _partnership_rr_by_wicket(
            controls["season_range"],
            controls["min_balls"],
        ),
    )
    if not rr_wkt_df.empty:
        fig_rr = go.Figure(
            go.Scatter(
                x=rr_wkt_df["wicket_number"],
                y=rr_wkt_df["avg_rr"],
                mode="lines+markers+text",
                text=rr_wkt_df["avg_rr"].apply(lambda value: f"{value:.2f}"),
                textposition="top center",
                line=dict(color=IPL_COLORWAY[0], width=3),
                marker=dict(size=10),
            )
        )
        fig_rr.update_layout(
            title="Average Partnership Run Rate by Wicket Number",
            xaxis_title="Wicket Number",
            yaxis_title="Avg Run Rate",
            xaxis=dict(dtick=1),
        )
        fig_rr = apply_ipl_style(fig_rr, height=420, show_legend=False)
        st.plotly_chart(fig_rr, width="stretch")
    else:
        st.info(rr_spec.empty_state_help)

    st.divider()

    recovery_spec = VISUAL_SPECS["recovery_partnerships"]
    _, recovery_df = _render_visual(
        recovery_spec,
        lambda controls: _recovery_partnerships(
            controls["season_range"],
            controls["limit"],
            controls["min_runs"],
            controls["min_wickets_down"],
        ),
    )
    _render_display_dataframe(
        recovery_spec,
        recovery_df,
        {
            "batting_partners": "Partners",
            "runs": "Runs",
            "balls": "Balls",
            "rr": "RR",
            "team": "Team",
            "season": "Season",
            "wkts_down": "Wickets Down",
        },
    )

    st.divider()

    col_k, col_l = st.columns(2)
    with col_k:
        biggest_spec = VISUAL_SPECS["biggest_partnerships"]
        _, big_df = _render_visual(
            biggest_spec,
            lambda controls: _biggest_partnerships(
                controls["season_range"],
                controls["limit"],
            ),
        )
        _render_display_dataframe(
            biggest_spec,
            big_df,
            {
                "batting_partners": "Partners",
                "runs": "Runs",
                "balls": "Balls",
                "rr": "RR",
                "boundaries": "Boundaries",
                "team": "Team",
                "season": "Season",
            },
        )

    with col_l:
        impact_spec = VISUAL_SPECS["most_impactful_partnerships"]
        _, impact_df = _render_visual(
            impact_spec,
            lambda controls: _most_impactful_partnerships(
                controls["season_range"],
                controls["limit"],
                controls["min_balls"],
            ),
        )
        _render_display_dataframe(
            impact_spec,
            impact_df,
            {
                "batting_partners": "Partners",
                "runs": "Runs",
                "balls": "Balls",
                "rr": "RR",
                "impact_score": "Impact Score",
                "team": "Team",
                "season": "Season",
            },
        )


# ── TAB 4: CLUTCH PERFORMANCES ───────────────────────────────────────
with tab_clutch:
    st.header("Clutch Performances")

    col_m, col_n = st.columns(2)
    with col_m:
        heroes_spec = VISUAL_SPECS["close_match_heroes"]
        _, heroes_df = _render_visual(
            heroes_spec,
            lambda controls: _close_match_heroes(
                controls["season_range"],
                controls["limit"],
                controls["min_matches"],
            ),
        )
        _render_display_dataframe(
            heroes_spec,
            heroes_df,
            {
                "batter": "Batter",
                "matches": "Matches",
                "total_runs": "Total Runs",
                "avg_runs": "Avg Runs/Match",
                "sr": "SR",
            },
            strike_rate_columns=["SR"],
        )

    with col_n:
        playoff_spec = VISUAL_SPECS["playoff_performance"]
        _, playoff_df = _render_visual(
            playoff_spec,
            lambda controls: _playoff_performance(
                controls["season_range"],
                controls["limit"],
                controls["min_runs"],
            ),
        )
        _render_display_dataframe(
            playoff_spec,
            playoff_df,
            {
                "batter": "Batter",
                "matches": "Matches",
                "total_runs": "Runs",
                "sr": "SR",
                "fours": "4s",
                "sixes": "6s",
            },
            strike_rate_columns=["SR"],
        )

    st.divider()

    col_o, col_p = st.columns(2)
    with col_o:
        final_spec = VISUAL_SPECS["final_heroes"]
        _, final_df = _render_visual(
            final_spec,
            lambda controls: _final_heroes(
                controls["season_range"],
                controls["limit"],
            ),
        )
        _render_display_dataframe(
            final_spec,
            final_df,
            {
                "player": "Player",
                "winning_team": "Winning Team",
                "season": "Season",
                "team1_score": "1st Inn Score",
                "team2_score": "2nd Inn Score",
                "venue": "Venue",
            },
        )

    with col_p:
        death_spec = VISUAL_SPECS["death_over_pressure_batting"]
        _, death_df = _render_visual(
            death_spec,
            lambda controls: _death_over_pressure_batting(
                controls["season_range"],
                controls["limit"],
                controls["min_balls"],
            ),
        )
        _render_display_dataframe(
            death_spec,
            death_df,
            {
                "batter": "Batter",
                "matches": "Matches",
                "balls": "Balls",
                "runs": "Runs",
                "sr": "SR",
                "sixes": "6s",
            },
            strike_rate_columns=["SR"],
        )
