# Demand Forecasting — Walmart M5

## Start here

Read the files in this order. It mirrors the order in which the work was done: the story first, the evidence for each stage next, and the code last — because a forecast is only as persuasive as the reasoning that precedes it.

1. This README, for the question and the result.
2. [data/README.md](data/README.md), then [data/raw/README.md](data/raw/README.md), for where the data came from and where the downloads go.
3. [reports/01-plan.md](reports/01-plan.md), for why food at CA_3, the 28-day test, and the measures.
4. [reports/02-analyze.md](reports/02-analyze.md), with these charts open: [monthly trend](images/ca_monthly_trend.png), [weekday pattern](images/ca_weekday_seasonality.png), [volume by store and category](images/ca_volume_by_store_and_category.png), [SNAP by category](images/ca_snap_by_category.png).
5. [reports/03-construct.md](reports/03-construct.md), with [forecast vs actual](images/ca3_foods_forecast_vs_actual.png), [daily error](images/ca3_foods_daily_error.png), and the scores in [ca3_foods_metrics.csv](data/processed/ca3_foods_metrics.csv).
6. [reports/ca3_foods_one_item_forecast.xlsx](reports/ca3_foods_one_item_forecast.xlsx), one item (FOODS_3_090) worked by hand in Excel.
7. [reports/04-execute.md](reports/04-execute.md), then [reports/business-report.md](reports/business-report.md), for the recommendation and the manager version.
8. [dashboards/ca3_foods_dashboard.html](dashboards/ca3_foods_dashboard.html), the one-page dashboard. Download it and open it in a browser.
9. [src/analyze_ca.py](src/analyze_ca.py), then [src/construct_forecast.py](src/construct_forecast.py), the code. Read the `#` comments next to reports 2 and 3.

The remaining files in [data/processed/](data/processed/) are small tables from the analyze step; open one when a report refers to it.

## Executive summary

**Business question.** How many food units will Walmart store CA_3 sell, item by item, over the next 28 days, and does LightGBM beat a same-weekday-four-weeks-ago copy?

**Result.** On the holdout 2016-04-25 through 2016-05-22 (1,437 FOODS series, 40,236 item-days, 109,870 actual units), LightGBM’s WAPE is **64.9%**, against **77.7%** for the lag-28 seasonal naive. MAPE, measured only on days with actual sales, tells the same story: 56.3% versus 87.8%. That said, the win is not clean. Both forecasts run high (LightGBM +2.6%, lag-28 +1.1%), and a high forecast translates into extra inventory, not stockouts. LightGBM wins on WAPE and MAPE; it loses on bias.

**Recommendation.** Use LightGBM for CA_3 food replenishment planning, and keep the lag-28 forecast as the benchmark. Dollar savings should not be claimed; after all, no dollar figure was ever calculated.

**Not in this result.** Other stores, HOUSEHOLD, HOBBIES, and inventory policy, which belongs to project 02. Note that the aggregate win does not extend to every item: on FOODS_3_090, the baseline WAPE of 0.1975 beats LightGBM’s 0.2130 (250,502 training units, 3,357 holdout units).

## Reports, chart, and code

| | |
|---|---|
| Plan | [reports/01-plan.md](reports/01-plan.md) |
| Analyze | [reports/02-analyze.md](reports/02-analyze.md) |
| Construct | [reports/03-construct.md](reports/03-construct.md) |
| Execute | [reports/04-execute.md](reports/04-execute.md) |
| Business report | [reports/business-report.md](reports/business-report.md) |
| Chart | [images/ca3_foods_forecast_vs_actual.png](images/ca3_foods_forecast_vs_actual.png) |
| Dashboard | [dashboards/ca3_foods_dashboard.html](dashboards/ca3_foods_dashboard.html) (open the file; GitHub will show the source) |
| Code | [src/analyze_ca.py](src/analyze_ca.py), [src/construct_forecast.py](src/construct_forecast.py) |

