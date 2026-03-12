# Technical Documentation — IPL Analytics Platform

## Architecture

The application follows a three-layer architecture:

```
Raw CSV → [3-Stage Pipeline] → Parquet Files → [DuckDB Views] → [Streamlit Pages]
```

### Data Pipeline

The preprocessing pipeline (`Data/preprocessing/run_pipeline.py`) runs three steps sequentially:

**Step 1 — `01_clean.py`** (Raw CSV → Cleaned Parquet)
- Drops 8 constant/empty columns (64 → 56)
- Standardizes team names using a 5-entry mapping (e.g., "Royal Challengers Bangalore" → "Royal Challengers Bengaluru")
- Standardizes 59 venue name variants down to 37 unique venues
- Parses win outcomes into structured columns (margin value, margin type)
- Adds delivery numbering (delivery_number, legal_ball_number)
- Classifies match stages (League, Qualifier 1, Qualifier 2, Eliminator, Final)
- Validates all transformations with assertions
- Output: `ball_by_ball_cleaned.parquet` (278,205 rows × 63 columns)

**Step 2 — `02_derive_features.py`** (Cleaned → Feature-Enriched Parquet)
- Adds `match_phase` — powerplay (overs 1-6), middle (7-15), death (16-20)
- Adds ball outcome flags — `is_four`, `is_six`, `is_boundary`, `is_dot`
- Computes dot ball sequences — `consecutive_dots_before`, `is_sequence_breaker`, `dot_sequence_outcome`
- Builds partnership tracking — `partnership_id`, `partnership_runs`, `partnership_balls`
- Calculates chase metrics for 2nd innings — `required_run_rate`, `current_run_rate`, `run_rate_pressure`
- Assigns batting position buckets — top order (1-3), middle order (4-5), lower middle (6-7), tail (8-11)
- Adds over-level stats — `is_maiden`, `over_runs`, `over_dots`, `over_boundaries`, `over_wickets`
- Adds bowling spell tracking — `bowling_stint`, `spell_number`
- Adds match context flags — `is_close_match`, `toss_winner_is_batting`, `is_super_over`
- Output: `ball_by_ball.parquet` (278,205 rows × 90 columns, 27 new features)

**Step 3 — `03_build_aggregates.py`** (Feature Parquet → 15 Aggregate Parquets)

Produces these aggregate files from the enriched ball-by-ball data:

| # | Output File | Rows | Description |
|---|-------------|------|-------------|
| 1 | match_summary.parquet | 1,169 | One row per match with scores, winner, margin, toss, venue |
| 2 | player_season.parquet | 3,138 | Player-team-season mapping for roster lookup |
| 3 | matchups.parquet | 29,533 | Batter vs bowler head-to-head aggregates |
| 4 | venue_stats.parquet | 42 | Venue-level averages (scores, boundaries, bat-first win %) |
| 5 | powerplay_stats.parquet | 2,365 | Per-innings powerplay runs, wickets, boundaries, run rate |
| 6 | dot_sequences.parquet | 34 | Outcomes after N consecutive dot balls |
| 7 | season_structure.parquet | 18 | Season metadata (dates, teams, venues, DLS matches) |
| 8 | player_batting_match.parquet | 17,708 | Per-innings batting card (runs, balls, 4s, 6s, SR, position) |
| 9 | player_bowling_match.parquet | 13,878 | Per-innings bowling figures (runs, balls, wickets, economy) |
| 10 | partnerships.parquet | 15,696 | Partnership runs, balls, boundaries per batting pair per innings |
| 11 | dismissal_patterns.parquet | 2,089 | Dismissal counts by type per player |
| 12 | dismissal_by_phase.parquet | 3,446 | Dismissal counts by type, phase, and player |
| 13 | team_season.parquet | 156 | Team wins, losses, and match counts per season |
| 14 | points_table.parquet | 156 | IPL points table with NRR (mirrors team_season) |

### Data Integrity

Aggregation functions include all deliveries (including no-balls) for batter run totals, fours, and sixes. Only the `balls` count uses `valid_ball` filtering because no-balls do not count as legal deliveries in cricket. This ensures:
- 703 batters: zero mismatches between aggregated and raw ball-by-ball totals
- 550 bowlers: zero mismatches between aggregated and raw ball-by-ball totals

---

## DuckDB Query Layer

