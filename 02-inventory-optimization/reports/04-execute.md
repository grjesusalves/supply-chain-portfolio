# Execute — CA_3 FOODS inventory (what a planner should change)

Set the reorder point and the safety stock for each of the 558 class A items to the values already in `data/processed/policy.csv`, order seven days of that item's mean LightGBM forecast rather than an economic order quantity, and do not manage by cycle service, debias the forecast, or claim a dollar saving.

PACE stage: **Execute**. This is the handoff. It does not recompute a policy, it does not change a safety stock, and it does not run a new simulation. Every figure below is already in [03-construct.md](03-construct.md), [02-analyze.md](02-analyze.md), `data/processed/policy.csv`, or `data/processed/policy_summary.csv`. If a planner needs the derivation, those files are the source. This page only says what to load.

## What to set

Class A is **558** items and **88,230** holdout units, a unit share of **0.8030399563120051**. That is about 80.3% of CA_3 FOODS units on **2016-04-25 through 2016-05-22**. It is not a short list. The ten busiest items are still only a cumulative share of 0.1265677619004278. Do not implement this policy on the five names at the top of the volume ranking and stop there. The file has one row per class A item, sorted by `item_id`. Class B and class C are not in it.

For each of those 558 rows, set:

- **Safety stock** to `safety_stock`. The total is **4,079** units. **193** items are 0. The other **365** are a positive integer. The median is 2. The 75th percentile is 7. The maximum is **193**, on `FOODS_3_681`.
- **Reorder point** to `reorder_point`. That cell is already expected lead-time demand plus the integer safety stock. Expected lead-time demand is the item's mean daily `lgbm` times 7. The reorder point is not rounded to a whole unit.
- **Order quantity** to `order_qty`. That cell is seven days of the item's own mean `lgbm`, the smallest whole number of units at least that mean week, and at least 1. It is one lead time of supply. It is not an economic order quantity. The search did not change it. There is no order cost and no holding-cost rate to optimize against.

Review stays continuous: order when the inventory position (on hand plus on order) is at or under the reorder point. Lead time stays **7 days**, fixed. That lead time is an assumption. The files have no lead time and no supplier history. Unmet demand stays lost sales. Do not add a 3-day or 14-day case.

The cap these integers were built for is a unit shortfall strictly under 0.05: units short divided by units demanded. On the class A total that shortfall is **2,681.5674402151976 / 88,230 = 0.030392921231046102**. About 3.0% of units went unfilled. The share of units sold is one minus that ratio, **0.9696070787689539**. **0** items missed the cap. The objective that was minimized, average end-of-day on-hand, sums to **14,461.064128366881**. Half the order quantity plus safety stock sums to **14,620.5** (cycle stock **10,541.5** plus safety stock **4,079**). Those two totals are close and they are not the same number. Neither one is a dollar holding cost.

## Do not manage by cycle service

The unit cap was met. A cycle-service cap was not, and it was not the constraint.

**601** of **2,819** cycles had a stockout. That share is **601 / 2,819 = 0.21319616885420362**, about 21% of cycles, not under 5%. The share of cycles with no stockout is **0.7868038311457963**. That is not 95%. The median item has **4** cycles. The mean is 5.051971326164875. **295** items have four cycles or fewer. A percentage built on four cycles is a count. Do not retune safety stock to push that percentage to 95%. This file does not do that retune, and Construct already showed why the two scores disagree.

The day-level stockout rate is reported beside the cap and was not searched for. **722** item-days had a shortfall, out of 558 × 28 = **15,624**, a rate of **722 / 15,624 = 0.046210957501280084**. It happens to sit under 0.05 on this window. It is not the rule.

The item closest to the unit cap is `FOODS_2_266`, shortfall **0.049946516104229** (3.046737482357969 units short out of 61 demanded). Its safety stock is 5, its order quantity is 13, and its reorder point is 17.95326251764203. It is still under 0.05. It is not a failure, and it is not a place to shave a unit without a new simulation. This stage does not run one.

## Do not debias

Use `lgbm` as-is. On the whole holdout file the forecast is high, a bias share of units of 0.025708572879134136. On class A it is low: **-5,020.5579692516685** units, a bias share of **-0.05690307116912239**, about 5.7% of class A units. The safety stocks were searched against that low forecast. They were not given a corrected mean. Subtracting the bias before ordering would be a different policy. This stage does not build it.

