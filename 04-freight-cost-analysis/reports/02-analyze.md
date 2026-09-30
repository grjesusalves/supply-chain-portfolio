# Analyze — Freight cost (USAID SCMS)

PACE stage: **Analyze**. This page checks the grain, classifies the freight and weight text, and stops before a rate. It does not publish median freight per kilogram, a mean, a freight-to-value share, a regression, a savings scenario, or a dashboard. The rate tables belong to a later commit, after the grain rule below is either confirmed or rewritten. The regression belongs to Construct. The savings number belongs to Execute.

The checks below are what [the plan](01-plan.md) said Analyze would confirm. Every figure comes from `src/analyze_freight.py` run on the local raw file (not re-downloaded). Aggregate tables are in `data/processed/`. The same line-level classes and the same constancy counts are defined in `sql/kpi_freight.sql`. Charts are in `images/`. The raw CSV stays git-ignored.

## How I would say this in an interview

The business question is what freight cost, per kilogram and against the value of the goods, and whether mode, country, or vendor is where the expensive shipments sit. That scorecard is not on this page. The field the scorecard needs is not a number on every line, and it is not the same string on every line of a delivery note.

There are **10,324 lines** and **7,030 distinct `ASN/DN #`**. Freight money was supposed to be one figure per delivery note, but only if the freight string is constant inside the note and the weight string is constant inside the note. Freight is not constant on **1,299 / 7,030** shipments. Weight is not constant on **1,322 / 7,030**. The plan said to stop there and not average the conflicting strings. I stopped. There is no median freight per kilogram in this stage, and no mean beside it, because there is no weighed set yet.

The disagreement is not two different dollar amounts. **0** shipments carry two different numeric freight strings. **0** carry two different numeric weights. The lines that disagree say `See ASN-… (ID#:…)` or `See DN-… (ID#:…)`. All **2,445** of those freight pointers name their own `ASN/DN #`, and all **2,445** cite the `ID` of the one line on that note marked `First Line Designation` = Yes. Every one of the 7,030 shipments has exactly one Yes line. That is a structure a later rule could use. It is not a rule I applied. Applying it would be inventing the rollup the gate told me not to invent.

What I can say without a rate: non-numeric freight was not turned into zero. `Freight Included in Commodity Cost` is **1,442 / 10,324** lines. `Invoiced Separately` is **239 / 10,324** lines. Those shipments are not free. Insurance was not added to anything. Mode, vendor, country, and INCO term do not vary inside an `ASN/DN #`. Manufacturing site does, on **880 / 7,030** shipments, so a site comparison would need its own rule even after freight is settled. The delivery dates in the file run from 2006 through 2015. Any dollar figure from this extract is historical. I would say that before I quoted a rate, and I am not quoting one yet.

## What was checked

The plan's nine checks. The rate cuts the plan listed after those checks were not computed, because check 3 failed.

1. Row and column count, and a Latin-1 read.
2. Distinct `ASN/DN #` versus rows.
3. Whether `Freight Cost (USD)` is constant inside one `ASN/DN #`, and whether `Weight (Kilograms)` is constant. This is the gate.
4. Freight strings classified as numeric, included-in-price, invoiced separately, see-another-note, or anything else. The same for weight. Line grain. Shipment-level class counts of the kind a rate would use were not published, because the gate did not pass. The pattern table in check 3 is the shipment count of those text patterns, and it is not a cost.
5. Nulls, and blank `Shipment Mode`.
6. Distinct `Shipment Mode` and `Vendor INCO Term` with line counts. Shipment counts for those fields were not added. The gate did not pass, so a shipment count would have required picking a line to speak for the note.
7. Cardinality of `Vendor`, `Country`, and `Manufacturing Site`.
8. Min and max of the delivery dates. Context for the extract, not a trend.
9. Whether line-item value is a positive number on the shipments we keep. No shipments were kept.

No regression.

## 1. Shape and encoding

| Check | Result |
|---|---|
| File | `data/raw/SCMS_Delivery_History_Dataset.csv` |
| Encoding used | **latin-1** |
| UTF-8 | Raises `UnicodeDecodeError`. The file is not UTF-8. |
| Rows | **10,324** |
| Columns | **33** |

The plan's expected size was 10,324 × 33. That is the file. The script refuses a different shape. Every column was read as text. A numeric dtype would have turned `See ASN-10007 (ID#:23194)` into a null and the classification would have been a silent drop.

`shape_check.csv`.

