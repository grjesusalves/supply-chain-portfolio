# Plan — Late delivery risk (DataCo)

PACE stage: **Plan**. This page settles the question, what "late" means, which numbers we will trust, and what the model is allowed to see. It computes no late rate, fits no classifier, and recommends no shipping mode; those tasks belong to Analyze, Construct, and Execute.

Read this page first. The checks Analyze will run are listed at the bottom, and the project README points here.

## How I would say this in an interview

The business is not asking for a model. It is asking which orders are likely to miss the date the customer was promised, and whether those misses cluster in a shipping mode, a region, or a product category.

I split that question into two jobs that draw on the same data and must not be confused.

The first job is a scorecard. Once deliveries have happened, what share arrived on time, how many days did shipping actually take, and which mode, region, or category accounts for the misses? That is descriptive work. SQL is the right tool, because the question calls for a few grouped rates, not a prediction.

The second job is a watchlist. At the moment an order is placed, before the carrier has moved it, which orders deserve attention because they resemble past late orders? That is a classification model, and it is useful only if it relies on information the business would actually hold at order time. If I let it see the delivery status, I am not predicting lateness; I am reading the answer key.

Plan is where I write those rules down, before any chart can tempt me to change the question.

## Business question

Which orders are likely to arrive late, and which shipping modes, regions, or product categories drive the delays?

Who uses the answer:

- A **fulfillment lead** uses the scorecard. If one shipping mode misses its own promise far more often than the others, the fix is the promise or the carrier, not a smarter model.
- A **regional operator** uses the same scorecard, cut by order region and market. A region with a worse slip has an execution problem; a region that looks worse only because it relies on a slower mode has a mix problem. Analyze has to separate the two.
- A **category manager** uses the cut by department and category, for the same reason. A category that is late because it ships First Class calls for a different conversation from a category that is late inside Standard Class.
- The **watchlist** serves whoever can still intervene before the ship date: customer service, or the person assigning a shipping mode. That person does not yet know the actual transit days, and the model is not allowed to know them either.

## What "late" means

The file already carries a label, `Late_delivery_risk`: 1 if the shipment is late, 0 if it is not. The data dictionary (Constante, Silva, and Pereira, 2019) also lists:

- `Delivery Status`, with four values named in the dictionary: Late delivery, Advance shipping, Shipping on time, Shipping canceled.
- `Days for shipping (real)`: actual shipping days.
- `Days for shipment (scheduled)`: the promised shipping days.
- `Shipping Mode`, with four values named in the dictionary: Standard Class, First Class, Second Class, Same Day.

**Decision.** The prediction target is `Late_delivery_risk`. The business question concerns arriving late, not being early, canceled, or merely "not perfect." Early (`Advance shipping`) is not a late delivery, and a cancel is not a delivery at all.

I will not assume, at the Plan stage, that the flag equals "real days greater than scheduled days," or that it lines up one-for-one with `Delivery Status`. Other public write-ups claim a perfect match between late status and the flag; that is their result, not ours. Analyze will build the cross-tab and the day comparison, and we will keep the flag as the target only if that check agrees. Should the flag and the day comparison disagree, we stop and commit to one definition in writing before any model is fit.

**Decision.** `Delivery Status`, `Days for shipping (real)`, and anything else known only after the shipment has moved are **outcome fields**. They may define the KPI; they may not be inputs to the classifier. Putting them in the model would make its accuracy look excellent and render it useless on a new order.

## KPIs we will compute later, and the formulas now

None of these numbers is calculated at this stage. The formulas are fixed now so that Analyze cannot quietly change the denominator.

The file has **180,519 rows and 53 columns** (see `data/README.md`). A row is an order line, not necessarily a unique order, and `Order Id` can repeat. Until Analyze checks whether every line on an order shares the same shipping outcome, every KPI below is computed at **line** grain. If lines on one order disagree, we will also publish an order-level rate, with the rule stated at that point; we will not invent that rule now.

**On-time delivery rate.** Among lines that were not canceled, the share with `Late_delivery_risk` = 0.

In words: take the lines that were genuinely a delivery attempt, count how many were not flagged late, and divide by the number of delivery attempts.

**Late rate.** One minus the on-time delivery rate, on the same denominator. Reporting both is fine; they express the same fact.

**Why canceled lines leave the denominator.** A canceled shipment neither kept nor broke a delivery promise. If cancels are coded as "not late," leaving them in makes on-time delivery look better than the operation actually was. Analyze will count how many lines are `Shipping canceled` and confirm how the flag treats them. The exclusion stands unless that check shows cancels are already absent.

**Lead time.** `Days for shipping (real)`, on the same non-canceled lines. We will report the **median** and show the mean beside it. A handful of very long shipments pulls a mean upward; a fulfillment lead acts on the typical shipment, which the median captures, and on the tail, which the mean hints at.

**Schedule slip.** Real days minus scheduled days, on the same lines. A positive slip means the shipment took longer than promised. This is the operational reading of lateness: not merely a 0/1 flag, but the number of days by which the promise was missed. We will report the median slip overall and by shipping mode, order region, and category.

**The cuts that answer "what drives delays."** Late rate and median slip by:

- `Shipping Mode`
- `Order Region` and `Market` (region is the finer cut; market is the rollup)
- `Category Name` and `Department Name` (category is the finer cut; department is the rollup)

A high late **count** is not a high late **rate**. Standard Class may hold the most late lines simply because it holds the most lines. The scorecard therefore leads with the rate and the slip, while volume serves as context, which is why the line count appears beside every rate. Those grouped rates are built in SQL, in `sql/`, so that the definition lives in one query rather than only inside a Python notebook.

## What the classifier is allowed to see

