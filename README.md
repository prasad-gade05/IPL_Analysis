# IPL Analytics Platform

**Live App:** https://analytics-ipl.streamlit.app/

> **Note:** The app is hosted on Streamlit's free tier. If it says the app is sleeping, wake it and wait a few seconds.

> **19 Seasons | 1,243 Matches | 15 Pages | 19 DuckDB Views**

An IPL analytics app built with **Streamlit + DuckDB + Parquet + Plotly** over ball-by-ball data from 2008-2026.

For the architecture and pipeline details, see **[TECHNICAL.md](TECHNICAL.md)**.

## What is implemented

- **15 Streamlit pages**, including `Explorer` and `Ask Anything`
- **Deterministic semantic search** in both `pages\14_Ask_Anything.py` and the semantic tab inside `pages\13_Explorer.py`
- **40 shipped semantic example prompts** backed by whitelisted planning and SQL compilation, not free-form text-to-SQL
- **58 Explorer presets across 11 categories**
- **Schema-driven per-visual controls** rolled out across the main analytics pages where local filtering preserves the meaning of the visual
- **19 parquet-backed DuckDB views**, including helper views added for semantic queries: `team_match_results`, `over_summary`, `innings_tags`, and `player_season_metrics`
- **71 pytest checks**

## Accuracy model

This project is intentionally conservative about statistics:

- supported semantic questions are mapped to known query families
- SQL is compiled from whitelisted patterns
- unsupported questions are rejected clearly instead of guessed
- result pages show assumptions, active filters, and generated SQL

The app favors explicit limits over plausible-but-unreliable answers.

## Quick start

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# 1. Clone the repo
git clone <repo-url> && cd IPL_Analysis

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Place raw data
# Download IPL.csv from Kaggle and place it at:
#   Data\raw\IPL.csv

# 5. Run preprocessing pipeline
python Data\preprocessing\run_pipeline.py

# 6. Launch the app
streamlit run app.py
```

## Project structure

```text
IPL_Analysis/
|- app.py
|- README.md
|- TECHNICAL.md
|- Data/
|  |- raw/
|  |  \- IPL.csv
|  |- processed/
|  |  |- ball_by_ball.parquet
|  |  |- match_summary.parquet
|  |  |- player_season.parquet
|  |  |- player_batting_match.parquet
|  |  |- player_bowling_match.parquet
|  |  |- matchups.parquet
|  |  |- venue_stats.parquet
|  |  |- partnerships.parquet
|  |  |- dot_sequences.parquet
|  |  |- powerplay_stats.parquet
|  |  |- season_structure.parquet
|  |  |- dismissal_patterns.parquet
|  |  |- dismissal_by_phase.parquet
|  |  |- team_season.parquet
|  |  |- points_table.parquet
|  |  |- team_match_results.parquet
|  |  |- over_summary.parquet
|  |  |- innings_tags.parquet
|  |  \- player_season_metrics.parquet
|  \- preprocessing/
|     |- run_pipeline.py
|     |- 01_clean.py
|     |- 02_derive_features.py
|     \- 03_build_aggregates.py
|- src/
|  |- db/
|  |- semantic/
|  |- utils/
|  \- visualizations/
|- pages/
|  |- 00_Home.py
|  |- 01_Season_Hub.py
|  |- 02_Leaderboards.py
|  |- 03_Player_Profile.py
|  |- 04_Team_Profile.py
|  |- 05_Venue_Intelligence.py
|  |- 06_Head_to_Head.py
|  |- 07_Phase_Analysis.py
|  |- 08_Pressure_Momentum.py
|  |- 09_Trends_Evolution.py
|  |- 10_Records_Anomalies.py
|  |- 11_Match_Center.py
|  |- 12_Tournament_Structure.py
|  |- 13_Explorer.py
|  \- 14_Ask_Anything.py
\- tests/
   \- test_project.py
```

## Dashboard pages

1. **Home** - landing page, all-time leaders, timeline, recent season highlights
2. **Season Hub** - one-season yearbook with points table and leaders
3. **Leaderboards** - all-time batting, bowling, team, all-round and misc rankings
4. **Player Profile** - career summary, season splits, venue/opposition/matchup views
5. **Team Profile** - franchise history, top performers, season and venue views
6. **Venue Intelligence** - venue scoring patterns, chase behavior, top performers
7. **Head-to-Head** - batter vs bowler and team vs team comparisons
8. **Phase Analysis** - powerplay, middle and death-over analytics
9. **Pressure & Momentum** - dot pressure, chase dynamics, clutch contexts
10. **Trends & Evolution** - season-over-season IPL shifts
11. **Records & Anomalies** - high-end and low-end extremes, milestone records
12. **Match Center** - match replay style scorecards and progression views
13. **Tournament Structure** - season formats, points tables, bracket comparisons
14. **Explorer** - query builder, presets, data dictionary, semantic search tab
15. **Ask Anything** - deterministic semantic stats search with SQL and assumptions

## Semantic search coverage

The semantic layer is limited to implemented query families. Current shipped examples cover prompts around:

- hat-tricks, wickets in an over, maidens, wicket maidens, perfect overs
- wicket, maiden, dot-ball, boundary, and scoring-shot streaks
- ducks, golden ducks, balls taken in an innings
- dismissal-type questions
- Orange Cap / Purple Cap history
- chase records, near misses, threshold and season consistency questions

If a question falls outside the supported grammar, the app says so instead of inventing a result.

## Testing

Run the suite with:

```bash
python -m pytest tests\ --tb=short -q
```

Current repository result: **71 passed**.

## Data

Source dataset: [IPL Dataset 2008-2025](https://www.kaggle.com/datasets/chaitu20/ipl-dataset2008-2025) by **chaitu20** (updated in place by its author; the current export covers 2008-2026).

Derived dataset notes: see **[DatasetReadme.md](DatasetReadme.md)**.
