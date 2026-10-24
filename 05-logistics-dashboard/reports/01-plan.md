# Plan — Logistics network and executive dashboard (Olist)

PACE stage: **Plan**. This page settles the question, the grain of each metric, and what "distance," "delivery time," and "freight" mean. It computes no rate, draws no map, and builds no dashboard; those tasks belong to Analyze, Construct, and Execute.

Read this page first. The checks Analyze will run are listed at the bottom, and the project README points here.

## How I would say this in an interview

Leadership is not asking for a map. It is asking whether customers and sellers sit in the same places, whether a longer haul genuinely means a slower delivery and a higher freight bill, and which few numbers deserve a look every week.

I treat that as three questions that share one dataset and must not share one row grain.

The first is a network question: where are customers, where are sellers, and what share of volume crosses a state line? That is a join and a count, with no model.

The second is a relationship question. Olist does not publish a distance column, so I must build one from zip-prefix coordinates and set it beside delivery days and freight. A raw chart, however, is not a cause: a heavy product shipped far will look expensive even if the extra kilometers did nothing. Plan writes that caveat down before anyone sees a slope and calls it a finding.

The third is a communication question. The weekly page is not the analysis; it is the five-minute version of the analysis for someone who will never read the SQL. If a number is missing from that page, it is because a VP cannot act on it weekly, not because we failed to chart it.

Plan is where those rules are written, before a chart can tempt me to change the question.

## Business question

Where are our customers relative to our sellers, how does distance affect delivery time and freight cost, and what does leadership need to see weekly?

Who uses the answer:

- A **logistics lead** uses the network picture. If demand sits in states where we have few sellers, the conversation is coverage, not a faster carrier.
- A **fulfillment lead** uses delivery days split into seller handling and transit. A long wait inside the same city is a seller problem; a long wait that grows with kilometers is a network problem. Those call for different meetings.
- A **finance partner** uses freight next to distance and next to weight, and needs to see whether we are paying for distance, for heavy goods, or for both.
- The **weekly reader** is a non-technical executive: one page, the same definitions every week, and no new chart unless it changes a decision.

## Grain, because one order is not one distance

An Olist order can contain several items, and those items can come from different sellers. Delivery timestamps live on the order; freight and the seller live on the item. The customer zip lives on the customer row attached to the order, and the seller zip on the seller.

| Question | Grain | Why |
|---|---|---|
| Where are customers? | `customer_unique_id` | One person can place many orders. Counting `customer_id` would count orders, not people. |
| Where is demand? | `order_id` | Leadership cares about orders, not about unique people, when they ask "where is the volume." |
| Where are sellers? | `seller_id` | The seller table has one zip prefix per seller. This is not a warehouse network. |
| Freight versus distance | order item | `freight_value` is stored on the item, and each item has one seller. |
| Delivery time versus distance | order | The customer waits once, for the order. The clock is on the order, not on the item. |

**Decision.** On an order with more than one seller, delivery time is compared with the **farthest** seller-to-customer distance on that order. The customer cannot receive the order until the last piece is in motion, so the short hop is not the one that explains the wait. Analyze will first count how often an order has more than one seller; if that share is tiny, the choice barely matters, and we will say so. We will not switch the rule after seeing the chart.

Freight never uses that maximum: each item keeps its own distance and its own `freight_value`.

## What "distance" means

There is no distance field. `olist_geolocation_dataset.csv` holds latitude and longitude by zip prefix, with many rows per prefix (1,000,163 rows in the file we already downloaded; see `data/README.md`).

**Decision.** For each zip prefix, take the mean latitude and the mean longitude; that is the prefix centroid. Distance is the haversine distance, in kilometers, between the customer prefix centroid and the seller prefix centroid. Haversine is great-circle distance on a sphere. It is not road distance, not driving time, and not what a carrier charges.

A prefix with no geolocation row cannot have a distance. Those items stay in the volume counts and drop out of every distance metric, and Analyze will count them. We will not fill them with a state average, because a filled-in distance would invent the very pattern we are trying to measure.

