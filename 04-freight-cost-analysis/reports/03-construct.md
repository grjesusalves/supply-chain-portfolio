# Construct — Freight cost (USAID SCMS)

PACE stage: **Construct**. This page fits the regression the plan reserved for after the scorecard. The outcome is freight per kilogram on the weighed set. The model that is interpreted is OLS of the log of that rate. It does not price a savings scenario, write an executive summary, or publish a Tableau workbook. Those belong to Execute.

Every figure below is from one run of `src/construct_freight.py` on the local raw file (Latin-1, not re-downloaded). The shipment table is the Yes-line rollup in `src/analyze_freight.py`. This stage does not parse freight a second way and does not choose a new grain. Metric tables are in `data/processed/construct_*.csv`. The chart is `images/construct_mode_coefficients.png`. The dashboard extract is `dashboards/shipment_weighed.csv`. The raw CSV stays git-ignored.

## How I would say this in an interview

The question is the rate, not the dollar bill. Freight per kilogram is defined on the weighed set: Yes-line freight is a plain decimal, Yes-line weight is a plain decimal and greater than zero. That is **6,174** shipments. I do not put included-in-price, invoiced separately, or a missing weight in as zero. `ASN-22365` stays out. Weight is 0.

Blank shipment mode is not a mode. I drop those shipments from the regression and count them: **211** weighed shipments. The model has **5,963** rows. 6,174 − 211 = 5,963. I do not impute a mode.

Air is the reference, because it is the most common named mode: **4,096** of the 5,963. The distribution is heavy-tailed. On the weighed set the median rate is **7.263901636359817**, the mean is **38.93012311964861**, and one air charter, `DN-1683`, is **31087.705** per kilogram on 4 kg. I do not fit the headline model to that raw rate. I fit OLS to **log(freight per kilogram)**. A log coefficient is approximately a percent change when it is small. The mode gaps are not small, so I also report exp(coefficient) − 1, and I do not quote either figure as dollars saved.

Holding log weight, grouped INCO term, and an Orgenics indicator, truck is lower than air and air charter is higher than air. Ocean is not distinguished from air: its 95% interval crosses zero. The per-kilogram rate falls as shipments get heavier. Orgenics, Ltd stays high, and 599 of its 600 model rows are air.

That ocean sentence is the full model, not "ocean costs the same." With mode and log weight only, ocean is still lower than air and the interval does not cross zero. The gap goes away when INCO term is added. **193 / 282** ocean rows in the model are DDP, and a DDP row is here only because the Yes line showed a number. Hundreds of DDP shipments never entered, because the freight was inside the commodity price. A low DDP coefficient is not a cheap term.

Mode alone has R-squared **0.1714216189489614**. The full model has **0.6660299231602032**. Weight, INCO, and Orgenics add the fit. Country, left out of the headline and checked with a minimum of 50 model rows, moves R-squared from **0.6660299231602032** to **0.6883078381217647**. Place is not nothing. It is not the story.

A log-dollar model on the same 5,963 rows has R-squared **0.5288105987422616** from log weight alone. Adding mode raises it to **0.5688396986201978**. Raw dollars mostly rediscover weight. That model is not the one I interpret.

Dropping rates above the weighed-set 95th percentile shrinks the charter-versus-air coefficient and does not flip the signs I would say out loud. Truck stays lower. Charter stays higher. Ocean still crosses zero. Orgenics stays high. The dollars are historical, delivered to client from **2006-05-02** to **2015-09-14**. Nothing here is a saving.

## What was built

| File | What it is |
|---|---|
| `src/construct_freight.py` | The sample, the OLS fits, the chart, the dashboard extract |
| `data/processed/construct_sample.csv` | Who is in the weighed set, who is dropped, and why there is no holdout |
| `data/processed/construct_metrics.csv` | n, R-squared, and the formula for each fit |
| `data/processed/construct_coefficients.csv` | Coefficients, HC1 95% intervals, classical intervals, exp(coefficient) − 1 on log outcomes |
| `data/processed/construct_reference_levels.csv` | The level each dummy is compared with |
| `data/processed/construct_grouping.csv` | INCO terms and countries kept or pooled, with the model-row count |
| `data/processed/construct_sensitivity.csv` | Full model versus the same formula at or below the weighed-set p95 |
| `data/processed/construct_wald.csv` | HC1 Wald tests: beyond mode, and the country block |
| `data/processed/construct_mode_weight.csv` | Median weight and median rate by named mode, model rows |
| `data/processed/construct_inco_by_mode.csv` | Grouped INCO term by mode, model rows |
| `data/processed/construct_orgenics_by_mode.csv` | Where the 600 Orgenics rows sit |
| `data/processed/construct_run.csv` | Library version and the headline formula |
| `images/construct_mode_coefficients.png` | Mode coefficients versus Air, full model and the p95 cut |
| `dashboards/shipment_weighed.csv` | Weighed set, one row per ASN/DN, for a later Tableau workbook |
| `dashboards/TABLEAU.md` | Sheets and filters. Not a published URL |

