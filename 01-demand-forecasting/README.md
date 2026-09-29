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
- **Analyze:** _data cleaning, EDA, key descriptive stats_
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
