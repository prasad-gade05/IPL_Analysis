# Visual Accuracy Incident Report

## Incident summary

This incident was a **data-logic accuracy issue**, not a rendering issue.

Several visuals were showing numbers that looked plausible but were computed from the wrong fields, the wrong grain, or the wrong cricket semantics. The most urgent user-reported example was the milestone-speed bug: visuals for fastest fifties and similar records were using a batter's **final innings balls** instead of the **balls taken to reach the milestone**.

During the wider audit, the same class of problem appeared in other visuals as well:

- wickets were sometimes counted from placeholder non-dismissal values
- bowling visuals sometimes used batting run fields
- some chase visuals used the wrong target logic
- one over-profile chart was averaging ball-level runs while being labeled as an over-level average
- one match-center chart assumed a standard 20-over chase even for D/L matches

## Impact

The impact was user-facing accuracy risk in high-visibility pages:

- `pages\10_Records_Anomalies.py`
- `pages\02_Leaderboards.py`
- `pages\03_Player_Profile.py`
- `pages\04_Team_Profile.py`
- `pages\05_Venue_Intelligence.py`
- `pages\06_Head_to_Head.py`
- `pages\07_Phase_Analysis.py`
- `pages\08_Pressure_Momentum.py`
- `pages\11_Match_Center.py`
- `pages\12_Tournament_Structure.py`
- `pages\13_Explorer.py`
- `pages\00_Home.py`

This mattered because the affected visuals are the kind of charts users quote, screenshot, and trust as factual records.

## Root causes

### 1. Milestone-speed logic used the wrong ball count

The milestone visuals were reading `player_batting.balls`, which is the batter's **full innings balls faced**.

That is wrong for questions like:

- fastest fifty
- fastest hundred
- slowest fifty

The correct source is the cumulative ball-level state in `balls`, specifically `batter_runs` and `batter_balls`, and the correct calculation is the earliest ball where the batter reaches the milestone.

### 2. Non-dismissals were stored as filled values, not nulls

In cleaned data, non-dismissals are not left as null:

- `wicket_kind = 'not_out'`
- `player_out = 'none'`

That means logic such as:

- `wicket_kind IS NOT NULL`
- `player_out IS NOT NULL`

is unsafe and can silently count non-dismissal rows as wickets or dismissals.

### 3. Some bowling visuals used the wrong run field

Three run concepts exist in the processed data and they are not interchangeable:

- `runs_batter` -> batter-only scoring
- `runs_total` -> total runs in the innings context
- `runs_bowler` -> runs charged to the bowler

A few bowling visuals were using batter-oriented fields where bowling economy or conceded runs should have used `runs_bowler`.

### 4. Some charts mixed row grain and chart label

At least one player over-profile chart was labeled as an over-level average, but the SQL was averaging `runs_batter` at ball grain. That undercounted the intended result and produced a chart that was internally inconsistent with its title.

### 5. Chase-target logic was inconsistent across pages

Some visuals needed the cricket target as:

- `first innings score + 1`

and some D/L matches needed the stored revised target from:

- `runs_target`

Using the wrong target source created incorrect chase labels and, in D/L matches, a wrong required-run-rate chart.

### 6. Historical knockout stages were partially excluded

Some queries filtered only modern playoff labels and missed older stage names such as:

- `Semi Final`
- `Elimination Final`
- `3rd Place Play-Off`

## What was fixed

### `pages\10_Records_Anomalies.py`

Fixed the milestone-speed visuals by adding milestone-specific logic that derives the earliest ball where the batter reached the milestone.

Updated:

- fastest fifties
- fastest centuries
- slowest fifties

Also updated the display so the distinction is explicit:

- `Balls to 50` / `Balls to 100`
- `Final Balls`

### `pages\02_Leaderboards.py`

Fixed successful chase target display to show the actual target to win, not just the first-innings score.

### `pages\04_Team_Profile.py`

Fixed highest successful chase target display to use the correct chase target.

### `pages\03_Player_Profile.py`

Fixed multiple issues:

- bowling wicket logic now uses `bowler_wicket`
- bowling conceded runs and economy now use `runs_bowler`
- batting over-by-over chart now averages **over totals per innings**, not ball-level runs
- dismissal views no longer treat `retired hurt` as a wicket-like dismissal event for those charts
- bowling over profile no longer drops extra-run deliveries from the runs conceded path

### `pages\05_Venue_Intelligence.py`

Fixed venue run-rate logic to use total innings runs instead of batter-only runs where the chart is about run rate, not batter scoring.

Also fixed dismissal-type filtering to exclude non-dismissal placeholders and `retired hurt`.

### `pages\06_Head_to_Head.py`