No SQL file was added. `sql/kpi_freight.sql` already defines the Yes-line grouped rates, and Analyze matched them. A SQL regression would be a second, fake estimate. The coefficients in this stage are statsmodels.

statsmodels **0.14.4+dfsg**, pandas **3.0.6**. Covariance for every interval I quote is **HC1**. The point estimates are OLS. WLS is not used. Weighting by kilograms would answer the rate of the typical kilogram and let the heaviest shipments dominate. The scorecard's headline is the typical shipment. The log is how the tail is handled. HC1 is how unequal variance across modes is handled after that log. Classical intervals are in the coefficient file. On the headline model they do not change which intervals contain zero.

There is no train/test split. This is an explanation of the shipments in the extract, not a predictor. A random holdout would not answer whether mode still lines up with the rate after weight. `construct_sample.csv` says `holdout_split` = none.

## The sample

The rollup is `yes_line_rollup`. One row per `ASN/DN #`. The freight string and the weight string are the single `First Line Designation` = Yes line. The script stops if that is not 7,030 shipments, if the weighed set is not 6,174, if included-in-price is not 593, if invoiced separately is not 239, if weight-not-numeric is not 23, or if `ASN-22365` is inside the weighed set. Manufacturing site is not a column. The rollup refuses to copy it. Insurance is not read.

| Step | Shipments | What happened |
|---|---:|---|
| Yes-line rollup | 7,030 | One row per ASN/DN |
| Included in commodity cost | 593 | Out. Not zero |
| Invoiced separately | 239 | Out. Not zero |
| See pointer on the Yes line | 0 | Counted. None |
| Weight captured separately | 23 | Freight parsed. No denominator |
| Weight not positive | 1 | `ASN-22365`, weight 0, freight 1002.35 |
| Weighed set | 6,174 | The outcome's population |
| Blank mode, weighed | 211 | Dropped from the model. Not imputed |
| Model rows | 5,963 | Named mode |

6,174 + 593 + 239 + 0 + 23 + 1 = 7,030. 6,174 − 211 = 5,963.

Blank is a null that the rollup labels `(blank)`. Analyze already showed it is not mixed with a named mode inside a note. Keeping it as a level would publish a coefficient for a label nobody chose. The 211 stay in `dashboards/shipment_weighed.csv`, with `in_regression_sample` = 0, so a dashboard can still see them.

Delivered-to-client dates, parsed with the same `%d-%b-%y` rule as Analyze: **2006-05-02** through **2015-09-14**. That is the window of the extract. It is not a trend.

On the weighed set, median freight per kilogram **7.263901636359817**, mean **38.93012311964861**, maximum **31087.705**. The maximum is `DN-1683`, Air Charter, vendor `SCMS from RDC`, weight 4 kg, freight 124350.82. It is inside the model, because the mode is named. The p95 of the weighed set, blank mode included, is **67.64871004566209**. That is the same cut Analyze reported. It was recomputed here. It was not copied into the script as a constant.

## Why the outcome is a log, and why the raw rate is not

The headline formula is:

`log_rate ~ C(mode, Treatment(reference='Air')) + log_weight + C(inco_grouped, Treatment(reference='N/A - From RDC')) + orgenics`

`log_rate` is log(freight per kilogram). `log_weight` is log(weight in kilograms). Freight dollars are not on the right-hand side. The rate already divides by weight, so log weight is a size control, not a second copy of the denominator. A negative coefficient means the per-kilogram rate is lower on heavier shipments. It does not mean the dollar bill is lower. In the dollar comparison below, log dollars still rise with log weight. They rise less than one-for-one, and that shortfall is this coefficient.

