# Freight Cost Analysis — USAID SCMS Shipments

> On 6,174 weighed shipments the median freight is 7.263901636359817 USD per kg. The mean, 38.93012311964861, is a tail (maximum 31087.705 on DN-1683, a 4 kg air charter). Air's median is 10.02401980861159, above truck 2.5032950842130273 and ocean 1.6810197953137624.
>
> A log model that holds weight puts truck about 36 percent below air and air charter about 66 percent above air. The 66 percent is not a planning factor. After rates above the weighed-set 95th percentile are dropped, the charter gap is about 21 percent (exp(coefficient) − 1 = 0.21122129787951574). Orgenics stays high (about 77 percent; 599 of 600 model rows are air). No country keeps an uncontrolled lead. Ocean's cheap median is tangled with DDP (193 of 282 ocean model rows).
>
> The only dollar figure is a what-if, not a saving. Weighed air at or above the weighed-set median weight (1054.5 kg), priced at the truck median on that slice (1.5292046183450931), and only where air is higher: 1,477 notes, 4761674.0 kg, actual freight 33085383.96 USD, difference 25803810.088146247 USD. A 25 percent share of that gap is 6450952.522036562 USD. Both are upper bounds. Included-in-price (593) and invoiced separately (239) are not in the figure. Dollars are historical, delivered 2006-05-02 through 2015-09-14.

## Business Question
What drives freight cost per kg / per shipment (mode, country, vendor, INCO term, weight), and where can freight spend be reduced?

## Data
See [`data/README.md`](data/README.md) for source, license, and file inventory.

## Approach (PACE: Plan, Analyze, Construct, Execute)
- **Plan:** question, shipment grain, and the freight metrics we will trust. See [`reports/01-plan.md`](reports/01-plan.md).
- **Analyze:** the raw-string gate failed, and the accepted rule (2026-09-29) is the Yes line of each ASN/DN. Median freight per kg on the weighed set, with the mean beside it, is in [`reports/02-analyze.md`](reports/02-analyze.md). No regression is fit in this stage.
- **Construct:** OLS of log freight per kilogram on the weighed shipments that have a named mode. See [`reports/03-construct.md`](reports/03-construct.md). No savings scenario in this stage.
- **Execute:** the heavy-air what-if, the recommendation, and the Tableau status are in [`reports/04-execute.md`](reports/04-execute.md). The one-page write-up is [`reports/executive-summary.md`](reports/executive-summary.md). The longer write-up is [`reports/business-report.md`](reports/business-report.md). Tableau Public was not published.

## Key Findings
- On the weighed set, median freight per kg is 7.263901636359817 (n = 6,174). The mean is 38.93012311964861. Air's weighed median is 10.02401980861159 (n = 4,096), against truck 2.5032950842130273 and ocean 1.6810197953137624.
- Holding log weight, grouped INCO, and an Orgenics indicator, truck is about 36 percent below air and the interval excludes zero. The charter premium shrinks from about 66 percent to about 21 percent when rates above the weighed-set p95 (67.64871004566209) are dropped. Orgenics stays about 77 percent higher (599 of 600 model rows are air). Botswana leads the uncontrolled country ranking and has 7 weighed air shipments inside the 500–5,000 kg band.
- A what-if, not a coefficient: 1,477 weighed air notes at or above 1054.5 kg and above the heavy-truck median rate (1.5292046183450931) account for a gap of 25803810.088146247 USD. A 25 percent share of that gap is 6450952.522036562 USD. Both are upper bounds. The 593 included-in-price and 239 invoiced-separately shipments are excluded, not zeroed.

## Recommendation
Use the median rate, not the mean, as the description of a typical shipment. Challenge Orgenics on air. Do not plan on the 66 percent charter gap; the cautious association is about 21 percent and is still not a saving. Do not treat ocean's low median as a mode to switch to while DDP hides freight (193 of 282 ocean model rows are DDP). If a mode conversation happens, start from the heavy-air what-if and label even the 25 percent share as an upper bound that still has to pass lane, lead time, cold chain, and INCO.

## Impact
Not a booked saving. Upper-bound what-if only: 25803810.088146247 USD if every one of 1,477 heavy air notes had moved at the observed heavy-truck median of 1.5292046183450931 USD per kg, or 6450952.522036562 USD at a 25 percent share of that gap. Historical prices, delivered to client 2006-05-02 through 2015-09-14. Included-in-price and invoiced-separately freight are not in the figure.

## Tools
Python (pandas, statsmodels) and SQL for the Analyze rate checks. Tableau Public is not published; the extract is dashboards/shipment_weighed.csv (6,174 weighed shipments).

## How to Reproduce
1. Download raw data into `data/raw/` (see `data/README.md`). The project copy is already on disk and stays git-ignored.
2. Run notebooks in `notebooks/` in order; reusable code lives in `src/`, SQL in `sql/`.
3. The Execute scenario is `python src/execute_freight.py` from this folder, or `python 04-freight-cost-analysis/src/execute_freight.py` from the repo root.
4. Processed outputs go to `data/processed/`; charts to `images/`; dashboards to `dashboards/`; write-ups to `reports/`.
