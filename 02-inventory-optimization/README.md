# Inventory Optimization (Safety Stock / Reorder Point / EOQ)

> Executive summary — fill in as the project progresses.

## Business Question
Given forecast demand and forecast error from Project 1, what safety stock and reorder points minimize holding cost while hitting a target service level (e.g., 95%)?

## Data
See [`data/README.md`](data/README.md) for source, license, and file inventory.

## Approach (PACE: Plan, Analyze, Construct, Execute)
- **Plan:** _stakeholders, success metrics, scope, assumptions_
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
Python (pandas, NumPy, SciPy), Excel, SQL, Tableau/Power BI

## How to Reproduce
1. No download is needed. The input is the committed Project 1 file `../01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv` (see `data/README.md`).
2. Run `python src/analyze_inventory.py`, then `python src/construct_policy.py`.
3. Outputs go to `data/processed/`, charts to `images/`, dashboard files to `dashboards/`, and write-ups to `reports/`.
