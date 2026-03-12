"""
Explorer — The ultimate IPL analytics power-tool.
Build dynamic queries across all IPL datasets with 9 entity types,
40+ one-click presets, interactive filters, auto-generated charts,
and a comprehensive user guide.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from src.db.connection import query
from src.visualizations.theme import apply_ipl_style, IPL_COLORWAY, big_number_style
from src.utils.constants import ALL_SEASONS
from src.utils.formatters import format_number

# ─── Page Config ────────────────────────────────────────────────────────
st.markdown(big_number_style(), unsafe_allow_html=True)

# ─── Cached helpers ─────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def run_query(sql: str, params: list | None = None) -> pd.DataFrame:
    return query(sql, params)

@st.cache_data(ttl=3600)
def get_all_batters() -> list[str]:
    df = query("SELECT DISTINCT batter FROM player_batting ORDER BY batter")
    return df["batter"].tolist()

@st.cache_data(ttl=3600)
def get_all_bowlers() -> list[str]:
    df = query("SELECT DISTINCT bowler FROM player_bowling ORDER BY bowler")
    return df["bowler"].tolist()

@st.cache_data(ttl=3600)
def get_all_teams() -> list[str]:
    df = query(
        "SELECT DISTINCT team FROM ("
        "  SELECT DISTINCT batting_team AS team FROM player_batting"
        "  UNION"
        "  SELECT DISTINCT bowling_team AS team FROM player_bowling"
        ") ORDER BY team"
    )
    return df["team"].tolist()

@st.cache_data(ttl=3600)
def get_all_venues() -> list[str]:
    df = query("SELECT DISTINCT venue FROM matches ORDER BY venue")
    return df["venue"].tolist()

@st.cache_data(ttl=3600)
def get_all_cities() -> list[str]:
    try:
        df = query("SELECT DISTINCT city FROM balls WHERE city IS NOT NULL ORDER BY city")
        return df["city"].tolist()
    except Exception:
        return []

@st.cache_data(ttl=3600)
def get_all_stages() -> list[str]:
    df = query("SELECT DISTINCT stage FROM matches WHERE stage IS NOT NULL ORDER BY stage")
    return df["stage"].tolist()

@st.cache_data(ttl=3600)
def get_view_columns(view_name: str) -> pd.DataFrame:
    df = query(f"SELECT * FROM {view_name} LIMIT 0")
    return pd.DataFrame({
        "Column": df.columns,
        "Type": [str(df[c].dtype) for c in df.columns],
    })

@st.cache_data(ttl=3600)
def get_view_sample(view_name: str) -> pd.DataFrame:
    return query(f"SELECT * FROM {view_name} LIMIT 5")


# ═══════════════════════════════════════════════════════════════════════
#  PRESET QUERIES — 40+ organized by category
# ═══════════════════════════════════════════════════════════════════════

PRESET_CATEGORIES: dict[str, dict[str, dict]] = {
    "Batting Legends": {
        "Top 15 All-Time Run Scorers": {
            "sql": """
                SELECT batter AS Player, SUM(runs) AS Runs, SUM(balls) AS Balls,
                       COUNT(*) AS Innings, SUM(fours) AS '4s', SUM(sixes) AS '6s',
                       ROUND(SUM(runs)*100.0/NULLIF(SUM(balls),0),2) AS SR,
                       ROUND(SUM(runs)*1.0/NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0),2) AS Avg
                FROM player_batting GROUP BY batter ORDER BY Runs DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Runs",
        },
        "Highest Strike Rates (min 1500 balls)": {
            "sql": """
                SELECT batter AS Player, SUM(runs) AS Runs, SUM(balls) AS Balls,
                       ROUND(SUM(runs)*100.0/NULLIF(SUM(balls),0),2) AS SR,
                       SUM(sixes) AS '6s', SUM(fours) AS '4s'
                FROM player_batting GROUP BY batter
                HAVING SUM(balls) >= 1500 ORDER BY SR DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "SR",
        },
        "Best Batting Averages (min 50 inn)": {
            "sql": """
                SELECT batter AS Player, SUM(runs) AS Runs, COUNT(*) AS Innings,
                       SUM(CASE WHEN was_out THEN 1 ELSE 0 END) AS Outs,
                       ROUND(SUM(runs)*1.0/NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0),2) AS Average,
                       ROUND(SUM(runs)*100.0/NULLIF(SUM(balls),0),2) AS SR
                FROM player_batting GROUP BY batter
                HAVING COUNT(*) >= 50 ORDER BY Average DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Average",
        },
        "Most Centuries": {
            "sql": """
                SELECT batter AS Player,
                       SUM(CASE WHEN runs >= 100 THEN 1 ELSE 0 END) AS Centuries,
                       SUM(CASE WHEN runs >= 50 AND runs < 100 THEN 1 ELSE 0 END) AS Fifties,
                       SUM(runs) AS Total_Runs, COUNT(*) AS Innings
                FROM player_batting GROUP BY batter
                HAVING SUM(CASE WHEN runs >= 100 THEN 1 ELSE 0 END) >= 1
                ORDER BY Centuries DESC, Fifties DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Centuries",
        },
        "Most Half-Centuries": {
            "sql": """
                SELECT batter AS Player,
                       SUM(CASE WHEN runs >= 50 THEN 1 ELSE 0 END) AS '50+_Scores',
                       SUM(CASE WHEN runs >= 50 AND runs < 100 THEN 1 ELSE 0 END) AS Fifties,
                       SUM(CASE WHEN runs >= 100 THEN 1 ELSE 0 END) AS Centuries,
                       SUM(runs) AS Total_Runs
                FROM player_batting GROUP BY batter
                ORDER BY "50+_Scores" DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "50+_Scores",
        },
        "Most Sixes (All-Time)": {
            "sql": """
                SELECT batter AS Player, SUM(sixes) AS Total_Sixes,
                       SUM(runs) AS Runs, SUM(balls) AS Balls,
                       ROUND(SUM(sixes)*1.0/COUNT(*),2) AS Sixes_Per_Inn
                FROM player_batting GROUP BY batter ORDER BY Total_Sixes DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Total_Sixes",
        },
        "Most Fours (All-Time)": {
            "sql": """
                SELECT batter AS Player, SUM(fours) AS Total_Fours,
                       SUM(runs) AS Runs, SUM(balls) AS Balls,
                       ROUND(SUM(fours)*1.0/COUNT(*),2) AS Fours_Per_Inn
                FROM player_batting GROUP BY batter ORDER BY Total_Fours DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Total_Fours",
        },
        "Highest Individual Scores": {
            "sql": """
                SELECT batter AS Player, runs AS Score, balls AS Balls,
                       fours AS '4s', sixes AS '6s',
                       ROUND(runs*100.0/NULLIF(balls,0),2) AS SR,
                       batting_team AS Team, season AS Season, venue AS Venue
                FROM player_batting ORDER BY runs DESC LIMIT 20
            """, "chart": "bar", "x": "Player", "y": "Score",
        },
        "1000+ Runs & 100+ Sixes Club": {
            "sql": """
                SELECT batter AS Player, SUM(runs) AS Runs, SUM(sixes) AS Sixes,
                       SUM(balls) AS Balls,
                       ROUND(SUM(runs)*100.0/NULLIF(SUM(balls),0),2) AS SR
                FROM player_batting GROUP BY batter
                HAVING SUM(runs) >= 1000 AND SUM(sixes) >= 100
                ORDER BY Sixes DESC
            """, "chart": "bar", "x": "Player", "y": "Sixes",
        },
    },
    "Bowling Masters": {
        "Top 15 All-Time Wicket Takers": {
            "sql": """
                SELECT bowler AS Bowler, SUM(wickets) AS Wickets,
                       SUM(balls_bowled) AS Balls, SUM(runs_conceded) AS Runs,
                       ROUND(SUM(runs_conceded)*6.0/NULLIF(SUM(balls_bowled),0),2) AS Economy,
                       ROUND(SUM(balls_bowled)*1.0/NULLIF(SUM(wickets),0),2) AS SR
                FROM player_bowling GROUP BY bowler ORDER BY Wickets DESC LIMIT 15
            """, "chart": "bar", "x": "Bowler", "y": "Wickets",
        },
        "Best Economy Rates (min 1000 balls)": {
            "sql": """
                SELECT bowler AS Bowler, SUM(balls_bowled) AS Balls,
                       SUM(runs_conceded) AS Runs, SUM(wickets) AS Wickets,
                       ROUND(SUM(runs_conceded)*6.0/NULLIF(SUM(balls_bowled),0),2) AS Economy
                FROM player_bowling GROUP BY bowler
                HAVING SUM(balls_bowled) >= 1000 ORDER BY Economy ASC LIMIT 15
            """, "chart": "bar", "x": "Bowler", "y": "Economy",
        },
        "Best Bowling Strike Rates (min 50 wkts)": {
            "sql": """
                SELECT bowler AS Bowler, SUM(wickets) AS Wickets,
                       SUM(balls_bowled) AS Balls,
                       ROUND(SUM(balls_bowled)*1.0/NULLIF(SUM(wickets),0),2) AS Bowling_SR,
                       ROUND(SUM(runs_conceded)*6.0/NULLIF(SUM(balls_bowled),0),2) AS Economy
                FROM player_bowling GROUP BY bowler
                HAVING SUM(wickets) >= 50 ORDER BY Bowling_SR ASC LIMIT 15
            """, "chart": "bar", "x": "Bowler", "y": "Bowling_SR",
        },
        "Best Death Over Bowlers (min 200 balls)": {
            "sql": """
                SELECT b.bowler AS Bowler, COUNT(*) AS Balls,
                       SUM(b.runs_batter + b.runs_extras) AS Runs,
                       SUM(CASE WHEN b.player_out IS NOT NULL THEN 1 ELSE 0 END) AS Wickets,
                       ROUND(SUM(b.runs_batter + b.runs_extras)*6.0/COUNT(*),2) AS Economy
                FROM balls b
                WHERE b.match_phase = 'death' AND b.valid_ball = true
                GROUP BY b.bowler HAVING COUNT(*) >= 200
                ORDER BY Economy ASC LIMIT 15
            """, "chart": "bar", "x": "Bowler", "y": "Economy",
        },
        "Best Powerplay Bowlers (min 200 balls)": {
            "sql": """
                SELECT b.bowler AS Bowler, COUNT(*) AS Balls,
                       SUM(b.runs_batter + b.runs_extras) AS Runs,
                       SUM(CASE WHEN b.player_out IS NOT NULL THEN 1 ELSE 0 END) AS Wickets,
                       ROUND(SUM(b.runs_batter + b.runs_extras)*6.0/COUNT(*),2) AS Economy
                FROM balls b
                WHERE b.match_phase = 'powerplay' AND b.valid_ball = true
                GROUP BY b.bowler HAVING COUNT(*) >= 200
                ORDER BY Economy ASC LIMIT 15
            """, "chart": "bar", "x": "Bowler", "y": "Economy",
        },
        "Most Dot Balls Bowled": {
            "sql": """
                SELECT bowler AS Bowler, SUM(dots_bowled) AS Dot_Balls,
                       SUM(balls_bowled) AS Total_Balls,
                       ROUND(SUM(dots_bowled)*100.0/NULLIF(SUM(balls_bowled),0),1) AS Dot_Pct,
                       SUM(wickets) AS Wickets
                FROM player_bowling GROUP BY bowler ORDER BY Dot_Balls DESC LIMIT 15
            """, "chart": "bar", "x": "Bowler", "y": "Dot_Balls",
        },
        "Most Maiden Overs": {
            "sql": """
                SELECT bowler AS Bowler, SUM(maidens) AS Maidens,
                       COUNT(*) AS Innings, SUM(wickets) AS Wickets,
                       ROUND(SUM(runs_conceded)*6.0/NULLIF(SUM(balls_bowled),0),2) AS Economy
                FROM player_bowling GROUP BY bowler
                HAVING SUM(maidens) >= 1 ORDER BY Maidens DESC LIMIT 15
            """, "chart": "bar", "x": "Bowler", "y": "Maidens",
        },
        "Best Single Match Bowling Figures": {
            "sql": """
                SELECT bowler AS Bowler, wickets AS Wickets,
                       runs_conceded AS Runs, balls_bowled AS Balls,
                       ROUND(runs_conceded*6.0/NULLIF(balls_bowled,0),2) AS Economy,
                       bowling_team AS Team, season AS Season, venue AS Venue
                FROM player_bowling ORDER BY wickets DESC, runs_conceded ASC LIMIT 20
            """, "chart": "bar", "x": "Bowler", "y": "Wickets",
        },
    },
    "Venue Intelligence": {
        "Highest-Scoring Venues (Avg 1st Inn)": {
            "sql": """
                SELECT venue AS Venue, COUNT(*) AS Matches,
                       ROUND(AVG(team1_score),1) AS Avg_1st_Inn,
                       ROUND(AVG(team2_score),1) AS Avg_2nd_Inn,
                       MAX(GREATEST(team1_score, team2_score)) AS Highest_Score
                FROM matches GROUP BY venue
                HAVING COUNT(*) >= 10
                ORDER BY Avg_1st_Inn DESC LIMIT 15
            """, "chart": "bar", "x": "Venue", "y": "Avg_1st_Inn",
        },
        "Best Chasing Venues (Win % batting 2nd)": {
            "sql": """
                SELECT venue AS Venue, COUNT(*) AS Matches,
                       SUM(CASE WHEN match_won_by = team2 THEN 1 ELSE 0 END) AS Chase_Wins,
                       ROUND(SUM(CASE WHEN match_won_by = team2 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS Chase_Win_Pct
                FROM matches WHERE match_won_by IS NOT NULL AND match_won_by != 'Unknown'
                GROUP BY venue HAVING COUNT(*) >= 10
                ORDER BY Chase_Win_Pct DESC LIMIT 15
            """, "chart": "bar", "x": "Venue", "y": "Chase_Win_Pct",
        },
        "Most Matches Hosted": {
            "sql": """
                SELECT venue AS Venue, COUNT(*) AS Matches,
                       MIN(season) AS First_Season, MAX(season) AS Last_Season,
                       ROUND(AVG(team1_score + team2_score),0) AS Avg_Total_Runs
                FROM matches GROUP BY venue ORDER BY Matches DESC LIMIT 20
            """, "chart": "bar", "x": "Venue", "y": "Matches",
        },
        "Venue Boundary Count (per match avg)": {
            "sql": """
                SELECT b.venue AS Venue, COUNT(DISTINCT b.match_id) AS Matches,
                       SUM(CASE WHEN b.is_four THEN 1 ELSE 0 END) AS Total_Fours,
                       SUM(CASE WHEN b.is_six THEN 1 ELSE 0 END) AS Total_Sixes,
                       ROUND(SUM(CASE WHEN b.is_boundary THEN 1 ELSE 0 END)*1.0/COUNT(DISTINCT b.match_id),1) AS Boundaries_Per_Match
                FROM balls b GROUP BY b.venue
                HAVING COUNT(DISTINCT b.match_id) >= 10
                ORDER BY Boundaries_Per_Match DESC LIMIT 15
            """, "chart": "bar", "x": "Venue", "y": "Boundaries_Per_Match",
        },
        "Toss Impact by Venue (Toss Winner Win%)": {
            "sql": """
                SELECT venue AS Venue, COUNT(*) AS Matches,
                       SUM(CASE WHEN toss_winner = match_won_by THEN 1 ELSE 0 END) AS Toss_Winner_Won,
                       ROUND(SUM(CASE WHEN toss_winner = match_won_by THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS Toss_Win_Pct
                FROM matches WHERE match_won_by IS NOT NULL AND match_won_by != 'Unknown'
                GROUP BY venue HAVING COUNT(*) >= 10
                ORDER BY Toss_Win_Pct DESC LIMIT 15
            """, "chart": "bar", "x": "Venue", "y": "Toss_Win_Pct",
        },
    },
    "Head-to-Head Matchups": {
        "Most Dominant Batter vs Bowler (min 50 balls)": {
            "sql": """
                SELECT batter AS Batter, bowler AS Bowler,
                       balls AS Balls, runs AS Runs,
                       ROUND(runs*100.0/NULLIF(balls,0),2) AS SR,
                       dismissals AS Dismissals,
                       fours AS '4s', sixes AS '6s'
                FROM matchups WHERE balls >= 50
                ORDER BY SR DESC LIMIT 20
            """, "chart": "bar", "x": "Batter", "y": "SR",
        },
        "Bowler Dominance (most dismissals of a batter)": {
            "sql": """
                SELECT bowler AS Bowler, batter AS Batter,
                       dismissals AS Dismissals, balls AS Balls,
                       runs AS Runs,
                       ROUND(runs*100.0/NULLIF(balls,0),2) AS Batter_SR
                FROM matchups WHERE dismissals >= 5
                ORDER BY Dismissals DESC, balls ASC LIMIT 20
            """, "chart": "bar", "x": "Bowler", "y": "Dismissals",
        },
        "Biggest Batter-Bowler Rivalries (most balls)": {
            "sql": """
                SELECT batter AS Batter, bowler AS Bowler,
                       balls AS Balls, runs AS Runs,
                       dismissals AS Dismissals,
                       ROUND(runs*100.0/NULLIF(balls,0),2) AS SR,
                       sixes AS '6s'
                FROM matchups ORDER BY balls DESC LIMIT 20
            """, "chart": "none", "x": "", "y": "",
        },
    },
    "Match Records": {
        "Highest Team Totals": {
            "sql": """
                SELECT season AS Season, venue AS Venue,
                       team1 AS Team1, team1_score AS T1_Score, team1_wickets AS T1_Wkts,
                       team2 AS Team2, team2_score AS T2_Score, team2_wickets AS T2_Wkts,
                       match_won_by AS Winner, stage AS Stage
                FROM matches
                ORDER BY GREATEST(team1_score, team2_score) DESC LIMIT 20
            """, "chart": "none", "x": "", "y": "",
        },
        "Lowest Team Totals (All Out or 20 overs)": {
            "sql": """
                SELECT season AS Season, venue AS Venue,
                       team1 AS Team1, team1_score AS T1_Score, team1_wickets AS T1_Wkts,
                       team2 AS Team2, team2_score AS T2_Score, team2_wickets AS T2_Wkts,
                       match_won_by AS Winner
                FROM matches
                ORDER BY LEAST(team1_score, team2_score) ASC LIMIT 20
            """, "chart": "none", "x": "", "y": "",
        },
        "Biggest Win Margins (by Runs)": {
            "sql": """
                SELECT season AS Season, venue AS Venue,
                       team1 AS Team1, team1_score AS T1_Score,
                       team2 AS Team2, team2_score AS T2_Score,
                       match_won_by AS Winner, win_margin_value AS Margin
                FROM matches WHERE win_margin_type = 'runs'
                ORDER BY win_margin_value DESC LIMIT 15
            """, "chart": "bar", "x": "Winner", "y": "Margin",
        },
        "Closest Finishes (by Wickets, 1 wkt wins)": {
            "sql": """
                SELECT season AS Season, venue AS Venue,
                       team1 AS Team1, team1_score AS T1_Score,
                       team2 AS Team2, team2_score AS T2_Score,
                       match_won_by AS Winner, win_margin_value AS Margin,
                       win_margin_type AS Type
                FROM matches WHERE win_margin_type = 'wickets' AND win_margin_value = 1
                ORDER BY season DESC
            """, "chart": "none", "x": "", "y": "",
        },
        "200+ Scores That Lost": {
            "sql": """
                SELECT m.season AS Season, m.venue AS Venue,
                       m.team1 AS Team1, m.team1_score AS T1_Score,
                       m.team2 AS Team2, m.team2_score AS T2_Score,
                       m.match_won_by AS Winner
                FROM matches m
                WHERE (m.team1_score >= 200 AND m.match_won_by = m.team2)
                   OR (m.team2_score >= 200 AND m.match_won_by = m.team1)
                ORDER BY GREATEST(m.team1_score, m.team2_score) DESC
            """, "chart": "none", "x": "", "y": "",
        },
        "Super Over Thrillers": {
            "sql": """
                SELECT m.season AS Season, m.venue AS Venue,
                       m.team1 AS Team1, m.team1_score AS T1_Score,
                       m.team2 AS Team2, m.team2_score AS T2_Score,
                       m.match_won_by AS Winner
                FROM matches m WHERE m.is_super_over_match = true
                ORDER BY m.season DESC
            """, "chart": "none", "x": "", "y": "",
        },
        "Finals — All IPL Champions": {
            "sql": """
                SELECT season AS Season, venue AS Venue,
                       team1 AS Team1, team1_score AS T1_Score,
                       team2 AS Team2, team2_score AS T2_Score,
                       match_won_by AS Champion, player_of_match AS PoM
                FROM matches WHERE stage = 'Final'
                ORDER BY season ASC
            """, "chart": "none", "x": "", "y": "",
        },
    },
    "Team Records": {
        "All-Time Team Win Percentages": {
            "sql": """
                SELECT team AS Team, SUM(matches_played) AS Matches,
                       SUM(wins) AS Wins, SUM(losses) AS Losses,
                       ROUND(SUM(wins)*100.0/NULLIF(SUM(matches_played),0),2) AS Win_Pct
                FROM team_season GROUP BY team
                HAVING SUM(matches_played) >= 20
                ORDER BY Win_Pct DESC
            """, "chart": "bar", "x": "Team", "y": "Win_Pct",
        },
        "Team Season-by-Season Wins": {
            "sql": """
                SELECT team AS Team, season AS Season,
                       matches_played AS Matches, wins AS Wins, losses AS Losses,
                       ROUND(wins*100.0/NULLIF(matches_played,0),1) AS Win_Pct
                FROM team_season ORDER BY season DESC, wins DESC
            """, "chart": "none", "x": "", "y": "",
        },
        "Most Player of Match Awards by Team": {
            "sql": """
                SELECT match_won_by AS Team, COUNT(*) AS PoM_Awards
                FROM matches WHERE player_of_match IS NOT NULL
                      AND match_won_by IS NOT NULL AND match_won_by != 'Unknown'
                GROUP BY match_won_by ORDER BY PoM_Awards DESC
            """, "chart": "bar", "x": "Team", "y": "PoM_Awards",
        },
        "Toss Decision Trends by Team": {
            "sql": """
                SELECT toss_winner AS Team,
                       SUM(CASE WHEN toss_decision='bat' THEN 1 ELSE 0 END) AS Chose_Bat,
                       SUM(CASE WHEN toss_decision='field' THEN 1 ELSE 0 END) AS Chose_Field,
                       COUNT(*) AS Tosses_Won,
                       ROUND(SUM(CASE WHEN toss_decision='field' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS Field_Pct
                FROM matches GROUP BY toss_winner
                HAVING COUNT(*) >= 20
                ORDER BY Field_Pct DESC
            """, "chart": "bar", "x": "Team", "y": "Field_Pct",
        },
    },
    "Powerplay & Death": {
        "Best Powerplay Batting (team avg runs)": {
            "sql": """
                SELECT p.batting_team AS Team,
                       COUNT(*) AS Innings,
                       ROUND(AVG(p.pp_runs),1) AS Avg_PP_Runs,
                       ROUND(AVG(p.pp_boundaries),1) AS Avg_Boundaries,
                       SUM(p.pp_wickets) AS Total_Wkts_Lost
                FROM powerplay p GROUP BY p.batting_team
                HAVING COUNT(*) >= 20
                ORDER BY Avg_PP_Runs DESC
            """, "chart": "bar", "x": "Team", "y": "Avg_PP_Runs",
        },
        "Most Expensive Overs Ever (20+ runs)": {
            "sql": """
                SELECT b.bowler AS Bowler, b.batting_team AS Batting_Team,
                       b.over+1 AS Over_No, b.season AS Season, b.venue AS Venue,
                       SUM(b.runs_batter + b.runs_extras) AS Over_Runs
                FROM balls b
                GROUP BY b.match_id, b.innings, b.over,
                         b.bowler, b.batting_team, b.season, b.venue
                HAVING SUM(b.runs_batter + b.runs_extras) >= 20
                ORDER BY Over_Runs DESC LIMIT 20
            """, "chart": "bar", "x": "Bowler", "y": "Over_Runs",
        },
        "Death Over Specialists — Batters (SR in overs 16-20)": {
            "sql": """
                SELECT b.batter AS Batter, COUNT(*) AS Balls,
                       SUM(b.runs_batter) AS Runs,
                       ROUND(SUM(b.runs_batter)*100.0/COUNT(*),2) AS SR,
                       SUM(CASE WHEN b.is_six THEN 1 ELSE 0 END) AS Sixes
                FROM balls b
                WHERE b.match_phase = 'death' AND b.valid_ball = true
                GROUP BY b.batter HAVING COUNT(*) >= 200
                ORDER BY SR DESC LIMIT 15
            """, "chart": "bar", "x": "Batter", "y": "SR",
        },
    },
    "Partnerships": {
        "Highest Partnership Stands": {
            "sql": """
                SELECT p.batting_partners AS Partners, p.runs AS Runs,
                       p.balls AS Balls, p.batting_team AS Team,
                       p.season AS Season, p.wicket_number AS Wicket
                FROM partnerships p ORDER BY p.runs DESC LIMIT 15
            """, "chart": "bar", "x": "Partners", "y": "Runs",
        },
        "Most Prolific Partnerships (total runs together)": {
            "sql": """
                SELECT p.batting_partners AS Partners,
                       SUM(p.runs) AS Total_Runs,
                       SUM(p.balls) AS Total_Balls,
                       COUNT(*) AS Times_Together,
                       ROUND(SUM(p.runs)*100.0/NULLIF(SUM(p.balls),0),2) AS SR
                FROM partnerships p GROUP BY p.batting_partners
                HAVING COUNT(*) >= 10
                ORDER BY Total_Runs DESC LIMIT 15
            """, "chart": "bar", "x": "Partners", "y": "Total_Runs",
        },
        "Fastest Partnerships (min 30 runs, best SR)": {
            "sql": """
                SELECT p.batting_partners AS Partners, p.runs AS Runs,
                       p.balls AS Balls,
                       ROUND(p.runs*100.0/NULLIF(p.balls,0),2) AS SR,
                       p.batting_team AS Team, p.season AS Season
                FROM partnerships p
                WHERE p.runs >= 30 AND p.balls >= 5
                ORDER BY SR DESC LIMIT 15
            """, "chart": "bar", "x": "Partners", "y": "SR",
        },
    },
    "Pressure & Clutch": {
        "Players for 5+ Teams": {
            "sql": """
                SELECT batter AS Player, COUNT(DISTINCT batting_team) AS Teams,
                       SUM(runs) AS Runs, LIST(DISTINCT batting_team) AS Team_List
                FROM player_batting GROUP BY batter
                HAVING COUNT(DISTINCT batting_team) >= 5
                ORDER BY Teams DESC, Runs DESC
            """, "chart": "bar", "x": "Player", "y": "Teams",
        },
        "Most Player of Match Awards": {
            "sql": """
                SELECT player_of_match AS Player, COUNT(*) AS Awards,
                       LIST(DISTINCT match_won_by) AS Teams
                FROM matches
                WHERE player_of_match IS NOT NULL
                GROUP BY player_of_match ORDER BY Awards DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Awards",
        },
        "Best in Finals & Knockouts": {
            "sql": """
                SELECT batter AS Player, SUM(runs) AS Runs,
                       SUM(balls) AS Balls, COUNT(*) AS Innings,
                       ROUND(SUM(runs)*100.0/NULLIF(SUM(balls),0),2) AS SR,
                       SUM(sixes) AS Sixes
                FROM player_batting
                WHERE season IN (SELECT DISTINCT season FROM matches WHERE stage IN ('Final','Qualifier 1','Qualifier 2','Eliminator'))
                  AND venue IN (SELECT DISTINCT venue FROM matches WHERE stage IN ('Final','Qualifier 1','Qualifier 2','Eliminator'))
                GROUP BY batter HAVING SUM(balls) >= 50
                ORDER BY Runs DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Runs",
        },
        "Close Match Performers (batting in tight wins)": {
            "sql": """
                SELECT b.batter AS Player,
                       COUNT(DISTINCT b.match_id) AS Close_Matches,
                       SUM(b.runs_batter) AS Runs,
                       SUM(CASE WHEN b.is_six THEN 1 ELSE 0 END) AS Sixes,
                       ROUND(SUM(b.runs_batter)*100.0/NULLIF(SUM(CASE WHEN b.valid_ball THEN 1 ELSE 0 END),0),2) AS SR
                FROM balls b
                WHERE b.is_close_match = true
                GROUP BY b.batter
                HAVING SUM(CASE WHEN b.valid_ball THEN 1 ELSE 0 END) >= 100
                ORDER BY Runs DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Runs",
        },
    },
    "Fun Facts & Anomalies": {
        "Most Ducks (0 runs, got out)": {
            "sql": """
                SELECT batter AS Player,
                       SUM(CASE WHEN runs = 0 AND was_out THEN 1 ELSE 0 END) AS Ducks,
                       SUM(CASE WHEN runs = 0 AND was_out AND balls <= 1 THEN 1 ELSE 0 END) AS Golden_Ducks,
                       COUNT(*) AS Innings, SUM(runs) AS Total_Runs
                FROM player_batting GROUP BY batter
                HAVING SUM(CASE WHEN runs = 0 AND was_out THEN 1 ELSE 0 END) >= 5
                ORDER BY Ducks DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Ducks",
        },
        "Dot Ball Suffocators (highest dot %)": {
            "sql": """
                SELECT bowler AS Bowler, SUM(dots_bowled) AS Dots,
                       SUM(balls_bowled) AS Balls,
                       ROUND(SUM(dots_bowled)*100.0/NULLIF(SUM(balls_bowled),0),1) AS Dot_Pct,
                       SUM(wickets) AS Wickets
                FROM player_bowling GROUP BY bowler
                HAVING SUM(balls_bowled) >= 500
                ORDER BY Dot_Pct DESC LIMIT 15
            """, "chart": "bar", "x": "Bowler", "y": "Dot_Pct",
        },
        "Boundary Hitters (highest boundary %)": {
            "sql": """
                SELECT batter AS Player, SUM(fours+sixes) AS Boundaries,
                       SUM(balls) AS Balls,
                       ROUND(SUM(fours+sixes)*100.0/NULLIF(SUM(balls),0),1) AS Boundary_Pct,
                       SUM(runs) AS Runs
                FROM player_batting GROUP BY batter
                HAVING SUM(balls) >= 500
                ORDER BY Boundary_Pct DESC LIMIT 15
            """, "chart": "bar", "x": "Player", "y": "Boundary_Pct",
        },
        "Season Orange Cap Winners (top scorer each year)": {
            "sql": """
                SELECT season AS Season, batter AS Player, SUM(runs) AS Runs,
                       SUM(balls) AS Balls,
                       ROUND(SUM(runs)*100.0/NULLIF(SUM(balls),0),2) AS SR
                FROM player_batting
                GROUP BY season, batter
                QUALIFY ROW_NUMBER() OVER (PARTITION BY season ORDER BY SUM(runs) DESC) = 1
                ORDER BY season ASC
            """, "chart": "bar", "x": "Player", "y": "Runs",
        },
        "Season Purple Cap Winners (top wicket taker each year)": {
            "sql": """
                SELECT season AS Season, bowler AS Bowler, SUM(wickets) AS Wickets,
                       SUM(runs_conceded) AS Runs,
                       ROUND(SUM(runs_conceded)*6.0/NULLIF(SUM(balls_bowled),0),2) AS Economy
                FROM player_bowling
                GROUP BY season, bowler
                QUALIFY ROW_NUMBER() OVER (PARTITION BY season ORDER BY SUM(wickets) DESC) = 1
                ORDER BY season ASC
            """, "chart": "bar", "x": "Bowler", "y": "Wickets",
        },
        "Dismissal Type Distribution (All-Time)": {
            "sql": """
                SELECT wicket_kind AS Dismissal_Type,
                       COUNT(*) AS Total,
                       ROUND(COUNT(*)*100.0/(SELECT COUNT(*) FROM balls WHERE player_out IS NOT NULL),1) AS Pct
                FROM balls WHERE player_out IS NOT NULL AND wicket_kind IS NOT NULL
                GROUP BY wicket_kind ORDER BY Total DESC
            """, "chart": "bar", "x": "Dismissal_Type", "y": "Total",
        },
    },
    "Dot Ball Analysis": {
        "Top Dot Ball Bowlers (most dots)": {
            "sql": """
                SELECT bowler AS Bowler, SUM(dots_bowled) AS Dot_Balls,
                       SUM(balls_bowled) AS Total_Balls,
                       ROUND(SUM(dots_bowled)*100.0/NULLIF(SUM(balls_bowled),0),1) AS Dot_Pct,
                       SUM(wickets) AS Wickets,
                       ROUND(SUM(runs_conceded)*6.0/NULLIF(SUM(balls_bowled),0),2) AS Economy
                FROM player_bowling GROUP BY bowler ORDER BY Dot_Balls DESC LIMIT 20
            """, "chart": "bar", "x": "Bowler", "y": "Dot_Balls",
        },
        "Dot Ball Suffocators (highest dot %)": {
            "sql": """
                SELECT bowler AS Bowler, SUM(dots_bowled) AS Dots,
                       SUM(balls_bowled) AS Balls,
                       ROUND(SUM(dots_bowled)*100.0/NULLIF(SUM(balls_bowled),0),1) AS Dot_Pct,
                       SUM(wickets) AS Wickets,
                       ROUND(SUM(runs_conceded)*6.0/NULLIF(SUM(balls_bowled),0),2) AS Economy
                FROM player_bowling GROUP BY bowler
                HAVING SUM(balls_bowled) >= 500
                ORDER BY Dot_Pct DESC LIMIT 20
            """, "chart": "bar", "x": "Bowler", "y": "Dot_Pct",
        },
        "Top Dot Ball Victims (batters facing most dots)": {
            "sql": """
                SELECT batter AS Batter, SUM(dots_faced) AS Dots_Faced,
                       SUM(balls) AS Balls,
                       ROUND(SUM(dots_faced)*100.0/NULLIF(SUM(balls),0),1) AS Dot_Pct,
                       SUM(runs) AS Runs,
                       ROUND(SUM(runs)*100.0/NULLIF(SUM(balls),0),1) AS SR
                FROM player_batting GROUP BY batter ORDER BY Dots_Faced DESC LIMIT 20
            """, "chart": "bar", "x": "Batter", "y": "Dots_Faced",
        },
        "Best Dot Ball Avoidance (lowest dot % batters, min 500 balls)": {
            "sql": """
                SELECT batter AS Batter, SUM(dots_faced) AS Dots_Faced,
                       SUM(balls) AS Balls,
                       ROUND(SUM(dots_faced)*100.0/NULLIF(SUM(balls),0),1) AS Dot_Pct,
                       SUM(runs) AS Runs,
                       ROUND(SUM(runs)*100.0/NULLIF(SUM(balls),0),1) AS SR
                FROM player_batting GROUP BY batter
                HAVING SUM(balls) >= 500
                ORDER BY Dot_Pct ASC LIMIT 20
            """, "chart": "bar", "x": "Batter", "y": "Dot_Pct",
        },
        "Dot Ball Pressure Sequences": {
            "sql": """
                SELECT consecutive_dots_before AS Consecutive_Dots,
                       dot_sequence_outcome AS Outcome,
                       count AS Total, pct AS Percentage
                FROM dot_sequences
                WHERE consecutive_dots_before >= 3
                ORDER BY consecutive_dots_before ASC, count DESC
            """, "chart": "bar", "x": "Outcome", "y": "Total",
        },
        "Dot Ball Kings by Phase": {
            "sql": """
                SELECT b.bowler AS Bowler, b.match_phase AS Phase,
                       SUM(CASE WHEN b.is_dot THEN 1 ELSE 0 END) AS Dots,
                       COUNT(*) AS Balls,
                       ROUND(SUM(CASE WHEN b.is_dot THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS Dot_Pct
                FROM balls b
                WHERE b.valid_ball = true
                GROUP BY b.bowler, b.match_phase
                HAVING COUNT(*) >= 200
                ORDER BY Dot_Pct DESC LIMIT 20
            """, "chart": "bar", "x": "Bowler", "y": "Dot_Pct",
        },
    },
}

