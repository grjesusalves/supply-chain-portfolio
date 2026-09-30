# Construct — CA_3 FOODS inventory (reorder point and safety stock)

PACE stage: **Construct**. This file builds the reorder point and the safety stock the plan already defined, and it scores them on the holdout. It does not reopen the ten decisions at the end of [01-plan.md](01-plan.md). Class A is the 558 items from [02-analyze.md](02-analyze.md). The forecast is not refit and it is not debiased. The project README is still the template. This file does not fill it.

The path through the page is: the simulation, the safety-stock search, the class A totals, and the one item a person can open in the workbook.

## What was counted

The demand file is the same one Analyze used: `01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv`. The class cut is recomputed with the Analyze functions, not retyped from the class file. Class A is **558** items and **88,230** holdout units. The days are **2016-04-25 through 2016-05-22**.

Signed error is still **`lgbm` minus `actual`**. On class A that bias is **-5,020.5579692516685** units, a share of units of **-0.05690307116912239**. The forecast on these items is low. That number is reproduced here so the reorder point is not built on a different error. It is not subtracted from `lgbm`. The plan's decision stands: use the forecast as-is.

`sell_price` was not opened. There is still no unit cost, no holding-cost rate, and no order cost. The objective stays in units. Dollar savings will not be claimed.

## What the columns mean

`fill_rate` in `data/processed/policy.csv` is **units short divided by units demanded**. The cap is that ratio **strictly under 0.05**. An exact 0.05 would fail. This is the unfilled share. It is how the plan defined a unit fill rate under 5%. It is not the fraction of units that were sold. The fraction sold is one minus this ratio.

A day counts as stocked out when that day's units short are above zero. A **cycle** is one day on which one or more lots were ordered. The cycle runs from that day through the day before the next order, or through 2016-05-22 if it is the last order. A stockout on the order day counts, because the order placed that day arrives seven days later. `cycles_with_stockout` is how many of those cycles contain a stockout day.

`avg_on_hand` is the mean of end-of-day on-hand over the 28 days, after demand and lost sales. `cycle_stock_units` is the order quantity divided by two. That is the textbook half-batch. It is not the objective.

## How a day runs

Lead time is **7 days**, fixed, an assumption. The files have no lead time and no lead-time variability. An order placed on day t is available at the start of day t+7, before that morning's review and before that day's demand. It cannot serve the day it was ordered. A receipt moves units from on-order to on-hand. The inventory position does not change when a receipt lands. The position is on-hand plus on-order. Unmet demand is lost. It is not subtracted as a backorder, and it does not deepen the position.

Review is continuous inside the day, in two looks, because the data are daily.

1. In the morning, before demand, if the position is at or under the reorder point, order the smallest number of lots that puts the position strictly above the reorder point. One lot when the position equals the reorder point. A second lot when one lot would land exactly on the reorder point, because the rule orders at `<=`.
2. Demand is the day's `actual`. Sales are the minimum of on-hand and actual. On-hand does not go negative.
3. After demand, if the position is back at or under the reorder point, order more lots the same day. Those lots also arrive on day t+7. They do not refill units already lost.

Across class A, **136** item-days placed more than one lot. The second look is not unused. Most order days are still one lot.

## Starting inventory

There is no on-hand history. None was invented from a month before the holdout.

On the morning of **2016-04-25**, on-hand equals the reorder point and on-order is zero. The first review is that same morning. The position is already at the reorder point, so the first order is placed before any holdout demand. After that order, on-order is no longer zero. The opening sentence "on-order none" is the balance before the review, not a refusal to order on day 0. Every class A item orders on day 0. The first receipt is the morning of **2016-05-02**.

The window is 28 days. That start is part of the result. The shelf begins at the reorder point, not empty, and the first week is covered only by that opening balance. A different opening balance would change both the shortfall and the average on-hand. I did not try other openings.

## Order quantity and expected lead-time demand

For each item, `mean_daily_lgbm` is the mean of that item's 28 `lgbm` values. Expected lead-time demand is that mean times 7. The forecast changes by day, so this is the mean day times the lead time. It is not the sum of one particular week, and it is not `actual`.

The order quantity is the smallest whole number of units that is at least that expected lead-time demand, and at least 1. `math.ceil` on a positive number, which is Excel `ROUNDUP(x, 0)`. An exact integer stays that integer. It is not an EOQ. The search does not change it.

The reorder point is expected lead-time demand plus the integer safety stock. It is not rounded. On-hand can sit on a fraction of a unit because the forecast mean is not an integer. Units short can therefore be fractional when the shelf is holding a fraction and the day's demand is larger. The cap is applied to that ratio.

## Safety stock

