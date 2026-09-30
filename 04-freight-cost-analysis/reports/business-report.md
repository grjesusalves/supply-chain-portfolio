# Business report — freight cost on USAID SCMS shipments

This report is for a procurement lead, a logistics lead, and a finance partner. The one-page version is [executive-summary.md](executive-summary.md). The stage note is [04-execute.md](04-execute.md). Nothing here treats a regression coefficient as money that was saved.

## Question

What drives freight cost across vendors, countries, and shipping modes, and where could money come out?

The person who can use the answer is not the same in each case. Procurement can challenge a vendor that stays expensive inside air and inside a weight band. Logistics can look at mode, and only on shipments that are heavy enough that a cheaper mode is even a conversation. Finance can look at a dollar figure only if the denominator, the dropped rows, and the assumption are on the page.

This is a public historical extract of USAID supply-chain shipments of antiretrovirals and HIV lab commodities. It is not USAID's internal decision file. Delivered to client runs from **2006-05-02** through **2015-09-14**. These are not current market rates.

## What a row is

A row in the file is a line item. The money is not. Freight is one charge on a delivery note, and the note is `ASN/DN #`.

The rule, accepted on 2026-09-29 and not reopened here: one row per ASN/DN. The freight string and the weight string are the single line where First Line Designation = Yes. Line-item value is summed. Freight is not summed and not averaged across lines. This stage did not parse the strings a second way. `src/execute_freight.py` calls the Yes-line rollup in `src/analyze_freight.py`.

Insurance is not in the rate. Manufacturing site is not on the scorecard. It is not constant on the note, and this rule does not pick a site.

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

6,174 + 593 + 239 + 0 + 23 + 1 = 7,030. Priced shipments, numeric freight, are **6,198**. Freight-to-value, numeric freight and a positive value sum, is **6,186**.

A blank shipment mode is a missing label. It is not a fifth mode. **226** shipments, **211** of them weighed, median freight per kilogram **4.654915254237289**. They stay out of every mode comparison I would say out loud, and they stay out of the savings scenario.

## Headline

On the weighed set:

| | |
|---|---:|
| Median freight per kg | 7.263901636359817 |
| Mean freight per kg | 38.93012311964861 |
| 95th percentile | 67.64871004566209 |
| Maximum | 31087.705 |
| Median freight / line-item value | 0.08758549492765344 |
| Numeric freight, priced set, USD | 68817849.41 |
| Numeric freight, weighed set, USD | 68686757.92 |

The maximum is `DN-1683`, Air Charter, weight **4** kg, freight **124350.82**. One light charter is enough to pull a mean. A logistics lead acts on the median, and on the tail as a tail. I would not quote 38.93 USD per kg as what a shipment costs.

## Mode

Weighed medians below were recomputed from `dashboards/shipment_weighed.csv` after this stage confirmed that file is the weighed set (6,174 rows, not rewritten). Shipment counts are `data/processed/kpi_by_mode.csv`.

| Mode | Shipments | Weighed n | Median freight per kg |
|---|---:|---:|---:|
| Air | 4,541 | 4,096 | 10.02401980861159 |
| (blank) | 226 | 211 | 4.654915254237289 |
| Air Charter | 494 | 423 | 4.317785194174758 |
| Truck | 1,442 | 1,162 | 2.5032950842130273 |
| Ocean | 327 | 282 | 1.6810197953137624 |

Air is the expensive named mode on the median. Charter's median sits below air and above truck and ocean. That unconditional order is not the regression. Charter's median weight on the model rows is far above air's. Air's own median weight on the weighed set is **656.0** kg. The weighed-set median weight, all modes, is **1054.5** kg.

Inside a stated band of 500–5,000 kg inclusive, air is still the high median: **7.091310572687225**, n = **1,971**. That band is the scorecard's size control. It is not the savings population. The savings population is defined below.

## Vendor

Orgenics, Ltd is the vendor whose high median survives air and the weight band. Inside air and 500–5,000 kg: **390** weighed shipments, median **15.1159699363971**, against the air-in-band reference **7.091310572687225**.

In the log model the Orgenics indicator is **0.5726954445178964**, HC1 interval **0.49503741646674093** to **0.650353472569052**, exp(coefficient) − 1 = **0.7730397465414948**. About 77 percent higher than other vendors, holding mode, log weight, and grouped INCO. **599 / 600** of those model rows are air. The indicator is an air comparison plus one ocean shipment. I would tell procurement that the rate stayed high after those controls. I would not quote 77 percent as a contract reduction.

