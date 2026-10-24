# Plan — CA_3 FOODS inventory policy (reorder point and safety stock)

PACE stage: **Plan**. This document settles the question, the scope, the meaning of the policy terms, and the way a later stage will keep score. It computes no reorder point, no safety-stock quantity, no order quantity and no holding cost; those belong to Analyze and Construct.

The intended reading order is this page first, then the decisions recorded at its end. The project README still holds placeholders for the later PACE stages, and this file does not fill them.

## Business question

For our top products, what reorder point and safety stock minimize holding costs while keeping stockouts under 5%?

That sentence is the question this project began with, and the decisions at the end pin down two of its words: what we minimize is units held, not dollars, and the stockout cap is a unit fill rate. This file still computes neither the reorder point nor the safety stock. Project 1 answered a different question, namely how many units each FOODS item at store CA_3 would sell on each day of the holdout. A forecast, however, is an input to replenishment rather than the replenishment decision itself. Someone still has to decide when to order, and how many extra units to keep so that an ordinary miss does not empty the shelf; this project is that decision. The LightGBM forecast from Project 1 is the demand we will plan from — not the answer.

## What the policy words mean

A **reorder point** is the inventory position that triggers a purchase order. Inventory position means units on hand plus units already on order, not whatever happens to be on the shelf at a given minute. When the position falls to the reorder point, we order, rather than waiting for the shelf to empty. In the usual continuous-review form, the reorder point equals expected demand over the lead time plus safety stock, with expected demand drawn from the planning forecast. The reorder point is not the order quantity.

**Safety stock** is the margin of units above that expected lead-time demand. Its job is to absorb ordinary surprises — a day that outsells the forecast, or a receipt that arrives late — and it is not stock we expect to sell. Every unit of it sits in the back room and costs money to hold, which means a larger cushion buys fewer stockouts at a higher holding cost. That trade-off is the reason the project exists.

Note that the forecast we will plan from runs **high**, not low. On this holdout, LightGBM beat the seasonal-naive baseline on WAPE (64.9% versus 77.7%) while running high by about 2.6% of units. A high forecast already behaves somewhat like extra inventory, since the plan expects more sales than occurred. Safety stock sized as though the forecast were unbiased, let alone low, would stack a buffer on top of a forecast already above actual. The decision, therefore, is to use that forecast as-is and not to build safety stock as if it were low.

**Economic order quantity (EOQ)** is the number of units to order once the reorder point is hit, when both an order cost and a holding cost exist. The two costs pull in opposite directions: small, frequent orders spend heavily on placing orders, whereas large, rare orders raise the average stock on hand, and holding cost rises with it. EOQ is the batch size at that balance; it does not set the service level. A store can order a sensible quantity and still stock out if its reorder point is too low, so order quantity and safety stock are not substitutes. That said, this project will not use EOQ for the batch, given that there is neither an order cost nor a holding-cost rate, and simulated dollar costs were refused. The order quantity is instead 7 days of the LightGBM forecast — one lead time of supply — in units, and it is not a cost optimum. Safety-stock math is the skill we will apply to the cushion, and Solver may change that cushion alone.

A **5% stockout cap** treats service as a constraint — not as a target of perfect availability. Among the policies that stay under the cap, we want the one holding the fewest units; we are not asked to drive stockouts to zero. A policy that almost never stocks out while holding a large buffer fails that test whenever a smaller buffer would still have stayed under 5%. Dollar savings will not be claimed.

"Under 5%," however, is not yet a formula. The same words can describe three different scores, and those scores do not rank policies alike:

- A **cycle service level** counts replenishment cycles; under 5% means that fewer than one cycle in twenty sees any stockout, even a one-unit miss.
- A **day-level stockout rate** counts the days on which the item is unavailable.
- A **unit fill rate** counts units; under 5% means we fail to fill fewer than 5% of the units demanded.