The application uses DuckDB as an in-process analytical SQL engine. On startup, `src/db/connection.py` registers 15 DuckDB views that map directly to parquet files:

| View Name | Source Parquet | Row Count |
|-----------|---------------|-----------|
| `balls` | ball_by_ball.parquet | 278,205 |
| `matches` | match_summary.parquet | 1,169 |
| `player_season` | player_season.parquet | 3,138 |
| `player_batting` | player_batting_match.parquet | 17,708 |
| `player_bowling` | player_bowling_match.parquet | 13,878 |
| `matchups` | matchups.parquet | 29,533 |
| `venues` | venue_stats.parquet | 42 |
| `partnerships` | partnerships.parquet | 15,696 |
| `dot_sequences` | dot_sequences.parquet | 34 |
| `powerplay` | powerplay_stats.parquet | 2,365 |
| `season_meta` | season_structure.parquet | 18 |
| `dismissals` | dismissal_patterns.parquet | 2,089 |
| `dismissals_phase` | dismissal_by_phase.parquet | 3,446 |
| `team_season` | team_season.parquet | 156 |
| `points_table` | points_table.parquet | 156 |

All SQL queries across all 14 pages run against these views. DuckDB executes them directly on parquet files — no data loading into memory required.

---

## Dashboard Pages

### Page 1 — Home (`00_Home.py`)
Hero stats (total matches, players, venues), IPL season timeline, latest season highlights.

### Page 2 — Season Hub (`01_Season_Hub.py`)
Complete season yearbook. Points table, top run scorers, top wicket takers, team performance breakdown for any selected season.

### Page 3 — Leaderboards (`02_Leaderboards.py`)
All-time batting rankings (runs, SR, average, centuries), bowling rankings (wickets, economy, SR), team rankings (win %).

### Page 4 — Player Profile (`03_Player_Profile.py`)
Full career dossier for any player. Season-by-season breakdown, batting/bowling cards, venue performance, matchup data, dismissal patterns.

### Page 5 — Team Profile (`04_Team_Profile.py`)
Franchise analytics. Season history, head-to-head records, top players, venue performance, toss analysis.

### Page 6 — Venue Intelligence (`05_Venue_Intelligence.py`)
Ground-specific analytics. Average scores, chase success rates, boundary frequency, phase-wise scoring, toss impact per venue.

### Page 7 — Head-to-Head (`06_Head_to_Head.py`)
Batter vs bowler matchups with runs, balls, dismissals, strike rate. Team vs team historical records.

### Page 8 — Phase Analysis (`07_Phase_Analysis.py`)
Deep-dive into powerplay (overs 1-6), middle overs (7-15), and death overs (16-20). Scoring rates, wicket frequency, boundary patterns by phase.

### Page 9 — Pressure & Momentum (`08_Pressure_Momentum.py`)
Four tabs: Dot Ball Pressure (cascade analysis, top dot ball bowlers and batters, phase-wise dot %), Chase Dynamics (success rates by target, best chase innings), Partnerships Under Pressure, Clutch Performances.

### Page 10 — Trends & Evolution (`09_Trends_Evolution.py`)
18-year evolution of IPL cricket. How scoring rates, boundary frequency, bowling economy, and other metrics have changed across seasons.

### Page 11 — Records & Anomalies (`10_Records_Anomalies.py`)
All IPL records — highest scores, best bowling figures, biggest wins, lowest totals, super over results, and statistical outliers.

### Page 12 — Match Center (`11_Match_Center.py`)
Ball-by-ball match replay. Select any match to view the full innings progression, fall of wickets, scoring flow, and partnership timeline.

### Page 13 — Tournament Structure (`12_Tournament_Structure.py`)
Season formats, playoff brackets, how the IPL structure has evolved over 18 seasons.

### Page 14 — Explorer (`13_Explorer.py`)
Custom query builder with 9 entity types, 58 preset SQL queries across 11 categories, a user guide, and a data dictionary. Supports filtering by season, team, player, venue, match phase, and more.

---

## Tech Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | Streamlit | >= 1.45.0 | Multi-page web application |
| Charts | Plotly | >= 6.0.0 | Interactive visualizations |
| Query Engine | DuckDB | >= 1.2.0 | In-process SQL on parquet files |
| Data Format | Apache Parquet | via PyArrow >= 18.0.0 | Columnar compressed storage |
| Data Processing | Pandas | >= 2.2.0 | DataFrame operations in pipeline |
| Numerical | NumPy | >= 1.26.0 | Numerical computations |
| Testing | pytest | >= 8.0.0 | 25 automated tests |
| Language | Python | 3.11 | Runtime |

