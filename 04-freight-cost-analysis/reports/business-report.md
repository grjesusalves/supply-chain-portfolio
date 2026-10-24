# Business report — freight cost on USAID SCMS shipments

This report is written for a procurement lead, a logistics lead, and a finance partner. The one-page version is [executive-summary.md](executive-summary.md), and the stage note is [04-execute.md](04-execute.md). Note that nothing here treats a regression coefficient as money that was saved.

## Question

What drives freight cost across vendors, countries, and shipping modes, and where could money come out?

The person who can act on the answer differs in each case. Procurement can challenge a vendor that stays expensive inside air and inside a weight band. Logistics can examine mode, but only on shipments heavy enough for a cheaper mode to be a genuine conversation. Finance can weigh a dollar figure only if the denominator, the dropped rows, and the assumption are all on the page.

Delivered to client runs from **2006-05-02** through **2015-09-14**. This is a public historical extract of USAID supply-chain shipments of antiretrovirals and HIV lab commodities, not USAID's internal decision file, and these are not current market rates.

## What a row is

A row in the file is a line item; the money is not. Freight is one charge on a delivery note, and the note is `ASN/DN #`.

The rule, accepted on 2026-09-29 and not reopened here, is one row per ASN/DN. The freight string and the weight string come from the single line where First Line Designation = Yes. Line-item value is summed, while freight is neither summed nor averaged across lines. This stage did not parse the strings a second way; `src/execute_freight.py` calls the Yes-line rollup in `src/analyze_freight.py`.

Insurance is not in the rate. Manufacturing site is not on the scorecard either, given that it is not constant on the note and this rule does not pick a site.

## Who is in the rate, and who is out

| Step | Shipments | What happened |
|---|---:|---|
| Yes-line rollup | 7,030 | One row per ASN/DN |
| Included in commodity cost | 593 | Out. Not zero |
| Invoiced separately | 239 | Out. Not zero |
| See pointer on the Yes line | 0 | Counted. None |
| Weight captured separately | 23 | Freight parsed. No denominator |
| Weight not positive | 1 | `ASN-22365`, weight 0 |
| Weighed set | 6,174 | The rate's population |
| Blank mode, weighed | 211 | Not a mode. Out of the regression. Not imputed |

6,174 + 593 + 239 + 0 + 23 + 1 = 7,030. Priced shipments, with numeric freight, number **6,198**; freight-to-value, with numeric freight and a positive value sum, covers **6,186**.

A blank shipment mode is a missing label, not a fifth mode. It covers **226** shipments, **211** of them weighed, at a median freight per kilogram of **$4.65**. They stay out of every mode comparison I would say out loud, and out of the savings scenario as well.

## Headline

On the weighed set:

| | |
|---|---:|
| Median freight per kg | $7.26 |
| Mean freight per kg | $38.93 |
| 95th percentile | $67.65 |
| Maximum | $31,088 |
| Median freight / line-item value | 8.8% |
| Numeric freight, priced set, USD | $68.8 million |
| Numeric freight, weighed set, USD | $68.7 million |

The maximum is `DN-1683`, an Air Charter weighing **4** kg with freight of **$124,351**. One light charter is enough to pull a mean. A logistics lead acts on the median, and treats the tail as a tail; I would not quote $38.93 per kg as what a shipment costs.

## Mode

The weighed medians below were recomputed from `dashboards/shipment_weighed.csv` after this stage confirmed that the file is the weighed set (6,174 rows, not rewritten). Shipment counts come from `data/processed/kpi_by_mode.csv`.

| Mode | Shipments | Weighed n | Median freight per kg |
|---|---:|---:|---:|
| Air | 4,541 | 4,096 | $10.02 |
| (blank) | 226 | 211 | $4.65 |
| Air Charter | 494 | 423 | $4.32 |
| Truck | 1,442 | 1,162 | $2.50 |
| Ocean | 327 | 282 | $1.68 |

Air is the expensive named mode on the median. Charter's median sits below air's and above truck's and ocean's. That said, this unconditional order is not the regression: charter's median weight on the model rows is far above air's. Air's own median weight on the weighed set is **656** kg, while the weighed-set median weight across all modes is **1,054.5** kg.

Inside a stated band of 500–5,000 kg inclusive, air still has the high median: **$7.09**, n = **1,971**. That band is the scorecard's size control, not the savings population, which is defined below.