Safety stock is an integer number of units, chosen separately for each item. Two calculations are on the page so the search is not a black box. Neither one is the policy.

The scale is the item's own 28-day sample standard deviation of daily (`lgbm` − `actual`), the same `daily_error_std` as Analyze, times the square root of 7. That is the usual independent-days lead-time sigma. The plan said not to treat that product as the policy by itself, and it is not.

Four non-overlapping 7-day blocks are not a per-item sigma. Each item has four block errors. A sample standard deviation of four points is not stable, and I did not pretend that it was. What I did compute is the ratio of that four-point standard deviation to the independent-days scale. The median ratio is **1.0005069444077974**. The mean ratio is **1.0620523240049689**. The 25th and 75th percentiles are **0.7162315258311641** and **1.328711418890887**. The median item's four-block width and the square-root-of-7 scale are the same size. The spread of the ratio is the noise of four points.

The mean of the block variances divided by the mean of (daily variance times 7) is **2.2010449293279675**. That ratio is not a factor I applied. It is pulled by items whose four weeks are much wider than their daily noise. Scaling every item by 2.2 would pad the typical item because of that tail. Those wide items get whatever integer the simulation needs. The others are not scaled up to match them.

Lag correlations of the daily error, averaged across the 558 items, are near zero: lag 1 is **0.031181120390307154**, then **0.0030323280216445502**, **-0.021846458696928986**, **-0.004837583353715764**, **0.004856937716273669**, **-0.017346099121796823**, and **0.015922062872085828** at lag 7. The median lag-1 correlation is **0.016914040466102682**. Adjacent days are weakly dependent. That supports the square root of 7 as a description of a typical item's scale. It does not make the scale the reorder-point policy. The cap is a simulated unit shortfall, not a normal quantile.

The candidate that uses the scale is the normal loss, and it is rejected wherever the simulation says so. Let σ_L be the daily error standard deviation times the square root of 7. The standard normal loss is n(z) = φ(z) − z(1 − Φ(z)). The textbook backorder identity sets n(z) = 0.05 × order quantity / σ_L, and safety stock = z × σ_L. I solved z by bisection. If z is not positive, the candidate is 0. If z is positive, the candidate is that product, ceiled to an integer. The formula assumes a normal lead-time demand, an unbiased forecast, backorders, and a long run of cycles. This holdout is none of those. Class A `lgbm` is low, unmet demand is lost, and a typical item has a handful of cycles.

That candidate was simulated anyway, so the miss is a count and not a suspicion. On **186** items the candidate's unit shortfall was not under 0.05. On those 186 the search used a higher safety stock. On **314** items the search used a lower safety stock than the candidate. On **58** items they are the same integer. 186 + 314 + 58 = 558. The sum of the candidate safety stocks is **3,012**. The sum of the safety stocks actually used is **4,079**. The median candidate is 4 units. The median policy is 2. The formula under-buffers the items the low forecast hurts, and it over-buffers a larger number of smaller misses. The cap is per item, so the over-buffered items do not repair the 186 misses. That is why the candidate is not the policy.

For the example item the candidate z is **-0.16203597071870773**, so the candidate safety stock is 0. The order quantity is large next to σ_L, and the formula thinks no buffer is required. The simulation of that zero is a shortfall of **0.16327516455060415**. The search raises it. The forecast mean is not adjusted before that test.

## The search

For each item, safety stock runs through the integers 0, 1, 2, and so on, up to a bound that cannot stock out on this finite series: opening on-hand at least the sum of the item's actual demand. The bound is only a bound. It is not a recommended buffer.

A value is feasible when units short / units demanded is strictly under 0.05. The objective is average end-of-day on-hand. The feasible value with the lowest average on-hand is kept. A tie closer than 1e-8 breaks toward the smaller safety stock, so a tie does not add a unit.

On all 558 items the lowest average on-hand was the smallest feasible integer. `n_items_chosen_above_min_ss` is **0**. The search did not keep an extra unit past the cap. Where the shortfall sits well under 5%, it is because safety stock 0 already cleared the cap, or because the last unit crossed from a miss to a much smaller shortfall. It is not because a larger buffer was preferred.

## Class A totals

The row is `data/processed/policy_summary.csv`. Item rows are `data/processed/policy.csv`, sorted by `item_id`.

| | Class A |
|---|---:|
| Items | 558 |
| Units demanded | 88,230 |
| Units short | 2,681.5674402151976 |
| Unit shortfall (`fill_rate`) | 0.030392921231046102 |
| Total average on-hand | 14,461.064128366881 |
| Total safety stock | 4,079 |
| Total cycle stock (order quantity / 2) | 10,541.5 |
| Textbook units held (cycle stock + safety stock) | 14,620.5 |
| Items missing the cap | 0 |
| Items with safety stock 0 | 193 |

