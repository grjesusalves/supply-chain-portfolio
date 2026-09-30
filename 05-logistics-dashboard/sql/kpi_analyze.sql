-- Analyze-stage SQL for the Olist logistics dashboard.
-- src/analyze_logistics.py loads the CSV tables, then executes this file.
-- Tables it expects: orders, customers, sellers, items, products, geo.
-- All six are loaded as TEXT so zip prefixes and money keep their file spelling.
-- Medians use the two-central-row average (the same rule as an even-count median).
--
-- Why a centroid, before any join:
-- geolocation has many points per zip prefix. Joining those points to an item
-- would multiply the item. Freight and distance would be counted once per point.
-- The mean latitude and mean longitude are taken per prefix first. One prefix,
-- one row, no fanout. The mean is what Plan locked. A median coordinate would
-- resist a bad point, and this file does not switch to it.
--
-- Why the prefix is zero-padded:
-- Customer and seller prefixes in this extract were stored without leading
-- zeros (length 4 or 5). Geolocation prefixes are 5 characters. Padding with
-- printf('%05d', ...) restores the prefix. It does not invent a location for
-- a prefix that is still absent after the pad. Those stay missing.
--
-- Why this grain:
-- freight_value and seller_id sit on the order item, so freight and item
-- distance stay on (order_id, order_item_id).
-- The customer waits once, so purchase-to-door stays on the order.
-- A multi-seller order uses the MAX item distance (farthest seller).
-- Freight does not use that max.
--
-- Why delivered-only for time and freight:
-- Any other status is not a completed delivery. A delivered timestamp that is
-- missing, or not after the purchase timestamp, is not a door time.
-- Those orders stay in the status counts and out of the medians.
--
-- Distance is haversine kilometers, earth radius 6371. Great-circle, not road.
-- Bands below are a proposal from the distance distribution. Construct freezes
-- them. Cuts are right-open: 50 km belongs to 50-200, not to 0-50.
-- 1000+ includes the extreme tail. Nothing in that tail is dropped here.

-- One degree of latitude is about 111 km. If this is not, the haversine is wrong
-- and the script stops.
CREATE TABLE res_haversine_unit AS
SELECT 2.0 * 6371.0 * ASIN(MIN(1.0, SQRT(
         POWER(SIN(RADIANS(-22.0 - -23.0) / 2.0), 2)
         + COS(RADIANS(-23.0)) * COS(RADIANS(-22.0))
           * POWER(SIN(RADIANS(-46.0 - -46.0) / 2.0), 2)
       ))) AS km_one_degree_lat;

-- Loose Brazil box from Plan: latitude -34 to 6, longitude -74 to -32.
-- A centroid on the boundary is inside. Null coordinates are not "outside";
-- they are counted separately. Wide prefix: the raw points span more than
-- 1 degree of latitude or longitude (about 111 km of latitude). That flag
-- is a warning that the mean was pulled. It is not a drop rule.
CREATE TABLE geo_centroid AS
SELECT
  printf('%05d', CAST(geolocation_zip_code_prefix AS INTEGER)) AS zip_prefix,
  AVG(CAST(geolocation_lat AS REAL)) AS lat,
  AVG(CAST(geolocation_lng AS REAL)) AS lng,
  COUNT(*) AS n_points,
  SUM(CASE
        WHEN geolocation_lat IS NULL OR geolocation_lng IS NULL THEN 1
        ELSE 0
      END) AS n_null_coord,
  SUM(CASE
        WHEN geolocation_lat IS NOT NULL
         AND geolocation_lng IS NOT NULL
         AND (CAST(geolocation_lat AS REAL) < -34
              OR CAST(geolocation_lat AS REAL) > 6
              OR CAST(geolocation_lng AS REAL) < -74
              OR CAST(geolocation_lng AS REAL) > -32)
        THEN 1 ELSE 0
      END) AS n_points_outside,
  MIN(CAST(geolocation_lat AS REAL)) AS lat_min,
  MAX(CAST(geolocation_lat AS REAL)) AS lat_max,
  MIN(CAST(geolocation_lng AS REAL)) AS lng_min,
  MAX(CAST(geolocation_lng AS REAL)) AS lng_max
FROM geo
GROUP BY printf('%05d', CAST(geolocation_zip_code_prefix AS INTEGER));

CREATE UNIQUE INDEX idx_centroid_zip ON geo_centroid(zip_prefix);

ALTER TABLE geo_centroid ADD COLUMN outside_brazil INTEGER;
ALTER TABLE geo_centroid ADD COLUMN wide_prefix INTEGER;

UPDATE geo_centroid
SET outside_brazil = CASE
      WHEN lat IS NULL OR lng IS NULL THEN 0
      WHEN lat < -34 OR lat > 6 OR lng < -74 OR lng > -32 THEN 1
      ELSE 0
    END,
    wide_prefix = CASE
      WHEN lat_min IS NULL OR lng_min IS NULL THEN 0
      WHEN (lat_max - lat_min) > 1 OR (lng_max - lng_min) > 1 THEN 1
      ELSE 0
    END;

CREATE INDEX idx_orders_id ON orders(order_id);
CREATE INDEX idx_customers_id ON customers(customer_id);
CREATE INDEX idx_sellers_id ON sellers(seller_id);
CREATE INDEX idx_items_order ON items(order_id);
CREATE INDEX idx_items_seller ON items(seller_id);
CREATE INDEX idx_items_product ON items(product_id);
CREATE INDEX idx_products_id ON products(product_id);

-- Left joins on purpose. An inner join would hide a broken key by shrinking
-- the item table. The fanout check below requires the row count not to grow
-- and reports it if a key is missing. Geolocation is already one row per prefix.
CREATE TABLE item_enriched AS
SELECT
  base.*,
  CASE
    WHEN base.in_time_population = 0 OR base.distance_km IS NULL THEN NULL
    WHEN base.distance_km < 50 THEN '0-50'
    WHEN base.distance_km < 200 THEN '50-200'
    WHEN base.distance_km < 500 THEN '200-500'
    WHEN base.distance_km < 1000 THEN '500-1000'
    ELSE '1000+'
  END AS item_band
