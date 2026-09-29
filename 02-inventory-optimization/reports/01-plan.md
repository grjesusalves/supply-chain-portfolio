# Plan — CA_3 FOODS inventory policy (reorder point and safety stock)

PACE stage: **Plan**. This document decides the question, the scope, the policy words, and how a later stage will keep score. It does not compute a reorder point, a safety-stock quantity, an order quantity, or a holding cost. Those belong to Analyze and Construct.

The study path is: read this page, then the open decisions at the end. The project README still has placeholders for the later PACE stages. This file does not fill them.

## Business question

For our top products, what reorder point and safety stock minimize holding costs while keeping stockouts under 5%?

That sentence is the decision. Project 1 answered a different question: how many units each FOODS item at store CA_3 would sell on each day of the holdout. A forecast is an input to replenishment, not the replenishment decision. Someone still has to say when to order and how many extra units to keep so an ordinary miss does not empty the shelf. This project is that decision. The LightGBM forecast from Project 1 is the demand we will plan from. It is not the answer.

## What the policy words mean

A **reorder point** is the inventory position that triggers a purchase order. Inventory position means units on hand plus units already on order, not whatever is on the shelf at this minute. When the position falls to the reorder point, we order. We do not wait until the shelf is empty. In the usual continuous-review form, the reorder point equals expected demand over the lead time, plus safety stock. Expected demand comes from the planning forecast. The reorder point is not the order quantity.

**Safety stock** is the extra units above that expected lead-time demand. Its job is to absorb ordinary surprises: a day that sells more than the forecast, or a receipt that shows up late. It is not the pile we expect to sell. Every unit of it sits in the back room and costs money to hold. A bigger cushion means fewer stockouts and a higher holding cost. That trade-off is the reason the project exists.

The forecast we will plan from runs **high**, not low. On this holdout, LightGBM beat the seasonal-naive baseline on WAPE (64.9% versus 77.7%) and was biased high by about 2.6% of units. A high forecast already behaves a little like extra inventory: the plan expects more sales than happened. Safety stock sized as if the forecast were unbiased, or as if it were low, would put a buffer on top of a forecast that is already above actual. This plan will not assume the forecast is low.

**Economic order quantity (EOQ)** is how many units to order once the reorder point is hit. Two costs pull in opposite directions. Small, frequent orders spend a lot on placing orders. Large, rare orders raise the average amount sitting in inventory, so holding cost rises. EOQ is the batch size at that balance. It does not set the service level. A store can order a sensible quantity and still stock out if the reorder point is too low. Order quantity and safety stock are not substitutes. EOQ is the skill we will use for the batch. Safety-stock math is the skill we will use for the cushion.

A **5% stockout cap** means service is a constraint, not a target of perfect availability. Among policies that stay under the cap, we want the lowest holding cost. We are not asked to drive stockouts to zero. A policy that almost never stocks out and holds a large buffer fails the cost test if a smaller buffer would still have stayed under 5%.

"Under 5%" is not yet a formula. The same words can mean three different scores, and they do not rank policies the same way.

- A **cycle service level** counts replenishment cycles. Under 5% means fewer than one cycle in twenty has any stockout, even a one-unit miss.
- A **day-level stockout rate** counts days the item is unavailable.
- A **unit fill rate** counts units. Under 5% means we fail to fill fewer than 5% of the units demanded.

One bad day on a huge item barely moves a cycle count and moves a fill rate a lot. The business question does not say which definition it means. A normal-distribution factor for a 95% cycle service level is one textbook reading. It is not the only reading, and we have not shown that lead-time demand is normal. The choice is open at the end of this plan. Until it is made, we will not treat any service factor as decided.

The skill underneath all of this is the **trade-off between cost and service level**: name the stockout measure, cap it, and only then spend holding cost.

## Scope

In:

- Store **CA_3**, category **FOODS**, the **1,437** items in the Project 1 holdout file.
- The holdout window **2016-04-25 through 2016-05-22** as the period a policy will later be checked on. That window is 28 days. 1,437 items × 28 days is the file's **40,236** rows.
- A subset of those items, the "top products." The subset is **not chosen yet**. ABC analysis in Analyze will propose it, after the rule in the decision list is picked.
- One policy per chosen item: a reorder point, a safety stock, and an order quantity.
- Holding cost as the objective, and the 5% stockout cap as the constraint.

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

- **Unit cost**, what the retailer paid for the unit. `sell_price` is not that. Holding cost belongs on the cash tied up in inventory. A shelf price overstates that cash unless we say we are using it as a stand-in.
- **Holding-cost rate**, the share of unit value it costs to hold stock for a year or a week. Not in M5.
- **Order cost**, the cost of placing one replenishment. Not in M5. EOQ cannot be computed without it or without a labeled assumption that replaces it.
- **Lead time**, in days from order to receipt, and any record of how much that lead time moves around. Not in M5. Safety stock needs a lead time before "demand over the lead time" means anything.
- On-hand inventory, receipts, and open purchase orders. We cannot reconstruct the position CA_3 actually held in April 2016. The later policy is a forward rule scored on holdout demand, not a story about what the store did.

A dollar holding cost written now would be an invented number. This plan does not invent one. Later stages may compare policies in **units of inventory** and leave the dollar line blank until the missing inputs are stated as assumptions.

## How we will keep score

Two tests, applied in Construct, defined here so the definitions cannot drift.

**Stockouts under 5%.** On the definition Alves picks, the simulated policy stays under 5% on the holdout for the chosen items. The check is a simple simulation, not the formula alone. The formula can claim a 95% cycle service level and still fail on lumpy FOODS demand, on a forecast that sits high, or on a 28-day window. We will also show the other two stockout definitions next to the headline one, so a pass on cycles cannot hide a bad fill rate.

**Holding cost minimized.** Among policies that pass the cap, we keep the one with the lowest holding cost. In units, that cost is the inventory the policy carries: cycle stock (in the textbook average, about half the order quantity) plus safety stock. In dollars, it is those units times a stated unit value times a stated holding rate. If either dollar input is still missing, the ranking stays in units and the dollar figure is omitted on purpose.

A cheap policy that stocks out past the cap is a fail. A policy that is far under the cap and holds a large buffer is also a fail if a smaller buffer still clears 5%. WAPE is not the score of this project. WAPE already judged the forecast.

## Method we intend

Nothing below is calculated. These are the skills the later stages will show, and why each one is on the list.

**ABC analysis** chooses the top products. Replenishment effort belongs on the items that dominate the volume, or the retail value, once that rule is picked. Class A is where a bad reorder point is expensive to explain. Class C is where a full safety-stock write-up is hard to defend. Analyze will show the cumulative share so the cutoff is a choice a reader can see. Plan does not set the cutoff.

**Safety-stock math** turns uncertainty into a unit buffer. The textbook piece is the spread of demand over the lead time, times a service factor tied to the stockout cap. The spread should come from this holdout's forecast errors (`lgbm` against `actual`), not from a guessed standard deviation. If lead time is an assumption and we treat it as fixed, only demand uncertainty enters. If lead time itself is uncertain, both enter, and the write-up has to say so. The service factor will not be built on the claim that the forecast is low. The holdout says it is high by about 2.6% of units.

**EOQ** sets the order quantity after an order cost and a holding cost exist, including the case where those are written down as assumptions rather than found in a file. We will not drop in a round order cost just to make the formula print. If the costs are still blank, the order quantity waits, and the simulation can still test safety stock against a stated order quantity that is labeled as a scenario.

**Simulation** is the check on the 5% cap. Python will replay each chosen item: apply the reorder point, consume demand, receive the order after the assumed lead time, and count stockouts and average inventory. Whether the demand path is the holdout's `actual` series, or a resample of residuals around `lgbm`, will be stated in Construct. The simulation checks the formula. It is not a new forecasting model.

