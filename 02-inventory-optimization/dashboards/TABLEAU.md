# Tableau Public extract — class A policy

Planner file: [`class_a_policy.csv`](class_a_policy.csv), one row per class A item, copied from `data/processed/policy.csv` (558 rows). Nothing was refit. `tableau` and `tabcmd` are not on this machine, and this workbook was **not** published to Tableau Public.

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

Lead time is an assumed **7 days**. The files have no lead time. There are no unit costs in this extract. Do not add a dollar field and do not claim dollar savings.

Manual Tableau Public steps (not done here): upload `class_a_policy.csv` to Tableau Public (public.tableau.com). Build four sheets: a KPI of unfilled share 3.0% (`SUM(units_short) / SUM(units_demanded)` from `policy_summary.csv` is 0.030392921231046102); a bar of `safety_stock` for the top items by `units_demanded`; a scatter of `safety_stock` vs `units_demanded`; a table of items with `fill_rate` > 0.04. Publishing that workbook is a manual upload because we cannot sign in as the user.
