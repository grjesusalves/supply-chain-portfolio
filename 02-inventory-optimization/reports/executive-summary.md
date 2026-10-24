# Executive summary — CA_3 food inventory

**Decision.** Set the reorder point and the safety stock for each of the 558 class A items to the values already in `data/processed/policy.csv`, order seven days of that item's mean LightGBM forecast rather than an economic order quantity, and do not manage by cycle service, debias the forecast, or claim a dollar saving.

The question was which reorder point and safety stock would keep stockouts under 5% while holding as few units as possible, for the top food items at Walmart store CA_3. "Top" carries a precise meaning here: class A from the holdout **2016-04-25 through 2016-05-22**, which comprises **558** items and **88,230** units, a share of **0.8030399563120051** of the **109,870** food units sold in that window. That is about 80.3% of units. It is not, however, a short list of bestsellers, given that the category has 1,437 food items in all. Class B and class C fall outside this decision.

## What the holdout showed

Of the **88,230** units demanded, the computed policy leaves **2,681.5674402151976** unfilled. The unfilled share is therefore **0.030392921231046102**, about 3.0% of units and comfortably under the 5% cap, while the share of units sold is **0.9696070787689539**. Not a single class A item missed the cap. Even the highest item shortfall — **0.049946516104229**, on `FOODS_2_266` — stays under 0.05.

Units held are units, not money — a distinction this page never blurs. Average on-hand across the 558 items sums to **14,461.064128366881**. Safety stock sums to **4,079**, and half the order quantity sums to **10,541.5**; taken together, those two pieces give the textbook units held, **14,620.5**. Strikingly, **193** of the 558 items need no safety stock at all, while the other **365** need a positive integer. The order quantity is simply seven days of each item's mean forecast, in whole units. It is not a cost formula.

## What not to conclude

Cycle service is not 95%, and it would be misleading to suggest otherwise. Of **2,819** replenishment cycles, **601** had a stockout — a share of **0.21319616885420362**, or about 21% of cycles — which leaves **0.7868038311457963** of cycles free of any stockout. A typical item, moreover, has only **4** cycles in this 28-day window, which means that percentage rests on a thin count. The constraint actually met is the share of units unfilled. The shelf should be managed to that, not to the cycle percentage.

Dollar savings will not be claimed. The files contain no unit cost, no holding-cost rate and no order cost, and the result names no supplier. Fewer units held is the objective that was used; it is not, and cannot honestly be presented as, a dollar figure.

Several assumptions sit beneath these numbers, and they deserve to be stated plainly. Lead time is an assumed **7 days**, given that the data record none. Unmet demand was treated as a lost sale, and an order is placed whenever the inventory position reaches the reorder point. The shelf was opened on 2016-04-25 already at the reorder point, and the first receipt arrives on 2016-05-02. A different opening balance was not tested, although it would change both the unfilled units and the units held. That assumption limits the claim: this is a forward rule scored on one window, not a reconstruction of what the store actually held.

The forecast was used as it stands. Note that on these class A items it runs low rather than high, by **-5,020.5579692516685** units — a share of **-0.05690307116912239**, or about 5.7% low. Even so, it should not be debiased before ordering, since the safety stocks were sized against the forecast as it is. The largest safety stock in the file, **193** units, belongs to `FOODS_3_681`, and it is there because that item's forecast is low, not because the item is the busiest. The busiest item, `FOODS_3_090`, carries a safety stock of 38.

Finally, Excel Solver was not run. The quantities come from a Python search over integer safety stocks, written into `reports/03-construct-solver.xlsx`, and this page does not recompute them. The interactive dashboard is [dashboards/class_a_policy_dashboard.html](../dashboards/class_a_policy_dashboard.html).

The policy, in short, meets its cap with room to spare on units, though not on cycles, and it should be adopted on exactly those terms. The planner page is [04-execute.md](04-execute.md); the longer story is [business-report.md](business-report.md).