FROM (
  SELECT
    i.order_id,
    CAST(i.order_item_id AS INTEGER) AS order_item_id,
    i.product_id,
    i.seller_id,
    i.price,
    i.freight_value,
    p.product_weight_g,
    o.order_status,
    o.customer_id,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    c.customer_unique_id,
    printf('%05d', CAST(c.customer_zip_code_prefix AS INTEGER)) AS customer_zip_prefix,
    c.customer_state,
    printf('%05d', CAST(s.seller_zip_code_prefix AS INTEGER)) AS seller_zip_prefix,
    s.seller_state,
    gc.lat AS customer_lat,
    gc.lng AS customer_lng,
    gs.lat AS seller_lat,
    gs.lng AS seller_lng,
    CASE
      WHEN gc.lat IS NULL OR gc.lng IS NULL OR gs.lat IS NULL OR gs.lng IS NULL THEN NULL
      ELSE 2.0 * 6371.0 * ASIN(MIN(1.0, SQRT(
        POWER(SIN(RADIANS(gc.lat - gs.lat) / 2.0), 2)
        + COS(RADIANS(gs.lat)) * COS(RADIANS(gc.lat))
          * POWER(SIN(RADIANS(gc.lng - gs.lng) / 2.0), 2)
      )))
    END AS distance_km,
    CASE WHEN gc.outside_brazil = 1 THEN 1 ELSE 0 END AS customer_outside,
    CASE WHEN gs.outside_brazil = 1 THEN 1 ELSE 0 END AS seller_outside,
    CASE WHEN gc.wide_prefix = 1 THEN 1 ELSE 0 END AS customer_wide,
    CASE WHEN gs.wide_prefix = 1 THEN 1 ELSE 0 END AS seller_wide,
    CASE
      WHEN o.order_status = 'delivered'
       AND o.order_delivered_customer_date IS NOT NULL
       AND julianday(o.order_delivered_customer_date) > julianday(o.order_purchase_timestamp)
      THEN 1 ELSE 0
    END AS in_time_population,
    CASE
      WHEN c.customer_state IS NULL OR s.seller_state IS NULL THEN NULL
      WHEN c.customer_state <> s.seller_state THEN 1
      ELSE 0
    END AS cross_state,
    CASE
      WHEN p.product_weight_g IS NULL THEN NULL
      WHEN CAST(p.product_weight_g AS REAL) <= 0 THEN NULL
      ELSE CAST(i.freight_value AS REAL) / (CAST(p.product_weight_g AS REAL) / 1000.0)
    END AS freight_per_kg
  FROM items i
  LEFT JOIN orders o ON o.order_id = i.order_id
  LEFT JOIN customers c ON c.customer_id = o.customer_id
  LEFT JOIN sellers s ON s.seller_id = i.seller_id
  LEFT JOIN products p ON p.product_id = i.product_id
  LEFT JOIN geo_centroid gc
    ON gc.zip_prefix = printf('%05d', CAST(c.customer_zip_code_prefix AS INTEGER))
  LEFT JOIN geo_centroid gs
    ON gs.zip_prefix = printf('%05d', CAST(s.seller_zip_code_prefix AS INTEGER))
) base;

-- Order grain for delivery time. MAX item distance is the farthest seller.
-- MIN is kept only so Analyze can say how many orders would change band.
-- Freight is not on this table.
CREATE TABLE delivered_order AS
SELECT
  o.order_id,
  c.customer_unique_id,
  c.customer_state,
  printf('%05d', CAST(c.customer_zip_code_prefix AS INTEGER)) AS customer_zip_prefix,
  o.order_purchase_timestamp,
  o.order_approved_at,
  o.order_delivered_carrier_date,
  o.order_delivered_customer_date,
  o.order_estimated_delivery_date,
  julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)
    AS purchase_to_door_days,
  CASE
    WHEN o.order_approved_at IS NOT NULL
    THEN julianday(o.order_approved_at) - julianday(o.order_purchase_timestamp)
  END AS approval_days,
  CASE
    WHEN o.order_approved_at IS NOT NULL AND o.order_delivered_carrier_date IS NOT NULL
    THEN julianday(o.order_delivered_carrier_date) - julianday(o.order_approved_at)
  END AS handling_days,
  CASE
    WHEN o.order_delivered_carrier_date IS NOT NULL
    THEN julianday(o.order_delivered_customer_date) - julianday(o.order_delivered_carrier_date)
  END AS transit_days,
  -- On time is the calendar date. Every estimate in this file is stored at
  -- 00:00:00, so a timestamp compare would call a delivery later on the
  -- promised day late. on_time_timestamp is kept only as that contrast.
  CASE
    WHEN o.order_estimated_delivery_date IS NULL THEN NULL
    WHEN date(o.order_delivered_customer_date) <= date(o.order_estimated_delivery_date) THEN 1
    ELSE 0
  END AS on_time_date,
  CASE
    WHEN o.order_estimated_delivery_date IS NULL THEN NULL
    WHEN julianday(o.order_delivered_customer_date) <= julianday(o.order_estimated_delivery_date) THEN 1
    ELSE 0
  END AS on_time_timestamp,
  agg.n_items,
  agg.n_sellers,
  agg.n_with_distance,
  agg.max_distance_km,
  agg.min_distance_km,
  CASE
    WHEN agg.max_distance_km IS NULL THEN NULL
    WHEN agg.max_distance_km < 50 THEN '0-50'
    WHEN agg.max_distance_km < 200 THEN '50-200'
    WHEN agg.max_distance_km < 500 THEN '200-500'
    WHEN agg.max_distance_km < 1000 THEN '500-1000'
    ELSE '1000+'
  END AS order_band
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
LEFT JOIN (
  SELECT
    order_id,
    COUNT(*) AS n_items,
    COUNT(DISTINCT seller_id) AS n_sellers,
    COUNT(distance_km) AS n_with_distance,
    MAX(distance_km) AS max_distance_km,
    MIN(distance_km) AS min_distance_km
  FROM item_enriched
  GROUP BY order_id
) agg ON agg.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
  AND julianday(o.order_delivered_customer_date) > julianday(o.order_purchase_timestamp);

