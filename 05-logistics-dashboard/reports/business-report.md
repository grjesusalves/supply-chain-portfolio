# Business report — where customers sit, and what distance shows up as

This report is written for a logistics lead, a fulfillment lead, and a finance partner. The two-minute page is [04-execute.md](04-execute.md), and the one-page decision is [executive-summary.md](executive-summary.md). Note that nothing here is a saving, and nothing here is in dollars.

## Question

Where are our customers relative to our sellers, how does distance sit next to delivery time and freight, and what should leadership look at every week?

The person who can act on the answer differs for each part. Coverage is a logistics conversation. A long wait that grows with kilometers is a network conversation, whereas a long wait inside the same city would have been a seller conversation. Freight is a finance conversation, and only if weight is in the room.

## What we looked at

Purchases in the file run from **4 Sep 2016** through **17 Oct 2018**, and the completed deliveries used below were purchased from **15 Sep 2016** through **29 Aug 2018**. The file is the public Olist extract: historical, not a live feed. Money is in Brazilian reais, and it was not converted.

A customer person is a `customer_unique_id`. An order is not a person: there are **96,096** people and **99,441** orders. A seller is a row in the seller table, **3,095** of them, not a warehouse.

Delivery time and freight rely on completed deliveries alone: **96,470** orders and **110,189** items. The customer's wait is purchase-to-door, the time from purchase to the door timestamp, and that wait is split so that the map is not blamed for the seller. Handling runs from approval to carrier handoff; transit, from carrier handoff to the door. The headline is the median, because a few very late orders pull a mean upward.

On time means the door date falls on or before the promised calendar date. The promise in this file is stored at midnight, so a delivery later on the promised day still counts as on time. The rate is never the only time number.

Olist does not publish a distance. Distance here is the straight-line kilometers between the average coordinate of the customer's zip prefix and the average coordinate of the seller's zip prefix; it is neither the road nor what a carrier charges. Five bands were frozen before this recommendation: under 50 km, 50–200, 200–500, 500–1,000, and 1,000 km or more. They were not moved to make a chart smoother.

An order can have more than one seller. Given that the customer waits for the whole order, delivery time uses the farthest seller on that order; the freight bill, by contrast, sits on the item, so each item keeps its own distance and its own freight. **1,275** of the **96,470** delivered orders have more than one seller, and the farthest-seller rule was kept.

**538** delivered items and **478** delivered orders have no distance, because a zip prefix had no coordinate. They stay in the weekly totals but are not assigned to a band, nor were they filled in with a state average.

## What we found

### Customers and sellers are not in the same places

Customers are in **27** states; sellers, in **23**.

| State | Share of people | Share of sellers | What it means |
|---|---:|---:|---|
| São Paulo | 41.9% (40,302 / 96,096) | 59.7% (1,849 / 3,095) | Most of the sellers, and a large but smaller share of the people |
| Rio de Janeiro | 12.9% | 5.5% | More of the customers than of the sellers |
| Paraná | 5.1% | 11.3% | Seller-heavy |

Four states have customers and no seller: Alagoas, Tocantins, Amapá, and Roraima. Together they account for **786** people and **807** orders (Alagoas 401 people and 413 orders, Tocantins 273 and 280, Amapá 67 and 68, Roraima 45 and 46). The gap is real; it is simply not where most of the volume sits.

Of the delivered items, **70,328 / 110,189 = 63.8%** go to a customer in a different state from the seller. Short hauls stay mostly inside one state, while the 1,000 km or more band is entirely cross-state in this extract.

This is a coverage picture, not a recommendation to open a building.

### The extra days are in transit

| | Median |
|---|---:|
| Purchase-to-door, 96,470 delivered orders | 10.2 days |
| Transit, carrier to door | 7.1 days |
| Handling, approval to carrier | 1.8 days |

| Band | Orders | Median purchase-to-door | Median transit | Median handling | On time |
|---|---:|---:|---:|---:|---|
| Under 50 km | 11,672 | 4.9 days | 2.0 days | 1.7 days | 11,153 / 11,672 = 95.6% |
| 50–200 km | 12,832 | 6.5 | 3.4 | 1.8 | 12,234 / 12,832 = 95.3% |
| 200–500 km | 30,258 | 10.0 | 7.0 | 1.8 | 28,323 / 30,258 = 93.6% |
| 500–1,000 km | 25,829 | 12.1 | 8.8 | 1.9 | 24,000 / 25,829 = 92.9% |
| 1,000 km or more | 15,401 | 16.4 | 13.2 | 1.9 | 13,792 / 15,401 = 89.6% |

11,672 + 12,832 + 30,258 + 25,829 + 15,401 = 95,992, the delivered orders that have a distance. The other **478** remain in the 10.2 day median and out of this table.

Handling does not move; it stays between **1.7 and 1.9 days**. Transit does, from **2.0 days** under 50 km to **13.2 days** at 1,000 km or more.

