-- Freight text checks. SQLite-compatible. Read-only SELECTs after one view.
--
-- Table: delivery_lines, one row per line from SCMS_Delivery_History_Dataset.csv
-- (Latin-1, 10,324 lines, 33 columns). This file does not load the CSV and
-- does not create a database. src/analyze_freight.py reads the CSV, builds
-- the same classes, and executes this file against an in-memory table of
-- those lines. The raw CSV stays git-ignored.
--
-- Grain: the row is a line item. The shipment id is "ASN/DN #".
-- The raw-string gate is the first half of this file. Freight Cost (USD)
-- is not the same string on every line of 1,299 shipments, and Weight
-- (Kilograms) is not the same string on every line of 1,322 shipments.
-- Those counts stay here. They are not averaged away.
--
-- The accepted rule, 2026-09-29, is the second half. One shipment per
-- ASN/DN. The freight string and the weight string are the single line
-- where First Line Designation = 'Yes'. That is not an average, and it
-- is not a zero on the lines that say See. The See lines cite that Yes
-- line. The queries below the gate compute the weighed-set median and
-- mean of freight per kilogram, the freight-to-value median and mean,
-- the exclusion counts, and the same rates by shipment mode. Country
-- and vendor rankings stay in the Python scorecard; SQLite has no
-- MEDIAN() aggregate, and the median below is the middle row or the
-- average of the two middle rows, which is the same rule pandas uses.
--
-- Exclusion that a later rate query must keep, once a shipment figure exists:
-- a freight or weight cell that is not a plain decimal is out of the priced
-- set and out of the weighed set. It is not zero.
--   'Freight Included in Commodity Cost' is freight bundled into the product
--   price, which is not a freight bill this scorecard can see.
--   'Invoiced Separately' is a freight bill this extract does not contain.
--   'Weight Captured Separately' is a weight this extract does not contain.
--   'See ASN-… (ID#:…)' / 'See DN-… (ID#:…)' points at another line. It is
--   not a second charge. It is also not a number.
-- Do not CAST those strings. In SQLite, CAST('See ASN-1 (ID#:2)' AS REAL)
-- is 0, and a zero would make the shipment look free.
--
-- A plain decimal is digits with at most one dot, nothing else. The GLOB
-- tests below are that definition. SQLite GLOB negates a class with ^,
-- not with !. Writing [!0-9] would treat ! as a literal and accept every digit. They match the Python check
-- ^[0-9]+(\.[0-9]+)?$ on this file (src/analyze_freight.py compares them).
--
-- Insurance is not selected. It is not the headline metric.
--
-- The delivery-date window is not computed here. SQLite's date() does not
-- parse the file's 2-Jun-06 values. src/analyze_freight.py parses those
-- three delivery columns with an explicit format and counts failures.

