# Late Delivery Risk Prediction — DataCo

> Executive summary — fill in as the project progresses.

## Business Question
Which orders are likely to be delivered late, and which shipping modes, regions, and product categories drive late-delivery risk?

## Data
See [`data/README.md`](data/README.md) for source, license, and file inventory.

## Approach (PACE: Plan, Analyze, Construct, Execute)
- **Plan:** question, late-delivery definition, KPI formulas, and model rules are in [`reports/01-plan.md`](reports/01-plan.md). No rates computed yet.
- **Analyze:** label checks, the late rate, and the mode / region / category scorecard are in [`reports/02-analyze.md`](reports/02-analyze.md). No model is fit in this stage.
- **Construct:** the two baselines, a logistic regression, and a random forest are scored on held-out orders in [`reports/03-construct.md`](reports/03-construct.md). No operating threshold is chosen in this stage.
- **Execute:** _how results are delivered (dashboard, report, recommendation)_

## Key Findings
- On non-canceled lines, 98,977 of 172,765 are late (late rate 0.5728996035076549). On-time delivery is 73,788 / 172,765.
- The late flag matches real days greater than scheduled days on every non-canceled line. All 4,423 disagreements are canceled lines, and the flag marks every canceled line 0.
- Shipping mode is the cut that moves the rate. First Class is late on 26,513 / 26,513 non-canceled lines. Median slip is 1 day in all 23 regions.
- On held-out orders, a logistic regression and a random forest did not beat the shipping-mode baseline on test ROC AUC (0.736119769260069 and 0.7347929101103273 versus 0.7383939473457695). Shipping mode accounts for 0.9308387729436968 of the forest's impurity importance.

## Recommendation
_What should the business do, and why?_

## Impact
_Estimated $ / % / service-level impact._

## Tools
Python (pandas, scikit-learn, XGBoost), SQL, Tableau/Power BI

## How to Reproduce
1. Download raw data into `data/raw/` (see `data/README.md`).
2. Run notebooks in `notebooks/` in order; reusable code lives in `src/`, SQL in `sql/`.
3. Processed outputs go to `data/processed/`; charts to `images/`; dashboards to `dashboards/`; write-ups to `reports/`.