The reported medians in the shortest and longest bands differ by **11.5 days** of purchase-to-door (16.4 − 4.9) and by **11.2 days** of transit (13.2 − 2.0), while handling differs by **0.2 days** (1.9 − 1.7). Present that as a difference in this extract, not as days the business would get back.

### On time is not the same as fast

**89,936 / 96,470 = 93.2%** of delivered orders meet the promised calendar date; under that rule, **6,534** orders (**6.8%**) are late.

The longest band is still about **89.6%** on time (13,792 / 15,401), yet the median customer there waits **16.4 days**. The shortest band is **95.6%** on time, with a wait of **4.9 days**. The promise moves with the haul, and a weekly review that shows only the rate will call both of those weeks a success.

### Freight per item rises. That is not a price list.

Total freight on the **110,189** delivered items is **R$2,202,835.80**, and the median item costs **R$16.26**.

| Band | Items | Median freight per item | Median freight per kg | Median weight |
|---|---:|---:|---:|---:|
| Under 50 km | 13,449 | R$9.06 | R$18.33 | 500 g |
| 50–200 km | 14,708 | R$11.92 | R$17.27 | 610 g |
| 200–500 km | 34,748 | R$15.70 | R$20.13 | 800 g |
| 500–1,000 km | 29,495 | R$17.75 | R$23.88 | 710 g |
| 1,000 km or more | 17,251 | R$25.38 | R$36.92 | 650 g |

Median freight per item is higher in every longer band, and the gap between the reported medians at the two ends is **R$16.32** (25.38 − 9.06). That is not money sitting on the table; two medians are not a bill.

Freight per kilogram is the check on weight. The median across items with a positive weight is **R$22.22**. Within the bands, it falls from **R$18.33** to **R$17.27** in the 50–200 km band, where the median item is heavier (**610 g** versus **500 g**), and then rises; past that band, both item freight and per-kilogram freight are higher. That pattern is consistent with a weight mix. It is neither a rate card nor a cause.

The **538** items with no distance sit inside the **R$2,202,835.80** and outside the band table; their freight is not a second total.

## What we recommend

Use the weekly page as four checks, and stop wherever a check would require a number this file does not have.

1. **Coverage.** Read customers by state beside sellers by state. São Paulo is seller-heavy; Rio de Janeiro has a larger share of people than of sellers; Paraná has a larger share of sellers than of people; and four states have no seller at all. **63.8%** of delivered items cross a state. Take that to a coverage conversation, not to a site-selection model.
2. **Where the days sit.** If a destination is slow, look at transit. Do not open a seller-handling program for a pattern absent from the handling column, which is flat at **1.7–1.9 days**. The **11.5 day** and **11.2 day** gaps are differences of medians in this extract, not a target for days saved.
3. **The promise.** Put median purchase-to-door days and median transit days on the same page as the on-time rate. **93.2%** on time, and about **89.6%** in the longest band, still leaves a **16.4 day** median wait. Do not manage to the rate alone.
4. **Freight.** Show median freight per item by band, but do not reprice from that slope, because weight moves too: freight per kilogram dips, then rises. Do not book a saving; none was estimated.

## What we will not claim

- We will not claim that kilometers caused the extra transit or the higher freight. Product mix, the day of the week, and the way the promise was set can all move with distance, and the file names no carrier.
- We will not claim that sellers are fast because handling is flat. Flat means only that the extra days in the longer bands are not sitting in the handling leg.
- We will not claim that on time means a short wait.
- We will not claim a road distance, a driving time, or a carrier's price; the kilometers are straight-line.
- We will not recommend a warehouse, a route, or a new promise formula, given that the file does not say how Olist built the estimate.
- We will not convert reais to dollars, and we will not invent a freight saving.
- We will not treat the **538** items or **478** orders with no distance as if they had one.

## Where the dashboard is

The dashboard is one HTML page, published at <https://grjesusalves.github.io/supply-chain-portfolio/05-logistics-dashboard/>.

The copy in this repo is [dashboards/logistics_weekly.html](../dashboards/logistics_weekly.html). It is one interactive page: full-period KPI cards (delivered orders, median purchase-to-door with transit and handling, on-time rate, cross-state share, freight); a weekly trend of orders, median purchase-to-door, and on-time rate with a date-range control; the frozen distance bands (median handling next to transit, on-time with the median wait, freight per item, and the band table); and customers by state next to sellers by state, with a state picker and sort. Tooltips, the date range, and the highlights change only the view; the KPI cards stay full-period, and a selected range shows sums of weekly counts, not a new median. The page shows no review score, no weekly handling series, and no freight per kilogram. Those checks live in this report rather than in a second weekly chart.

There is no Tableau Public URL, because the workbook was not published. Should someone publish later, the sheet list is [dashboards/TABLEAU.md](../dashboards/TABLEAU.md), and the definitions the page uses are the SQL in `sql/`.