# Flatten for backward compat
PRESET_QUERIES: dict[str, dict] = {}
for _cat, _presets in PRESET_CATEGORIES.items():
    PRESET_QUERIES.update(_presets)


# ─── View metadata for Data Dictionary ──────────────────────────────────

VIEW_DESCRIPTIONS: dict[str, str] = {
    "balls": "Ball-by-ball event log — every delivery bowled (~90 cols, ~278K rows). Granularity: one row per ball.",
    "matches": "Match-level summaries with scores, result, toss (~24 cols, ~1.2K rows). Granularity: one row per match.",
    "player_batting": "Per-match batting scorecard for each batter (~18 cols, ~17.7K rows). Granularity: one row per batter per match.",
    "player_bowling": "Per-match bowling figures for each bowler (~15 cols, ~13.9K rows). Granularity: one row per bowler per match.",
    "matchups": "Head-to-head batter vs bowler aggregated stats (~12 cols, ~29.5K rows). Granularity: one row per batter-bowler pair.",
    "venues": "Venue-level aggregate statistics (~9 cols, 42 rows). Granularity: one row per venue.",
    "partnerships": "Batting partnership data per innings (~12 cols, ~15.7K rows). Granularity: one row per partnership per innings.",
    "powerplay": "Powerplay (overs 1-6) stats per innings (~14 cols, ~2.4K rows). Granularity: one row per team per match.",
    "season_meta": "Season-level metadata — dates, champion, team count (~11 cols, 18 rows). Granularity: one row per season.",
    "team_season": "Team seasonal win/loss summary (~7 cols, 156 rows). Granularity: one row per team per season.",
    "points_table": "League standings with NRR and positions (~9 cols, 156 rows). Granularity: one row per team per season.",
    "dismissals": "Dismissal type counts per player (~3 cols, ~2.1K rows). Granularity: one row per player per dismissal type.",
    "dismissals_phase": "Dismissal types broken down by match phase (~4 cols, ~3.4K rows). Granularity: one row per player per phase per type.",
    "dot_sequences": "Consecutive dot ball sequence outcomes (~4 cols, 34 rows). Granularity: aggregate by sequence length.",
}