Joining geolocation to items **before** collapsing to one centroid per prefix would multiply rows. The SQL in `sql/kpi_definitions.sql` therefore aggregates geolocation first, and Analyze will prove the row counts before and after the join.

## What "delivery time" means

**Decision.** Headline delivery time is purchase-to-door: `order_delivered_customer_date` minus `order_purchase_timestamp`, in days. That is what the customer feels.

The population is orders whose `order_status` is `delivered` and whose delivered timestamp is present and later than the purchase timestamp; anything else is not a completed delivery. Analyze will list the other statuses and the null timestamps, which stay out of the median.

We will also split purchase-to-door into three legs, given that distance can explain only the last one:

- Approval lag: purchase to `order_approved_at`.
- Handling: approval to `order_delivered_carrier_date`. This is mostly the seller, not the map.
- Transit: carrier handoff to `order_delivered_customer_date`. This is the leg that should grow with kilometers.

The weekly page shows purchase-to-door as the headline, with transit beside it. If transit is flat across distance while handling is not, we do not recommend a network change.

**On time** means delivered on or before `order_estimated_delivery_date`. Olist's estimate may already be looser for far destinations, so a far state can be slow in days and still "on time." We therefore report both median days and the on-time rate; reporting only the rate would hide precisely the thing distance is supposed to affect.

We use the median for days and show the mean beside it. A few very late orders pull a mean upward, and leadership acts on the typical order.

## What "freight" means

**Decision.** Freight is `freight_value` on the order item, in Brazilian reais, for the same delivered orders used in the delivery-time metrics. The population is shared so that the two relationships can be read together.

We will report:

- Total freight.
- Median freight per item.
- Freight per kilogram, after joining `olist_products_dataset.csv` on `product_id`. Weight is the control, and a chart of freight against distance that ignores weight is not an answer.

Items with missing or non-positive weight stay in the freight totals and drop out of freight per kilogram; Analyze will count them.

Price is context, not a driver we are testing. We may show freight as a share of `price`, so that a R$15 freight bill reads differently on a cheap item than on an expensive one. We will not claim that price causes freight.

## What leadership sees weekly

The data is a historical public extract, not a live feed. "Weekly" means the page is shaped as a weekly operating review: one row per week of `order_purchase_timestamp`, plus the cuts below. We will not describe it as a live pipeline.

The page, and only the page, contains:

1. Orders purchased that week.
2. Median purchase-to-door days, and median transit days.
3. On-time rate against the estimated delivery date.
4. Total freight and median freight per item.
5. Share of items that cross a state line (customer state different from seller state).
6. One distance-band table: order count, median purchase-to-door days, median transit days, median freight per item.
7. Customers by state next to sellers by state, so coverage is visible without a second report.

Review score is not on this page. The project folder used to mention reviews, but this brief does not, and a star rating answers neither where customers sit nor what distance does to time and freight.

Distance bands will be fixed in Analyze after we see the distribution, then written down and left unchanged rather than adjusted to make a chart look smoother. Plan does not invent the cut points.

## KPIs we will compute later, and the formulas now

None of these numbers is calculated at this stage. The formulas are fixed now so that Analyze cannot quietly change the denominator. File sizes and row counts already recorded in `data/README.md` are inventory, not findings.

**Cross-state share.** Among delivered items with both a customer state and a seller state, the share where those states differ.

**Median purchase-to-door.** Median of purchase-to-door days on delivered orders with a usable timestamp pair.

**On-time rate.** Among those same orders, the share delivered on or before `order_estimated_delivery_date`. Orders with a null estimate drop out of this rate alone, and Analyze will count them.

**Median freight per item.** Median of `freight_value` on delivered items.

**Freight per kilogram.** `freight_value` divided by product weight in kilograms, on delivered items with a positive weight. The product table stores weight in grams, and the SQL converts it.