-- ---------------------------------------------------------------------------
-- Line-level flags. One row per input line. This view does not collapse an
-- ASN/DN to one freight figure.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS line_flags;
CREATE VIEW line_flags AS
SELECT
    "ID",
    "ASN/DN #",
    "Shipment Mode",
    "Vendor INCO Term",
    "Vendor",
    "Country",
    "Manufacturing Site",
    "Freight Cost (USD)",
    "Weight (Kilograms)",
    "Line Item Value",
    CASE
        WHEN "Freight Cost (USD)" NOT GLOB '*[^0-9.]*'
         AND "Freight Cost (USD)" GLOB '*[0-9]*'
         AND "Freight Cost (USD)" NOT GLOB '*.*.*'
         AND "Freight Cost (USD)" NOT GLOB '.*'
         AND "Freight Cost (USD)" NOT GLOB '*.'
            THEN 'numeric'
        WHEN "Freight Cost (USD)" = 'Freight Included in Commodity Cost'
            THEN 'included_in_price'
        WHEN "Freight Cost (USD)" = 'Invoiced Separately'
            THEN 'invoiced_separately'
        WHEN "Freight Cost (USD)" LIKE 'See ASN-%'
          OR "Freight Cost (USD)" LIKE 'See DN-%'
            THEN 'see_another_note'
        WHEN "Freight Cost (USD)" IS NULL OR TRIM("Freight Cost (USD)") = ''
            THEN 'blank'
        ELSE 'other'
    END AS freight_class,
    CASE
        WHEN "Weight (Kilograms)" NOT GLOB '*[^0-9.]*'
         AND "Weight (Kilograms)" GLOB '*[0-9]*'
         AND "Weight (Kilograms)" NOT GLOB '*.*.*'
         AND "Weight (Kilograms)" NOT GLOB '.*'
         AND "Weight (Kilograms)" NOT GLOB '*.'
            THEN 'numeric'
        WHEN "Weight (Kilograms)" = 'Weight Captured Separately'
            THEN 'captured_separately'
        WHEN "Weight (Kilograms)" LIKE 'See ASN-%'
          OR "Weight (Kilograms)" LIKE 'See DN-%'
            THEN 'see_another_note'
        WHEN "Weight (Kilograms)" IS NULL OR TRIM("Weight (Kilograms)") = ''
            THEN 'blank'
        ELSE 'other'
    END AS weight_class
FROM delivery_lines;

-- ---------------------------------------------------------------------------
-- File grain. line_rows is the extract. shipments is distinct ASN/DN #.
-- A shipment with five lines counts five times in line_rows and once here.
-- ---------------------------------------------------------------------------
SELECT
    'row_and_asn' AS check_name,
    COUNT(*) AS line_rows,
    COUNT(DISTINCT "ASN/DN #") AS shipments
FROM delivery_lines;

-- ---------------------------------------------------------------------------
-- Freight text, line grain. Do not read lines as shipments. See pointers and
-- the included-in-price phrase repeat across the lines of one note.
-- ---------------------------------------------------------------------------
SELECT
    'freight_class' AS check_name,
    freight_class AS class_name,
    COUNT(*) AS lines
FROM line_flags
GROUP BY freight_class
ORDER BY freight_class;

-- ---------------------------------------------------------------------------
-- Weight text, line grain. Same warning as freight.
-- ---------------------------------------------------------------------------
SELECT
    'weight_class' AS check_name,
    weight_class AS class_name,
    COUNT(*) AS lines
FROM line_flags
GROUP BY weight_class
ORDER BY weight_class;

-- ---------------------------------------------------------------------------
-- Shipment mode, line grain. (blank) is a null mode, not a mode name.
-- No shipment count: the grain gate did not pass, so this query does not
-- pick a line to represent the note.
-- ---------------------------------------------------------------------------
SELECT
    'shipment_mode' AS check_name,
    COALESCE("Shipment Mode", '(blank)') AS label,
    COUNT(*) AS lines
FROM delivery_lines
GROUP BY COALESCE("Shipment Mode", '(blank)')
ORDER BY label;

-- ---------------------------------------------------------------------------
-- Vendor INCO term, line grain. Not a rate, and not a shipment count.
-- ---------------------------------------------------------------------------
SELECT
    'vendor_inco_term' AS check_name,
    "Vendor INCO Term" AS label,
    COUNT(*) AS lines
FROM delivery_lines
GROUP BY "Vendor INCO Term"
ORDER BY label;

-- ---------------------------------------------------------------------------
-- Constancy gate. A shipment is not constant when two lines carry different
-- freight strings. Pointers count as a different string. That is why this
-- file does not rate the raw string. The Yes-line rates are a later
-- section, and they do not flip this gate to passed.
-- ---------------------------------------------------------------------------
SELECT
    'freight_not_constant' AS check_name,
    COUNT(*) AS shipments
FROM (
    SELECT "ASN/DN #"
    FROM delivery_lines
    GROUP BY "ASN/DN #"
    HAVING COUNT(DISTINCT "Freight Cost (USD)") > 1
);

