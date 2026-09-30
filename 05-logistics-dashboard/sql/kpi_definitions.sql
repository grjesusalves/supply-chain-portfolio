-- Plan definitions only. This file does not run against the data in the Plan stage.
-- Analyze will execute these rules and record the row counts.
-- SQL comments use -- rather than #. The reasoning is the comment.

-- Geolocation has many points per zip prefix (about 1,000,163 rows in the file).
-- Join it only after this collapse, or every item will fan out.
-- centroid: one row per zip prefix, mean latitude, mean longitude.

-- Distance is haversine kilometers between the customer prefix centroid
-- and the seller prefix centroid. Great-circle, not road distance.
-- Earth radius used here: 6371 km.
-- A prefix missing from geolocation does not get a state-average fill.
-- Those items stay in volume counts and drop out of distance metrics.
--
-- Join rule added in Analyze, because the extract proved an unpadded join wrong.
-- Customer and seller prefixes are stored without leading zeros (length 4 or 5).
-- Geolocation prefixes are 5 characters. Pad with
-- printf('%05d', CAST(prefix AS INTEGER)) before the join.
-- That restores the prefix. It does not impute a location that is still missing.
-- Without the pad, 24,265 of 99,441 customer rows miss a centroid.
-- With the pad, 279 do. See reports/02-analyze.md.

-- Grain
-- Freight and distance: one row per order item (order_id, order_item_id).
-- freight_value and seller_id live on the item.
-- Delivery time: one row per order.
-- On a multi-seller order, delivery time uses the MAX item distance.
-- The customer waits for the farthest seller. Freight does not use that max.

-- Population for time and freight metrics
-- order_status = 'delivered'
-- order_delivered_customer_date is present
-- delivered timestamp is after order_purchase_timestamp
-- Other statuses are counted in Analyze and then excluded.

-- Purchase-to-door days
-- julianday(order_delivered_customer_date) - julianday(order_purchase_timestamp)
-- Headline. What the customer feels. Report the median, show the mean beside it.

-- Legs, so a seller delay is not called a distance effect
-- approval lag: order_approved_at - order_purchase_timestamp
-- handling:    order_delivered_carrier_date - order_approved_at
-- transit:     order_delivered_customer_date - order_delivered_carrier_date
-- Weekly page shows purchase-to-door and transit. Distance should show up in transit.

-- On time
-- Delivered on or before the estimated delivery DATE, not the raw timestamp.
-- Analyze found every order_estimated_delivery_date stored at 00:00:00
-- (99,441 / 99,441). A timestamp compare would mark a delivery later on the
-- promised calendar day as late (1,292 delivered orders in this extract).
-- date(order_delivered_customer_date) <= date(order_estimated_delivery_date)
-- Null estimate: drop from this rate only, and count the drops.
-- Do not report on-time rate without median days. The promise may already be looser for far states.

-- Freight
-- Same delivered population.
-- Median freight_value per item.
-- Freight per kg: freight_value / (product_weight_g / 1000.0)
-- Join products on product_id.
-- Non-positive or null weight: keep in freight totals, drop from per-kg.

-- Cross-state share
-- customer_state <> seller_state, among delivered items with both states present.

-- Weekly page grain
-- One row per week of order_purchase_timestamp (the Monday of that week),
-- plus the distance-band cut and the state cut.
--
-- Bands frozen in Construct. Right-open. The last band includes the tail.
-- 50 km belongs to 50-200, not to 0-50.
--   0-50 km
--   50-200 km
--   200-500 km
--   500-1,000 km
--   1,000 km or more
-- Not moved to make a chart smoother. See sql/kpi_construct.sql.