The shortfall is 2,681.5674402151976 / 88,230 = 0.030392921231046102. That is the cap metric, and it is under 0.05. One minus that shortfall is 0.9696070787689539, the share of units sold. No class A item missed the cap. The highest item shortfall is **0.049946516104229**, on `FOODS_2_266`, which is still under 0.05.

The objective that was minimized, item by item, sums to **14,461.064128366881** units of average on-hand. The textbook expression, half the order quantity plus safety stock, sums to **14,620.5**. They are close on this window and they are not the same number. The search used the simulation. The textbook expression is reported so the difference is visible. Neither number is a dollar holding cost.

**193** items clear the cap at safety stock 0. The other **365** need a positive integer. **114** items have a shortfall of exactly 0. Six of those have a positive safety stock: the last unit removed every stockout, which is a step in a discrete search, not a padded buffer. The median safety stock is 2. The 75th percentile is 7. The maximum is **193**, on `FOODS_3_681`, not on the busiest item. The median item shortfall is **0.038070671837693734**. Among items with a positive safety stock the median shortfall is **0.04308352428601003**. The mass sits near the cap. The unweighted mean of the item shortfalls is **0.029163436585459158**, pulled down by the zeros.

The same five names Analyze listed, read from `policy.csv`, show that the buffer is not a volume ranking.

| Item | Units demanded | Order quantity | Safety stock | Reorder point | Unit shortfall |
|---|---:|---:|---:|---:|---:|
| FOODS_3_090 | 3,357 | 713 | 38 | 750.8852726036218 | 0.04978097330842364 |
| FOODS_3_586 | 1,883 | 474 | 0 | 473.8546930978276 | 0.010698516676671493 |
| FOODS_3_120 | 1,617 | 435 | 0 | 434.0506172848497 | 0.04016659413429209 |
| FOODS_3_252 | 1,405 | 272 | 71 | 342.45635833336723 | 0.049497253855254636 |
| FOODS_3_681 | 1,253 | 230 | 193 | 422.7964730863048 | 0.04964367670685971 |

`FOODS_3_586` is the second-busiest item and its safety stock is 0. `FOODS_3_681` is fifth and its safety stock is 193. `FOODS_3_681`'s `lgbm` summed to 919.1858923452189 against 1,253 actual, a gap of 333.8141076547811 units. The reorder point was not given that gap as a debiased mean. The simulation put 193 units on the safety stock because that is the only decision the search is allowed to change, and 193 is the smallest integer that brings this item's shortfall under 0.05.

![Safety stock and the unit shortfall](../images/class_a_safety_stock.png)

The left panel is the unit shortfall at the chosen safety stock. The dashed line is 0.05. The bar at zero is the items that never stocked out. The rest piles up against the cap, which is what a search that stops at the first feasible integer looks like. The right panel is safety stock against holdout units. The labeled points are `FOODS_3_090` and `FOODS_3_681`. A bigger item is not a bigger buffer.

## What was reported beside the cap

The cap is the unit shortfall. These two are not substitutes, and one of them does not clear 5%.

Day-level stockout rate: **722** item-days had a shortfall, out of 558 × 28 = 15,624. That rate is 722 / 15,624 = **0.046210957501280084**. It is under 0.05 on this window. It was not the constraint. I did not search for it.

Cycle stockout share: **601** cycles had a stockout, out of **2,819** cycles. That share is 601 / 2,819 = **0.21319616885420362**. It is not under 0.05. The textbook cycle service level, the share of cycles with no stockout, is **0.7868038311457963**. That is not 95%. A policy that meets the unit cap on this file does not meet a 5% cycle-stockout cap. The plan said not to swap them. This is the case it was warning about.

The window cannot show a stable cycle service. The median item has **4** cycles. The mean is **5.051971326164875**. The minimum is **1** (one item) and the maximum is **27**. **295** items have four cycles or fewer. A share built on four cycles is a count. It is still reported. The cap that was enforced is the unit shortfall.

## FOODS_3_090

This is the busiest class A item and the live sheet in the workbook. From `policy.csv`: mean daily `lgbm` **101.84075322908883**, expected lead-time demand **712.8852726036218**, order quantity **713**, safety stock **38**, reorder point **750.8852726036218**, units short **167.11472739637816**, units demanded **3,357**, shortfall **0.04978097330842364**, days stocked out **3**, cycles **5**, cycles with a stockout **2**, average on-hand **345.9080843935039**, cycle stock **356.5**.

