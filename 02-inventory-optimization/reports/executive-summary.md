# Executive summary — CA_3 food inventory

**Decision.** Set the reorder point and the safety stock for each of the 558 class A items to the values already in `data/processed/policy.csv`, order seven days of that item's mean LightGBM forecast rather than an economic order quantity, and do not manage by cycle service, debias the forecast, or claim a dollar saving.

The question was which reorder point and safety stock keep stockouts under 5% while holding as few units as possible, for the top food items at Walmart store CA_3. "Top" is class A from the holdout **2016-04-25 through 2016-05-22**: **558** items and **88,230** units, a share of **0.8030399563120051** of the **109,870** food units in that window. That is about 80.3% of units. It is not a short list of bestsellers. The category has 1,437 food items. Class B and class C are outside this decision.

## What the holdout showed

The policy already computed leaves **2,681.5674402151976** units unfilled out of **88,230** demanded. The unfilled share is **0.030392921231046102**, about 3.0% of units, under the 5% cap. The share of units sold is **0.9696070787689539**. No class A item missed the cap. The highest item shortfall is **0.049946516104229**, on `FOODS_2_266`, still under 0.05.

Units held are units, not money. Average on-hand across the 558 items sums to **14,461.064128366881**. Safety stock sums to **4,079**. Half the order quantity sums to **10,541.5**. Those two pieces together, the textbook units held, are **14,620.5**. **193** of the 558 items need no safety stock. The other **365** need a positive integer. The order quantity is seven days of that item's mean forecast, in whole units. It is not a cost formula.

## What not to conclude

Cycle service is not 95%. Of **2,819** replenishment cycles, **601** had a stockout, a share of **0.21319616885420362** (about 21% of cycles). The share of cycles with no stockout is **0.7868038311457963**. A typical item has only **4** cycles in this 28-day window, so that percentage is a thin count. The constraint that was met is the share of units unfilled. Do not manage the shelf to the cycle percentage.

Dollar savings will not be claimed. The files have no unit cost, no holding-cost rate, and no order cost, and this result names no supplier. Fewer units held is the objective that was used. It is not a dollar figure.

Lead time is an assumption of **7 days**. The data have no lead time. Unmet demand was treated as a lost sale, and an order is placed when the inventory position hits the reorder point. The shelf was opened on 2016-04-25 already at the reorder point. The first receipt is 2016-05-02. A different opening balance was not tested, and it would change both the unfilled units and the units held. That assumption limits the claim: this is a forward rule scored on one window, not a reconstruction of what the store held.

The forecast was used as it is. On these class A items it is low, not high: **-5,020.5579692516685** units, a share of **-0.05690307116912239** (about 5.7% low). Do not debias it before ordering. The largest safety stock in the file is **193** units on `FOODS_3_681`, because that item's forecast is low, not because it is the busiest item. The busiest item, `FOODS_3_090`, has safety stock 38.

Excel Solver was not run. The quantities are a Python search of integer safety stocks, written into `reports/03-construct-solver.xlsx`. This page does not recompute them. There is no dashboard yet.

The planner page is [04-execute.md](04-execute.md). The longer story is [business-report.md](business-report.md).
