# Execute — Freight cost (USAID SCMS)

PACE stage: **Execute**. This page ties together the savings scenario, the two write-ups, and the Tableau status. It neither fits a new formula nor publishes a workbook. The scorecard comes from Analyze and the log model from Construct, and both were checked again in `src/execute_freight.py`. Where this run prints a coefficient one digit longer than [03-construct.md](03-construct.md), the value is from that fit. The R-squared of the headline model matched `construct_metrics.csv`: **0.666**.

## How I would say this in an interview

I would lead with the decision. The typical weighed shipment costs **$7.26** per kilogram, not the mean of **$38.93**, and on the median air is the expensive mode. Charter's 66 percent gap is not a planning factor; the cautious figure, after dropping rates above the weighed-set 95th percentile, is about 21 percent, and even that is not dollars. Orgenics stays high. No country keeps the uncontrolled lead. Ocean's cheap median is tangled with DDP, at **193 / 282** model rows.

The dollar number is a what-if. Weighed air at or above the weighed-set median weight, **1,054.5** kg, is priced at the observed truck median on that slice, **$1.53**, but only where the air rate is higher: **1,477** notes, **4.76 million** kg, actual freight of **$33.1 million**, and a difference of **$25.8 million**. A 25 percent share of that gap is **$6.45 million**. Both are upper bounds. The **593** included-in-price shipments and the **239** invoiced-separately shipments are not in the figure, and the prices run from **2006-05-02** to **2015-09-14**. I did not publish Tableau Public.

## What we deliver

A hiring manager receives three things, and none of them is a published dashboard.

1. The one-page decision: [executive-summary.md](executive-summary.md).
2. The longer scorecard, model, and scenario: [business-report.md](business-report.md).
3. A reproducible what-if, not a coefficient, in `src/execute_freight.py`, with the note-level inputs in `data/processed/execute_scenario_air_notes.csv` and `data/processed/execute_scenario_truck_notes.csv` and the printed metrics in `data/processed/execute_scenario_result.csv`.

## The scenario

Population rule: weighed Air shipments whose Yes-line weight is at or above the median Yes-line weight of the weighed set (**1,054.5** kg). Given that air's own median weight is **656** kg, this cut is heavier than a typical air note; **1,664** weighed air notes clear it.

Counterfactual: the observed median freight per kilogram of weighed Truck shipments on that same weight slice, **$1.53**, n = **793**. Not ocean, not the charter coefficient, and not the all-truck median of **$2.50**.

Dollar difference: the sum of weight times (air rate minus that truck median), counted only where the air rate is higher. **187** heavy air notes are already at or below the truck median, and they add zero.

| | |
|---|---:|
| Notes in the sum | 1,477 |
| Kilograms | 4.76 million |
| Actual freight, USD | $33.1 million |
| Dollar difference, USD | $25.8 million |
| 25 percent of that difference, USD | $6.45 million |

The 25 percent share is not a selected subset of notes, and the plan named no share. Both figures are upper bounds.

Excluded from the sum, and not treated as zeros: included-in-price **593**, invoiced separately **239**, see-on-Yes-line **0**, weight not numeric **23**, and `ASN-22365` (weight 0). Blank mode is not in it (**79** weighed blank notes are at or above the cutoff). Charter is not moved (**301** weighed charters are at or above the cutoff). Ocean is not the counterfactual (**250** weighed ocean notes are at or above the cutoff), and **193 / 282** ocean model rows are DDP.

What would make it wrong: truck may not be feasible for the lane, the lead time, the cold chain, or the commodity; INCO can hide freight in the goods price; the dollars date from 2006–2015; the Yes-line rule itself; and note that the 4 kg charter (`DN-1683`, **$31,088** per kg) sits outside this weight cut and is not the source of the gap.

## Where Tableau Public fits

`dashboards/shipment_weighed.csv` is the weighed set, **6,174** rows, which this stage checked against the Yes-line rollup. It was not rewritten, and it has no savings column; a summed counterfactual on that file would look like an invoice. The what-if stays in the scenario CSVs.

`dashboards/TABLEAU.md` lists the sheets a public workbook should contain. Publishing that workbook is a manual step; this stage neither logged in nor published, and there is no public URL.

## Where to look

- One page: [executive-summary.md](executive-summary.md)
- Full report: [business-report.md](business-report.md)
- Scorecard: [02-analyze.md](02-analyze.md)
- Log model: [03-construct.md](03-construct.md)
- Scenario script: [src/execute_freight.py](../src/execute_freight.py)