The item's `lgbm` sums to 2,851.5410904144874. Actual is 3,357. The forecast is low by 505.45890958551263 units over the 28 days. Safety stock is 38, not 505. The mean was not corrected. When the position hits the reorder point, another lot of 713 goes on order. That pipeline is what replaces units. The 38 is the extra on the reorder point that the cap required on top of that rule.

The opening on-hand is the reorder point, 750.8852726036218. The first receipt is 2016-05-02. The first seven days of actual sum to **904**. The opening balance does not cover 904, so the item stocks out before the first receipt even with safety stock 38. Those seven `lgbm` values sum to 733.7686219100218, which is not the planning expectation. The expectation stays the mean week, 712.8852726036218.

The shortfall is three days: 2016-04-30, 2016-05-01, and 2016-05-13. Orders go out on day indexes 0, 5, 12, 18, and 25, one lot each. Two of the five cycles contain a stockout. The cycle stockout share on this item is 2/5. The unit shortfall is just under 0.05. Same item, different score. That is why the cap is the unit shortfall.

Safety stock 37, the integer just below the choice, has units short 168.1147273963782 and shortfall **0.05007885832480732**. That fails the strict cap. Its average on-hand is 345.7295129649324, a little lower than 345.9080843935039. The objective would have taken 37 if 37 had been feasible. It was not. Safety stock 0, which is also the normal-loss candidate, has shortfall 0.16327516455060415. The enumeration is on `Example_search` in the workbook, from 0 through 2,645. The minimum feasible safety stock on that sheet is 38, and it matches the Python choice. The minimum average on-hand among feasible rows is the average at 38.

## The workbook

`reports/03-construct-solver.xlsx` has four sheets.

`Example_FOODS_3_090` is the model. Safety stock in B8 is the decision. Average end-of-day on-hand in B11 is the objective, and it is a formula of the 28-day simulation under it. The shortfall in B14 is units short / units demanded. The constraint is that cell strictly under 0.05. The order quantity is `ROUNDUP` of the mean daily `lgbm` times 7, at least 1. A Solver run must not change the order quantity, the lead time, the forecast, or actual. Named ranges are `SafetyStock`, `AvgOnHand`, `FillRate`, `OrderQty`, and `ReorderPoint`.

I recalculated that sheet outside Python. The largest absolute gap between the formula on-hand and shortfall and the Python trace, at safety stock 38, was 0 at eight decimal places.

`Example_search` is the integer enumeration for this item. It is values from Python, plus formulas that mark the cap and take the minimum feasible safety stock. `Class_A` is one row per item. The safety-stock column is the decision. The reorder point, the shortfall, the half-batch, and the cap flag are formulas of the recorded columns. Editing a safety stock on `Class_A` does not rerun 558 simulations. The portfolio objective on that sheet is the sum of average on-hand. The items-missing-cap formula counted 0 when the sheet was recalculated. `Notes` is the Solver setup.

Excel Solver was not run. No Solver binary was available, and I did not invent a Solver answer. The integers are the Python enumeration, written into the decision cells so the sheet shows the same policy as the CSV.

If someone opens Solver on the example sheet: minimize `AvgOnHand` by changing `SafetyStock`, with `SafetyStock` an integer ≥ 0, and the shortfall under the cap. The Solver dialog has `<=` and not a strict `<`. The cap is strict, so the practical constraint is the shortfall `<= 0.049999`, or throw away a result that lands on exactly 0.05. The method is **Evolutionary**. The simulation is a step function of safety stock. **GRG Nonlinear** assumes a smooth function and can stop on a flat step between integers. The simplex method does not apply, because lost sales are not a linear program. `Example_search` is the integer search Evolutionary would be approximating, already computed.

## What this stage does not do

No class B or C policy. No debiasing of `lgbm`. No per-item sigma from four blocks. No service factor treated as the answer. No EOQ. No change to the order quantity inside the search. No 3-day or 14-day lead time. No lead-time variability. No historical on-hand. No dollar cost. Dollar savings will not be claimed. No claim that the cycle-stockout share is under 5%. It is 0.21319616885420362. No dashboard. No edit to the Project 1 forecast. No edit to the project README.

## How to reproduce

From the repo root:

```bash
python 02-inventory-optimization/src/construct_policy.py
```

The script imports `analyze_inventory.py` for the file check, the signed error, the ABC cut, and the 7-day blocks. It needs pandas, NumPy, matplotlib, and openpyxl.

| Output | What it is |
|---|---|
| `src/construct_policy.py` | The simulation and the integer search |
| `data/processed/policy.csv` | One row per class A item |
| `data/processed/policy_summary.csv` | One row of class A totals |
| `reports/03-construct-solver.xlsx` | Example simulation, the search, and the class A sheet |
| `images/class_a_safety_stock.png` | Shortfall at the chosen safety stock, and safety stock against volume |
