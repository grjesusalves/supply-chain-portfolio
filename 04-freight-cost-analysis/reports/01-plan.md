# Plan — Freight cost (USAID SCMS)

PACE stage: **Plan**. This page settles the question, the unit of analysis, which dollar figures we will trust, and what a later model is allowed to explain. It computes no freight rate, fits no regression, and recommends no mode shift; those tasks belong to Analyze, Construct, and Execute.

Read this page first. The checks Analyze will run are listed at the bottom, and the project README points here.

## How I would say this in an interview

The business is not asking for a model. It is asking what drives freight and shipment cost across vendors, countries, and shipping modes, and where money could come out.

I would split that question into two jobs that draw on the same file and must not be confused.

The first job is a scorecard. Across the shipments in this extract, what did freight actually cost, per kilogram and as a share of cargo value, and which mode, country, or vendor accounts for the expensive shipments? That is descriptive work. The comparison is fair only if a big shipment and a small one are not treated as the same kind of bill, and only if one delivery-note freight charge is not counted once for every line on that note.

The second job is an explanation. Once weight, value, and mode are held constant, does vendor, country, or INCO term still move the bill? That is a regression, and it comes later, in Construct. A coefficient is not a savings promise; the savings number, if we publish one, is a scenario with its assumption written on it, and that belongs to Execute.

Plan is where I write those rules down, before a chart proclaiming "air is expensive" can tempt me to skip the grain problem.

## Business question

What drives freight and shipment cost across vendors, countries, and shipping modes, and where could we save money?

Who uses the answer:

- A **procurement lead** uses the scorecard to decide which vendors and lanes to challenge. A vendor that looks expensive only because it ships light freight by air calls for a different conversation from a vendor that is expensive inside the same mode and the same weight band.
- A **logistics lead** uses the mode comparison. The actionable case is a lane heavy enough for a cheaper mode and not obviously an emergency. Air versus ocean is not a moral ranking; it is a cost ranking that must still respect what the shipment was.
- A **finance partner** uses the savings scenario, and only if the denominator, the dropped rows, and the assumption are on the page. A single dollar figure without a line such as "this excludes freight that was bundled into the product price" will not survive that meeting.

This is a public historical extract of USAID supply-chain shipments of antiretrovirals and HIV lab commodities, not USAID's internal decision file, and I would say so out loud.

## The file

The source, and the reason this copy exists, are in `data/README.md`. In short, the official data.usaid.gov file no longer resolves. The copy on disk is the mudar-hussain GitHub mirror of `SCMS_Delivery_History_Dataset`, kept because it matches the published profile of the 2015-09-29 SCMS extract. It is U.S. government work, in the public domain. Re-check it against an official file if one comes back.

Verified on the project copy, read as Latin-1: **10,324 data rows and 33 columns**. That count is a file check, not a finding about freight.

A row is a **line item** on a delivery, not a shipment; the shipment identifier is `ASN/DN #`. The fields this question actually uses:

- Who and where: `Country`, `Vendor`, `Manufacturing Site`, `Managed By`, `Fulfill Via`
- Commercial terms: `Vendor INCO Term`, `Shipment Mode`
- What moved: `Product Group`, `Sub Classification`, `Item Description`, `Molecule/Test Type`, `Line Item Quantity`, `Line Item Value`
- The money and the weight: `Weight (Kilograms)`, `Freight Cost (USD)`, `Line Item Insurance (USD)`

The dates (`Scheduled Delivery Date`, `Delivered to Client Date`, and the PQ/PO dates) describe the window of the extract; they are not the question. USAID's own description of this dataset warns that conclusions about the cost of moving a specific line item, and about lead time, will not be accurate. We will not build a lead-time recommendation on top of that warning.

`Line Item Insurance (USD)` is not freight, and the headline metric stays freight. Folding insurance in would silently change the question to "landed logistics extras," which we will not do unless we label a second metric.

## Unit of analysis

**Decision.** Freight money is analyzed at **shipment** grain, one row per `ASN/DN #`. Line items stay in the work only to describe what was on the shipment: product group, total quantity, total line-item value, vendor, country, mode, and INCO term.

Why this is a decision rather than a preference: `Freight Cost (USD)` is one field on every line. If the same delivery-note charge is repeated on every line, averaging the lines counts a five-line shipment five times and lets multi-line shipments dominate the mean. USAID's note that line-item freight conclusions will not be accurate is the same warning in their words.

