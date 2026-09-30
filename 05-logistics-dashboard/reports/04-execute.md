# Execute — Logistics network and executive dashboard (Olist)

PACE stage: **Execute**. This is the page I would walk through with a logistics lead. It does not recompute a median, move a distance band, or attach a reais figure to a recommendation. The counts are Analyze. The page is Construct. Both are used as published.

## How I would say this in an interview

Leadership is not asking for a map. I would tell them three things, and I would not put a saving next to any of them.

Coverage is uneven. There are **96,096** customer people, **99,441** orders, and **3,095** sellers. Customers sit in **27** states. Sellers sit in **23**. São Paulo is **40,302** people (**41.9%**) and **1,849** sellers (**59.7%**). Rio de Janeiro is **12.9%** of the people and **5.5%** of the sellers. Paraná is seller-heavy: **5.1%** of the people and **11.3%** of the sellers. Alagoas, Tocantins, Amapá, and Roraima have customers and no seller. On the items that were delivered, **70,328 of 110,189** cross a state line. That is **63.8%**. The conversation is coverage. It is not a new building. A zip-prefix centroid is not a warehouse.

The extra days show up in transit, not in seller handling. On **96,470** delivered orders the median purchase-to-door time is **10.2 days**. Median transit is **7.1 days**. Median handling is **1.8 days**, and across the frozen bands it stays between **1.7 and 1.9**. Transit goes from **2.0 days** under 50 km to **13.2 days** at 1,000 km or more. The reported median purchase-to-door time is **16.4 days** in the longest band and **4.9 days** in the shortest. That is a difference of **11.5 days** in this extract. The reported median transit differs by **11.2 days** (**13.2** versus **2.0**). Handling differs by **0.2 days** (**1.9** versus **1.7**). Those are differences of the medians already on the page. They are not a forecast of days saved if a seller moved.

The promise already stretches, so the on-time rate hides the wait. Delivered on or before the promised calendar date: **89,936 / 96,470 = 93.2%**. The longest band is still about **89.6%** on time, and the median wait there is **16.4 days**. I would not let 93% close the meeting. Days sit next to the rate.

Freight per item rises with distance. It is not a rate card. Total freight on delivered items is **R$2,202,835.80**. Median freight per item is **R$16.26**, and the band medians are **R$9.06, R$11.92, R$15.70, R$17.75, and R$25.38**. The longest band's median is **R$16.32** above the shortest band's median. That is a difference of two medians in this extract, not a surcharge to remove. Freight per kilogram dips in the 50–200 km band and then rises. The median item in that band is heavier. Weight is in the mix. I would not reprice from the raw slope, and I would not quote a saving. Currency is reais. I would not convert it.

## What we deliver

A weekly reader gets three things, and none of them is a Tableau workbook.

1. The weekly page, already published: <https://grjesusalves.github.io/supply-chain-portfolio/05-logistics-dashboard/>. The same file in the repo is [dashboards/logistics_weekly.html](../dashboards/logistics_weekly.html).
2. The recommendation below. Coverage, transit, and the promise are three conversations. Freight is a fourth, and it does not end in a price change.
3. The SQL that defines the numbers the page uses: `sql/kpi_definitions.sql`, `sql/kpi_analyze.sql`, and `sql/kpi_construct.sql`.

The one-page version is [executive-summary.md](executive-summary.md). The longer write-up is [business-report.md](business-report.md).

The file is a historical extract. Delivered purchases run from **15 Sep 2016** through **29 Aug 2018**. All purchases in the file run from **4 Sep 2016** through **17 Oct 2018**. It is not a live feed.

## Question

Where are our customers relative to our sellers, how does distance sit next to delivery time and freight cost, and what does leadership need to see weekly?

## Answer

Customers and sellers do not sit in the same places, the extra wait is in transit, and the weekly page has to show days beside the on-time rate.

| What leadership asked | What this extract shows |
|---|---|
| Where are the people, and where are the sellers? | SP is 41.9% of people and 59.7% of sellers. RJ is 12.9% of people and 5.5% of sellers. PR is 5.1% of people and 11.3% of sellers. AL, TO, AP, and RR have customers and no seller. |
| How much volume crosses a state? | 70,328 / 110,189 delivered items = 63.8%. |
| Does a longer haul show up as a slower delivery? | Transit median 2.0 days under 50 km, 13.2 days at 1,000 km or more. Handling stays 1.7–1.9 days. |
| Does "on time" mean fast? | No. 93.2% on time overall. About 89.6% on time in the longest band, where the median wait is 16.4 days. |
| Does freight rise with distance? | Median freight per item rises across every longer band, from R$9.06 to R$25.38. Freight per kilogram does not. It dips, then rises. |

**1,275** delivered orders have more than one seller. Delivery time on those orders uses the farthest seller. Freight stays on the item. **538** delivered items and **478** delivered orders have no distance. They stay in the weekly totals and out of the band table.

## Recommendation

Run four checks off the weekly page. Do not turn any of them into a savings target.

**Coverage.** Keep customers by state next to sellers by state. São Paulo holds most of the sellers. Rio de Janeiro has a larger share of people than of sellers. Paraná is the reverse. Four states have customers and no seller at all. **63.8%** of delivered items already cross a state. A logistics lead uses that picture to talk about coverage. This extract does not choose a city for a new building.

**Transit, not handling.** When the wait is long, look at the haul, not at seller handling. Handling is flat. The extra days are in transit. The **11.5 day** gap in reported median purchase-to-door, and the **11.2 day** gap in reported median transit, are differences inside this extract. They are not a promise that moving a seller would give those days back.

**The promise.** Report median purchase-to-door days and median transit days next to the on-time rate, every week. **93.2%** on time, and about **89.6%** in the longest band, can sit on top of a **16.4 day** wait. Do not manage the network to the rate alone. The estimate is already looser where the haul is longer. This file does not say how that estimate was built.

**Freight.** Read median freight per item next to the band, and do not reprice from that slope. The medians rise from **R$9.06** to **R$25.38**. Freight per kilogram dips in the 50–200 km band and then rises, and the median item there is heavier. That is consistent with a weight mix. It is not a cause. A finance partner who wants a saving will not find one here. None is estimated.

## What we deliberately did not do

- **No dollar impact, and no conversion to dollars.** The file is in Brazilian reais. A dollar figure would be a rate we invented, or a saving the bands do not support.
- **No causal claim.** The bands are a cross-section of this extract. Kilometers are not shown to cause the extra transit or the higher freight. There is no carrier name in the file.
- **No warehouse and no routing solver.** Uneven coverage is a fact about these states. It is not a site recommendation.
- **No new distance, and no retuned bands.** The five cuts stayed frozen. Haversine kilometers are not road kilometers.
- **No review score, and no live feed.** The page is the seven items Construct already published.

## Where the dashboard is

The dashboard is the HTML page. It is published at <https://grjesusalves.github.io/supply-chain-portfolio/05-logistics-dashboard/>.

Tableau Public is the tool the plan named, and it was not published. There is no Tableau Public URL. Do not look for one. `dashboards/TABLEAU.md` is the sheet list if that publish happens later. The extracts are `data/processed/weekly_scorecard.csv`, `data/processed/distance_bands.csv`, and `data/processed/state_coverage.csv`.

## Where to look

- One page: [executive-summary.md](executive-summary.md)
- Full report: [business-report.md](business-report.md)
- Scorecard: [02-analyze.md](02-analyze.md)
- The page and the frozen bands: [03-construct.md](03-construct.md)
- Weekly HTML in the repo: [dashboards/logistics_weekly.html](../dashboards/logistics_weekly.html)
