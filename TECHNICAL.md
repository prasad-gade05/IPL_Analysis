# Technical Documentation - IPL Analytics Platform

## 1. Architecture

The app is a local-analytics stack:

```text
Raw CSV
  -> 3-step preprocessing pipeline
  -> processed parquet datasets
  -> DuckDB views
  -> Streamlit pages
  -> Plotly charts / semantic result tables
```

There is no separate backend API. DuckDB runs in-process inside the Streamlit app.

## 2. Preprocessing pipeline

Pipeline entry point: `Data\preprocessing\run_pipeline.py`

### Step 1 - `01_clean.py`

- drops constant or empty raw columns
- standardizes team names
- canonicalizes venue names
- parses result margins and stage information
- adds delivery numbering fields
- writes `ball_by_ball_cleaned.parquet`

Output after cleaning:

- `ball_by_ball_cleaned.parquet`: **278,205 rows x 63 columns**

### Step 2 - `02_derive_features.py`

- adds match phase labels
- adds dot, four, six, boundary and wicket helper flags
- adds partnership tracking
- adds chase pressure fields such as `current_run_rate` and `required_run_rate`
- adds over-level fields such as `over_runs`, `over_dots`, `over_boundaries`, `over_wickets`, `is_maiden`
- adds spell and context flags

Output after feature engineering:

- `ball_by_ball.parquet`: **278,205 rows x 90 columns**

### Step 3 - `03_build_aggregates.py`

This stage produces the app-facing analytical datasets:

| Output file | Rows | Purpose |
| --- | ---: | --- |
| `match_summary.parquet` | 1,169 | One row per match |
| `player_season.parquet` | 3,138 | Player-team-season roster mapping |
| `matchups.parquet` | 29,533 | Batter vs bowler aggregates |
| `venue_stats.parquet` | 42 | Venue scoring and result summaries |
| `powerplay_stats.parquet` | 2,365 | Powerplay innings summaries |
| `dot_sequences.parquet` | 34 | Outcomes after dot-ball streaks |
| `season_structure.parquet` | 18 | Season-level metadata |
| `player_batting_match.parquet` | 17,708 | Per-innings batting cards |
| `player_bowling_match.parquet` | 13,878 | Per-innings bowling cards |
| `partnerships.parquet` | 15,696 | Partnership-level summaries |
| `dismissal_patterns.parquet` | 2,089 | Dismissal types by player |
| `dismissal_by_phase.parquet` | 3,446 | Dismissal types by player and phase |
| `team_season.parquet` | 156 | Team-by-season results |
| `points_table.parquet` | 156 | Points table with NRR |
| `team_match_results.parquet` | 2,338 | Team result row per match |
| `over_summary.parquet` | 45,034 | Over-level innings summaries |
| `innings_tags.parquet` | 17,708 | Innings-level tags for semantic filtering |
| `player_season_metrics.parquet` | 3,137 | Player-season batting and bowling summary metrics |

That is **18 app-facing aggregate parquet files**, plus the feature parquet `ball_by_ball.parquet`.

## 3. Data-integrity rules that matter

Several cricket-specific rules are enforced because the same mistakes were easy to make in multiple visuals:

- batting run totals use the correct batting fields, while bowling conceded runs use `runs_bowler`
- wicket logic uses real dismissal semantics, not placeholder non-dismissal values
- batting ball counts use legal-ball logic where required
- milestone questions are resolved from ball-level progression, not final innings totals
- chase visuals use stored target context where needed, including rain-affected matches
- unsupported semantic questions are rejected instead of guessed

The codebase also keeps verified aggregate consistency checks for:

- **703 batters** with zero mismatches between aggregate and ball-level batting totals
- **550 bowlers** with zero mismatches between aggregate and ball-level bowling totals

## 4. DuckDB query layer

Source: `src\db\connection.py`

On app startup the project registers **19 parquet-backed DuckDB views**:

| View | Source parquet | Rows |
| --- | --- | ---: |
| `balls` | `ball_by_ball.parquet` | 278,205 |
| `matches` | `match_summary.parquet` | 1,169 |
| `player_season` | `player_season.parquet` | 3,138 |
| `player_batting` | `player_batting_match.parquet` | 17,708 |
| `player_bowling` | `player_bowling_match.parquet` | 13,878 |
| `team_match_results` | `team_match_results.parquet` | 2,338 |
| `over_summary` | `over_summary.parquet` | 45,034 |
| `innings_tags` | `innings_tags.parquet` | 17,708 |
| `player_season_metrics` | `player_season_metrics.parquet` | 3,137 |
| `matchups` | `matchups.parquet` | 29,533 |
| `venues` | `venue_stats.parquet` | 42 |
| `partnerships` | `partnerships.parquet` | 15,696 |
| `dot_sequences` | `dot_sequences.parquet` | 34 |
| `powerplay` | `powerplay_stats.parquet` | 2,365 |
| `season_meta` | `season_structure.parquet` | 18 |
| `dismissals` | `dismissal_patterns.parquet` | 2,089 |
| `dismissals_phase` | `dismissal_by_phase.parquet` | 3,446 |
| `team_season` | `team_season.parquet` | 156 |
| `points_table` | `points_table.parquet` | 156 |

