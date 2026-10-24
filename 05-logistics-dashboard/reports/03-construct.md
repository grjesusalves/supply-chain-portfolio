# Construct — Logistics network and executive dashboard (Olist)

PACE stage: **Construct**. This page freezes the distance bands and builds the weekly page the plan already specified. It reopens neither the grain, nor the haversine, nor the delivered-order population, and it writes no recommendation; that belongs to Execute.

The path through the page runs as follows: what was built, why each extract has the grain it has, the bands now that they are frozen, and what Execute still has to do.

## How I would say this in an interview

Analyze already answered the three questions. Customers and sellers do not sit in the same states, and a longer haul shows up in transit days and in freight per item, not in a second definition of distance. The weekly page is therefore not a new analysis; it presents those answers on one page, with the same denominators, for someone who will never read the SQL.

I froze the five bands Analyze proposed, and I did not move a cut after the chart was drawn. Fifty kilometers stays in the 50–200 band, and the tail stays in 1,000 kilometers or more.

The order count on the page covers every purchase that week, while the days and the on-time rate cover delivered orders alone. A week that was purchased and never delivered is not given a door time of zero. Freight stays on the item: the band for a delivery time is the farthest seller's, and the band for a freight bill is that item's own distance.

The HTML page is the stand-in. Tableau Public is the tool the plan named, and it was not published from this machine; there is no Tableau Public URL because I did not create one.

## What was built

`src/construct_logistics.py` loads the raw CSVs with the Analyze loader, runs `sql/kpi_analyze.sql`, and then runs `sql/kpi_construct.sql` in the same SQLite connection. The centroid and the haversine are the expressions in the Analyze file; this stage defines no second version. `band_of` is imported from `analyze_logistics.py`, and the script checks that those labels still match `order_band`. They do, on all 95,992 orders that have a distance.

The script writes three extracts and one page:

| Output | What it is | Rows |
|---|---|---:|
| `data/processed/weekly_scorecard.csv` | One row per purchase week | 101 |
| `data/processed/distance_bands.csv` | The frozen bands | 5 |
| `data/processed/state_coverage.csv` | Customers and sellers by state | 27 |
| `dashboards/logistics_weekly.html` | The weekly page | — |

`dashboards/TABLEAU.md` states which CSV feeds which view, and that the HTML page is what a reader opens before anyone publishes to Tableau Public. The workbook was not published.

Delivered purchases run from 15 Sep 2016 through 29 Aug 2018, and all purchases in the file from 4 Sep 2016 through 17 Oct 2018. The page is a weekly operating review of that historical extract, not a live feed. Currency is reais, and nothing is converted.

The script stops if a total disagrees with Analyze, rather than rewriting a denominator to make the page match. This run produced no disagreement.

## Why the grain of each extract matches the plan

The plan said the weekly page consists of seven items that do not share one row, and the extracts follow that rule.

| Page item | Grain | Who is in it |
|---|---|---|
| Orders purchased that week | Order | Every status. The week is the week of `order_purchase_timestamp`. |
| Median purchase-to-door, median transit, on-time rate | Order | Delivered, door timestamp present and after purchase. |
| Total freight, median freight per item, cross-state share | Item | Delivered items. Freight and the seller live on the item. |
| Distance-band order count and the two day medians | Order | Farthest seller. Orders with no distance are not in a band. |
| Median freight in the band table | Item | That item's own distance. Not the farthest seller. |
| Customers by state | Person | `customer_unique_id`, all customers, not only delivered orders. |
| Sellers by state | Seller row | The seller table. Not a warehouse, and not only sellers with a delivered item. |

The week starts on Monday. SQLite's day-of-week is 0 on Sunday, so days since Monday are `(w + 6) % 7`, and a purchase on Monday stays on that Monday. This is not an ISO week number, so the week does not split on 1 January.

The earliest purchase falls on 4 Sep 2016, a Sunday, so the first row is the Monday of that week, 29 Aug 2016. The last purchase week starts on 15 Oct 2018. The first and last weeks are partial, and they are kept.

101 weeks have at least one purchase. Eleven Mondays between the first and the last have none; they are not rows, and on the chart they appear as gaps, not zeros. Ten of the 101 weeks have purchases but no delivered order. Those weeks keep an order count, while the days, the on-time rate, the freight, and the cross-state share are blank. A missing delivery is neither zero days nor zero reais.

Medians use the two-central-row average, the same rule as Analyze. A weekly median is never averaged with the other weeks to produce the extract median; the extract median is computed on the orders, and the page titles use that number.

Negative transit, on 23 orders, is excluded from the transit median only. Those orders stay in the purchase-to-door median, the delivered order count, and the on-time rate. The weekly transit denominator sums to 96,446, which is 96,470 minus 1 order with no carrier timestamp minus those 23.

