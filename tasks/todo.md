# Plan: Update IPL Analytics Platform from 2008-2025 to 2008-2026

## Findings from data investigation (verified empirically)

The new raw file `Data/raw/IPL.csv` (295,732 rows x 64 cols) supersedes
`Data/raw/ipl_ball_by_ball.csv` (278,205 rows x 64 cols):

1. **Superset check PASSED**: all 1,169 old match_ids exist in the new file; the
   74 new matches are all season `2026` (2026-03-28 to 2026-05-31, 10 teams,
   74 matches, Final won by Royal Challengers Bengaluru).
2. **Schema deltas**:
   - `Unnamed: 0` column is gone (was dropped by cleaning anyway).
   - New all-null column `power_surge_start` must be dropped.
   - `striker_out` / `valid_ball` / `bowler_wicket` changed representation from
     True/False strings to 0/1 ints — pandas reads them as int64, and
     `astype(bool)` on int64 0/1 is still correct. NO fix needed.
3. **THREE format-breaking changes** in shared columns:
   - `date`: `18-04-2008` (DD-MM-YYYY) -> `2008-04-18` (YYYY-MM-DD).
     Current `pd.to_datetime(format="%d-%m-%Y")` would NaT every row. FIXED.
   - `batting_partners`: `('A', 'B')` tuple-string -> `A|B` pipe-separated.
     Partnership-id change detection still works, but the published parquet
     schema would silently change format. NORMALIZED back to tuple-string for
     dataset format stability.
4. **New venue**: `Shaheed Veer Narayan Singh International Stadium, Raipur`
   mapped to the pre-existing bare spelling of the same stadium.
5. **New season string**: `2026` added to SEASON_MAP in both
   `01_clean.py` and `src/utils/constants.py`; ALL_SEASONS extended to 2026.
6. 2026 stages: 70 `Unknown` + Q1/Eliminator/Q2/Final known -> existing
   step_07 logic fills Unknowns as League. Verified 0 Unknown remaining.
7. No new wicket kinds, teams, extra types, or toss decisions in 2026.
8. Base Kaggle dataset URL `chaitu20/ipl-dataset2008-2025` still resolves
   (404 for a `-2026` slug): author updated the same dataset in place. The
   attribution URL is kept, described coverage updated.
9. `Data/raw/` is gitignored; `Data/processed/*.parquet` IS tracked in git
   (needed for Streamlit deploy) -> regenerated parquets are expected repo
   changes (user commits).
10. Many pytest "golden" assertions are data-dependent. Strategy executed:
    run pipeline first, then tests, then update ONLY assertions verified
    correct via direct DuckDB queries.

## Checklist — ALL COMPLETE

### Phase A — Pipeline fixes
- [x] A1. `01_clean.py`: RAW_CSV -> IPL.csv; power_surge_start dropped;
      2026 in SEASON_MAP; Raipur venue mapped; dual-format date parsing
      (YYYY-MM-DD first, DD-MM-YYYY fallback, raises if unparseable);
      batting_partners pipe -> tuple-string normalization; docstring updated
- [x] A2. `constants.py`: SEASON_MAP + 2026; ALL_SEASONS -> 2008..2026

### Phase B — App season-boundary updates
- [x] B1. `filters.py` default -> (2008, 2026)
- [x] B2. query defaults: player_queries (3), team_queries (3), pressure_queries (1)
- [x] B3. `00_Home.py`: default range, slider max 2026, header 19 seasons / 1,240+ matches / 35+ venues
- [x] B4. `11_Match_Center.py` default season 2026
- [x] B5. `12_Tournament_Structure.py` default season 2026
- [x] B6. `09_Trends_Evolution.py` 2008 to 2026
- [x] B7. `13_Explorer.py` welcome: 19 seasons / 295,000+ records / 1,240+ matches
- [x] B8. `app.py` About: 19 seasons

### Phase C — Data regenerated
- [x] C1. Pipeline run: 295,732 rows -> cleaned 63 cols -> enriched 90 cols -> 19 aggregates
- [x] C2. Audit PASSED: 1,243 matches; seasons 2008-2026 (19); 0 Unknown stages;
      0 NaT dates; 2026 champion RCB; 37 venues; 15 franchises; 738 batters;
      577 bowlers; 163 super-over deliveries; batting_partners legacy format
      restored (0 pipe strings); Raipur 8 matches

### Phase D — Tests
- [x] D1. Structural assertions updated (rows 295,732; 19 seasons; BETWEEN 2008 AND 2026; raw CSV name)
- [x] D2. Golden assertion changes each verified independently via DuckDB:
      Gill 400+ streak 6->7 (scored 400+ every season 2020-2026);
      max maidens 14->15 (B Kumar, added maidens in 2026);
      RG Sharma caught 168->174; Rashid Khan LBWs 37->39;
      ALL_SEASONS length 18->19
- [x] D3. Full suite green: 71 passed

### Phase E — Docs & Kaggle metadata
- [x] E1. README.md: 19 seasons | 1,243 matches; 2008-2026; raw file `IPL.csv`; 71 pytest checks; source note
- [x] E2. TECHNICAL.md: all row counts, batters/bowlers, 71 passed
- [x] E3. DatasetReadme.md: 2008-2026 title/description; HF repo slug kept with note
- [x] E4. Kaggle_Metadata.md: 296K records / 295,732 deliveries / 1,243 matches /
      19 seasons / 738 batters / 577 bowlers / 37 venues / 163 super-over
      deliveries; dropped-columns note; attribution slug note; verification note

### Phase F — Cleanup & final audit
- [x] F1. Stale `Data/raw/ipl_ball_by_ball.csv` removed (verified strict subset)
- [x] F2. Grep sweep: remaining `2025` mentions are all legitimate
      (SEASON_MAP entries, attribution URL slugs, historical data facts in tests, this plan)
- [x] F3. `git status` reviewed; Streamlit boot smoke test HTTP 200; NO commits made (user commits)

## Review / verification section

- Final pytest result: **71 passed** (`python -m pytest tests\ --tb=short -q`)
- Verified 2026 headline facts: 74 matches, 2026-03-28 -> 2026-05-31, 10 teams,
  champion Royal Challengers Bengaluru, 4 super-over deliveries (KKR super-over
  win), stage reconstruction correct (70 league + Q1 + Eliminator + Q2 + Final)
- Kaggle numbers recomputed from regenerated `ball_by_ball.parquet`:
  295,732 x 90; 1,243 matches; 19 seasons; 738 batters; 577 bowlers;
  15 franchises; 37 venues; 163 super-over deliveries
