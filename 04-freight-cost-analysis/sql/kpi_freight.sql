-- Freight text checks. SQLite-compatible. Read-only SELECTs after one view.
--
-- Table: delivery_lines, one row per line from SCMS_Delivery_History_Dataset.csv
-- (Latin-1, 10,324 lines, 33 columns). This file does not load the CSV and
-- does not create a database. src/analyze_freight.py reads the CSV, builds
-- the same classes, and executes this file against an in-memory table of
-- those lines. The raw CSV stays git-ignored.
--
-- Grain: the row is a line item. The shipment id is "ASN/DN #".
-- Money was going to be one figure per ASN/DN. That rollup is not in this
-- file. Freight Cost (USD) is not the same string on every line of 1,299
-- shipments, and Weight (Kilograms) is not the same string on every line of
-- 1,322 shipments. The plan says not to average conflicting freight strings
-- and not to invent a replacement rule here. There is no median freight per
-- kilogram, no mean, and no GROUP BY mode / country / vendor rate.
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
-- freight strings. Pointers count as a different string. This is why the
-- rate queries are absent.
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