CREATE VIEW delivered_item AS
SELECT * FROM item_enriched WHERE in_time_population = 1;

-- Counts that prove the join did not multiply items, and what would have
-- happened if the raw geolocation points had been joined instead.
CREATE TABLE res_fanout AS
SELECT
  (SELECT COUNT(*) FROM items) AS items_before,
  (SELECT COUNT(*) FROM item_enriched) AS items_after,
  (SELECT COUNT(*) FROM item_enriched WHERE order_id IS NULL) AS items_missing_order,
  (SELECT COUNT(*) FROM item_enriched WHERE customer_id IS NULL) AS items_missing_customer,
  (SELECT COUNT(*) FROM item_enriched WHERE seller_id IS NULL) AS items_missing_seller,
  (SELECT COUNT(*) FROM item_enriched WHERE product_id IS NOT NULL AND product_weight_g IS NULL AND product_id NOT IN (SELECT product_id FROM products)) AS items_missing_product,
  (SELECT COUNT(*) FROM geo_centroid) AS centroid_rows,
  (SELECT COUNT(DISTINCT zip_prefix) FROM geo_centroid) AS centroid_prefixes,
  (SELECT MAX(n_points) FROM geo_centroid) AS max_points_one_prefix,
  (SELECT SUM(gc.n_points)
     FROM item_enriched i
     JOIN geo_centroid gc ON gc.zip_prefix = i.customer_zip_prefix) AS rows_if_customer_geo_not_collapsed,
  (SELECT SUM(gs.n_points)
     FROM item_enriched i
     JOIN geo_centroid gs ON gs.zip_prefix = i.seller_zip_prefix) AS rows_if_seller_geo_not_collapsed;

CREATE TABLE res_order_status AS
SELECT order_status, COUNT(*) AS n
FROM orders
GROUP BY order_status
ORDER BY n DESC;

CREATE TABLE res_door_by_status AS
SELECT
  order_status,
  SUM(CASE WHEN order_delivered_customer_date IS NULL THEN 1 ELSE 0 END) AS null_door,
  SUM(CASE WHEN order_delivered_customer_date IS NOT NULL THEN 1 ELSE 0 END) AS has_door,
  COUNT(*) AS n
FROM orders
GROUP BY order_status
ORDER BY n DESC;

CREATE TABLE res_orders_without_items AS
SELECT o.order_status, COUNT(*) AS n
FROM orders o
LEFT JOIN (SELECT DISTINCT order_id FROM items) i ON i.order_id = o.order_id
WHERE i.order_id IS NULL
GROUP BY o.order_status
ORDER BY n DESC;

CREATE TABLE res_dates AS
SELECT
  MIN(order_purchase_timestamp) AS min_purchase_all,
  MAX(order_purchase_timestamp) AS max_purchase_all,
  (SELECT MIN(order_purchase_timestamp) FROM delivered_order) AS min_purchase_population,
  (SELECT MAX(order_purchase_timestamp) FROM delivered_order) AS max_purchase_population,
  SUM(CASE WHEN order_purchase_timestamp IS NULL THEN 1 ELSE 0 END) AS null_purchase,
  SUM(CASE
        WHEN order_estimated_delivery_date IS NULL THEN 1 ELSE 0
      END) AS null_estimate_all,
  SUM(CASE
        WHEN order_estimated_delivery_date IS NOT NULL
         AND order_estimated_delivery_date NOT LIKE '%00:00:00' THEN 1 ELSE 0
      END) AS estimate_not_midnight
FROM orders;

CREATE TABLE res_zip_match AS
SELECT
  (SELECT COUNT(*) FROM customers) AS customers,
  (SELECT COUNT(*)
     FROM customers c
     LEFT JOIN geo_centroid g
       ON g.zip_prefix = printf('%05d', CAST(c.customer_zip_code_prefix AS INTEGER))
    WHERE g.zip_prefix IS NULL) AS customers_missing_padded,
  (SELECT COUNT(*)
     FROM customers c
     LEFT JOIN geo_centroid g ON g.zip_prefix = c.customer_zip_code_prefix
    WHERE g.zip_prefix IS NULL) AS customers_missing_unpadded,
  (SELECT COUNT(DISTINCT printf('%05d', CAST(c.customer_zip_code_prefix AS INTEGER)))
     FROM customers c
     LEFT JOIN geo_centroid g
       ON g.zip_prefix = printf('%05d', CAST(c.customer_zip_code_prefix AS INTEGER))
    WHERE g.zip_prefix IS NULL) AS distinct_customer_prefix_missing_padded,
  (SELECT COUNT(DISTINCT printf('%05d', CAST(customer_zip_code_prefix AS INTEGER))) FROM customers) AS distinct_customer_prefixes,
  (SELECT COUNT(*) FROM sellers) AS sellers,
  (SELECT COUNT(*)
     FROM sellers s
     LEFT JOIN geo_centroid g
       ON g.zip_prefix = printf('%05d', CAST(s.seller_zip_code_prefix AS INTEGER))
    WHERE g.zip_prefix IS NULL) AS sellers_missing_padded,
  (SELECT COUNT(*)
     FROM sellers s
     LEFT JOIN geo_centroid g ON g.zip_prefix = s.seller_zip_code_prefix
    WHERE g.zip_prefix IS NULL) AS sellers_missing_unpadded,
  (SELECT COUNT(DISTINCT printf('%05d', CAST(s.seller_zip_code_prefix AS INTEGER)))
     FROM sellers s
     LEFT JOIN geo_centroid g
       ON g.zip_prefix = printf('%05d', CAST(s.seller_zip_code_prefix AS INTEGER))
    WHERE g.zip_prefix IS NULL) AS distinct_seller_prefix_missing_padded,
  (SELECT COUNT(DISTINCT printf('%05d', CAST(seller_zip_code_prefix AS INTEGER))) FROM sellers) AS distinct_seller_prefixes;

