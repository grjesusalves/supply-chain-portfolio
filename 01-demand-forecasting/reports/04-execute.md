# Execute — CA_3 food forecast

PACE stage: **Execute**. This is the page a hiring manager can read in two minutes, and it is deliberately narrow. It refits nothing; every score below comes from the Construct holdout, used exactly as computed.

## Question

For Walmart store **CA_3**, and for food alone, how many units should replenishment expect over the next 28 days — and does a LightGBM forecast actually beat the simplest credible alternative, which is to copy the same weekday from four weeks earlier?

## Answer

On error, the answer is yes; on bias, the answer comes with a caveat that deserves equal weight. The holdout runs **2016-04-25 through 2016-05-22** and covers 1,437 series, 40,236 item-days and **109,870** actual units. On that window, the figure to quote is **WAPE**, not MAPE:

| Model | WAPE | MAPE (actual > 0 only) |
|---|---:|---:|
| Seasonal naive (lag-28) | **77.7%** | 87.8% |
| LightGBM | **64.9%** | 56.3% |

MAPE can only be computed on the 25,302 days that sold at least one unit. Given that about 66% of California item-days are zeros, MAPE silently discards most of the problem and makes a poor headline; WAPE, by contrast, keeps those days in the score.

Both forecasts run **high**. Measured as forecast minus actual, divided by actual units, bias is **+1.1%** for the lag-28 copy and **+2.6%** for LightGBM. A high forecast means the store plans **extra inventory**; it does not mean the model is shielding the shelf from stockouts, and the two should not be confused. LightGBM wins on WAPE and on MAPE. On bias, however, it loses — it is more high, not less.

## Recommendation

Use **LightGBM** for CA_3 food replenishment planning, and keep the **lag-28** forecast as the benchmark every time the model is refreshed, so that any erosion in its edge is caught early. Do **not** claim dollar savings; none were calculated, and none can be inferred from unit error alone.

That said, the average conceals at least one undeniable exception. **FOODS_3_090** is the store's heaviest food item, with 250,502 training units and 3,357 holdout units, and on it the baseline WAPE of **0.1975** beats LightGBM's **0.2130**. A buyer, in other words, should not be told that the model is better on every item.

## Out of scope

This page does not cover the other stores (CA_1, CA_2, CA_4), the other categories (HOUSEHOLD, HOBBIES) or inventory policy; safety stock and reorder points belong to project 02. Nor does it translate forecast error into a service level or a dollar figure, given that neither follows directly from the scores above.

## Where to look

- Longer write-up: [business-report.md](business-report.md)
- Scores and method: [03-construct.md](03-construct.md)
- Chart: [images/ca3_foods_forecast_vs_actual.png](../images/ca3_foods_forecast_vs_actual.png)
- Static dashboard (no Tableau login): [dashboards/ca3_foods_dashboard.html](../dashboards/ca3_foods_dashboard.html)

Publishing that chart to Tableau Public remains a manual step — one that requires importing `data/processed/ca3_foods_holdout_predictions.csv` — and it was not done here. The forecast, then, is ready for planning use; what remains is presentation, not analysis.