The same right-hand side fit to the raw rate, which I do not interpret, has R-squared **0.0290102645992079**. The air-charter coefficient is 198.272068, HC1 interval **−11.612473 to 408.156609**, which contains zero, on a rate whose median is about 7. Dropping only `DN-1683` moves that charter coefficient to 112.053649 (interval **−14.023779 to 238.131078**, still contains zero) and moves the raw-rate R-squared to **0.0337041196888303**. One shipment is enough to shove a raw-rate coefficient by tens of dollars per kilogram. That is why the headline is the log. `exp(coefficient) − 1` is blank on those raw-rate rows. It is not a percent when the outcome is not a log.

## What is in, and what is out

| Input | Decision |
|---|---|
| Shipment mode | In. Reference = Air, the most common mode on the model rows. 4,096 rows. |
| log(weight) | In. Size control on the rate. See above. |
| Vendor INCO term | In, after pooling. Reference = `N/A - From RDC`, 2,983 model rows. |
| Orgenics, Ltd | In, as one indicator versus every other vendor. 600 model rows. Not a 73-level vendor factor. |
| Country | Out of the headline. A separate check pools countries with fewer than 50 model rows. |
| Manufacturing site | Out. Mixed on 880 notes. Not copied. |
| Insurance | Out. Not read. |
| Raw freight | Out of every rate formula. |
| Blank mode | Out of the model. Counted. |

INCO grouping, counted on the 5,963 model rows, not on the 7,030 notes. Keep a term with at least **50** model rows. Pool the rest as `Other`. Fifty is above the scorecard's rank threshold of 20. A level that is only large enough to rank a median is still a noisy dummy. The script stops if a real level is already named Other.

| INCO term | Model rows | In the model as |
|---|---:|---|
| N/A - From RDC | 2,983 | itself, and the reference |
| EXW | 2,163 | itself |
| FCA | 352 | itself |
| DDP | 296 | itself |
| CIP | 163 | itself |
| DAP | 3 | Other |
| DDU | 2 | Other |
| CIF | 1 | Other |

3 + 2 + 1 = 6. The Other coefficient is estimated. n = 6 is not a finding, and I do not quote it as a commercial term. `N/A - From RDC` is large, so it stays. It is the reference because it is the most common grouped term, not because the label sorts first.

Vendor is not a 73-level factor. The indicator is 1 when the vendor is `Orgenics, Ltd` and 0 otherwise. One vendor string on the model rows contains "orgenics". The reference is not Orgenics: 5,363 rows.

Country is the same cardinality problem, 43 countries on the file. The headline model omits it. The check keeps a country with at least 50 model rows and pools the rest as Other. That keeps **20** countries. **18** countries, **211** model rows, sit in Other. That 211 is the pooled tail. It is not the 211 blank-mode shipments, which are already out of this sample. The reference for the check is Nigeria, the most common kept country, **748** model rows. The check does not re-pick Air or the INCO reference.

## Mode, before the other controls

Model rows only. Medians match the weighed-set mode cut for these four names, because a named mode was not dropped. `construct_mode_weight.csv`.

| Mode | n | Median weight, kg | Mean weight, kg | Median freight per kg | Mean freight per kg |
|---|---:|---:|---:|---:|---:|
| Air | 4,096 | 656.0 | 1992.924072265625 | 10.02401980861159 | 33.52045768694116 |
| Air Charter | 423 | 3289.0 | 7686.458628841608 | 4.317785194174758 | 162.32892875891395 |
| Truck | 1,162 | 2673.0 | 6404.715146299483 | 2.5032950842130277 | 14.44080492244196 |
| Ocean | 282 | 5687.0 | 6877.386524822695 | 1.6810197953137624 | 20.662665611969857 |

4,096 + 423 + 1,162 + 282 = 5,963. Air is light. Ocean's median weight is 5687 / 656 = 8.669207317073171 times air's median weight. Charter is 3289 / 656 = 5.013719512195122 times. A low unconditional rate on ocean or charter is partly a heavy shipment. The mean rates, especially charter's 162.32892875891395 against a median of 4.317785194174758, are the tail. The log model is aimed at the rate, not at that mean.

