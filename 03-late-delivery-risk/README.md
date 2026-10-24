# Late Delivery Risk Prediction — DataCo

## Start here

The reading order runs from the big picture down to the code; each step assumes the one before it.

1. This page: the summary just below, then [Business Question](#business-question), [Key Findings](#key-findings), and [Recommendation](#recommendation).
2. [Dashboard](dashboards/late_delivery_dashboard.html): the result at a glance. GitHub shows the HTML source, so download the file and open it in a browser.
3. [Business report](reports/business-report.md): the manager's version, with no code.
4. [Plan](reports/01-plan.md): the question, the KPI, and what was deliberately left out of scope.
5. [Analyze](reports/02-analyze.md): the label check, the removal of cancels, and the First Class finding. Charts: [late rate by shipping mode](images/late_rate_by_shipping_mode.png) and [real days by shipping mode](images/real_days_by_shipping_mode.png).
6. [Construct](reports/03-construct.md): the order-level split, the baselines, the models, and why they lost. Chart: [test AUC and AP by model](images/test_auc_ap_by_model.png).
7. [Execute](reports/04-execute.md): the recommendation, and why it carries neither a threshold nor a dollar figure.
8. Code: [analyze_late_delivery.py](src/analyze_late_delivery.py), then [construct_late_delivery.py](src/construct_late_delivery.py). The `#` comments show how each number was produced.
9. [SQL KPI queries](sql/kpi_late_delivery.sql): the same KPIs, written in SQL.
10. [Processed tables](data/processed/): open one to check a number yourself, for example [mode_scorecard.csv](data/processed/mode_scorecard.csv) or [construct_metrics.csv](data/processed/construct_metrics.csv).

> Of 172,765 non-canceled lines, 98,977 arrived late, a late rate of 0.5728996035076549; on-time delivery is 73,788 / 172,765, or 0.4271003964923451.
>
> The shipping mode is what moves that rate. First Class is late on 26,513 / 26,513 lines: the promise is 1 day, and real days are 2 on every single line. Second Class is late on 26,987 / 33,806, with a median slip of 2; Same Day on 4,454 / 9,293, with a median slip of 0; Standard Class on 41,023 / 103,153, also with a median slip of 0.
>
> Once the mode is fixed, region does not move the rate. First Class is late in all 23 regions and all 5 markets, and the median slip is 1 day in every region. Category tells the same story: the median slip is 1 for 49 of 50 categories.
>
> Neither a logistic regression nor a random forest beat the shipping-mode baseline on held-out orders, with test ROC AUC of 0.736119769260069 and 0.7347929101103273 against 0.7383939473457695.
>
> The clear-sighted response is to manage the mode: fix either the First Class promise or the operation behind it. Do not deploy a classifier, and do not set an operating threshold. Note that the file carries no dollar penalty for a late delivery, so none is estimated.

## Business Question
Which orders are likely to be delivered late, and which shipping modes, regions, and product categories drive late-delivery risk?

## Data
See [`data/README.md`](data/README.md) for the source, license, and file inventory.

## Approach (PACE: Plan, Analyze, Construct, Execute)
- **Plan:** the question, the late-delivery definition, the KPI formulas, and the model rules are set out in [`reports/01-plan.md`](reports/01-plan.md). No rate is computed at this stage.
- **Analyze:** the label checks, the late rate, and the mode / region / category scorecard are in [`reports/02-analyze.md`](reports/02-analyze.md). No model is fit at this stage.
- **Construct:** the two baselines, a logistic regression, and a random forest are scored on held-out orders in [`reports/03-construct.md`](reports/03-construct.md). No operating threshold is chosen at this stage.
- **Execute:** the recommendation, what was deliberately left undone, and the Tableau Public step are in [`reports/04-execute.md`](reports/04-execute.md). The fulfillment write-up is [`reports/business-report.md`](reports/business-report.md), and the browser dashboard is [`dashboards/late_delivery_dashboard.html`](dashboards/late_delivery_dashboard.html). There is no operating threshold, and the dollar impact is not estimated.

## Key Findings
- On non-canceled lines, 98,977 of 172,765 are late, a late rate of 0.5728996035076549; on-time delivery is 73,788 / 172,765. More than half of all delivery attempts, in other words, miss their promise.
- First Class is late on 26,513 / 26,513 non-canceled lines. Scheduled days are 1 and real days are 2 on every one of them; the failure is structural, not occasional.
- On held-out orders, neither a logistic regression nor a random forest beat the shipping-mode baseline, with test ROC AUC of 0.736119769260069 and 0.7347929101103273 against 0.7383939473457695. Whatever signal region, category, or price carry, the mode has already captured it.

## Recommendation
Manage the shipping mode. The First Class promise is 1 day, yet delivery takes 2 days on every non-canceled First Class line (26,513 / 26,513); either the promise or the operation has to change. That said, a model is not the answer: do not deploy the logistic model or the random forest, and do not set an operating threshold, given that neither beat the shipping-mode baseline.

## Impact
Not estimated. The file records no late-delivery cost, so no dollar impact is claimed.

## Tools
Python (pandas, scikit-learn), SQL, and a browser dashboard. Tableau Public is not published; the extract is data/processed/mode_scorecard.csv.

## How to Reproduce
1. Download the raw data into `data/raw/` (see `data/README.md`).
2. From the repo root, run `python 03-late-delivery-risk/src/analyze_late_delivery.py`, then `python 03-late-delivery-risk/src/construct_late_delivery.py`. The KPI queries in `sql/kpi_late_delivery.sql` match the Analyze tables.
3. Processed outputs go to `data/processed/`; charts to `images/`; dashboards to `dashboards/`; write-ups to `reports/`.