SELECT
    'weight_not_constant' AS check_name,
    COUNT(*) AS shipments
FROM (
    SELECT "ASN/DN #"
    FROM delivery_lines
    GROUP BY "ASN/DN #"
    HAVING COUNT(DISTINCT "Weight (Kilograms)") > 1
);

-- ---------------------------------------------------------------------------
-- Conflicting numbers, as opposed to a number sitting next to a pointer.
-- The WHERE keeps only plain decimals, so a See line cannot become 0 and
-- then look like a second numeric value. Zero rows is "no two different
-- numeric strings", not "the field is constant".
-- ---------------------------------------------------------------------------
SELECT
    'two_numeric_freight' AS check_name,
    COUNT(*) AS shipments
FROM (
    SELECT "ASN/DN #"
    FROM delivery_lines
    WHERE "Freight Cost (USD)" NOT GLOB '*[^0-9.]*'
      AND "Freight Cost (USD)" GLOB '*[0-9]*'
      AND "Freight Cost (USD)" NOT GLOB '*.*.*'
      AND "Freight Cost (USD)" NOT GLOB '.*'
      AND "Freight Cost (USD)" NOT GLOB '*.'
    GROUP BY "ASN/DN #"
    HAVING COUNT(DISTINCT "Freight Cost (USD)") > 1
);

SELECT
    'two_numeric_weight' AS check_name,
    COUNT(*) AS shipments
FROM (
    SELECT "ASN/DN #"
    FROM delivery_lines
    WHERE "Weight (Kilograms)" NOT GLOB '*[^0-9.]*'
      AND "Weight (Kilograms)" GLOB '*[0-9]*'
      AND "Weight (Kilograms)" NOT GLOB '*.*.*'
      AND "Weight (Kilograms)" NOT GLOB '.*'
      AND "Weight (Kilograms)" NOT GLOB '*.'
    GROUP BY "ASN/DN #"
    HAVING COUNT(DISTINCT "Weight (Kilograms)") > 1
);

-- ---------------------------------------------------------------------------
-- A zero line-item value cannot support freight / value. This is a line
-- count. Shipment sums are not taken in this file.
-- ---------------------------------------------------------------------------
SELECT
    'line_value_zero' AS check_name,
    COUNT(*) AS lines
FROM delivery_lines
WHERE "Line Item Value" = '0';

-- ---------------------------------------------------------------------------
-- See lines whose pointer is not their own ASN/DN #. The Python check also
-- requires the cited ID to be the first line of that same note. SQLite
-- confirms the note id embedded in the text.
-- ---------------------------------------------------------------------------
SELECT
    'see_not_own_asn' AS check_name,
    COUNT(*) AS lines
FROM delivery_lines
WHERE (
        "Freight Cost (USD)" LIKE 'See ASN-%'
        OR "Freight Cost (USD)" LIKE 'See DN-%'
    )
  AND "Freight Cost (USD)" NOT LIKE 'See ' || "ASN/DN #" || ' (ID#:%';

-- ---------------------------------------------------------------------------
-- Blank shipment mode. Null and empty text are the same bucket.
-- ---------------------------------------------------------------------------
SELECT
    'blank_shipment_mode' AS check_name,
    SUM(
        CASE
            WHEN "Shipment Mode" IS NULL OR TRIM("Shipment Mode") = '' THEN 1
            ELSE 0
        END
    ) AS lines
FROM delivery_lines;

-- ---------------------------------------------------------------------------
-- Cardinality a later regression would have to carry. Distinct non-null
-- labels. Not a ranking by cost.
-- ---------------------------------------------------------------------------
SELECT
    'cardinality' AS check_name,
    COUNT(DISTINCT "Vendor") AS vendor,
    COUNT(DISTINCT "Country") AS country,
    COUNT(DISTINCT "Manufacturing Site") AS manufacturing_site
FROM delivery_lines;

