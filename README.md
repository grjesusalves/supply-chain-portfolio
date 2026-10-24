# Supply Chain Analytics Portfolio

Business Analytics student, **UMass Amherst** — a portfolio built for **entry-level Supply Chain Analyst** roles.
Five projects, one discipline: each follows the PACE framework (Plan, Analyze, Construct, Execute) and closes with an executive summary written for the person who has to make the decision, not for the person who wrote the code.

| # | Project | Business question | Dataset | Key skills |
|---|---|---|---|---|
| 01 | [Demand Forecasting](01-demand-forecasting/) | Forecast 28-day item-store demand for Walmart | M5 Forecasting Accuracy (Walmart) | Time series, feature engineering, forecast accuracy (WRMSSE/MAPE) |
| 02 | [Inventory Optimization](02-inventory-optimization/) | Set safety stock / reorder points / EOQ for target service level | Output of Project 01 | Inventory policy, service level, cost trade-offs |
| 03 | [Late Delivery Risk](03-late-delivery-risk/) | Predict and explain late deliveries | DataCo Smart Supply Chain (Mendeley) | Classification, feature importance, SQL |
| 04 | [Freight Cost Analysis](04-freight-cost-analysis/) | What drives freight cost and where to save | USAID SCMS Shipment Pricing Data | Regression, cost drivers, spend analysis |
| 05 | [Logistics Dashboard](05-logistics-dashboard/) | Where customers sit relative to sellers, and how distance affects delivery time and freight | Olist Brazilian E-Commerce | SQL joins, geographic analysis, interactive HTML dashboard (GitHub Pages) |

## Repository structure
Every project shares the same layout, which means a reader who has navigated one can navigate all five:
```
NN-project/
├── README.md          # executive summary (PACE)
├── data/
│   ├── README.md      # source, license, download date, file list, row counts
│   ├── raw/           # original downloads (git-ignored — see data/README.md to re-download)
│   └── processed/     # cleaned / derived data
├── notebooks/  sql/  src/  reports/  dashboards/  images/
```

## Reproducing
Raw data is not committed; the files are simply too large. That said, nothing is left to guesswork: each `data/README.md` records the exact source URL and download command, so every result in this portfolio can be rebuilt from the original source.
