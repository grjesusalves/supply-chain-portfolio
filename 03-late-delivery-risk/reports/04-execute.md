# Execute — Late delivery risk (DataCo)

PACE stage: **Execute**. This is the page a hiring manager can read in two minutes. It does not refit a model and it does not pick a threshold. The rates are the Analyze scorecard. The model scores are the Construct holdout. Both are used exactly.

## What we deliver

A fulfillment lead gets three things, and none of them is a classifier.

1. The mode scorecard. On **172,765** non-canceled lines, late rate, line count, and median slip for the four shipping modes.
2. The recommendation. Manage the shipping mode. Fix the First Class promise or the operation. Do not deploy a model.
3. A page that opens in a browser with no Tableau install: [dashboards/late_delivery_dashboard.html](../dashboards/late_delivery_dashboard.html). The longer write-up is [business-report.md](business-report.md).

The extract behind the dashboard is `data/processed/mode_scorecard.csv`. It is the non-canceled rows already in `late_rate_by_shipping_mode.csv` and `kpi_overall.csv`, with scheduled days copied from the non-canceled day grid.

## Question

Which orders miss the date the customer was promised, and is the miss a shipping mode, a region, a category, or something a model can rank at order time?

## Answer

It is the shipping mode.

On the lines that were a delivery attempt, **98,977 of 172,765 are late**. Late rate **0.5728996035076549**. On-time delivery is **73,788 / 172,765**, rate **0.4271003964923451**.

| Shipping Mode | Lines | Late lines | Late rate | Median slip | Scheduled days | Median real days |
|---|---:|---:|---:|---:|---:|---:|
| First Class | 26,513 | 26,513 | 1.0 | 1 | 1 | 2 |
| Second Class | 33,806 | 26,987 | 0.7982902443353251 | 2 | 2 | 4 |
| Same Day | 9,293 | 4,454 | 0.47928548369740664 | 0 | 0 | 0 |
| Standard Class | 103,153 | 41,023 | 0.39769080879858076 | 0 | 4 | 4 |

First Class promises 1 day. Real days are 2 on every non-canceled First Class line. There is no on-time First Class line in this file. Standard Class has the most late lines (41,023) and the lowest late rate, and its median slip is 0.

Region does not move the rate once mode is fixed. First Class is late in all 23 regions and all 5 markets. Median slip is 1 day in every region. The largest gap between a region's late rate and the rate implied by its mode mix is Canada, **−0.06522236464088049**, on **907** lines. Category is the same kind of negative result: median slip is 1 for 49 of 50 categories. Cleats, the largest category, is 13,496 / 23,514 (late rate 0.5739559411414477), next to the overall rate.

The models lost to the mode rule. On held-out orders, **19,722** late lines out of **34,272**, test ROC AUC is **0.7383939473457695** for the shipping-mode baseline, **0.736119769260069** for logistic regression, and **0.7347929101103273** for the random forest. When each rule flags the same share of lines (19,613 of 34,272), the mode catches **13,828** late lines, logistic **13,790**, and the forest **13,762**. Shipping mode is **0.9308387729436968** of the forest's impurity importance. Category is **0.006610455290712629**.

## Recommendation

Manage the shipping mode. The First Class promise is 1 day and delivery is 2 days on all **26,513** non-canceled First Class lines. Fix the promise or the operation. Second Class is late on **26,987 / 33,806**, median slip 2. Do not deploy the logistic model or the random forest.

## What we deliberately did not do

- **No operating threshold** on the logistic model or the random forest. They did not beat the shipping-mode baseline, so there is no score cutoff to operate. The 0.5 table in Construct is a description of one arbitrary cut. This stage does not adopt it.
- **No dollar claim.** The file has no late-delivery cost. If money comes up, it is not available. Dollar impact is not estimated.
- No refit, no fifth model, and no watchlist that treats region or category as a ranking inside a mode.

## Where Tableau Public fits

The dashboard a hiring manager can open without Tableau installed is the HTML file above. Tableau Public is the publish step, and it was not done here.

The extract to upload is **`data/processed/mode_scorecard.csv`**. We cannot sign into the user's Tableau Public account from here. Do not look for a public Tableau URL. None was created.

## Where to look

- Business report: [business-report.md](business-report.md)
- Scorecard and the region check: [02-analyze.md](02-analyze.md)
- Model scores: [03-construct.md](03-construct.md)
- Chart: [images/late_rate_by_shipping_mode.png](../images/late_rate_by_shipping_mode.png)