# ─── SQL builder functions ──────────────────────────────────────────────

def _build_batting_query(
    players: list[str], season_range: tuple[int, int], teams: list[str],
    venues: list[str], min_runs: int, min_balls: int,
    group_by: str, sort_col: str, limit: int,
) -> tuple[str, list]:
    group_map = {
        "Player": "batter",
        "Season": "season",
        "Team": "batting_team",
        "Venue": "venue",
        "Player + Season": "batter, season",
        "Player + Team": "batter, batting_team",
        "Venue + Season": "venue, season",
    }
    gb_cols = group_map.get(group_by, "batter")

    agg = (
        "SUM(runs) AS total_runs, SUM(balls) AS total_balls, "
        "COUNT(*) AS innings, "
        "SUM(fours) AS fours, SUM(sixes) AS sixes, "
        "SUM(fours + sixes) AS boundaries, "
        "SUM(CASE WHEN was_out THEN 1 ELSE 0 END) AS outs, "
        "SUM(CASE WHEN runs = 0 AND was_out THEN 1 ELSE 0 END) AS ducks, "
        "SUM(CASE WHEN runs >= 50 THEN 1 ELSE 0 END) AS fifty_plus, "
        "SUM(CASE WHEN runs >= 100 THEN 1 ELSE 0 END) AS centuries, "
        "MAX(runs) AS highest_score, "
        "ROUND(SUM(runs)*100.0/NULLIF(SUM(balls),0),2) AS strike_rate, "
        "ROUND(SUM(runs)*1.0/NULLIF(SUM(CASE WHEN was_out THEN 1 ELSE 0 END),0),2) AS average"
    )

    where_parts: list[str] = []
    params: list = []
    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if players:
        placeholders = ", ".join(["?"] * len(players))
        where_parts.append(f"batter IN ({placeholders})")
        params.extend(players)
    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"batting_team IN ({placeholders})")
        params.extend(teams)
    if venues:
        placeholders = ", ".join(["?"] * len(venues))
        where_parts.append(f"venue IN ({placeholders})")
        params.extend(venues)

    where_clause = " AND ".join(where_parts)

    having_parts: list[str] = []
    if min_runs > 0:
        having_parts.append(f"SUM(runs) >= {min_runs}")
    if min_balls > 0:
        having_parts.append(f"SUM(balls) >= {min_balls}")
    having_clause = (" HAVING " + " AND ".join(having_parts)) if having_parts else ""

    valid_sort_cols = {
        "total_runs", "total_balls", "innings", "fours", "sixes",
        "boundaries", "outs", "ducks", "fifty_plus", "centuries",
        "highest_score", "strike_rate", "average",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "total_runs"

    sql = (
        f"SELECT {gb_cols}, {agg} "
        f"FROM player_batting "
        f"WHERE {where_clause} "
        f"GROUP BY {gb_cols}"
        f"{having_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_bowling_query(
    bowlers: list[str], season_range: tuple[int, int], teams: list[str],
    venues: list[str], min_wickets: int, min_balls: int,
    group_by: str, sort_col: str, limit: int,
) -> tuple[str, list]:
    group_map = {
        "Player": "bowler",
        "Season": "season",
        "Team": "bowling_team",
        "Venue": "venue",
        "Player + Season": "bowler, season",
        "Player + Team": "bowler, bowling_team",
        "Venue + Season": "venue, season",
    }
    gb_cols = group_map.get(group_by, "bowler")

    agg = (
        "SUM(balls_bowled) AS total_balls, "
        "SUM(wickets) AS total_wickets, "
        "SUM(runs_conceded) AS runs_conceded, "
        "COUNT(*) AS innings, "
        "SUM(maidens) AS maidens, "
        "SUM(dots_bowled) AS dots, "
        "ROUND(SUM(dots_bowled)*100.0/NULLIF(SUM(balls_bowled),0),1) AS dot_pct, "
        "ROUND(SUM(runs_conceded)*6.0/NULLIF(SUM(balls_bowled),0),2) AS economy, "
        "ROUND(SUM(balls_bowled)*1.0/NULLIF(SUM(wickets),0),2) AS bowling_sr, "
        "MAX(wickets) AS best_wickets"
    )

    where_parts: list[str] = []
    params: list = []
    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if bowlers:
        placeholders = ", ".join(["?"] * len(bowlers))
        where_parts.append(f"bowler IN ({placeholders})")
        params.extend(bowlers)
    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"bowling_team IN ({placeholders})")
        params.extend(teams)
    if venues:
        placeholders = ", ".join(["?"] * len(venues))
        where_parts.append(f"venue IN ({placeholders})")
        params.extend(venues)

    where_clause = " AND ".join(where_parts)

    having_parts: list[str] = []
    if min_wickets > 0:
        having_parts.append(f"SUM(wickets) >= {min_wickets}")
    if min_balls > 0:
        having_parts.append(f"SUM(balls_bowled) >= {min_balls}")
    having_clause = (" HAVING " + " AND ".join(having_parts)) if having_parts else ""

    valid_sort_cols = {
        "total_balls", "total_wickets", "runs_conceded", "innings",
        "maidens", "dots", "dot_pct", "economy", "bowling_sr", "best_wickets",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "total_wickets"

    sql = (
        f"SELECT {gb_cols}, {agg} "
        f"FROM player_bowling "
        f"WHERE {where_clause} "
        f"GROUP BY {gb_cols}"
        f"{having_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_team_query(
    teams: list[str], season_range: tuple[int, int],
    group_by: str, sort_col: str, limit: int,
) -> tuple[str, list]:
    group_map = {
        "Team": "team",
        "Season": "season",
        "Team + Season": "team, season",
    }
    gb_cols = group_map.get(group_by, "team")

    agg = (
        "SUM(matches_played) AS matches, "
        "SUM(wins) AS wins, "
        "SUM(losses) AS losses, "
        "ROUND(SUM(wins)*100.0/NULLIF(SUM(matches_played),0),2) AS win_pct"
    )

    where_parts: list[str] = []
    params: list = []
    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"team IN ({placeholders})")
        params.extend(teams)

    where_clause = " AND ".join(where_parts)

    valid_sort_cols = {"matches", "wins", "losses", "win_pct"}
    if sort_col not in valid_sort_cols:
        sort_col = "wins"

    sql = (
        f"SELECT {gb_cols}, {agg} "
        f"FROM team_season "
        f"WHERE {where_clause} "
        f"GROUP BY {gb_cols} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_match_query(
    season_range: tuple[int, int], stages: list[str], venues: list[str],
    teams: list[str], toss_decision: str, close_only: bool,
    sort_col: str, limit: int,
) -> tuple[str, list]:
    where_parts: list[str] = []
    params: list = []
    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if stages:
        placeholders = ", ".join(["?"] * len(stages))
        where_parts.append(f"stage IN ({placeholders})")
        params.extend(stages)
    if venues:
        placeholders = ", ".join(["?"] * len(venues))
        where_parts.append(f"venue IN ({placeholders})")
        params.extend(venues)
    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"(team1 IN ({placeholders}) OR team2 IN ({placeholders}))")
        params.extend(teams)
        params.extend(teams)
    if toss_decision and toss_decision != "Any":
        where_parts.append("toss_decision = ?")
        params.append(toss_decision.lower())
    if close_only:
        where_parts.append("is_close_match = true")

    where_clause = " AND ".join(where_parts)

    valid_sort_cols = {
        "season", "date", "team1_score", "team2_score", "win_margin_value",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "date"

    sql = (
        "SELECT match_id, season, date, venue, team1, team2, "
        "team1_score, team1_wickets, team2_score, team2_wickets, "
        "match_won_by, win_margin_value, win_margin_type, stage, "
        "toss_winner, toss_decision, player_of_match "
        f"FROM matches "
        f"WHERE {where_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_ball_query(
    season_range: tuple[int, int], teams: list[str], batters: list[str],
    bowlers: list[str], phases: list[str], over_range: tuple[int, int],
    innings: str, venues: list[str], ball_types: list[str],
    dismissal_kinds: list[str],
    sort_col: str, limit: int,
) -> tuple[str, list]:
    where_parts: list[str] = []
    params: list = []
    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])
    where_parts.append("over BETWEEN ? AND ?")
    params.extend([over_range[0], over_range[1]])

    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"batting_team IN ({placeholders})")
        params.extend(teams)
    if batters:
        placeholders = ", ".join(["?"] * len(batters))
        where_parts.append(f"batter IN ({placeholders})")
        params.extend(batters)
    if bowlers:
        placeholders = ", ".join(["?"] * len(bowlers))
        where_parts.append(f"bowler IN ({placeholders})")
        params.extend(bowlers)
    if phases:
        placeholders = ", ".join(["?"] * len(phases))
        where_parts.append(f"match_phase IN ({placeholders})")
        params.extend(phases)
    if innings and innings != "Both":
        where_parts.append("innings = ?")
        params.append(int(innings[0]))
    if venues:
        placeholders = ", ".join(["?"] * len(venues))
        where_parts.append(f"venue IN ({placeholders})")
        params.extend(venues)
    if ball_types:
        type_conditions = []
        for bt in ball_types:
            if bt == "Fours":
                type_conditions.append("is_four = true")
            elif bt == "Sixes":
                type_conditions.append("is_six = true")
            elif bt == "Boundaries":
                type_conditions.append("is_boundary = true")
            elif bt == "Dot Balls":
                type_conditions.append("is_dot = true")
            elif bt == "Wickets":
                type_conditions.append("player_out IS NOT NULL")
        if type_conditions:
            where_parts.append(f"({' OR '.join(type_conditions)})")
    if dismissal_kinds:
        placeholders = ", ".join(["?"] * len(dismissal_kinds))
        where_parts.append(f"wicket_kind IN ({placeholders})")
        params.extend(dismissal_kinds)

    where_clause = " AND ".join(where_parts)

    valid_sort_cols = {
        "(runs_batter + runs_extras)", "over", "ball", "season", "runs_batter",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "(runs_batter + runs_extras)"

    sql = (
        "SELECT match_id, season, innings, over, ball, "
        "batter, bowler, batting_team, bowling_team, "
        "runs_batter, (runs_batter + runs_extras) AS total_runs, "
        "is_four, is_six, is_dot, "
        "wicket_kind, player_out, match_phase, venue "
        f"FROM balls "
        f"WHERE {where_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_matchup_query(
    batters: list[str], bowlers: list[str],
    min_balls: int, min_dismissals: int,
    sort_col: str, limit: int,
) -> tuple[str, list]:
    where_parts: list[str] = []
    params: list = []

    if batters:
        placeholders = ", ".join(["?"] * len(batters))
        where_parts.append(f"batter IN ({placeholders})")
        params.extend(batters)
    if bowlers:
        placeholders = ", ".join(["?"] * len(bowlers))
        where_parts.append(f"bowler IN ({placeholders})")
        params.extend(bowlers)

    having_parts: list[str] = []
    if min_balls > 0:
        having_parts.append(f"SUM(total_balls) >= {min_balls}")
    if min_dismissals > 0:
        having_parts.append(f"SUM(dismissals) >= {min_dismissals}")

    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    agg = (
        "SUM(total_balls) AS balls, "
        "SUM(total_runs) AS runs, "
        "SUM(dismissals) AS dismissals, "
        "SUM(total_fours) AS fours, "
        "SUM(total_sixes) AS sixes, "
        "ROUND(SUM(total_runs)*100.0/NULLIF(SUM(total_balls),0),2) AS strike_rate, "
        "ROUND(SUM(total_runs)*1.0/NULLIF(SUM(dismissals),0),2) AS avg_vs"
    )
    having_clause = (" HAVING " + " AND ".join(having_parts)) if having_parts else ""

    valid_sort_cols = {"balls", "runs", "dismissals", "strike_rate", "avg_vs", "sixes", "fours"}
    if sort_col not in valid_sort_cols:
        sort_col = "balls"

    sql = (
        f"SELECT batter, bowler, {agg} "
        f"FROM matchups"
        f"{where_clause} "
        f"GROUP BY batter, bowler"
        f"{having_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_partnership_query(
    teams: list[str], season_range: tuple[int, int],
    min_runs: int, wicket_number: int,
    sort_col: str, limit: int,
) -> tuple[str, list]:
    where_parts: list[str] = []
    params: list = []
    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"batting_team IN ({placeholders})")
        params.extend(teams)
    if min_runs > 0:
        where_parts.append("runs >= ?")
        params.append(min_runs)
    if wicket_number > 0:
        where_parts.append("wicket_number = ?")
        params.append(wicket_number)

    where_clause = " AND ".join(where_parts)

    valid_sort_cols = {"runs", "balls", "season"}
    if sort_col not in valid_sort_cols:
        sort_col = "runs"

    sql = (
        "SELECT batting_partners, runs, balls, batting_team, "
        "bowling_team, season, venue, wicket_number, "
        "ROUND(runs*100.0/NULLIF(balls,0),2) AS strike_rate "
        f"FROM partnerships "
        f"WHERE {where_clause} "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_venue_query(
    venues: list[str], season_range: tuple[int, int],
    sort_col: str, limit: int,
) -> tuple[str, list]:
    where_parts: list[str] = []
    params: list = []
    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])
    if venues:
        placeholders = ", ".join(["?"] * len(venues))
        where_parts.append(f"venue IN ({placeholders})")
        params.extend(venues)
    where_clause = " AND ".join(where_parts)

    valid_sort_cols = {
        "matches", "avg_1st_inn", "avg_2nd_inn", "highest_total",
        "chase_win_pct", "boundaries_per_match",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "matches"

    sql = (
        "SELECT venue, "
        "COUNT(*) AS matches, "
        "ROUND(AVG(team1_score),1) AS avg_1st_inn, "
        "ROUND(AVG(team2_score),1) AS avg_2nd_inn, "
        "MAX(GREATEST(team1_score, team2_score)) AS highest_total, "
        "MIN(LEAST(team1_score, team2_score)) AS lowest_total, "
        "ROUND(SUM(CASE WHEN match_won_by = team2 THEN 1 ELSE 0 END)*100.0/"
        "NULLIF(SUM(CASE WHEN match_won_by IS NOT NULL AND match_won_by != 'Unknown' THEN 1 ELSE 0 END),0),1) AS chase_win_pct, "
        "ROUND(SUM(CASE WHEN toss_winner = match_won_by THEN 1 ELSE 0 END)*100.0/"
        "NULLIF(SUM(CASE WHEN match_won_by IS NOT NULL AND match_won_by != 'Unknown' THEN 1 ELSE 0 END),0),1) AS toss_advantage_pct "
        f"FROM matches "
        f"WHERE {where_clause} "
        f"GROUP BY venue "
        f"HAVING COUNT(*) >= 3 "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_powerplay_query(
    teams: list[str], season_range: tuple[int, int],
    group_by: str, sort_col: str, limit: int,
) -> tuple[str, list]:
    group_map = {
        "Team": "batting_team",
        "Season": "season",
        "Team + Season": "batting_team, season",
    }
    gb_cols = group_map.get(group_by, "batting_team")

    where_parts: list[str] = []
    params: list = []
    where_parts.append("season BETWEEN ? AND ?")
    params.extend([season_range[0], season_range[1]])

    if teams:
        placeholders = ", ".join(["?"] * len(teams))
        where_parts.append(f"batting_team IN ({placeholders})")
        params.extend(teams)
    where_clause = " AND ".join(where_parts)

    valid_sort_cols = {
        "avg_pp_runs", "avg_pp_boundaries", "total_wkts_lost",
        "innings", "avg_pp_sr",
    }
    if sort_col not in valid_sort_cols:
        sort_col = "avg_pp_runs"

    sql = (
        f"SELECT {gb_cols}, "
        "COUNT(*) AS innings, "
        "ROUND(AVG(pp_runs),1) AS avg_pp_runs, "
        "ROUND(AVG(pp_boundaries),1) AS avg_pp_boundaries, "
        "SUM(pp_wickets) AS total_wkts_lost, "
        "ROUND(AVG(pp_runs)*100.0/NULLIF(AVG(pp_balls_faced),0),1) AS avg_pp_sr "
        f"FROM powerplay "
        f"WHERE {where_clause} "
        f"GROUP BY {gb_cols} "
        f"HAVING COUNT(*) >= 5 "
        f"ORDER BY {sort_col} DESC "
        f"LIMIT {int(limit)}"
    )
    return sql, params


def _build_dismissal_query(
    players: list[str], phases: list[str],
    sort_col: str, limit: int,
) -> tuple[str, list]:
    # Use dismissals_phase if phase filter, else dismissals
    if phases:
        where_parts: list[str] = []
        params: list = []
        placeholders = ", ".join(["?"] * len(phases))
        where_parts.append(f"match_phase IN ({placeholders})")
        params.extend(phases)
        if players:
            pl = ", ".join(["?"] * len(players))
            where_parts.append(f"player_out IN ({pl})")
            params.extend(players)
        where_clause = " AND ".join(where_parts)

        valid_sort_cols = {"total", "player_out"}
        if sort_col not in valid_sort_cols:
            sort_col = "total"

        sql = (
            "SELECT player_out, wicket_kind, match_phase, "
            "COUNT(*) AS total "
            f"FROM dismissals_phase "
            f"WHERE {where_clause} "
            f"GROUP BY player_out, wicket_kind, match_phase "
            f"ORDER BY {sort_col} DESC "
            f"LIMIT {int(limit)}"
        )
    else:
        where_parts = []
        params = []
        if players:
            pl = ", ".join(["?"] * len(players))
            where_parts.append(f"player_out IN ({pl})")
            params.extend(players)
        where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

        valid_sort_cols = {"count", "player_out"}
        if sort_col not in valid_sort_cols:
            sort_col = "count"

        sql = (
            "SELECT player_out, wicket_kind, "
            "count "
            f"FROM dismissals"
            f"{where_clause} "
            f"ORDER BY {sort_col} DESC "
            f"LIMIT {int(limit)}"
        )
    return sql, params


# ─── Auto-chart logic ───────────────────────────────────────────────────

def _auto_chart(df: pd.DataFrame, group_by: str, entity_type: str):
    if df.empty or len(df) < 2:
        return

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        return

    y_col = numeric_cols[0]
    priority_map = {
        "Batting Stats": ["total_runs", "strike_rate", "average", "Runs"],
        "Bowling Stats": ["total_wickets", "economy", "bowling_sr"],
        "Team Stats": ["wins", "win_pct"],
        "Venue Stats": ["matches", "avg_1st_inn", "highest_total"],
        "Powerplay Stats": ["avg_pp_runs", "avg_pp_sr"],
        "Matchup Stats": ["balls", "runs", "strike_rate"],
        "Partnership Stats": ["runs", "strike_rate"],
        "Dismissal Patterns": ["count", "total"],
    }
    for c in priority_map.get(entity_type, []):
        if c in numeric_cols:
            y_col = c
            break

    non_numeric = df.select_dtypes(exclude="number").columns.tolist()
    x_col = non_numeric[0] if non_numeric else df.columns[0]

    season_groups = {"Season", "Player + Season", "Team + Season", "Venue + Season"}
    entity_groups = {"Player", "Team", "Venue", "Player + Team"}

    if group_by in season_groups:
        x_col = "season" if "season" in df.columns else x_col
        fig = px.line(
            df.sort_values(x_col) if x_col in df.columns else df,
            x=x_col, y=y_col,
            title=f"{y_col.replace('_', ' ').title()} by {group_by}",
            markers=True,
        )
    elif group_by in entity_groups:
        label_col = x_col
        for candidate in ["batter", "bowler", "Player", "team", "batting_team", "bowling_team", "Team", "venue", "Venue"]:
            if candidate in df.columns:
                label_col = candidate
                break
        chart_df = df.sort_values(y_col, ascending=True).tail(30)
        fig = px.bar(
            chart_df, x=y_col, y=label_col,
            orientation="h",
            title=f"{y_col.replace('_', ' ').title()} by {group_by}",
            text_auto=True,
        )
    else:
        chart_df = df.head(30)
        fig = px.bar(
            chart_df, y=y_col,
            title=f"{y_col.replace('_', ' ').title()}",
            text_auto=True,
        )

    apply_ipl_style(fig, height=max(400, min(len(df) * 28, 800)))
    st.plotly_chart(fig, width='stretch')


def _show_summary_stats(df: pd.DataFrame):
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.empty:
        return
    stats = numeric_df.describe().loc[["count", "mean", "min", "50%", "max"]].T
    stats.columns = ["Count", "Mean", "Min", "Median", "Max"]
    stats["Mean"] = stats["Mean"].round(2)
    stats["Median"] = stats["Median"].round(2)
    st.dataframe(stats, width='stretch')


# ═══════════════════════════════════════════════════════════════════════
#  PAGE UI
# ═══════════════════════════════════════════════════════════════════════

st.title("Explorer")
st.caption("The ultimate IPL analytics power-tool — 40+ one-click presets, 9 entity types, deep filters, and instant visualizations.")

# ── Navigation tabs ─────────────────────────────────────────────────────
main_tab_builder, main_tab_presets, main_tab_guide, main_tab_dict = st.tabs([
    "Query Builder", "Quick Presets", "User Guide", "Data Dictionary",
])

# ═══════════════════════════════════════════════════════════════════════
#  TAB 1: USER GUIDE
# ═══════════════════════════════════════════════════════════════════════
with main_tab_guide:
    st.subheader("How to Use the Explorer")
    st.markdown("""
Welcome to the **Explorer** — your all-access pass to querying 18 seasons of IPL data across **278,000+ ball-by-ball records**, **1,200+ matches**, and **700+ players**.

This tool gives you two ways to explore:
""")

    with st.expander("Quick Presets — One-Click Analytics", expanded=True):
        st.markdown("""
**What are Presets?** Pre-built queries covering the most popular IPL analytics questions — organized into 10 categories.

**How to use:**
1. Go to the **Quick Presets** tab
2. Pick a category (e.g., Batting Legends, Bowling Masters)
3. Click any preset button — results appear instantly with charts

**Categories available:**
| Category | What it covers |
|----------|---------------|
| Batting Legends | Top scorers, highest SR, centuries, fifties, sixes, highest scores |
| Bowling Masters | Top wicket takers, best economy, death/PP specialists, maidens |
| Venue Intelligence | Highest scoring venues, chasing success, toss impact |
| Head-to-Head Matchups | Batter vs bowler matchups, rivalry stats |
| Match Records | Highest/lowest totals, biggest wins, super overs, finals |
| Team Records | Win percentages, season-by-season, toss trends |
| Powerplay & Death | Powerplay batting, death bowling, most expensive overs |
| Partnerships | Highest stands, most prolific pairs, fastest partnerships |
| Pressure & Clutch | Close match heroes, knockout performers, PoM awards |
| Fun Facts & Anomalies | Ducks, golden ducks, boundary %, Orange/Purple cap winners |
| Dot Ball Analysis | Top dot ball bowlers and batters, dot sequences, phase analysis |
""")

    with st.expander("Query Builder — Build Your Own Analysis", expanded=True):
        st.markdown("""
**What is the Query Builder?** A point-and-click interface to create custom SQL queries — no coding required.

**Step-by-step:**
1. Go to the **Query Builder** tab
2. **Choose an entity type** (what you want to analyze):

| Entity Type | Best for | Example question |
|-------------|----------|-----------------|
| **Batting Stats** | Player/team batting performance | "Who has the best SR in death overs for CSK?" |
| **Bowling Stats** | Player/team bowling performance | "Bowlers with best economy at Wankhede?" |
| **Team Stats** | Team win/loss records | "RCB's win % over the years?" |
| **Match Stats** | Match-level results and scorecards | "All finals and their results?" |
| **Ball-by-Ball** | Individual delivery analysis | "All sixes hit by Gayle in powerplay?" |
| **Matchup Stats** | Batter vs bowler head-to-head | "Kohli's record against Bumrah?" |
| **Partnership Stats** | Partnership innings details | "Top 10 opening partnerships for MI?" |
| **Venue Stats** | Venue-level analytics | "Chase win % at Chinnaswamy?" |
| **Powerplay Stats** | Powerplay team performance | "Who scores fastest in powerplay?" |

3. **Set your filters:**
   - **Season range** — Narrow to specific years (e.g., 2020-2024)
   - **Players/Teams** — Focus on specific players or franchises
   - **Venues** — Analyze venue-specific performance
   - **Group By** — Choose how to aggregate (by Player, Season, Team, Venue, or combos)
   - **Sort By** — Pick the metric to rank results by
   - **Min thresholds** — Set qualification criteria (min runs, balls, wickets)
   - **Result limit** — Control how many rows to return (10-500)

4. Click **Run Query** — results + chart + downloadable CSV appear instantly
""")

    with st.expander("10 Example Queries You Can Build", expanded=False):
        st.markdown("""
Here are real examples to try in the Query Builder:

---

**1. "Top 10 run scorers for CSK, all-time"**
- Entity: **Batting Stats** → Team: **Chennai Super Kings** → Group by: **Player** → Sort by: **total_runs** → Limit: 10

**2. "Virat Kohli's season-by-season performance"**
- Entity: **Batting Stats** → Batter: **V Kohli** → Group by: **Player + Season** → Sort by: **total_runs**

**3. "Best economy bowlers at Wankhede Stadium"**
- Entity: **Bowling Stats** → Venue: **Wankhede Stadium** → Min balls: 100 → Sort by: **economy**

**4. "All matches at Eden Gardens that were won chasing"**
- Entity: **Match Stats** → Venue: **Eden Gardens** → Sort by: **date**

**5. "All sixes in death overs of 2024 season"**
- Entity: **Ball-by-Ball** → Season: 2024-2024 → Phase: **death** → Ball type: **Sixes** → Sort by: **runs_batter**

**6. "Kohli vs Bumrah head-to-head"**
- Entity: **Matchup Stats** → Batter: **V Kohli** → Bowler: **JJ Bumrah**

**7. "Top 15 opening stands of all time"**
- Entity: **Partnership Stats** → Wicket number: **1** → Sort by: **runs** → Limit: 15

**8. "Which venues favor chasing teams?"**
- Entity: **Venue Stats** → Sort by: **chase_win_pct**

**9. "Team powerplay scoring comparison in 2023-2024"**
- Entity: **Powerplay Stats** → Season: 2023-2024 → Group by: **Team** → Sort by: **avg_pp_runs**

**10. "Bowlers with 50+ wickets and sub-7.5 economy"**
- Entity: **Bowling Stats** → Min wickets: 50 → Sort by: **economy**
""")

    with st.expander("Cricket Terminology Cheat Sheet", expanded=False):
        st.markdown("""
| Term | Meaning |
|------|---------|
| **Strike Rate (SR)** | Runs scored per 100 balls. SR = (Runs / Balls) × 100. Higher = more aggressive. |
| **Economy** | Runs conceded per over by a bowler. Economy = (Runs / Balls) × 6. Lower = better. |
| **Average** | Runs per dismissal for batters (Runs / Outs). Higher = more consistent. For bowlers, runs per wicket. |
| **Bowling SR** | Balls bowled per wicket. Lower = more frequent wicket-taking. |
| **Dot Ball** | A delivery where zero runs are scored. Builds pressure. |
| **Boundary** | A four (ball reaches the boundary rope) or six (clears the rope). |
| **Powerplay** | Overs 1-6 where fielding restrictions apply. Only 2 fielders allowed outside 30-yard circle. |
| **Middle Overs** | Overs 7-15. Consolidation phase with up to 5 fielders outside the circle. |
| **Death Overs** | Overs 16-20. High-scoring phase where batters go all out. |
| **Duck** | A batter gets out scoring 0. A "Golden Duck" = out on the very first ball faced. |
| **Maiden Over** | An over where 0 runs are conceded off the bat. |
| **Orange Cap** | Awarded to the leading run-scorer of the season. |
| **Purple Cap** | Awarded to the leading wicket-taker of the season. |
| **NRR** | Net Run Rate — used to separate teams on equal points. Higher = better. |
| **Super Over** | Tiebreaker: each team bats 1 over. Used when scores are tied. |
| **DLS Method** | Duckworth-Lewis-Stern — revised target for rain-affected matches. |
| **Toss Decision** | Whether the toss winner chose to **bat** first or **field** first. |
| **Close Match** | Won by ≤10 runs or ≤2 wickets — indicates high pressure. |
| **Qualifier** | Knockout stage match in IPL playoffs. |
| **Eliminator** | Loser-goes-home playoff match. |
""")


# ═══════════════════════════════════════════════════════════════════════
#  TAB 2: QUICK PRESETS
# ═══════════════════════════════════════════════════════════════════════
with main_tab_presets:
    st.subheader("Quick Presets")
    st.caption("Click any preset to instantly see results with charts. 50+ pre-built analytics queries organized by category.")

    all_cat_names = ["All Categories"] + list(PRESET_CATEGORIES.keys())
    selected_filter = st.selectbox(
        "Filter by category",
        all_cat_names,
        key="preset_cat_filter",
    )

    if selected_filter == "All Categories":
        cats_to_show = PRESET_CATEGORIES
    else:
        cats_to_show = {selected_filter: PRESET_CATEGORIES[selected_filter]}

    preset_clicked: str | None = None
    clicked_category: str | None = None

    for cat_name, cat_presets in cats_to_show.items():
        st.markdown(f"#### {cat_name}")
        preset_names = list(cat_presets.keys())
        cols = st.columns(min(3, len(preset_names)))
        for i, name in enumerate(preset_names):
            with cols[i % len(cols)]:
                if st.button(name, key=f"preset_{cat_name}_{i}", width='stretch'):
                    preset_clicked = name
                    clicked_category = cat_name
        st.divider()

    if preset_clicked and clicked_category:
        preset = cats_to_show[clicked_category][preset_clicked]
        st.markdown(f"### {preset_clicked}")
        with st.expander("SQL Query", expanded=False):
            st.code(preset["sql"].strip(), language="sql")

        try:
            preset_df = run_query(preset["sql"])
            if preset_df.empty:
                st.info("No results found for this query.")
            else:
                if preset["chart"] == "bar" and preset["x"] and preset["y"]:
                    chart_df = preset_df.sort_values(preset["y"], ascending=True)
                    fig = px.bar(
                        chart_df,
                        x=preset["y"], y=preset["x"],
                        orientation="h",
                        title=preset_clicked,
                        text_auto=True,
                    )
                    apply_ipl_style(fig, height=max(400, len(chart_df) * 28))
                    st.plotly_chart(fig, width='stretch')

                st.dataframe(preset_df, width='stretch', hide_index=True)

                csv = preset_df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    file_name=f"explorer_{preset_clicked.replace(' ', '_').lower()}.csv",
                    mime="text/csv",
                    key="preset_download",
                )
        except Exception as e:
            st.error(f"Query error: {e}")


# ═══════════════════════════════════════════════════════════════════════
#  TAB 3: CUSTOM QUERY BUILDER
# ═══════════════════════════════════════════════════════════════════════
with main_tab_builder:
    st.subheader("Custom Query Builder")
    st.caption("Choose an entity type, set filters, and run — no SQL knowledge required.")

    ENTITY_TYPES = [
        "Batting Stats", "Bowling Stats", "Team Stats", "Match Stats",
        "Ball-by-Ball", "Matchup Stats", "Partnership Stats",
        "Venue Stats", "Powerplay Stats",
    ]

    entity_type = st.radio(
        "What do you want to analyze?",
        ENTITY_TYPES,
        horizontal=True,
        key="entity_type",
        help="Each entity type queries a different dataset. See the User Guide for details.",
    )

    with st.form("query_builder_form"):
        # ── Common filters ──
        season_col1, season_col2, limit_col = st.columns([1, 1, 1])
        with season_col1:
            season_start = st.selectbox("Season from", ALL_SEASONS, index=0, key="season_start")
        with season_col2:
            season_end = st.selectbox("Season to", ALL_SEASONS, index=len(ALL_SEASONS)-1, key="season_end")
        with limit_col:
            limit = st.slider("Result limit", 10, 500, 25, step=5, key="limit_slider",
                              help="Max rows to return. Increase for broader analysis.")

        # ── Entity-specific filters ──
        sql_to_run: str = ""
        sql_params: list = []
        current_group_by: str = "Player"

        if entity_type == "Batting Stats":
            fc1, fc2 = st.columns(2)
            with fc1:
                sel_players = st.multiselect("Filter batters", get_all_batters(), key="bat_players",
                                             help="Leave empty for all batters")
                sel_teams = st.multiselect("Filter teams", get_all_teams(), key="bat_teams")
                sel_venues = st.multiselect("Filter venues", get_all_venues(), key="bat_venues")
            with fc2:
                current_group_by = st.selectbox(
                    "Group by", ["Player", "Season", "Team", "Venue",
                                 "Player + Season", "Player + Team", "Venue + Season"],
                    key="bat_group",
                    help="How to aggregate the data. 'Player + Season' shows each player's stats per year.",
                )
                sort_by = st.selectbox(
                    "Sort by",
                    ["total_runs", "strike_rate", "average", "innings", "sixes", "fours",
                     "boundaries", "fifty_plus", "centuries", "highest_score", "ducks"],
                    key="bat_sort",
                )
            mc1, mc2 = st.columns(2)
            with mc1:
                min_runs = st.slider("Min total runs", 0, 2000, 0, step=50, key="bat_min_runs",
                                     help="Only show results where total runs ≥ this value")
            with mc2:
                min_balls = st.slider("Min total balls", 0, 1000, 0, step=25, key="bat_min_balls")

        elif entity_type == "Bowling Stats":
            fc1, fc2 = st.columns(2)
            with fc1:
                sel_bowlers = st.multiselect("Filter bowlers", get_all_bowlers(), key="bowl_players")
                sel_teams = st.multiselect("Filter teams", get_all_teams(), key="bowl_teams")
                sel_venues = st.multiselect("Filter venues", get_all_venues(), key="bowl_venues")
            with fc2:
                current_group_by = st.selectbox(
                    "Group by", ["Player", "Season", "Team", "Venue",
                                 "Player + Season", "Player + Team", "Venue + Season"],
                    key="bowl_group",
                )
                sort_by = st.selectbox(
                    "Sort by",
                    ["total_wickets", "economy", "bowling_sr", "innings", "dots",
                     "dot_pct", "maidens", "best_wickets", "runs_conceded"],
                    key="bowl_sort",
                )
            mc1, mc2 = st.columns(2)
            with mc1:
                min_wickets = st.slider("Min total wickets", 0, 200, 0, step=5, key="bowl_min_wkts")
            with mc2:
                min_balls = st.slider("Min total balls bowled", 0, 1000, 0, step=25, key="bowl_min_balls")

        elif entity_type == "Team Stats":
            fc1, fc2 = st.columns(2)
            with fc1:
                sel_teams = st.multiselect("Filter teams", get_all_teams(), key="team_filter")
            with fc2:
                current_group_by = st.selectbox(
                    "Group by", ["Team", "Season", "Team + Season"], key="team_group",
                )
                sort_by = st.selectbox(
                    "Sort by", ["wins", "win_pct", "matches", "losses"], key="team_sort",
                )

        elif entity_type == "Match Stats":
            fc1, fc2 = st.columns(2)
            with fc1:
                sel_stages = st.multiselect("Stage filter", get_all_stages(), key="match_stages",
                                            help="Filter by tournament stage (League, Final, etc.)")
                sel_venues = st.multiselect("Venue filter", get_all_venues(), key="match_venues")
            with fc2:
                sel_teams_match = st.multiselect("Team filter (either team)", get_all_teams(), key="match_teams",
                                                 help="Show matches involving these teams")
                sel_toss = st.selectbox("Toss decision filter", ["Any", "bat", "field"], key="match_toss")
            close_only = st.checkbox("Only close matches (≤10 runs / ≤2 wickets)", key="match_close")
            sort_by = st.selectbox(
                "Sort by",
                ["date", "team1_score", "team2_score", "win_margin_value", "season"],
                key="match_sort",
            )

        elif entity_type == "Ball-by-Ball":
            fc1, fc2 = st.columns(2)
            with fc1:
                sel_teams = st.multiselect("Batting team", get_all_teams(), key="bbb_teams")
                sel_batters = st.multiselect("Batter filter", get_all_batters(), key="bbb_batters")
                sel_venues_bbb = st.multiselect("Venue filter", get_all_venues(), key="bbb_venues")
            with fc2:
                sel_bowlers_bbb = st.multiselect("Bowler filter", get_all_bowlers(), key="bbb_bowlers")
                sel_phases = st.multiselect("Phase filter", ["powerplay", "middle", "death"], key="bbb_phases")
                sel_innings = st.selectbox("Innings", ["Both", "1st innings", "2nd innings"], key="bbb_innings")
            oc1, oc2 = st.columns(2)
            with oc1:
                over_start = st.number_input("Over from", 0, 19, 0, key="over_start",
                                             help="0-indexed. Over 0 = 1st over.")
                sel_ball_types = st.multiselect(
                    "Ball type filter",
                    ["Fours", "Sixes", "Boundaries", "Dot Balls", "Wickets"],
                    key="bbb_ball_types",
                    help="Filter to only specific ball outcomes",
                )
            with oc2:
                over_end = st.number_input("Over to", 0, 19, 19, key="over_end")
                sel_dismissal_kinds = st.multiselect(
                    "Dismissal type",
                    ["caught", "bowled", "run out", "lbw", "stumped",
                     "caught and bowled", "hit wicket", "retired out"],
                    key="bbb_dismissals",
                )
            sort_by = st.selectbox(
                "Sort by",
                ["(runs_batter + runs_extras)", "runs_batter", "over", "season"],
                key="bbb_sort",
            )

        elif entity_type == "Matchup Stats":
            fc1, fc2 = st.columns(2)
            with fc1:
                sel_batters_mu = st.multiselect("Batter filter", get_all_batters(), key="mu_batters",
                                                help="Leave empty to see all matchups")
                sel_bowlers_mu = st.multiselect("Bowler filter", get_all_bowlers(), key="mu_bowlers")
            with fc2:
                mu_min_balls = st.slider("Min balls faced", 0, 100, 10, step=5, key="mu_min_balls")
                mu_min_dism = st.slider("Min dismissals", 0, 10, 0, key="mu_min_dism")
            sort_by = st.selectbox(
                "Sort by",
                ["balls", "runs", "dismissals", "strike_rate", "avg_vs", "sixes"],
                key="mu_sort",
            )

        elif entity_type == "Partnership Stats":
            fc1, fc2 = st.columns(2)
            with fc1:
                sel_teams_p = st.multiselect("Team filter", get_all_teams(), key="part_teams")
            with fc2:
                part_min_runs = st.slider("Min partnership runs", 0, 200, 0, step=10, key="part_min_runs")
                part_wicket = st.selectbox("Wicket number", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                                           key="part_wicket",
                                           help="0 = all wickets. 1 = opening stand, 2 = 1st wicket partnership, etc.")
            sort_by = st.selectbox(
                "Sort by", ["runs", "balls", "season"], key="part_sort",
            )

        elif entity_type == "Venue Stats":
            fc1, fc2 = st.columns(2)
            with fc1:
                sel_venues_v = st.multiselect("Filter venues", get_all_venues(), key="venue_filter")
            with fc2:
                sort_by = st.selectbox(
                    "Sort by",
                    ["matches", "avg_1st_inn", "avg_2nd_inn", "highest_total",
                     "chase_win_pct", "toss_advantage_pct"],
                    key="venue_sort",
                    help="'chase_win_pct' = % of matches won by team batting 2nd",
                )

        elif entity_type == "Powerplay Stats":
            fc1, fc2 = st.columns(2)
            with fc1:
                sel_teams_pp = st.multiselect("Filter teams", get_all_teams(), key="pp_teams")
            with fc2:
                current_group_by = st.selectbox(
                    "Group by", ["Team", "Season", "Team + Season"], key="pp_group",
                )
                sort_by = st.selectbox(
                    "Sort by",
                    ["avg_pp_runs", "avg_pp_boundaries", "total_wkts_lost", "innings", "avg_pp_sr"],
                    key="pp_sort",
                )

        submitted = st.form_submit_button("🚀 Run Query", width='stretch', type="primary")

    # ── Execute query after form submission ─────────────────────────────
    if submitted:
        season_range = (min(season_start, season_end), max(season_start, season_end))

        try:
            if entity_type == "Batting Stats":
                sql_to_run, sql_params = _build_batting_query(
                    sel_players, season_range, sel_teams, sel_venues,
                    min_runs, min_balls, current_group_by, sort_by, limit,
                )
            elif entity_type == "Bowling Stats":
                sql_to_run, sql_params = _build_bowling_query(
                    sel_bowlers, season_range, sel_teams, sel_venues,
                    min_wickets, min_balls, current_group_by, sort_by, limit,
                )
            elif entity_type == "Team Stats":
                sql_to_run, sql_params = _build_team_query(
                    sel_teams, season_range, current_group_by, sort_by, limit,
                )
            elif entity_type == "Match Stats":
                sql_to_run, sql_params = _build_match_query(
                    season_range, sel_stages, sel_venues, sel_teams_match,
                    sel_toss, close_only, sort_by, limit,
                )
            elif entity_type == "Ball-by-Ball":
                sql_to_run, sql_params = _build_ball_query(
                    season_range, sel_teams, sel_batters, sel_bowlers_bbb,
                    sel_phases, (int(over_start), int(over_end)),
                    sel_innings, sel_venues_bbb, sel_ball_types,
                    sel_dismissal_kinds, sort_by, limit,
                )
            elif entity_type == "Matchup Stats":
                sql_to_run, sql_params = _build_matchup_query(
                    sel_batters_mu, sel_bowlers_mu,
                    mu_min_balls, mu_min_dism, sort_by, limit,
                )
            elif entity_type == "Partnership Stats":
                sql_to_run, sql_params = _build_partnership_query(
                    sel_teams_p, season_range,
                    part_min_runs, part_wicket, sort_by, limit,
                )
            elif entity_type == "Venue Stats":
                sql_to_run, sql_params = _build_venue_query(
                    sel_venues_v, season_range, sort_by, limit,
                )
            elif entity_type == "Powerplay Stats":
                sql_to_run, sql_params = _build_powerplay_query(
                    sel_teams_pp, season_range, current_group_by, sort_by, limit,
                )

            with st.expander("Generated SQL", expanded=False):
                st.code(sql_to_run.strip(), language="sql")
                if sql_params:
                    st.caption(f"Parameters: `{sql_params}`")

            result_df = run_query(sql_to_run, sql_params)

            if result_df.empty:
                st.warning("No results found. Try broadening your filters.")
            else:
                st.success(f"✅ {format_number(len(result_df))} rows returned")

                # Summary metrics
                m1, m2, m3, m4 = st.columns(4)
                numeric_cols = result_df.select_dtypes(include="number").columns.tolist()
                if numeric_cols:
                    primary = numeric_cols[0]
                    m1.metric("Rows", format_number(len(result_df)))
                    m2.metric(f"Σ {primary}", format_number(result_df[primary].sum()))
                    m3.metric(f"Avg {primary}", format_number(result_df[primary].mean(), decimals=1))
                    m4.metric(f"Max {primary}", format_number(result_df[primary].max()))

                # Auto-chart for all entity types
                chart_group = current_group_by if entity_type not in (
                    "Match Stats", "Ball-by-Ball", "Matchup Stats", "Partnership Stats",
                    "Venue Stats", "Powerplay Stats",
                ) else "Player"

                if entity_type == "Venue Stats":
                    chart_group = "Venue"
                elif entity_type == "Powerplay Stats":
                    chart_group = current_group_by
                elif entity_type == "Matchup Stats":
                    chart_group = "Player"

                _auto_chart(result_df, chart_group, entity_type)

                # Result table
                st.dataframe(result_df, width='stretch', hide_index=True)

                # Summary statistics
                with st.expander("Summary Statistics"):
                    _show_summary_stats(result_df)

                # Export
                csv = result_df.to_csv(index=False)
                st.download_button(
                    "Download Results as CSV",
                    csv,
                    file_name="explorer_results.csv",
                    mime="text/csv",
                    key="custom_download",
                )

        except Exception as e:
            st.error(f"Query error: {e}")
            st.exception(e)


# ═══════════════════════════════════════════════════════════════════════
#  TAB 4: DATA DICTIONARY
# ═══════════════════════════════════════════════════════════════════════
with main_tab_dict:
    st.subheader("Data Dictionary")
    st.caption("Browse all available data views, their schemas, and sample records.")

    selected_view = st.selectbox(
        "Select a view",
        list(VIEW_DESCRIPTIONS.keys()),
        key="dict_view",
    )

    st.markdown(f"**{selected_view}** — {VIEW_DESCRIPTIONS.get(selected_view, '')}")

    tab_schema, tab_sample = st.tabs(["Schema", "Sample Data"])

    with tab_schema:
        try:
            col_df = get_view_columns(selected_view)
            st.dataframe(col_df, width='stretch', hide_index=True)
        except Exception as e:
            st.error(f"Could not load schema: {e}")

    with tab_sample:
        try:
            sample_df = get_view_sample(selected_view)
            st.dataframe(sample_df, width='stretch', hide_index=True)
        except Exception as e:
            st.error(f"Could not load sample: {e}")

    st.divider()
    st.markdown("##### Key Relationships Between Views")
    st.markdown("""
| From → To | Join Key | Use Case |
|-----------|----------|----------|
| `balls` → `matches` | `match_id` | Link ball events to match context |
| `player_batting` → `matches` | `match_id, season` | Link batting cards to match results |
| `player_bowling` → `matches` | `match_id, season` | Link bowling figures to match results |
| `matchups` → `player_batting` | `batter` | Combine matchup data with career stats |
| `partnerships` → `matches` | `match_id` | Link partnerships to match context |
| `team_season` → `points_table` | `team, season` | Combine win/loss with standings |
""")
