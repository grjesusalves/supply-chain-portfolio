# Business report — forecasting food demand at Walmart store CA_3

This report is the Execute deliverable, written for a replenishment planner and for a hiring manager who wants more than the two-minute page; that shorter page is [04-execute.md](04-execute.md). Nothing here refits a model, and nothing here should be read as a dollar saving.

## Situation

Walmart's M5 file records daily unit sales for 3,049 items across ten stores. Replenishment orders **units**, not dollars, and it does so at the level of the item and the store; a category manager can then read the same forecast once it has been added up.

California has four stores, and the patterns among them are pronounced. Across all California categories, **Sunday** is the peak weekday and Wednesday the trough. **SNAP** days, the 1st through the 10th of each month, lift food by about **10%** while lifting household and hobbies far less. **CA_3** is the largest California store. Above all, about **66%** of California item-days are zeros, which means a percentage error that divides by actual sales makes a poor headline: it either explodes or quietly ignores most days. The score to quote is therefore **WAPE**, total absolute error divided by total actual units.

The finished model does not cover all of that ground. It covers **FOODS at CA_3** alone.

## Approach

The work follows PACE, and each stage did one job.

- **Plan** fixed the question, the 28-day horizon, the holdout dates and the lag-28 baseline, together with the rule that MAPE applies only to days with sales while WAPE includes the zeros. From the outset, it declined to estimate dollar impact. See [01-plan.md](01-plan.md).
- **Analyze** measured the California slice without fitting a model. It explains why the first build is food at CA_3, and why `snap_CA` stays in the feature list. See [02-analyze.md](02-analyze.md).
- **Construct** fit the baseline and a single LightGBM model, then scored both on the holdout. See [03-construct.md](03-construct.md); the code is `src/construct_forecast.py`.
- **Execute**, comprising this report, the short page and a static dashboard, says what to do with those scores. It does not change them.

## Data

The source is the M5 Forecasting Accuracy files from Walmart, already described in `data/README.md`. The scored slice is as follows:

| Item | Value |
|---|---|
| Store and category | CA_3, FOODS |
| Series | 1,437 |
| Holdout | 2016-04-25 through 2016-05-22 (28 days) |
| Item-days | 40,236 |
| Actual units | 109,870 |
| Days in MAPE (actual > 0) | 25,302 |
| Days left out of MAPE | 14,934 |

Training labels stop on 2016-04-24, and the holdout is a single origin; actuals inside those 28 days are never used as features. The window happens to include SNAP days (2016-05-01 through 2016-05-10) and several events — Pesach End, Orthodox Easter, Cinco de Mayo and Mother's Day. That is a property of this particular month. It is not a second test.

## Method

This page carries no code. It compares two forecasts on the same holdout.

**Seasonal naive (lag-28).** For each item and each holdout day, the forecast is simply that item's actual sales on the same weekday four weeks earlier. Those source days are the 28 days immediately before the holdout, so they are known at the moment the forecast is made. It is a single observation rather than a four-week average, and it is the benchmark that any more elaborate model has to beat.

**LightGBM.** A single pooled gradient-boosted tree model serves all 1,437 items, and it forecasts direct multi-step rather than recursively, day by day. Its features are lags of 28, 35 and 42 days, two rolling means that end at the lag-28 day, weekday, month, the California SNAP flag, an event flag and that week's price. Lags of 1–27 days are excluded for a simple reason: at a 28-day horizon, those days have not yet happened. Predictions below zero would be clipped to zero, although this run did not need to clip a single holdout row.

The model produces a point forecast of units. It is not, and should not be mistaken for, a safety-stock formula.

## Results

The ratios below are taken from the Construct file without rounding. The percent columns show the same ratios times 100, to one decimal, which is the form the executive page quotes.

| Model | MAPE | MAPE % | WAPE | WAPE % | Bias | Bias % | Sum of absolute error | Sum of (forecast − actual) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seasonal naive (lag-28) | 0.8781250159967809 | 87.8% | 0.777000091016656 | 77.7% | 0.010694457085646673 | +1.1% | 85,369.0 | 1,175.0 |
| LightGBM | 0.5633893484087068 | 56.3% | 0.6490765893903951 | 64.9% | 0.02570857287913414 | +2.6% | 71,314.04487632272 | 2,824.600902230468 |

LightGBM wins on both **WAPE** and **MAPE**. Absolute error falls from 85,369 units to 71,314.04487632272 units, on 109,870 units sold — fewer units of miss, which is undeniable progress, though it is not a dollar figure.

That said, LightGBM loses on **bias**. Both forecasts run high: the copy by 1,175 units, LightGBM by 2,824.600902230468 units. Lower absolute error paired with a larger positive bias is, all the same, an over-forecast.

MAPE looks worse than WAPE because every item-day counts equally, and a one-unit miss on a one-unit day registers as a 100% error. WAPE, therefore, should lead.

![Daily total actual versus both forecasts](../images/ca3_foods_forecast_vs_actual.png)

The chart sums all 1,437 items by day, and both forecasts preserve the weekend peak. The static dashboard at [dashboards/ca3_foods_dashboard.html](../dashboards/ca3_foods_dashboard.html) shows the same daily totals alongside the metrics. Given that there is no Tableau connector in this environment and Tableau Public was never signed in, **publishing to Tableau Public is a manual step**, one the student can complete by importing `data/processed/ca3_foods_holdout_predictions.csv`.

## One-item caveat

The highest-volume training item for this store and category is **FOODS_3_090**, with **250,502** units in training and **3,357** units in the holdout. On that item, the baseline's **WAPE 0.1975** beats LightGBM's **0.2130**. The aggregate win, in short, is not a win on the busiest series. The workbook that traces it is `reports/ca3_foods_one_item_forecast.xlsx`. A buyer, then, should not be told that the model is better on every item.

## Risks

**Intermittent demand.** Many series sell nothing on a typical day, and a point forecast of a fraction of a unit is a rate, not a case quantity. Moreover, a zero can mean "not listed yet," "did not sell" or a stockout the file cannot see. MAPE either hides or explodes on those days; WAPE does neither.

**Bias.** A forecast that is high on average builds **extra inventory** if the store orders to it; it does not, by itself, prevent stockouts. LightGBM is the more high of the two (+2.6% versus +1.1%). Individual days can still fall short — the net can be high while a given Sunday is low — so bias is not a promise about every day. It is the direction of the total.

**One window, one store, one category.** This holdout covers late April and May 2016, and it does not prove the same gap in November, at CA_1 or in hobbies. Note, too, that the tree count was chosen on a slice of training days that the final fit also sees. The holdout played no part in choosing it, which means this is a limit on how clean the tree count is — not a leak of holdout sales.

## Next step

Project **02, inventory optimization**, is where these errors become a reorder point or a safety-stock quantity, and where a holding cost could eventually turn units into money. This project stops, deliberately, at the unit forecast and at the recommendation below.

**Use LightGBM for CA_3 food replenishment planning. Keep the lag-28 forecast as the benchmark. Do not claim dollar savings.**