**Excel Solver** is the cost-and-service trade-off in a workbook an interviewer can open. Same definitions as the Python path. Solver pushes the decision variables down so holding cost falls without crossing the cap. It does not forecast. The tools for the calculation stage are Excel Solver and Python. Tableau Public waits for the dashboard.

## Assumptions the later stages have to write down

Several of these are still choices. Listing them is not the same as making them. The decision list at the end is what blocks Analyze.

- Expected daily demand is the LightGBM forecast, unless we first remove the high bias of about 2.6% of units. We will say which one we used.
- A zero in `actual` means zero units recorded as sold. It may be a true zero or a stockout Project 1 could not see. We still cannot separate those.
- The policy language in this plan is continuous review. Periodic review is a different formula. We will not mix them.
- Lead time is a stated assumption in days. It is not a column we forgot to aggregate.
- Uncertainty of demand over that lead time is estimated from the holdout errors. We will look at whether those errors are close enough to normal for a service-factor formula. If they are not, the simulation is the number we trust.
- Unmet demand is either lost or backordered, one of the two, for the whole simulation.
- No case pack, no supplier minimum, and no capacity limit, unless we add one and say so.
- One store. A miss at CA_3 is not filled from CA_1.
- Dollar holding cost uses a stated unit value and a stated rate. Shelf price is not unit cost unless the write-up says it is being used as a proxy.
- The test is one 28-day origin. A policy that survives May 2016 is not proven for a holiday quarter. Plan accepts a single window, as Project 1 did.
- Holdout actuals score the policy. They do not refit the forecast.

## What this stage does not do

No ABC classes and no item list. No standard deviation, no service factor, no safety stock, no reorder point. No EOQ. No Solver model and no simulation. No dollar cost, because the inputs are missing. No dashboard. No edit to the Project 1 forecast.

Analyze, when it is started, is still descriptive: volume concentration, the size and direction of forecast errors, and a written list of which costs are assumptions. Construct builds the quantities, the workbook, and the simulation. Execute says what a planner should change on the reorder point. None of that is this file.

## Decisions still open before Analyze

These have to be settled before Analyze starts. This plan does not answer them, and it does not fill them with a guessed number.

1. **Top-product rule.** ABC on unit volume, ABC on retail value (holdout units times `sell_price`), or a fixed count of items. The cutoff (class A share, or how many items) is not chosen here.
2. **Stockout definition for the 5% cap.** Cycle service level (share of replenishment cycles with any stockout), day-level stockout rate, or unit fill rate. The cap applies to the definition you pick. The other two will be reported beside it, not substituted for it.
3. **Lead time.** One assumed lead time in days, a small set of lead times to test as scenarios, or a stop until a real lead time is supplied. There is no lead time in the data, and this plan does not propose one.
4. **Lead-time variability.** Treat that lead time as fixed, or also put uncertainty on it. There is no supplier history to estimate the spread. If it varies, the spread has to be an explicit assumption too.
5. **Unit value.** Use `sell_price` only as a labeled stand-in for inventory value, apply a cost-to-price ratio you choose, or keep the objective in units until a unit cost exists. Do not treat `sell_price` as unit cost without saying so.
6. **Holding-cost rate and order cost.** The holding rate (annual or weekly, stated as such) and the cost per purchase order. Both are missing. EOQ and a dollar holding cost wait on these, even when they are labeled assumptions rather than data.
7. **Forecast bias.** Use the LightGBM forecast as-is (about 2.6% high on units), or remove that bias before it becomes expected demand. Safety stock will not be built on the idea that the forecast is low.
8. **Review policy.** Continuous review (order when the inventory position hits the reorder point) or periodic review (order on a fixed calendar). The reorder-point formula described above is the continuous one.
9. **Unmet demand.** Lost sales, or backorders. The simulation needs one of those.
10. **What Solver may change.** Safety stock only, or safety stock and order quantity together. The objective is holding cost. The constraint is the 5% stockout cap on the definition from decision 2.
