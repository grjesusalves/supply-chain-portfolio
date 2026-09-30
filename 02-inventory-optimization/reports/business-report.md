# Business report — inventory policy for food at Walmart store CA_3

This report is the story from the question through the recommendation. The two-minute decision is [executive-summary.md](executive-summary.md). The planner page is [04-execute.md](04-execute.md). Nothing here recomputes a safety stock, and nothing here is a dollar saving.

## Situation

Replenishment at CA_3 orders **units** of food, item by item. Project 1 already produced a daily unit forecast. A forecast does not say when to buy or how many extra units to keep so an ordinary miss does not empty the shelf. That is this project.

The question, as it was first written, was: for our top products, what reorder point and safety stock minimize holding costs while keeping stockouts under 5%? [01-plan.md](01-plan.md) fixed two words in that sentence before any quantity was computed. The thing minimized is **units held**, not dollars. The stockout cap is a **unit fill rate**: units short divided by units demanded, strictly under 0.05. Dollar savings will not be claimed. There is no unit cost, no holding-cost rate, and no order cost in the M5 files, and `sell_price` is what the shopper paid, not what the unit cost the retailer.

## Approach

The work follows PACE. The ten planning decisions were not reopened after [01-plan.md](01-plan.md).

- **Plan** defined the reorder point, safety stock, and the 5% cap, and refused a dollar EOQ. The order quantity is 7 days of the LightGBM forecast, in units. Lead time is an assumption of 7 days, fixed. Review is continuous. Unmet demand is lost sales. The forecast is used as-is.
- **Analyze** cut the classes and measured forecast error. It did not size a buffer. See [02-analyze.md](02-analyze.md). Code: `src/analyze_inventory.py`.
- **Construct** searched an integer safety stock for each class A item and scored it with a simulation. See [03-construct.md](03-construct.md). Code: `src/construct_policy.py`.
- **Execute** (the short pages and this report) says what a planner should load. It does not change the integers.

## Data

No new download. The demand file is `01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv`, columns `item_id`, `day`, `actual`, `baseline`, and `lgbm`. The grid is complete.

| Item | Value |
|---|---|
| Store and category | CA_3, FOODS |
| Series | 1,437 |
| Holdout | 2016-04-25 through 2016-05-22 (28 days) |
| Item-days | 40,236 |
| Actual units | 109,870 |

The planning forecast is `lgbm`. `actual` scores the policy. It is not the demand a buyer expected on 2016-04-24. Absent from the files: unit cost, holding-cost rate, order cost, lead time, on-hand inventory, receipts, and supplier history. Raw CSVs stay git-ignored.

## What "top products" means

Items are ranked by actual holdout units. Class A is every item up through the volume that reaches 80% of units, including the whole tie at that volume. Not retail value, and not a headcount chosen in advance.

| Class | Items | Share of items | Holdout units | Share of units |
|---|---:|---:|---:|---:|
| A | 558 | 0.3883089770354906 | 88,230 | 0.8030399563120051 |
| B | 472 | 0.32846207376478775 | 16,486 | 0.15005005916082642 |
| C | 407 | 0.28322894919972164 | 5,154 | 0.04690998452716847 |
| All | 1,437 | 1 | 109,870 | 1 |

Class A is **558** items, about 80.3% of units. It is not a short list. After the ten busiest items the cumulative share is still 0.1265677619004278. The policy below is for those 558 items only.

## The forecast the policy used

Daily error is `lgbm` minus `actual`. On the whole file the forecast is high: bias **2,824.6009022304675** units, a share of **0.025708572879134136**, WAPE **0.6490765893903951** against a seasonal-naive WAPE of **0.777000091016656**.

Class A is the other direction. Bias is **-5,020.5579692516685** units, a share of **-0.05690307116912239** (about 5.7% low), on **15,624** item-days. Class A WAPE is **0.5137881782511478**. The file-level high bias is not a description of the items a reorder point is written for. The decision still stands: do not debias. Construct did not subtract that gap from `lgbm`.

## How the quantities were built

Lead time is **7 days**, one number, an assumption. An order placed on day t is available at the start of day t+7. It cannot serve the day it was ordered. The inventory position is on hand plus on order. Lost sales do not deepen the position.

For each item, expected lead-time demand is the mean of that item's 28 `lgbm` values, times 7. The order quantity is the smallest whole number of units at least that mean week, and at least 1. It is not an EOQ. The search does not change it.

Safety stock is an integer chosen item by item. The candidate from a normal-loss formula was simulated and rejected as the policy. On **186** items that candidate missed the cap. On **314** the search used a lower safety stock. On **58** they match. The candidate safety stocks sum to **3,012**. The safety stocks used sum to **4,079**. The cap is a simulated unit shortfall, not a normal quantile. Class A `lgbm` is low, unmet demand is lost, and a typical item has a handful of cycles. The formula assumes none of that.

The search tries safety stock 0, 1, 2, and so on. It keeps the feasible integer with the lowest average end-of-day on-hand. On all 558 items that was the smallest feasible integer.

