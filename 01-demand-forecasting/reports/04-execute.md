# Execute — CA_3 food forecast

PACE stage: **Execute**. This is the page a hiring manager can read in two minutes. It refits nothing; the scores are the Construct holdout, used exactly as computed.

## Question

For Walmart store **CA_3**, food only, how many units should replenishment expect over the next 28 days, and is a LightGBM forecast better than copying the same weekday four weeks ago?

## Answer

Yes on error — with a bias caveat that deserves equal weight. On the holdout **2016-04-25 through 2016-05-22** (1,437 series, 40,236 item-days, **109,870** actual units), quote **WAPE**, not MAPE:

| Model | WAPE | MAPE (actual > 0 only) |
|---|---:|---:|
| Seasonal naive (lag-28) | **77.7%** | 87.8% |
| LightGBM | **64.9%** | 56.3% |

MAPE uses only the 25,302 days that sold at least one unit. Given that about 66% of California item-days are zeros, MAPE makes a poor headline; WAPE, by contrast, keeps those days in the score.

Both forecasts are **high**. Bias is **+1.1%** for the lag-28 copy and **+2.6%** for LightGBM (forecast minus actual, divided by actual units). A high forecast means the store plans **extra inventory**; it does not mean the model is protecting the shelf from stockouts. LightGBM wins on WAPE and MAPE, but it loses on bias: it is more high, not less.

## Recommendation

Use **LightGBM** for CA_3 food replenishment planning. Keep the **lag-28** forecast as the benchmark every time the model is refreshed. Do **not** claim dollar savings; none were calculated.

That said, one item does not follow the average. On **FOODS_3_090** (250,502 training units, 3,357 holdout units), the baseline WAPE **0.1975** beats LightGBM **0.2130**. A buyer should not be told the model is better on every item.

## Out of scope

Other stores (CA_1, CA_2, CA_4), other categories (HOUSEHOLD, HOBBIES), and inventory policy. Safety stock and reorder points are project 02. This page does not turn the error into a service level or a dollar figure.

## Where to look

- Longer write-up: [business-report.md](business-report.md)
- Scores and method: [03-construct.md](03-construct.md)
- Chart: [images/ca3_foods_forecast_vs_actual.png](../images/ca3_foods_forecast_vs_actual.png)
- Static dashboard (no Tableau login): [dashboards/ca3_foods_dashboard.html](../dashboards/ca3_foods_dashboard.html)

Publishing that chart to Tableau Public remains a manual step — import `data/processed/ca3_foods_holdout_predictions.csv` — and it was not done here.
