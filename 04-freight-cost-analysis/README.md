# Freight Cost Analysis — USAID SCMS Shipments

> Executive summary — fill in as the project progresses.

## Business Question
What drives freight cost per kg / per shipment (mode, country, vendor, INCO term, weight), and where can freight spend be reduced?

## Data
See [`data/README.md`](data/README.md) for source, license, and file inventory.

## Approach (PACE: Plan, Analyze, Construct, Execute)
- **Plan:** question, shipment grain, and the freight metrics we will trust. See [`reports/01-plan.md`](reports/01-plan.md).
- **Analyze:** the shipment-grain check, the freight and weight text classes, and the reason no rate is published yet are in [`reports/02-analyze.md`](reports/02-analyze.md). No regression is fit in this stage.
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
Python (pandas, statsmodels), SQL, Excel, Tableau/Power BI

## How to Reproduce
1. Download raw data into `data/raw/` (see `data/README.md`).
2. Run notebooks in `notebooks/` in order; reusable code lives in `src/`, SQL in `sql/`.
3. Processed outputs go to `data/processed/`; charts to `images/`; dashboards to `dashboards/`; write-ups to `reports/`.