-- ---------------------------------------------------------------------------
-- Accepted Yes-line rule (2026-09-29).
--
-- One row per ASN/DN, taken from the line where First Line Designation
-- is Yes. Freight and weight stay text until the plain-decimal test
-- passes. CAST is applied only after that test, and to Line Item Value,
-- which is a plain decimal on every row. CAST is not applied to a See
-- pointer, to "Freight Included in Commodity Cost", to "Invoiced
-- Separately", or to "Weight Captured Separately".
--
-- Priced: the Yes-line freight is a plain decimal.
-- Weighed: priced, the Yes-line weight is a plain decimal, and that
-- weight is greater than 0. A weight of 0 is a drop, not a rate.
-- Freight-to-value: priced, and the sum of Line Item Value on the note
-- is positive. The sum is every line on the note. Freight is not summed.
-- Insurance is not selected.
--
-- Manufacturing site is not in this rollup. It is not constant inside
-- the note, and this rule does not pick a site.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS shipment_value;
CREATE VIEW shipment_value AS
SELECT
    "ASN/DN #" AS asn_dn,
    COUNT(*) AS line_count,
    SUM(CAST("Line Item Value" AS REAL)) AS line_item_value_sum
FROM delivery_lines
GROUP BY "ASN/DN #";

DROP VIEW IF EXISTS yes_shipment;
CREATE VIEW yes_shipment AS
SELECT
    y."ASN/DN #" AS asn_dn,
    COALESCE(y."Shipment Mode", '(blank)') AS shipment_mode,
    v.line_item_value_sum AS line_item_value_sum,
    CASE
        WHEN y."Freight Cost (USD)" NOT GLOB '*[^0-9.]*'
         AND y."Freight Cost (USD)" GLOB '*[0-9]*'
         AND y."Freight Cost (USD)" NOT GLOB '*.*.*'
         AND y."Freight Cost (USD)" NOT GLOB '.*'
         AND y."Freight Cost (USD)" NOT GLOB '*.'
            THEN CAST(y."Freight Cost (USD)" AS REAL)
    END AS freight_usd,
    CASE
        WHEN y."Weight (Kilograms)" NOT GLOB '*[^0-9.]*'
         AND y."Weight (Kilograms)" GLOB '*[0-9]*'
         AND y."Weight (Kilograms)" NOT GLOB '*.*.*'
         AND y."Weight (Kilograms)" NOT GLOB '.*'
         AND y."Weight (Kilograms)" NOT GLOB '*.'
            THEN CAST(y."Weight (Kilograms)" AS REAL)
    END AS weight_kg,
    CASE
        WHEN y."Freight Cost (USD)" = 'Freight Included in Commodity Cost'
            THEN 'included_in_price'
        WHEN y."Freight Cost (USD)" = 'Invoiced Separately'
            THEN 'invoiced_separately'
        WHEN y."Freight Cost (USD)" LIKE 'See ASN-%'
          OR y."Freight Cost (USD)" LIKE 'See DN-%'
            THEN 'see_another_note'
        WHEN y."Freight Cost (USD)" NOT GLOB '*[^0-9.]*'
         AND y."Freight Cost (USD)" GLOB '*[0-9]*'
         AND y."Freight Cost (USD)" NOT GLOB '*.*.*'
         AND y."Freight Cost (USD)" NOT GLOB '.*'
         AND y."Freight Cost (USD)" NOT GLOB '*.'
            THEN 'numeric'
        ELSE 'other'
    END AS yes_freight_class
FROM delivery_lines AS y
INNER JOIN shipment_value AS v
    ON v.asn_dn = y."ASN/DN #"
WHERE y."First Line Designation" = 'Yes';

SELECT
    'yes_line_rows' AS check_name,
    COUNT(*) AS lines,
    COUNT(DISTINCT asn_dn) AS shipments
FROM yes_shipment;

SELECT
    'yes_freight_other' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'other';

SELECT
    'yes_priced' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'numeric';

