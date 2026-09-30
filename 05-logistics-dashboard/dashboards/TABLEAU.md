# Tableau Public — weekly logistics review

The page a reviewer can open without Tableau is [`logistics_weekly.html`](logistics_weekly.html). That HTML file is the stand-in, so the portfolio is readable before anyone publishes to Tableau Public. This workbook was **not** published. There is no Tableau Public URL. `tableau` and `tabcmd` are not on this machine, and this file does not invent a link.

The extracts are three CSVs. Connect each one as its own data source. Do not join them. A join would mix a week, a distance band, and a state on one row, and the grains below are the point.

From Tableau Public (public.tableau.com): **Data → New Data Source → Text file**. Point at the file. Repeat for the other two. Set `week_start` to a date. Leave the medians as numbers, not as strings.

## `data/processed/weekly_scorecard.csv`

One row per week that has at least one purchase. The week starts on Monday (`week_start`) and runs through Sunday (`week_end`). 101 rows. Weeks with no purchase are absent, not stored as zero. A week with purchases and no delivered order keeps the order count and leaves the time, freight, and cross-state fields blank. A blank is not zero days.

| Column | Meaning |
|---|---|
| `week_start` | Monday of the purchase week. Continuous date axis. |
| `week_end` | Sunday of that week. The first and last weeks of the extract are partial. |
| `orders_purchased` | Every order purchased that week, every status. Not only delivered orders. Sums to 99,441. |
| `delivered_orders` | Delivered orders purchased that week. Denominator for the time metrics. Sums to 96,470. |
| `median_purchase_to_door_days` | Median purchase-to-door days on those delivered orders. Already a median. |
| `median_transit_days` | Median carrier-to-door days. Negative durations are already excluded. |
| `transit_orders` | Orders in that transit median. |
| `on_time_orders` | Delivered on or before the estimate’s calendar date. |
| `on_time_rate` | `on_time_orders / delivered_orders` for that week. |
| `freight_total_brl` | Freight on delivered items purchased that week, in reais. |
| `delivered_items` | Delivered items purchased that week. Sums to 110,189. |
| `median_freight_brl` | Median freight per delivered item that week, in reais. Already a median. |
| `cross_state_items` | Delivered items whose customer state differs from the seller state. |
| `cross_state_share` | `cross_state_items / delivered_items` for that week. |

## `data/processed/distance_bands.csv`

Five rows. The cuts are frozen: 0–50, 50–200, 200–500, 500–1,000, and 1,000 kilometers or more. Right-open, so 50 km is in 50–200. The last band includes the tail. Do not add a cut and do not drop 1,000 km or more.

| Column | Meaning |
|---|---|
| `band_order` | Sort key, 1 through 5. Alphabetical order puts 1,000 km first. Do not use it. |
| `band` | Code: `0-50`, `50-200`, `200-500`, `500-1000`, `1000+`. |
| `band_label` | Label for the table: `0–50 km` through `1,000 km or more`. |
| `lo_km_inclusive` | Low end, kilometers, included. |
| `hi_km_exclusive` | High end, kilometers, excluded. Blank on the last band. |
| `orders` | Delivered orders whose farthest seller falls in the band. Sums to 95,992. |
| `median_purchase_to_door_days` | Median purchase-to-door days on those orders. |
| `median_transit_days` | Median transit days on those orders, negatives excluded. |
| `items` | Delivered items whose own distance falls in the band. Sums to 109,651. |
| `median_freight_brl` | Median freight per item on those items, in reais. Not the order’s farthest seller. |

## `data/processed/state_coverage.csv`

27 rows, one per state that has a customer or a seller. People are `customer_unique_id` on the full customer table, not delivered orders only. Sellers are the seller table, 3,095 rows.

| Column | Meaning |
|---|---|
| `state` | Brazilian state code. |
| `customer_people` | Distinct people with a customer row in that state. |
| `sellers` | Sellers whose seller row is in that state. |
| `people_share` | `customer_people / 96,096`. The denominator is distinct people in the file, not the sum of this column. |
| `seller_share` | `sellers / 3,095`. |

The state rows of `customer_people` sum to 96,136, because 39 people appear in more than one state. A Tableau “percent of total” on `customer_people` uses 96,136 and is not the share on this page. Use `people_share` and `seller_share`.

## The seven views, and nothing else

1. **Orders purchased that week.** Line. Columns: `week_start`, `orders_purchased`. Do not filter to delivered orders. If Tableau draws a line across a missing Monday, show the gap. Do not fill it with zero.
2. **Median purchase-to-door and median transit.** One line chart, both measures in days, one axis. Columns: `week_start`, `median_purchase_to_door_days`, `median_transit_days`. Do not average the weekly medians. The extract medians are 10.2 days and 7.1 days, computed on the orders, not on the weeks.
3. **On-time rate.** Line of `on_time_rate` by `week_start`, formatted as a percent. A total for the extract is `SUM(on_time_orders) / SUM(delivered_orders)` = 89,936 / 96,470. It is not the average of the weekly rates.
4. **Freight.** Two panes, not one dual axis. `SUM(freight_total_brl)` by week, in reais, and `median_freight_brl` by week. The extract total is R$2,202,835.80. The extract median is R$16.26. Do not average the weekly medians and call it R$16.26.
5. **Cross-state share.** Line of `cross_state_share` by `week_start`. The extract share is `SUM(cross_state_items) / SUM(delivered_items)` = 70,328 / 110,189. Not the average of the weekly shares.
6. **Distance-band table.** `band_label`, `orders`, `median_purchase_to_door_days`, `median_transit_days`, `median_freight_brl`. Sort by `band_order`. This is a table, not a new set of cuts.
7. **Customers by state next to sellers by state.** Bar chart, `people_share` beside `seller_share`, by `state`. Horizontal bars are easier to read. Do not add orders as a third bar.

## What not to add

- No review score. It is not on this page.
- No freight per kilogram, no seller-handling series, no map, no carrier, no warehouse.
- No conversion from reais to dollars.
- No second distance definition. The bands are frozen.
- No row for a week with no purchases, filled in as zero days or zero freight.
- No claim that this file was published to Tableau Public.