---

## Cricket Terminology Reference

| Term | Definition |
|------|-----------|
| Ball / Delivery | A single bowling action. 6 legal deliveries make 1 over. |
| Over | A set of 6 legal deliveries bowled by one bowler. A T20 innings has 20 overs max. |
| Runs | Points scored. Batter can score 0-6 runs per delivery by running or hitting boundaries. |
| Four (4) | Ball reaches the boundary rope along the ground. Scores 4 runs. |
| Six (6) | Ball clears the boundary rope without bouncing. Scores 6 runs. |
| Boundary | Either a four or a six. |
| Dot Ball | A delivery where the batter scores 0 runs. Builds pressure on the batting side. |
| Wicket | A batter getting out (dismissed). 10 wickets end an innings. |
| Strike Rate (SR) | Batting: (Runs / Balls Faced) x 100. Higher means more aggressive scoring. |
| Batting Average | Runs / Times Dismissed. Higher means more consistent run-scoring. |
| Economy Rate | Bowling: (Runs Conceded / Balls Bowled) x 6. Lower means more restrictive. |
| Bowling Strike Rate | Balls Bowled / Wickets Taken. Lower means more frequent wicket-taking. |
| No-Ball | An illegal delivery (front foot overstepping). Awards 1 extra run + free hit. Batter's runs still count. Does not count as a legal delivery. |
| Wide | A delivery too far from the batter to hit. Awards 1 extra run. Does not count as a legal delivery. |
| Maiden Over | An over where 0 runs are conceded off legal deliveries. |
| Powerplay | Overs 1-6. Fielding restrictions: only 2 fielders outside the 30-yard circle. Encourages aggressive batting. |
| Middle Overs | Overs 7-15. Up to 5 fielders outside the circle. Consolidation phase. |
| Death Overs | Overs 16-20. Final phase where batters attempt to maximize scoring. |
| Duck | A batter dismissed for 0 runs. |
| Golden Duck | A batter dismissed on the first ball faced (0 runs, 1 ball). |
| Orange Cap | Award for the highest run scorer in an IPL season. |
| Purple Cap | Award for the highest wicket taker in an IPL season. |
| Net Run Rate (NRR) | (Runs Scored / Overs Faced) - (Runs Conceded / Overs Bowled). Tiebreaker for teams on equal points. |
| Super Over | Tiebreaker when match scores are level. Each team bats 1 over (6 balls). |
| DLS Method | Duckworth-Lewis-Stern. Mathematical formula to set revised targets in rain-affected matches. |
| Innings | One team's turn to bat. A T20 match has 2 innings (one per team). |
| Chase | The 2nd innings where the batting team tries to surpass the 1st innings score. |
| Target | The score the chasing team needs to win (1st innings score + 1). |
| Required Run Rate (RRR) | Runs needed / Overs remaining. Used to gauge chase difficulty. |
| Run Out | A batter dismissed by the fielding side hitting the stumps while the batter is out of the crease. |
| Caught | A batter dismissed when a fielder catches the ball after the batter hits it, before it bounces. |
| Bowled | A batter dismissed when the ball hits the stumps directly from the bowler. |
| LBW | Leg Before Wicket. Batter dismissed when the ball would have hit the stumps but hit the batter's leg instead. |
| Stumped | A batter dismissed when the wicketkeeper removes the bails while the batter is out of the crease. |
| Qualifier | Playoff match where the winner advances. IPL uses Qualifier 1, Qualifier 2, and Eliminator. |
| Eliminator | Playoff match where the loser is eliminated from the tournament. |

---

## Testing

25 automated tests in `tests/test_project.py` covering:
- Parquet file existence and schema validation
- Data integrity assertions (no null match IDs, valid seasons, etc.)
- Constants validation (team colors, phase ranges, season ordering)
- Import checks for all source modules
- Pipeline output verification

Run tests: `python -m pytest tests/ --tb=short -q`

---

## Data Source

IPL Ball-by-Ball Dataset 2008-2025 from Kaggle by [chaitu20](https://www.kaggle.com/datasets/chaitu20/ipl-dataset2008-2025). Contains 278,205 delivery records across 1,169 matches.