Analyze must prove that the field behaves this way before we roll it up. The check: within one `ASN/DN #`, is `Freight Cost (USD)` constant, and is `Weight (Kilograms)` constant? If both are, the shipment takes that one freight figure and that one weight, and line-item value is **summed**. If they are not, we stop and write a new rule; we do not average conflicting freight strings and move on.

**Decision.** Rows whose freight or weight is not a number do not receive a zero. They leave the per-kilogram metric, and we report how many shipments that drop removes. Putting a zero on "freight included in commodity cost" would make those shipments look free.

The non-numeric cases we will look for, given that this field is text in the file and the published description of the extract says as much, are phrases such as freight included in the commodity cost, invoiced separately, and a pointer to another delivery note ("see DN"). Weight suffers from the same kind of problem ("weight captured separately," pointers at another note). Those are labels to classify. Analyze counts them; Plan does not borrow counts from someone else's notebook.

## KPIs we will compute later, and the formulas now

None of these numbers is calculated at this stage. The formulas are fixed now so that Analyze cannot quietly change the denominator.

The population for every freight KPI is the set of shipments whose freight parsed as a number; call that the **priced set**. A second, stricter set, the **weighed set**, also requires weight to parse as a number. Per-kilogram metrics use the weighed set. Dollar totals for "how much freight did we observe" use the priced set, and they always appear next to the count of shipments that were excluded, and why.

**Freight per kilogram.** Numeric freight divided by numeric weight, on the weighed set, at shipment grain. We will report the **median** and show the mean beside it. A few very expensive light shipments pull a mean upward; a logistics lead acts on the typical shipment, which the median captures, and on the tail, which the mean hints at.

**Freight as a share of cargo value.** Numeric freight divided by the sum of `Line Item Value` on that shipment, under the same weighed-or-priced logic: this one requires a numeric freight and a positive value sum. It answers "how heavy was the freight bill relative to the goods," which per-kilogram cannot.

**Mode, vendor, and country comparisons.** Median freight per kilogram, median freight-to-value, total numeric freight, and shipment count, cut by:

- `Shipment Mode`
- `Country`
- `Vendor`
- `Vendor INCO Term`
- `Manufacturing Site`, as a secondary cut, because origin can be the real driver hiding inside a vendor name

A high freight **total** is not a high freight **rate**. The largest vendors will carry the largest totals simply because they have the most shipments. The scorecard therefore leads with the median rate and shows the shipment count and the dollar total beside it. A vendor is not "expensive" on the scorecard unless it is high inside a comparison that holds mode and shipment size roughly constant. Construct is where "held constant" becomes a regression; in Analyze, "roughly constant" means a weight band or a simple split, stated in the write-up rather than applied as a silent filter.

**What we will not average.** A line-level mean of `Freight Cost (USD)`; a mean that treats "included in commodity cost" as zero; a freight total that sums the line-level field without first collapsing to `ASN/DN #`.

## What we expect, stated as hypotheses

These are not findings, and Analyze and Construct are free to reject every one of them.

- Air, and air charter if it appears, will show a higher median freight per kilogram than ocean or truck.
- Weight and cargo value will move the dollar bill, and mode will still matter once weight is held roughly constant. If it does not, the honest story is "you pay for kilograms," not "you pay for air."
- `Vendor INCO Term` changes what freight is even visible, since EXW and DDP do not put the same cost on the invoice. A term that often reads "included in commodity cost" is not a cheap term; it is a term where the freight is hidden in the product price, and it stays out of the priced set.
- A vendor, manufacturing site, or country can look expensive merely because of mix: light shipments, air, or a small count. The recommendation waits until the mix is separated from the rate.
- The savings case, if the data supports one, is a mode shift on lanes heavy enough for a cheaper mode and not obviously urgent. We will not infer urgency from a column that does not exist. Product group and first-line designation are the closest proxies in this file, and they are weak ones; Execute must say so.

## What a later regression is allowed to explain

This belongs to Construct, not this stage; the rule is written now so that the model cannot wander.

The outcome is shipment freight per kilogram on the weighed set, not the raw dollar bill. Raw dollars mostly rediscover that "heavier shipments cost more," which we already know before fitting anything.