SELECT
    'yes_weighed' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'numeric'
  AND weight_kg IS NOT NULL
  AND weight_kg > 0;

SELECT
    'yes_freight_to_value' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'numeric'
  AND line_item_value_sum > 0;

SELECT
    'yes_excluded_included' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'included_in_price';

SELECT
    'yes_excluded_invoiced' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'invoiced_separately';

SELECT
    'yes_excluded_see' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'see_another_note';

SELECT
    'yes_excluded_weight_text' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'numeric'
  AND weight_kg IS NULL;

SELECT
    'yes_excluded_weight_not_positive' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'numeric'
  AND weight_kg IS NOT NULL
  AND weight_kg <= 0;

SELECT
    'yes_value_sum_le_0' AS check_name,
    COUNT(*) AS shipments
FROM shipment_value
WHERE line_item_value_sum <= 0;

SELECT
    'yes_priced_value_sum_le_0' AS check_name,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'numeric'
  AND line_item_value_sum <= 0;

SELECT
    'yes_total_numeric_freight' AS check_name,
    SUM(freight_usd) AS total_freight,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'numeric';

WITH ranked AS (
    SELECT
        freight_usd * 1.0 / weight_kg AS rate,
        ROW_NUMBER() OVER (ORDER BY freight_usd * 1.0 / weight_kg) AS rn,
        COUNT(*) OVER () AS n
    FROM yes_shipment
    WHERE yes_freight_class = 'numeric'
      AND weight_kg IS NOT NULL
      AND weight_kg > 0
)
SELECT
    'yes_median_freight_per_kg' AS check_name,
    AVG(CASE WHEN rn IN ((n + 1) / 2, (n + 2) / 2) THEN rate END) AS median_rate,
    MAX(n) AS weighed_n
FROM ranked;

SELECT
    'yes_mean_freight_per_kg' AS check_name,
    AVG(freight_usd * 1.0 / weight_kg) AS mean_rate,
    COUNT(*) AS weighed_n
FROM yes_shipment
WHERE yes_freight_class = 'numeric'
  AND weight_kg IS NOT NULL
  AND weight_kg > 0;

WITH ranked AS (
    SELECT
        freight_usd * 1.0 / line_item_value_sum AS rate,
        ROW_NUMBER() OVER (ORDER BY freight_usd * 1.0 / line_item_value_sum) AS rn,
        COUNT(*) OVER () AS n
    FROM yes_shipment
    WHERE yes_freight_class = 'numeric'
      AND line_item_value_sum > 0
)
SELECT
    'yes_median_freight_to_value' AS check_name,
    AVG(CASE WHEN rn IN ((n + 1) / 2, (n + 2) / 2) THEN rate END) AS median_rate,
    MAX(n) AS weighed_n
FROM ranked;

SELECT
    'yes_mean_freight_to_value' AS check_name,
    AVG(freight_usd * 1.0 / line_item_value_sum) AS mean_rate,
    COUNT(*) AS shipments
FROM yes_shipment
WHERE yes_freight_class = 'numeric'
  AND line_item_value_sum > 0;

WITH ranked AS (
    SELECT
        shipment_mode,
        freight_usd * 1.0 / weight_kg AS rate,
        ROW_NUMBER() OVER (
            PARTITION BY shipment_mode
            ORDER BY freight_usd * 1.0 / weight_kg
        ) AS rn,
        COUNT(*) OVER (PARTITION BY shipment_mode) AS n
    FROM yes_shipment
    WHERE yes_freight_class = 'numeric'
      AND weight_kg IS NOT NULL
      AND weight_kg > 0
)
SELECT
    'yes_mode_rate' AS check_name,
    shipment_mode AS label,
    MAX(n) AS weighed_n,
    AVG(rate) AS mean_rate,
    AVG(CASE WHEN rn IN ((n + 1) / 2, (n + 2) / 2) THEN rate END) AS median_rate
FROM ranked
GROUP BY shipment_mode
ORDER BY shipment_mode;
