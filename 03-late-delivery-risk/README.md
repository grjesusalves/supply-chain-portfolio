# Late Delivery Risk Prediction — DataCo

> On 172,765 non-canceled lines, 98,977 are late (late rate 0.5728996035076549). On-time delivery is 73,788 / 172,765 (0.4271003964923451).
>
> Shipping mode is what moves the rate. First Class is late on 26,513 / 26,513: the promise is 1 day and real days are 2 on every line. Second Class is 26,987 / 33,806 (median slip 2). Same Day is 4,454 / 9,293 (median slip 0). Standard Class is 41,023 / 103,153 (median slip 0).
>
> Region does not move the rate once mode is fixed. First Class is late in all 23 regions and all 5 markets. Median slip is 1 day in every region. Category median slip is 1 for 49 of 50 categories.
>
> A logistic regression and a random forest did not beat the shipping-mode baseline on held-out orders (test ROC AUC 0.736119769260069 and 0.7347929101103273 versus 0.7383939473457695).
>
> Manage the mode. Fix the First Class promise or the operation. Do not deploy a classifier and do not set an operating threshold. A dollar penalty for a late delivery is not in the file and is not estimated.

## Business Question
Which orders are likely to be delivered late, and which shipping modes, regions, and product categories drive late-delivery risk?

## Data
See [`data/README.md`](data/README.md) for source, license, and file inventory.

## Approach (PACE: Plan, Analyze, Construct, Execute)
- **Plan:** question, late-delivery definition, KPI formulas, and model rules are in [`reports/01-plan.md`](reports/01-plan.md). No rates computed yet.
- **Analyze:** label checks, the late rate, and the mode / region / category scorecard are in [`reports/02-analyze.md`](reports/02-analyze.md). No model is fit in this stage.
- **Construct:** the two baselines, a logistic regression, and a random forest are scored on held-out orders in [`reports/03-construct.md`](reports/03-construct.md). No operating threshold is chosen in this stage.
- **Execute:** the recommendation, what was deliberately not done, and the Tableau Public step are in [`reports/04-execute.md`](reports/04-execute.md). The fulfillment write-up is [`reports/business-report.md`](reports/business-report.md). The browser dashboard is [`dashboards/late_delivery_dashboard.html`](dashboards/late_delivery_dashboard.html). No operating threshold. Dollar impact is not estimated.

## Key Findings
- On non-canceled lines, 98,977 of 172,765 are late (late rate 0.5728996035076549). On-time delivery is 73,788 / 172,765.
- First Class is late on 26,513 / 26,513 non-canceled lines. Scheduled days are 1 and real days are 2 on every one of them.
- On held-out orders, a logistic regression and a random forest did not beat the shipping-mode baseline (test ROC AUC 0.736119769260069 and 0.7347929101103273 versus 0.7383939473457695).

## Recommendation
Manage the shipping mode. The First Class promise is 1 day and delivery is 2 days on every non-canceled First Class line (26,513 / 26,513). Fix the promise or the operation. Do not deploy the logistic model or the random forest, and do not set an operating threshold. They did not beat the shipping-mode baseline.

## Impact
Not estimated. The file has no late-delivery cost, so no dollar impact is claimed.

## Tools
Python (pandas, scikit-learn), SQL, and a browser dashboard. Tableau Public is not published; the extract is data/processed/mode_scorecard.csv.

## How to Reproduce
1. Download raw data into `data/raw/` (see `data/README.md`).
2. From the repo root, run `python 03-late-delivery-risk/src/analyze_late_delivery.py`, then `python 03-late-delivery-risk/src/construct_late_delivery.py`. The KPI queries in `sql/kpi_late_delivery.sql` match the Analyze tables.
3. Processed outputs go to `data/processed/`; charts to `images/`; dashboards to `dashboards/`; write-ups to `reports/`.
