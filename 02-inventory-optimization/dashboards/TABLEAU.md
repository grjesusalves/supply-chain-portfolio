# Tableau Public extract — class A policy

The planner file, [`class_a_policy.csv`](class_a_policy.csv), holds one row for each class A item and is copied directly from `data/processed/policy.csv`, all 558 rows of it. Nothing was refit along the way. That said, neither `tableau` nor `tabcmd` is installed on this machine, which means this workbook was **not** published to Tableau Public — a gap worth stating before anyone goes looking for the link.

| Column | Meaning |
|---|---|
| `item_id` | Class A food item at CA_3. |
| `units_demanded` | Holdout units demanded, 2016-04-25 through 2016-05-22. |
| `order_qty` | Order quantity: seven days of that item's mean LightGBM forecast, in whole units. Not an economic order quantity. |
| `safety_stock` | Integer safety stock already chosen in `policy.csv`. |
| `reorder_point` | Expected lead-time demand plus `safety_stock`. Not rounded to a whole unit. |
| `units_short` | Units unfilled on the holdout. Can be fractional. |
| `fill_rate` | **Unfilled share**: `units_short` / `units_demanded`. This is not the share of units sold. The cap is strictly under 0.05. |
| `units_filled_share` | `1 - fill_rate`. Share of units filled. |
| `days_stocked_out` | Days in the 28-day window with a shortfall above zero. |
| `cycles` | Replenishment cycles in the window. |
| `cycles_with_stockout` | Cycles that contain a stockout day. |
| `avg_on_hand` | Mean end-of-day on-hand over the 28 days, in units. |

Lead time is an assumed **7 days**, given that the files contain no lead time at all. Moreover, the extract carries no unit costs; a dollar field should not be bolted on afterwards, and dollar savings should not be claimed on the strength of a file that never measured them.

The remaining Tableau Public steps were not done here, and they are short. The first is to upload `class_a_policy.csv` to Tableau Public (public.tableau.com). The second is to build four sheets: a KPI showing the unfilled share of 3.0%, where `SUM(units_short) / SUM(units_demanded)` from `policy_summary.csv` comes to 0.030392921231046102; a bar chart of `safety_stock` for the top items by `units_demanded`; a scatter of `safety_stock` against `units_demanded`; and a table of the items whose `fill_rate` is > 0.04. Publishing that workbook remains a manual upload, since no one but the account owner can sign in to it — which means the extract is ready, and the last step belongs to the owner.
