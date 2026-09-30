-- Late-delivery scorecard. SQLite-compatible. Read-only SELECTs.
--
-- Table: order_lines, one row per order line from DataCoSupplyChainDataset.csv
-- (Latin-1, 180,519 lines, 53 columns). This file does not load the CSV and
-- does not create a database. src/analyze_late_delivery.py reads the CSV and
-- writes the same aggregates to data/processed/. The raw CSV stays git-ignored.
--
-- Grain: the row is an order line (Order Item Id), not an order.
-- Order Id repeats (65,752 distinct orders). Analyze checked that Shipping Mode,
-- Late_delivery_risk, Days for shipping (real), Days for shipment (scheduled),
-- and Delivery Status do not vary inside an Order Id. The lines on an order
-- do not disagree, so this scorecard stays at line grain. It does not also
-- publish an order-level rate. An order with five lines would count five times;
-- that is the grain the flag is stored on.
--
-- KPI population: Delivery Status <> 'Shipping canceled'.
-- A canceled line did not keep or break a delivery promise. Every canceled
-- line has Late_delivery_risk = 0, including lines whose real days exceed the
-- scheduled days. Leaving those lines in would call them on time.
-- The WHERE on each rate query below is that exclusion. Do not drop it.
--
-- Late rate: Late_delivery_risk = 1, divided by lines in the population.
-- On-time rate: Late_delivery_risk = 0, same denominator. One minus the other.
-- Advance shipping is on time. The business question is "late," not "perfect."
--
-- Mean slip is AVG(real days - scheduled days). Positive means longer than
-- the promise. SQLite has no MEDIAN() aggregate. Median lead time and median
-- slip are computed in src/analyze_late_delivery.py, not here, so this file
-- does not invent a median by averaging.
--
-- Personal-data columns (names, email, password, street) are not selected.

-- ---------------------------------------------------------------------------
-- Population check. Canceled lines are counted here so the exclusion is
-- visible, and they are not in the rate queries below.
-- Grain: order line. No WHERE yet: this is the count the WHERE removes.
-- ---------------------------------------------------------------------------
SELECT
    CASE
        WHEN "Delivery Status" = 'Shipping canceled' THEN 'canceled_excluded'
        ELSE 'kpi_population'
    END AS population,
    COUNT(*) AS lines,
    SUM("Late_delivery_risk") AS late_lines
FROM order_lines
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------------
-- How the flag labels canceled lines, against the day comparison.
-- real > scheduled would be the day-rule for "late". The flag marks every
-- canceled line 0, whether or not real days exceeded the promise.
-- These rows are not in the KPI rate.
-- ---------------------------------------------------------------------------
SELECT
    "Late_delivery_risk" AS late_delivery_risk,
    CASE
        WHEN "Days for shipping (real)" > "Days for shipment (scheduled)" THEN 1
        ELSE 0
    END AS real_exceeds_scheduled,
    COUNT(*) AS lines
FROM order_lines
WHERE "Delivery Status" = 'Shipping canceled'
GROUP BY 1, 2
ORDER BY 1, 2;

-- ---------------------------------------------------------------------------
-- Cross-tab of the flag against Delivery Status. All lines, so Advance
-- shipping, Shipping on time, Late delivery, and Shipping canceled each
-- show their flag counts. This is a check, not the KPI rate.
-- ---------------------------------------------------------------------------
SELECT
    "Delivery Status" AS delivery_status,
    "Late_delivery_risk" AS late_delivery_risk,
    COUNT(*) AS lines
FROM order_lines
GROUP BY 1, 2
ORDER BY 1, 2;

-- ---------------------------------------------------------------------------
-- Scheduled days versus Shipping Mode. One row per pair.
-- Analyze found one scheduled value for each mode. If a mode appears twice
-- here, the two columns are no longer the same fact.
-- All lines, including canceled: the promise is set before the outcome.
-- ---------------------------------------------------------------------------
SELECT
    "Shipping Mode" AS shipping_mode,
    "Days for shipment (scheduled)" AS days_scheduled,
    COUNT(*) AS lines
FROM order_lines
GROUP BY 1, 2
ORDER BY 2, 1;

-- ---------------------------------------------------------------------------
-- Overall KPI. Grain: order line.
-- WHERE drops Shipping canceled. See the header for why.
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*) AS lines,
    SUM("Late_delivery_risk") AS late_lines,
    COUNT(*) - SUM("Late_delivery_risk") AS on_time_lines,
    1.0 * SUM("Late_delivery_risk") / COUNT(*) AS late_rate,
    1.0 * (COUNT(*) - SUM("Late_delivery_risk")) / COUNT(*) AS on_time_rate,
    AVG("Days for shipping (real)") AS mean_lead_time,
    AVG("Days for shipping (real)" - "Days for shipment (scheduled)") AS mean_slip
