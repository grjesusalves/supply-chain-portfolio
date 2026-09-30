# Executive summary — freight cost (USAID SCMS)

Do not book a saving. On the shipments where freight and weight were both real numbers, the typical rate is the median, **$7.26** per kilogram, not the mean **$38.93**. Air is the expensive mode on that median. A logistics lead who wants a dollar figure gets a labeled what-if, not a regression coefficient: weighed air notes at or above **1,054.5** kg, priced at the observed truck median on that same slice, and only where the air rate is higher. That gap is **$25.8 million** on **1,477** notes. A quarter of it is **$6.45 million**. Both numbers are upper bounds. The prices are historical, delivered to client from **2006-05-02** through **2015-09-14**.

The longer page is [business-report.md](business-report.md). The stage note is [04-execute.md](04-execute.md).

## The rate I would plan from

The population is the weighed set: one row per `ASN/DN #`, freight and weight taken from the single First Line Designation = Yes line, weight greater than zero. **6,174** shipments. Median freight per kilogram **$7.26**. Mean **$38.93**. The mean is the tail. The maximum is **$31,088** on `DN-1683`, air charter, **4** kg, freight **$124,351**. The 95th percentile of the weighed set is **$67.65**.

Freight as a share of line-item value, where the value sum is positive: median **8.8%** on **6,186** shipments. Numeric Yes-line freight, counted once, is **$68.8 million** on the priced set and **$68.7 million** on the weighed set. Insurance is not in either figure.

Not in the rate, and not zeros: **593** included-in-price, **239** invoiced separately, **0** see-another-note on the Yes line, **23** weight not numeric, and **1** zero-weight note (`ASN-22365`).

## Mode, vendor, country

| Mode | Shipments | Weighed n | Median freight per kg |
|---|---:|---:|---:|
| Air | 4,541 | 4,096 | $10.02 |
| (blank) | 226 | 211 | $4.65 |
| Air Charter | 494 | 423 | $4.32 |
| Truck | 1,442 | 1,162 | $2.50 |
| Ocean | 327 | 282 | $1.68 |

Shipment counts are the Analyze scorecard (`data/processed/kpi_by_mode.csv`). Weighed counts and medians were recomputed from `dashboards/shipment_weighed.csv` after this stage checked that file against the Yes-line rollup. Blank is not a mode.

Inside 500–5,000 kg, air's median is still the high one: **$7.09** on **1,971** weighed air notes. Orgenics, Ltd stays high there: **390** notes, median **$15.12**, against that **$7.09**. SCMS from RDC is the largest vendor in that air band (**612** of 1,971) and sits below the reference, median **$5.66**.

No country keeps the uncontrolled lead. The highest country median on the weighed set, among countries with at least 20 weighed shipments, is Botswana: **38.94** on **62** shipments. Inside air and the 500–5,000 kg band that count is **7**. Seven is under the rank threshold of 20. I do not call Botswana expensive.

## What the regression does not let me say

OLS of log(freight per kilogram), HC1 95% intervals, named modes only. **5,963** rows (6,174 minus **211** blank). Reference mode Air (**4,096**). This stage refit that model. R-squared **0.666**.

Truck versus air: coefficient **−0.444**, interval **−0.513** to **−0.375**. exp(coefficient) − 1 = **−0.359**, about 36 percent lower. The interval excludes zero.

Air charter versus air: **0.504**, interval **0.400** to **0.609**. exp(coefficient) − 1 = **0.656**, about 66 percent higher. Do not use 66 percent as a planning factor. Charter looks cheap on the median because charter shipments are heavier. The mode-only log model has charter below air (coefficient **−0.413**). After log weight, charter is above air. Dropping rates above the weighed-set 95th percentile (**$67.65**) leaves **5,658** rows and shrinks the charter coefficient to **0.192**, exp(coefficient) − 1 = **0.211**, about 21 percent. That is the cautious figure. It is still not dollars.

Ocean versus air in the full model: **0.078**, interval **−0.046** to **0.203**, which includes zero. With mode and log weight only, ocean is still about 36 percent below air (exp(coefficient) − 1 = **−0.360**). **193 / 282** ocean rows in the model are DDP, and a DDP row is in the model only because the Yes line showed a number.

