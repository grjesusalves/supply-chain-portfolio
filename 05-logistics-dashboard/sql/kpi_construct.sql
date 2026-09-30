-- Construct-stage SQL for the Olist logistics weekly page.
-- src/construct_logistics.py loads the CSVs, runs sql/kpi_analyze.sql, then
-- runs this file in the same SQLite connection.
--
-- This file does not recompute the centroid or the haversine. Those
-- expressions are executed in sql/kpi_analyze.sql. They are copied into the
-- comments below so a reviewer can read the definition here. An executable
-- second copy would be a second definition, and this page is not allowed to
-- drift from Analyze.
--
-- Tables this file reads, all built by sql/kpi_analyze.sql:
--   orders, customers, sellers
--   delivered_order   (one row per delivered order)
--   delivered_item    (one row per delivered item)
--   geo_centroid      (one row per zero-padded zip prefix)
--
-- Centroid.
-- Geolocation has many points per zip prefix. The mean latitude and the mean
-- longitude are taken per prefix before any join. Joining the raw points
-- would multiply items, and a freight total on that table would not be freight.
-- Customer and seller prefixes in this extract are not zero-padded. Geolocation
-- prefixes are 5 characters. The join pads with
--   printf('%05d', CAST(prefix AS INTEGER))
-- Padding restores a leading zero. It does not fill a prefix that is still
-- missing. Those items stay in the volume counts and drop out of distance.
-- Out-of-Brazil centroids stay in. They are not a filter.
--
-- Haversine.
-- Kilometers between the customer prefix centroid and the seller prefix
-- centroid. Great-circle on a sphere, not road distance, not a carrier bill.
-- Earth radius 6371 km.
--   2 * 6371 * ASIN(MIN(1, SQRT(
--       SIN(RADIANS(lat1 - lat2) / 2) ^ 2
--     + COS(RADIANS(lat2)) * COS(RADIANS(lat1))
--       * SIN(RADIANS(lng1 - lng2) / 2) ^ 2
--   )))
-- A missing centroid makes the distance NULL. It is not a state average.
--
-- Population for time and freight.
-- order_status = 'delivered'
-- order_delivered_customer_date is present
-- that timestamp is after order_purchase_timestamp
-- delivered_order and delivered_item already apply that filter.
-- This file does not add a second one.
-- Purchase-to-door days:
--   julianday(order_delivered_customer_date) - julianday(order_purchase_timestamp)
-- Transit days:
--   julianday(order_delivered_customer_date) - julianday(order_delivered_carrier_date)
-- A negative transit duration is a timestamp out of order, not a duration.
-- It is excluded from the transit median only. The order stays in the
-- purchase-to-door median, the order count, and the on-time rate.
-- On time is the calendar date, because every estimate in this extract is
-- stored at midnight:
--   date(order_delivered_customer_date) <= date(order_estimated_delivery_date)
-- A timestamp compare is not the KPI.
--
-- Grain, same as the plan.
-- Orders purchased that week: one row per order, every status. Not only
-- delivered orders. The week is the week of order_purchase_timestamp.
-- Median purchase-to-door, median transit, and the on-time rate: order grain,
-- the delivered population. The customer waits once.
-- Total freight, median freight per item, and the cross-state share: item
-- grain, delivered items. freight_value and the seller live on the item.
-- Distance-band order count, median purchase-to-door, and median transit:
-- order grain, using the farthest seller (MAX item distance), and only
-- orders that have a distance. Freight in the band table is the item's own
-- distance, not that maximum. An order can have items in different bands.
-- Customers by state: distinct customer_unique_id, all customers, not only
-- delivered orders. A person in two states is counted in each.
-- Sellers by state: one row of the seller table. This is not a warehouse list.
--
-- Week.
-- The week starts on Monday. SQLite strftime('%w') is 0 on Sunday through
-- 6 on Saturday. Days since Monday are (w + 6) % 7. Subtracting that many
-- days lands on Monday, and a purchase that is already on Monday stays there.
-- This is not an ISO week number, so the week does not split on 1 January.
-- The first and last weeks of the extract are partial. They are not dropped.
-- A week of purchases with no delivered order has a count and a blank door
-- time. A missing delivery is not zero days.
--
-- Frozen bands. Right-open. The last band includes the tail.
--   0-50        distance >= 0    and < 50
--   50-200      distance >= 50   and < 200     (50 km is in this band)
--   200-500     distance >= 200  and < 500
--   500-1000    distance >= 500  and < 1000
--   1000+       distance >= 1000               (includes the extreme tail)
-- order_band and item_band were assigned with these cuts in kpi_analyze.sql.
-- This file groups by those columns. It does not re-cut the kilometers.
-- The cuts are not moved to make a chart smoother.
--
-- Medians use the two-central-row average, the same rule as kpi_analyze.sql.
-- If the count is odd, both central ranks are the same row. If the count is
-- even, the median is the average of the two central rows.