FROM order_lines
WHERE "Delivery Status" <> 'Shipping canceled';

-- ---------------------------------------------------------------------------
-- Late rate by Shipping Mode. Grain: order line. Same WHERE.
-- Sort by late rate descending. lines sits beside the rate so a large mode
-- with a low rate is not read as the worst mode. Standard Class can have
-- the most late lines because it has the most lines.
-- ---------------------------------------------------------------------------
SELECT
    "Shipping Mode" AS shipping_mode,
    COUNT(*) AS lines,
    SUM("Late_delivery_risk") AS late_lines,
    COUNT(*) - SUM("Late_delivery_risk") AS on_time_lines,
    1.0 * SUM("Late_delivery_risk") / COUNT(*) AS late_rate,
    AVG("Days for shipping (real)" - "Days for shipment (scheduled)") AS mean_slip,
    AVG("Days for shipping (real)") AS mean_lead_time
FROM order_lines
WHERE "Delivery Status" <> 'Shipping canceled'
GROUP BY "Shipping Mode"
ORDER BY late_rate DESC, lines DESC;

-- ---------------------------------------------------------------------------
-- Late rate by Order Region. Finer geography cut. Same grain and WHERE.
-- ---------------------------------------------------------------------------
SELECT
    "Order Region" AS order_region,
    COUNT(*) AS lines,
    SUM("Late_delivery_risk") AS late_lines,
    1.0 * SUM("Late_delivery_risk") / COUNT(*) AS late_rate,
    AVG("Days for shipping (real)" - "Days for shipment (scheduled)") AS mean_slip
FROM order_lines
WHERE "Delivery Status" <> 'Shipping canceled'
GROUP BY "Order Region"
ORDER BY late_rate DESC, lines DESC;

-- ---------------------------------------------------------------------------
-- Late rate by Market. Region rolled up. Same grain and WHERE.
-- ---------------------------------------------------------------------------
SELECT
    "Market" AS market,
    COUNT(*) AS lines,
    SUM("Late_delivery_risk") AS late_lines,
    1.0 * SUM("Late_delivery_risk") / COUNT(*) AS late_rate,
    AVG("Days for shipping (real)" - "Days for shipment (scheduled)") AS mean_slip
FROM order_lines
WHERE "Delivery Status" <> 'Shipping canceled'
GROUP BY "Market"
ORDER BY late_rate DESC, lines DESC;

-- ---------------------------------------------------------------------------
-- Late rate by Shipping Mode inside Market.
-- Same grain and WHERE. This is the mix check: if a market looks worse only
-- because of its mode mix, the rate inside a mode will not move with market.
-- It is a cross-tab, not a causal estimate.
-- ---------------------------------------------------------------------------
SELECT
    "Market" AS market,
    "Shipping Mode" AS shipping_mode,
    COUNT(*) AS lines,
    SUM("Late_delivery_risk") AS late_lines,
    1.0 * SUM("Late_delivery_risk") / COUNT(*) AS late_rate
FROM order_lines
WHERE "Delivery Status" <> 'Shipping canceled'
GROUP BY "Market", "Shipping Mode"
ORDER BY "Shipping Mode", late_rate DESC;

-- ---------------------------------------------------------------------------
-- Late rate by Category Name. Finer product cut. Same grain and WHERE.
-- Category labels are kept as stored, including trailing spaces.
-- ---------------------------------------------------------------------------
SELECT
    "Category Name" AS category_name,
    COUNT(*) AS lines,
    SUM("Late_delivery_risk") AS late_lines,
    1.0 * SUM("Late_delivery_risk") / COUNT(*) AS late_rate,
    AVG("Days for shipping (real)" - "Days for shipment (scheduled)") AS mean_slip
FROM order_lines
WHERE "Delivery Status" <> 'Shipping canceled'
GROUP BY "Category Name"
ORDER BY late_rate DESC, lines DESC;

-- ---------------------------------------------------------------------------
-- Late rate by Department Name. Category rolled up. Same grain and WHERE.
-- ---------------------------------------------------------------------------
SELECT
    "Department Name" AS department_name,
    COUNT(*) AS lines,
    SUM("Late_delivery_risk") AS late_lines,
    1.0 * SUM("Late_delivery_risk") / COUNT(*) AS late_rate,
    AVG("Days for shipping (real)" - "Days for shipment (scheduled)") AS mean_slip
FROM order_lines
WHERE "Delivery Status" <> 'Shipping canceled'
GROUP BY "Department Name"
ORDER BY late_rate DESC, lines DESC;
