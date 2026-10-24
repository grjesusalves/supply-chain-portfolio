# Execute — Late delivery risk (DataCo)

PACE stage: **Execute**. This is the page a hiring manager can read in two minutes. It neither refits a model nor picks a threshold: the rates come from the Analyze scorecard and the model scores from the Construct holdout, and both are used exactly as produced.

## What we deliver

A fulfillment lead receives three things, and none of them is a classifier.

1. The mode scorecard: on **172,765** non-canceled lines, the late rate, line count, and median slip for each of the four shipping modes.
2. The recommendation: manage the shipping mode, and fix the First Class promise or the operation behind it. Do not deploy a model.
3. A page that opens in a browser with no Tableau install: [dashboards/late_delivery_dashboard.html](../dashboards/late_delivery_dashboard.html). The longer write-up is [business-report.md](business-report.md).

The extract behind the dashboard is `data/processed/mode_scorecard.csv`. It holds the non-canceled rows already present in `late_rate_by_shipping_mode.csv` and `kpi_overall.csv`, with scheduled days copied from the non-canceled day grid.

## Question

Which orders miss the date the customer was promised, and does the miss stem from a shipping mode, a region, a category, or something a model can rank at order time?

## Answer

It is the shipping mode.

Of the lines that were a genuine delivery attempt, **98,977 of 172,765 are late**, a late rate of **0.5728996035076549**. On-time delivery is **73,788 / 172,765**, a rate of **0.4271003964923451**.

| Shipping Mode | Lines | Late lines | Late rate | Median slip | Scheduled days | Median real days |
|---|---:|---:|---:|---:|---:|---:|
| First Class | 26,513 | 26,513 | 1.0 | 1 | 1 | 2 |
| Second Class | 33,806 | 26,987 | 0.7982902443353251 | 2 | 2 | 4 |
| Same Day | 9,293 | 4,454 | 0.47928548369740664 | 0 | 0 | 0 |
| Standard Class | 103,153 | 41,023 | 0.39769080879858076 | 0 | 4 | 4 |

First Class promises 1 day, and real days are 2 on every non-canceled First Class line; there is not a single on-time First Class line in this file. Standard Class, by contrast, has the most late lines (41,023) alongside the lowest late rate, and its median slip is 0.

Once the mode is fixed, region does not move the rate. First Class is late in all 23 regions and all 5 markets, and the median slip is 1 day in every region. The largest gap between a region's late rate and the rate implied by its mode mix belongs to Canada, at **−0.06522236464088049**, on **907** lines. Category returns the same kind of negative result: the median slip is 1 for 49 of 50 categories. Cleats, the largest category, is 13,496 / 23,514, a late rate of 0.5739559411414477, next to the overall rate.

The models lost to the mode rule. On held-out orders, with **19,722** late lines out of **34,272**, test ROC AUC is **0.7383939473457695** for the shipping-mode baseline, **0.736119769260069** for the logistic regression, and **0.7347929101103273** for the random forest. When each rule flags the same share of lines (19,613 of 34,272), the mode catches **13,828** late lines, the logistic model **13,790**, and the forest **13,762**. Shipping mode accounts for **0.9308387729436968** of the forest's impurity importance; category, for **0.006610455290712629**.

## Recommendation

Manage the shipping mode. The First Class promise is 1 day, and delivery takes 2 days on all **26,513** non-canceled First Class lines; either the promise or the operation must change. Second Class is late on **26,987 / 33,806**, with a median slip of 2. Do not deploy the logistic model or the random forest.

## What we deliberately did not do

- **No operating threshold** on the logistic model or the random forest. Given that neither beat the shipping-mode baseline, there is no score cutoff worth operating. The 0.5 table in Construct describes one arbitrary cut, and this stage does not adopt it.
- **No dollar claim.** The file carries no late-delivery cost; if money comes up, the honest answer is that it is not available. The dollar impact is not estimated.
- No refit, no fifth model, and no watchlist that treats region or category as a ranking inside a mode.

## Where Tableau Public fits

The dashboard a hiring manager can open without Tableau installed is the HTML file above. Tableau Public is the publishing step, and it was not done here.

The extract to upload is **`data/processed/mode_scorecard.csv`**. We cannot sign into the user's Tableau Public account from this environment, so there is no point looking for a public Tableau URL; none was created.

## Where to look

- Business report: [business-report.md](business-report.md)
- Scorecard and the region check: [02-analyze.md](02-analyze.md)
- Model scores: [03-construct.md](03-construct.md)
- Chart: [images/late_rate_by_shipping_mode.png](../images/late_rate_by_shipping_mode.png)