![CA_3 FOODS daily actual vs both forecasts](images/ca3_foods_forecast_vs_actual.png)

The dashboard is a static HTML page. Publishing to Tableau Public remains a manual step — import `data/processed/ca3_foods_holdout_predictions.csv` — given that this repo was never signed into Tableau.

## Data
See [`data/README.md`](data/README.md) for source, license, and file inventory.

## Approach (PACE: Plan, Analyze, Construct, Execute)
- **Plan:** [reports/01-plan.md](reports/01-plan.md). Decisions (no model is fit in this stage):
  - **Scope:** California only, stores CA_1, CA_2, CA_3, CA_4. M5 has three states and ten stores; four California stores still show store differences and still run on a laptop.
  - **Horizon:** next 28 days (M5's official forecast horizon, four weeks).
  - **Target:** daily unit sales (the evaluation series), not dollar sales.
  - **Grain:** forecast item–store–day, then roll up bottom-up to category–store–week for the executive view.
  - **Holdout:** last 28 days of `sales_train_evaluation` (2016-04-25 through 2016-05-22). Train on everything before that.
  - **Baseline:** seasonal naive, same weekday four weeks earlier (lag-28), because retail demand repeats weekly and a 28-day-ahead origin cannot use actuals inside the horizon.
  - **Stronger model:** LightGBM on lag and calendar features (price, SNAP, events). Prophet only as a category-level check, not at item grain (too slow).
  - **Metrics:** MAPE and bias (mean forecast minus actual, as a percent of actual). Also a volume-weighted MAPE so a tiny item does not dominate. MAPE explodes when actual is 0, so report WAPE (sum of absolute errors / sum of actuals) or a denominator floor alongside MAPE, plus the share of zero-sales days.
  - **Why accuracy matters:** error becomes units of safety stock. Biased high inflates inventory; biased low causes stockouts. Direction only — no dollar figures.
  - **Out of scope:** inventory optimization (project 02), causal promo experiments, all 10 stores.
  - **Excel:** one category, one store, seasonal naive versus a simple Excel forecast, for interviewers who open a spreadsheet.
- **Analyze:** [reports/02-analyze.md](reports/02-analyze.md). Descriptive checks for CA_1–CA_4 only, from `src/analyze_ca.py`. No model is fit.
  - **Shape:** 12,196 item–store series (3,049 items in each store), `d_1` 2011-01-29 through `d_1941` 2016-05-22. Missing cells: 0. Zero-sale cells: 15,621,951 of 23,672,436 (share 0.6599215644727058). Validation matches evaluation on `d_1`–`d_1913` (0 mismatched cells).
  - **Weekday:** Sunday averages 18,507.230215827338 CA units per day; Wednesday averages 12,947.335740072202. Correlation of the statewide daily total is 0.8408696097678586 at lag 7 and 0.84399231729513 at lag 28, so the lag-28 baseline keeps the weekly pattern.
  - **SNAP:** `snap_CA` is on for the 1st–10th of each month (640 days). Statewide average daily units are 15,823.4234375 on SNAP days vs 14,657.74481168332 otherwise (lift 0.07952646473197889). FOODS lift is 0.1024460777606011; HOUSEHOLD 0.03620140269117922; HOBBIES 0.02992724013488668.
  - **Volume and intermittency:** CA_3 is 11,363,540 units (share 0.3892060877940489); FOODS is 19,535,863 (share 0.6691116333387758). 9,145 of 12,196 series sell on fewer than half of days, which is why MAPE needs the zero-day rule from the plan.
  - **Price and first cut:** 2,660,038 of 3,390,488 CA item–store–weeks have a price (0.7845590369291973). The other 730,450 weeks are all before the first price and contain 0 units; there are 0 interior price holes. Construct should prove the pipeline on FOODS at CA_3 (7,625,660 units) before all 12,196 series.
- **Construct:** [reports/03-construct.md](reports/03-construct.md). FOODS at CA_3 only (1,437 series), horizon 28 days, holdout `d_1914`–`d_1941` (2016-04-25 through 2016-05-22). Train labels stop at `d_1913`. Script: `src/construct_forecast.py`. Seasonal naive is lag-28 from the 28 days before the holdout. LightGBM is direct multi-step with lags 28/35/42, rolling means ending at lag 28, weekday, month, `snap_CA`, an event flag, and that week's price. No lags 1–27. Holdout scores (ratios, not percents; MAPE only where actual > 0; WAPE is the volume-weighted score):
  - Seasonal naive: MAPE 0.8781250159967809, WAPE 0.777000091016656, bias 0.010694457085646673 (sum of absolute error 85369.0, sum of forecast−actual 1175.0, sum of actual 109870.0).
  - LightGBM: MAPE 0.5633893484087068, WAPE 0.6490765893903951, bias 0.02570857287913414 (sum of absolute error 71314.04487632272, sum of forecast−actual 2824.600902230468).
  - LightGBM beat the baseline on WAPE and MAPE, including WAPE on every weekday. It did not win on bias: both forecasts are high, and LightGBM is higher. On the highest-volume training item, FOODS_3_090 (250,502 units on `d_1`–`d_1913`), the baseline WAPE is lower (0.1974977658623771 vs LightGBM 0.2129970073026922). Workbook: `reports/ca3_foods_one_item_forecast.xlsx`. Chart: `images/ca3_foods_forecast_vs_actual.png`. No dollar figure.
- **Execute:** [reports/04-execute.md](reports/04-execute.md) and [reports/business-report.md](reports/business-report.md). No refit. Recommendation: use LightGBM for CA_3 food replenishment planning, keep lag-28 as the benchmark, do not claim dollar savings. WAPE 64.9% (LightGBM) vs 77.7% (lag-28). Both forecasts are high (+2.6% vs +1.1%), which means extra inventory, not stockouts. Dashboard: [dashboards/ca3_foods_dashboard.html](dashboards/ca3_foods_dashboard.html). Tableau Public was not published; import the predictions CSV by hand if you want that.

## Key Findings
- On FOODS at CA_3, over the holdout 2016-04-25 through 2016-05-22, LightGBM posts a WAPE of **64.9%** against **77.7%** for lag-28. MAPE (actual > 0) is 56.3% versus 87.8%, and absolute error falls from 85,369 units to 71,314.04487632272 units, on 109,870 actual units.
- Both forecasts are high: bias is +2.6% for LightGBM and +1.1% for lag-28. A high bias means extra inventory, not a stockout bias; moreover, LightGBM is the more high of the two.
- About 66% of California item-days are zeros, which means MAPE cannot serve as the headline. WAPE does.
- The exception matters: on FOODS_3_090, the baseline WAPE of 0.1975 beats LightGBM’s 0.2130.

## Recommendation
Use LightGBM for CA_3 food replenishment planning, and keep the lag-28 forecast as the standing benchmark. It would be a mistake to claim the model wins on every item; it would be equally a mistake to claim dollar savings.

## Impact
No dollar savings and no service-level change are claimed. The undeniable gain is in units: a smaller absolute error. The undeniable cost is a larger positive bias. Turning that trade-off into safety stock is the work of project 02.

## Tools
Python (pandas, LightGBM). Static HTML dashboard in `dashboards/`. Tableau Public was not used.

## How to Reproduce
1. Download raw data into `data/raw/` (see `data/README.md`).
2. Run `src/analyze_ca.py`, then `src/construct_forecast.py`. All code is Python in `src/`; this project has no notebooks or SQL.
3. Processed outputs go to `data/processed/`; charts to `images/`; dashboards to `dashboards/`; write-ups to `reports/`.

## Takeaway
Cutting WAPE from 77.7% to 64.9% is a meaningful result in a state where about 66% of item-days sell nothing. It is not, however, a licence to stop checking. The model should earn its place at every refresh against the lag-28 benchmark, and its high bias should be priced into inventory policy rather than ignored.