## 2. ASN/DN # is not the row

| Check | Result |
|---|---|
| Rows | 10,324 |
| Distinct `ASN/DN #` | **7,030** |
| Distinct `ID` | **10,324** (0 duplicate IDs) |
| Shipments with one line | **5,580** |
| Shipments with more than one line | **1,450** |

5,580 + 1,450 = 7,030 shipments. The one-line shipments account for 5,580 rows. The other 10,324 − 5,580 = 4,744 rows sit on the 1,450 multi-line notes.

| Lines on the shipment | Shipments | Line rows |
|---:|---:|---:|
| 1 | 5,580 | 5,580 |
| 2 | 819 | 1,638 |
| 3 | 312 | 936 |
| 4 | 120 | 480 |
| 5 | 67 | 335 |
| 6 | 41 | 246 |
| 7 | 15 | 105 |
| 8 | 14 | 112 |
| 9 | 6 | 54 |
| 10 | 10 | 100 |
| 11 | 4 | 44 |
| 12 | 2 | 24 |
| 13 | 7 | 91 |
| 14 | 9 | 126 |
| 15 | 9 | 135 |
| 16 | 6 | 96 |
| 17 | 5 | 85 |
| 19 | 1 | 19 |
| 26 | 1 | 26 |
| 38 | 1 | 38 |
| 54 | 1 | 54 |

The shipment column sums to 7,030 and the line-row column sums to 10,324. `grain_check.csv`, `lines_per_asn.csv`.

A one-line shipment is constant by definition. The gate in the next section is about the 1,450 notes that have something to disagree about, and about whether that disagreement is large enough to refuse a rollup for the whole file. It is.

## 3. Constancy gate

**The gate did not pass.**

A shipment is constant on a column when every line on that `ASN/DN #` has the same string, with a null counted as its own value. Freight and weight are the money gate. The other columns are the ones a rollup would also have had to copy. They are here so a later stage does not assume them.

| Column | Shipments | Not constant | Constant | Money gate |
|---|---:|---:|---:|---|
| Freight Cost (USD) | 7,030 | **1,299** | 5,731 | Yes |
| Weight (Kilograms) | 7,030 | **1,322** | 5,708 | Yes |
| Shipment Mode | 7,030 | **0** | 7,030 | No |
| Vendor | 7,030 | **0** | 7,030 | No |
| Country | 7,030 | **0** | 7,030 | No |
| Vendor INCO Term | 7,030 | **0** | 7,030 | No |
| Manufacturing Site | 7,030 | **880** | 6,150 | No |
| First Line Designation | 7,030 | **1,450** | 5,580 | No |
| Managed By | 7,030 | **0** | 7,030 | No |
| Fulfill Via | 7,030 | **0** | 7,030 | No |
| Product Group | 7,030 | **0** | 7,030 | No |

1,299 + 5,731 = 7,030. 1,322 + 5,708 = 7,030. 880 + 6,150 = 7,030. The 1,450 shipments where `First Line Designation` is not constant are the same 1,450 multi-line shipments. The 5,580 where it is constant are the one-line shipments. `constancy_by_column.csv`.

Mode, vendor, country, and INCO term do not need a tie-break. They are one value per note on all 7,030, including notes whose mode is blank: a blank is not mixed with a named mode inside the same `ASN/DN #`, because the disagreement count is 0. Manufacturing site is mixed on 880 shipments. Product group is not mixed.

`shipment_rollup_status.csv` is the decision row:

| Field | Value |
|---|---|
| gate_passed | **0** |
| shipments | 7,030 |
| shipments, freight not constant | 1,299 |
| shipments, weight not constant | 1,322 |
| shipments with two distinct numeric freight strings | **0** |
| shipments with two distinct numeric weight strings | **0** |
| median freight per kg | not computed |
| mean freight per kg | not computed |
| weighed shipments | not computed |

Reason stored on that row: not computed; freight or weight is not constant inside `ASN/DN #`, and no rollup rule was invented.

### What the disagreement looks like

The pattern table counts shipments by the set of freight labels on the note and the set of weight labels on the note. It does not pick a dollar. It covers every shipment.

