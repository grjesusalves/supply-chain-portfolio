# Business report — inventory policy for food at Walmart store CA_3

This report follows the work from the original question through to the recommendation. The two-minute decision lives in [executive-summary.md](executive-summary.md), and the planner page in [04-execute.md](04-execute.md). Nothing here recomputes a safety stock, and nothing here should be read as a dollar saving.

## Situation

Replenishment at CA_3 orders food in **units**, item by item. Project 1 already produced a daily unit forecast. That said, a forecast does not say when to buy, nor how many extra units to keep so that an ordinary miss does not empty the shelf; answering those two questions is the work of this project.

As first written, the question asked which reorder point and safety stock, for our top products, would minimize holding costs while keeping stockouts under 5%. Before a single quantity was computed, [01-plan.md](01-plan.md) tightened two words in that sentence. The quantity minimized is **units held**, not dollars, and the stockout cap is a **unit fill rate** — units short divided by units demanded, strictly under 0.05. Dollar savings will not be claimed. After all, the M5 files contain no unit cost, no holding-cost rate and no order cost, and `sell_price` records what the shopper paid, not what the unit cost the retailer.

## Approach

The work follows PACE, and the ten planning decisions in [01-plan.md](01-plan.md) were never reopened once set.

- **Plan** defined the reorder point, the safety stock and the 5% cap, and declined to compute a dollar EOQ. The order quantity is 7 days of the LightGBM forecast, in units; lead time is a fixed assumption of 7 days; review is continuous; unmet demand is a lost sale; and the forecast is used exactly as published.
- **Analyze** cut the classes and measured forecast error, but it sized no buffer. See [02-analyze.md](02-analyze.md); the code is `src/analyze_inventory.py`.
- **Construct** searched for an integer safety stock for each class A item and scored every candidate with a simulation. See [03-construct.md](03-construct.md); the code is `src/construct_policy.py`.
- **Execute**, comprising the short pages and this report, says what a planner should load. It does not change the integers.

## Data

No new download was required. The demand file is `01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv`, with columns `item_id`, `day`, `actual`, `baseline` and `lgbm`, and its grid is complete.

| Item | Value |
|---|---|
| Store and category | CA_3, FOODS |
| Series | 1,437 |
| Holdout | 2016-04-25 through 2016-05-22 (28 days) |
| Item-days | 40,236 |
| Actual units | 109,870 |

The planning forecast is `lgbm`, while `actual` scores the policy; the latter is emphatically not the demand a buyer expected on 2016-04-24. Several things are absent from the files altogether: unit cost, holding-cost rate, order cost, lead time, on-hand inventory, receipts and supplier history. The raw CSVs remain git-ignored.

## What "top products" means

Items are ranked by actual holdout units. Class A is every item up to the volume at which cumulative units reach 80%, including the whole tie at that volume. It is defined neither by retail value nor by a headcount chosen in advance.

| Class | Items | Share of items | Holdout units | Share of units |
|---|---:|---:|---:|---:|
| A | 558 | 0.3883089770354906 | 88,230 | 0.8030399563120051 |
| B | 472 | 0.32846207376478775 | 16,486 | 0.15005005916082642 |
| C | 407 | 0.28322894919972164 | 5,154 | 0.04690998452716847 |
| All | 1,437 | 1 | 109,870 | 1 |

Class A thus runs to **558** items, about 80.3% of units — hardly a short list. Even after the ten busiest items, the cumulative share is still only 0.1265677619004278, which means volume is spread thinly across many products. The policy below covers those 558 items and no others.

## The forecast the policy used

Daily error is defined as `lgbm` minus `actual`. Across the whole file, the forecast runs high: bias is **2,824.6009022304675** units, a share of **0.025708572879134136**, with a WAPE of **0.6490765893903951** against a seasonal-naive WAPE of **0.777000091016656**.

Class A, however, points the other way. Its bias is **-5,020.5579692516685** units, a share of **-0.05690307116912239** — about 5.7% low — on **15,624** item-days, and its WAPE is **0.5137881782511478**. The file-level high bias, then, does not describe the very items a reorder point is written for. The decision nonetheless stands: do not debias. Construct did not subtract that gap from `lgbm`.

## How the quantities were built

Lead time is **7 days** — a single number, and an assumption. An order placed on day t becomes available at the start of day t+7; it cannot, therefore, serve the day on which it was placed. The inventory position is on hand plus on order, and lost sales do not deepen it.

For each item, expected lead-time demand is the mean of that item's 28 `lgbm` values, multiplied by 7. The order quantity is the smallest whole number of units that is at least that mean week, and at least 1. It is not an EOQ, and the search leaves it untouched.

Safety stock, by contrast, is an integer chosen item by item. The candidate from a normal-loss formula was simulated and then rejected as the policy: on **186** items it missed the cap, on **314** the search settled on a lower safety stock, and on **58** the two agree. The candidate safety stocks sum to **3,012**, whereas the safety stocks actually used sum to **4,079**. The reason is structural. The cap is a simulated unit shortfall, not a normal quantile; class A `lgbm` runs low, unmet demand is lost, and a typical item completes only a handful of cycles. The formula assumes none of that, which is why it could not be the policy.