One bad day on a huge item barely moves a cycle count, yet it moves a fill rate considerably. The cap is therefore a **unit fill rate** under 5%, with cycle service level and the day-level stockout rate reported beside it rather than substituted for it. A normal-distribution factor for a 95% cycle service level is one textbook reading; it is not this cap, and we have not shown that lead-time demand is normal. No service factor is calculated in this file.

The skill underlying all of this is the **trade-off between units held and service level**: the stockout measure is unit fill rate, the cap is 5%, and only then do we spend inventory.

## Scope

In:

- Store **CA_3**, category **FOODS**, and the **1,437** items in the Project 1 holdout file.
- The holdout window, **2016-04-25 through 2016-05-22**, as the period on which a policy will later be checked. The window spans 28 days, and 1,437 items × 28 days gives the file's **40,236** rows.
- A subset of those items, the "top products," selected by a rule already decided: ABC on unit volume, using actual holdout units. Class A comprises the items that cumulatively reach 80% of holdout units — neither retail value nor a fixed count chosen in advance. Analyze applies the rule; this plan does not list the items.
- One policy per chosen item, consisting of a reorder point, a safety stock and an order quantity. The order quantity is 7 days of the LightGBM forecast, in units, and it is not a cost optimum.
- Units held (cycle stock plus safety stock) as the objective, and a unit fill rate under 5% as the constraint.

Out:

- HOBBIES, HOUSEHOLD, the other California stores, Texas and Wisconsin.
- A new demand forecast, or a dollar-sales forecast; Project 1 already built the unit forecast this policy will use.
- Multi-echelon inventory, a warehouse and transfers between stores, since the M5 files show no distribution center.
- Any claim that a price or a SNAP day caused a sales change. The calendar remains available should a lead time happen to cover a SNAP stretch, but it is not a second model.
- Tableau Public, which belongs to the dashboard stage, once there is a result to show. It is neither a Plan tool nor the means of calculating the policy.
- Any computed policy: this file contains no reorder point, no safety stock, no EOQ, no Solver solution and no simulation result.

## Data we will use

There is no new download; Project 2 reads Project 1. I checked the forecast file's columns, the Project 1 data notes, and the headers of the two raw files a cost model would join. Raw CSVs stay git-ignored, and this project will not commit them.

The planning file is `01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv`.

| Column | What it is |
|---|---|
| `item_id` | The FOODS item. |
| `day` | The holdout date. |
| `actual` | Units that sold that day. |
| `baseline` | Seasonal naive from Project 1: the same weekday four weeks earlier. |
| `lgbm` | The LightGBM forecast, in units per day. |

Every one of those measures is **daily unit sales, not dollars**. The planning forecast is **`lgbm`**; `baseline` is the comparison Project 1 already ran, and `actual` is what a later simulation will score a policy against. Treating `actual` as the demand we "expected" would amount to planning with information no buyer had on 2016-04-24.

The five items with the most actual holdout units serve as context, not as the assortment:

| Item | Holdout units (`actual`) |
|---|---|
| FOODS_3_090 | 3,357 |
| FOODS_3_586 | 1,883 |
| FOODS_3_120 | 1,617 |
| FOODS_3_252 | 1,405 |
| FOODS_3_681 | 1,253 |

A high-volume item is not automatically the right subject for a deep safety-stock study if its forecast barely misses, whereas a smaller item can matter a great deal if its misses are wide. ABC has not yet been run, and these five are not selected.

Two further Project 1 files remain available for later stages, still from `01-demand-forecasting/data/raw/` and still uncommitted:

- `sell_prices.csv` holds `store_id`, `item_id`, `wm_yr_wk` and `sell_price` — the weekly shelf price, one row per item–store–week. It is what the shopper paid.
- `calendar.csv` holds the date, Walmart week, weekday, event names and the SNAP flags, including `snap_CA`. It can date the holdout, but it carries no supplier dates.

The sales history in `sales_train_evaluation.csv` is the source Project 1 already used. The processed forecast file suffices for the holdout check, so there is no need to copy the raw sales file into this project.

## What we do not have