| Freight pattern | Weight pattern | Shipments | Line rows |
|---|---|---:|---:|
| constant_numeric | constant_numeric | 4,942 | 4,942 |
| mixed_numeric_and_see | mixed_numeric_and_see | 1,233 | 3,551 |
| constant_included_in_price | constant_captured_separately | 397 | 1,217 |
| constant_invoiced_separately | constant_captured_separately | 181 | 181 |
| constant_included_in_price | constant_numeric | 173 | 173 |
| mixed_invoiced_and_see | mixed_captured_and_see | 57 | 161 |
| constant_included_in_price | mixed_captured_and_numeric | 23 | 52 |
| constant_numeric | constant_captured_separately | 15 | 15 |
| mixed_numeric_and_see | mixed_captured_and_see | 8 | 30 |
| mixed_invoiced_and_see | mixed_numeric_and_see | 1 | 2 |

Shipments: 4,942 + 1,233 + 397 + 181 + 173 + 57 + 23 + 15 + 8 + 1 = 7,030. Line rows: 4,942 + 3,551 + 1,217 + 181 + 173 + 161 + 52 + 15 + 30 + 2 = 10,324. The column `shipments_with_two_numeric_freights` is 0 on every row of `text_pattern_by_shipment.csv`, and the same for weight.

Freight patterns, rolled up from that table (still text, still not a rate):

| Freight text on the shipment | Shipments | Line rows |
|---|---:|---:|
| Constant numeric | 4,942 + 15 = **4,957** | 4,957 |
| Constant `Freight Included in Commodity Cost` | 397 + 173 + 23 = **593** | 1,217 + 173 + 52 = **1,442** |
| Constant `Invoiced Separately` | **181** | 181 |
| Mixed: a number and a See pointer | 1,233 + 8 = **1,241** | 3,551 + 30 = **3,581** |
| Mixed: `Invoiced Separately` and a See pointer | 57 + 1 = **58** | 161 + 2 = **163** |

4,957 + 593 + 181 + 1,241 + 58 = 7,030. The 1,299 non-constant freight shipments are 1,241 + 58. The constant freight shipments are 4,957 + 593 + 181 = 5,731, which matches the constancy table.

Every constant-numeric freight shipment is one line (4,957 shipments, 4,957 rows). Every constant-invoiced shipment is one line (181 and 181). The included-in-price phrase is never mixed with a See pointer: all 1,442 included lines sit on the 593 shipments where that phrase is the only freight string.

Weight patterns from the same table:

| Weight text on the shipment | Shipments | Line rows |
|---|---:|---:|
| Constant numeric | 4,942 + 173 = **5,115** | 4,942 + 173 = 5,115 |
| Constant `Weight Captured Separately` | 397 + 181 + 15 = **593** | 1,217 + 181 + 15 = 1,413 |
| Mixed: a number and a See pointer | 1,233 + 1 = **1,234** | 3,551 + 2 = 3,553 |
| Mixed: captured separately and a See pointer | 57 + 8 = **65** | 161 + 30 = 191 |
| Mixed: captured separately and a number | **23** | 52 |

5,115 + 593 + 1,234 + 65 + 23 = 7,030. The 1,322 non-constant weight shipments are 1,234 + 65 + 23. The 23 are the case the freight gate would have missed on its own: freight is the constant phrase `Freight Included in Commodity Cost`, and weight is not constant.

Chart: `images/freight_text_patterns_by_shipment.png`. Blue bars are constant freight strings. Red bars are the 1,241 + 58 shipments where the freight strings disagree. The chart is shipment counts of text, not a freight rate.

### Four shipments, so the strings are visible

Smallest shipment in each mixed pattern. Not a sample of dollars. `disagreement_examples.csv`.

Numeric freight on the Yes line, See pointer on the other line. `ASN-10007`, Air, two lines:

| ID | First line | Freight Cost (USD) | Weight (Kilograms) | Line item value |
|---|---|---|---|---:|
| 23194 | Yes | 1082.89 | 43 | 1120 |
| 69881 | No | See ASN-10007 (ID#:23194) | See ASN-10007 (ID#:23194) | 2850 |

`Invoiced Separately` on the Yes line, See pointer on the other line. `ASN-2513`, Air, two lines:

| ID | First line | Freight Cost (USD) | Weight (Kilograms) | Line item value |
|---|---|---|---|---:|
| 3360 | Yes | Invoiced Separately | Weight Captured Separately | 75 |
| 9939 | No | See ASN-2513 (ID#:3360) | See ASN-2513 (ID#:3360) | 140 |

Freight constant, weight not. `ASN-130`, Air, two lines. Both lines say the freight is included in the commodity cost. The weights disagree.

| ID | First line | Freight Cost (USD) | Weight (Kilograms) | Line item value |
|---|---|---|---|---:|
| 44 | Yes | Freight Included in Commodity Cost | 328 | 4374 |
| 7968 | No | Freight Included in Commodity Cost | Weight Captured Separately | 64461.24 |

Numeric freight, weight captured, and a See pointer. `ASN-21679`, Air, two lines:

| ID | First line | Freight Cost (USD) | Weight (Kilograms) | Line item value |
|---|---|---|---|---:|
| 13900 | Yes | 1090.87 | Weight Captured Separately | 8658 |
| 71241 | No | See ASN-21679 (ID#:13900) | See ASN-21679 (ID#:13900) | 250 |

Averaging 1082.89 with the text `See ASN-10007 (ID#:23194)` is not a defined operation. Replacing the text with zero would call that line free. Neither was done.

### Where the non-pointer text sits

`First Line Designation` = Yes on exactly one line of every shipment: 7,030 / 7,030. `first_line_designation.csv`.

The See check, `see_pointer_check.csv`:

| Check | Lines |
|---|---:|
| Freight lines in the see class | 2,445 |
| Of those, weight string identical to the freight string | 2,445 |
| Pointer names this row's own `ASN/DN #` | 2,445 |
| Cited `ID` exists in the file | 2,445 |
| Cited `ID` is the Yes line on that same `ASN/DN #` | 2,445 |
| See lines that are themselves the Yes line | **0** |

The class of the text on that Yes line, one shipment per row because there is one Yes line. This is a description of where the text lives. **It is not a priced set, not a weighed set, and not the headline rate.** No kilogram was divided.

| Yes-line freight text | Yes-line weight text | Shipments |
|---|---|---:|
| numeric | numeric | 6,175 |
| included_in_price | captured_separately | 397 |
| invoiced_separately | captured_separately | 238 |
| included_in_price | numeric | 196 |
| numeric | captured_separately | 23 |
| invoiced_separately | numeric | 1 |

6,175 + 397 + 238 + 196 + 23 + 1 = 7,030. `yes_line_text_class.csv`.

That table reconciles to the line classes. Numeric freight lines in the whole file are 6,198, and numeric Yes lines are 6,175 + 23 = 6,198, so every numeric freight string sits on a Yes line. Included Yes lines are 397 + 196 = 593, which is the 593 constant-included shipments, and those shipments hold all 1,442 included lines. Invoiced Yes lines are 238 + 1 = 239, which is every invoiced line in the file (181 constant single-line shipments + 58 mixed with a See pointer).

On the mixed freight shipments the arithmetic is the same fact. Mixed numeric-and-see is 1,241 shipments and 3,581 lines. Numeric freight lines beyond the 4,957 constant-numeric shipments are 6,198 − 4,957 = 1,241, one per mixed shipment. The other 3,581 − 1,241 = 2,340 lines are the See pointers. Mixed invoiced-and-see is 58 shipments and 163 lines. Invoiced lines beyond the 181 constant-invoiced shipments are 239 − 181 = 58. The other 163 − 58 = 105 lines are See pointers. 2,340 + 105 = 2,445, which is every See line.

The candidate rule, not adopted: take the freight string and the weight string from the Yes line, because the other lines either repeat a non-numeric phrase or point at that Yes line's `ID` on the same note, and because no note contains two different numeric freight strings or two different numeric weights. Do not average. Do not coerce the phrase to zero. This stage does not do that. Section "Before Construct" says what would still be open if someone did.

## 4. Freight and weight classes, line grain

A plain decimal is `^[0-9]+(\.[0-9]+)?$`. No commas, no scientific notation, and no leading sign appeared. Text that fails that test stays text. `float` of a See pointer is not taken, and SQLite `CAST` of that pointer is not taken either, because the cast is 0.

There is no `other` bucket and no blank freight or weight cell. The script exits if either appears. The four freight labels and the three weight labels below are the whole file.

Freight, every line. Denominator 10,324.

| Class | What the cell says | Lines | Share of 10,324 |
|---|---|---:|---:|
| numeric | a plain decimal | 6,198 | 0.6003487020534677 |
| see_another_note | `See ASN-… (ID#:…)` or `See DN-… (ID#:…)` | 2,445 | 0.2368268113134444 |
| included_in_price | `Freight Included in Commodity Cost` | 1,442 | 0.13967454475009686 |
| invoiced_separately | `Invoiced Separately` | 239 | 0.02314994188299109 |

6,198 + 2,445 + 1,442 + 239 = 10,324. The shares are those counts divided by 10,324, as written by the script. `freight_class_counts.csv`. Chart: `images/freight_class_by_line.png`. The axis is lines, and the title says it is not a cost rate.

Weight, every line. Same denominator.

| Class | What the cell says | Lines | Share of 10,324 |
|---|---|---:|---:|
| numeric | a plain decimal | 6,372 | 0.6172026346377373 |
| see_another_note | the same See pointer as the freight cell on that row | 2,445 | 0.2368268113134444 |
| captured_separately | `Weight Captured Separately` | 1,507 | 0.14597055404881829 |

6,372 + 2,445 + 1,507 = 10,324. `weight_class_counts.csv`. The 2,445 weight pointers are the same strings as the 2,445 freight pointers, not a second population (`see_pointer_check.csv`).

Shipment-level class counts for a rate were not published. The pattern table in check 3 is the shipment accounting that was allowed: it counts labels, it does not divide money.

### Line class inside mode and INCO term

These are line counts. A multi-line note contributes one row per line. The included-in-price phrase is repeated on every line of those notes, and a See line is not a second freight bill. A share in this section is not a shipment share and not a rate. `grain` on both files is `line`.

Freight class by `Shipment Mode`. Blank mode is a null, not a mode name. Row totals are the mode's lines.

| Shipment Mode | Included | Invoiced | Numeric | See | Lines |
|---|---:|---:|---:|---:|---:|
| (blank) | 49 | 0 | 211 | 100 | 360 |
| Air | 334 | 190 | 4,115 | 1,474 | 6,113 |
| Air Charter | 71 | 2 | 424 | 153 | 650 |
| Ocean | 30 | 15 | 282 | 44 | 371 |
| Truck | 958 | 32 | 1,166 | 674 | 2,830 |
| All lines | 1,442 | 239 | 6,198 | 2,445 | 10,324 |

49 + 211 + 100 = 360. 334 + 190 + 4,115 + 1,474 = 6,113. 71 + 2 + 424 + 153 = 650. 30 + 15 + 282 + 44 = 371. 958 + 32 + 1,166 + 674 = 2,830. `freight_class_by_mode.csv`.

Freight class by `Vendor INCO Term`. Same grain, same warning.

| Vendor INCO Term | Included | Invoiced | Numeric | See | Lines |
|---|---:|---:|---:|---:|---:|
| CIF | 1 | 0 | 2 | 0 | 3 |
| CIP | 97 | 0 | 163 | 15 | 275 |
| DAP | 4 | 0 | 3 | 2 | 9 |
| DDP | 1,123 | 0 | 303 | 17 | 1,443 |
| DDU | 12 | 0 | 3 | 0 | 15 |
| EXW | 16 | 138 | 2,167 | 457 | 2,778 |
| FCA | 3 | 25 | 352 | 17 | 397 |
| N/A - From RDC | 186 | 76 | 3,205 | 1,937 | 5,404 |
| All lines | 1,442 | 239 | 6,198 | 2,445 | 10,324 |

1,123 + 303 + 17 = 1,443 DDP lines. 16 + 138 + 2,167 + 457 = 2,778 EXW lines. 186 + 76 + 3,205 + 1,937 = 5,404 RDC lines. `freight_class_by_inco.csv`.

On this line grain, the most common freight string on DDP lines is `Freight Included in Commodity Cost` (1,123 / 1,443 DDP lines). The most common freight string on EXW lines is a plain decimal (2,167 / 2,778 EXW lines). That is the plan's INCO hypothesis as a description of the text: a term can hide the freight inside the product price, and that phrase was not coded as zero, so those lines are not a cheap rate. It is not a finding that DDP shipments are expensive or cheap. No shipment rate was computed, and the line count repeats the included phrase once per line.

### Edges of the numeric strings

Not a mean. Not a per-kilogram rate. Counted so a zero denominator is not discovered later. `numeric_range_notes.csv`.

| Column | Numeric lines | Min | Max | Negative | Zero | Positive |
|---|---:|---:|---:|---:|---:|---:|
| Freight Cost (USD) | 6,198 | 0.75 | 289653.2 | 0 | 0 | 6,198 |
| Weight (Kilograms) | 6,372 | 0 | 857354 | 0 | **1** | 6,371 |

The one zero weight is a real numeric zero, not a parse failure. `zero_weight_lines.csv`:

| ID | ASN/DN # | First line | Mode | Weight | Freight | Line item value |
|---|---|---|---|---:|---:|---:|
| 23750 | ASN-22365 | Yes | Air | 0 | 1002.35 | 96 |

It is one line, so the strings are constant, and it would still be illegal in a per-kilogram denominator. A later weighed set has to drop it on purpose and count the drop. It was not divided here.

## 5. Nulls and blank shipment mode

Three columns have any null. Freight and weight are not among them. A blank string and a null are the same count on this file. Denominator 10,324.

| Column | Nulls | Blank or null | Share of 10,324 |
|---|---:|---:|---:|
| Dosage | 1,736 | 1,736 | 0.16815187911662147 |
| Shipment Mode | **360** | **360** | 0.03487020534676482 |
| Line Item Insurance (USD) | 287 | 287 | 0.027799302595893065 |

The other 30 columns have 0 nulls and 0 blank strings. `null_counts.csv`.

Dosage is not an input to this question. Insurance is not the headline metric. The 287 null insurance values were not filled with zero and were not added to freight.

Blank `Shipment Mode` is 360 / 10,324 lines. Those 360 lines are 211 numeric freight, 100 See pointers, and 49 included-in-price (the mode table in check 4). They are not a mode.

## 6. Shipment mode and INCO term, line counts

Shipment counts are not in these tables. `grain` is `line` on every row. Denominator 10,324.

| Shipment Mode | Lines | Share of 10,324 |
|---|---:|---:|
| Air | 6,113 | 0.5921154591243704 |
| Truck | 2,830 | 0.274118558698179 |
| Air Charter | 650 | 0.06296009298721426 |
| Ocean | 371 | 0.035935683843471525 |
| (blank) | 360 | 0.03487020534676482 |

6,113 + 2,830 + 650 + 371 + 360 = 10,324. Four named modes, plus blank. `mode_line_counts.csv`.

| Vendor INCO Term | Lines | Share of 10,324 |
|---|---:|---:|
| N/A - From RDC | 5,404 | 0.5234405269275475 |
| EXW | 2,778 | 0.26908175125920186 |
| DDP | 1,443 | 0.13977140643161565 |
| FCA | 397 | 0.03845408756296009 |
| CIP | 275 | 0.02663696241766757 |
| DDU | 15 | 0.0014529252227818675 |
| DAP | 9 | 0.0008717551336691205 |
| CIF | 3 | 0.0002905850445563735 |

5,404 + 2,778 + 1,443 + 397 + 275 + 15 + 9 + 3 = 10,324. Eight terms. `inco_line_counts.csv`.

No ranking by cost. Air having the most lines does not make air the expensive mode. That comparison was not computed.

## 7. Cardinality

Distinct non-null labels. A null is not a level. `cardinality.csv`.

| Column | Distinct non-null | Nulls |
|---|---:|---:|
| Vendor | **73** | 0 |
| Country | **43** | 0 |
| Manufacturing Site | **88** | 0 |
| Shipment Mode | 4 | 360 |
| Vendor INCO Term | 8 | 0 |
| Product Group | 5 | 0 |
| Sub Classification | 6 | 0 |
| Managed By | 4 | 0 |
| Fulfill Via | 2 | 0 |
| First Line Designation | 2 | 0 |

73 vendors, 43 countries, and 88 manufacturing sites is the cardinality a later one-hot encoding would have to carry. This stage does not encode them and does not drop rare levels. No small-n threshold was applied, because no rate cut was published. The threshold shows up with the rate tables, not before them.

Whitespace does not split a vendor into two. `whitespace_labels.csv`:

| Column | Rows with an internal double space | Distinct raw | Distinct if internal whitespace is collapsed |
|---|---:|---:|---:|
| Vendor | 70 | 73 | 73 |
| Manufacturing Site | 23 | 88 | 88 |
| Country | 0 | 43 | 43 |
| Shipment Mode | 0 | 4 | 4 |

Collapsing internal whitespace leaves the counts unchanged. Cardinality above uses the raw string.

Manufacturing site is the column that is not constant. How many distinct sites share one note, `manufacturing_site_mix.csv`:

| Distinct sites on the shipment | Shipments |
|---:|---:|
| 1 | 6,150 |
| 2 | 580 |
| 3 | 194 |
| 4 | 60 |
| 5 | 23 |
| 6 | 11 |
| 7 | 3 |
| 8 | 2 |
| 9 | 4 |
| 10 | 1 |
| 11 | 2 |

6,150 + 580 + 194 + 60 + 23 + 11 + 3 + 2 + 4 + 1 + 2 = 7,030. Shipments with more than one site: 7,030 − 6,150 = 880, the constancy count. No rule was chosen for which site would represent the note.

## 8. Delivery dates

The three delivery columns are all `dd-Mon-yy` (`2-Jun-06`). The script parses them with that format only. It does not let a parser guess. Unparseable values would have stayed in the table as a count. There were none.

`%y` maps 00–68 to 2000–2068 and 69–99 to 1969–1999. A year outside 2000–2068 would mean the pivot had placed a date in the wrong century. That count is 0 on all three columns.

| Column | Rows | Parsed | Unparseable | Min | Max | Years outside 2000–2068 |
|---|---:|---:|---:|---|---|---:|
| Scheduled Delivery Date | 10,324 | 10,324 | **0** | 2006-05-02 | 2015-12-31 | 0 |
| Delivered to Client Date | 10,324 | 10,324 | **0** | 2006-05-02 | 2015-09-14 | 0 |
| Delivery Recorded Date | 10,324 | 10,324 | **0** | 2006-05-02 | 2015-09-14 | 0 |

`date_window.csv`. Delivered-to-client dates in this file run from 2 May 2006 through 14 September 2015. Scheduled delivery dates run through 31 December 2015. That is the window of the extract. It is not a trend, and it is not a lead-time result. The plan already says line-item lead-time conclusions from this file will not be accurate. None are drawn here.

The extract is historical. A rate from these years is not a current market rate. This stage does not publish a rate anyway.

`PQ First Sent to Client Date` and `PO Sent to Vendor Date` are not the window. They mix slash dates with sentinel labels. The slash dates were counted and not parsed into a min or a max. The sentinels were not dropped.

| Column | Slash-shaped strings (not parsed) | Not a slash date |
|---|---:|---:|
| PQ First Sent to Client Date | 7,643 | 2,681 |
| PO Sent to Vendor Date | 4,592 | 5,732 |

7,643 + 2,681 = 10,324. 4,592 + 5,732 = 10,324. The non-slash labels, `non_delivery_date_labels.csv`:

| Column | Label | Lines |
|---|---|---:|
| PQ First Sent to Client Date | Pre-PQ Process | 2,476 |
| PQ First Sent to Client Date | Date Not Captured | 205 |
| PO Sent to Vendor Date | N/A - From RDC | 5,404 |
| PO Sent to Vendor Date | Date Not Captured | 328 |

2,476 + 205 = 2,681. 5,404 + 328 = 5,732.

## 9. Line-item value

No shipment was kept, so the plan's check — value sums to a positive number on the shipments we keep — has an empty population. The answer is not "passed." The answer is that the population was not formed.

At line grain, every `Line Item Value` is a plain decimal. `line_item_value_check.csv`:

| Check | Result |
|---|---:|
| Lines | 10,324 |
| Plain numbers | 10,324 |
| Positive | 10,307 |
| Zero (the string `0`) | **17** |
| Negative | **0** |
| Shipments kept for freight-to-value | **0** |

10,307 + 17 = 10,324.

A diagnostic sum, labeled as a diagnostic and not as a KPI, adds the line values inside each `ASN/DN #` the way a later rollup would. It does not touch freight. Of 7,030 shipments, **15** would have a value sum ≤ 0 and **7,015** would have a value sum > 0. 15 + 7,015 = 7,030. A freight-to-value share needs a positive denominator. Those 15 would be out of that share even after a freight rule exists, and they would have to be counted as a drop rather than divided. They are not a drop from a rate this stage computed, because no rate was computed.

## What was not computed

The plan's headline is median freight per kilogram on the weighed set (numeric freight and numeric weight, shipment grain), with the mean beside it, plus freight divided by the sum of line-item value where freight is numeric and the value sum is positive. Insurance is not in either one.

None of those were computed. The weighed set was not formed. The priced set was not formed. There is no overall KPI row with a median in it, and there is no `kpi_by_mode.csv`, `kpi_by_country.csv`, `kpi_by_vendor.csv`, or `kpi_by_inco.csv`. The script raises if a `kpi_*.csv` file is already in `data/processed/`, so a stale rate cannot sit next to this writeup. It also raises if a future file passes the gate, because the rate section has not been written and a passing gate must not fall through as if the rates were zero.

Cuts by mode, country, vendor, INCO term, and manufacturing site were not built. The mode-controlled and weight-band comparisons were not built. No vendor and no country is called expensive. No small-n threshold was used, because there is no cut to suppress. Top and bottom quantiles of freight per kilogram were not computed. There is no distribution to explain a gap between a mean and a median.

How many shipments a priced set or a weighed set would drop is not a number yet. The exclusion reasons are known, and they were not applied to a kept set: non-numeric freight, non-numeric weight, a zero weight (1 numeric line, `ASN-22365`), and a non-positive value sum (15 shipments in the diagnostic only).

## Hypotheses from the plan

These were descriptive claims the plan allowed this stage to support or reject. They are not causal.

- Air, and air charter, will show a higher median freight per kilogram than ocean or truck. **Not tested.** The median was not computed. Neither supported nor rejected.
- Weight and cargo value move the dollar bill, and mode still matters after weight is held roughly constant. **Not tested.** No weight band was applied to a rate. Neither supported nor rejected.
- `Vendor INCO Term` changes what freight is visible. A term that often says included in the commodity cost is not a cheap term. **Supported as a description of the text, at line grain only.** On DDP lines, 1,123 / 1,443 say `Freight Included in Commodity Cost`. On EXW lines, 16 / 2,778 say that, and 2,167 / 2,778 are a plain decimal. The phrase was not set to zero. This is not a shipment share (the phrase repeats across lines of a note) and not a rate.
- A vendor, site, or country can look expensive only because of mix. **Not tested.** No one was called expensive. The constancy check does say mode, vendor, country, and INCO term are already one value per note, and manufacturing site is not (880 / 7,030).
- A savings case on a mode shift. **Out of this stage.** Execute, and only after a weighed set exists.

## SQL

`sql/kpi_freight.sql` is the line-level classification and the constancy gate, written for SQLite against a table named `delivery_lines`. The comments state the grain (one row per line), the reason there is no shipment rate (freight not constant on 1,299 notes, weight not constant on 1,322), and the exclusion a later rate has to keep (non-numeric text is not zero; do not `CAST` a See pointer, because SQLite turns it into 0). SQLite GLOB negates a character class with `^`. A `[!0-9]` class would treat `!` as a literal and accept every digit. The file says so.

There is no median query in the file. SQLite has no `MEDIAN()` aggregate, and inventing one here would invent the rollup.

`src/analyze_freight.py` loads the lines into an in-memory database, executes that file, and requires the SQL counts to equal the Python counts. It writes `sql_check_match.csv` with `matched_python` = 1 on every returned row. A mismatch stops the script before the charts are treated as done. On this run they matched, including 10,324 rows, 7,030 shipments, the four freight classes, the three weight classes, the mode and INCO line counts, 1,299 and 1,322 non-constant shipments, 0 shipments with two numeric freight strings, 0 with two numeric weights, 17 zero line-item values, 0 See lines pointing at a different note, 360 blank modes, and cardinality 73 / 43 / 88.

The delivery-date window is not in the SQL file. SQLite `date()` does not parse `2-Jun-06`. The window is the Python parse in check 8.

## Before Construct

The user has to decide the rollup before any model, any median, or any Tableau shipment table.

The gate failed on the raw strings. The failure is a pointer pattern, not two bills:

- Use the single `First Line Designation` = Yes line as the shipment's freight string and weight string. Every shipment has one. Every See line cites that line's `ID` on the same `ASN/DN #`. No shipment has two different numeric freight strings or two different numeric weights.
- Do not average a number with a See pointer. Do not set `Freight Included in Commodity Cost`, `Invoiced Separately`, or `Weight Captured Separately` to zero. Those stay out of the priced set and the weighed set, and the drop gets counted.
- Do not divide by the weight on `ASN-22365` (`ID` 23750). The weight is the number 0.
- Manufacturing site is still not one value on 880 / 7,030 shipments. A site feature needs its own rule. Mode, vendor, country, and INCO term do not.
- Freight-to-value still needs a positive sum of `Line Item Value`. The diagnostic, which is not a kept set, says 15 / 7,030 shipments would fail that test if the lines were summed.
- The outcome of a later regression, if the rule above is accepted, stays freight per kilogram on the weighed set. It does not produce a savings number. Insurance stays out of the headline. The delivery dates say 2006–2015. The figure would be historical.

Until that rule is accepted or replaced, this stage's result stands: no freight rate.
