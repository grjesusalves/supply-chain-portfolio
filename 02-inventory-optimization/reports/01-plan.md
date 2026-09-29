# Plan — CA_3 FOODS inventory policy (reorder point and safety stock)

PACE stage: **Plan**. This document decides the question, the scope, the policy words, and how a later stage will keep score. It does not compute a reorder point, a safety-stock quantity, an order quantity, or a holding cost. Those belong to Analyze and Construct.

The study path is: read this page, then the decisions recorded at the end. The project README still has placeholders for the later PACE stages. This file does not fill them.

## Business question

For our top products, what reorder point and safety stock minimize holding costs while keeping stockouts under 5%?

That sentence is the question this project started from. The decisions at the end fix two words in it: the thing we minimize is units held, not dollars, and the stockout cap is a unit fill rate. This file still does not compute the reorder point or the safety stock. Project 1 answered a different question: how many units each FOODS item at store CA_3 would sell on each day of the holdout. A forecast is an input to replenishment, not the replenishment decision. Someone still has to say when to order and how many extra units to keep so an ordinary miss does not empty the shelf. This project is that decision. The LightGBM forecast from Project 1 is the demand we will plan from. It is not the answer.

## What the policy words mean

A **reorder point** is the inventory position that triggers a purchase order. Inventory position means units on hand plus units already on order, not whatever is on the shelf at this minute. When the position falls to the reorder point, we order. We do not wait until the shelf is empty. In the usual continuous-review form, the reorder point equals expected demand over the lead time, plus safety stock. Expected demand comes from the planning forecast. The reorder point is not the order quantity.

**Safety stock** is the extra units above that expected lead-time demand. Its job is to absorb ordinary surprises: a day that sells more than the forecast, or a receipt that shows up late. It is not the pile we expect to sell. Every unit of it sits in the back room and costs money to hold. A bigger cushion means fewer stockouts and a higher holding cost. That trade-off is the reason the project exists.

The forecast we will plan from runs **high**, not low. On this holdout, LightGBM beat the seasonal-naive baseline on WAPE (64.9% versus 77.7%) and was biased high by about 2.6% of units. A high forecast already behaves a little like extra inventory: the plan expects more sales than happened. Safety stock sized as if the forecast were unbiased, or as if it were low, would put a buffer on top of a forecast that is already above actual. The decision is to use that forecast as-is and not to build safety stock as if it were low.

**Economic order quantity (EOQ)** is how many units to order once the reorder point is hit, when an order cost and a holding cost both exist. Two costs pull in opposite directions. Small, frequent orders spend a lot on placing orders. Large, rare orders raise the average amount sitting in inventory, so holding cost rises. EOQ is the batch size at that balance. It does not set the service level. A store can order a sensible quantity and still stock out if the reorder point is too low. Order quantity and safety stock are not substitutes. This project will not use EOQ for the batch. There is no order cost and no holding-cost rate, and simulated dollar costs were refused. The order quantity is 7 days of the LightGBM forecast, one lead time of supply, in units. It is not a cost optimum. Safety-stock math is the skill we will use for the cushion. Solver may change that cushion only.

A **5% stockout cap** means service is a constraint, not a target of perfect availability. Among policies that stay under the cap, we want the fewest units held. We are not asked to drive stockouts to zero. A policy that almost never stocks out and holds a large buffer fails that test if a smaller buffer would still have stayed under 5%. Dollar savings will not be claimed.

"Under 5%" is not yet a formula. The same words can mean three different scores, and they do not rank policies the same way.

- A **cycle service level** counts replenishment cycles. Under 5% means fewer than one cycle in twenty has any stockout, even a one-unit miss.
- A **day-level stockout rate** counts days the item is unavailable.
- A **unit fill rate** counts units. Under 5% means we fail to fill fewer than 5% of the units demanded.

One bad day on a huge item barely moves a cycle count and moves a fill rate a lot. The cap is a **unit fill rate** under 5%. Cycle service level and the day-level stockout rate are reported beside it. They are not substitutes for the cap. A normal-distribution factor for a 95% cycle service level is one textbook reading. It is not this cap, and we have not shown that lead-time demand is normal. No service factor is calculated in this file.

The skill underneath all of this is the **trade-off between units held and service level**: the stockout measure is unit fill rate, the cap is 5%, and only then do we spend inventory.

## Scope

In:

- Store **CA_3**, category **FOODS**, the **1,437** items in the Project 1 holdout file.
- The holdout window **2016-04-25 through 2016-05-22** as the period a policy will later be checked on. That window is 28 days. 1,437 items × 28 days is the file's **40,236** rows.
- A subset of those items, the "top products." The rule is decided: ABC on unit volume, using actual holdout units. Class A is the items that cumulatively reach 80% of holdout units. Not retail value, and not a fixed count chosen in advance. Analyze applies the rule. This plan does not list the items.
- One policy per chosen item: a reorder point, a safety stock, and an order quantity. The order quantity is 7 days of the LightGBM forecast, in units. It is not a cost optimum.
- Units held (cycle stock plus safety stock) as the objective, and a unit fill rate under 5% as the constraint.

Out:

- HOBBIES, HOUSEHOLD, the other California stores, and Texas and Wisconsin.
- A new demand forecast, or a dollar-sales forecast. Project 1 already built the unit forecast this policy will use.
- Multi-echelon inventory, a warehouse, and transfers between stores. The M5 files do not show a distribution center.
- A claim that a price or a SNAP day caused a sales change. The calendar is available later if a lead time happens to cover a SNAP stretch. It is not a second model.
- Tableau Public. That is the dashboard stage, after there is a result to show. It is not a Plan tool, and it is not how the policy will be calculated.
- Any computed policy. This file has no reorder point, no safety stock, no EOQ, no Solver solution, and no simulation result.

## Data we will use

No new download. Project 2 reads Project 1. I checked the forecast file's columns, the Project 1 data notes, and the headers of the two raw files a cost model would join. Raw CSVs stay git-ignored. This project will not commit them.

The planning file is `01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv`.

| Column | What it is |
|---|---|
| `item_id` | The FOODS item. |
| `day` | The holdout date. |
| `actual` | Units that sold that day. |
| `baseline` | Seasonal naive from Project 1: the same weekday four weeks earlier. |
| `lgbm` | The LightGBM forecast, in units per day. |

Every one of those measures is **daily unit sales, not dollars**. The planning forecast is **`lgbm`**. `baseline` is the comparison Project 1 already ran. `actual` is what a later simulation will score a policy against. Using `actual` as the demand we "expected" would be planning with information a buyer did not have on 2016-04-24.

The five items with the most actual units in the holdout are context, not the assortment:

| Item | Holdout units (`actual`) |
|---|---|
| FOODS_3_090 | 3,357 |
| FOODS_3_586 | 1,883 |
| FOODS_3_120 | 1,617 |
| FOODS_3_252 | 1,405 |
| FOODS_3_681 | 1,253 |

A high-volume item is not automatically the right place for a deep safety-stock study if its forecast barely misses, and a smaller item can matter if its misses are wide. ABC has not been run. These five are not selected.

Two other Project 1 files are available later, still from `01-demand-forecasting/data/raw/`, and still not committed:

- `sell_prices.csv` has `store_id`, `item_id`, `wm_yr_wk`, and `sell_price`. That is the weekly shelf price, one row per item–store–week. It is what the shopper paid.
- `calendar.csv` has the date, Walmart week, weekday, event names, and the SNAP flags, including `snap_CA`. It can date the holdout. It has no supplier dates.

The sales history in `sales_train_evaluation.csv` is the source Project 1 already used. The processed forecast file is enough for the holdout check. We do not need to copy the raw sales file into this project.

## What we do not have

Checked, and absent from the forecast columns, from `sell_prices.csv`, from `calendar.csv`, and from the Project 1 data notes:

- **Unit cost**, what the retailer paid for the unit. `sell_price` is not that. We will not use it as a stand-in, and we will not apply a cost-to-price ratio. The objective stays in units.
- **Holding-cost rate**, the share of unit value it costs to hold stock for a year or a week. Not in M5. We will not simulate one.
- **Order cost**, the cost of placing one replenishment. Not in M5. We will not invent one, and we will not compute a dollar EOQ.
- **Lead time** in the files, in days from order to receipt, and any record of how much that lead time moves around. Not in M5. The working lead time is an assumption of 7 days, fixed. It is not a column we found.
- On-hand inventory, receipts, and open purchase orders. We cannot reconstruct the position CA_3 actually held in April 2016. The later policy is a forward rule scored on holdout demand, not a story about what the store did.

A dollar holding cost written now would be an invented number. This plan does not invent one. Simulated dollar costs were refused. Later stages compare policies in **units of inventory**. Dollar savings will not be claimed.

## How we will keep score

Two tests, applied in Construct, defined here so the definitions cannot drift.

**Stockouts under 5%.** The constraint is unit fill rate: the simulated policy fills all but under 5% of units demanded on the holdout for the chosen items. The check is a simple simulation, not the formula alone. The formula can claim a 95% cycle service level and still fail on lumpy FOODS demand, on a forecast that sits high, or on a 28-day window. Cycle service level and the day-level stockout rate are reported beside the fill rate. They do not substitute for the cap.

**Units held, minimized.** Among policies that pass the fill-rate cap, we keep the one with the fewest units held: cycle stock (in the textbook average, about half the order quantity) plus safety stock. There is no dollar ranking. Unit value stays in units. `sell_price` is not a stand-in. There is no cost-to-price ratio, no holding-cost rate, and no order cost. Dollar savings will not be claimed.

A policy that stocks out past the fill-rate cap is a fail. A policy that is far under the cap and holds a large buffer is also a fail if a smaller buffer still clears 5%. WAPE is not the score of this project. WAPE already judged the forecast.

## Method we intend

Nothing below is calculated. These are the skills the later stages will show, and why each one is on the list.

**ABC analysis** chooses the top products. The rule is unit volume: actual holdout units, not retail value, and not a fixed count chosen in advance. Class A is the items that cumulatively reach 80% of holdout units. That is where a bad reorder point is expensive to explain. Class C is where a full safety-stock write-up is hard to defend. Analyze will show the cumulative share and name the items that cross 80%. This plan does not list them.