**Distance band summary.** For each band: item count, median distance, median freight per item, and, at order grain, median purchase-to-door and median transit, using the farthest-seller rule above.

Those definitions live in SQL (`sql/kpi_definitions.sql`), and the dashboard reads the same definitions. A number that exists only inside a notebook will drift from the number on the page.

## Scope

| Decision | Choice | Why |
|---|---|---|
| Dataset | Brazilian E-Commerce Public Dataset by Olist, nine CSVs already in `data/raw/` | Same files as the Kaggle release. Source and license are in `data/README.md`. Non-commercial, with attribution. |
| Tables this question needs | orders, customers, sellers, order items, geolocation, products | Payments, reviews, and category translation do not answer this question. |
| Distance | Mean lat/lng per zip prefix, then haversine in km | The file has many points per prefix. Road distance is not in the data. |
| Delivery headline | Purchase-to-door, median, delivered orders only | What the customer feels. |
| Delivery split | Approval, handling, transit | So we do not blame the map for a seller delay. |
| Multi-seller orders | Farthest seller for delivery time; each item for freight | The clock is on the order. The bill is on the item. |
| Weight | Joined from products, freight per kg | Stops a weight effect from being called a distance effect. |
| Weekly page | The seven items listed above | An executive page, not the whole analysis. |
| Tool for the metrics | SQL | The skill this project is meant to show is joins and KPI definitions. |
| Dashboard | Tableau Public, at Construct | Not in this stage. Power BI is the fallback only if you say so before Construct. |
| Executive summary and business report | Execute | Plan only reserves `reports/`. |

## Out of scope

- A routing or warehouse-location solver. We may show that demand and sellers sit in different states; we will not recommend a new building from a centroid.
- Carrier choice, since the files name no carrier.
- A regression leaderboard. Distance bands, the transit split, and freight per kilogram make the argument; a model is optional later and is not the deliverable.
- Review text, payments, and marketing.
- Converting reais to dollars. The file is in BRL, and a conversion would rest on a rate we invented.
- Tableau Public at this stage.

## What Analyze will check

1. Confirm the row counts in `data/README.md` by reading the nine CSVs; do not trust the README over the files.
2. Distinct `customer_unique_id` against customers against orders; distinct sellers; and the share of orders with more than one seller.
3. `order_status` counts, null delivered timestamps, and timestamps that fall before the purchase.
4. The purchase-date minimum and maximum, which define the window the weekly page covers. Do not assume a date range from memory.
5. Zip prefixes on customers and sellers that are absent from geolocation, after the centroid aggregation.
6. The row count of items before and after the geolocation join, which must not grow.
7. Coordinates that fall outside Brazil. Count them, and do not silently drop them until we see how many there are.
8. Null and non-positive `freight_value`, `price`, and product weight.
9. How often `order_estimated_delivery_date` is null on delivered orders.
10. The distribution of item distance, so that Construct's bands are chosen from the data and then frozen.

## Decisions locked here

- Customer location is the order's customer, counted as a person with `customer_unique_id` and as demand with `order_id`.
- Distance is haversine kilometers between zip-prefix centroids. Missing prefixes are excluded, not imputed.
- Delivery time versus distance uses the farthest seller on the order.
- Freight versus distance stays at item grain and is also shown per kilogram.
- Headline time is purchase-to-door, with transit reported beside it. On-time uses Olist's estimated date and is never the only time metric.
- The weekly page consists of the seven items listed above, with no review score.
- Tableau Public is the dashboard tool, and it starts at Construct.

## Before Analyze

There is nothing to download. The nine CSVs are already in `data/raw/` and stay git-ignored. GitHub is already connected, no new connector is needed, and Tableau Public is not needed until Construct.

Send **A** for Analyze. If you want delivery time tied to the nearest seller instead of the farthest, review score added to the weekly page, or Power BI instead of Tableau Public, say so before sending A; otherwise, those decisions stand.