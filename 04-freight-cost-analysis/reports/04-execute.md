# Execute — Freight cost (USAID SCMS)

PACE stage: **Execute**. This page ties the savings scenario, the two write-ups, and the Tableau status. It does not refit a new formula and it does not publish a workbook. The scorecard is Analyze. The log model is Construct. Both were checked again in `src/execute_freight.py`. Where this run prints a coefficient one digit longer than [03-construct.md](03-construct.md), the value is that fit. The R-squared of the headline model matched `construct_metrics.csv`: **0.6660299231602032**.

## How I would say this in an interview

I would lead with the decision. The typical weighed shipment is **7.263901636359817** USD per kilogram, not the mean of **38.93012311964861**. Air is the expensive mode on the median. Charter's 66 percent gap is not a planning factor; the cautious figure, after dropping rates above the weighed-set 95th percentile, is about 21 percent, exp(coefficient) − 1 = **0.21122129787951574**, and it is still not dollars. Orgenics stays high. No country keeps the uncontrolled lead. Ocean's cheap median is tangled with DDP, **193 / 282** model rows.

The dollar number is a what-if. Weighed air at or above the weighed-set median weight, **1054.5** kg, priced at the observed truck median on that slice, **1.5292046183450931**, only where the air rate is higher. **1,477** notes, **4761674.0** kg, actual freight **33085383.96** USD, difference **25803810.088146247** USD. A 25 percent share of that gap is **6450952.522036562** USD. Both are upper bounds. The **593** included-in-price shipments and the **239** invoiced-separately shipments are not in the figure. The prices run from **2006-05-02** to **2015-09-14**. I did not publish Tableau Public.

## What we deliver

A hiring manager gets three things, and none of them is a published dashboard.

1. The one-page decision: [executive-summary.md](executive-summary.md).
2. The longer scorecard, model, and scenario: [business-report.md](business-report.md).
3. A reproducible what-if, not a coefficient, in `src/execute_freight.py`, with the note-level inputs in `data/processed/execute_scenario_air_notes.csv` and `data/processed/execute_scenario_truck_notes.csv` and the printed metrics in `data/processed/execute_scenario_result.csv`.

## The scenario

Population rule: weighed Air shipments whose Yes-line weight is at or above the median Yes-line weight of the weighed set (**1054.5** kg). Air's own median weight is **656.0** kg, so this cut is heavier than a typical air note. **1,664** weighed air notes clear it.

Counterfactual: the observed median freight per kilogram of weighed Truck shipments on that same weight slice, **1.5292046183450931**, n = **793**. Not ocean. Not the charter coefficient. Not the all-truck median of **2.5032950842130273**.

Dollar difference: sum of weight times (air rate minus that truck median), only where the air rate is higher. **187** heavy air notes are already at or below the truck median and add zero.

| | |
|---|---:|
| Notes in the sum | 1,477 |
| Kilograms | 4761674.0 |
| Actual freight, USD | 33085383.96 |
| Dollar difference, USD | 25803810.088146247 |
| 25 percent of that difference, USD | 6450952.522036562 |

The 25 percent share is not a selected subset of notes. The plan named no share. Both figures are upper bounds.

Not in the sum, and not zeros: included-in-price **593**, invoiced separately **239**, see-on-Yes-line **0**, weight not numeric **23**, `ASN-22365` (weight 0). Blank mode is not in it (**79** weighed blank notes are at or above the cutoff). Charter is not moved (**301** weighed charters are at or above the cutoff). Ocean is not the counterfactual (**250** weighed ocean notes are at or above the cutoff), and **193 / 282** ocean model rows are DDP.

What would make it wrong: truck may not be feasible for the lane, the lead time, the cold chain, or the commodity; INCO can hide freight in the goods price; the dollars are 2006–2015; the Yes-line rule; the 4 kg charter (`DN-1683`, **31087.705** per kg) is outside this weight cut and is not the source of the gap.

## Where Tableau Public fits

`dashboards/shipment_weighed.csv` is the weighed set. This stage checked it against the Yes-line rollup. **6,174** rows. It was not rewritten. It has no savings column. A summed counterfactual on that file would look like an invoice. The what-if stays in the scenario CSVs.

`dashboards/TABLEAU.md` lists the sheets a public workbook should have. Publishing that workbook is a manual step. This stage did not log in and did not publish. There is no public URL.

## Where to look

- One page: [executive-summary.md](executive-summary.md)
- Full report: [business-report.md](business-report.md)
- Scorecard: [02-analyze.md](02-analyze.md)
- Log model: [03-construct.md](03-construct.md)
- Scenario script: [src/execute_freight.py](../src/execute_freight.py)