The following were checked for and found absent from the forecast columns, from `sell_prices.csv`, from `calendar.csv` and from the Project 1 data notes:

- **Unit cost**, meaning what the retailer paid for the unit. `sell_price` is not that, and we will neither use it as a stand-in nor apply a cost-to-price ratio; the objective stays in units.
- **Holding-cost rate**, the share of unit value it costs to hold stock for a year or a week. It is not in M5, and we will not simulate one.
- **Order cost**, the cost of placing one replenishment. It is not in M5; we will not invent one, nor compute a dollar EOQ.
- **Lead time** in the files, in days from order to receipt, together with any record of how much that lead time varies. It is not in M5. The working lead time is an assumption of 7 days, fixed — not a column we found.
- On-hand inventory, receipts and open purchase orders. We cannot reconstruct the position CA_3 actually held in April 2016, so the later policy is a forward rule scored on holdout demand rather than an account of what the store did.

A dollar holding cost written now would be an invented number, and this plan invents none. Simulated dollar costs were refused, so later stages compare policies in **units of inventory**. Dollar savings will not be claimed.

## How we will keep score

Two tests apply in Construct; they are defined here so that the definitions cannot drift.

**Stockouts under 5%.** The constraint is unit fill rate: on the holdout, the simulated policy must fill all but under 5% of the units demanded for the chosen items. The check is a simple simulation rather than the formula alone. After all, the formula can promise a 95% cycle service level and still fail on lumpy FOODS demand, on a forecast that sits high, or over a 28-day window. Cycle service level and the day-level stockout rate are reported beside the fill rate, but they do not substitute for the cap.

**Units held, minimized.** Among the policies that pass the fill-rate cap, we keep the one holding the fewest units: cycle stock (in the textbook average, about half the order quantity) plus safety stock. There is no dollar ranking, and unit value stays in units. `sell_price` is not a stand-in, and there is no cost-to-price ratio, no holding-cost rate and no order cost. Dollar savings will not be claimed.

A policy that stocks out past the fill-rate cap fails. So, too, does a policy that sits far under the cap with a large buffer, if a smaller buffer would still clear 5%. WAPE is not this project's score; it has already judged the forecast.

## Method we intend

Nothing below is calculated. These are the skills the later stages will demonstrate, together with the reason each one is on the list.

**ABC analysis** selects the top products. The rule is unit volume — actual holdout units, neither retail value nor a fixed count chosen in advance — and class A comprises the items that cumulatively reach 80% of holdout units. That is where a bad reorder point is costly to explain, whereas class C is where a full safety-stock write-up is hard to defend. Analyze will show the cumulative share and name the items that cross 80%; this plan does not list them.

**Safety-stock math** turns uncertainty into a unit buffer. The textbook form multiplies the spread of demand over the lead time by a service factor tied to the stockout cap. That spread should come from this holdout's forecast errors (`lgbm` against `actual`), not from a guessed standard deviation. Given that lead time is a fixed assumption of 7 days, only demand uncertainty enters; there is neither supplier history nor lead-time variability. Nor will the service factor rest on a claim that the forecast is low. The forecast is used as-is: the holdout shows it running high by about 2.6% of units, and that bias is not removed before the holdout scores the policy.

**Order quantity** is not an EOQ. No dollar EOQ will be computed, and no order cost or holding-cost rate will be simulated merely to make that formula print. The order quantity is 7 days of the LightGBM forecast — one lead time of supply — in units, and it is not a cost optimum. Solver does not change it.

**Simulation** is the check on the 5% cap. Python will replay each chosen item: apply the reorder point, consume demand, receive the order after the assumed lead time, and count stockouts and average inventory. Whether the demand path is the holdout's `actual` series or a resample of residuals around `lgbm` will be stated in Construct. The simulation checks the formula; it is not a new forecasting model.

**Excel Solver** presents the units-and-service trade-off in a workbook an interviewer can open, under the same definitions as the Python path. Solver may change safety stock only, lowering units held without crossing a unit fill rate of 5%; it neither changes the order quantity nor forecasts. The tools for the calculation stage are Excel Solver and Python, while Tableau Public waits for the dashboard.

