# Plan — Late delivery risk (DataCo)

PACE stage: **Plan**. This page decides the question, what "late" means, which numbers we will trust, and what the model is allowed to see. It does not compute a late rate, fit a classifier, or recommend a shipping mode. Those belong to Analyze, Construct, and Execute.

Read this page first. The checks Analyze will run are at the bottom. The project README points here.

## How I would say this in an interview

The business is not asking for a model. It is asking which orders are likely to miss the date the customer was promised, and whether the misses cluster in a shipping mode, a region, or a product category.

I split that into two jobs that use the same data and must not be mixed up.

The first job is a scorecard. After deliveries have happened, what share arrived on time, how many days did shipping actually take, and which mode, region, or category accounts for the misses. That is descriptive. SQL is the right tool, because the question is a few grouped rates, not a prediction.

The second job is a watchlist. At the moment an order is placed, before the carrier has moved it, which orders deserve attention because they look like past late orders. That is a classification model. The model is only useful if it uses information the business would actually have at order time. If I let it see the delivery status, I am not predicting lateness. I am reading the answer key.

Plan is where I write those rules down, before any chart can tempt me to change the question.

## Business question

Which orders are likely to arrive late, and which shipping modes, regions, or product categories drive the delays?

Who uses the answer:

- A **fulfillment lead** uses the scorecard. If one shipping mode misses its own promise far more often than the others, the fix is the promise or the carrier, not a smarter model.
- A **regional operator** uses the same scorecard cut by order region and market. A region with a worse slip is an execution problem. A region that looks worse only because it uses a slower mode is a mix problem. Analyze has to separate those.
- A **category manager** uses the cut by department and category, for the same reason. A category that is late because it ships First Class is a different conversation from a category that is late inside Standard Class.
- The **watchlist** is for whoever can still intervene before the ship date: customer service, or the person assigning a shipping mode. That person does not yet know the actual transit days. The model is not allowed to know them either.

## What "late" means

The file already carries a label, `Late_delivery_risk`: 1 if the shipment is late, 0 if it is not. The data dictionary (Constante, Silva, and Pereira, 2019) also has:

- `Delivery Status`, with four values named in the dictionary: Late delivery, Advance shipping, Shipping on time, Shipping canceled.
- `Days for shipping (real)`: actual shipping days.
- `Days for shipment (scheduled)`: the promised shipping days.
- `Shipping Mode`, with four values named in the dictionary: Standard Class, First Class, Second Class, Same Day.

**Decision.** The prediction target is `Late_delivery_risk`. The business question is about arriving late, not about being early, canceled, or merely "not perfect." Early (`Advance shipping`) is not a late delivery. A cancel is not a delivery at all.

I am not going to assume, in Plan, that the flag equals "real days greater than scheduled days," or that it lines up one-for-one with `Delivery Status`. Other public writeups claim a perfect match between late status and the flag. That is their result, not ours. Analyze will build the cross-tab and the day comparison and we will keep the flag as the target only if that check agrees. If the flag and the day comparison disagree, we stop and pick one definition in writing before any model.

**Decision.** `Delivery Status`, `Days for shipping (real)`, and anything else that is only known after the shipment has moved are **outcome fields**. They may define the KPI. They may not be inputs to the classifier. Putting them in the model would make the accuracy look excellent and the model useless on a new order.

## KPIs we will compute later, and the formulas now

None of these numbers are calculated in this stage. The formulas are fixed so Analyze cannot quietly change the denominator.

The file has **180,519 rows and 53 columns** (see `data/README.md`). A row is an order line, not necessarily a unique order. `Order Id` can repeat. Until Analyze checks whether every line on one order shares the same shipping outcome, every KPI below is at **line** grain. If lines on one order disagree, we will also publish an order-level rate, with the rule stated at that point. We will not invent that rule now.

**On-time delivery rate.** Among lines that were not canceled, the share with `Late_delivery_risk` = 0.

In words: take the lines that were actually a delivery attempt, count how many were not flagged late, divide by how many delivery attempts there were.

**Late rate.** One minus the on-time delivery rate, on that same denominator. Reporting both is fine. They are the same fact.

**Why canceled lines leave the denominator.** A canceled shipment did not keep or break a delivery promise. If cancels are coded as "not late," leaving them in makes on-time delivery look better than the operation was. Analyze will count how many lines are `Shipping canceled` and confirm how the flag treats them. The exclusion stands unless that check shows cancels are already absent.

**Lead time.** `Days for shipping (real)`, on the same non-canceled lines. We will report the **median**, and we will show the mean beside it. A handful of very long shipments pull a mean up. A fulfillment lead acts on the typical shipment, which is the median, and on the tail, which the mean hints at.