Orgenics versus everyone else: **0.573**, interval **0.495** to **0.650**. exp(coefficient) − 1 = **0.773**, about 77 percent higher. **599 / 600** of those model rows are air. That is not money to take out of a contract.

log(weight): **−0.505**, interval **−0.521** to **−0.489**. The per-kilogram rate is lower on heavier shipments. It is not a lever to ship heavier freight.

## The what-if, with the assumption on it

Rule, one sentence: a weighed Air shipment is in the scenario if its Yes-line weight is at or above the median Yes-line weight of the weighed set (**1,054.5** kg), and it adds to the dollar gap only when its freight per kilogram is above the observed median freight per kilogram of weighed Truck shipments on that same slice.

That truck median is **$1.53**, on **793** truck notes. It is not the all-truck median, and it is not the ocean median. It is not the charter coefficient.

| | |
|---|---:|
| Heavy air notes (weight ≥ 1,054.5 kg) | 1,664 |
| Of which the air rate is above the truck median | 1,477 |
| Kilograms on those 1,477 notes | 4.76 million |
| Actual freight on those 1,477 notes, USD | $33.1 million |
| Dollar difference, USD | $25.8 million |
| 25 percent of that difference, USD | $6.45 million |

**187** of the 1,664 heavy air notes are already at or below the truck median. They contribute nothing to the difference. The 25 percent figure is a quarter of the dollar gap. It is not a list of lanes I chose. Both figures assume those kilograms could have moved at the truck median. That is the assumption that would make the number wrong, together with these:

- Truck may be infeasible for the lane, the lead time, the cold chain, or the commodity.
- INCO terms can hide freight inside the goods price. The **593** included-in-price shipments and the **239** invoiced-separately shipments are not in this dollar figure. They were not set to zero.
- `ASN-22365` (weight 0) is not in it. Blank mode is not in it. Charter is not moved (**301** weighed charters sit at or above 1,054.5 kg and stay out). Ocean is not the counterfactual (**250** weighed ocean notes sit at or above the cutoff). **193 / 282** ocean model rows are DDP.
- The dollars are 2006–2015 prices. The Yes-line rule takes one freight string per note. The 4 kg charter at about 31,088 USD per kg is not in this scenario. Its weight is 4, which is below 1,054.5.

## Recommendation

Manage the rate you can see, and do not turn a coefficient into a budget cut. Use the median, about $7.26 per kg, as the description of a typical weighed shipment. Challenge Orgenics on air. Do not plan a charter premium off the 66 percent figure; if a charter comparison is needed at all, the cautious association is the p95 cut, about 21 percent, and it is still not a saving. Do not switch a lane to ocean because the ocean median is low. If a mode conversation happens, start from the heavy-air what-if above, label even the 25 percent share as an upper bound, and stop where truck is not actually available.

Tableau Public was not published. There is no URL.

## How I would say this in an interview

I would not open with the model. I would say the typical shipment in this extract cost **$7.26** per kilogram, and the mean of **$38.93** is a tail, including one 4 kilogram air charter at **$31,088** per kilogram. Air is the expensive mode on the median, **$10.02**, against truck **$2.50** and ocean **$1.68**.

Charter looks cheaper than air until weight is held constant. The full log model says about 66 percent higher than air, and I would not plan on that. After I drop rates above the 95th percentile, the same contrast is about 21 percent. Orgenics stays high, about 77 percent in that log model, and **599** of **600** of those rows are air. I would take that to procurement as a rate to challenge, not as a dollar to remove.

I would not call a country expensive off the uncontrolled median. Botswana leads that list and has only **7** weighed air shipments inside the weight band I used as a control. Ocean's cheap median is tangled with DDP: **193** of **282** ocean rows in the model are DDP, and DDP only enters when freight was a visible number.

The only dollar figure I would put on a slide is a what-if. Weighed air at or above **1,054.5** kilograms, priced at the truck median on that same slice, **$1.53**, and only where air is actually higher. That is **1,477** notes, **4.76 million** kilograms, **$33.1 million** of actual freight, and a difference of **$25.8 million**. A quarter of that difference is **$6.45 million**. Both are upper bounds. Truck may not be feasible, the invoice can hide freight, and these prices run from 2006-05-02 to 2015-09-14. I did not publish a Tableau workbook.
