# Execute — Logistics network and executive dashboard (Olist)

PACE stage: **Execute**. This is the page I would walk through with a logistics lead. It neither recomputes a median, nor moves a distance band, nor attaches a reais figure to a recommendation. The counts come from Analyze and the page from Construct, and both are used as published.

## How I would say this in an interview

Leadership is not asking for a map. I would tell them three things, and I would not put a saving next to any of them.

Coverage is uneven. There are **96,096** customer people, **99,441** orders, and **3,095** sellers; customers sit in **27** states, sellers in **23**. São Paulo accounts for **40,302** people (**41.9%**) and **1,849** sellers (**59.7%**). Rio de Janeiro holds **12.9%** of the people but only **5.5%** of the sellers, while Paraná is seller-heavy, with **5.1%** of the people and **11.3%** of the sellers. Alagoas, Tocantins, Amapá, and Roraima have customers and no seller. Of the items that were delivered, **70,328 of 110,189** cross a state line, or **63.8%**. The conversation, then, is coverage, not a new building; a zip-prefix centroid is not a warehouse.

The extra days show up in transit, not in seller handling. On **96,470** delivered orders, the median purchase-to-door time is **10.2 days**, median transit **7.1 days**, and median handling **1.8 days**, which stays between **1.7 and 1.9** across the frozen bands. Transit, by contrast, rises from **2.0 days** under 50 km to **13.2 days** at 1,000 km or more. The reported median purchase-to-door time is **16.4 days** in the longest band and **4.9 days** in the shortest, a difference of **11.5 days** in this extract. Reported median transit differs by **11.2 days** (**13.2** versus **2.0**), and handling by **0.2 days** (**1.9** versus **1.7**). Those are differences between medians already on the page; they are not a forecast of days saved if a seller moved.

The promise already stretches, so the on-time rate hides the wait. Delivered on or before the promised calendar date: **89,936 / 96,470 = 93.2%**. The longest band is still about **89.6%** on time, even though its median wait is **16.4 days**. I would not let 93% close the meeting; days belong next to the rate.

Freight per item rises with distance, but it is not a rate card. Total freight on delivered items is **R$2,202,835.80**, median freight per item is **R$16.26**, and the band medians run **R$9.06, R$11.92, R$15.70, R$17.75, and R$25.38**. The longest band's median sits **R$16.32** above the shortest band's: a difference of two medians in this extract, not a surcharge to remove. Freight per kilogram dips in the 50–200 km band, where the median item is heavier, and then rises, so weight is in the mix. I would not reprice from the raw slope, and I would not quote a saving. Currency is reais, and I would not convert it.

## What we deliver

A weekly reader receives three things, and none of them is a Tableau workbook.

1. The weekly page, already published: <https://grjesusalves.github.io/supply-chain-portfolio/05-logistics-dashboard/>. The same file in the repo is [dashboards/logistics_weekly.html](../dashboards/logistics_weekly.html).
2. The recommendation below. Coverage, transit, and the promise are three conversations; freight is a fourth, and it does not end in a price change.
3. The SQL that defines the numbers the page uses: `sql/kpi_definitions.sql`, `sql/kpi_analyze.sql`, and `sql/kpi_construct.sql`.

The one-page version is [executive-summary.md](executive-summary.md), and the longer write-up is [business-report.md](business-report.md).

The file is a historical extract, not a live feed. Delivered purchases run from **15 Sep 2016** through **29 Aug 2018**, and all purchases in the file from **4 Sep 2016** through **17 Oct 2018**.

## Question

Where are our customers relative to our sellers, how does distance sit next to delivery time and freight cost, and what does leadership need to see weekly?

## Answer

Customers and sellers do not sit in the same places, the extra wait accumulates in transit, and the weekly page must therefore show days beside the on-time rate.