## Vendor

Orgenics, Ltd is the vendor whose high median survives both air and the weight band. Inside air and 500–5,000 kg, it has **390** weighed shipments at a median of **$15.12**, against the air-in-band reference of **$7.09**.

In the log model, the Orgenics indicator is **0.573**, with an HC1 interval of **0.495** to **0.650** and exp(coefficient) − 1 = **0.773**: about 77 percent higher than other vendors, holding mode, log weight, and grouped INCO constant. Yet **599 / 600** of those model rows are air, so the indicator is an air comparison plus one ocean shipment. I would tell procurement that the rate stayed high after those controls; I would not quote 77 percent as a contract reduction.

SCMS from RDC carries the bulk of that same air band, and it is not the expensive vendor. It accounts for **612** of **1,971** weighed air notes in the band, the largest vendor count, at a median of **$5.66**, below the air reference of **$7.09**. A large dollar total is not a high rate: SCMS from RDC moves the most air in the band, and its median sits under the reference.

## Country

No country keeps an uncontrolled lead.

On the weighed set, among countries with at least 20 weighed shipments, the highest median is Botswana's: **38.94** on **62** shipments. Inside air and 500–5,000 kg, however, Botswana has only **7** weighed shipments, with a median of **4.94**. I do not rank a median on seven notes, and I do not call Botswana expensive. The uncontrolled lead stemmed from mix, mostly weight, and it does not survive the control.

The same check on `dashboards/shipment_weighed.csv` lifts two other high uncontrolled medians over the rank threshold inside the band. Guyana: weighed n **155**, uncontrolled median **16.56**, air-and-band n **22**, air-and-band median **10.27**. Congo, DRC: weighed n **104**, uncontrolled median **15.96**, air-and-band n **28**, air-and-band median **9.97**. Both controlled medians are lower than the uncontrolled ones, both counts sit just over 20, and neither country is the uncontrolled leader; I would not open a country program on that margin. Sudan's air-and-band count is **0** (weighed n **42**, uncontrolled median **37.07**), and South Sudan's is **10**.

The country regression was not refit at this stage. `data/processed/construct_metrics.csv` records an R-squared of **0.688** when grouped country is added to the headline model, against **0.666** without it, and this stage's refit of the headline model returned that same **0.666**. Place adds a little fit; it is not the story, and the headline formula does not contain country.

## What the regression says, and what it does not

The outcome is log(freight per kilogram), not raw dollars, so the coefficients are log points. A mode gap I quote in percent is exp(coefficient) − 1, and it is not a dollar saving.

The sample comprises **5,963** weighed shipments with a named mode; blank mode, **211**, is dropped rather than imputed. The reference mode is Air, **4,096**, and the reference INCO term is `N/A - From RDC`. Vendor enters as one indicator, Orgenics versus everyone else, and the covariance for the intervals is HC1. This stage refit the headline formula with the Construct functions, and the point estimates match `construct_metrics.csv` on the R-squared I checked. A few coefficients print one binary digit longer than in the Construct write-up; that is the same fit, not a new model.

Fit, from this refit: the mode-only R-squared is **0.171**; mode and log weight reach **0.625**; and the full model (mode, log weight, grouped INCO, Orgenics) reaches **0.666**.

| Versus Air, full model | Coefficient | HC1 95% interval | exp(coefficient) − 1 | Contains 0? |
|---|---:|---|---:|---|
| Truck | −0.444 | −0.513 to −0.375 | −0.359 | No |
| Air Charter | 0.504 | 0.400 to 0.609 | 0.656 | No |
| Ocean | 0.078 | −0.046 to 0.203 | 0.081 | Yes |

log(weight): **−0.505**, interval **−0.521** to **−0.489**.

Why charter flips. Mode-only, charter versus air is **−0.413**, about 34 percent lower (exp(coefficient) − 1 = **−0.339**), and the interval excludes zero. After log weight, the coefficient becomes **0.393** (exp(coefficient) − 1 = **0.481**). Charters are heavier, and at a given weight the charter rate is higher. The full model, which also holds INCO and Orgenics constant, puts that gap at about 66 percent; the tail inflates it.