Fixed bowling comparison logic:

- wickets -> `SUM(bowler_wicket)`
- runs conceded / economy -> `runs_bowler`

### `pages\07_Phase_Analysis.py`

Fixed several phase visuals:

- wicket counts now exclude `not_out` and `retired hurt`
- top bowlers use `bowler_wicket`
- economy uses `runs_bowler`
- batting average denominator now uses real dismissals of that batter

### `pages\08_Pressure_Momentum.py`

Fixed dismissal-probability logic so wickets are not inferred from placeholder non-dismissal values.

Also corrected chase-target handling in chase visuals.

### `pages\11_Match_Center.py`

Fixed the worm / chase context logic:

- target line now uses stored `runs_target` for chase innings when available
- the required-run-rate chart now uses processed `current_run_rate` and `required_run_rate`
- for `D/L` matches, the required-run-rate chart is intentionally hidden because the processed data does not yet store the revised over limit, and showing a hard-coded 20-over version would be misleading

### `pages\12_Tournament_Structure.py`

Fixed knockout filtering to include all non-league stage values, not only modern playoff names.

### `pages\13_Explorer.py`

Fixed multiple preset and builder issues:

- phase bowling presets now use `runs_bowler`
- bowling wicket counts use `bowler_wicket`
- death-over batting strike rate uses legal-ball denominator without dropping no-ball run rows from the numerator path
- knockout preset uses stage logic that includes historical non-league rounds
- dismissal distributions exclude non-dismissal placeholders and `retired hurt`
- builder wicket filtering uses real-dismissal semantics

### `pages\00_Home.py`

Fixed headline metrics:

- total runs now use `runs_total`
- total wickets exclude `not_out` and `retired hurt`

## Validation performed

### Code validation

- `python -m compileall app.py pages src Data\preprocessing`
- `python -m pytest tests\ --tb=short -q`

Result at incident close:

- compile succeeded
- test suite result at that time: **25 passed**

Current repository state after later semantic-search and per-visual-control work:

- `python -m pytest tests\ --tb=short -q` -> **52 passed**

### Data validation highlights

These checks were run directly against the processed DuckDB/parquet views:

#### Milestone bug was real

Examples where final innings balls differ materially from balls to fifty:

- `CH Gayle`: `17` balls to 50 vs `65` final balls in the innings
- `BB McCullum`: `32` vs `73`
- `SE Marsh`: `27` vs `68`
- `PC Valthaty`: `23` vs `63`
- `DA Warner`: `20` vs `59`

This confirms the original fastest-fifty style logic was genuinely wrong before the fix.

#### Home headline runs were undercounting extras

- `SUM(runs_total) = 374283`
- `SUM(runs_batter) = 355373`

Difference:

- `18910` runs

That confirms the old home-page total runs metric was missing extras.

#### Phase wicket counts now reflect real dismissals

Validated real-dismissal counts:

- powerplay: `3369`
- middle: `5342`
- death: `5095`

#### D/L target mismatch was real

Validated samples where stored chase target differs from `team1_score + 1`:

- match `336022`: `119` vs stored target `89`
- match `336025`: `150` vs stored target `53`
- match `392183`: `105` vs stored target `54`
- match `392186`: `159` vs stored target `69`
- match `392214`: `186` vs stored target `187`

That confirms Match Center needed to use stored chase targets instead of reconstructing them from the first innings score.

#### Historical knockout stages exist in the data

Validated non-league stages:

- `3rd Place Play-Off`
- `Elimination Final`
- `Eliminator`
- `Final`
- `Qualifier 1`
- `Qualifier 2`
- `Semi Final`

## Final status before push

At the end of the final pass:

- no remaining high-confidence logic bugs were found in the changed areas
- compile passed
- tests passed
- targeted DuckDB validations matched the intended logic

Important limit:

This audit substantially improved correctness and removed the confirmed bugs above, but no software audit can honestly claim perfect accuracy forever. If you want the next level of safety, the best follow-up is to add page-level data assertions for the bug classes found here:

- milestone-to-threshold tests
- dismissal-semantic tests
- bowling-field semantic tests
- chase-target tests
- D/L target tests

## Files changed in this incident response

- `pages\00_Home.py`
- `pages\02_Leaderboards.py`
- `pages\03_Player_Profile.py`
- `pages\04_Team_Profile.py`
- `pages\05_Venue_Intelligence.py`
- `pages\06_Head_to_Head.py`
- `pages\07_Phase_Analysis.py`
- `pages\08_Pressure_Momentum.py`
- `pages\10_Records_Anomalies.py`
- `pages\11_Match_Center.py`
- `pages\12_Tournament_Structure.py`
- `pages\13_Explorer.py`