CREATE TABLE res_brazil AS
SELECT
  (SELECT COUNT(*) FROM geo) AS geo_rows,
  (SELECT SUM(CASE
        WHEN geolocation_lat IS NULL OR geolocation_lng IS NULL THEN 1 ELSE 0
      END) FROM geo) AS raw_null_coord,
  (SELECT SUM(CASE
        WHEN CAST(geolocation_lat AS REAL) < -34
          OR CAST(geolocation_lat AS REAL) > 6
          OR CAST(geolocation_lng AS REAL) < -74
          OR CAST(geolocation_lng AS REAL) > -32
        THEN 1 ELSE 0
      END) FROM geo) AS raw_points_outside,
  (SELECT COUNT(*) FROM geo_centroid) AS centroids,
  (SELECT SUM(outside_brazil) FROM geo_centroid) AS centroids_outside,
  (SELECT SUM(CASE WHEN lat IS NULL OR lng IS NULL THEN 1 ELSE 0 END) FROM geo_centroid) AS centroids_null,
  (SELECT SUM(CASE WHEN n_points_outside > 0 THEN 1 ELSE 0 END) FROM geo_centroid) AS prefixes_with_outside_point,
  (SELECT SUM(CASE WHEN n_points_outside > 0 AND outside_brazil = 0 THEN 1 ELSE 0 END) FROM geo_centroid) AS outside_point_centroid_inside,
  (SELECT SUM(wide_prefix) FROM geo_centroid) AS wide_prefixes,
  (SELECT SUM(CASE WHEN wide_prefix = 1 THEN n_points ELSE 0 END) FROM geo_centroid) AS points_in_wide_prefixes,
  (SELECT MIN(lat) FROM geo_centroid) AS min_lat,
  (SELECT MAX(lat) FROM geo_centroid) AS max_lat,
  (SELECT MIN(lng) FROM geo_centroid) AS min_lng,
  (SELECT MAX(lng) FROM geo_centroid) AS max_lng;

CREATE TABLE res_centroids_outside AS
SELECT zip_prefix, lat, lng, n_points, n_points_outside, lat_min, lat_max, lng_min, lng_max
FROM geo_centroid
WHERE outside_brazil = 1
ORDER BY lat;

CREATE TABLE res_grain AS
SELECT
  (SELECT COUNT(*) FROM orders) AS orders,
  (SELECT COUNT(DISTINCT order_id) FROM orders) AS distinct_order_id,
  (SELECT COUNT(*) FROM customers) AS customer_rows,
  (SELECT COUNT(DISTINCT customer_id) FROM customers) AS distinct_customer_id,
  (SELECT COUNT(DISTINCT customer_unique_id) FROM customers) AS distinct_people,
  (SELECT COUNT(*) FROM (
      SELECT customer_unique_id FROM customers
      GROUP BY customer_unique_id HAVING COUNT(*) > 1
  )) AS people_with_more_than_one_order,
  (SELECT MAX(n) FROM (
      SELECT COUNT(*) AS n FROM customers GROUP BY customer_unique_id
  )) AS max_orders_per_person,
  (SELECT COUNT(*) FROM (
      SELECT customer_unique_id FROM customers
      GROUP BY customer_unique_id HAVING COUNT(DISTINCT customer_state) > 1
  )) AS people_with_more_than_one_state,
  (SELECT COUNT(*) FROM (
      SELECT customer_unique_id FROM customers
      GROUP BY customer_unique_id HAVING COUNT(DISTINCT customer_state) = 2
  )) AS people_with_two_states,
  (SELECT COUNT(*) FROM (
      SELECT customer_unique_id FROM customers
      GROUP BY customer_unique_id HAVING COUNT(DISTINCT customer_state) >= 3
  )) AS people_with_three_or_more_states,
  (SELECT MAX(n) FROM (
      SELECT COUNT(DISTINCT customer_state) AS n FROM customers GROUP BY customer_unique_id
  )) AS max_states_per_person,
  (SELECT COUNT(*) FROM sellers) AS sellers,
  (SELECT COUNT(DISTINCT seller_id) FROM sellers) AS distinct_seller_id,
  (SELECT COUNT(DISTINCT seller_state) FROM sellers) AS seller_states,
  (SELECT COUNT(DISTINCT customer_state) FROM customers) AS customer_states,
  (SELECT COUNT(*) FROM items) AS items,
  (SELECT COUNT(*) FROM (
      SELECT order_id, order_item_id FROM items
      GROUP BY order_id, order_item_id HAVING COUNT(*) > 1
  )) AS duplicate_order_item_pairs,
  (SELECT COUNT(DISTINCT order_id) FROM items) AS orders_with_items,
  (SELECT COUNT(*) FROM (
      SELECT order_id FROM items
      GROUP BY order_id HAVING COUNT(DISTINCT seller_id) > 1
  )) AS multi_seller_orders,
  (SELECT COUNT(*) FROM orders o
     WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.order_id = o.order_id)) AS orders_without_items,
  (SELECT COUNT(*) FROM items i
     WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.order_id = i.order_id)) AS items_without_order,
  (SELECT COUNT(*) FROM sellers s
     WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.seller_id = s.seller_id)) AS sellers_not_in_items,
  (SELECT COUNT(*) FROM (
      SELECT seller_id FROM items
      WHERE NOT EXISTS (SELECT 1 FROM sellers s WHERE s.seller_id = items.seller_id)
  )) AS item_rows_seller_not_in_table;

