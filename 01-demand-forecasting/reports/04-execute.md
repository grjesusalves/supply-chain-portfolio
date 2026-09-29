# Execute — CA_3 food forecast

PACE stage: **Execute**. This is the page a hiring manager can read in two minutes. It does not refit a model. The scores are the Construct holdout, used exactly.

## Question

For Walmart store **CA_3**, food only, how many units should replenishment expect over the next 28 days, and is a LightGBM forecast better than copying the same weekday four weeks ago?

## Answer

Yes on error, with a bias caveat. On the holdout **2016-04-25 through 2016-05-22** (1,437 series, 40,236 item-days, **109,870** actual units), quote **WAPE**, not MAPE:

| Model | WAPE | MAPE (actual > 0 only) |
|---|---:|---:|
| Seasonal naive (lag-28) | **77.7%** | 87.8% |
| LightGBM | **64.9%** | 56.3% |

MAPE uses the 25,302 days that sold at least one unit. About 66% of California item-days are zeros, so MAPE is a bad headline. WAPE keeps those days in the score.

Both forecasts are **high**. Bias is **+1.1%** for the lag-28 copy and **+2.6%** for LightGBM (forecast minus actual, divided by actual units). A high forecast means the store plans **extra inventory**. It does not mean the model is protecting the shelf from stockouts. LightGBM wins on WAPE and MAPE and loses on bias: it is more high, not less.

## Recommendation

Use **LightGBM** for CA_3 food replenishment planning. Keep the **lag-28** forecast as the benchmark every time the model is refreshed. Do **not** claim dollar savings. None were calculated.

One item does not follow the average. On **FOODS_3_090** (250,502 training units, 3,357 holdout units), the baseline WAPE **0.1975** beats LightGBM **0.2130**. Do not tell a buyer the model is better on every item.

## Out of scope

Other stores (CA_1, CA_2, CA_4), other categories (HOUSEHOLD, HOBBIES), and inventory policy. Safety stock and reorder points are project 02. This page does not turn the error into a service level or a dollar figure.

## Where to look

- Longer write-up: [business-report.md](business-report.md)
- Scores and method: [03-construct.md](03-construct.md)
- Chart: [images/ca3_foods_forecast_vs_actual.png](../images/ca3_foods_forecast_vs_actual.png)
- Static dashboard (no Tableau login): [dashboards/ca3_foods_dashboard.html](../dashboards/ca3_foods_dashboard.html)

Publishing that chart to Tableau Public is a manual step: import `data/processed/ca3_foods_holdout_predictions.csv`. It was not done here.
