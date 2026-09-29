# Plan — California demand forecasting (Walmart M5)

PACE stage: **Plan**. This document decides the question, the scope, the score, and the baseline. It does not fit a model, tune a parameter, or report an accuracy number. Those belong to Analyze and Construct.

The study path is: read this page, then the checks in [What Analyze will check](#what-analyze-will-check). The project README points here and keeps the later PACE stages as placeholders until they are written.

## Business question

How many units will each item sell, in each California Walmart store, on each of the next 28 days?

Two people use the answer, at two grains:

- A **replenishment planner** needs the forecast at **item–store–day**. That is the series the shelf is ordered from.
- A **category manager** needs the same forecast **rolled up to category–store–week**. That is the view in an executive meeting. We will not build a second model for that view. We will add up the item–store–day forecasts (bottom-up), so the weekly chart is the same forecast, just summed.

The business question is not "what is the dollar sales forecast." Dollar sales mix price and units. Replenishment orders units. Price is a feature we may use later, not the target.

## Why accuracy matters (units of safety stock, not dollars)

A forecast is an input to inventory, not the inventory decision itself. Turning error into a reorder point is **project 02**. This project only has to get the direction right.

Safety stock is the extra units held so that ordinary forecast misses do not empty the shelf. In the usual textbook form it grows with how wide the forecast errors are over the lead time: a bigger typical miss means **more units** of buffer to hold the same service level. A tight forecast means fewer units of buffer. That is the link between accuracy and inventory, stated in units.

Bias has a direction, and the direction matters more than a single average error:

- **Biased high** means the average forecast sits above actual demand. The store orders as if it will sell more than it does. On-hand inventory rises. Safety stock placed on top of an already high forecast makes the extra inventory larger, not smaller.
- **Biased low** means the average forecast sits below actual demand. The store orders too little. Shelves stock out even when the absolute error looks modest, because the misses all point the same way.

We will **not** convert that into dollars here. A dollar figure needs a holding-cost rate and a margin, and this dataset does not give us those. Any dollar number at this stage would be invented. Project 02 is where service level and inventory cost are in scope.

## Scope, and why it is this wide

| Decision | Choice | Why |
|---|---|---|
| Geography | California only | M5 covers three states (CA, TX, WI) and ten stores. California is four stores. That is enough to see store differences and small enough to run on a laptop. |
| Stores | `CA_1`, `CA_2`, `CA_3`, `CA_4` | These are the four California stores in the file. No other CA store ids exist in M5. |
| Horizon | Next **28 days** | That is M5's official forecast horizon: four weeks, produced from one forecast origin. We are not forecasting one day ahead and rolling forward inside the test window. |
| Target | Daily **unit** sales | The evaluation series is units (`sales_train_evaluation`), not dollars. |
| Forecast grain | Item–store–day | One row of the sales file is already one item in one store. Expected size: 3,049 items × 4 stores = **12,196 series**. Analyze will confirm the filter. |
| Executive grain | Category–store–week | Sum of the item–store–day forecasts. Week means Walmart's week (`wm_yr_wk`), which runs Saturday–Friday (`wday` 1 is Saturday), not Monday–Sunday. |
| What we will not forecast | The other six stores; dollar sales; a separate model at the weekly grain | See [Out of scope](#out-of-scope). |

The full competition is 3,049 products × 10 stores = 30,490 series and about 450 MB of CSV. Cutting to California drops the series count to about 40% of the file (4 of 10 stores) without dropping the hard part, which is intermittent item-level demand.

## Train and test

All scoring uses data we already have. We do **not** forecast the Kaggle days that were never published as actuals (`d_1942`–`d_1969`, 2016-05-23 through 2016-06-19). Those actuals are not in the files, so we could not score them.

**Test window:** the last 28 days of `sales_train_evaluation`.

- Columns `d_1914` through `d_1941`.
- Dates **2016-04-25 (Monday) through 2016-05-22 (Sunday)**, from `calendar.csv`.

**Train window:** every day before that.

- Columns `d_1` through `d_1913`.
- Dates **2011-01-29 through 2016-04-24**.
- That is exactly the span of `sales_train_validation`. The validation file is the same history with the test days removed. Analyze will check that the two files agree on `d_1`–`d_1913` for the California rows, so we are not mixing two histories.

One origin, one 28-day block. We will not use an actual from inside the test window to forecast a later day in that window. That rule is what makes the baseline below the right naive model.

The holdout is not a quiet four weeks. The calendar already shows, inside those 28 days: Pesach End, Orthodox Easter, Cinco de Mayo, Mother's Day, and a run of `snap_CA = 1` days (2016-05-01 through 2016-05-10). It also does not line up with Walmart weeks: `wm_yr_wk` 11613 contributes only Monday–Friday, 11614–11616 are full Saturday–Friday weeks, and 11617 contributes only Saturday–Sunday. Analyze will treat the partial weeks as partial when it rolls up. None of that is a fitted result. It is the calendar, read so we do not pretend the test window is a typical anonymous month.

## Metrics

We will report four numbers. They answer different questions. None of them is computed in this stage.

### MAPE

Mean absolute percentage error.

In words: for each scored row, take the absolute gap between forecast and actual, divide by the actual, then average those ratios. Multiply by 100 to read it as a percent.

If we score each item–store–day, a row with actual 10 and forecast 12 contributes `|12 − 10| / 10 = 0.20` (20%). The MAPE is the average of those ratios.

**MAPE explodes or is undefined when actual is 0**, because the formula divides by actual. M5 has many zero-sales days. A MAPE that silently drops those days, or that divides by zero and becomes infinity, is not a usable score.

**Decision for zero-sales days:**

- Publish MAPE **only on days whose actual units are greater than zero**.
- Next to it, publish the **share of test days that were excluded** because actual was 0. If we hide that share, MAPE looks better than the business is.
- Also publish a sensitivity: the same MAPE with a **floor of 1 unit in the denominator**, so a zero-actual day contributes `|forecast − 0| / 1`. That stops the explosion without pretending the day did not happen. It is a sensitivity, not the headline MAPE.

### WAPE

Weighted absolute percentage error. In words: add up the absolute gaps, and divide by the sum of actual units. Multiply by 100 to read it as a percent.

`WAPE = (sum of |forecast − actual|) / (sum of actual)`.

WAPE stays defined as long as total actual units are not zero. A day with actual 0 still adds `|forecast|` to the numerator (a forecast of 3 units on a day that sold nothing is a 3-unit error) and adds nothing to the denominator. That is the right companion to MAPE. We will compute WAPE on **all** test days, zeros included.

WAPE is not the same thing as an average of percentages. One bad day on a huge item moves WAPE more than many bad days on a tiny item. That is what we want for a volume conversation, and it is why we still show MAPE beside it.

### Volume-weighted MAPE

Unweighted MAPE lets a tiny, intermittent item count as much as a high-volume grocery item. A hobby SKU that sells twice a month can post a 200% MAPE and pull the average as hard as a food SKU with a 10% MAPE.

In words: compute MAPE **per item–store series** on the test window (positive-actual days only, same rule as above). Then take a weighted average of those series MAPEs, where the weight is that series' **total actual units** in the test window. Divide by the sum of those units.

A series that sold 1 unit barely moves the number. A series that sold 1,000 units moves it a lot. This is the MAPE a category manager should look at. The unweighted MAPE is the one that tells us whether we are systematically bad at slow items.

If someone weights each *day's* percentage error by that day's actual units, the weights cancel and the result collapses toward WAPE (and zero-actual days drop out, because their weight is zero). We will **not** call that volume-weighted MAPE. Volume-weighted MAPE here means **series-level MAPE, weighted by series volume**. WAPE is reported separately, under its own name, so the two are not confused.

### Bias

In words: average forecast minus average actual, divided by average actual, times 100 so it reads as a percent of actual.

- **Positive bias:** forecast is too high, on average. Inventory inflates.
- **Negative bias:** forecast is too low, on average. Stockouts.

We will report bias in percent and also in units (average forecast minus average actual, not divided), at item–store over the 28 days and again after the category–store–week rollup. A model can win on MAPE and still be dangerously biased. Both numbers stay on the scorecard.

We will not use the M5 competition metric (WRMSSE) as the decision metric. It is a weighted, scaled error across the whole hierarchy and all ten stores. It is the right score for a Kaggle leaderboard. It is a poor score for explaining a replenishment miss to a planner. We may compute it later as a footnote. It is not the number this project is built around.

## Baseline and the stronger model

Nothing in this section is fitted. These are the methods Construct is allowed to build, and the reason each one is on the list.

### Baseline: seasonal naive, lag-28

For each item–store and each test day, the forecast is the **actual unit sales on that same weekday four weeks earlier**.

The lag is 28 because 28 is divisible by 7, so the weekday matches: the forecast for a Saturday is a Saturday. Retail demand repeats weekly. Saturday is not like Tuesday, and a method that ignores that will lose to a one-line baseline.

The lag is 28 rather than 7 because of the horizon rule above. We forecast all 28 days from a single origin, the day before the test window, and we may not use actuals from inside the window. A lag-7 forecast for the last day of the horizon would need the actual from seven days earlier, which is still inside the test window and unknown at origin time. A lag-28 forecast for every day in the window uses only the 28 days **before** the window (the last four weeks of training). Those actuals are known. Lag-28 is the seasonal naive that respects the M5 horizon. Lag-7 would be appropriate only if we updated the forecast every day with new actuals, which we are not doing.

This baseline needs no fitting. If LightGBM cannot beat it on WAPE and on bias, the model is not earning its complexity.

It is one observation, not an average of the last four weeks. Do not describe it as a four-week moving average. A moving average would be a different baseline and would blur the weekday.

### Stronger model: LightGBM

LightGBM (gradient-boosted trees) on features that are known before the horizon:

- **Lags and rolling history** of unit sales, computed from training actuals only. No test-window actuals.
- **Calendar:** weekday, month, Walmart week, event name and event type.
- **SNAP:** `snap_CA`, not the Texas or Wisconsin flags.
- **Price:** `sell_price` for that item, store, and Walmart week, and a simple change versus a recent week.

Why this model: one learner can share patterns across 12,196 series, it accepts lags and calendar flags without a hand-built seasonality formula, and it is fast enough for four stores on a laptop. Construct will fit it. Plan does not.

Leakage rule, written now so Construct cannot "accidentally" break it: a feature for a test day may use only information that would have been known on 2016-04-24. Price for a future Walmart week is allowed only if we treat the posted `sell_prices` row as known (the file contains it). Actual units from `d_1914` onward are never a feature.

### Prophet, category level only

Prophet is a check, not the item-level model. We will fit it on **category–store–day** series (3 categories × 4 stores = 12 series), as a classical trend-plus-weekly-seasonality comparison.

We will not fit Prophet once per item–store. That is about 12,196 separate models. It is too slow at this grain, and it does not use the cross-series structure that makes LightGBM the better item-level tool.

The Excel file described next is a third view of the same baseline, for a person who will not open a notebook. It is not a fourth modeling approach.

## Excel version

Interviewers often open a spreadsheet and nothing else. Construct will add one workbook:

- **One category, one store.** Analyze will pick the pair. The rule is: a series that is not mostly zeros, so a seasonal pattern is visible. FOODS is the likely category. The specific store is not chosen in Plan.
- Two columns of forecast over the same 28-day holdout: the **lag-28 seasonal naive**, and one **simple Excel forecast** (Excel's forecast function or an equivalent that a reviewer can see the formula for).
- The same metrics as the Python path, on that one series, so the spreadsheet and the notebook cannot disagree about the definition.

The workbook is a teaching and interview artifact. It is not the model we will trust for 12,196 series.

## Data on hand

No new download. Raw files already sit in `data/raw/` and are git-ignored. See [`data/README.md`](../data/README.md) for the source, the license, the download date (2026-09-28), and the row counts. Summary of what each file is for:

| File | What it is | How this project uses it |
|---|---|---|
| `sales_train_evaluation.csv` | One row per item–store. Identity columns (`id`, `item_id`, `dept_id`, `cat_id`, `store_id`, `state_id`) plus daily unit sales `d_1` … `d_1941` (2011-01-29 through 2016-05-22). 30,490 rows in the full file. | **Target.** Filter to `state_id = CA` (stores `CA_1`–`CA_4`). Last 28 day-columns are the test actuals. Earlier day-columns are the training actuals. |
| `sales_train_validation.csv` | Same identity columns and the same item–store rows, but the day columns stop at `d_1913` (2016-04-24). | The training window as its own file. Analyze checks that it matches evaluation on the overlapping days. We do not need it as a second source of truth if that check passes. |
| `calendar.csv` | One row per date, 2011-01-29 onward, with `d` (the day column name), `wm_yr_wk`, `weekday`, `wday`, `month`, `year`, event name/type (two slots), and `snap_CA`, `snap_TX`, `snap_WI`. | Joins a `d_` column to a real date. Supplies weekday, events, and the California SNAP flag. Also defines Walmart weeks for the executive rollup. |
| `sell_prices.csv` | `store_id`, `item_id`, `wm_yr_wk`, `sell_price`. One price per item–store–week, not per day. | Price feature only. Not the target. Weeks with no row are weeks we do not have a price (often weeks the item was not offered). |
| `sample_submission.csv` | Kaggle's submission template for the unpublished horizon. | **Not used.** Our test actuals are already in the evaluation file. |

`m5-forecasting-accuracy.zip` is the archive those CSVs came from. It is not an input to the analysis.

Categories in the file are `HOBBIES`, `HOUSEHOLD`, and `FOODS`. Departments sit under those (`HOBBIES_1`, `HOBBIES_2`, `HOUSEHOLD_1`, `HOUSEHOLD_2`, `FOODS_1`, `FOODS_2`, `FOODS_3`). The executive rollup is category, not department. Department is available if Analyze shows that one department behaves unlike the rest of its category.

## Out of scope

- **Inventory optimization.** Safety stock, reorder points, and EOQ are project 02. This plan only states the direction from bias and error to units of inventory.
- **Causal promo experiments.** Price and event flags may be features. We will not claim that a price change *caused* a sales change. The data is observational.
- **All 10 stores, and Texas and Wisconsin.** Including them would restate the full competition and is not needed to show store differences.
- **Dollar-sales forecasts and invented dollar impact.**
- **The unpublished Kaggle horizon** (`d_1942`–`d_1969`).
- **A second, independent forecast at category–week.** The executive view is a sum.
- **Model fitting, hyperparameter search, and accuracy tables.** Not in Plan.

## Risks

**Intermittent demand.** Many item–store series sell on a small share of days. The first rows of the evaluation file (hobby items) are long runs of zeros with occasional units of 1 or 2. A point forecast of "0.2 units" is a rate, not a shelf quantity. Analyze must show the share of zero days by category and store **before** any model is praised. A method that predicts zero every day can look acceptable on a badly defined MAPE and still miss every day that matters.

**Zeros and MAPE.** Covered above. If Construct reports a MAPE without the share of zero-actual days, the number is not interpretable. WAPE is on the scorecard so those days still create error.

**SNAP days in California.** `snap_CA` marks days when SNAP benefits are issued in California. Food demand often jumps on those days. The flag is not the same series as `snap_TX` or `snap_WI`. A California model that ignores `snap_CA`, or that copies another state's flag, will pile its food-category error onto the SNAP calendar. The test window itself contains ten SNAP days in a row in early May 2016. That is a feature of this holdout, not a reason to drop the holdout. It is a reason Analyze should plot FOODS against `snap_CA` before Construct fits anything.

**Events in this particular test window.** Religious and retail holidays fall inside the 28 days (listed above). A single 28-day holdout can flatter or punish a model that handles events well or badly. We will not add more cutoffs in Plan. We will label the events on the error charts so a bad week is not read as a bad model in general.

**Partial Walmart weeks.** The executive week is Saturday–Friday, and this holdout starts on Monday and ends on Sunday. Two of the five touched `wm_yr_wk` values are partial. Summing them and calling them "a week" would understate volume. Analyze will flag partial weeks, and the weekly score will either mark them or use only complete weeks. The daily score uses all 28 days either way.

**Missing prices.** `sell_prices` is weekly and is not a complete grid. An item can have no price row for a store-week. Construct may not fill that hole with a future actual or with a price from inside a gap in a way that uses the test outcome. Analyze will measure how often a California item–store–week has no price.

**Hierarchy that does not add up.** Avoided by construction: we forecast at the bottom and sum. We will not average a weekly model with a daily model and hope they match.

**One holdout.** A single origin cannot prove the model works in November the way it works in May. Plan accepts that. A rolling origin would be a Construct extension, not a reason to change the test window. The window stays the last 28 days so the split is the same one M5 used between the validation file and the evaluation file.

## Assumptions

- The evaluation file's unit columns are the actual demand we are willing to treat as demand. A zero can mean "did not sell" or "was not in stock." We cannot see stockouts separately. Analyze should not call every zero a demand zero without saying that.
- All four California stores sell the same item list. That is the M5 file layout (every item appears in every store). Analyze confirms it on the filtered rows.
- The forecast origin is the morning of 2016-04-25, with history through 2016-04-24. No later actuals.
- Walmart week is the week we roll up to, because price and the calendar are already in `wm_yr_wk`.
- Beating lag-28 on WAPE, without a worse bias, is the bar for keeping LightGBM. A model that only wins on unweighted MAPE by fitting noise on tiny items does not clear the bar.

## What Analyze will check

Analyze is still descriptive. It does not fit LightGBM or Prophet.

1. **Filter check.** Row count after `store_id` in (`CA_1`, `CA_2`, `CA_3`, `CA_4`). Expect 12,196. Confirm no other `state_id = CA` store. Confirm item counts match across the four stores.
2. **File agreement.** For those rows, `sales_train_validation` `d_1`–`d_1913` equals `sales_train_evaluation` on the same columns.
3. **Zero-sales share** by store and by category (and by department if a category is mixed). This is the number that tells us whether MAPE is even a fair headline.
4. **Weekday profile.** Mean units by `wday` for each category, so we can see the weekly repeat that justifies lag-28.
5. **SNAP.** Mean FOODS units on `snap_CA = 1` days versus other days, by store, compared with HOBBIES and HOUSEHOLD (which should move less). Same plot for the test window alone, because that window is SNAP-heavy.
6. **Events inside the holdout.** Mark 2016-04-30, 2016-05-01, 2016-05-05, and 2016-05-08 on a daily total chart. Decide whether any category–store pair is an outlier on those dates before we pick the Excel pair.
7. **Partial weeks.** Confirm the `wm_yr_wk` split documented above (11613 and 11617 partial; 11614–11616 complete) and choose how the weekly executive table will label them.
8. **Price coverage.** Share of item–store–weeks in the California training span with no `sell_prices` row.
9. **Excel pair.** Pick one category and one store using the zero-share results, and freeze that choice in the Analyze write-up.
10. **A printed lag-28 example for one series**, calculated by hand or in a sheet, so the baseline definition is visible before any model code exists. That is a worked example of the decision in this plan, not a model comparison.

## What the next stages are for

- **Analyze** writes up the checks above. Still no model leaderboard.
- **Construct** builds the lag-28 baseline, the LightGBM model under the leakage rule, the 12-series Prophet check, and the one-category Excel workbook. It reports MAPE (with the zero-day share), volume-weighted MAPE, bias, and WAPE.
- **Execute** says what a planner should do with a biased-high versus biased-low result, in units, and points inventory policy at project 02.

This Plan stage stops before any of that fitting.