SCMS from RDC is the bulk of that same air band and is not the expensive vendor. **612** of **1,971** weighed air notes in the band, the largest vendor count, median **5.655085537731795**, which is below the air reference **7.091310572687225**. A large dollar total is not a high rate. SCMS from RDC moves the most air in the band and the median sits under the reference.

## Country

No country keeps an uncontrolled lead.

On the weighed set, among countries with at least 20 weighed shipments, the highest median is Botswana: **38.938094117647054** on **62** shipments. Inside air and 500–5,000 kg, Botswana has **7** weighed shipments. The median of those seven is **4.937908450704226**. I do not rank a median on seven notes, and I do not call Botswana expensive. The uncontrolled lead was mix, mostly weight, and it does not survive the control.

The same check on `dashboards/shipment_weighed.csv` puts two other high uncontrolled medians over the rank threshold inside the band. Guyana: weighed n **155**, uncontrolled median **16.5646**, air-and-band n **22**, air-and-band median **10.267478869134363**. Congo, DRC: weighed n **104**, uncontrolled median **15.964528005701299**, air-and-band n **28**, air-and-band median **9.970426731415694**. Both controlled medians are lower than the uncontrolled ones, both counts are just over 20, and neither is the uncontrolled leader. I do not open a country program on that margin. Sudan's air-and-band count is **0** (weighed n **42**, uncontrolled median **37.069165120593695**). South Sudan's air-and-band count is **10**.

The country regression was not refit in this stage. `data/processed/construct_metrics.csv` records R-squared **0.6883078381217647** when grouped country is added to the headline model, against **0.6660299231602032** without it. This stage refit the headline model and got that same **0.6660299231602032**. Place adds a little fit. It is not the story. The headline formula does not contain country.

## What the regression says, and what it does not

The outcome is log(freight per kilogram), not raw dollars. Coefficients are log points. A mode gap I quote in percent is exp(coefficient) − 1. It is not a dollar saving.

Sample: weighed shipments with a named mode. **5,963**. Blank mode, **211**, dropped, not imputed. Reference mode Air, **4,096**. Reference INCO term `N/A - From RDC`. Vendor is one indicator, Orgenics versus everyone else. Covariance for the intervals is HC1. This stage refit the headline formula with the Construct functions. Point estimates match `construct_metrics.csv` on the R-squared I checked. A few coefficients print one binary digit longer than the Construct writeup. That is the same fit, not a new model.

Fit, from this refit: mode-only R-squared **0.17142161894896146**. Mode and log weight **0.624897919846368**. Full model (mode, log weight, grouped INCO, Orgenics) **0.6660299231602032**.

| Versus Air, full model | Coefficient | HC1 95% interval | exp(coefficient) − 1 | Contains 0? |
|---|---:|---|---:|---|
| Truck | −0.44430449116910703 | −0.5134742340654226 to −0.3751347482727915 | −0.35872986999493534 | No |
| Air Charter | 0.5044214943619498 | 0.40014577395283873 to 0.6086972147710609 | 0.6560272222122926 | No |
| Ocean | 0.07832985106529215 | −0.04630920831811078 to 0.20296891044869508 | 0.08147932695122935 | Yes |

log(weight) **−0.5049510700069987**, interval **−0.521310803420571** to **−0.48859133659342635**.

Why charter flips. Mode-only, charter versus air is **−0.4134577317308613** (about 34 percent lower: exp(coefficient) − 1 = **−0.33864051168950005**). The interval excludes zero. After log weight, the coefficient is **0.3926059704516047** (exp(coefficient) − 1 = **0.4808347816972092**). Charters are heavier. At a given weight, the charter rate is higher. The full model, which also holds INCO and Orgenics, puts that gap at about 66 percent. The tail inflates it.

Sensitivity: drop weighed rates above **67.64871004566209**. **5,658** model rows remain. Charter versus air shrinks to **0.19162918766097609**, interval **0.10229920733529456** to **0.2809591679866576**, exp(coefficient) − 1 = **0.21122129787951574**. Still above air. About 21 percent. That is the figure I would say if someone forces a charter comparison. I would not quote 66 percent as a planning factor. Truck stays below air. Ocean's interval still contains zero. Orgenics stays high (coefficient **0.5994684372852546**).