**Safety-stock math** turns uncertainty into a unit buffer. The textbook piece is the spread of demand over the lead time, times a service factor tied to the stockout cap. The spread should come from this holdout's forecast errors (`lgbm` against `actual`), not from a guessed standard deviation. Lead time is an assumption of 7 days, and it is fixed, so only demand uncertainty enters. There is no supplier history and no lead-time variability. The service factor will not be built on the claim that the forecast is low. The forecast is used as-is. The holdout says it is high by about 2.6% of units, and that bias is not removed before the holdout scores the policy.

**Order quantity** is not an EOQ. A dollar EOQ will not be computed, and no order cost or holding-cost rate will be simulated to make that formula print. The order quantity is 7 days of the LightGBM forecast, one lead time of supply, in units. It is not a cost optimum. Solver does not change it.

**Simulation** is the check on the 5% cap. Python will replay each chosen item: apply the reorder point, consume demand, receive the order after the assumed lead time, and count stockouts and average inventory. Whether the demand path is the holdout's `actual` series, or a resample of residuals around `lgbm`, will be stated in Construct. The simulation checks the formula. It is not a new forecasting model.

**Excel Solver** is the units-and-service trade-off in a workbook an interviewer can open. Same definitions as the Python path. Solver may change safety stock only, so units held fall without crossing a unit fill rate of 5%. It does not change the order quantity, and it does not forecast. The tools for the calculation stage are Excel Solver and Python. Tableau Public waits for the dashboard.

## Assumptions the later stages have to write down

The ten choices that were blocking Analyze are decided at the end of this file. What follows is the working list, including the ones that are no longer open.

- Expected daily demand is the LightGBM forecast as-is. The high bias of about 2.6% of units is not removed. The holdout that will later score the policy is the same holdout that shows that bias.
- A zero in `actual` means zero units recorded as sold. It may be a true zero or a stockout Project 1 could not see. We still cannot separate those.
- Review is continuous. Periodic review is a different formula. We will not mix them.
- Lead time is 7 days, one number, and it is an assumption. The data has no lead time. There is no 3-day and 14-day scenario grid.
- That lead time is fixed. No variability. No supplier history. Uncertainty of demand over the lead time is estimated from the holdout errors. We will look at whether those errors are close enough to normal for a service-factor formula. If they are not, the simulation is the number we trust.
- Unmet demand is lost sales, for the whole simulation.
- No case pack, no supplier minimum, and no capacity limit, unless we add one and say so.
- One store. A miss at CA_3 is not filled from CA_1.
- The objective stays in units. `sell_price` is not a stand-in for unit value. There is no cost-to-price ratio, no holding-cost rate, and no order cost. Dollar savings will not be claimed.
- The test is one 28-day origin. A policy that survives May 2016 is not proven for a holiday quarter. Plan accepts a single window, as Project 1 did.
- Holdout actuals score the policy. They do not refit the forecast.

## What this stage does not do

No ABC item list. The class A rule is decided; the items are not named here. No standard deviation, no service factor, no safety stock, no reorder point. No EOQ and no dollar order quantity. No Solver model and no simulation. No dollar cost. Dollar savings will not be claimed. No dashboard. No edit to the Project 1 forecast.

Analyze, when it is started, is still descriptive: apply the class A rule, show volume concentration, and show the size and direction of forecast errors. It does not reopen the ten decisions below. Construct builds the quantities, the workbook, and the simulation. Execute says what a planner should change on the reorder point. None of that is this file.

## Decisions

These were open. They are decided. This plan does not compute them into quantities, and it does not add any number that is not in the list.

1. **Top products.** ABC on unit volume, using actual holdout units. Class A is the items that cumulatively reach 80% of holdout units. Not retail value. Not a fixed count chosen in advance.
2. **Stockout cap.** Unit fill rate under 5% is the constraint. Also report cycle service level and day-level stockout rate beside it. Do not substitute them for the cap.
3. **Lead time.** 7 days. One number. It is explicitly an assumption. The data has no lead time. Do not add a 3-day and 14-day scenario grid.
4. **Lead-time variability.** The lead time is fixed. No variability. No supplier history.
5. **Unit value.** Stay in units. Do not use `sell_price` as a stand-in. No cost-to-price ratio.
6. **Holding-cost rate and order cost.** Neither. Alves refused simulated dollar costs. Do not compute a dollar EOQ. The order quantity is 7 days of the LightGBM forecast (one lead time of supply), in units, and it is not a cost optimum.
7. **Forecast bias.** Use the LightGBM forecast as-is. Do not remove the high bias of about 2.6% of units on the holdout that will later score the policy. Do not build safety stock as if the forecast were low.
8. **Review policy.** Continuous review. Order when the inventory position hits the reorder point.
9. **Unmet demand.** Lost sales.
10. **What Solver may change.** Safety stock only. The objective is units held (cycle stock plus safety stock). The constraint is a unit fill rate under 5%.

Dollar savings will not be claimed. There is no unit cost, no holding-cost rate, and no order cost to turn units held into dollars.