CREATE TABLE res_population AS
SELECT
  (SELECT COUNT(*) FROM delivered_order) AS delivered_orders,
  (SELECT COUNT(*) FROM orders
    WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL) AS delivered_null_door,
  (SELECT COUNT(*) FROM orders
    WHERE order_status <> 'delivered' AND order_delivered_customer_date IS NOT NULL) AS non_delivered_with_door,
  (SELECT COUNT(*) FROM orders
    WHERE order_delivered_customer_date IS NOT NULL
      AND julianday(order_delivered_customer_date) <= julianday(order_purchase_timestamp)) AS door_on_or_before_purchase,
  (SELECT COUNT(*) FROM orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
      AND julianday(order_delivered_customer_date) <= julianday(order_purchase_timestamp)) AS delivered_door_on_or_before_purchase,
  (SELECT COUNT(*) FROM delivered_order WHERE order_estimated_delivery_date IS NULL) AS population_null_estimate,
  (SELECT COUNT(*) FROM delivered_item) AS delivered_items,
  (SELECT COUNT(*) FROM delivered_item WHERE distance_km IS NOT NULL) AS delivered_items_with_distance,
  (SELECT COUNT(*) FROM delivered_item WHERE distance_km IS NULL) AS delivered_items_missing_distance,
  (SELECT COUNT(*) FROM delivered_item WHERE customer_lat IS NULL) AS delivered_items_missing_customer_centroid,
  (SELECT COUNT(*) FROM delivered_item WHERE seller_lat IS NULL) AS delivered_items_missing_seller_centroid,
  (SELECT COUNT(*) FROM delivered_item WHERE customer_lat IS NULL AND seller_lat IS NULL) AS delivered_items_missing_both,
  (SELECT COUNT(DISTINCT customer_zip_prefix) FROM delivered_item WHERE customer_lat IS NULL) AS distinct_missing_customer_prefix_on_delivered_items,
  (SELECT COUNT(DISTINCT seller_zip_prefix) FROM delivered_item WHERE seller_lat IS NULL) AS distinct_missing_seller_prefix_on_delivered_items,
  (SELECT COUNT(*) FROM delivered_order WHERE max_distance_km IS NOT NULL) AS delivered_orders_with_distance,
  (SELECT COUNT(*) FROM delivered_order WHERE max_distance_km IS NULL) AS delivered_orders_missing_distance,
  (SELECT COUNT(*) FROM delivered_order
    WHERE n_with_distance > 0 AND n_with_distance < n_items) AS delivered_orders_partial_distance,
  (SELECT COUNT(*) FROM delivered_order WHERE n_sellers > 1) AS delivered_multi_seller,
  (SELECT COUNT(*) FROM delivered_order WHERE n_items IS NULL OR n_items = 0) AS delivered_orders_without_items,
  (SELECT SUM(CASE WHEN customer_outside = 1 OR seller_outside = 1 THEN 1 ELSE 0 END) FROM delivered_item) AS delivered_items_outside_centroid,
  (SELECT SUM(CASE WHEN customer_wide = 1 OR seller_wide = 1 THEN 1 ELSE 0 END) FROM delivered_item) AS delivered_items_wide_prefix,
  (SELECT COUNT(DISTINCT seller_id) FROM delivered_item) AS sellers_with_delivered_item,
  (SELECT COUNT(*) FROM orders
    WHERE order_purchase_timestamp > (SELECT MAX(order_purchase_timestamp) FROM delivered_order)) AS orders_after_last_delivered_purchase;

CREATE TABLE res_distance_tail AS
SELECT
  SUM(CASE WHEN distance_km >= 2000 THEN 1 ELSE 0 END) AS ge_2000,
  SUM(CASE WHEN distance_km >= 2500 THEN 1 ELSE 0 END) AS ge_2500,
  SUM(CASE WHEN distance_km >= 3000 THEN 1 ELSE 0 END) AS ge_3000,
  SUM(CASE WHEN distance_km >= 3500 THEN 1 ELSE 0 END) AS ge_3500,
  SUM(CASE WHEN distance_km >= 4000 THEN 1 ELSE 0 END) AS ge_4000,
  SUM(CASE WHEN distance_km >= 5000 THEN 1 ELSE 0 END) AS ge_5000,
  SUM(CASE WHEN distance_km >= 6000 THEN 1 ELSE 0 END) AS ge_6000,
  MIN(distance_km) AS min_km,
  MAX(distance_km) AS max_km,
  AVG(distance_km) AS mean_km,
  SUM(CASE WHEN distance_km = 0 THEN 1 ELSE 0 END) AS exact_zero,
  SUM(CASE WHEN distance_km < 1 THEN 1 ELSE 0 END) AS under_1km,
  SUM(CASE WHEN distance_km < 10 THEN 1 ELSE 0 END) AS under_10km
FROM delivered_item
WHERE distance_km IS NOT NULL;

CREATE TABLE res_legs AS
SELECT
  COUNT(*) AS n_orders,
  SUM(CASE WHEN approval_days IS NULL THEN 1 ELSE 0 END) AS approval_null,
  SUM(CASE WHEN approval_days < 0 THEN 1 ELSE 0 END) AS approval_neg,
  SUM(CASE WHEN handling_days IS NULL THEN 1 ELSE 0 END) AS handling_null,
  SUM(CASE WHEN handling_days < 0 THEN 1 ELSE 0 END) AS handling_neg,
  SUM(CASE WHEN transit_days IS NULL THEN 1 ELSE 0 END) AS transit_null,
  SUM(CASE WHEN transit_days < 0 THEN 1 ELSE 0 END) AS transit_neg,
  MIN(handling_days) AS min_handling_including_neg,
  MIN(transit_days) AS min_transit_including_neg,
  AVG(purchase_to_door_days) AS mean_p2d,
  AVG(approval_days) AS mean_approval,
  AVG(CASE WHEN handling_days >= 0 THEN handling_days END) AS mean_handling_nonneg,
  AVG(handling_days) AS mean_handling_including_neg,
  AVG(CASE WHEN transit_days >= 0 THEN transit_days END) AS mean_transit_nonneg,
  AVG(transit_days) AS mean_transit_including_neg
FROM delivered_order;

-- On time uses the calendar date. The timestamp version is the contrast.
CREATE TABLE res_ontime AS
SELECT
  COUNT(*) AS n_orders,
  SUM(CASE WHEN order_estimated_delivery_date IS NULL THEN 1 ELSE 0 END) AS null_estimate,
  SUM(on_time_date) AS on_time_date_n,
  SUM(on_time_timestamp) AS on_time_timestamp_n,
  SUM(CASE
        WHEN date(order_delivered_customer_date) = date(order_estimated_delivery_date) THEN 1
        ELSE 0
      END) AS same_calendar_day_n,
  SUM(CASE
        WHEN date(order_delivered_customer_date) = date(order_estimated_delivery_date)
         AND on_time_timestamp = 0 THEN 1
        ELSE 0
      END) AS same_day_late_by_timestamp_n
