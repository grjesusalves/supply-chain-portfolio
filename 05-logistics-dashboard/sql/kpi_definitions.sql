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
-- delivered on or before order_estimated_delivery_date
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
-- One row per week of order_purchase_timestamp, plus the distance-band cut
-- and the state cut. Bands are chosen in Analyze from the distance distribution
-- and then frozen. They are not chosen to make the chart smoother.