`FOODS_3_681` is the illustration. Its `lgbm` summed to 919.1858923452189 against 1,253 actual, a gap of 333.8141076547811 units. Safety stock is **193**, not that gap. The reorder point is 422.7964730863048 and the order quantity is 230. The 193 is the smallest integer that brought this item's shortfall under 0.05 (the shortfall is 0.04964367670685971). The forecast mean was not adjusted.

## Do not claim dollars

There is still no unit cost, no holding-cost rate, and no order cost. `sell_price` was not used. There is no supplier in this result. Average on-hand of 14,461.064128366881 and textbook units held of 14,620.5 are units on a 28-day window. Dollar savings will not be claimed.

## The opening inventory limits the claim

There is no on-hand history, and none was invented from the month before the holdout.

On the morning of **2016-04-25**, on-hand equals the reorder point and on-order is zero before the first review. The position is already at the reorder point, so every class A item orders that morning. The first receipt is the morning of **2016-05-02**. The first week is covered only by the opening balance. The shelf does not start empty, and it does not start from a counted position. A different opening balance would change both the shortfall and the average on-hand. Other openings were not tried. The 0.030392921231046102 unfilled share is the score of this start, on this one window, not a proof that CA_3 would have missed 3% of units in April 2016, and not a proof for a holiday quarter.

## What to watch

The search kept the smallest feasible integer on every item. `n_items_chosen_above_min_ss` is **0**. Where a shortfall sits well under 5%, safety stock 0 already cleared the cap, or the last unit crossed from a miss to a much smaller shortfall. The mass of the other items sits near the cap. The median item shortfall is **0.038070671837693734**. Among items with a positive safety stock the median shortfall is **0.04308352428601003**. Do not trim a unit off those rows in the name of less inventory. On `FOODS_3_090`, safety stock 38 has shortfall **0.04978097330842364** and safety stock 37 has shortfall **0.05007885832480732**, which fails the strict cap. The objective would have taken 37 if 37 had been feasible. It was not. I am not changing 38.

Volume is not the buffer. The same five names Analyze listed, read from `policy.csv`:

| Item | Units demanded | Order quantity | Safety stock | Reorder point | Unit shortfall |
|---|---:|---:|---:|---:|---:|
| FOODS_3_090 | 3,357 | 713 | 38 | 750.8852726036218 | 0.04978097330842364 |
| FOODS_3_586 | 1,883 | 474 | 0 | 473.8546930978276 | 0.010698516676671493 |
| FOODS_3_120 | 1,617 | 435 | 0 | 434.0506172848497 | 0.04016659413429209 |
| FOODS_3_252 | 1,405 | 272 | 71 | 342.45635833336723 | 0.049497253855254636 |
| FOODS_3_681 | 1,253 | 230 | 193 | 422.7964730863048 | 0.04964367670685971 |

`FOODS_3_586` is the second-busiest item and its safety stock is 0. `FOODS_3_681` is fifth and its safety stock is 193, the largest buffer in the file, because the forecast on that item is low. Watch that row. A planner who "corrects" the forecast and also keeps 193 would be buffering twice. A planner who drops 193 because the item is not the busiest would put the shortfall back over the cap. Neither change is this handoff.

`FOODS_3_090` is the worked example in `reports/03-construct-solver.xlsx`. Mean daily `lgbm` is 101.84075322908883, expected lead-time demand is 712.8852726036218, order quantity 713, safety stock 38, reorder point 750.8852726036218. The first seven days of actual sum to 904, so the item stocks out before the first receipt even with safety stock 38. That is the opening-balance limit on the busiest item, not a reason to invent a larger buffer in this file.

## What this stage does not do

No new simulation. No change to safety stock, reorder point, or order quantity. No debiasing. No class B or class C policy. No EOQ. No dollar cost. Dollar savings will not be claimed. No 3-day or 14-day lead time. No supplier file. No claim that cycle service is 95%. It is 0.7868038311457963.

Excel Solver was not run. No Solver answer was invented. The integers are the Python enumeration from Construct, written into `reports/03-construct-solver.xlsx` so the sheet matches `policy.csv`. This stage does not open Solver.

No dashboard yet. The chart already in Construct is [images/class_a_safety_stock.png](../images/class_a_safety_stock.png). A dashboard is a later stage. None was built here.

The one-page version is [executive-summary.md](executive-summary.md). The longer story is [business-report.md](business-report.md). The scores and the simulation rules are [03-construct.md](03-construct.md).