Candidate inputs: `Shipment Mode`, `Vendor INCO Term`, `Country`, `Vendor`, a measure of shipment size (weight or line-item value, not both if they are the same fact), and `Manufacturing Site` only if its cardinality is something a regression can carry. Analyze will count distinct vendors, countries, and sites before Construct one-hot encodes them.

Not inputs: the freight field itself, insurance, line-item identifiers, and any column that is constant inside the shipment and was already used to build the outcome.

We will not treat a coefficient as savings. The savings figure is a scenario in Execute: take a stated share of priced air shipments that also sit above a stated weight, price them at the median freight per kilogram of a cheaper mode that we actually observe, and show the difference. Beside it go the shipments that were excluded and what would make the scenario wrong (the goods could not move by that mode, the INCO term means the invoice is not the real cost, the extract is a decade old).

## Scope

| Decision | Choice | Why |
|---|---|---|
| Dataset | SCMS delivery history mirror, 10,324 × 33, Latin-1 | Official URL is gone. See `data/README.md`. File check done on the project copy. |
| Grain for money | One row per `ASN/DN #` | Freight on a delivery note is not a line-item cost. |
| Grain for product mix | Line items, summed onto the shipment | The question still needs to say what moved. |
| Headline outcome | Median freight per kg, weighed set | Typical shipment, not a mean pulled by outliers, and not a fake zero. |
| Second outcome | Freight / sum of line-item value | Rate versus the goods, not only versus weight. |
| Insurance | Out of the headline | Different question. |
| Lead time | Context dates only, no recommendation | USAID says line-item lead-time conclusions will not be accurate. |
| Model | Later, in Construct: regression of freight per kg | Explanation after the scorecard, not instead of it. |
| Tools | Python for the rollup and the model; SQL for the grouped rates | Same split as the other projects in this portfolio. |
| Dashboard | Not in this stage | Tableau Public starts in Construct, once a clean shipment table exists, and the published story is Execute. |

## Out of scope

- Forecasting demand or freight.
- A lead-time or on-time-delivery scorecard; Project 03 already owns late delivery, on a different dataset.
- Rebuilding a vendor's price list. Pack price and unit price describe the commodity, not the freight.
- Treating this extract as current market rates. The file is the 2015 SCMS delivery history, so any dollar figure is historical.
- Tableau Public, the executive summary, and the business report. Plan only reserves the folders.

## What Analyze will check

1. Reconfirm 10,324 rows, 33 columns, and a Latin-1 read.
2. Count distinct `ASN/DN #` against rows.
3. Within one `ASN/DN #`, test whether `Freight Cost (USD)` is constant and whether `Weight (Kilograms)` is constant. This is the gate for the shipment rollup.
4. Classify freight strings into numeric, included-in-price, invoiced separately, see-another-note, and anything else, and do the same for weight. Publish the counts, and do not coerce the text to zero.
5. Count nulls and blank `Shipment Mode`.
6. List distinct `Shipment Mode` and `Vendor INCO Term` with shipment counts, before any ranking.
7. Cardinality of `Vendor`, `Country`, and `Manufacturing Site`.
8. Min and max of the delivery dates, so that the write-up can state which years this extract covers. That is context, not a trend claim.
9. Confirm that line-item value sums to a positive number on the shipments we keep, since a zero-value shipment cannot support a freight-to-value share.

## Decisions locked here

- Money sits at `ASN/DN #` grain, subject to the constancy check. If freight is not constant inside a delivery note, Analyze stops and we rewrite the rule.
- Non-numeric freight is excluded, never zeroed, and the exclusion is reported.
- The headline metric is median freight per kilogram on the weighed set. Freight-to-value sits beside it; insurance does not.
- Vendor and country comparisons must survive a control for mode and shipment size before anyone is called expensive.
- The regression explains freight per kilogram; it does not produce the savings number, which is a labeled scenario in Execute.
- No Tableau and no executive write-up until a clean shipment table exists. Tableau Public comes in at Construct.

## Before Analyze

There is nothing to download. `SCMS_Delivery_History_Dataset.csv` is already in `data/raw/` on the project machine, and it stays git-ignored because of its size. GitHub is already connected, and Tableau Public is not needed until Construct.

Send **A** for Analyze. If you want the grain to stay at line item, or insurance folded into the headline cost, say so before sending A; otherwise, both decisions stand.