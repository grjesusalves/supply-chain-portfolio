# Plan — California demand forecasting (Walmart M5)

PACE stage: **Plan**. Before a single model is fit, this document fixes the question, the scope, the score and the baseline. It fits no model, tunes no parameter and reports no accuracy number; those tasks belong to Analyze and Construct, and keeping them out of this page is the point.

The study path is straightforward: read this page, then the checks in [What Analyze will check](#what-analyze-will-check). The project README points here, and it keeps the later PACE stages as placeholders until they are written.

## Business question

How many units will each item sell, in each California Walmart store, on each of the next 28 days?

Two people rely on the answer, and they need it at two different grains:

- A **replenishment planner** needs the forecast at **item–store–day**, because that is the series from which the shelf is ordered.
- A **category manager** needs the same forecast **rolled up to category–store–week**, because that is the view that reaches an executive meeting. Rather than build a second model for that view, we will add up the item–store–day forecasts (bottom-up), which means the weekly chart is the same forecast, simply summed.

The business question, then, is not "what is the dollar sales forecast." Dollar sales blend price and units, whereas replenishment orders units. Price is a feature we may use later — not the target.

## Why accuracy matters (units of safety stock, not dollars)

A forecast is an input to inventory, not the inventory decision itself. Turning error into a reorder point is the work of **project 02**; this project need only get the direction right.

Safety stock is the extra stock held so that ordinary forecast misses do not empty the shelf. In its usual textbook form, it grows with the width of the forecast errors over the lead time: a bigger typical miss means **more units** of buffer to hold the same service level, while a tight forecast means fewer. That is the pivotal link between accuracy and inventory, stated in units rather than money.

Bias has a direction, and that direction matters more than any single average error:

- **Biased high** means the average forecast sits above actual demand. The store orders as if it will sell more than it does, and on-hand inventory rises accordingly. Safety stock placed on top of an already high forecast makes the excess larger, not smaller.
- **Biased low** means the average forecast sits below actual demand. The store orders too little, and shelves stock out even when the absolute error looks modest, because the misses all point the same way.

We will **not** convert any of this into dollars here. A dollar figure requires a holding-cost rate and a margin, and this dataset provides neither; any dollar number at this stage would therefore be invented. Service level and inventory cost come into scope only in Project 02.

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

The full competition spans 3,049 products × 10 stores = 30,490 series and about 450 MB of CSV. Cutting to California reduces the series count to about 40% of the file (4 of 10 stores) without discarding the hard part, which is intermittent item-level demand.

## Train and test

All scoring relies on data we already hold. We do **not** forecast the Kaggle days whose actuals were never published (`d_1942`–`d_1969`, 2016-05-23 through 2016-06-19); those actuals are absent from the files, which means they could not be scored in any case.

**Test window:** the last 28 days of `sales_train_evaluation`.

- Columns `d_1914` through `d_1941`.
- Dates **2016-04-25 (Monday) through 2016-05-22 (Sunday)**, taken from `calendar.csv`.

**Train window:** every day before the test window.

- Columns `d_1` through `d_1913`.
- Dates **2011-01-29 through 2016-04-24**.
- That is exactly the span of `sales_train_validation`, which holds the same history with the test days removed. Analyze will check that the two files agree on `d_1`–`d_1913` for the California rows, so that we are not quietly mixing two histories.

The design is one origin and one 28-day block. No actual from inside the test window will be used to forecast a later day in that window; that rule, more than any other, is what makes the baseline below the right naive model.

The holdout, moreover, is not a quiet four weeks. The calendar already shows several events inside those 28 days — Pesach End, Orthodox Easter, Cinco de Mayo and Mother's Day — as well as a run of `snap_CA = 1` days (2016-05-01 through 2016-05-10). Nor does the window line up with Walmart weeks: `wm_yr_wk` 11613 contributes only Monday–Friday, 11614–11616 are full Saturday–Friday weeks, and 11617 contributes only Saturday–Sunday. Analyze will treat the partial weeks as partial when it rolls up. None of this is a fitted result. It is simply the calendar, read carefully so that we do not pretend the test window is a typical, anonymous month.

## Metrics

We will report four numbers. Each answers a different question, and none is computed at this stage.

### MAPE

Mean absolute percentage error.

In words: for each scored row, take the absolute gap between forecast and actual, divide it by the actual, and then average those ratios. Multiply by 100 to read the result as a percent.

If we score each item–store–day, a row with actual 10 and forecast 12 contributes `|12 − 10| / 10 = 0.20` (20%), and the MAPE is the average of all such ratios.

**MAPE explodes, or becomes undefined, when actual is 0**, because the formula divides by actual. Given that M5 contains a great many zero-sales days, a MAPE that silently drops those days, or that divides by zero and becomes infinite, is not a usable score.

**Decision for zero-sales days:**

- Publish MAPE **only on days whose actual units are greater than zero**.
- Alongside it, publish the **share of test days that were excluded** because actual was 0. Hiding that share would make MAPE look better than the business actually is.
- Publish a sensitivity as well: the same MAPE with a **floor of 1 unit in the denominator**, so that a zero-actual day contributes `|forecast − 0| / 1`. That stops the explosion without pretending the day never happened. It remains a sensitivity, however, not the headline MAPE.

### WAPE

Weighted absolute percentage error. In words: add up the absolute gaps, then divide by the sum of actual units. Multiply by 100 to read the result as a percent.

`WAPE = (sum of |forecast − actual|) / (sum of actual)`.

WAPE stays defined as long as total actual units are not zero. A day with actual 0 still adds `|forecast|` to the numerator — a forecast of 3 units on a day that sold nothing is a 3-unit error — while adding nothing to the denominator. That property makes it the right companion to MAPE, and we will therefore compute WAPE on **all** test days, zeros included.

WAPE is not the same thing as an average of percentages. One bad day on a huge item moves WAPE more than many bad days on a tiny one. That is precisely what a conversation about volume requires; that said, it is also why we still show MAPE beside it.

### Volume-weighted MAPE

Unweighted MAPE lets a tiny, intermittent item count for as much as a high-volume grocery item. A hobby SKU that sells twice a month can post a 200% MAPE and pull the average just as hard as a food SKU with a 10% MAPE.

In words: compute MAPE **per item–store series** on the test window, using positive-actual days only under the same rule as above. Then take a weighted average of those series MAPEs, where each weight is that series' **total actual units** in the test window, and divide by the sum of those units.

A series that sold 1 unit barely moves the number, whereas a series that sold 1,000 units moves it considerably. This is the MAPE a category manager should watch. The unweighted MAPE, by contrast, is the one that tells us whether we are systematically poor at slow items.

If someone instead weights each *day's* percentage error by that day's actual units, the weights cancel and the result collapses toward WAPE (and zero-actual days drop out, because their weight is zero). We will **not** call that volume-weighted MAPE. Here, volume-weighted MAPE means **series-level MAPE, weighted by series volume**, and WAPE is reported separately, under its own name, so that the two are never confused.

### Bias

In words: average forecast minus average actual, divided by average actual, times 100 so that it reads as a percent of actual.

- **Positive bias:** the forecast is too high on average, and inventory inflates.
- **Negative bias:** the forecast is too low on average, and the shelf stocks out.

We will report bias both in percent and in units (average forecast minus average actual, undivided), at item–store over the 28 days and again after the category–store–week rollup. A model can win on MAPE and still be dangerously biased, which is why both numbers stay on the scorecard.

We will not use the M5 competition metric (WRMSSE) as the decision metric. It is a weighted, scaled error across the whole hierarchy and all ten stores — the right score for a Kaggle leaderboard, yet a poor one for explaining a replenishment miss to a planner. We may compute it later as a footnote; it is not the number around which this project is built.

## Baseline and the stronger model

Nothing in this section is fitted. These are the methods Construct is permitted to build, together with the reason each one earns its place on the list.

### Baseline: seasonal naive, lag-28

For each item–store and each test day, the forecast is the **actual unit sales on that same weekday four weeks earlier**.

The lag is 28 because 28 is divisible by 7, so the weekday always matches: the forecast for a Saturday is drawn from a Saturday. Retail demand repeats weekly. Saturday is not like Tuesday, and a method that ignores the difference will lose to a one-line baseline.

The lag is 28 rather than 7 because of the horizon rule above. We forecast all 28 days from a single origin, the day before the test window, and we may not use actuals from inside that window. A lag-7 forecast for the last day of the horizon would need the actual from seven days earlier, which still lies inside the test window and is unknown at origin time. A lag-28 forecast for every day in the window, by contrast, uses only the 28 days **before** the window — the last four weeks of training — and those actuals are known. Lag-28 is therefore the seasonal naive that respects the M5 horizon. Lag-7 would be appropriate only if we updated the forecast daily with new actuals, which we are not doing.

This baseline requires no fitting at all. If LightGBM cannot beat it on WAPE and on bias, the model is not earning its complexity.

It is a single observation, not an average of the last four weeks, and it should not be described as a four-week moving average. A moving average would be a different baseline altogether, and it would blur the weekday.

### Stronger model: LightGBM

LightGBM (gradient-boosted trees) will be trained on features that are known before the horizon:

- **Lags and rolling history** of unit sales, computed from training actuals only, with no test-window actuals.
- **Calendar:** weekday, month, Walmart week, event name and event type.
- **SNAP:** `snap_CA`, rather than the Texas or Wisconsin flags.
- **Price:** `sell_price` for that item, store and Walmart week, together with a simple change versus a recent week.

The case for this model is threefold: a single learner can share patterns across 12,196 series, it accepts lags and calendar flags without a hand-built seasonality formula, and it runs fast enough for four stores on a laptop. Construct will fit it; Plan does not.

The leakage rule is written down now, so that Construct cannot "accidentally" break it: a feature for a test day may use only information that would have been known on 2016-04-24. Price for a future Walmart week is allowed only on the understanding that the posted `sell_prices` row counts as known (the file contains it). Actual units from `d_1914` onward are never a feature.

### Prophet, category level only

Prophet is a check, not the item-level model. We will fit it on **category–store–day** series (3 categories × 4 stores = 12 series) as a classical trend-plus-weekly-seasonality comparison.

We will not fit Prophet once per item–store, which would mean about 12,196 separate models. That is too slow at this grain, and it forgoes the cross-series structure that makes LightGBM the better item-level tool.

The Excel file described next offers a third view of the same baseline, for a person who will not open a notebook. It is not a fourth modeling approach.

## Excel version

Interviewers often open a spreadsheet and nothing else. Construct will therefore add one workbook:

- **One category, one store.** Analyze will pick the pair, under one rule: the series must not be mostly zeros, so that a seasonal pattern is visible. FOODS is the likely category; the specific store is not chosen in Plan.
- Two forecast columns over the same 28-day holdout: the **lag-28 seasonal naive**, and one **simple Excel forecast** (Excel's forecast function, or an equivalent whose formula a reviewer can see).
- The same metrics as the Python path, on that one series, so that the spreadsheet and the notebook cannot disagree about a definition.

The workbook is a teaching and interview artifact — not the model we will trust for 12,196 series.

## Data on hand

No new download is required. The raw files already sit in `data/raw/` and are git-ignored; [`data/README.md`](../data/README.md) records the source, the license, the download date (2026-09-28) and the row counts. The table below summarizes what each file is for:

| File | What it is | How this project uses it |
|---|---|---|
| `sales_train_evaluation.csv` | One row per item–store. Identity columns (`id`, `item_id`, `dept_id`, `cat_id`, `store_id`, `state_id`) plus daily unit sales `d_1` … `d_1941` (2011-01-29 through 2016-05-22). 30,490 rows in the full file. | **Target.** Filter to `state_id = CA` (stores `CA_1`–`CA_4`). Last 28 day-columns are the test actuals. Earlier day-columns are the training actuals. |
| `sales_train_validation.csv` | Same identity columns and the same item–store rows, but the day columns stop at `d_1913` (2016-04-24). | The training window as its own file. Analyze checks that it matches evaluation on the overlapping days. We do not need it as a second source of truth if that check passes. |
| `calendar.csv` | One row per date, 2011-01-29 onward, with `d` (the day column name), `wm_yr_wk`, `weekday`, `wday`, `month`, `year`, event name/type (two slots), and `snap_CA`, `snap_TX`, `snap_WI`. | Joins a `d_` column to a real date. Supplies weekday, events, and the California SNAP flag. Also defines Walmart weeks for the executive rollup. |
| `sell_prices.csv` | `store_id`, `item_id`, `wm_yr_wk`, `sell_price`. One price per item–store–week, not per day. | Price feature only. Not the target. Weeks with no row are weeks we do not have a price (often weeks the item was not offered). |
| `sample_submission.csv` | Kaggle's submission template for the unpublished horizon. | **Not used.** Our test actuals are already in the evaluation file. |

`m5-forecasting-accuracy.zip` is the archive from which those CSVs came. It is not an input to the analysis.

The file's categories are `HOBBIES`, `HOUSEHOLD` and `FOODS`, with departments beneath them (`HOBBIES_1`, `HOBBIES_2`, `HOUSEHOLD_1`, `HOUSEHOLD_2`, `FOODS_1`, `FOODS_2`, `FOODS_3`). The executive rollup is by category, not department. Department remains available, however, should Analyze show that one department behaves unlike the rest of its category.

## Out of scope

- **Inventory optimization.** Safety stock, reorder points and EOQ belong to project 02; this plan states only the direction from bias and error to units of inventory.
- **Causal promo experiments.** Price and event flags may serve as features, but we will not claim that a price change *caused* a sales change. The data is observational.
- **All 10 stores, and Texas and Wisconsin.** Including them would merely restate the full competition, and they are not needed to show store differences.
- **Dollar-sales forecasts and invented dollar impact.**
- **The unpublished Kaggle horizon** (`d_1942`–`d_1969`).
- **A second, independent forecast at category–week.** The executive view is a sum.
- **Model fitting, hyperparameter search and accuracy tables**, none of which belongs in Plan.

## Risks

**Intermittent demand.** Many item–store series sell on only a small share of days. The first rows of the evaluation file, all hobby items, are long runs of zeros punctuated by occasional units of 1 or 2. A point forecast of "0.2 units" is a rate, not a shelf quantity. Analyze must therefore show the share of zero days by category and store **before** any model is praised. After all, a method that predicts zero every day can look acceptable on a badly defined MAPE while missing every day that matters.

**Zeros and MAPE.** This was covered above, but it bears repeating: if Construct reports a MAPE without the share of zero-actual days, the number cannot be interpreted. WAPE is on the scorecard so that those days still register as error.

**SNAP days in California.** `snap_CA` marks the days on which SNAP benefits are issued in California, and food demand often jumps on those days. The flag is not the same series as `snap_TX` or `snap_WI`. A California model that ignores `snap_CA`, or that borrows another state's flag, will pile its food-category error onto the SNAP calendar. The test window itself contains ten consecutive SNAP days in early May 2016. That is a feature of this holdout rather than a reason to drop it; it is, however, a reason for Analyze to plot FOODS against `snap_CA` before Construct fits anything.

**Events in this particular test window.** Religious and retail holidays fall inside the 28 days, as listed above, and a single 28-day holdout can flatter or punish a model according to how well it handles them. We will not add further cutoffs in Plan. Instead, we will label the events on the error charts, so that a bad week is not mistaken for a bad model.

**Partial Walmart weeks.** The executive week runs Saturday–Friday, whereas this holdout starts on a Monday and ends on a Sunday. Two of the five `wm_yr_wk` values it touches are therefore partial, and summing them as though each were "a week" would understate volume. Analyze will flag partial weeks, and the weekly score will either mark them or use complete weeks only. The daily score uses all 28 days either way.

**Missing prices.** `sell_prices` is weekly, and it is not a complete grid: an item can lack a price row for a given store-week. Construct may not fill such a hole with a future actual, nor with a price from inside a gap in any way that draws on the test outcome. Analyze will measure how often a California item–store–week has no price.

**Hierarchy that does not add up.** This risk is avoided by construction: we forecast at the bottom and sum upward. We will not average a weekly model with a daily model and hope that they match.

**One holdout.** A single origin cannot prove that the model works in November as it does in May, and Plan concedes the point. That said, a rolling origin would be a Construct extension, not a reason to change the test window. The window stays at the last 28 days so that the split matches the one M5 itself used between the validation file and the evaluation file.

## Assumptions

- The evaluation file's unit columns are the actual demand we are willing to treat as demand. A zero can mean "did not sell" or "was not in stock," and since stockouts are not visible separately, Analyze should not call every zero a demand zero without saying so.
- All four California stores sell the same item list. That follows from the M5 file layout, in which every item appears in every store, and Analyze confirms it on the filtered rows.
- The forecast origin is the morning of 2016-04-25, with history through 2016-04-24 and no later actuals.
- The Walmart week is the unit of rollup, because price and the calendar are already keyed to `wm_yr_wk`.
- Beating lag-28 on WAPE, without a worse bias, is the bar LightGBM must clear to be kept. A model that wins only on unweighted MAPE, by fitting noise on tiny items, does not clear it.

## What Analyze will check

Analyze remains descriptive; it fits neither LightGBM nor Prophet.

1. **Filter check.** Count rows after filtering `store_id` in (`CA_1`, `CA_2`, `CA_3`, `CA_4`), expecting 12,196. Confirm that no other `state_id = CA` store exists, and that item counts match across the four stores.
2. **File agreement.** For those rows, confirm that `sales_train_validation` `d_1`–`d_1913` equals `sales_train_evaluation` on the same columns.
3. **Zero-sales share** by store and by category, and by department where a category is mixed. This is the number that tells us whether MAPE is even a fair headline.
4. **Weekday profile.** Mean units by `wday` for each category, so that the weekly repeat that justifies lag-28 is visible.
5. **SNAP.** Mean FOODS units on `snap_CA = 1` days versus other days, by store, compared with HOBBIES and HOUSEHOLD, which should move less. The same plot is repeated for the test window alone, given that the window is SNAP-heavy.
6. **Events inside the holdout.** Mark 2016-04-30, 2016-05-01, 2016-05-05 and 2016-05-08 on a daily total chart, and decide whether any category–store pair is an outlier on those dates before the Excel pair is chosen.
7. **Partial weeks.** Confirm the `wm_yr_wk` split documented above (11613 and 11617 partial; 11614–11616 complete), and decide how the weekly executive table will label them.
8. **Price coverage.** Measure the share of item–store–weeks in the California training span that have no `sell_prices` row.
9. **Excel pair.** Pick one category and one store on the strength of the zero-share results, and freeze that choice in the Analyze write-up.
10. **A printed lag-28 example for one series**, calculated by hand or in a sheet, so that the baseline definition is visible before any model code exists. It is a worked example of a decision in this plan, not a model comparison.

## What the next stages are for

- **Analyze** writes up the checks above, still without a model leaderboard.
- **Construct** builds the lag-28 baseline, the LightGBM model under the leakage rule, the 12-series Prophet check and the one-category Excel workbook, and it reports MAPE (with the zero-day share), volume-weighted MAPE, bias and WAPE.
- **Execute** says what a planner should do with a biased-high versus a biased-low result, in units, and hands inventory policy to project 02.

This Plan stage stops, deliberately, before any of that fitting begins. Its value lies not in a number but in the rules: once they are fixed here, no later result can quietly rewrite them.