FROM delivered_order;

CREATE TABLE res_money AS
SELECT
  (SELECT COUNT(*) FROM items WHERE freight_value IS NULL) AS freight_null_all_items,
  (SELECT COUNT(*) FROM items WHERE CAST(freight_value AS REAL) = 0) AS freight_zero_all_items,
  (SELECT COUNT(*) FROM items WHERE CAST(freight_value AS REAL) < 0) AS freight_neg_all_items,
  (SELECT COUNT(*) FROM items WHERE price IS NULL) AS price_null_all_items,
  (SELECT COUNT(*) FROM items WHERE CAST(price AS REAL) = 0) AS price_zero_all_items,
  (SELECT COUNT(*) FROM items WHERE CAST(price AS REAL) < 0) AS price_neg_all_items,
  (SELECT COUNT(*) FROM products WHERE product_weight_g IS NULL) AS weight_null_products,
  (SELECT COUNT(*) FROM products WHERE product_weight_g IS NOT NULL AND CAST(product_weight_g AS REAL) = 0) AS weight_zero_products,
  (SELECT COUNT(*) FROM products WHERE CAST(product_weight_g AS REAL) < 0) AS weight_neg_products,
  (SELECT COUNT(*) FROM item_enriched WHERE product_weight_g IS NULL) AS weight_null_all_joined_items,
  (SELECT COUNT(*) FROM item_enriched WHERE product_weight_g IS NOT NULL AND CAST(product_weight_g AS REAL) <= 0) AS weight_nonpositive_all_joined_items,
  (SELECT COUNT(*) FROM delivered_item WHERE freight_value IS NULL) AS freight_null_delivered,
  (SELECT COUNT(*) FROM delivered_item WHERE CAST(freight_value AS REAL) = 0) AS freight_zero_delivered,
  (SELECT COUNT(*) FROM delivered_item WHERE CAST(freight_value AS REAL) < 0) AS freight_neg_delivered,
  (SELECT COUNT(*) FROM delivered_item WHERE price IS NULL) AS price_null_delivered,
  (SELECT COUNT(*) FROM delivered_item WHERE CAST(price AS REAL) <= 0) AS price_nonpositive_delivered,
  (SELECT COUNT(*) FROM delivered_item WHERE product_weight_g IS NULL) AS weight_null_delivered_items,
  (SELECT COUNT(*) FROM delivered_item WHERE product_weight_g IS NOT NULL AND CAST(product_weight_g AS REAL) <= 0) AS weight_nonpositive_delivered_items,
  (SELECT COUNT(*) FROM delivered_item WHERE freight_per_kg IS NOT NULL) AS delivered_items_with_fpk,
  (SELECT SUM(CAST(REPLACE(freight_value, '.', '') AS INTEGER)) FROM delivered_item) AS delivered_freight_cents,
  (SELECT SUM(CAST(REPLACE(price, '.', '') AS INTEGER)) FROM delivered_item) AS delivered_price_cents,
  (SELECT SUM(CAST(REPLACE(freight_value, '.', '') AS INTEGER)) FROM delivered_item WHERE freight_per_kg IS NOT NULL) AS delivered_freight_cents_positive_weight,
  (SELECT SUM(CAST(product_weight_g AS INTEGER)) FROM delivered_item WHERE freight_per_kg IS NOT NULL) AS delivered_weight_g_positive,
  (SELECT AVG(CAST(freight_value AS REAL)) FROM delivered_item) AS mean_freight,
  (SELECT AVG(freight_per_kg) FROM delivered_item) AS mean_fpk,
  (SELECT AVG(CAST(freight_value AS REAL) / CAST(price AS REAL)) FROM delivered_item WHERE CAST(price AS REAL) > 0) AS mean_freight_over_price;

CREATE TABLE res_cross_state AS
SELECT
  COUNT(*) AS delivered_items,
  SUM(CASE WHEN customer_state IS NULL OR seller_state IS NULL THEN 1 ELSE 0 END) AS missing_state,
  SUM(CASE WHEN cross_state = 1 THEN 1 ELSE 0 END) AS cross_state_n,
  SUM(CASE WHEN cross_state = 0 THEN 1 ELSE 0 END) AS same_state_n
FROM delivered_item;

-- Where customers and sellers are. People are customer_unique_id.
-- A person in two states is counted in each; res_grain counts those people.
-- Do not join this back to orders on customer_unique_id: that would fan out.
CREATE TABLE res_state AS
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
ords AS (
  SELECT customer_state AS state, COUNT(*) AS orders
  FROM customers
  GROUP BY customer_state
),
sells AS (
  SELECT seller_state AS state, COUNT(*) AS sellers
  FROM sellers
  GROUP BY seller_state
),
deliv AS (
  SELECT customer_state AS state, COUNT(*) AS delivered_orders
  FROM delivered_order
  GROUP BY customer_state
)
SELECT
  st.state,
  COALESCE(p.customer_people, 0) AS customer_people,
  COALESCE(o.orders, 0) AS orders,
  COALESCE(s.sellers, 0) AS sellers,
  COALESCE(d.delivered_orders, 0) AS delivered_orders
FROM states st
LEFT JOIN people p ON p.state = st.state
LEFT JOIN ords o ON o.state = st.state
LEFT JOIN sells s ON s.state = st.state
LEFT JOIN deliv d ON d.state = st.state
ORDER BY customer_people DESC, st.state;

CREATE TABLE res_seller_delivered_state AS
SELECT seller_state AS state, COUNT(DISTINCT seller_id) AS sellers_with_delivered_item
FROM delivered_item
GROUP BY seller_state
ORDER BY sellers_with_delivered_item DESC;

CREATE TABLE res_orders_after_population AS
SELECT o.order_status, COUNT(*) AS n
FROM orders o
WHERE o.order_purchase_timestamp > (SELECT MAX(order_purchase_timestamp) FROM delivered_order)
GROUP BY o.order_status
ORDER BY n DESC;

