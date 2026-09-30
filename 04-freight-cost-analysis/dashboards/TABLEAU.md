# Tableau Public extract — weighed shipments

Planner file: [`shipment_weighed.csv`](shipment_weighed.csv), one row per weighed `ASN/DN #`, from the Yes-line rollup (6,174 rows). Nothing was refit. `tableau` and `tabcmd` are not on this machine, and this workbook was **not** published to Tableau Public. There is no public URL.

The file is the weighed set only. Yes-line freight is a plain decimal and Yes-line weight is a plain decimal greater than zero. Included-in-price (593 shipments), invoiced separately (239), weight captured separately (23), and `ASN-22365` (weight 0) are not in this file and are not zeros. A low rate on this extract is not a cheap INCO term. Insurance and manufacturing site are not columns. There is no savings field. Do not add one.

| Column | Meaning |
|---|---|
| `asn_dn` | Shipment id. One row per note. |
| `shipment_mode` | Air, Air Charter, Ocean, Truck, or `(blank)`. Blank is a null, not a mode. |
| `country` | Destination country. Constant on the note. |
| `vendor` | Vendor. Constant on the note. |
| `vendor_inco_term` | Vendor INCO term. Constant on the note. |
| `weight_kg` | Yes-line weight, kilograms, greater than 0. |
| `freight_usd` | Yes-line freight, USD. Not summed across lines. |
| `freight_per_kg` | `freight_usd` / `weight_kg`. The headline measure. |
| `line_item_value_sum` | Sum of line-item value on the note. Not a freight figure. |
| `in_regression_sample` | 1 if the mode is named (5,963 rows). 0 if the mode is `(blank)` (211 rows). |

Story: on the shipments where freight and weight were both real numbers, the median rate is 7.263901636359817 USD per kg (mean 38.93012311964861, pulled by a heavy tail). Air's median is higher than ocean or truck before any control. Heavier shipments have a lower rate per kilogram. Orgenics, Ltd stays high inside air. Blank mode is not a mode. None of that is a dollar saving. The regression that holds weight and INCO term is in [`../reports/03-construct.md`](../reports/03-construct.md), not in this workbook.

Sheets to build:

1. A KPI of **median** `freight_per_kg` on all 6,174 rows, with the count beside it. Put the mean next to it and label the mean as the tail, not as the typical shipment. The check values from this run are median 7.263901636359817 and mean 38.93012311964861.
2. A bar of median `freight_per_kg` by `shipment_mode`, with the shipment count on the label. Keep `(blank)` visible and title it as not a mode. Do not sort this bar by total `freight_usd`. A large dollar total is not a high rate.
3. A scatter of `weight_kg` against `freight_per_kg`, colored by `shipment_mode`, on logarithmic axes if the marks allow it. This is the "the rate falls as the shipment gets heavier" sheet. The 4 kg charter will sit far out. Do not drop it silently. A filter for `freight_per_kg` at or below 67.64871004566209 (the weighed-set 95th percentile) can show the body.
4. A bar of median `freight_per_kg` for `vendor` = `Orgenics, Ltd` against every other vendor, with the view filtered to `shipment_mode` = Air, and the counts on the marks. That is the scorecard comparison. It is not a savings number.

Filters: `shipment_mode`, `country`, `vendor`, `vendor_inco_term`, and `in_regression_sample`. Use `in_regression_sample` = 1 when the sheet is supposed to match the regression sample of 5,963. Leave it at all values when the sheet is the weighed set.

Do not build a savings sheet, a manufacturing-site sheet, or an insurance sheet. Do not make total freight dollars the headline.

Manual Tableau Public steps (not done here): upload `shipment_weighed.csv` to Tableau Public (public.tableau.com) and build the four sheets above. Publishing that workbook is a manual upload because we cannot sign in as the user. The publish belongs to Execute.