Ocean is the result that is easy to misuse. With mode and log weight only, ocean versus air is **−0.447037535044809**, exp(coefficient) − 1 = **−0.360480096583939**, about 36 percent lower, and the interval excludes zero. Adding INCO, the full-model interval includes zero. **193 / 282** ocean rows in the model are DDP. A DDP shipment whose Yes line says the freight is inside the commodity price never entered this regression. A low ocean median is not a cheap mode I can switch onto, and it is not the counterfactual in the scenario below.

The regression does not say what would happen if a note changed mode. It is a partial association in this extract. Raw-rate OLS is not interpreted (R-squared **0.02901026459920797** in `construct_metrics.csv`). A log-dollar model is mostly weight and was not interpreted.

## The savings what-if

This is not a coefficient. The plan said: take heavy air above a stated weight, price it at a cheaper mode's observed median freight per kilogram, and show the difference next to who was excluded and what would make it wrong. The plan did not name the kilograms and did not name the share.

The weight rule, one sentence: a weighed Air shipment is in the population if its Yes-line weight is at or above the median Yes-line weight of the weighed set.

Why that cut, and not air's own median. Air's median weight is **656.0** kg. Calling that "heavy" would put a typical air note into a mode-shift story. The weighed-set median, **1054.5** kg, is the typical weighed shipment in the file. Analyze already set the floor of the comparison band at 500 kg because that floor still contains this median. At or above **1054.5** kg is the heavy half of the weighed set. It includes the upper part of the 500–5,000 kg band and the air notes heavier than 5,000 kg. It does not include the 4 kg charter.

The cheaper mode is truck, not ocean. Truck's unconditional median is below air, and truck is not the DDP problem ocean is. The counterfactual rate is the observed median freight per kilogram of weighed Truck shipments with weight at or above the same **1054.5** kg. That median is **1.5292046183450931** on **793** truck notes. It is lower than the all-truck median **2.5032950842130273** because the slice is the heavy half. Using the all-truck median would be a different scenario. Using the 66 percent charter gap would be a third, and it is not this one.

A heavy air note contributes kilograms times (its rate minus **1.5292046183450931**) only when its rate is above that truck median. Notes already at or below it contribute zero. They are not flipped into a negative "saving."

| | |
|---|---:|
| Weighed air notes with weight ≥ 1054.5 kg | 1,664 |
| Kilograms on those 1,664 | 7437442.0 |
| Actual freight on those 1,664, USD | 34144242.03 |
| Of which the rate is not above the truck median | 187 |
| Notes in the dollar sum | 1,477 |
| Kilograms on those 1,477 | 4761674.0 |
| Actual freight on those 1,477, USD | 33085383.96 |
| Dollar difference, USD | 25803810.088146247 |
| 25 percent of that difference, USD | 6450952.522036562 |

The 25 percent share is 0.25 times the full dollar difference. The plan did not name a share, and it did not name a subset of lanes. This is not the cheapest quartile and it is not "destinations that already have a truck." It is a straight quarter of the gap, labeled as an upper bound in the same way the full gap is an upper bound. The full gap assumes every one of the 1,477 notes could have moved at the truck median. The quarter assumes a quarter of that gap could have. Neither assumption was tested against a lane, a temperature requirement, or a promised date.

Who is not in the dollar figure:

- The **593** included-in-price shipments. Freight bundled into the commodity price is not free, and it is not in this sum.
- The **239** invoiced-separately shipments. The bill is not in the extract. It was not set to zero.
- `ASN-22365`, the one zero-weight shipment. A zero weight is not a per-kilogram rate.
- Blank mode. **79** weighed blank-mode notes sit at or above 1054.5 kg. They are not air, and they are not in the sum.
- Air charter. **301** weighed charters sit at or above the cutoff. This scenario does not "move" them.
- Ocean. **250** weighed ocean notes sit at or above the cutoff. Ocean's median is not the counterfactual. **193 / 282** ocean model rows are DDP, and DDP only enters the model when freight was a visible number.

What would make the number wrong:

- Truck may not be feasible for the lane, the lead time, the cold chain, or the commodity. The file has no urgency flag. Product group is a weak proxy, and this scenario does not use it as one.
- An INCO term can hide the real freight inside the goods price. A note that looks like a gap may not be a gap the shipper pays.
- The prices are what this extract recorded from 2006-05-02 through 2015-09-14. They are not a 2026 rate card.
- The Yes-line rule takes one freight string and one weight string. It does not average lines. If that rule were wrong, the dollars would move with it.
- The tail that pulls the mean, `DN-1683` at **31087.705** USD per kg, is not in this scenario. Weight 4 is below 1054.5. Restricting to heavy air is what keeps that note out. It does not make the remaining gap a forecast.

The inputs are `data/processed/execute_scenario_air_notes.csv` (the 1,664 heavy air notes, with a flag for the 1,477 that enter the sum) and `data/processed/execute_scenario_truck_notes.csv` (the 793 truck notes whose median is the counterfactual). The result rows are `data/processed/execute_scenario_result.csv`. Python is the source of truth. No new SQL file was added. `sql/kpi_freight.sql` already checks the Yes-line rates. A SQL copy of this scenario would be a second estimate.

## Caveats

- The fit is observational. Switching a shipment onto truck is the scenario above, with the assumption written on it. It is not the truck coefficient.
- Excluded notes are missing, not zero.
- The log and the HC1 intervals handle a heavy tail. They are not a causal claim.
- Orgenics is one vendor indicator, not a full vendor model.
- Country is a check. The uncontrolled leaders do not keep that lead.
- Tableau Public was not published. The extract is the weighed set, not a savings column. A summed counterfactual on a dashboard would look like an invoice.

## What I would do next

I would not fit another model first. I would take the 1,477 notes to someone who knows the lanes and ask which of them could actually move by truck, then reprice only that list at the truck median on this slice. That is a smaller number than **6450952.522036562**, or it is zero. I would also keep Orgenics as a procurement conversation inside air, separate from any mode shift. I would not build an ocean business case until the DDP notes with hidden freight are visible. I would not update the dollars to current tariffs from this file. The file ends in 2015.

## How this was delivered

Plan locked the grain, the exclusions, and the rule that a saving is a scenario ([01-plan.md](01-plan.md)). Analyze built the Yes-line scorecard and did not fit a model ([02-analyze.md](02-analyze.md)). Construct fit the log model and did not price a scenario ([03-construct.md](03-construct.md)). This page is the scenario, the recommendation, and the refusal to publish a Tableau URL.

The browser file a hiring manager can open without Tableau is not a substitute I invented. The extract to upload, manually, is `dashboards/shipment_weighed.csv`. The sheet list is `dashboards/TABLEAU.md`. This environment did not sign in. No public Tableau URL exists.

## How I would say this in an interview

The business asked where freight money could come out. I would split that into a scorecard and a what-if, and I would not let the model answer the second one.

The scorecard is the median, **7.263901636359817** dollars per kilogram on **6,174** weighed shipments. The mean, **38.93012311964861**, is one charter of 4 kilograms at **31087.705** per kilogram and the rest of the tail. Air's median is **10.02401980861159**. Truck is **2.5032950842130273**. Ocean is **1.6810197953137624**. I dropped included-in-price and invoiced-separately. I did not call them free. That is **593** and **239** shipments.

Holding weight, truck stays lower than air, about 36 percent in the log model, and charter flips from cheaper than air to more expensive, because charters are heavier. I would not plan on the 66 percent charter gap. After I cut the tail at the 95th percentile, that gap is about 21 percent, exp(coefficient) − 1 = **0.21122129787951574**, and it is still an association. Orgenics stays about 77 percent higher, almost all of it air, median **15.1159699363971** inside the weight band against **7.091310572687225**. Botswana looks expensive until I hold mode and weight, and then it has **7** notes in the band. Ocean looks cheap, and **193** of **282** ocean rows in the model are DDP.

The dollar figure I would defend is a what-if. Air at or above **1054.5** kilograms, which is the median weight of the weighed set, not air's own lighter median of **656** kilograms. The counterfactual is the truck median on that same slice, **1.5292046183450931**, not a coefficient and not ocean. **1,477** notes clear that rate. **4761674.0** kilograms. **33085383.96** dollars of freight actually on those notes. The difference is **25803810.088146247**. I would also show a quarter of it, **6450952.522036562**, and I would call both upper bounds. Truck may not be feasible, the commercial term may be hiding the real bill, and the prices stop in 2015.
