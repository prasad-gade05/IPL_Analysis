# IPL Analytics Platform

**Live App:** https://analytics-ipl.streamlit.app/

> **Note:** This app is hosted on Streamlit's free tier. If you see a screen saying _"This app has gone to sleep"_, it's not broken — just click the button to wake it up. Free hosting sleeps inactive apps to save resources for the open-source community. It'll be back in ~30 seconds!

> **18 Seasons | 1,169 Matches | 703 Players | 37 Venues**

A comprehensive, interactive analytics dashboard for Indian Premier League data (2008–2025),
built with **Streamlit + DuckDB + Parquet + Plotly**.

For detailed technical documentation (architecture, data pipeline, schema, cricket glossary), see **[TECHNICAL.md](TECHNICAL.md)**.

## Quick Start

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
#   data/raw/ipl_ball_by_ball.csv

# 5. Run preprocessing pipeline
python data/preprocessing/run_pipeline.py

# 6. Launch the app
streamlit run app.py
```

## Project Structure

```
IPL_Analysis/
├── app.py                          # Main Streamlit entry point
├── requirements.txt                # Python dependencies
├── runtime.txt                     # Python version for Streamlit Cloud
├── .streamlit/
│   └── config.toml                 # Theme & Streamlit configuration
├── data/
│   ├── raw/                        # Original CSV (git-ignored)
│   │   └── ipl_ball_by_ball.csv
│   ├── processed/                  # Parquet files (committed)
│   │   ├── ball_by_ball.parquet
│   │   ├── match_summary.parquet
│   │   ├── player_season.parquet
│   │   ├── player_batting_match.parquet
│   │   ├── player_bowling_match.parquet
│   │   ├── matchups.parquet
│   │   ├── venue_stats.parquet
│   │   ├── partnerships.parquet
│   │   ├── dot_sequences.parquet
│   │   ├── powerplay_stats.parquet
│   │   ├── season_structure.parquet
│   │   ├── dismissal_patterns.parquet
│   │   ├── team_season.parquet
│   │   └── points_table.parquet
│   └── preprocessing/
│       ├── run_pipeline.py         # Pipeline orchestrator
│       ├── 01_clean.py             # Data cleaning
│       ├── 02_derive_features.py   # Feature engineering
│       └── 03_build_aggregates.py  # Pre-computed aggregates
├── src/
│   ├── db/
│   │   ├── connection.py           # DuckDB singleton + parquet views
│   │   └── queries/
│   │       ├── player_queries.py
│   │       ├── team_queries.py
│   │       ├── matchup_queries.py
│   │       ├── venue_queries.py
│   │       ├── pressure_queries.py
│   │       └── season_queries.py
│   ├── visualizations/
│   │   └── theme.py                # Plotly theme + team colors
│   └── utils/
│       ├── constants.py            # Team colors, phases, mappings
│       ├── filters.py              # Reusable Streamlit filter widgets
│       └── formatters.py           # Number/text formatting
├── pages/                          # Streamlit multi-page app pages
│   ├── 00_Home.py
│   ├── 01_Season_Hub.py
│   ├── 02_Leaderboards.py
│   ├── 03_Player_Profile.py
│   ├── 04_Team_Profile.py
│   ├── 05_Venue_Intelligence.py
│   ├── 06_Head_to_Head.py
│   ├── 07_Phase_Analysis.py
│   ├── 08_Pressure_Momentum.py
│   ├── 09_Trends_Evolution.py
│   ├── 10_Records_Anomalies.py
│   ├── 11_Match_Center.py
│   ├── 12_Tournament_Structure.py
│   └── 13_Explorer.py
├── tests/
│   └── test_project.py
└── AI_Instructions/                # Architecture docs (git-ignored)
    ├── initial_context.txt
    ├── initial_eda.txt
    ├── structure.txt
    ├── derived_calculations.yaml
    └── testing_and_data_integrity.yaml
```

## Tech Stack

| Component    | Technology                            |
| ------------ | ------------------------------------- |
| Frontend     | Streamlit (multi-page app)            |
| Charts       | Plotly (interactive)                  |
| Query Engine | DuckDB (in-process analytical SQL)    |
| Data Storage | Apache Parquet (columnar, compressed) |
| Hosting      | Streamlit Community Cloud (free)      |
| Language     | 100% Python                           |

## Dashboard Pages (14 total)

1. **Home** — Hero stats, IPL timeline, latest season highlights
2. **Season Hub** — Complete season yearbook with points table
3. **Leaderboards** — All-time batting, bowling, team rankings
4. **Player Profile** — Complete career dossier for any player
5. **Team Profile** — Franchise analytics and history
6. **Venue Intelligence** — Ground-specific batting/bowling insights
7. **Head-to-Head** — Batter vs Bowler, Team vs Team
8. **Phase Analysis** — Powerplay/Middle/Death deep-dives
9. **Pressure & Momentum** — Dot ball cascades, chase dynamics
10. **Trends & Evolution** — 18-year evolution of IPL cricket
11. **Records & Anomalies** — Every IPL record and outlier
12. **Match Center** — Ball-by-ball match replay
13. **Tournament Structure** — Season formats and brackets
14. **Explorer** — Custom query builder with 58 presets

## Deployment (Streamlit Cloud)

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set main file: `app.py`
5. Deploy — that's it!

## Data

Dataset sourced from Kaggle: [IPL Dataset 2008–2025](https://www.kaggle.com/datasets/chaitu20/ipl-dataset2008-2025) by **chaitu20**.