CREATE TABLE res_order_overall AS
SELECT
  COUNT(*) AS n,
  AVG(purchase_to_door_days) AS mean_p2d,
  AVG(max_distance_km) AS mean_max_km,
  SUM(on_time_date) AS on_time_n,
  SUM(CASE WHEN transit_days >= 0 THEN 1 ELSE 0 END) AS transit_nonneg_n,
  AVG(CASE WHEN transit_days >= 0 THEN transit_days END) AS mean_transit_nonneg,
  SUM(CASE WHEN handling_days >= 0 THEN 1 ELSE 0 END) AS handling_nonneg_n,
  AVG(CASE WHEN handling_days >= 0 THEN handling_days END) AS mean_handling_nonneg,
  SUM(CASE WHEN approval_days IS NOT NULL THEN 1 ELSE 0 END) AS approval_n,
  AVG(approval_days) AS mean_approval
FROM delivered_order;

CREATE TABLE res_order_band_stats AS
SELECT
  order_band AS band,
  COUNT(*) AS n,
  AVG(max_distance_km) AS mean_km,
  AVG(purchase_to_door_days) AS mean_p2d,
  SUM(on_time_date) AS on_time_n,
  SUM(CASE WHEN transit_days >= 0 THEN 1 ELSE 0 END) AS transit_nonneg_n,
  AVG(CASE WHEN transit_days >= 0 THEN transit_days END) AS mean_transit_nonneg,
  SUM(CASE WHEN handling_days >= 0 THEN 1 ELSE 0 END) AS handling_nonneg_n,
  AVG(CASE WHEN handling_days >= 0 THEN handling_days END) AS mean_handling_nonneg,
  SUM(CASE WHEN approval_days IS NOT NULL THEN 1 ELSE 0 END) AS approval_n,
  AVG(approval_days) AS mean_approval,
  SUM(CASE WHEN transit_days < 0 THEN 1 ELSE 0 END) AS transit_neg_n,
  SUM(CASE WHEN handling_days < 0 THEN 1 ELSE 0 END) AS handling_neg_n
FROM delivered_order
WHERE order_band IS NOT NULL
GROUP BY order_band;

CREATE TABLE res_item_overall AS
SELECT
  COUNT(*) AS n,
  AVG(distance_km) AS mean_km,
  AVG(CAST(freight_value AS REAL)) AS mean_freight,
  SUM(CAST(REPLACE(freight_value, '.', '') AS INTEGER)) AS freight_cents,
  SUM(CASE WHEN freight_per_kg IS NOT NULL THEN 1 ELSE 0 END) AS n_fpk,
  AVG(freight_per_kg) AS mean_fpk,
  SUM(CASE WHEN cross_state = 1 THEN 1 ELSE 0 END) AS cross_n,
  AVG(CASE
        WHEN product_weight_g IS NOT NULL AND CAST(product_weight_g AS REAL) > 0
        THEN CAST(product_weight_g AS REAL)
      END) AS mean_weight_g_positive
FROM delivered_item;

CREATE TABLE res_item_band_stats AS
SELECT
  item_band AS band,
  COUNT(*) AS n,
  AVG(distance_km) AS mean_km,
  AVG(CAST(freight_value AS REAL)) AS mean_freight,
  SUM(CAST(REPLACE(freight_value, '.', '') AS INTEGER)) AS freight_cents,
  SUM(CASE WHEN freight_per_kg IS NOT NULL THEN 1 ELSE 0 END) AS n_fpk,
  AVG(freight_per_kg) AS mean_fpk,
  SUM(CASE WHEN cross_state = 1 THEN 1 ELSE 0 END) AS cross_n,
  AVG(CASE
        WHEN product_weight_g IS NOT NULL AND CAST(product_weight_g AS REAL) > 0
        THEN CAST(product_weight_g AS REAL)
      END) AS mean_weight_g
FROM delivered_item
WHERE item_band IS NOT NULL
GROUP BY item_band;

CREATE TABLE res_cross_by_band AS
SELECT
  item_band AS band,
  COUNT(*) AS n,
  SUM(cross_state) AS cross_n
FROM delivered_item
WHERE item_band IS NOT NULL
GROUP BY item_band;


-- Medians.
-- Rank rows by the metric. If the count is odd, both central ranks land on
-- the same row. If the count is even, they land on the two central rows and
-- the median is their average. low_central and high_central are those rows.
-- A negative handling or transit time is a timestamp out of order, not a
-- duration, so the leg median drops it. The order stays in purchase-to-door.
-- The unfiltered leg median is stored beside it so the exclusion is visible.


