# Kaggle Metadata — ipl-enriched-dataset (IPL Dataset 2008-2026, Enriched for ML)

Kaggle dataset name: **ipl-enriched-dataset**. Copy the blocks below into the matching fields on the Kaggle dataset editor.

---

## 1. Subtitle

> Every ball of IPL 2008-2026: 296K ball-by-ball records across 1,243 matches, enriched with 27 ML-ready features (phases, dot-ball pressure, chase metrics, partnerships, bowler spells).

---

## 2. About Section

Paste the block below into the **About** field.

```markdown
## Overview

A ball-by-ball dataset of every Indian Premier League (IPL) delivery from **2008 to 2026** (19 seasons, 1,243 matches, 295,732 deliveries), enriched with **27 engineered features** to make it directly usable for machine learning and advanced sports analytics.

This is not just raw scorecard data — it adds analytics-driven context on top of every single delivery: match phase, dot-ball pressure sequences, chase dynamics (RRR / CRR), partnership tracking, bowler spell structure, maiden overs, and close-match context.

## Dataset snapshot

| Metric | Value |
|---|---|
| Deliveries | 295,732 |
| Columns | 90 (63 base + 27 derived) |
| Seasons | 2008 - 2026 (19) |
| Matches | 1,243 |
| Batters | 738 |
| Bowlers | 577 |
| Franchises | 15 |
| Venues | 37 |
| Super-over deliveries | 163 |

## What was added (27 derived features)

**Match & phase context**
- `match_phase` - powerplay / middle / death buckets
- `is_super_over` - super-over deliveries (innings 3/4)
- `is_close_match` - wins by <=10 runs or <=2 wickets

**Delivery outcomes**
- `is_four`, `is_six`, `is_boundary`, `is_dot` - legal boundary and dot-ball flags
- `consecutive_dots_before` - dot-ball streak length before each delivery
- `is_sequence_breaker` - the delivery that ends a dot-ball streak
- `dot_sequence_outcome` - how a streak ended (wicket / boundary / scoring shot / other)

**Chase & pressure (2nd innings)**
- `balls_remaining`, `runs_needed`, `required_run_rate`, `current_run_rate`, `run_rate_pressure`

**Partnerships**
- `partnership_id`, `partnership_runs`, `partnership_balls`

**Bowling structure**
- `is_maiden`, `over_runs`, `over_dots`, `over_boundaries`, `over_wickets`
- `bowling_stint`, `spell_number`

**Player context**
- `batting_position_bucket` - top_order / middle_order / lower_middle / tail
- `toss_winner_is_batting`

## Cleaning & normalization applied

- Season labels standardized to integers (e.g. `2007/08` -> `2008`)
- Overs re-indexed from 0 to 1-based; `ball_no` recomputed
- Team names modernized (e.g. `Delhi Daredevils` -> `Delhi Capitals`, `Kings XI Punjab` -> `Punjab Kings`)
- Venue names deduplicated and standardized (e.g. `Sardar Patel Stadium, Motera` -> `Narendra Modi Stadium`)
- `Unknown` stages reconstructed per season from match sequence (League / Qualifier 1 / Eliminator / Qualifier 2 / Semi Final / Final)
- `win_outcome` parsed into `win_margin_value` + `win_margin_type`
- Structural nulls filled with meaningful defaults (`no_extra`, `not_out`, `none`, `normal`, `no_dls`)

## Suggested use cases

- Match outcome prediction and win-probability modeling
- Run-rate / chase-pressure forecasting (time-series)
- Batter and bowler performance analytics with context-aware features
- Dot-ball pressure and momentum analysis
- Franchise, venue, and season trend studies
- Feature-engineering benchmarking for tabular ML models

## File format & license

- Single **`.parquet`** file (efficient columnar storage, ~5 MB) - no need to parse 100+ MB of CSV
- **License: CC0 (Public Domain)** - fully free to use, share, and modify

## Attribution

- Base data: **IPL Dataset (2008-2026)** by chaitu20 (Kaggle, CC0) - https://www.kaggle.com/datasets/chaitu20/ipl-dataset2008-2025
- Underlying source: ball-by-ball data from **Cricsheet** - https://cricsheet.org/
- Enrichment pipeline: 3-stage preprocessing (clean -> derive -> aggregate), see the project repo for full details
```