## The bands are frozen

Analyze proposed five cuts from the distance distribution and left them unfrozen; they are frozen here. The bands are right-open, and the last one includes the tail, the 8,678 km point among it. Fifty kilometers belongs to 50–200, not to 0–50.

| Band | Orders | Median purchase-to-door | Median transit | Items | Median freight per item |
|---|---:|---:|---:|---:|---:|
| 0–50 km | 11,672 | 4.9 days | 2.0 days | 13,449 | R$9.06 |
| 50–200 km | 12,832 | 6.5 | 3.4 | 14,708 | R$11.92 |
| 200–500 km | 30,258 | 10.0 | 7.0 | 34,748 | R$15.70 |
| 500–1,000 km | 25,829 | 12.1 | 8.8 | 29,495 | R$17.75 |
| 1,000 km or more | 15,401 | 16.4 | 13.2 | 17,251 | R$25.38 |

11,672 + 12,832 + 30,258 + 25,829 + 15,401 = 95,992, which is every delivered order with a distance. The other 478 delivered orders stay in the weekly time metrics and out of this table.

13,449 + 14,708 + 34,748 + 29,495 + 17,251 = 109,651, which is every delivered item with a distance. The other 538 items stay in the weekly freight total and out of this table; their freight sits inside the R$2,202,835.80, not in a second total.

The order columns use the farthest seller, while the freight column uses the item, so an order can have items in different bands. That is the plan, and the SQL groups by `order_band` and `item_band` from Analyze rather than cutting the kilometers again.

The same medians, at full precision, match `res_med_p2d_band`, `res_med_transit_band`, and `res_med_freight_band`. The page rounds days to one decimal and freight to cents, while the CSV keeps the full value.

## What the page shows

`dashboards/logistics_weekly.html` carries the seven items below as one interactive executive page: a KPI strip, the weekly trend, the band exhibits, and customers next to sellers by state, with tooltips, a weekly date range, band highlighting, and a state picker. It is drawn by `src/build_dashboard.py` from the three extracts (the script inlines `src/dashboard_assets/`), which `construct_logistics.py` calls at the end of its run. The interactions change only the view; the KPI cards stay full-period. Median handling appears only per band, from the Analyze band table, to show that the days sit in transit. There is no weekly handling series, no freight per kilogram, no review score, and no map.

1. **Orders purchased that week.** 99,441 orders, every status.
2. **Median purchase-to-door and median transit.** On 96,470 delivered orders, 10.2 days and 7.1 days. The purchase-to-door median is the average of the two central orders, 10.217476851539686 days, because 96,470 is even. The transit median is 7.10031250026077 days, on 96,446 orders.
3. **On-time rate, calendar date.** 89,936 / 96,470 = 93.2%. The estimate is stored at midnight, so the comparison is on the date. A weekly rate reflects that week's orders; it is not averaged across weeks to reach 93.2%.
4. **Total freight and median freight per item.** R$2,202,835.80 on 110,189 delivered items, with a median item of R$16.26. Zero freight stays in, and so do items with no distance.
5. **Cross-state share.** 70,328 / 110,189 = 63.8% of delivered items.
6. **The band table** above: order count, median purchase-to-door, median transit, and median freight per item.
7. **Customers by state next to sellers by state.** 96,096 people and 3,095 sellers across 27 states. São Paulo holds 40,302 / 96,096 = 41.9% of the people and 1,849 / 3,095 = 59.7% of the sellers. The state rows sum to 96,136 people, because 39 people appear in more than one state, and the share uses 96,096, not 96,136. Alagoas, Amapá, Roraima, and Tocantins have customers and no sellers. The chart matches `res_state` from Analyze on both people and sellers.

These are the same figures as in [02-analyze.md](02-analyze.md); Construct did not recompute them on a different population.

## What Execute still has to do

The README executive summary is still the placeholder, and the recommendation and impact lines remain empty; this file does not fill them.

Execute writes the executive summary, the business report, and the recommendation. It is the stage that says what a logistics lead, a fulfillment lead, or a finance partner should do with the page; this file does not.

Tableau Public remains a manual publish, with `dashboards/TABLEAU.md` as the sheet list and the HTML page as the stand-in until that publication exists. Do not add a URL that was never published.

Do not retune the bands in Execute to make a bar smoother. Do not put review score or freight per kilogram on the weekly page, and do not add a weekly handling series. Do not convert reais, and do not treat a week with no delivery as zero days.

## How to reproduce

From the project folder:

```bash
python3 src/construct_logistics.py
```

The script needs the raw CSVs in `data/raw/` and the packages Analyze already used: pandas, NumPy, and matplotlib. It reads `sql/kpi_analyze.sql` and `sql/kpi_construct.sql`, and it does not commit.