# Execute — CA_3 FOODS inventory (what a planner should change)

Set the reorder point and the safety stock for each of the 558 class A items to the values already in `data/processed/policy.csv`, order seven days of that item's mean LightGBM forecast rather than an economic order quantity, and do not manage by cycle service, debias the forecast, or claim a dollar saving.

PACE stage: **Execute**. This page is the handoff, and nothing more. It recomputes no policy, changes no safety stock and runs no new simulation. Every figure below already appears in [03-construct.md](03-construct.md), [02-analyze.md](02-analyze.md), `data/processed/policy.csv` or `data/processed/policy_summary.csv`; a planner who needs the derivation should go to those files, given that this page says only what to load.

## What to set

Class A comprises **558** items and **88,230** holdout units, a unit share of **0.8030399563120051** — about 80.3% of CA_3 FOODS units on **2016-04-25 through 2016-05-22**. It is not a short list. Even the ten busiest items together reach a cumulative share of only 0.1265677619004278, which means that implementing this policy on the five names at the top of the volume ranking, and stopping there, would miss the point entirely. The file holds one row per class A item, sorted by `item_id`; class B and class C are not in it.

For each of those 558 rows, set the following:

- **Safety stock** to `safety_stock`. The total comes to **4,079** units. Of the items, **193** carry 0, while the other **365** carry a positive integer; the median is 2, the 75th percentile is 7, and the maximum, **193**, belongs to `FOODS_3_681`.
- **Reorder point** to `reorder_point`. That cell already equals expected lead-time demand plus the integer safety stock, where expected lead-time demand is the item's mean daily `lgbm` times 7. The reorder point is deliberately left unrounded.
- **Order quantity** to `order_qty`. That cell holds seven days of the item's own mean `lgbm`, expressed as the smallest whole number of units that is at least that mean week, and at least 1. It represents one lead time of supply rather than an economic order quantity, and the search never changed it. After all, there is no order cost and no holding-cost rate against which to optimize.

Review remains continuous: an order is placed whenever the inventory position, on hand plus on order, is at or under the reorder point. Lead time remains fixed at **7 days**, an assumption made necessary because the files carry neither a lead time nor any supplier history. Unmet demand remains a lost sale, and no 3-day or 14-day case should be bolted on.

The cap these integers were built to satisfy is a unit shortfall strictly under 0.05, that is, units short divided by units demanded. On the class A total, that shortfall is **2,681.5674402151976 / 88,230 = 0.030392921231046102**, so about 3.0% of units went unfilled, and the share of units sold — one minus that ratio — is **0.9696070787689539**. Precisely **0** items missed the cap. The objective that was minimized, average end-of-day on-hand, sums to **14,461.064128366881**, while half the order quantity plus safety stock sums to **14,620.5** (cycle stock **10,541.5** plus safety stock **4,079**). Those two totals are close, yet they are not the same number; moreover, neither is a dollar holding cost.

## Do not manage by cycle service

The unit cap was met. A cycle-service cap was not — but then, it was never the constraint.

Of **2,819** cycles, **601** had a stockout. That share, **601 / 2,819 = 0.21319616885420362**, comes to about 21% of cycles, nowhere near under 5%, and the share of cycles with no stockout, **0.7868038311457963**, is well short of 95%. The figure deserves less weight than it appears to carry, however. The median item has just **4** cycles, the mean is 5.051971326164875, and **295** items have four cycles or fewer; a percentage built on four cycles is, in truth, a count. Safety stock should therefore not be retuned to push that percentage to 95%. This file performs no such retune, and Construct has already shown why the two scores disagree.

The day-level stockout rate is reported alongside the cap, but it was never searched for. Out of 558 × 28 = **15,624** item-days, **722** had a shortfall, a rate of **722 / 15,624 = 0.046210957501280084**. It happens to sit under 0.05 on this window. It is not the rule.

The item closest to the unit cap is `FOODS_2_266`, with a shortfall of **0.049946516104229** — 3.046737482357969 units short out of 61 demanded. Its safety stock is 5, its order quantity 13 and its reorder point 17.95326251764203. It remains under 0.05, which makes it neither a failure nor a place to shave a unit without a fresh simulation — and this stage runs none.

## Do not debias

Use `lgbm` exactly as it stands. Across the whole holdout file, the forecast runs high, with a bias share of units of 0.025708572879134136. On class A, however, it runs low, by **-5,020.5579692516685** units, a bias share of **-0.05690307116912239**, or about 5.7% of class A units. The safety stocks were searched against that low forecast rather than against a corrected mean, which means subtracting the bias before ordering would amount to a different policy altogether — one this stage does not build.