---

## 3. Provenance

Kaggle's Provenance editor has two boxes: **Sources** and **Collection Methodology**.

### 3a. Sources box

```markdown
1. **IPL Dataset (2008-2026)** by chaitu20 (Kaggle, CC0 license)
   URL: https://www.kaggle.com/datasets/chaitu20/ipl-dataset2008-2025
   A single CSV of ball-by-ball IPL deliveries from 2008-2026, in flattened Cricsheet format. (The dataset slug retains "2008-2025" from its original release; the author updated the same dataset in place to cover 2008-2026.)

2. **Cricsheet** (https://cricsheet.org/) - underlying origin of the base data
   Cricsheet publishes open, machine-readable ball-by-ball cricket data. The base CSV carries Cricsheet's standard schema (match_type, event_name, gender, team_type, balls_per_over, overs, match_number, review_* fields), indicating the raw deliveries were sourced from Cricsheet's IPL match files and flattened into one table.

3. **This dataset** - the enrichment layer
   The base CSV was run through a 3-stage, reproducible preprocessing pipeline (clean -> derive -> aggregate) that produced this enriched parquet. No new matches or deliveries were collected; all 27 additional attributes are computed from the base data.
```

### 3b. Collection Methodology box

```markdown
This dataset was built by taking an existing ball-by-ball IPL dataset and running it through a deterministic, reproducible 3-stage preprocessing pipeline:

**Stage 1 - Cleaning (10 steps)**
- Dropped 8 constant/uninformative columns (match_type, event_name, gender, team_type, balls_per_over, overs, match_number, power_surge_start; legacy releases carried Unnamed: 0 instead of power_surge_start)
- Fixed data types: dates parsed, seasons mapped to integers, over indexes converted from 0-based to 1-based
- Filled structural nulls with meaningful defaults (extra_type -> "no_extra", wicket_kind -> "not_out", result_type -> "normal", method -> "no_dls")
- Standardized team names across rename events (e.g. Delhi Daredevils -> Delhi Capitals)
- Standardized venue names across rename/reused stadium aliases (e.g. Sardar Patel Stadium -> Narendra Modi Stadium)
- Reconstructed "Unknown" match stages per season from match sequence (League / Qualifier 1 / Eliminator / Qualifier 2 / Semi Final / Final)
- Parsed win_outcome strings into structured win_margin_value + win_margin_type columns
- Added derived structural flags (is_chasing, has_review, is_super_over_match)
- Ran integrity validation (over range, bat position range, team_wicket <= 10, runs_total = runs_batter + runs_extras)

**Stage 2 - Feature engineering (11 blocks -> 27 derived attributes)**
- Match phase bucketing (powerplay / middle / death by over)
- Boundary, six, and dot-ball flags on legal deliveries
- Consecutive dot-ball sequence tracking with break-outcome classification
- Partnership tracking (runs and legal balls per partnership segment)
- Chase metrics for 2nd innings: balls remaining, runs needed, required run rate, current run rate, run-rate pressure
- Batting position bucketing (top order / middle order / lower middle / tail)
- Over-level bowling stats: maidens, runs, dots, boundaries, wickets per over
- Super-over flags (innings 3/4)
- Bowler spell tracking (stint IDs and spell numbers)
- Match context: close finishes (<=10 runs or <=2 wickets) and toss decision effects

**Stage 3 - Aggregation**
- Built 19 derived analytical views (match summaries, player-season metrics, venue stats, partnerships, dot sequences, powerplay stats, points tables, etc.) used by the companion analytics dashboard

All steps are idempotent and reproducible - running the pipeline again on the same base CSV yields identical output. The output is published as a single .parquet file for efficient storage and fast loading.
```

---

## Notes for verification

- All numbers above were verified against the actual enriched file (`Data/processed/ball_by_ball.parquet`) and the pipeline code (`Data/preprocessing/01_clean.py`, `02_derive_features.py`, `03_build_aggregates.py`).
- 295,732 rows x 90 columns, 1,243 matches, 19 seasons (2008-2026), 738 batters, 577 bowlers, 15 franchises, 37 venues, 163 super-over deliveries.