Every page query and every semantic query runs against these views.

## 5. Streamlit application surface

Navigation is defined in `app.py`. The current app has **15 pages**:

1. `00_Home.py`
2. `01_Season_Hub.py`
3. `02_Leaderboards.py`
4. `03_Player_Profile.py`
5. `04_Team_Profile.py`
6. `05_Venue_Intelligence.py`
7. `06_Head_to_Head.py`
8. `07_Phase_Analysis.py`
9. `08_Pressure_Momentum.py`
10. `09_Trends_Evolution.py`
11. `10_Records_Anomalies.py`
12. `11_Match_Center.py`
13. `12_Tournament_Structure.py`
14. `13_Explorer.py`
15. `14_Ask_Anything.py`

### Explorer

`pages\13_Explorer.py` now exposes:

- query builder
- 58 preset queries across 11 categories
- semantic search tab
- guide and data dictionary tabs

### Ask Anything

`pages\14_Ask_Anything.py` is a dedicated deterministic semantic search page with:

- supported example prompts
- assumptions and warning text
- generated SQL
- result tables and charts
- related follow-up prompts

## 6. Deterministic semantic search

Semantic code lives in `src\semantic\`.

Key files:

- `planner.py` - maps supported natural-language prompts to a normalized query plan
- `compiler.py` - compiles the plan into whitelisted SQL
- `service.py` - executes the plan/compile/query/explain flow
- `explain.py` - human-readable assumptions and warnings
- `examples.py` - shipped supported example prompts

### What it is

This is **not** free-form text-to-SQL.

The engine is intentionally narrow:

1. detect a supported query family
2. normalize filters and thresholds
3. compile only approved SQL patterns
4. execute on DuckDB views
5. explain assumptions in the UI

### Current shipped coverage

`src\semantic\examples.py` contains **40 supported example prompts**.

Supported families include:

- hat-tricks and other sequence events
- wickets in an over, maidens, wicket maidens, perfect overs
- wicket, maiden, dot-ball, boundary and scoring-shot streaks
- ducks, golden ducks and innings-by-balls questions
- dismissal-type families
- Orange Cap / Purple Cap history
- chase records, near misses and threshold-based season consistency

### Accuracy behavior

Recent hardening in the semantic layer includes:

- season filtering on streak leaderboards is applied after streak formation so cross-season streaks are not fragmented incorrectly
- year phrases such as `2024 for V Kohli` are not misread as `4-fors`
- unsupported questions are surfaced as unsupported instead of forced through a weak interpretation

## 7. Per-visual control framework

The configurable-visual system is built from:

- `src\utils\control_schema.py`
- `src\utils\control_renderer.py`
- `src\utils\visual_specs.py`
- `src\visualizations\card_renderer.py`

### What it does

Each visual can declare a local `VisualSpec` and render only the controls that make sense for that visual:

- season range
- result limit
- minimum qualification thresholds
- innings selector
- local team or category selectors
- boolean toggles where needed

### Where it is used

The local-control rollout now covers the main analytics pages:

- Home
- Season Hub
- Leaderboards
- Player Profile
- Team Profile
- Venue Intelligence
- Head-to-Head
- Phase Analysis
- Pressure & Momentum
- Trends & Evolution
- Records & Anomalies
- Tournament Structure

`Match Center` intentionally remains context-driven because arbitrary local control overrides would distort match-specific interpretation.

## 8. Tech stack

| Component | Technology | Purpose |
| --- | --- | --- |
| UI | Streamlit | Multi-page web app |
| Charts | Plotly | Interactive charts |
| Query engine | DuckDB | Analytical SQL on parquet |
| Storage | Parquet / PyArrow | Columnar datasets |
| Processing | Pandas / NumPy | Pipeline and transformations |
| Testing | pytest | Automated validation |
| Language | Python 3.11 | Runtime |

## 9. Testing

Test file: `tests\test_project.py`

Current repository result:

- `python -m pytest tests\ --tb=short -q`
- **52 passed**

Coverage in the suite includes:

- processed file existence
- schema and row-level sanity checks
- constants and helper validation
- import checks
- pipeline output expectations
- semantic planner/compiler regression checks

## 10. Data source

The source dataset is the public IPL ball-by-ball dataset from Kaggle by **chaitu20**.