Mode-only OLS of log(freight per kg), reference Air. HC1 95% intervals. exp(coefficient) − 1 is the multiplicative change. n = 5,963. R-squared **0.1714216189489614**. Adjusted **0.1710044793041968**.

| Versus Air | n | Coefficient | HC1 95% interval | exp(coefficient) − 1 | Contains 0? |
|---|---:|---:|---|---:|---|
| Air Charter | 423 | −0.4134577317308613 | −0.5791710892556131 to −0.2477443742061095 | −0.3386405116895 | No |
| Ocean | 282 | −1.5516303515544525 | −1.7000753195882716 to −1.4031853835206334 | −0.788097783058091 | No |
| Truck | 1,162 | −1.3196520757753012 | −1.4011861033141193 to −1.238118048236483 | −0.732771739020915 | No |

Without controls, charter is about 34 percent lower than air, ocean about 79 percent lower, truck about 73 percent lower. All three intervals exclude zero. This is the scorecard, written as a regression. It is the baseline. It is not the model I would leave a hiring manager with, because it ignores that those modes are heavier.

## What log weight does, and what INCO then does

These two fits are bridges. They are marked `interpreted` = 0. They exist so the ocean result in the headline model is not described as a weight result.

Mode and log weight. R-squared **0.624897919846368**. Adjusted **0.6246460889768456**.

| Term | Coefficient | HC1 95% interval | exp(coefficient) − 1 | Contains 0? |
|---|---:|---|---:|---|
| Air Charter vs Air | 0.3926059704516047 | 0.2903765000992002 to 0.4948354408040092 | 0.4808347816972091 | No |
| Ocean vs Air | −0.447037535044809 | −0.5606804601135622 to −0.3333946099760558 | −0.360480096583939 | No |
| Truck vs Air | −0.5622376208888001 | −0.625484098750756 to −0.4989911430268443 | −0.4300676565435097 | No |
| log(weight) | −0.5032181425767487 | −0.5193263119112531 to −0.4871099732422442 | −0.3954181050442178 | No |

Holding weight, the charter sign flips. Charter was lower than air because charter shipments are heavier. At a given weight, charter's rate is higher, about 48 percent. Ocean is still about 36 percent lower than air, and the interval still excludes zero. Truck is about 43 percent lower. Weight does not make ocean and air the same.

The log-weight coefficient is an elasticity. A 1 percent heavier shipment lines up with a rate about 0.50 percent lower. It is not a small dummy, so "approximately a percent" is this slope, not a claim that the ocean gap was a small percent. A doubling of weight, still in this bridge model: ln(2) × −0.5032181425767487 = −0.34880423673368594, and exp(−0.34880423673368594) − 1 = −0.2944687661494655. The arithmetic I use for the headline model's slope is in the next section. Neither number is a recommendation to ship heavier freight.

Mode, log weight, and grouped INCO. R-squared **0.6538294457842162**. Ocean's coefficient becomes **−0.0050641216780788**, interval **−0.1323346592323069 to 0.1222064158761492**, which contains zero. Charter stays higher (0.4953870377615136, interval 0.3911567860909865 to 0.5996172894320406). Truck stays lower (−0.4471047918078274, interval −0.5162912043240274 to −0.3779183792916274).

INCO is why ocean loses the gap. On the model rows, `construct_inco_by_mode.csv`:

| Mode | CIP | DDP | EXW | FCA | N/A - From RDC | Other |
|---|---:|---:|---:|---:|---:|---:|
| Air | 163 | 103 | 2,063 | 350 | 1,411 | 6 |
| Air Charter | 0 | 0 | 17 | 0 | 406 | 0 |
| Ocean | 0 | 193 | 82 | 2 | 5 | 0 |
| Truck | 0 | 0 | 1 | 0 | 1,161 | 0 |

193 + 82 + 2 + 5 = 282. Ocean is 193 / 282 = 0.6843971631205674 DDP. Truck is 1,161 / 1,162 = 0.9991394148020654 `N/A - From RDC`, which is the INCO reference, so truck's coefficient is not an INCO mix. Charter is 406 / 423 = 0.9598108747044918 the same reference term. Air is the mode that actually spans the terms.

DDP's own coefficient in this bridge is −0.6105351684166391, interval −0.7339843939988501 to −0.4870859428344282. That is the DDP shipments whose freight was a number. Analyze counted 313 DDP shipments kept out because the Yes line says the freight is in the commodity cost. Those 313 are not in this coefficient. Calling the visible DDP rows cheap would repeat the mistake the plan forbade.