The search tries safety stock 0, 1, 2 and so on, and it keeps the feasible integer with the lowest average end-of-day on-hand. On all 558 items, that turned out to be the smallest feasible integer.

No on-hand history exists. On the morning of 2016-04-25, therefore, on-hand is set equal to the reorder point and on-order to zero before the review, so every class A item places an order that morning. The first receipt arrives on **2016-05-02**, which means the first week is covered by the opening balance alone — a pivotal assumption, revisited under Risks.

Excel Solver was not run. No Solver binary was available, and no Solver answer was invented in its place. The integers come from the Python enumeration and are written into `reports/03-construct-solver.xlsx`, so that the workbook shows the same policy as the CSV; the example sheet is `Example_FOODS_3_090`.

## Results

The class A totals come from `data/processed/policy_summary.csv`:

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

The shortfall amounts to about 3.0% of units demanded, and the share of units sold is **0.9696070787689539**. The average on-hand that was minimized and the textbook expression are close on this window, yet they are not the same number; the search relied on the simulation throughout.

Note that the same policy does not deliver a 95% cycle service. Of **15,624** item-days, **722** had a shortfall, a day-level rate of **0.046210957501280084** — a rate that was never the constraint. Of **2,819** cycles, **601** had a stockout, a share of **0.21319616885420362**, or about 21% of cycles, leaving **0.7868038311457963** of cycles with no stockout at all. The median item has just **4** cycles. The plan warned against swapping these scores, and this window is precisely the case it had in mind.

The buffer, moreover, does not follow a volume ranking. Five busy items from `policy.csv` make the point:

| Item | Units demanded | Order quantity | Safety stock | Reorder point | Unit shortfall |
|---|---:|---:|---:|---:|---:|
| FOODS_3_090 | 3,357 | 713 | 38 | 750.8852726036218 | 0.04978097330842364 |
| FOODS_3_586 | 1,883 | 474 | 0 | 473.8546930978276 | 0.010698516676671493 |
| FOODS_3_120 | 1,617 | 435 | 0 | 434.0506172848497 | 0.04016659413429209 |
| FOODS_3_252 | 1,405 | 272 | 71 | 342.45635833336723 | 0.049497253855254636 |
| FOODS_3_681 | 1,253 | 230 | 193 | 422.7964730863048 | 0.04964367670685971 |

`FOODS_3_586` is the second-busiest item, yet its safety stock is 0. `FOODS_3_681` ranks fifth, and its safety stock of **193** is the largest in the file. Its `lgbm` summed to 919.1858923452189 against 1,253 actual, and the 193 is simply the smallest integer that brings that item under the cap. It is neither a debiased mean nor a reward for size.

The item closest to the cap is `FOODS_2_266`, with a shortfall of **0.049946516104229**, safety stock 5, order quantity 13 and reorder point 17.95326251764203, on 61 units demanded. The median item shortfall is **0.038070671837693734**; among items with a positive safety stock, it rises to **0.04308352428601003**. Given that the search stops at the first integer that clears 0.05, many rows sit close to the line. On `FOODS_3_090`, for instance, safety stock 37 yields a shortfall of **0.05007885832480732** and fails, whereas safety stock 38 passes.

## Risks

**Opening inventory.** The shelf starts at the reorder point rather than from a physical count, and a different opening balance would change both the shortfall and the average on-hand. Other openings were not tried. On `FOODS_3_090`, the first seven days of actual sales sum to **904**, which the opening balance does not cover; the item therefore stocks out before the first receipt, even with safety stock 38.

**One window, one store, one category.** The test spans 28 days in late April and May 2016. It proves nothing about a holiday quarter, another California store, or hobbies and household, and class B and class C receive no policy here.

**Lead time is assumed.** It is fixed at seven days, with no variability, because the files contain no supplier lead time. Moving that assumption would move the reorder point, and this project did not run a 3-day or 14-day grid to show by how much.

**Cycle service is the wrong headline.** About 21% of cycles had a stockout, so quoting 95% availability on the strength of the unit result would misstate the file. The result that cleared the cap is the unit shortfall of 0.030392921231046102.

**The class A forecast is low.** A buyer who adds the class A gap back into `lgbm` and also loads these safety stocks would buffer the same miss twice. Conversely, a buyer who trims the large buffers because the file-level forecast is high — about 2.6% on all food items — would be reading the wrong sign. On class A, the sign is negative.

**No dollars.** Units held are not a saving, and no holding-cost rate was simulated to turn them into one.

## Recommendation

Set the reorder point and the safety stock for each of the 558 class A items to the values already in `data/processed/policy.csv`, order seven days of that item's mean LightGBM forecast rather than an economic order quantity, and do not manage by cycle service, debias the forecast, or claim a dollar saving.

The interactive dashboard is [dashboards/class_a_policy_dashboard.html](../dashboards/class_a_policy_dashboard.html), and the Construct chart is [images/class_a_safety_stock.png](../images/class_a_safety_stock.png).
