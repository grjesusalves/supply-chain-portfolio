# Demand Forecasting — Walmart M5

> Executive summary — fill in as the project progresses.

## Business Question
How accurately can we forecast the next 28 days of daily unit sales for Walmart items in California stores CA_1, CA_2, CA_3, and CA_4, and which items and stores drive the error?

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
- **Construct:** _models / queries / calculations built_
- **Execute:** _how results are delivered (dashboard, report, recommendation)_

## Key Findings
- _Finding 1 (quantified)_
- _Finding 2_
- _Finding 3_

## Recommendation
_What should the business do, and why?_

## Impact
_Estimated $ / % / service-level impact._

## Tools
Python (pandas, statsmodels/LightGBM), SQL, Tableau/Power BI

## How to Reproduce
1. Download raw data into `data/raw/` (see `data/README.md`).
2. Run notebooks in `notebooks/` in order; reusable code lives in `src/`, SQL in `sql/`.
3. Processed outputs go to `data/processed/`; charts to `images/`; dashboards to `dashboards/`; write-ups to `reports/`.