| What leadership asked | What this extract shows |
|---|---|
| Where are the people, and where are the sellers? | SP is 41.9% of people and 59.7% of sellers. RJ is 12.9% of people and 5.5% of sellers. PR is 5.1% of people and 11.3% of sellers. AL, TO, AP, and RR have customers and no seller. |
| How much volume crosses a state? | 70,328 / 110,189 delivered items = 63.8%. |
| Does a longer haul show up as a slower delivery? | Transit median 2.0 days under 50 km, 13.2 days at 1,000 km or more. Handling stays 1.7–1.9 days. |
| Does "on time" mean fast? | No. 93.2% on time overall. About 89.6% on time in the longest band, where the median wait is 16.4 days. |
| Does freight rise with distance? | Median freight per item rises across every longer band, from R$9.06 to R$25.38. Freight per kilogram does not. It dips, then rises. |

**1,275** delivered orders have more than one seller; delivery time on those orders uses the farthest seller, while freight stays on the item. **538** delivered items and **478** delivered orders have no distance; they stay in the weekly totals and out of the band table.

## Recommendation

Run four checks off the weekly page, and do not turn any of them into a savings target.

**Coverage.** Keep customers by state next to sellers by state. São Paulo holds most of the sellers; Rio de Janeiro has a larger share of people than of sellers; Paraná is the reverse; and four states have customers and no seller at all. **63.8%** of delivered items already cross a state. A logistics lead uses that picture to discuss coverage, but this extract does not choose a city for a new building.

**Transit, not handling.** When the wait is long, look at the haul rather than at seller handling. Handling is flat; the extra days are in transit. The **11.5 day** gap in reported median purchase-to-door, and the **11.2 day** gap in reported median transit, are differences inside this extract, not a promise that moving a seller would give those days back.

**The promise.** Report median purchase-to-door days and median transit days next to the on-time rate, every week. **93.2%** on time, and about **89.6%** in the longest band, can sit on top of a **16.4 day** wait, so the network should not be managed to the rate alone. The estimate is already looser where the haul is longer, although this file does not say how that estimate was built.

**Freight.** Read median freight per item next to the band, and do not reprice from that slope. The medians rise from **R$9.06** to **R$25.38**, yet freight per kilogram dips in the 50–200 km band before rising, and the median item there is heavier. That is consistent with a weight mix; it is not a cause. A finance partner looking for a saving will not find one here, because none is estimated.

## What we deliberately did not do

- **No dollar impact, and no conversion to dollars.** The file is in Brazilian reais; a dollar figure would rest on a rate we invented, or on a saving the bands do not support.
- **No causal claim.** The bands are a cross-section of this extract. Kilometers are not shown to cause the extra transit or the higher freight, and the file names no carrier.
- **No warehouse and no routing solver.** Uneven coverage is a fact about these states, not a site recommendation.
- **No new distance, and no retuned bands.** The five cuts stayed frozen, and haversine kilometers are not road kilometers.
- **No review score, and no live feed.** The page consists of the seven items Construct already published.

## Where the dashboard is

The dashboard is the interactive HTML page, published at <https://grjesusalves.github.io/supply-chain-portfolio/05-logistics-dashboard/>. Tooltips, the weekly date range, band highlighting, and the state picker change only the view; the KPI cards stay full-period.

Tableau Public is the tool the plan named, and it was not published, so there is no Tableau Public URL to look for. Should that publication happen later, `dashboards/TABLEAU.md` is the sheet list, and the extracts are `data/processed/weekly_scorecard.csv`, `data/processed/distance_bands.csv`, and `data/processed/state_coverage.csv`.

## Where to look

- One page: [executive-summary.md](executive-summary.md)
- Full report: [business-report.md](business-report.md)
- Scorecard: [02-analyze.md](02-analyze.md)
- The page and the frozen bands: [03-construct.md](03-construct.md)
- Weekly HTML in the repo: [dashboards/logistics_weekly.html](../dashboards/logistics_weekly.html)