-- Orders purchased that week. Every status. The weekly page's order count.
CREATE TABLE res_week_orders AS
SELECT
  date(
    order_purchase_timestamp,
    '-' || ((CAST(strftime('%w', order_purchase_timestamp) AS INTEGER) + 6) % 7) || ' days'
  ) AS week_start,
  COUNT(*) AS orders_purchased
FROM orders
WHERE order_purchase_timestamp IS NOT NULL
GROUP BY 1;


-- Delivered orders in that purchase week. Denominator for the time metrics.
-- on_time_date is already the calendar comparison. Null estimates would be
-- NULL in that column; Analyze found zero of them on this population.
CREATE TABLE res_week_time AS
SELECT
  date(
    order_purchase_timestamp,
    '-' || ((CAST(strftime('%w', order_purchase_timestamp) AS INTEGER) + 6) % 7) || ' days'
  ) AS week_start,
  COUNT(*) AS delivered_orders,
  SUM(on_time_date) AS on_time_orders,
  SUM(CASE WHEN transit_days IS NOT NULL AND transit_days >= 0 THEN 1 ELSE 0 END) AS transit_orders
FROM delivered_order
GROUP BY 1;


-- Median purchase-to-door on delivered orders purchased that week.
-- The population already requires the door time to be after purchase, so
-- this median does not drop negative values. There are none to drop.
CREATE TABLE res_week_med_p2d AS
WITH base AS (
  SELECT
    date(
      order_purchase_timestamp,
      '-' || ((CAST(strftime('%w', order_purchase_timestamp) AS INTEGER) + 6) % 7) || ' days'
    ) AS week_start,
    purchase_to_door_days AS x
  FROM delivered_order
  WHERE purchase_to_door_days IS NOT NULL
),
ranked AS (
  SELECT
    week_start,
    x,
    ROW_NUMBER() OVER (PARTITION BY week_start ORDER BY x) AS rn,
    COUNT(*) OVER (PARTITION BY week_start) AS n
  FROM base
)
SELECT
  week_start,
  AVG(x) AS median_purchase_to_door_days,
  MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY week_start;


-- Median transit. Negative durations are out of this median only.
CREATE TABLE res_week_med_transit AS
WITH base AS (
  SELECT
    date(
      order_purchase_timestamp,
      '-' || ((CAST(strftime('%w', order_purchase_timestamp) AS INTEGER) + 6) % 7) || ' days'
    ) AS week_start,
    transit_days AS x
  FROM delivered_order
  WHERE transit_days IS NOT NULL
    AND transit_days >= 0
),
ranked AS (
  SELECT
    week_start,
    x,
    ROW_NUMBER() OVER (PARTITION BY week_start ORDER BY x) AS rn,
    COUNT(*) OVER (PARTITION BY week_start) AS n
  FROM base
)
SELECT
  week_start,
  AVG(x) AS median_transit_days,
  MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY week_start;