## The model I interpret

Full model: mode, log weight, grouped INCO, Orgenics indicator. n = **5,963**. R-squared **0.6660299231602032**. Adjusted **0.6654688175203514**. Ten regressors besides the intercept: three modes, log weight, five INCO dummies, Orgenics. HC1 95% intervals.

| Term | Level n | Coefficient | HC1 95% interval | exp(coefficient) − 1 | Contains 0? |
|---|---:|---:|---|---:|---|
| Air Charter vs Air | 423 | 0.5044214943619498 | 0.4001457739528387 to 0.6086972147710609 | 0.6560272222122925 | No |
| Ocean vs Air | 282 | 0.0783298510652921 | −0.0463092083181107 to 0.202968910448695 | 0.0814793269512292 | **Yes** |
| Truck vs Air | 1,162 | −0.444304491169107 | −0.5134742340654226 to −0.3751347482727915 | −0.3587298699949353 | No |
| log(weight kg) | 5,963 | −0.5049510700069987 | −0.521310803420571 to −0.4885913365934263 | −0.3964648943269261 | No |
| CIP vs N/A - From RDC | 163 | −0.7380293127181504 | −0.9432394158153252 to −0.5328192096209756 | −0.5219449150829699 | No |
| DDP vs N/A - From RDC | 296 | −0.6640875885511761 | −0.785746003535495 to −0.5424291735668573 | −0.4852570291087608 | No |
| EXW vs N/A - From RDC | 2,163 | 0.1598111380228407 | 0.1051869931668938 to 0.2144352828787877 | 0.1732892603360689 | No |
| FCA vs N/A - From RDC | 352 | −0.0144143119381717 | −0.1086712524114007 to 0.0798426285350572 | −0.0143109230996327 | **Yes** |
| Orgenics vs everyone else | 600 | 0.5726954445178964 | 0.4950374164667409 to 0.650353472569052 | 0.7730397465414947 | No |

In words. Truck's rate is lower than air's, about 36 percent, after weight, INCO, and Orgenics. The interval does not contain zero. Air charter's rate is higher than air's, about 66 percent, on the same controls. The interval does not contain zero. Ocean's point estimate is a small positive number and the interval contains zero, so ocean is not distinguished from air in this model. FCA is not distinguished from `N/A - From RDC`.

EXW is higher than `N/A - From RDC`, about 17 percent. CIP and DDP are lower, about 52 percent and about 49 percent, on the shipments that had a numeric freight. I would not walk into a meeting and call CIP or DDP a saving. The shipments where those terms hid the freight are not in the regression. They were not set to zero. They were counted in Analyze: 89 included-in-price on CIP at shipment grain, 313 on DDP.

The Other INCO coefficient is in the file. Six shipments. I am not using it.

log weight, −0.5049510700069987, interval −0.521310803420571 to −0.4885913365934263. The rate falls as shipments get heavier. A 1 percent difference in weight lines up with about a 0.505 percent difference in the rate, in the other direction. For a doubling: ln(2) × −0.5049510700069987 = −0.3500054104960787, and exp(−0.3500054104960787) − 1 = −0.29531572298311837. About 30 percent lower rate at twice the weight, holding mode, INCO, and Orgenics. That is a description of this extract. It is not a lever.

The chart `images/construct_mode_coefficients.png` is these three mode coefficients, full model in blue and the p95 cut in red. Zero is Air. The title says log freight per kilogram, the named-mode weighed sample, and that it is not a dollar saving.

### Orgenics

The coefficient is **0.5726954445178964**, interval **0.4950374164667409 to 0.650353472569052**, exp(coefficient) − 1 = **0.7730397465414947**. About 77 percent higher than other vendors, holding mode, log weight, and INCO. The interval does not contain zero. It is not a dollar saving and it is not the scorecard's median gap. The scorecard compared medians inside air and a weight band. This coefficient is a log-rate gap with a continuous weight control and an INCO control.

Where the 600 rows are, `construct_orgenics_by_mode.csv`:

| Mode | Orgenics n | Other n | Orgenics median rate | Other median rate |
|---|---:|---:|---:|---:|
| Air | 599 | 3,497 | 17.334166666666665 | 8.772086217124778 |
| Ocean | 1 | 281 | 4.020758583976577 | 1.680848101265823 |
| Air Charter | 0 | 423 |  | 4.317785194174758 |
| Truck | 0 | 1,162 |  | 2.5032950842130277 |

599 + 1 = 600. 599 / 600 = 0.9983333333333333. The indicator is an air comparison plus one ocean shipment. It is not a vendor that is expensive because it flies: mode is in the model, and inside air the Orgenics median is still 17.334166666666665 against 8.772086217124778. I would tell a procurement lead that Orgenics stayed high after mode, weight, and INCO. I would not quote 77 percent as money to take out of a contract.

### Does anything beyond mode add fit?

Yes. Mode-only R-squared 0.1714216189489614. Full model 0.6660299231602032. The difference is 0.6660299231602032 − 0.1714216189489614 = **0.4946083042112417**. Almost all of that arrives when log weight is added (mode and log weight already reach 0.624897919846368). Grouped INCO and the Orgenics indicator are the rest of the step to 0.6660299231602032.

The joint HC1 Wald test that log weight, the five INCO dummies, and Orgenics are all zero has statistic **5027.853688670431** on 7 restrictions. statsmodels stored the p-value as **0.0**, which is underflow at this statistic, not a test that failed to run. `construct_wald.csv`. I would say the extra terms add fit. I would not say the p-value is a causal claim.

## Country, as a check, not as the headline

Same 5,963 rows. Countries with at least 50 model rows stay named. The rest are Other (211 rows). Reference Nigeria (748). R-squared **0.6883078381217647**. Adjusted **0.6867315122862374**. The gain on the headline model is 0.6883078381217647 − 0.6660299231602032 = **0.0222779149615615**.

The HC1 Wald test that the 20 country coefficients are jointly zero has statistic **413.8245469809**, 20 restrictions, p-value **2.7584772766328093e-75**. So country adds something. The something is small next to the 0.4946083042112417 that weight, INCO, and Orgenics add beyond mode. I do not one-hot 43 countries, and I do not call Botswana or South Sudan expensive off this check. Botswana and South Sudan each have 59 model rows, which clears the pool rule and is still not a procurement ranking. The coefficients are in `construct_coefficients.csv` under `full_log_rate_plus_country` for anyone who wants the level. They are not the model I interpret. The headline formula does not contain country.

## The short dollar comparison

Same 5,963 rows. Outcome log(freight dollars). Not interpreted.

| Model | R-squared | log(weight) coefficient | HC1 95% interval |
|---|---:|---:|---|
| log weight only | 0.5288105987422616 | 0.4689278220545754 | 0.4556750520294901 to 0.4821805920796606 |
| log weight and mode | 0.5688396986201978 | 0.4967818574232516 | 0.480673688088747 to 0.5128900267577563 |

Mode adds 0.5688396986201978 − 0.5288105987422616 = **0.0400290998779362** of R-squared on top of weight. The dollar elasticity is about 0.47 to 0.50, not 1. Heavier shipments cost more dollars, and not in proportion. On the matching rate regression (mode and log weight), the weight coefficient is −0.5032181425767487. The dollar model's weight coefficient minus 1 is 0.4967818574232516 − 1 = −0.5032181425767484. Same fact, two outcomes. A model of raw dollars mostly finds weight. The plan already expected that. It is why the headline is the rate.

## Sensitivity: rates at or below the weighed-set p95

The cut is freight per kilogram **greater than 67.64871004566209**, the p95 of all 6,174 weighed shipments, blank mode included. Applied to the model rows, that drops **305** shipments and leaves **5,658**. 5,658 + 305 = 5,963. Of the 305, 232 are Air, 47 are Air Charter, 20 are Truck, and 6 are Ocean. 232 + 47 + 20 + 6 = 305. Four blank-mode weighed shipments are also above the p95. They were already out of the model. The formula and the reference levels are not re-picked on the trimmed sample.

