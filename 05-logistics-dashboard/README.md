# Logistics Performance Dashboard — Olist Brazilian E-Commerce

> Executive summary — fill in as the project progresses.

## Business Question
Where are our customers relative to our sellers, how does distance affect delivery time and freight cost, and what does leadership need to see weekly?

## Data
See [`data/README.md`](data/README.md) for source, license, and file inventory.

## Approach (PACE: Plan, Analyze, Construct, Execute)
- **Plan:** question, grain, distance, and KPI definitions. See [`reports/01-plan.md`](reports/01-plan.md).
- **Analyze:** grain, distance, delivery time, and freight. See [`reports/02-analyze.md`](reports/02-analyze.md).
- **Construct:** _models / queries / calculations built_
- **Execute:** _how results are delivered (dashboard, report, recommendation)_

## Key Findings
- 63.8% of delivered items cross a state line (70,328 / 110,189). São Paulo has 59.7% of sellers (1,849 / 3,095) and 41.9% of customer people (40,302 / 96,096). Rio de Janeiro has 12.9% of the people and 5.5% of the sellers.
- Median purchase-to-door time on 96,470 delivered orders is 10.2 days. Median transit rises from 2.0 days under 50 km to 13.2 days at 1,000 km or more. Median seller handling stays between 1.7 and 1.9 days, so the extra wait is not a handling time.
- Median freight per item rises from R$9.06 under 50 km to R$25.38 at 1,000 km or more. Median freight per kilogram is R$22.22 and is not higher in every longer band. On time, by calendar date, is 93.2% (89,936 / 96,470), including 89.6% in the longest band where the median wait is 16.4 days.

## Recommendation
_What should the business do, and why?_

## Impact
_Estimated $ / % / service-level impact._

## Tools
SQL (PostgreSQL/SQLite), Python (pandas), Tableau/Power BI

## How to Reproduce
1. Download raw data into `data/raw/` (see `data/README.md`).
2. Run notebooks in `notebooks/` in order; reusable code lives in `src/`, SQL in `sql/`.
3. Processed outputs go to `data/processed/`; charts to `images/`; dashboards to `dashboards/`; write-ups to `reports/`.
