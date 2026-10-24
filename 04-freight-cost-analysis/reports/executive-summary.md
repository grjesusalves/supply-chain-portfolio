# Executive summary — freight cost (USAID SCMS)

Do not book a saving. On the shipments where freight and weight were both real numbers, the typical rate is the median, **$7.26** per kilogram, not the mean of **$38.93**, and on that median air is the expensive mode. A logistics lead who wants a dollar figure receives a labeled what-if rather than a regression coefficient: weighed air notes at or above **1,054.5** kg, priced at the observed truck median on that same slice, and counted only where the air rate is higher. That gap is **$25.8 million** on **1,477** notes, and a quarter of it is **$6.45 million**. Both numbers are upper bounds, and the prices are historical, delivered to client from **2006-05-02** through **2015-09-14**.

The longer page is [business-report.md](business-report.md), and the stage note is [04-execute.md](04-execute.md).

## The rate I would plan from

**6,174** shipments make up the weighed set: one row per `ASN/DN #`, with freight and weight taken from the single First Line Designation = Yes line, and weight greater than zero. The median freight per kilogram is **$7.26**; the mean is **$38.93**. That mean is the tail. The maximum, **$31,088**, belongs to `DN-1683`, an air charter of **4** kg carrying freight of **$124,351**, while the 95th percentile of the weighed set is **$67.65**.

Freight as a share of line-item value, where the value sum is positive, has a median of **8.8%** on **6,186** shipments. Numeric Yes-line freight, counted once, totals **$68.8 million** on the priced set and **$68.7 million** on the weighed set; insurance is in neither figure.

Excluded from the rate, and not treated as zeros: **593** included-in-price, **239** invoiced separately, **0** see-another-note on the Yes line, **23** with weight not numeric, and **1** zero-weight note (`ASN-22365`).

## Mode, vendor, country

| Mode | Shipments | Weighed n | Median freight per kg |
|---|---:|---:|---:|
| Air | 4,541 | 4,096 | $10.02 |
| (blank) | 226 | 211 | $4.65 |
| Air Charter | 494 | 423 | $4.32 |
| Truck | 1,442 | 1,162 | $2.50 |
| Ocean | 327 | 282 | $1.68 |

Shipment counts come from the Analyze scorecard (`data/processed/kpi_by_mode.csv`). Weighed counts and medians were recomputed from `dashboards/shipment_weighed.csv` after this stage checked that file against the Yes-line rollup. Note that blank is not a mode.

Inside 500–5,000 kg, air's median remains the high one, at **$7.09** on **1,971** weighed air notes. Orgenics, Ltd stays high there too: **390** notes at a median of **$15.12**, against that **$7.09**. SCMS from RDC, the largest vendor in that air band (**612** of 1,971), sits below the reference, at a median of **$5.66**.

No country keeps the uncontrolled lead. The highest country median on the weighed set, among countries with at least 20 weighed shipments, is Botswana's: **38.94** on **62** shipments. Inside air and the 500–5,000 kg band, however, that count falls to **7**, under the rank threshold of 20. I do not call Botswana expensive.

## What the regression does not let me say

**5,963** rows (6,174 minus **211** blank) enter an OLS of log(freight per kilogram), with HC1 95% intervals and named modes only. The reference mode is Air (**4,096**). This stage refit that model, and its R-squared is **0.666**.

Truck versus air: coefficient **−0.444**, interval **−0.513** to **−0.375**. exp(coefficient) − 1 = **−0.359**, about 36 percent lower, and the interval excludes zero.

Air charter versus air: **0.504**, interval **0.400** to **0.609**. exp(coefficient) − 1 = **0.656**, about 66 percent higher. That 66 percent should not be used as a planning factor. Charter looks cheap on the median because charter shipments are heavier; the mode-only log model places charter below air (coefficient **−0.413**), and only after log weight does charter move above air. Dropping rates above the weighed-set 95th percentile (**$67.65**) leaves **5,658** rows and shrinks the charter coefficient to **0.192**, exp(coefficient) − 1 = **0.211**, about 21 percent. That is the cautious figure, and it is still not dollars.

Ocean versus air in the full model: **0.078**, interval **−0.046** to **0.203**, which includes zero. With mode and log weight only, ocean is still about 36 percent below air (exp(coefficient) − 1 = **−0.360**). That said, **193 / 282** ocean rows in the model are DDP, and a DDP row enters the model only because its Yes line showed a number.