Sensitivity: drop weighed rates above **$67.65**, and **5,658** model rows remain. Charter versus air shrinks to **0.192**, interval **0.102** to **0.281**, exp(coefficient) − 1 = **0.211**: still above air, at about 21 percent. That is the figure I would give if someone forced a charter comparison; I would not quote 66 percent as a planning factor. Truck stays below air, ocean's interval still contains zero, and Orgenics stays high (coefficient **0.599**).

Ocean is the result most easily misused. With mode and log weight only, ocean versus air is **−0.447**, exp(coefficient) − 1 = **−0.360**, about 36 percent lower, and the interval excludes zero. Once INCO is added, the full-model interval includes zero. **193 / 282** ocean rows in the model are DDP, and a DDP shipment whose Yes line says the freight is inside the commodity price never entered this regression at all. A low ocean median is therefore not a cheap mode I can switch onto, and it is not the counterfactual in the scenario below.

The regression does not say what would happen if a note changed mode; it is a partial association in this extract. Raw-rate OLS is not interpreted (R-squared **0.029** in `construct_metrics.csv`), and a log-dollar model, being mostly weight, was not interpreted either.

## The savings what-if

This is not a coefficient. The plan said to take heavy air above a stated weight, price it at a cheaper mode's observed median freight per kilogram, and show the difference next to who was excluded and what would make it wrong. It named neither the kilograms nor the share.

The weight rule, in one sentence: a weighed Air shipment is in the population if its Yes-line weight is at or above the median Yes-line weight of the weighed set.

Why that cut, and not air's own median? Air's median weight is **656** kg, and calling that "heavy" would drag a typical air note into a mode-shift story. The weighed-set median, **1,054.5** kg, is the typical weighed shipment in the file; Analyze had already set the floor of the comparison band at 500 kg precisely because that floor still contains this median. At or above **1,054.5** kg is the heavy half of the weighed set. It includes the upper part of the 500–5,000 kg band and the air notes heavier than 5,000 kg, and it excludes the 4 kg charter.

The cheaper mode is truck, not ocean: truck's unconditional median is below air's, and truck does not carry ocean's DDP problem. The counterfactual rate is the observed median freight per kilogram of weighed Truck shipments with weight at or above the same **1,054.5** kg. That median is **$1.53** on **793** truck notes, lower than the all-truck median of **$2.50** because the slice is the heavy half. Using the all-truck median would make a different scenario; using the 66 percent charter gap would make a third, and it is not this one.

A heavy air note contributes kilograms times (its rate minus **$1.53**) only when its rate exceeds that truck median. Notes already at or below it contribute zero; they are not flipped into a negative "saving."

| | |
|---|---:|
| Weighed air notes with weight ≥ 1,054.5 kg | 1,664 |
| Kilograms on those 1,664 | 7.44 million |
| Actual freight on those 1,664, USD | $34.1 million |
| Of which the rate is not above the truck median | 187 |
| Notes in the dollar sum | 1,477 |
| Kilograms on those 1,477 | 4.76 million |
| Actual freight on those 1,477, USD | 33.1 million |
| Dollar difference, USD | $25.8 million |
| 25 percent of that difference, USD | $6.45 million |

The 25 percent share is 0.25 times the full dollar difference. The plan named neither a share nor a subset of lanes, so this is neither the cheapest quartile nor "destinations that already have a truck." It is a straight quarter of the gap, labeled an upper bound in the same way the full gap is. The full gap assumes every one of the 1,477 notes could have moved at the truck median; the quarter assumes a quarter of that gap could have. Neither assumption was tested against a lane, a temperature requirement, or a promised date.

Who is not in the dollar figure:

- The **593** included-in-price shipments. Freight bundled into the commodity price is not free, and it is not in this sum.
- The **239** invoiced-separately shipments. The bill is not in the extract, and it was not set to zero.
- `ASN-22365`, the one zero-weight shipment. A zero weight yields no per-kilogram rate.
- Blank mode. **79** weighed blank-mode notes sit at or above 1,054.5 kg; they are not air, and they are not in the sum.
- Air charter. **301** weighed charters sit at or above the cutoff, and this scenario does not "move" them.
- Ocean. **250** weighed ocean notes sit at or above the cutoff. Ocean's median is not the counterfactual, given that **193 / 282** ocean model rows are DDP and DDP enters the model only when freight was a visible number.

What would make the number wrong:

- Truck may not be feasible for the lane, the lead time, the cold chain, or the commodity. The file has no urgency flag; product group is a weak proxy, and this scenario does not use it as one.
- An INCO term can hide the real freight inside the goods price, so a note that looks like a gap may not be a gap the shipper pays.
- The prices are what this extract recorded from 2006-05-02 through 2015-09-14; they are not a 2026 rate card.
- The Yes-line rule takes one freight string and one weight string without averaging lines. If that rule were wrong, the dollars would move with it.
- The tail that pulls the mean, `DN-1683` at about **$31,088** per kg, is not in this scenario, since its weight of 4 is below 1,054.5. Restricting to heavy air is what keeps that note out; it does not, however, turn the remaining gap into a forecast.

The inputs are `data/processed/execute_scenario_air_notes.csv` (the 1,664 heavy air notes, with a flag for the 1,477 that enter the sum) and `data/processed/execute_scenario_truck_notes.csv` (the 793 truck notes whose median is the counterfactual). The result rows are in `data/processed/execute_scenario_result.csv`. Python is the source of truth, and no new SQL file was added: `sql/kpi_freight.sql` already checks the Yes-line rates, and a SQL copy of this scenario would amount to a second estimate.

## Caveats

- The fit is observational. Switching a shipment onto truck is the scenario above, with its assumption written on it; it is not the truck coefficient.
- Excluded notes are missing, not zero.
- The log and the HC1 intervals handle a heavy tail; they are not a causal claim.
- Orgenics is one vendor indicator, not a full vendor model.
- Country is a check, and the uncontrolled leaders do not keep that lead.
- Tableau Public was not published. The extract is the weighed set, not a savings column, because a summed counterfactual on a dashboard would look like an invoice.

## What I would do next

I would not fit another model first. I would take the 1,477 notes to someone who knows the lanes, ask which of them could actually move by truck, and reprice only that list at the truck median on this slice. The result will be smaller than **$6.45 million**, or it will be zero. I would also keep Orgenics as a procurement conversation inside air, separate from any mode shift. I would not build an ocean business case until the DDP notes with hidden freight are visible, and I would not update the dollars to current tariffs from this file; after all, the file ends in 2015.

## How this was delivered

Plan locked the grain, the exclusions, and the rule that a saving is a scenario ([01-plan.md](01-plan.md)). Analyze built the Yes-line scorecard without fitting a model ([02-analyze.md](02-analyze.md)). Construct fit the log model without pricing a scenario ([03-construct.md](03-construct.md)). This page supplies the scenario, the recommendation, and the refusal to publish a Tableau URL.

The browser file a hiring manager can open without Tableau is not a substitute I invented. The extract to upload, manually, is `dashboards/shipment_weighed.csv`, and the sheet list is `dashboards/TABLEAU.md`. This environment did not sign in, and no public Tableau URL exists.

## How I would say this in an interview

The business asked where freight money could come out. I would split that into a scorecard and a what-if, and I would not let the model answer the second.

The scorecard is the median, **$7.26** per kilogram on **6,174** weighed shipments. The mean, **$38.93**, reflects one 4 kilogram charter at **$31,088** per kilogram and the rest of the tail. Air's median is **$10.02**, truck's **$2.50**, and ocean's **$1.68**. I dropped included-in-price and invoiced-separately shipments, **593** and **239** of them, without calling them free.

Holding weight constant, truck stays below air, by about 36 percent in the log model, while charter flips from cheaper than air to more expensive, because charters are heavier. I would not plan on the 66 percent charter gap; once I cut the tail at the 95th percentile, that gap is about 21 percent, and it remains an association. Orgenics stays about 77 percent higher, almost all of it on air, with a median of **$15.12** inside the weight band against **$7.09**. Botswana looks expensive until I hold mode and weight, at which point it has **7** notes in the band. Ocean looks cheap, yet **193** of **282** ocean rows in the model are DDP.

The dollar figure I would defend is a what-if: air at or above **1,054.5** kilograms, the median weight of the weighed set rather than air's own lighter median of **656** kilograms. The counterfactual is the truck median on that same slice, **$1.53**, neither a coefficient nor ocean. **1,477** notes clear that rate, carrying **4.76 million** kilograms and **$33.1 million** of actual freight, and the difference is **$25.8 million**. I would also show a quarter of it, **$6.45 million**, and call both upper bounds. Truck may not be feasible, the commercial term may be hiding the real bill, and the prices stop in 2015.