Known when the order is placed, and therefore allowed as candidate features:

- `Shipping Mode` and `Days for shipment (scheduled)` (the promise itself; these two may be the same fact written twice, and Analyze will check)
- `Order Region`, `Market`, `Order Country`
- `Category Name`, `Department Name`, `Product Name` (product name is high cardinality; we may keep department and category and drop the raw product name if it only memorizes rare items)
- `Customer Segment`
- quantity, price, sales, and discount fields that exist on the order line
- calendar parts of the order date (month, day of week), not the shipping date

Not allowed as features:

- `Late_delivery_risk` (the target)
- `Delivery Status`
- `Days for shipping (real)`
- `Shipping date (DateOrders)`, if it records the moment the goods actually moved rather than a planned date. Analyze will confirm which date is which before either is used.

Customer name, email, and street-level identifiers are personal data. They are not predictors we want, and they have no place in a public portfolio notebook; Analyze will drop them before any table is written to `data/processed/`.

## How we will know the model worked

A late-delivery classifier is easy to over-praise. If most lines are late, a model that declares "everything is late" earns a high accuracy while doing nothing, so accuracy will not be the headline score. We do not yet know the class balance; Analyze will measure it, and Plan does not borrow a percentage from someone else's notebook.

There are three comparisons, all scored on a held-out slice of lines and never on the rows the model was fit on:

1. **Majority-class baseline.** Predict the more common label for every line. This is the score earned by doing nothing.
2. **Shipping-mode baseline.** Predict using only `Shipping Mode`, with each mode's late rate estimated on the training rows alone. If the full model cannot beat this, the other features add no operational signal, and the honest recommendation is "manage the mode," not "deploy a model."
3. **The model.** A logistic regression first, because a coefficient on shipping mode is something a fulfillment lead can argue with. Then one tree model in scikit-learn, because interactions (a category that is late only in one region) are precisely what a single coefficient misses. We will not tune a long list of models; two, plus the two baselines, is enough to defend in an interview.

Scores we will report:

- **ROC AUC**, for ranking: does a line that was actually late tend to receive a higher risk score than a line that was not?
- **Average precision**, because it attends to the late class rather than to easy on-time lines.
- **Recall on late lines** at one chosen threshold: of the lines that were late, what share did we flag? Missing a late line is the operational failure. The threshold itself is an Execute decision, since it trades false alarms against missed lates, and Plan does not pick it.

## Scope

| Decision | Choice | Why |
|---|---|---|
| Dataset | DataCo Smart Supply Chain, Mendeley Data, DOI 10.17632/8gx2fvg2k6.5, CC BY 4.0 | Already on disk at `data/raw/DataCoSupplyChainDataset.csv`. Latin-1. 180,519 lines, 53 columns. Cite Constante, Silva, and Pereira (2019). |
| File we will not use | `tokenized_access_logs.csv` | Web logs. Different question. |
| Grain | Order line, until Analyze checks `Order Id` | The flag lives on the line. |
| Target | `Late_delivery_risk` | Matches "arrive late." Early is not late. |
| KPI population | Drop canceled lines | A cancel is not an on-time delivery. |
| Model inputs | Order-time fields only | Otherwise the model sees the outcome. |
| Models | Logistic regression, then one scikit-learn tree model | Interpretable first, then interactions. |
| KPI tool | SQL | The scorecard is a grouped rate. |
| Model tool | Python, scikit-learn | What the project brief asked for. |
| Dashboard | Not in this stage | Tableau Public is an Execute deliverable, after the scorecard and the model exist. |

## Out of scope

- A dollar cost per late day. The file has sales and profit fields, but it states no penalty for lateness, so any cost figure here would be invented. If Execute wants a cost, it will use an assumption clearly labeled as such.
- Fraud, payment type, and the access logs.
- Changing the customer's shipping mode within this project. We may recommend it; we will not simulate a re-price.
- Tableau, the executive summary, and the business report. Those belong to Execute; Plan only reserves the folders.

## What Analyze will check

1. Confirm 180,519 rows and 53 columns, and that the read uses Latin-1.
2. Count distinct `Order Id` against rows. If they differ, show whether shipping mode, the late flag, and real days are constant inside an order.
3. Cross-tab `Late_delivery_risk` against `Delivery Status`.
4. Compare the flag to `Days for shipping (real)` minus `Days for shipment (scheduled)`. Record every disagreement rather than smoothing it over.
5. Count canceled lines and how the flag labels them.
6. Measure the class balance of the flag on the non-canceled lines. This is the first time a late rate is stated, and it will be computed, not assumed.
7. Nulls, especially on the candidate features.
8. Whether `Days for shipment (scheduled)` is a one-to-one relabeling of `Shipping Mode`.
9. Cardinality of region, category, and product name, so that Construct does not one-hot encode a column with thousands of levels by accident.
10. Personal-data columns to drop before anything is saved under `data/processed/`.

## Decisions locked here

- The target is `Late_delivery_risk`, subject to the day-comparison check.
- The on-time rate excludes canceled lines.
- The classifier does not see outcome fields.
- The headline model scores are ROC AUC, average precision, and late-class recall, measured against a majority baseline and a shipping-mode baseline.
- Logistic regression first, then one tree model; no model horse race.
- No Tableau and no executive write-up until Execute.

## Before Analyze

There is nothing to download. `DataCoSupplyChainDataset.csv` is already in `data/raw/` on the project machine, and it stays git-ignored because of its size. GitHub is already connected, and Tableau Public is not needed until Execute.

Send **A** for Analyze. If you want canceled lines kept in the on-time rate, or the target defined as "real days greater than scheduled days" instead of the published flag, say so before sending A; otherwise, both decisions stand.
