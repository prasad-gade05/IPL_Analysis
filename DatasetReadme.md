---
pretty_name: "IPL Dataset 2008-2025 (Enriched for ML)"
language:
  - en
license: cc0-1.0
task_categories:
  - tabular-classification
  - tabular-regression
  - time-series-forecasting
task_ids:
  - tabular-multi-class-classification
  - tabular-single-column-regression
  - multivariate-time-series-forecasting
tags:
  - cricket
  - ipl
  - sports-analytics
  - tabular-data
  - feature-engineering
  - parquet
size_categories:
  - 100K<n<1M
---

# Dataset Summary

This dataset is an enriched version of the **IPL Dataset 2008-2025**.  
It starts from the original Kaggle data and adds analytics-driven, derived attributes to improve usefulness for machine learning and advanced data analysis workflows.

# Modifications & Derived Attributes

The base data was extended with new engineered features created through extensive analytics.

The final enriched file adds **27 derived attributes**:

- `match_phase` - Phase bucket by over: powerplay, middle, death.
- `is_four` - `True` when a legal boundary four is hit.
- `is_six` - `True` when a legal boundary six is hit.
- `is_boundary` - `True` when delivery is either a four or six.
- `is_dot` - `True` for a legal dot ball (0 total runs).
- `consecutive_dots_before` - Count of consecutive dot balls immediately before the current ball.
- `is_sequence_breaker` - `True` when a non-dot ball ends a dot-ball streak.
- `dot_sequence_outcome` - Outcome after a dot-ball streak (`wicket`, `boundary`, `scoring_shot`, `other`).
- `partnership_id` - Running identifier for each batting partnership segment.
- `partnership_runs` - Cumulative runs in current partnership.
- `partnership_balls` - Cumulative legal balls in current partnership.
- `balls_remaining` - Legal balls left in chase innings.
- `runs_needed` - Runs still needed to reach target.
- `required_run_rate` - Required run rate at that ball in chase innings.
- `current_run_rate` - Current scoring rate at that ball.
- `run_rate_pressure` - Difference between required and current run rates.
- `batting_position_bucket` - Batting order group: top_order, middle_order, lower_middle, tail.
- `is_maiden` - `True` if bowler's over conceded 0 runs in legal deliveries.
- `over_runs` - Total runs conceded in the over by that bowler.
- `over_dots` - Dot balls in that over.
- `over_boundaries` - Boundaries conceded in that over.
- `over_wickets` - Wickets taken in that over.
- `is_super_over` - `True` for super-over innings (innings 3/4).
- `bowling_stint` - Running stint ID when bowler changes during innings.
- `spell_number` - Spell count for each bowler within innings.
- `is_close_match` - `True` for close finishes (<=10 runs or <=2 wickets margin).
- `toss_winner_is_batting` - `True` when toss winner chose batting first.

# Data Format

The published dataset is stored in **`.parquet`** format for efficient loading and processing.

```python
from datasets import load_dataset

# From Hugging Face Hub
ds = load_dataset("prasad-gade05/ipl-enriched-2008-2025")

# Optional: load local parquet files directly
# ds = load_dataset("parquet", data_files={"train": "path/to/data.parquet"})
```

# Usage

This dataset can be used for:

- Match outcome prediction
- Player performance analytics
- Team strategy analysis
- Feature-driven benchmarking for tabular ML models
- Historical trend modeling across IPL seasons

# Acknowledgements / Attribution

Original base dataset:

- **Name:** IPL Dataset 2008-2025
- **Source:** Kaggle
- **Creator:** **chaitu20**
- **URL:** https://www.kaggle.com/datasets/chaitu20/ipl-dataset2008-2025
- **Original License:** **CC0 (Public Domain)**

This Hugging Face version includes additional feature engineering and analytics-derived columns built on top of that original CC0 dataset.
