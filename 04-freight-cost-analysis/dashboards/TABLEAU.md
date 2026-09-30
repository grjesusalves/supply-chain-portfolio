# Tableau Public extract — weighed shipments

Planner file: [`shipment_weighed.csv`](shipment_weighed.csv), one row per weighed `ASN/DN #`, from the Yes-line rollup. Execute checked this file against that rollup. **6,174** rows. The file was not rewritten. `tableau` and `tabcmd` are not how this stage publishes, and this workbook was **not** published to Tableau Public. There is no public URL. Publishing is a manual step the user still has to do.

The file is the weighed set only. Yes-line freight is a plain decimal and Yes-line weight is a plain decimal greater than zero. Included-in-price (593 shipments), invoiced separately (239), weight captured separately (23), and `ASN-22365` (weight 0) are not in this file and are not zeros. A low rate on this extract is not a cheap INCO term. Insurance and manufacturing site are not columns. There is no savings column. Do not add one. The dollar what-if is computed in `src/execute_freight.py` and written under `data/processed/execute_scenario_*.csv`. Summing a counterfactual on this extract would look like an invoice, and it would not match the scenario unless the filter is exactly the one below.

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

Story, after Execute. On the shipments where freight and weight were both real numbers, the median rate is 7.263901636359817 USD per kg (mean 38.93012311964861, pulled by a heavy tail, maximum 31087.705 on a 4 kg air charter). Air's median is higher than ocean or truck before any control. Heavier shipments have a lower rate per kilogram. Orgenics, Ltd stays high inside air. Blank mode is not a mode. No country keeps an uncontrolled lead. Charter looks cheap on the median until weight is held constant, and the about-66-percent log gap is not a planning factor; the cautious figure after the p95 cut is about 21 percent, and it is still not dollars saved. Ocean's cheap median is tangled with DDP. The only dollar figure is a what-if in the reports: weighed air at or above 1054.5 kg (the weighed-set median weight), compared with the observed truck median on that same slice (1.5292046183450931), only where the air rate is higher. That gap is an upper bound, not money that was saved. The regression that holds weight and INCO term is in [`../reports/03-construct.md`](../reports/03-construct.md). The what-if is in [`../reports/04-execute.md`](../reports/04-execute.md).

Sheets a public workbook should have:

1. A KPI of **median** `freight_per_kg` on all 6,174 rows, with the count beside it. Put the mean next to it and label the mean as the tail, not as the typical shipment. The check values from the Execute run are median 7.263901636359817 and mean 38.93012311964861.
2. A bar of median `freight_per_kg` by `shipment_mode`, with the shipment count on the label. Keep `(blank)` visible and title it as not a mode. Do not sort this bar by total `freight_usd`. A large dollar total is not a high rate.
3. A scatter of `weight_kg` against `freight_per_kg`, colored by `shipment_mode`, on logarithmic axes if the marks allow it. This is the "the rate falls as the shipment gets heavier" sheet. The 4 kg charter will sit far out. Do not drop it silently. A filter for `freight_per_kg` at or below 67.64871004566209 (the weighed-set 95th percentile) can show the body. Title the unfiltered view so a reader does not treat the charter tail as the typical rate.
4. A bar of median `freight_per_kg` for `vendor` = `Orgenics, Ltd` against every other vendor, with the view filtered to `shipment_mode` = Air, and the counts on the marks. That is the scorecard comparison. It is not a savings number.
5. Do not build a savings sheet. To see the scenario population only, filter `shipment_mode` = Air and `weight_kg` ≥ 1054.5. That filter is 1,664 notes. The dollar gap uses 1,477 of them, the ones whose rate is above 1.5292046183450931, and it lives in the Python output, not in a calculated field. Do not subtract the truck median from every mark and sum it.

Filters: `shipment_mode`, `country`, `vendor`, `vendor_inco_term`, and `in_regression_sample`. Use `in_regression_sample` = 1 when the sheet is supposed to match the regression sample of 5,963. Leave it at all values when the sheet is the weighed set.

Do not build a manufacturing-site sheet or an insurance sheet. Do not make total freight dollars the headline.

Manual Tableau Public step (not done here): upload `shipment_weighed.csv` to Tableau Public (public.tableau.com) and build the sheets above. Publishing is a manual step the user still has to do. This stage did not log in and did not publish. There is no public URL.