**Schedule slip.** Real days minus scheduled days, on the same lines. Positive slip means the shipment took longer than the promise. This is the operational reading of lateness: not just a 0/1 flag, but by how many days the promise was missed. We will report median slip overall and by shipping mode, order region, and category.

**The cuts that answer "what drives delays."** Late rate and median slip by:

- `Shipping Mode`
- `Order Region` and `Market` (region is the finer cut; market is the rollup)
- `Category Name` and `Department Name` (category is the finer cut; department is the rollup)

A high late **count** is not a high late **rate**. Standard Class may have the most late lines simply because it has the most lines. The scorecard leads with the rate and the slip. Volume is context, so we also show the line count beside every rate. SQL is how those grouped rates get built, in `sql/`, so the definition lives in one query and not only inside a Python notebook.

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
- `Shipping date (DateOrders)`, if it is the moment the goods actually moved rather than a planned date. Analyze will confirm which date is which before either date is used.

Customer name, email, and street-level identifiers are personal data. They are not predictors we want, and they do not belong in a public portfolio notebook. Analyze will drop them before any table is written to `data/processed/`.

## How we will know the model worked

A late-delivery classifier is easy to over-praise. If most lines are late, a model that says "everything is late" has a high accuracy and does nothing. We will not use accuracy as the headline score. We do not yet know the class balance. Analyze will measure it. Plan does not borrow a percentage from someone else's notebook.

Three comparisons, all scored on a held-out slice of lines, never on the rows the model was fit on:

1. **Majority-class baseline.** Predict the more common label for every line. This is the score you get for doing nothing.
2. **Shipping-mode baseline.** Predict using only `Shipping Mode`, with the late rate of each mode estimated on the training rows only. If the full model cannot beat this, the other features are not adding an operational signal, and the honest recommendation is "manage the mode," not "deploy a model."
3. **The model.** A logistic regression first, because a coefficient on shipping mode is something a fulfillment lead can argue with. Then one tree model in scikit-learn, because interactions (a category that is late only in one region) are what a single coefficient misses. We will not tune a long list of models. Two, plus the two baselines, is enough to defend in an interview.

Scores we will report:

- **ROC AUC**, for ranking: does a line that was actually late tend to get a higher risk score than a line that was not.
- **Average precision**, because it pays attention to the late class rather than to easy on-time lines.
- **Recall on late lines** at one chosen threshold: of the lines that were late, what share did we flag. Missing a late line is the operational failure. The threshold itself is an Execute decision, because it trades false alarms for missed lates. Plan does not pick it.

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

- A dollar cost per late day. The file has sales and profit fields, but it does not state a penalty for being late. A cost number here would be invented. If Execute wants a cost, it will use an assumption we label as an assumption.
- Fraud, payment type, and the access logs.
- Changing the customer's shipping mode inside this project. We may recommend it. We will not simulate a re-price.
- Tableau, the executive summary, and the business report. Those are Execute. Plan only reserves the folders.

## What Analyze will check

1. Confirm 180,519 rows and 53 columns, and that the read uses Latin-1.
2. Count distinct `Order Id` versus rows. If they differ, show whether shipping mode, the late flag, and real days are constant inside an order.
3. Cross-tab `Late_delivery_risk` against `Delivery Status`.
4. Compare the flag to `Days for shipping (real)` minus `Days for shipment (scheduled)`. Record every disagreement. Do not smooth it over.
5. Count canceled lines and how the flag labels them.
6. Class balance of the flag on the non-canceled lines. This is the first time we state a late rate, and it will be computed, not assumed.
7. Nulls, especially on the candidate features.
8. Whether `Days for shipment (scheduled)` is a one-to-one relabeling of `Shipping Mode`.
9. Cardinality of region, category, and product name, so Construct does not one-hot encode a column with thousands of levels by accident.
10. Personal-data columns to drop before anything is saved under `data/processed/`.

## Decisions locked here

- Target is `Late_delivery_risk`, subject to the day-comparison check.
- On-time rate excludes canceled lines.
- The classifier does not see outcome fields.
- Headline model scores are ROC AUC, average precision, and late-class recall, against a majority baseline and a shipping-mode baseline.
- Logistic regression first, then one tree model. No model horse race.
- No Tableau and no executive writeup until Execute.

## Before Analyze

Nothing to download. `DataCoSupplyChainDataset.csv` is already in `data/raw/` on the project machine, and it stays git-ignored because of its size. GitHub is already connected. Tableau Public is not needed until Execute.

Send **A** for Analyze. If you want canceled lines kept in the on-time rate, or the target defined as "real days greater than scheduled days" instead of the published flag, say so before A. Otherwise those two decisions stand.
