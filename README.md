# Supply Chain Analytics Portfolio

Business Analytics student, **UMass Amherst** — portfolio targeting **entry-level Supply Chain Analyst** roles.
Each project follows the PACE framework (Plan, Analyze, Construct, Execute) and is written up as an executive summary.

| # | Project | Business question | Dataset | Key skills |
|---|---|---|---|---|
| 01 | [Demand Forecasting](01-demand-forecasting/) | Forecast 28-day item-store demand for Walmart | M5 Forecasting Accuracy (Walmart) | Time series, feature engineering, forecast accuracy (WRMSSE/MAPE) |
| 02 | [Inventory Optimization](02-inventory-optimization/) | Set safety stock / reorder points / EOQ for target service level | Output of Project 01 | Inventory policy, service level, cost trade-offs |
| 03 | [Late Delivery Risk](03-late-delivery-risk/) | Predict and explain late deliveries | DataCo Smart Supply Chain (Mendeley) | Classification, feature importance, SQL |
| 04 | [Freight Cost Analysis](04-freight-cost-analysis/) | What drives freight cost and where to save | USAID SCMS Shipment Pricing Data | Regression, cost drivers, spend analysis |
| 05 | [Logistics Dashboard](05-logistics-dashboard/) | Track delivery KPIs (lead time, OTD, freight, reviews) | Olist Brazilian E-Commerce | SQL joins, KPI design, Tableau/Power BI |

## Repository structure
Every project has the same layout:
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
Raw data is not committed (size). Each `data/README.md` contains the exact source URL and download command.