There is no on-hand history. On the morning of 2016-04-25, on-hand equals the reorder point and on-order is zero before the review, so every class A item orders that morning. The first receipt is **2016-05-02**. The first week is covered only by that opening balance.

Excel Solver was not run. No Solver binary was available, and no Solver answer was invented. The integers are the Python enumeration, written into `reports/03-construct-solver.xlsx` so the workbook shows the same policy as the CSV. The example sheet is `Example_FOODS_3_090`.

## Results

From `data/processed/policy_summary.csv`:

| | Class A |
|---|---:|
| Items | 558 |
| Units demanded | 88,230 |
| Units short | 2,681.5674402151976 |
| Unit shortfall | 0.030392921231046102 |
| Total average on-hand | 14,461.064128366881 |
| Total safety stock | 4,079 |
| Total cycle stock (order quantity / 2) | 10,541.5 |
| Textbook units held | 14,620.5 |
| Items missing the cap | 0 |
| Items with safety stock 0 | 193 |

The shortfall is about 3.0% of units demanded. The share of units sold is **0.9696070787689539**. The average on-hand that was minimized and the textbook expression are close on this window and they are not the same number. The search used the simulation.

The same policy does not deliver a 95% cycle service. **722** of **15,624** item-days had a shortfall, a day-level rate of **0.046210957501280084**. That rate was not the constraint. **601** of **2,819** cycles had a stockout, a share of **0.21319616885420362** (about 21% of cycles). The share of cycles with no stockout is **0.7868038311457963**. The median item has **4** cycles. The plan said not to swap these scores. This window is the case it was warning about.

The buffer is not a volume ranking. Five busy items from `policy.csv`:

| Item | Units demanded | Order quantity | Safety stock | Reorder point | Unit shortfall |
|---|---:|---:|---:|---:|---:|
| FOODS_3_090 | 3,357 | 713 | 38 | 750.8852726036218 | 0.04978097330842364 |
| FOODS_3_586 | 1,883 | 474 | 0 | 473.8546930978276 | 0.010698516676671493 |
| FOODS_3_120 | 1,617 | 435 | 0 | 434.0506172848497 | 0.04016659413429209 |
| FOODS_3_252 | 1,405 | 272 | 71 | 342.45635833336723 | 0.049497253855254636 |
| FOODS_3_681 | 1,253 | 230 | 193 | 422.7964730863048 | 0.04964367670685971 |

`FOODS_3_586` is the second-busiest item and its safety stock is 0. `FOODS_3_681` is fifth and its safety stock is **193**, the maximum in the file. Its `lgbm` summed to 919.1858923452189 against 1,253 actual. The 193 is the smallest integer that brings that item under the cap. It is not a debiased mean, and it is not there because the item is large.

The item closest to the cap is `FOODS_2_266`, shortfall **0.049946516104229**, safety stock 5, order quantity 13, reorder point 17.95326251764203, on 61 units demanded. The median item shortfall is **0.038070671837693734**. Among items with a positive safety stock the median shortfall is **0.04308352428601003**. The search stops at the first integer that clears 0.05, so many rows sit near the line. On `FOODS_3_090`, safety stock 37 has shortfall **0.05007885832480732** and fails. Safety stock 38 passes.

## Risks

**Opening inventory.** The shelf starts at the reorder point, not from a count. A different opening balance would change both the shortfall and the average on-hand. Other openings were not tried. On `FOODS_3_090` the first seven days of actual sum to **904**, and the opening balance does not cover that, so the item stocks out before the first receipt even with safety stock 38.

**One window, one store, one category.** The test is 28 days in late April and May 2016. It does not prove a holiday quarter, another California store, or hobbies and household. Class B and class C have no policy here.

**Lead time is assumed.** Seven days, fixed, with no variability. The files do not contain a supplier lead time. Moving that assumption would move the reorder point. This project did not run a 3-day or 14-day grid.

**Cycle service is the wrong headline.** About 21% of cycles had a stockout. Quoting 95% availability from the unit result would mis-state the file. The result that cleared the cap is the unit shortfall of 0.030392921231046102.

**The class A forecast is low.** A buyer who adds the class A gap back into `lgbm` and also loads these safety stocks would buffer the miss twice. A buyer who drops the large buffers because the file-level forecast is high (about 2.6% on all food items) would be using the wrong sign. On class A the sign is negative.

**No dollars.** Units held are not a saving. No holding-cost rate was simulated to turn them into one.

## Recommendation

Set the reorder point and the safety stock for each of the 558 class A items to the values already in `data/processed/policy.csv`, order seven days of that item's mean LightGBM forecast rather than an economic order quantity, and do not manage by cycle service, debias the forecast, or claim a dollar saving.

There is no dashboard yet. The Construct chart is [images/class_a_safety_stock.png](../images/class_a_safety_stock.png). Publishing a dashboard is a later stage. It was not done here.