-- Freight is the delivered item. Cents come from the file's two-decimal text,
-- the same REPLACE rule as Analyze, so the weekly cents sum to the extract
-- total and not to a float. Items with no distance stay in this total.
-- They are not in the band table below.
CREATE TABLE res_week_freight AS
SELECT
  date(
    order_purchase_timestamp,
    '-' || ((CAST(strftime('%w', order_purchase_timestamp) AS INTEGER) + 6) % 7) || ' days'
  ) AS week_start,
  COUNT(*) AS delivered_items,
  SUM(CAST(REPLACE(freight_value, '.', '') AS INTEGER)) AS freight_cents,
  SUM(CASE WHEN cross_state = 1 THEN 1 ELSE 0 END) AS cross_state_items
FROM delivered_item
GROUP BY 1;


-- Median freight per item, delivered items purchased that week, with or
-- without a distance. Zero freight stays in. The plan counted it. It did
-- not drop it.
CREATE TABLE res_week_med_freight AS
WITH base AS (
  SELECT
    date(
      order_purchase_timestamp,
      '-' || ((CAST(strftime('%w', order_purchase_timestamp) AS INTEGER) + 6) % 7) || ' days'
    ) AS week_start,
    CAST(freight_value AS REAL) AS x
  FROM delivered_item
  WHERE freight_value IS NOT NULL
),
ranked AS (
  SELECT
    week_start,
    x,
    ROW_NUMBER() OVER (PARTITION BY week_start ORDER BY x) AS rn,
    COUNT(*) OVER (PARTITION BY week_start) AS n
  FROM base
)
SELECT
  week_start,
  AVG(x) AS median_freight_brl,
  MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY week_start;


-- One row per purchase week. Time, freight, and cross-state are left-joined.
-- A week that has purchases and no delivered order keeps its order count.
-- The metric columns stay NULL. They are not coerced to zero.
CREATE TABLE res_weekly AS
SELECT
  o.week_start,
  date(o.week_start, '+6 days') AS week_end,
  o.orders_purchased,
  t.delivered_orders,
  p.median_purchase_to_door_days,
  tr.median_transit_days,
  t.transit_orders,
  t.on_time_orders,
  CASE
    WHEN t.delivered_orders IS NULL OR t.delivered_orders = 0 THEN NULL
    ELSE t.on_time_orders * 1.0 / t.delivered_orders
  END AS on_time_rate,
  f.freight_cents,
  f.delivered_items,
  mf.median_freight_brl,
  f.cross_state_items,
  CASE
    WHEN f.delivered_items IS NULL OR f.delivered_items = 0 THEN NULL
    ELSE f.cross_state_items * 1.0 / f.delivered_items
  END AS cross_state_share
FROM res_week_orders o
LEFT JOIN res_week_time t ON t.week_start = o.week_start
LEFT JOIN res_week_med_p2d p ON p.week_start = o.week_start
LEFT JOIN res_week_med_transit tr ON tr.week_start = o.week_start
LEFT JOIN res_week_freight f ON f.week_start = o.week_start
LEFT JOIN res_week_med_freight mf ON mf.week_start = o.week_start
ORDER BY o.week_start;