| Term | Full model | At or below p95 | What changes |
|---|---|---|---|
| Air Charter vs Air | 0.5044214943619498 (0.4001457739528387 to 0.6086972147710609) | 0.191629187660976 (0.1022992073352945 to 0.2809591679866576) | Shrinks. Still above air. Interval still excludes zero. n at this level 376, from 423 |
| Ocean vs Air | 0.0783298510652921 (−0.0463092083181107 to 0.202968910448695) | −0.0728872796681124 (−0.1835926916703626 to 0.0378181323341378) | Point estimate changes sign. **Both intervals contain zero** |
| Truck vs Air | −0.444304491169107 (−0.5134742340654226 to −0.3751347482727915) | −0.5270787245364076 (−0.592743463412094 to −0.461413985660721) | Still lower. Interval still excludes zero |
| log(weight) | −0.5049510700069987 (−0.521310803420571 to −0.4885913365934263) | −0.4088697343861048 (−0.4245428785493292 to −0.3931965902228805) | Still negative. The slope is flatter. Interval still excludes zero |
| Orgenics | 0.5726954445178964 (0.4950374164667409 to 0.650353472569052) | 0.5994684372852546 (0.5247227556656192 to 0.6742141189048899) | Still higher. 567 of the 600 Orgenics rows remain |

R-squared on the trimmed sample is **0.6094230866419924**. That R-squared is not comparable as a contest with 0.6660299231602032, because the outcome's tail was cut. The comparison that matters is the coefficients.

Air is the reference, so there is no air coefficient to watch. The air gap is these contrasts. The charter-versus-air gap is the one that moves: 0.5044214943619498 down to 0.191629187660976, which is exp(coefficient) − 1 of 0.6560272222122925 down to 0.2112212978795158. The tail, including the 4 kg charter, inflates how large that premium looks. It does not create the premium. Truck, the weight slope, and Orgenics do not change their story. Ocean was already not distinguished from air, and it still is not.

## Assumptions I would say out loud

- The fit is observational. A coefficient is a partial association in this extract. It is not the effect of switching a shipment onto another mode, another vendor, or another INCO term.
- The window is historical. Delivered to client runs from 2006-05-02 to 2015-09-14. These are not current market rates.
- INCO term changes what freight is visible. Included-in-price and invoiced separately are missing from the outcome. They are not cheap shipments. DDP and CIP look low here because the hidden bills never entered.
- Excluded notes are missing, not zero. That includes the 593, the 239, the 23 captured-separately weights, `ASN-22365`, and, for the regression only, the 211 blank modes.
- The log and the HC1 intervals are concessions to a heavy tail. They are not a claim that the residuals are normal, and they are not a claim that the association is causal.
- Orgenics is one vendor indicator, not a full vendor model. Country is a check, not a lane ranking.

## Dashboard extract

`dashboards/shipment_weighed.csv` is the weighed set, **6,174** rows, one per ASN/DN. Columns: `asn_dn`, `shipment_mode`, `country`, `vendor`, `vendor_inco_term`, `weight_kg`, `freight_usd`, `freight_per_kg`, `line_item_value_sum`, and `in_regression_sample` (1 on the 5,963, 0 on the 211 blank-mode rows). No manufacturing site. No insurance. No savings column. Included-in-price and invoiced shipments are not in the file and are not zeros. `dashboards/TABLEAU.md` says which sheets to build and which filters to put on them. Nothing was published to Tableau Public. This machine was not signed in. Publishing is Execute.

## What Execute still has to do

- A **savings scenario**, if one is published at all: a stated share of priced air shipments above a stated weight, priced at a cheaper mode's median freight per kilogram that we actually observe, next to the shipments that were excluded and next to the reasons the scenario would be wrong. The goods may not be able to move by that mode. The INCO term may mean the invoice is not the real cost. The extract delivered from 2006-05-02 through 2015-09-14. This page does not compute that scenario. The charter and ocean coefficients above are not inputs to a dollar saving. Ocean is not distinguished from air once INCO is held constant, which is a reason to be careful about an "air to ocean" dollar figure that ignores terms.
- The **executive summary** and the **business report**. Key Findings, Recommendation, and Impact in the project README are still empty on purpose.
- **Tableau Public.** The extract and the sheet list exist. The workbook does not, and there is no URL.

## Before Execute

The regression rules from the plan are the ones this page fit: freight per kilogram, not raw dollars as the headline; no manufacturing site; no insurance; no zero-filled text; no 73 vendor coefficients; no 43 country coefficients in the model I interpret. Send **E** for Execute if this sample and this log model are the ones to carry forward.
