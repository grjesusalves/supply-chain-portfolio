# Executive summary — logistics network (Olist)

**Decision.** Do not manage this network from the **93.2%** on-time rate, and do not reprice freight from the rise in freight per item. Coverage is uneven, the extra days accumulate in transit, and the promise already stretches with distance. No saving is claimed, and currency stays in reais.

The interactive weekly page is the decision tool: <https://grjesusalves.github.io/supply-chain-portfolio/05-logistics-dashboard/>. Note that it is a historical extract, not a live feed; delivered purchases run from **15 Sep 2016** through **29 Aug 2018**.

## What to do

**Talk about coverage, not a new building.** Of **96,096** customer people, São Paulo accounts for **40,302 (41.9%)**, yet it also hosts **1,849 of 3,095** sellers (**59.7%**). Rio de Janeiro holds **12.9%** of the people but only **5.5%** of the sellers, while Paraná is seller-heavy, with **5.1%** of the people and **11.3%** of the sellers. Alagoas, Tocantins, Amapá, and Roraima have customers and no seller at all. **70,328 of 110,189** delivered items cross a state (**63.8%**). That is the coverage picture; a centroid, after all, is not a warehouse.

**Send a long wait to transit, not to seller handling.** On **96,470** delivered orders, median purchase-to-door is **10.2 days**, median transit **7.1 days**, and median handling **1.8 days**. Handling stays between **1.7 and 1.9** days across the frozen bands, whereas transit climbs from **2.0 days** under 50 km to **13.2 days** at 1,000 km or more. The reported medians in those two bands differ by **11.5 days** of purchase-to-door (**16.4** versus **4.9**) and by **11.2 days** of transit. That is a difference in this extract, not a forecast of days saved.

**Keep days next to the on-time rate.** **89,936 / 96,470** delivered orders are on time by calendar date (**93.2%**). The longest band is still about **89.6%** on time, with a median wait of **16.4 days**. A high rate, in short, is not a short wait.

**Do not reprice from the freight slope.** Total freight is **R$2,202,835.80**, and median freight per item is **R$16.26**, rising through **R$9.06, R$11.92, R$15.70, R$17.75, R$25.38** across the five bands. Freight per kilogram, however, dips in the 50–200 km band before rising, so weight is in that mix. The **R$16.32** gap between the longest and shortest freight medians is a difference of two medians, not a saving.

## What not to conclude

Distance is not shown to cause the extra days or the higher freight. The file has no carrier, and there is no dollar impact. **538** delivered items and **478** delivered orders have no distance and stay out of the band table, and **1,275** multi-seller delivered orders keep the farthest-seller rule for the clock. The HTML page is the dashboard; there is no Tableau Public URL.

The stage note is [04-execute.md](04-execute.md), and the longer story is [business-report.md](business-report.md).