Orgenics versus everyone else: **0.573**, interval **0.495** to **0.650**. exp(coefficient) − 1 = **0.773**, about 77 percent higher, and **599 / 600** of those model rows are air. That is not money to take out of a contract.

log(weight): **−0.505**, interval **−0.521** to **−0.489**. The per-kilogram rate is lower on heavier shipments; it is not, however, a lever to ship heavier freight.

## The what-if, with the assumption on it

The rule, in one sentence: a weighed Air shipment enters the scenario if its Yes-line weight is at or above the median Yes-line weight of the weighed set (**1,054.5** kg), and it adds to the dollar gap only when its freight per kilogram exceeds the observed median freight per kilogram of weighed Truck shipments on that same slice.

That truck median is **$1.53**, on **793** truck notes. It is neither the all-truck median, nor the ocean median, nor the charter coefficient.

| | |
|---|---:|
| Heavy air notes (weight ≥ 1,054.5 kg) | 1,664 |
| Of which the air rate is above the truck median | 1,477 |
| Kilograms on those 1,477 notes | 4.76 million |
| Actual freight on those 1,477 notes, USD | $33.1 million |
| Dollar difference, USD | $25.8 million |
| 25 percent of that difference, USD | $6.45 million |

**187** of the 1,664 heavy air notes are already at or below the truck median, so they contribute nothing to the difference. The 25 percent figure is a quarter of the dollar gap, not a list of lanes I chose. Both figures assume those kilograms could have moved at the truck median; that assumption, together with the ones below, is what would make the number wrong:

- Truck may be infeasible for the lane, the lead time, the cold chain, or the commodity.
- INCO terms can hide freight inside the goods price. The **593** included-in-price shipments and the **239** invoiced-separately shipments are not in this dollar figure; they were not set to zero.
- `ASN-22365` (weight 0) is not in it, and neither is blank mode. Charter is not moved (**301** weighed charters sit at or above 1,054.5 kg and stay out). Ocean is not the counterfactual (**250** weighed ocean notes sit at or above the cutoff), and **193 / 282** ocean model rows are DDP.
- The dollars are 2006–2015 prices, and the Yes-line rule takes one freight string per note. The 4 kg charter at about 31,088 USD per kg is not in this scenario, given that its weight of 4 is below 1,054.5.

## Recommendation

Manage the rate you can see, and do not turn a coefficient into a budget cut. Use the median, about $7.26 per kg, to describe a typical weighed shipment, and challenge Orgenics on air. Do not plan a charter premium from the 66 percent figure; if a charter comparison is needed at all, the cautious association is the p95 cut, about 21 percent, and even that is not a saving. Do not switch a lane to ocean merely because the ocean median is low. If a mode conversation does happen, start from the heavy-air what-if above, label even the 25 percent share as an upper bound, and stop wherever truck is not actually available.

Tableau Public was not published, so there is no URL.

## How I would say this in an interview

I would not open with the model. I would say that the typical shipment in this extract cost **$7.26** per kilogram, and that the mean of **$38.93** is a tail, one that includes a 4 kilogram air charter at **$31,088** per kilogram. On the median, air is the expensive mode, at **$10.02**, against truck at **$2.50** and ocean at **$1.68**.

Charter looks cheaper than air until weight is held constant. The full log model puts it about 66 percent above air, and I would not plan on that; once I drop rates above the 95th percentile, the same contrast is about 21 percent. Orgenics stays high, about 77 percent in that log model, and **599** of **600** of those rows are air. I would take that to procurement as a rate to challenge, not as a dollar to remove.

I would not call a country expensive on the strength of the uncontrolled median. Botswana leads that list, yet it has only **7** weighed air shipments inside the weight band I used as a control. Ocean's cheap median, meanwhile, is tangled with DDP: **193** of **282** ocean rows in the model are DDP, and DDP enters only when freight was a visible number.

The only dollar figure I would put on a slide is a what-if: weighed air at or above **1,054.5** kilograms, priced at the truck median on that same slice, **$1.53**, and only where air is actually higher. That comes to **1,477** notes, **4.76 million** kilograms, **$33.1 million** of actual freight, and a difference of **$25.8 million**; a quarter of that difference is **$6.45 million**. Both are upper bounds. Truck may not be feasible, the invoice can hide freight, and these prices run from 2006-05-02 to 2015-09-14. I did not publish a Tableau workbook.