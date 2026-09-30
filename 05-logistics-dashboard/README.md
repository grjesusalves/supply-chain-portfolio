# Logistics Performance Dashboard — Olist Brazilian E-Commerce

> Executive summary — fill in as the project progresses.

## Business Question
Where are our customers relative to our sellers, how does distance affect delivery time and freight cost, and what does leadership need to see weekly?

## Data
See [`data/README.md`](data/README.md) for source, license, and file inventory.

## Approach (PACE: Plan, Analyze, Construct, Execute)
- **Plan:** question, grain, distance, and KPI definitions. See [`reports/01-plan.md`](reports/01-plan.md).
- **Analyze:** _data cleaning, EDA, key descriptive stats_
- **Construct:** _models / queries / calculations built_
- **Execute:** _how results are delivered (dashboard, report, recommendation)_

## Key Findings
- _Finding 1 (quantified)_
- _Finding 2_
- _Finding 3_

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