CREATE TABLE res_med_p2d AS
WITH ranked AS (
  SELECT purchase_to_door_days AS x,
         ROW_NUMBER() OVER (ORDER BY purchase_to_door_days) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_order
  WHERE purchase_to_door_days IS NOT NULL
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_approval AS
WITH ranked AS (
  SELECT approval_days AS x,
         ROW_NUMBER() OVER (ORDER BY approval_days) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_order
  WHERE approval_days IS NOT NULL AND approval_days >= 0
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_handling_nonneg AS
WITH ranked AS (
  SELECT handling_days AS x,
         ROW_NUMBER() OVER (ORDER BY handling_days) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_order
  WHERE handling_days IS NOT NULL AND handling_days >= 0
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_handling_all AS
WITH ranked AS (
  SELECT handling_days AS x,
         ROW_NUMBER() OVER (ORDER BY handling_days) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_order
  WHERE handling_days IS NOT NULL
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_transit_nonneg AS
WITH ranked AS (
  SELECT transit_days AS x,
         ROW_NUMBER() OVER (ORDER BY transit_days) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_order
  WHERE transit_days IS NOT NULL AND transit_days >= 0
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_transit_all AS
WITH ranked AS (
  SELECT transit_days AS x,
         ROW_NUMBER() OVER (ORDER BY transit_days) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_order
  WHERE transit_days IS NOT NULL
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_freight AS
WITH ranked AS (
  SELECT CAST(freight_value AS REAL) AS x,
         ROW_NUMBER() OVER (ORDER BY CAST(freight_value AS REAL)) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_item
  WHERE freight_value IS NOT NULL
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_fpk AS
WITH ranked AS (
  SELECT freight_per_kg AS x,
         ROW_NUMBER() OVER (ORDER BY freight_per_kg) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_item
  WHERE freight_per_kg IS NOT NULL
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_item_km AS
WITH ranked AS (
  SELECT distance_km AS x,
         ROW_NUMBER() OVER (ORDER BY distance_km) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_item
  WHERE distance_km IS NOT NULL
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_order_km AS
WITH ranked AS (
  SELECT max_distance_km AS x,
         ROW_NUMBER() OVER (ORDER BY max_distance_km) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_order
  WHERE max_distance_km IS NOT NULL
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_weight AS
WITH ranked AS (
  SELECT CAST(product_weight_g AS REAL) AS x,
         ROW_NUMBER() OVER (ORDER BY CAST(product_weight_g AS REAL)) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_item
  WHERE product_weight_g IS NOT NULL AND CAST(product_weight_g AS REAL) > 0
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_freight_over_price AS
WITH ranked AS (
  SELECT CAST(freight_value AS REAL) / CAST(price AS REAL) AS x,
         ROW_NUMBER() OVER (ORDER BY CAST(freight_value AS REAL) / CAST(price AS REAL)) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_item
  WHERE CAST(price AS REAL) > 0
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_price AS
WITH ranked AS (
  SELECT CAST(price AS REAL) AS x,
         ROW_NUMBER() OVER (ORDER BY CAST(price AS REAL)) AS rn,
         COUNT(*) OVER () AS n
  FROM delivered_item
  WHERE price IS NOT NULL
)
SELECT AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


CREATE TABLE res_med_p2d_band AS
WITH ranked AS (
  SELECT order_band AS band,
         purchase_to_door_days AS x,
         ROW_NUMBER() OVER (PARTITION BY order_band ORDER BY purchase_to_door_days) AS rn,
         COUNT(*) OVER (PARTITION BY order_band) AS n
  FROM delivered_order
  WHERE order_band IS NOT NULL
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;


CREATE TABLE res_med_approval_band AS
WITH ranked AS (
  SELECT order_band AS band,
         approval_days AS x,
         ROW_NUMBER() OVER (PARTITION BY order_band ORDER BY approval_days) AS rn,
         COUNT(*) OVER (PARTITION BY order_band) AS n
  FROM delivered_order
  WHERE order_band IS NOT NULL AND approval_days IS NOT NULL AND approval_days >= 0
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;


CREATE TABLE res_med_handling_band AS
WITH ranked AS (
  SELECT order_band AS band,
         handling_days AS x,
         ROW_NUMBER() OVER (PARTITION BY order_band ORDER BY handling_days) AS rn,
         COUNT(*) OVER (PARTITION BY order_band) AS n
  FROM delivered_order
  WHERE order_band IS NOT NULL AND handling_days IS NOT NULL AND handling_days >= 0
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;


CREATE TABLE res_med_transit_band AS
WITH ranked AS (
  SELECT order_band AS band,
         transit_days AS x,
         ROW_NUMBER() OVER (PARTITION BY order_band ORDER BY transit_days) AS rn,
         COUNT(*) OVER (PARTITION BY order_band) AS n
  FROM delivered_order
  WHERE order_band IS NOT NULL AND transit_days IS NOT NULL AND transit_days >= 0
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;


CREATE TABLE res_med_order_km_band AS
WITH ranked AS (
  SELECT order_band AS band,
         max_distance_km AS x,
         ROW_NUMBER() OVER (PARTITION BY order_band ORDER BY max_distance_km) AS rn,
         COUNT(*) OVER (PARTITION BY order_band) AS n
  FROM delivered_order
  WHERE order_band IS NOT NULL
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;


CREATE TABLE res_med_freight_band AS
WITH ranked AS (
  SELECT item_band AS band,
         CAST(freight_value AS REAL) AS x,
         ROW_NUMBER() OVER (PARTITION BY item_band ORDER BY CAST(freight_value AS REAL)) AS rn,
         COUNT(*) OVER (PARTITION BY item_band) AS n
  FROM delivered_item
  WHERE item_band IS NOT NULL
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;


CREATE TABLE res_med_fpk_band AS
WITH ranked AS (
  SELECT item_band AS band,
         freight_per_kg AS x,
         ROW_NUMBER() OVER (PARTITION BY item_band ORDER BY freight_per_kg) AS rn,
         COUNT(*) OVER (PARTITION BY item_band) AS n
  FROM delivered_item
  WHERE item_band IS NOT NULL AND freight_per_kg IS NOT NULL
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;


CREATE TABLE res_med_item_km_band AS
WITH ranked AS (
  SELECT item_band AS band,
         distance_km AS x,
         ROW_NUMBER() OVER (PARTITION BY item_band ORDER BY distance_km) AS rn,
         COUNT(*) OVER (PARTITION BY item_band) AS n
  FROM delivered_item
  WHERE item_band IS NOT NULL
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;


CREATE TABLE res_med_weight_band AS
WITH ranked AS (
  SELECT item_band AS band,
         CAST(product_weight_g AS REAL) AS x,
         ROW_NUMBER() OVER (PARTITION BY item_band ORDER BY CAST(product_weight_g AS REAL)) AS rn,
         COUNT(*) OVER (PARTITION BY item_band) AS n
  FROM delivered_item
  WHERE item_band IS NOT NULL AND product_weight_g IS NOT NULL AND CAST(product_weight_g AS REAL) > 0
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;


CREATE TABLE res_med_km_by_cross AS
WITH ranked AS (
  SELECT cross_state AS band,
         distance_km AS x,
         ROW_NUMBER() OVER (PARTITION BY cross_state ORDER BY distance_km) AS rn,
         COUNT(*) OVER (PARTITION BY cross_state) AS n
  FROM delivered_item
  WHERE distance_km IS NOT NULL AND cross_state IS NOT NULL
)
SELECT band,
       AVG(x) AS median_x,
       MIN(x) AS low_central,
       MAX(x) AS high_central,
       MIN(n) AS n
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY band;