`FOODS_3_681` illustrates the point. Its `lgbm` summed to 919.1858923452189 against 1,253 actual, a gap of 333.8141076547811 units, yet its safety stock is **193**, not that gap. Its reorder point is 422.7964730863048 and its order quantity 230. The 193 is simply the smallest integer that brought this item's shortfall under 0.05, to 0.04964367670685971. Note that the forecast mean itself was never adjusted.

## Do not claim dollars

There is still no unit cost, no holding-cost rate and no order cost; `sell_price` was not used, and no supplier appears anywhere in this result. An average on-hand of 14,461.064128366881 and textbook units held of 14,620.5 are units on a 28-day window, nothing more. Dollar savings will not be claimed.

## The opening inventory limits the claim

No on-hand history exists, and none was invented from the month before the holdout.

On the morning of **2016-04-25**, on-hand is set equal to the reorder point and on-order to zero before the first review. Given that the position already sits at the reorder point, every class A item places an order that morning. The first receipt arrives on the morning of **2016-05-02**, so the first week is covered by the opening balance alone. The shelf, in other words, does not start empty; neither, however, does it start from a counted position. This is the pivotal limitation of the result. A different opening balance would change both the shortfall and the average on-hand, and other openings were not tried. The 0.030392921231046102 unfilled share is therefore the score of this start on this one window — not proof that CA_3 would have missed 3% of units in April 2016, and still less proof for a holiday quarter.

## What to watch

The search kept the smallest feasible integer on every item; `n_items_chosen_above_min_ss` is **0**. Where a shortfall sits well under 5%, either safety stock 0 already cleared the cap or the last unit crossed from a miss to a much smaller shortfall. The bulk of the remaining items, by contrast, sits close to the cap: the median item shortfall is **0.038070671837693734**, and among items with a positive safety stock it is **0.04308352428601003**. Trimming a unit off those rows in the name of leaner inventory would be a mistake. On `FOODS_3_090`, safety stock 38 yields a shortfall of **0.04978097330842364**, whereas safety stock 37 yields **0.05007885832480732** and fails the strict cap. The objective would have taken 37 had 37 been feasible. It was not, and the 38 stands.

Volume does not dictate the buffer. The same five names that Analyze listed, read here from `policy.csv`, make that plain:

| Item | Units demanded | Order quantity | Safety stock | Reorder point | Unit shortfall |
|---|---:|---:|---:|---:|---:|
| FOODS_3_090 | 3,357 | 713 | 38 | 750.8852726036218 | 0.04978097330842364 |
| FOODS_3_586 | 1,883 | 474 | 0 | 473.8546930978276 | 0.010698516676671493 |
| FOODS_3_120 | 1,617 | 435 | 0 | 434.0506172848497 | 0.04016659413429209 |
| FOODS_3_252 | 1,405 | 272 | 71 | 342.45635833336723 | 0.049497253855254636 |
| FOODS_3_681 | 1,253 | 230 | 193 | 422.7964730863048 | 0.04964367670685971 |

`FOODS_3_586` is the second-busiest item, yet its safety stock is 0. `FOODS_3_681` ranks fifth, and its safety stock of 193 is the largest buffer in the file — because the forecast on that item runs low. That row deserves watching. A planner who "corrects" the forecast while keeping 193 would be buffering twice; a planner who drops 193 because the item is not the busiest would push the shortfall back over the cap. Neither change belongs to this handoff.

`FOODS_3_090` serves as the worked example in `reports/03-construct-solver.xlsx`. Its mean daily `lgbm` is 101.84075322908883, its expected lead-time demand 712.8852726036218, its order quantity 713, its safety stock 38 and its reorder point 750.8852726036218. The first seven days of actual sales sum to 904, so the item stocks out before the first receipt even with safety stock 38. That is the opening-balance limit revealing itself on the busiest item — not a reason to invent a larger buffer in this file.

## What this stage does not do

This stage runs no new simulation and changes no safety stock, reorder point or order quantity. It does not debias the forecast, and it sets no class B or class C policy. It computes no EOQ and no dollar cost; dollar savings will not be claimed. It tests no 3-day or 14-day lead time and draws on no supplier file. Nor does it claim that cycle service is 95%. It is 0.7868038311457963.

Excel Solver was not run, and no Solver answer was invented. The integers are the Python enumeration from Construct, written into `reports/03-construct-solver.xlsx` so that the sheet matches `policy.csv`; this stage does not open Solver.

## Dashboard

The dashboard file is [dashboards/class_a_policy_dashboard.html](../dashboards/class_a_policy_dashboard.html), with the planner extract at [dashboards/class_a_policy.csv](../dashboards/class_a_policy.csv). Publishing to Tableau Public remains a manual upload, since only the account owner can sign in.

The one-page version is [executive-summary.md](executive-summary.md), and the longer story is [business-report.md](business-report.md). The scores and the simulation rules are set out in [03-construct.md](03-construct.md). The policy is ready to load; what it needs now is not a better number on this window, but a second window and a real lead time to test it against.
