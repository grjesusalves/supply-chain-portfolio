# Business report — forecasting food demand at Walmart store CA_3

This report is the Execute deliverable for a replenishment planner and a hiring manager who wants more than the two-minute page. The two-minute page is [04-execute.md](04-execute.md). Nothing here refits a model, and nothing here is a dollar saving.

## Situation

Walmart’s M5 file is daily unit sales for 3,049 items in ten stores. Replenishment orders **units**, not dollars, at the item and the store. A category manager can look at the same forecast after it is added up.

California has four stores. Across all California categories, **Sunday** is the peak weekday and Wednesday is the trough. **SNAP** days (the 1st through the 10th) lift food by about **10%** and lift household and hobbies much less. **CA_3** is the largest California store. About **66%** of California item-days are zeros, so a percentage error that divides by actual sales is a poor headline: it either explodes or it ignores most days. The score to quote is **WAPE** (total absolute error divided by total actual units).

The finished model does not cover all of that. It covers **FOODS at CA_3** only.

## Approach

The work follows PACE.

- **Plan** fixed the question, the 28-day horizon, the holdout dates, the lag-28 baseline, and the rule that MAPE is only for days with sales while WAPE includes zeros. It refused dollar impact. See [01-plan.md](01-plan.md).
- **Analyze** measured the California slice and did not fit a model. It is why the first build is food at CA_3, and why `snap_CA` stays in the feature list. See [02-analyze.md](02-analyze.md).
- **Construct** fit the baseline and one LightGBM model and scored the holdout. See [03-construct.md](03-construct.md). Code: `src/construct_forecast.py`.
- **Execute** (this report, the short page, and a static dashboard) says what to do with those scores. It does not change them.

## Data

Source is the M5 Forecasting Accuracy files (Walmart), already described in `data/README.md`. The scored slice is:

| Item | Value |
|---|---|
| Store and category | CA_3, FOODS |
| Series | 1,437 |
| Holdout | 2016-04-25 through 2016-05-22 (28 days) |
| Item-days | 40,236 |
| Actual units | 109,870 |
| Days in MAPE (actual > 0) | 25,302 |
| Days left out of MAPE | 14,934 |

Training labels stop on 2016-04-24. The holdout is one origin. Actuals inside those 28 days are not used as features. The window includes SNAP days (2016-05-01 through 2016-05-10) and several events (Pesach End, Orthodox Easter, Cinco de Mayo, Mother’s Day). That is a property of this month, not a second test.

## Method

No code on this page. Two forecasts, same holdout.

**Seasonal naive (lag-28).** For each item and each holdout day, the forecast is that item’s actual sales on the same weekday four weeks earlier. Those source days are the 28 days just before the holdout, so they are known when the forecast is made. It is one observation, not a four-week average. It is the benchmark a more complicated model has to beat.

**LightGBM.** One pooled gradient-boosted tree model for all 1,437 items, direct multi-step (not a recursive day-by-day forecast). Features are lags of 28, 35, and 42 days, two rolling means that end at the lag-28 day, weekday, month, the California SNAP flag, an event flag, and that week’s price. Lags of 1–27 days are excluded because, at a 28-day horizon, those days have not happened yet. Predictions below zero would be clipped to zero; this run did not need to clip any holdout row.

The model is a point forecast of units. It is not a safety-stock formula.

## Results

Ratios below are the Construct file, not rounded. The percent column is the same ratio times 100, to one decimal, which is what the executive page quotes.

| Model | MAPE | MAPE % | WAPE | WAPE % | Bias | Bias % | Sum of absolute error | Sum of (forecast − actual) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seasonal naive (lag-28) | 0.8781250159967809 | 87.8% | 0.777000091016656 | 77.7% | 0.010694457085646673 | +1.1% | 85,369.0 | 1,175.0 |
| LightGBM | 0.5633893484087068 | 56.3% | 0.6490765893903951 | 64.9% | 0.02570857287913414 | +2.6% | 71,314.04487632272 | 2,824.600902230468 |

LightGBM wins **WAPE** and **MAPE**. Absolute error falls from 85,369 units to 71,314.04487632272 units, on 109,870 units sold. That is fewer units of miss. It is not a dollar figure.

LightGBM loses on **bias**. Both forecasts are high. The copy is high by 1,175 units. LightGBM is high by 2,824.600902230468 units. Lower absolute error with a larger positive bias is still an over-forecast.

MAPE looks worse than WAPE because each item-day counts the same, and a one-unit miss on a one-unit day is a 100% error. Lead with WAPE.

![Daily total actual versus both forecasts](../images/ca3_foods_forecast_vs_actual.png)

The chart is the sum of all 1,437 items by day. Both forecasts keep the weekend peak. The static dashboard at [dashboards/ca3_foods_dashboard.html](../dashboards/ca3_foods_dashboard.html) shows the same daily totals and the metrics. There is no Tableau connector in this environment, and Tableau Public was not signed in. **Publishing to Tableau Public is a manual step** the student can do by importing `data/processed/ca3_foods_holdout_predictions.csv`.

## One-item caveat

The highest-volume training item at this store and category is **FOODS_3_090**: **250,502** units in training, **3,357** units in the holdout. On that item the baseline **WAPE 0.1975** beats LightGBM **0.2130**. The aggregate win is not a win on the busiest series. The workbook is `reports/ca3_foods_one_item_forecast.xlsx`. Do not tell a buyer the model is better on every item.

## Risks

**Intermittent demand.** Many series do not sell on a typical day. A point forecast of a fraction of a unit is a rate, not a case quantity. Zeros can be “not listed yet,” “did not sell,” or a stockout the file cannot see. MAPE hides or explodes on those days. WAPE does not.

**Bias.** A forecast that is high on average, if the store orders to it, builds **extra inventory**. It does not, by itself, prevent stockouts. LightGBM is the more high of the two (+2.6% versus +1.1%). Some individual days are still short — the net can be high while a Sunday is low — so bias is not a promise about every day. It is the direction of the total.

**One window, one store, one category.** This holdout is late April and May 2016. It does not prove the same gap in November, at CA_1, or in hobbies. The tree count was chosen on a slice of training days that the final fit also sees. The holdout was not used to choose it. That is a limit on how clean the tree count is, not a leak of holdout sales.

## Next step

Project **02, inventory optimization**, is where these errors become a reorder point or a safety-stock quantity, and where a holding cost could turn units into money. This project stops at the unit forecast and the recommendation below.

**Use LightGBM for CA_3 food replenishment planning. Keep the lag-28 forecast as the benchmark. Do not claim dollar savings.**