## Assumptions the later stages have to write down

The ten choices that were blocking Analyze are decided at the end of this file. What follows is the working list, including those no longer open.

- Expected daily demand is the LightGBM forecast as-is. Its high bias of about 2.6% of units is not removed, and the holdout that will later score the policy is the very holdout that reveals that bias.
- A zero in `actual` means zero units recorded as sold. It may be a true zero or a stockout Project 1 could not see, and we still cannot separate the two.
- Review is continuous. Periodic review follows a different formula, and the two will not be mixed.
- Lead time is 7 days, a single number, and it is an assumption, since the data holds no lead time. There is no 3-day and 14-day scenario grid.
- That lead time is fixed, with no variability and no supplier history. Demand uncertainty over the lead time is estimated from the holdout errors, and we will examine whether those errors are close enough to normal for a service-factor formula; if they are not, the simulation is the number we trust.
- Unmet demand is treated as lost sales throughout the simulation.
- There is no case pack, no supplier minimum and no capacity limit, unless we add one and say so.
- There is one store, so a miss at CA_3 is not filled from CA_1.
- The objective stays in units. `sell_price` is not a stand-in for unit value, and there is no cost-to-price ratio, no holding-cost rate and no order cost. Dollar savings will not be claimed.
- The test rests on one 28-day origin, and a policy that survives May 2016 is not thereby proven for a holiday quarter. Plan concedes the limitation of a single window, as Project 1 did.
- Holdout actuals score the policy; they do not refit the forecast.

## What this stage does not do

This stage produces no ABC item list: the class A rule is decided, but the items are not named here. It produces no standard deviation, no service factor, no safety stock and no reorder point; no EOQ and no dollar order quantity; no Solver model and no simulation; and no dollar cost. Dollar savings will not be claimed. There is no dashboard, and no edit to the Project 1 forecast.

Analyze, once started, remains descriptive: it applies the class A rule, shows volume concentration, and shows the size and direction of forecast errors, without reopening the ten decisions below. Construct builds the quantities, the workbook and the simulation, and Execute says what a planner should change about the reorder point. None of that is this file.

## Decisions

These questions were open and are now decided. This plan does not turn them into quantities, and it adds no number that is not in the list.

1. **Top products.** ABC on unit volume, using actual holdout units; class A comprises the items that cumulatively reach 80% of holdout units. Neither retail value nor a fixed count chosen in advance.
2. **Stockout cap.** A unit fill rate under 5% is the constraint. Cycle service level and the day-level stockout rate are reported beside it, never substituted for it.
3. **Lead time.** 7 days, a single number and explicitly an assumption, given that the data holds no lead time. No 3-day and 14-day scenario grid is added.
4. **Lead-time variability.** The lead time is fixed, with no variability and no supplier history.
5. **Unit value.** The analysis stays in units; `sell_price` is not used as a stand-in, and there is no cost-to-price ratio.
6. **Holding-cost rate and order cost.** Neither is used, since Alves refused simulated dollar costs, and no dollar EOQ is computed. The order quantity is 7 days of the LightGBM forecast (one lead time of supply), in units, and it is not a cost optimum.
7. **Forecast bias.** The LightGBM forecast is used as-is. Its high bias of about 2.6% of units, on the holdout that will later score the policy, is not removed, and safety stock is not built as if the forecast were low.
8. **Review policy.** Continuous review: an order is placed when the inventory position hits the reorder point.
9. **Unmet demand.** Lost sales.
10. **What Solver may change.** Safety stock only. The objective is units held (cycle stock plus safety stock), and the constraint is a unit fill rate under 5%.

Dollar savings will not be claimed, for the simple reason that there is no unit cost, no holding-cost rate and no order cost with which to turn units held into dollars. What the plan does promise is narrower but defensible: a policy measured honestly in units, against a stated service cap.