-- Distance-band table for the page.
-- Order count and the two day medians: farthest seller, orders with a distance.
-- Median freight: the item's own band, items with a distance.
-- band_order keeps 1000+ last. Alphabetical order would not.
CREATE TABLE res_distance_band AS
WITH band_dim AS (
  SELECT '0-50' AS band, 1 AS band_order, '0–50 km' AS band_label,
         0 AS lo_km_inclusive, 50 AS hi_km_exclusive
  UNION ALL SELECT '50-200', 2, '50–200 km', 50, 200
  UNION ALL SELECT '200-500', 3, '200–500 km', 200, 500
  UNION ALL SELECT '500-1000', 4, '500–1,000 km', 500, 1000
  UNION ALL SELECT '1000+', 5, '1,000 km or more', 1000, NULL
),
order_n AS (
  SELECT order_band AS band, COUNT(*) AS orders
  FROM delivered_order
  WHERE order_band IS NOT NULL
  GROUP BY order_band
),
p2d AS (
  SELECT band, AVG(x) AS median_purchase_to_door_days, MIN(n) AS n
  FROM (
    SELECT
      order_band AS band,
      purchase_to_door_days AS x,
      ROW_NUMBER() OVER (PARTITION BY order_band ORDER BY purchase_to_door_days) AS rn,
      COUNT(*) OVER (PARTITION BY order_band) AS n
    FROM delivered_order
    WHERE order_band IS NOT NULL
      AND purchase_to_door_days IS NOT NULL
  ) AS ranked
  WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
  GROUP BY band
),
transit AS (
  SELECT band, AVG(x) AS median_transit_days, MIN(n) AS n
  FROM (
    SELECT
      order_band AS band,
      transit_days AS x,
      ROW_NUMBER() OVER (PARTITION BY order_band ORDER BY transit_days) AS rn,
      COUNT(*) OVER (PARTITION BY order_band) AS n
    FROM delivered_order
    WHERE order_band IS NOT NULL
      AND transit_days IS NOT NULL
      AND transit_days >= 0
  ) AS ranked
  WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
  GROUP BY band
),
item_n AS (
  SELECT item_band AS band, COUNT(*) AS items
  FROM delivered_item
  WHERE item_band IS NOT NULL
  GROUP BY item_band
),
freight AS (
  SELECT band, AVG(x) AS median_freight_brl, MIN(n) AS n
  FROM (
    SELECT
      item_band AS band,
      CAST(freight_value AS REAL) AS x,
      ROW_NUMBER() OVER (PARTITION BY item_band ORDER BY CAST(freight_value AS REAL)) AS rn,
      COUNT(*) OVER (PARTITION BY item_band) AS n
    FROM delivered_item
    WHERE item_band IS NOT NULL
      AND freight_value IS NOT NULL
  ) AS ranked
  WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
  GROUP BY band
)
SELECT
  d.band_order,
  d.band,
  d.band_label,
  d.lo_km_inclusive,
  d.hi_km_exclusive,
  o.orders,
  p.median_purchase_to_door_days,
  t.median_transit_days,
  i.items,
  f.median_freight_brl
FROM band_dim d
LEFT JOIN order_n o ON o.band = d.band
LEFT JOIN p2d p ON p.band = d.band
LEFT JOIN transit t ON t.band = d.band
LEFT JOIN item_n i ON i.band = d.band
LEFT JOIN freight f ON f.band = d.band
ORDER BY d.band_order;


-- Customers by state next to sellers by state.
-- People are customer_unique_id on the full customer table. Demand is not
-- this count: customer_id is one row per order. Sellers are the seller table,
-- not sellers who happen to have a delivered item.
-- Do not join customers back to orders on customer_unique_id. A person with
-- several orders would be counted once per order.
-- people_share uses distinct people in the whole file as the denominator,
-- not the sum of the state rows. Thirty-nine people sit in more than one
-- state, so the state rows sum to more than that denominator.
CREATE TABLE res_state_coverage AS
WITH states AS (
  SELECT customer_state AS state FROM customers
  UNION
  SELECT seller_state AS state FROM sellers
),
people AS (
  SELECT customer_state AS state, COUNT(DISTINCT customer_unique_id) AS customer_people
  FROM customers
  GROUP BY customer_state
),
sells AS (
  SELECT seller_state AS state, COUNT(*) AS sellers
  FROM sellers
  GROUP BY seller_state
)
SELECT
  st.state,
  COALESCE(p.customer_people, 0) AS customer_people,
  COALESCE(s.sellers, 0) AS sellers,
  COALESCE(p.customer_people, 0) * 1.0
    / (SELECT COUNT(DISTINCT customer_unique_id) FROM customers) AS people_share,
  COALESCE(s.sellers, 0) * 1.0
    / (SELECT COUNT(*) FROM sellers) AS seller_share
FROM states st
LEFT JOIN people p ON p.state = st.state
LEFT JOIN sells s ON s.state = st.state
ORDER BY customer_people DESC, st.state;
