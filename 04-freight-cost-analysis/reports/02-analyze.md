# Analyze — Freight cost (USAID SCMS)

PACE stage: **Analyze**. This page checks the grain, classifies the freight and weight text, records that the raw-string gate failed, and then computes the scorecard under the Yes-line rule accepted on 2026-09-29. It publishes median freight per kilogram on the weighed set, with the mean beside it, and freight divided by the sum of line-item value. It fits no regression, prices no savings scenario, and builds no dashboard; the regression belongs to Construct, and the savings number to Execute.

The checks below are the ones [the plan](01-plan.md) said Analyze would confirm. Every figure comes from one run of `src/analyze_freight.py` on the local raw file, not a fresh download. Aggregate tables are in `data/processed/`. The line-level classes, the constancy counts, and the Yes-line rates that SQLite can express are in `sql/kpi_freight.sql`, and charts are in `images/`. The raw CSV stays git-ignored.

## How I would say this in an interview

The business question is what freight cost, per kilogram and against the value of the goods, and whether mode, country, or vendor is where the expensive shipments sit. The raw field is not a number on every line, nor is it the same string on every line of a delivery note. The scorecard applies one accepted rule to that problem, and it states what that rule left out.

There are **10,324 lines** and **7,030 distinct `ASN/DN #`**. Freight is not the same string on **1,299 / 7,030** shipments, and weight is not the same string on **1,322 / 7,030**. That raw-string gate failed, and the failure remains on record. The disagreement, however, is not two bills: **0** shipments carry two different numeric freight strings, and **0** carry two different numeric weights. All **2,445** See pointers name their own `ASN/DN #` and cite the one line marked `First Line Designation` = Yes, and every shipment has exactly one Yes line. On **2026-09-29**, that Yes line was accepted as the shipment's freight string and weight string. I do not average a number with a pointer, and I do not turn text into zero.

The priced set comprises the **6,198** shipments whose Yes-line freight is a plain decimal. **593** say freight is included in the commodity cost, **239** say invoiced separately, and **0** Yes lines are See pointers; those 832 stay out, and they stay counted. The weighed set is the priced set restricted to a Yes-line weight that parses and is greater than zero: **6,174**. The other **24** priced shipments are **23** whose weight reads captured separately, plus **ASN-22365** / `ID` **23750**, with weight **0** and freight **1002.35**. That zero is not a denominator.

On those 6,174, median freight per kilogram is **7.263901636359817** USD, and the mean beside it is **38.93012311964861**. The mean is the tail, not the typical shipment. The 95th percentile is **67.64871004566209**, the maximum is **31087.705** (`DN-1683`, air charter, 4 kg, freight 124350.82), and the mean of the **5,865** shipments at or below that percentile is **10.192922033058075**. Freight divided by the sum of line-item value, where freight is numeric and the sum is positive, uses **6,186** shipments, with a median of **0.08758549492765344** and a mean of **23.80493291423158**. The line-value diagnostic still flags **15 / 7,030** shipments with a sum that is not positive; **12** of those are priced, so they are the drop from the ratio. The mean of the ratio is driven by a value of **0.01** on `ASN-29746` (freight 1344.94, ratio 134494), not by a typical share of cargo value, and **429 / 6,186** ratios exceed 1.

Air is the most common mode (**4,541** shipments, **4,096** weighed) and carries the high median, **10.02401980861159**, against ocean at **1.6810197953137624** and truck at **2.5032950842130273**. Air charter's median is **4.317785194174758**, above ocean and truck, while its mean is **162.32892875891395** because of that 4 kg charter. Inside a stated band of **500 kg to 5,000 kg** inclusive, air still has the high median (**7.091310572687225**, n=**1,971**), against air charter at **6.426378331512651**, truck at **3.280690194237653**, and ocean at **2.2482072238333775**. I do not call Botswana, Sudan, South Sudan, Orasure, Roche, Bio-Rad, or Aspen expensive: their uncontrolled medians lead the ranking, yet their weighed count inside air and that weight band is under 20, and Sudan's is 0. Orgenics is the vendor whose high median survives both controls, with **390** weighed air shipments in the band at a median of **15.1159699363971**, against the reference median of **7.091310572687225**. Manufacturing site is still not on the scorecard (**880 / 7,030** notes mix sites), and insurance is not in the rate. There is no regression and no savings number. Delivered-to-client dates run from **2006-05-02** to **2015-09-14**, so the dollars are historical.

## What was checked

The plan's nine checks follow. Check 3 failed on the raw strings; that failure forms the gate section, and it is not deleted. The rate cuts were computed after it, under the Yes-line rule accepted on 2026-09-29, and they are not a regression.

1. Row and column count, and a Latin-1 read.
2. Distinct `ASN/DN #` against rows.
3. Whether `Freight Cost (USD)` is constant inside one `ASN/DN #`, and whether `Weight (Kilograms)` is constant. This is the gate.
4. Freight strings classified as numeric, included-in-price, invoiced separately, see-another-note, or anything else, and the same for weight, at line grain. Shipment-level class counts of the kind a rate would use were not published, because the gate did not pass. The pattern table in check 3 is the shipment count of those text patterns, not a cost.
5. Nulls, and blank `Shipment Mode`.
6. Distinct `Shipment Mode` and `Vendor INCO Term` with line counts. Shipment counts for those fields were not added, given that the gate did not pass and a shipment count would have required picking a line to speak for the note.
7. Cardinality of `Vendor`, `Country`, and `Manufacturing Site`.
8. Min and max of the delivery dates: context for the extract, not a trend.
9. Whether line-item value is a positive number on the shipments we keep. Under the Yes-line rule, 6,186 shipments are kept for freight-to-value. 15 shipments have a value sum that is not positive, and 12 of those have numeric freight, so those 12 are the drop from the ratio.

No regression.

## 1. Shape and encoding

| Check | Result |
|---|---|
| File | `data/raw/SCMS_Delivery_History_Dataset.csv` |
| Encoding used | **latin-1** |
| UTF-8 | Raises `UnicodeDecodeError`. The file is not UTF-8. |
| Rows | **10,324** |
| Columns | **33** |

The plan expected 10,324 × 33, and that is the file; the script refuses any other shape. Every column was read as text, because a numeric dtype would have turned `See ASN-10007 (ID#:23194)` into a null, and the classification would have become a silent drop.

`shape_check.csv`.

## 2. ASN/DN # is not the row

| Check | Result |
|---|---|
| Rows | 10,324 |
| Distinct `ASN/DN #` | **7,030** |
| Distinct `ID` | **10,324** (0 duplicate IDs) |
| Shipments with one line | **5,580** |
| Shipments with more than one line | **1,450** |

5,580 + 1,450 = 7,030 shipments. The one-line shipments account for 5,580 rows, and the other 10,324 − 5,580 = 4,744 rows sit on the 1,450 multi-line notes.

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

The shipment column sums to 7,030, and the line-row column to 10,324. `grain_check.csv`, `lines_per_asn.csv`.

A one-line shipment is constant by definition. The gate in the next section concerns the 1,450 notes that have something to disagree about, and whether that disagreement is large enough to refuse a rollup for the whole file. It is.

## 3. Constancy gate

**The gate did not pass.**

A shipment is constant on a column when every line on that `ASN/DN #` carries the same string, with a null counted as its own value. Freight and weight form the money gate. The other columns are the ones a rollup would also have had to copy; they appear here so that a later stage does not take them for granted.

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

1,299 + 5,731 = 7,030; 1,322 + 5,708 = 7,030; 880 + 6,150 = 7,030. The 1,450 shipments where `First Line Designation` is not constant are the same 1,450 multi-line shipments, and the 5,580 where it is constant are the one-line shipments. `constancy_by_column.csv`.

Mode, vendor, country, and INCO term need no tie-break. Each carries one value per note on all 7,030, including notes whose mode is blank: a blank is never mixed with a named mode inside the same `ASN/DN #`, since the disagreement count is 0. Manufacturing site is mixed on 880 shipments; product group is not mixed at all.

`shipment_rollup_status.csv` holds the decision row:

| Field | Value |
|---|---|
| gate_passed | **0** |
| shipments | 7,030 |
| shipments, freight not constant | 1,299 |
| shipments, weight not constant | 1,322 |
| shipments with two distinct numeric freight strings | **0** |
| shipments with two distinct numeric weight strings | **0** |
| median freight per kg | blank on this row |
| mean freight per kg | blank on this row |
| weighed shipments | blank on this row |
| accepted_rule | yes_line |
| accepted_rule_date | 2026-09-29 |

The reason stored on that row reads: raw-string gate failed; freight or weight is not the same string on every line of the ASN/DN. Rates are not on this row. The accepted Yes-line rule is applied after this gate and written to the kpi files.

The blank rate cells are deliberate. This file is the gate, and putting the Yes-line median here would make a failed gate look as though it had produced the rate.

### What the disagreement looks like

The pattern table counts shipments by the set of freight labels and the set of weight labels on each note. It picks no dollar, and it covers every shipment.

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

Shipments: 4,942 + 1,233 + 397 + 181 + 173 + 57 + 23 + 15 + 8 + 1 = 7,030. Line rows: 4,942 + 3,551 + 1,217 + 181 + 173 + 161 + 52 + 15 + 30 + 2 = 10,324. The column `shipments_with_two_numeric_freights` is 0 on every row of `text_pattern_by_shipment.csv`, and the same holds for weight.

Freight patterns, rolled up from that table (still text, and still not a rate):

| Freight text on the shipment | Shipments | Line rows |
|---|---:|---:|
| Constant numeric | 4,942 + 15 = **4,957** | 4,957 |
| Constant `Freight Included in Commodity Cost` | 397 + 173 + 23 = **593** | 1,217 + 173 + 52 = **1,442** |
| Constant `Invoiced Separately` | **181** | 181 |
| Mixed: a number and a See pointer | 1,233 + 8 = **1,241** | 3,551 + 30 = **3,581** |
| Mixed: `Invoiced Separately` and a See pointer | 57 + 1 = **58** | 161 + 2 = **163** |

4,957 + 593 + 181 + 1,241 + 58 = 7,030. The 1,299 non-constant freight shipments are 1,241 + 58, and the constant freight shipments are 4,957 + 593 + 181 = 5,731, which matches the constancy table.

Every constant-numeric freight shipment is a single line (4,957 shipments, 4,957 rows), and so is every constant-invoiced shipment (181 and 181). The included-in-price phrase is never mixed with a See pointer: all 1,442 included lines sit on the 593 shipments where that phrase is the only freight string.

Weight patterns, from the same table:

| Weight text on the shipment | Shipments | Line rows |
|---|---:|---:|
| Constant numeric | 4,942 + 173 = **5,115** | 4,942 + 173 = 5,115 |
| Constant `Weight Captured Separately` | 397 + 181 + 15 = **593** | 1,217 + 181 + 15 = 1,413 |
| Mixed: a number and a See pointer | 1,233 + 1 = **1,234** | 3,551 + 2 = 3,553 |
| Mixed: captured separately and a See pointer | 57 + 8 = **65** | 161 + 30 = 191 |
| Mixed: captured separately and a number | **23** | 52 |

5,115 + 593 + 1,234 + 65 + 23 = 7,030. The 1,322 non-constant weight shipments are 1,234 + 65 + 23. The 23 are the case the freight gate would have missed on its own: freight is the constant phrase `Freight Included in Commodity Cost`, while weight is not constant.

Chart: `images/freight_text_patterns_by_shipment.png`. Blue bars are constant freight strings; red bars are the 1,241 + 58 shipments whose freight strings disagree. The chart shows shipment counts of text, not a freight rate.

### Four shipments, so the strings are visible

The smallest shipment in each mixed pattern is shown below; this is not a sample of dollars. `disagreement_examples.csv`.

Numeric freight on the Yes line, a See pointer on the other line: `ASN-10007`, Air, two lines.

| ID | First line | Freight Cost (USD) | Weight (Kilograms) | Line item value |
|---|---|---|---|---:|
| 23194 | Yes | 1082.89 | 43 | 1120 |
| 69881 | No | See ASN-10007 (ID#:23194) | See ASN-10007 (ID#:23194) | 2850 |

`Invoiced Separately` on the Yes line, a See pointer on the other line: `ASN-2513`, Air, two lines.

| ID | First line | Freight Cost (USD) | Weight (Kilograms) | Line item value |
|---|---|---|---|---:|
| 3360 | Yes | Invoiced Separately | Weight Captured Separately | 75 |
| 9939 | No | See ASN-2513 (ID#:3360) | See ASN-2513 (ID#:3360) | 140 |

Freight constant, weight not: `ASN-130`, Air, two lines. Both lines say the freight is included in the commodity cost, but the weights disagree.

| ID | First line | Freight Cost (USD) | Weight (Kilograms) | Line item value |
|---|---|---|---|---:|
| 44 | Yes | Freight Included in Commodity Cost | 328 | 4374 |
| 7968 | No | Freight Included in Commodity Cost | Weight Captured Separately | 64461.24 |

Numeric freight, weight captured separately, and a See pointer: `ASN-21679`, Air, two lines.

| ID | First line | Freight Cost (USD) | Weight (Kilograms) | Line item value |
|---|---|---|---|---:|
| 13900 | Yes | 1090.87 | Weight Captured Separately | 8658 |
| 71241 | No | See ASN-21679 (ID#:13900) | See ASN-21679 (ID#:13900) | 250 |

Averaging 1082.89 with the text `See ASN-10007 (ID#:23194)` is not a defined operation, and replacing the text with zero would declare that line free. Neither was done.

### Where the non-pointer text sits

`First Line Designation` = Yes appears on exactly one line of every shipment: 7,030 / 7,030. `first_line_designation.csv`.

The See check, from `see_pointer_check.csv`:

| Check | Lines |
|---|---:|
| Freight lines in the see class | 2,445 |
| Of those, weight string identical to the freight string | 2,445 |
| Pointer names this row's own `ASN/DN #` | 2,445 |
| Cited `ID` exists in the file | 2,445 |
| Cited `ID` is the Yes line on that same `ASN/DN #` | 2,445 |
| See lines that are themselves the Yes line | **0** |

The next table gives the class of the text on that Yes line, one shipment per row because each shipment has one Yes line. It describes where the text lives; it is not itself the priced set or the weighed set. The scorecard later on this page is where a kilogram is divided, and this count divides none.

| Yes-line freight text | Yes-line weight text | Shipments |
|---|---|---:|
| numeric | numeric | 6,175 |
| included_in_price | captured_separately | 397 |
| invoiced_separately | captured_separately | 238 |
| included_in_price | numeric | 196 |
| numeric | captured_separately | 23 |
| invoiced_separately | numeric | 1 |

6,175 + 397 + 238 + 196 + 23 + 1 = 7,030. `yes_line_text_class.csv`. The 6,175 numeric-and-numeric shipments include `ASN-22365`, with weight 0, so the weighed set is 6,175 − 1 = 6,174. That drop is counted in the scorecard, not inside this class table.

That table reconciles to the line classes. Numeric freight lines in the whole file number 6,198, and numeric Yes lines number 6,175 + 23 = 6,198, so every numeric freight string sits on a Yes line. Included Yes lines total 397 + 196 = 593, which matches the 593 constant-included shipments, and those shipments hold all 1,442 included lines. Invoiced Yes lines total 238 + 1 = 239, which is every invoiced line in the file (181 constant single-line shipments + 58 mixed with a See pointer).

On the mixed freight shipments, the arithmetic states the same fact. Mixed numeric-and-see covers 1,241 shipments and 3,581 lines. Numeric freight lines beyond the 4,957 constant-numeric shipments number 6,198 − 4,957 = 1,241, one per mixed shipment, and the other 3,581 − 1,241 = 2,340 lines are See pointers. Mixed invoiced-and-see covers 58 shipments and 163 lines. Invoiced lines beyond the 181 constant-invoiced shipments number 239 − 181 = 58, and the other 163 − 58 = 105 lines are See pointers. 2,340 + 105 = 2,445, which is every See line.

That is the rule the user accepted on 2026-09-29, and it is the rule the scorecard below uses. Take the freight string and the weight string from the Yes line, given that the other lines either repeat a non-numeric phrase or point at that Yes line's `ID` on the same note, and given that no note contains two different numeric freight strings or two different numeric weights. Do not average, and do not coerce the phrase to zero. The gate section above remains the record that the raw strings failed; accepting the Yes line does not change `gate_passed` from 0.

## 4. Freight and weight classes, line grain

A plain decimal is `^[0-9]+(\.[0-9]+)?$`. No commas, no scientific notation, and no leading sign appeared. Text that fails that test stays text: `float` of a See pointer is not taken, and neither is SQLite `CAST` of that pointer, because the cast returns 0.

There is no `other` bucket and no blank freight or weight cell, and the script exits if either appears. The four freight labels and the three weight labels below cover the whole file.

Freight, every line, on a denominator of 10,324.

| Class | What the cell says | Lines | Share of 10,324 |
|---|---|---:|---:|
| numeric | a plain decimal | 6,198 | 0.6003487020534677 |
| see_another_note | `See ASN-… (ID#:…)` or `See DN-… (ID#:…)` | 2,445 | 0.2368268113134444 |
| included_in_price | `Freight Included in Commodity Cost` | 1,442 | 0.13967454475009686 |
| invoiced_separately | `Invoiced Separately` | 239 | 0.02314994188299109 |

6,198 + 2,445 + 1,442 + 239 = 10,324. The shares are those counts divided by 10,324, as written by the script. `freight_class_counts.csv`. Chart: `images/freight_class_by_line.png`; its axis is lines, and its title states that it is not a cost rate.

Weight, every line, on the same denominator.

| Class | What the cell says | Lines | Share of 10,324 |
|---|---|---:|---:|
| numeric | a plain decimal | 6,372 | 0.6172026346377373 |
| see_another_note | the same See pointer as the freight cell on that row | 2,445 | 0.2368268113134444 |
| captured_separately | `Weight Captured Separately` | 1,507 | 0.14597055404881829 |

6,372 + 2,445 + 1,507 = 10,324. `weight_class_counts.csv`. The 2,445 weight pointers are the same strings as the 2,445 freight pointers, not a second population (`see_pointer_check.csv`).

Shipment-level class counts for a rate were not published. The pattern table in check 3 is the shipment accounting that was permitted: it counts labels, and it divides no money.

### Line class inside mode and INCO term

These are line counts, so a multi-line note contributes one row per line. The included-in-price phrase is repeated on every line of those notes, and a See line is not a second freight bill. A share in this section is therefore neither a shipment share nor a rate. `grain` on both files is `line`.

Freight class by `Shipment Mode`. Blank mode is a null, not a mode name, and the row totals are each mode's lines.

| Shipment Mode | Included | Invoiced | Numeric | See | Lines |
|---|---:|---:|---:|---:|---:|
| (blank) | 49 | 0 | 211 | 100 | 360 |
| Air | 334 | 190 | 4,115 | 1,474 | 6,113 |
| Air Charter | 71 | 2 | 424 | 153 | 650 |
| Ocean | 30 | 15 | 282 | 44 | 371 |
| Truck | 958 | 32 | 1,166 | 674 | 2,830 |
| All lines | 1,442 | 239 | 6,198 | 2,445 | 10,324 |

49 + 211 + 100 = 360; 334 + 190 + 4,115 + 1,474 = 6,113; 71 + 2 + 424 + 153 = 650; 30 + 15 + 282 + 44 = 371; 958 + 32 + 1,166 + 674 = 2,830. `freight_class_by_mode.csv`.

Freight class by `Vendor INCO Term`, at the same grain and with the same warning.

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

1,123 + 303 + 17 = 1,443 DDP lines; 16 + 138 + 2,167 + 457 = 2,778 EXW lines; 186 + 76 + 3,205 + 1,937 = 5,404 RDC lines. `freight_class_by_inco.csv`.

On this line grain, the most common freight string on DDP lines is `Freight Included in Commodity Cost` (1,123 / 1,443 DDP lines), while the most common on EXW lines is a plain decimal (2,167 / 2,778 EXW lines). That is the plan's INCO hypothesis expressed as a description of the text: a term can hide the freight inside the product price, and since that phrase was not coded as zero, those lines do not register as a cheap rate. It is not a finding that DDP shipments are expensive or cheap; no shipment rate was computed, and the line count repeats the included phrase once per line.

### Edges of the numeric strings

This is neither a mean nor a per-kilogram rate; it is counted so that a zero denominator is not discovered later. `numeric_range_notes.csv`.

| Column | Numeric lines | Min | Max | Negative | Zero | Positive |
|---|---:|---:|---:|---:|---:|---:|
| Freight Cost (USD) | 6,198 | 0.75 | 289653.2 | 0 | 0 | 6,198 |
| Weight (Kilograms) | 6,372 | 0 | 857354 | 0 | **1** | 6,371 |

The one zero weight is a genuine numeric zero, not a parse failure. `zero_weight_lines.csv`:

| ID | ASN/DN # | First line | Mode | Weight | Freight | Line item value |
|---|---|---|---|---:|---:|---:|
| 23750 | ASN-22365 | Yes | Air | 0 | 1002.35 | 96 |

It is a single line, so its strings are constant, yet it would still be illegal in a per-kilogram denominator. A later weighed set must drop it deliberately and count the drop; it was not divided here.

## 5. Nulls and blank shipment mode

Three columns contain any null, and freight and weight are not among them. On this file, a blank string and a null yield the same count. Denominator 10,324.

| Column | Nulls | Blank or null | Share of 10,324 |
|---|---:|---:|---:|
| Dosage | 1,736 | 1,736 | 0.16815187911662147 |
| Shipment Mode | **360** | **360** | 0.03487020534676482 |
| Line Item Insurance (USD) | 287 | 287 | 0.027799302595893065 |

The other 30 columns have 0 nulls and 0 blank strings. `null_counts.csv`.

Dosage is not an input to this question, and insurance is not the headline metric. The 287 null insurance values were neither filled with zero nor added to freight.

Blank `Shipment Mode` covers 360 / 10,324 lines: 211 numeric freight, 100 See pointers, and 49 included-in-price (see the mode table in check 4). They are not a mode.

## 6. Shipment mode and INCO term, line counts

Shipment counts are not in these tables; `grain` is `line` on every row. Denominator 10,324.

| Shipment Mode | Lines | Share of 10,324 |
|---|---:|---:|
| Air | 6,113 | 0.5921154591243704 |
| Truck | 2,830 | 0.274118558698179 |
| Air Charter | 650 | 0.06296009298721426 |
| Ocean | 371 | 0.035935683843471525 |
| (blank) | 360 | 0.03487020534676482 |

6,113 + 2,830 + 650 + 371 + 360 = 10,324: four named modes, plus blank. `mode_line_counts.csv`.

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

5,404 + 2,778 + 1,443 + 397 + 275 + 15 + 9 + 3 = 10,324, across eight terms. `inco_line_counts.csv`.

This line-count table carries no ranking by cost. Air having the most lines does not, by itself, make air the expensive mode; the shipment-level comparison is in the scorecard section, on the weighed set, after the Yes-line rule.

## 7. Cardinality

Distinct non-null labels; a null is not a level. `cardinality.csv`.

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

73 vendors, 43 countries, and 88 manufacturing sites: that is the cardinality a later one-hot encoding would have to carry. This stage neither encodes them nor drops rare levels. No small-n threshold was applied, because no rate cut was published here; the threshold appears with the rate tables, not before them.

Whitespace does not split a vendor into two. `whitespace_labels.csv`:

| Column | Rows with an internal double space | Distinct raw | Distinct if internal whitespace is collapsed |
|---|---:|---:|---:|
| Vendor | 70 | 73 | 73 |
| Manufacturing Site | 23 | 88 | 88 |
| Country | 0 | 43 | 43 |
| Shipment Mode | 0 | 4 | 4 |

Collapsing internal whitespace leaves the counts unchanged, and the cardinality above uses the raw string.

Manufacturing site is the column that is not constant. The number of distinct sites sharing one note, from `manufacturing_site_mix.csv`:

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

6,150 + 580 + 194 + 60 + 23 + 11 + 3 + 2 + 4 + 1 + 2 = 7,030. Shipments with more than one site number 7,030 − 6,150 = 880, the constancy count. No rule was chosen for which site would represent the note.

## 8. Delivery dates

The three delivery columns are all `dd-Mon-yy` (`2-Jun-06`), and the script parses them with that format alone rather than letting a parser guess. Unparseable values would have stayed in the table as a count; there were none.

`%y` maps 00–68 to 2000–2068 and 69–99 to 1969–1999, so a year outside 2000–2068 would mean the pivot had placed a date in the wrong century. That count is 0 on all three columns.

| Column | Rows | Parsed | Unparseable | Min | Max | Years outside 2000–2068 |
|---|---:|---:|---:|---|---|---:|
| Scheduled Delivery Date | 10,324 | 10,324 | **0** | 2006-05-02 | 2015-12-31 | 0 |
| Delivered to Client Date | 10,324 | 10,324 | **0** | 2006-05-02 | 2015-09-14 | 0 |
| Delivery Recorded Date | 10,324 | 10,324 | **0** | 2006-05-02 | 2015-09-14 | 0 |

`date_window.csv`. Delivered-to-client dates in this file run from 2 May 2006 through 14 September 2015, and scheduled delivery dates run through 31 December 2015. That is the window of the extract; it is neither a trend nor a lead-time result. The plan already states that line-item lead-time conclusions from this file will not be accurate, and none are drawn here.

The extract is historical, and a rate from these years is not a current market rate. The scorecard later on this page is that historical figure, not a quote for a lane today.

`PQ First Sent to Client Date` and `PO Sent to Vendor Date` do not define the window, since they mix slash dates with sentinel labels. The slash dates were counted but not parsed into a min or a max, and the sentinels were not dropped.

| Column | Slash-shaped strings (not parsed) | Not a slash date |
|---|---:|---:|
| PQ First Sent to Client Date | 7,643 | 2,681 |
| PO Sent to Vendor Date | 4,592 | 5,732 |

7,643 + 2,681 = 10,324, and 4,592 + 5,732 = 10,324. The non-slash labels, from `non_delivery_date_labels.csv`:

| Column | Label | Lines |
|---|---|---:|
| PQ First Sent to Client Date | Pre-PQ Process | 2,476 |
| PQ First Sent to Client Date | Date Not Captured | 205 |
| PO Sent to Vendor Date | N/A - From RDC | 5,404 |
| PO Sent to Vendor Date | Date Not Captured | 328 |

2,476 + 205 = 2,681. 5,404 + 328 = 5,732.

## 9. Line-item value

At line grain, every `Line Item Value` is a plain decimal. `line_item_value_check.csv`:

| Check | Result |
|---|---:|
| Lines | 10,324 |
| Plain numbers | 10,324 |
| Positive | 10,307 |
| Zero (the string `0`) | **17** |
| Negative | **0** |
| Shipments kept for freight-to-value | **6,186** |
| Rule those 6,186 were kept under | yes_line |

10,307 + 17 = 10,324. The kept count does not mean "the gate passed"; it reflects the Yes-line rule: numeric freight on the Yes line, and a positive sum of line-item value. `reason_none_kept` is blank on that file because a population was kept.

The sum covers every line on the note, and freight is not summed to build it. Of 7,030 shipments, **15** have a value sum ≤ 0 and **7,015** a value sum > 0; 15 + 7,015 = 7,030. That 15 is the same diagnostic as the pre-rule check, recomputed after the rule, and it did not move, because the sum does not depend on which line carries the freight text.

Of the 15, **12** are priced, and those 12 are the drop from freight-to-value: 6,198 − 12 = **6,186**. All 12 also sit in the weighed set (`value_sum_not_positive_among_weighed` = 12), so the other 3 of the 15 were already out because their Yes-line freight is not a number. A non-positive sum is counted; it is never used as a denominator.

## Accepted rule, 2026-09-29

The user accepted the Yes-line rule on 2026-09-29. The gate story above stands, and `gate_passed` is still 0. The rates in this section do not represent the gate changing its mind; they are the rule applied after the gate, and the script writes both.

One shipment per `ASN/DN #`. The freight string and the weight string come from the single `First Line Designation` = Yes line. Mode, vendor, country, and INCO term are copied, given that each is already constant on all 7,030 notes. Manufacturing site is not copied: it is not constant on 880 / 7,030, and the rule does not pick a site. There is accordingly no site column on `shipment_rollup.csv` and no `kpi_by_site` file.

Line-item value is summed across the lines of the note; freight is not. A See line is neither a second freight bill nor a zero. `Freight Included in Commodity Cost` and `Invoiced Separately` are not zeros either, and insurance is not read.

`src/analyze_freight.py` keeps the raw-string gate, writes it to `shipment_rollup_status.csv`, and then builds the rollup. It neither skips the rate because the gate failed nor treats a `kpi_*.csv` file as something to refuse. If a shipment ever carries two different numeric freight strings, two different numeric weights, or anything other than exactly one Yes line, the script stops. Those are the facts on which the rule was accepted, and a rate computed after they ceased to be true would amount to a silent change of rule.

## Shipment rollup

`shipment_rollup.csv` holds one row per `ASN/DN #`: 7,030 rows, 7,030 distinct ids. The exclusion reason explains why a shipment sits outside the weighed set, and `kept` means it is in the weighed set.

| exclusion_reason | Shipments | What it means |
|---|---:|---|
| kept | 6,174 | Yes-line freight parses, Yes-line weight parses, weight > 0 |
| included_in_price | 593 | Yes line says `Freight Included in Commodity Cost`. Not zero. |
| invoiced_separately | 239 | Yes line says `Invoiced Separately`. The bill is not in this extract. Not zero. |
| see_another_note | **0** | No Yes line is a See pointer. Counted so the bucket is not a silent skip. |
| weight_not_numeric | 23 | Freight parses. Weight says `Weight Captured Separately`. |
| weight_not_positive | 1 | `ASN-22365`, `ID` 23750, Air, weight 0, freight 1002.35 |

6,174 + 593 + 239 + 0 + 23 + 1 = 7,030.

Priced set: freight parses. 6,174 + 23 + 1 = **6,198**. The text exclusions are 593 + 239 + 0 = **832**, and 6,198 + 832 = 7,030.

The 23 weight-text shipments and the one zero-weight shipment sit in the priced dollar total but outside freight per kilogram. Their freight sums to 130089.14 + 1002.35 = **131091.49**, and the priced total minus the weighed total is 68817849.41 − 68686757.92 = **131091.49**: the same dollars, not a second population.

## Headline rates

There are two denominators; they are not the same set, and neither is 7,030.

**Freight per kilogram** is Yes-line freight divided by Yes-line weight, on the weighed set only. n = **6,174**.

| | Value |
|---|---:|
| Median | **7.263901636359817** |
| Mean | **38.93012311964861** |
| p95 | 67.64871004566209 |
| Maximum | 31087.705 |
| Shipments at or below p95 | 5,865 |
| Mean of those 5,865 | 10.192922033058075 |

5,865 + 309 = 6,174. The 309 above p95 are why the mean is 38.93 while the median is 7.26. The maximum is `DN-1683`, an air charter from vendor `SCMS from RDC`, weighing 4 kg, with freight of 124350.82 and a rate of 31087.705. One light charter is not the typical shipment. The median is the headline; the mean sits beside it so that the tail remains visible. `kpi_overall.csv`.

**Freight / sum of line-item value** requires numeric Yes-line freight and a positive value sum, but no weight. n = **6,186**.

| | Value |
|---|---:|
| Median | **0.08758549492765344** |
| Mean | **23.80493291423158** |
| p95 | 1.3832606333295914 |
| Maximum | 134494.0 |
| Shipments at or below p95 | 5,876 |
| Mean of those 5,876 | 0.1595093840115462 |

The median says freight is about 0.088 of the goods on the typical priced shipment with a positive value sum; the mean says nothing of the kind. `ASN-29746` is Air, with freight of 1344.94, a value sum of 0.01, a weight of 60, and a ratio of 134494. The value sum parsed, and it was not dropped, because the rule drops only a non-positive sum and 0.01 is positive. **429 / 6,186** ratios exceed 1, counted from `shipment_rollup.csv`. The mean of freight-to-value reflects that thin denominator, just as the mean of freight per kilogram reflects the 4 kg charter. I would quote the median.

The drop into that 6,186: 15 shipments have a value sum ≤ 0, and 12 of them are priced; 6,198 − 12 = 6,186. The other 3 were already outside the priced set.

Total numeric freight on the priced set, with the Yes line counted once per shipment, is **68817849.41** USD, and the weighed-set subset of that total is **68686757.92**. A large total is not a high rate, which is why the cuts below place the count next to the median.

## By mode

Population: all 7,030 shipments, with the rate computed on the weighed subset. Blank mode is a null, labeled `(blank)`, not a fifth mode anyone chose; it stays in the table because 211 weighed shipments would otherwise vanish. `kpi_by_mode.csv`. Rows are sorted with rank-eligible rows first, by median freight per kilogram. Every mode here has weighed n ≥ 20, so nothing in this cut is suppressed.

| Shipment mode | Shipments | Weighed n | Median freight per kg | Mean freight per kg | Median freight-to-value | Total numeric freight | Included | Invoiced | Weight not numeric | Weight not positive |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Air | 4,541 | 4,096 | 10.02401980861159 | 33.52045768694116 | 0.11202338697225243 | 43038623.5 | 236 | 190 | 18 | 1 |
| (blank) | 226 | 211 | 4.654915254237289 | 55.8415240167103 | 0.046903703703703704 | 1396700.4100000001 | 15 | 0 | 0 | 0 |
| Air Charter | 494 | 423 | 4.317785194174758 | 162.32892875891395 | 0.059178201471780156 | 8926108.48 | 68 | 2 | 1 | 0 |
| Truck | 1,442 | 1,162 | 2.5032950842130273 | 14.44080492244196 | 0.040487201046337816 | 11865688.23 | 244 | 32 | 4 | 0 |
| Ocean | 327 | 282 | 1.6810197953137624 | 20.662665611969857 | 0.03137888691366382 | 3590728.7899999996 | 30 | 15 | 0 | 0 |

4,541 + 226 + 494 + 1,442 + 327 = 7,030. Weighed: 4,096 + 211 + 423 + 1,162 + 282 = 6,174. Included: 236 + 15 + 68 + 244 + 30 = 593. Invoiced: 190 + 0 + 2 + 32 + 15 = 239. Weight not numeric: 18 + 1 + 4 = 23. Weight not positive: 1, on Air, which is `ASN-22365`.

Air's median is the high one. Air charter's median sits above truck and ocean and far below its own mean, and ocean has the low median. Blank sits between air and air charter on the median, and it is not interpreted as a mode.

Chart: `images/freight_per_kg_by_mode.png`: median freight per kilogram by shipment mode, on the weighed set only, with a title naming the weighed set and the Yes-line rule. The bar labels give the medians, rounded for the axis, and the weighed counts; the table above is the unrounded source. Blank appears on the chart so that the weighed set is complete.

Freight-to-value n is not the weighed n. Air's freight-to-value n is 4,104: the 4,096 weighed, minus 11 weighed air shipments with a non-positive value sum, plus the 18 weight-text shipments and the 1 zero-weight shipment, all of which have numeric freight and a positive value sum. 4,096 − 11 + 18 + 1 = 4,104. The mode file's `value_sum_not_positive_among_priced` for Air is 11, and the twelfth non-positive priced shipment is on Truck (`value_sum_not_positive_among_priced` = 1); 11 + 1 = 12.

## Quantiles

`kpi_freight_per_kg_quantiles.csv`: freight per kilogram on the weighed set. p50 is the median, and the script checks that the two match.

| Slice | n | Mean | p10 | p25 | p50 | p75 | p90 | p95 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Weighed set | 6,174 | 38.93012311964861 | 1.2140816936857448 | 3.0485389448979117 | 7.263901636359817 | 14.920496171902421 | 31.50277289446681 | 67.64871004566209 | 31087.705 |
| Air | 4,096 | 33.52045768694116 | 2.5139122440866624 | 5.38730562168386 | 10.02401980861159 | 17.881496428571428 | 38.428952533829715 | 75.14475 | 19480.97 |
| (blank) | 211 | 55.8415240167103 | 2.8759275749480557 | 3.5430295518324693 | 4.654915254237289 | 7.700668402967166 | 15.874111111111112 | 32.11046875 | 9789.07 |
| Air Charter | 423 | 162.32892875891395 | 1.2674147187215465 | 2.063229790630289 | 4.317785194174758 | 14.752771728757697 | 75.64953921072603 | 199.2245773182297 | 31087.705 |
| Ocean | 282 | 20.662665611969857 | 0.8209284989671952 | 1.1374906188456888 | 1.6810197953137624 | 2.873973255984417 | 8.620029784597792 | 16.359695270599705 | 1951.898 |
| Truck | 1,162 | 14.44080492244196 | 0.656930475190986 | 1.0756608068684734 | 2.5032950842130273 | 5.670985919287563 | 11.627465531115881 | 20.75551286821706 | 5220.79 |
| Weight 500–5,000 kg | 2,856 | 7.307612915150316 | 1.5312094520296893 | 3.089839089542757 | 5.709063842196066 | 9.842006471755566 | 15.19765386639196 | 18.545200663879914 | 86.11554016620498 |

Air charter is the mean-versus-median lesson in a single mode. Half of those 423 shipments sit at or below 4.32 USD per kg, yet the 95th percentile is 199.22 and the max is the 4 kg charter. The overall mean of 38.93 is that kind of tail, spread across the weighed set. Inside 500–5,000 kg, by contrast, the mean (7.31) and the median (5.71) are close, and the max is 86.1 rather than 31,088. The gap stems from the light tail and a few extreme bills, not from a second typical rate.

Freight-to-value, on priced shipments with a positive value sum, n = 6,186: p10 0.016211745002713926, p25 0.03600269136373899, p50 0.08758549492765344, p75 0.20140867136685853, p90 0.6625170321855831, p95 1.3832606333295914, max 134494.0. The shape is the same: the median is the figure, and the mean is the right tail.

## By country, vendor, and INCO term

The columns match the mode cut, on every shipment. Full files: `kpi_by_country.csv` (43 countries), `kpi_by_vendor.csv` (73 vendors), and `kpi_by_inco.csv` (8 terms). A row is **rank-eligible** when weighed n ≥ **20**. Rows under that threshold stay in those files, marked `rank_eligible` = 0, and are repeated in `kpi_small_n.csv` (172 rows), so that a sort by median is not mistaken for a ranking of a handful of shipments. The threshold is 20 weighed shipments; it is not a p-value.

Among the uncontrolled cuts, **21** vendors and **24** countries are rank-eligible; the other 52 vendors and 19 countries sit in the small-n file. Three INCO terms fall under the threshold, DDU (weighed n = 2), DAP (3), and CIF (2), so they are not ranked. Their medians are in the file, and they are not a finding.

INCO term, rank-eligible rows. The median does not mean "this term is cheap," because a term that mostly reads included-in-price has already left the priced set.

| INCO term | Shipments | Priced | Weighed | Median freight per kg | Mean | Median freight-to-value | Total numeric freight | Included | Invoiced | Weight not numeric |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FCA | 380 | 352 | 352 | 11.620328027950311 | 24.59868648086931 | 0.2283534932938894 | 2039273.45 | 3 | 25 | 0 |
| EXW | 2,320 | 2,167 | 2,163 | 11.377721893491124 | 32.01023300560841 | 0.10983607142857142 | 28248651.189999998 | 15 | 138 | 3 |
| CIP | 252 | 163 | 163 | 5.5529636363636365 | 14.644208347676829 | 0.0633298392732355 | 1170620.66 | 89 | 0 | 0 |
| N/A - From RDC | 3,440 | 3,205 | 3,193 | 5.0502 | 46.84473834608726 | 0.06940848044305989 | 34854520.36 | 159 | 76 | 12 |
| DDP | 616 | 303 | 296 | 1.4414988381608416 | 35.165007543731974 | 0.028815118530054286 | 2499186.51 | 313 | 0 | 7 |

380 + 2,320 + 252 + 3,440 + 616 + 12 + 7 + 3 = 7,030, counting the three small terms. DDP's weighed median is the lowest of the eligible terms, yet **313 / 616** DDP shipments never entered the priced set, because their Yes line says the freight is in the commodity cost. That low median describes only the DDP shipments whose freight was a number; it is not a finding that DDP is cheap. EXW runs the other way: 15 included and 138 invoiced separately out of 2,320, with a weighed median of 11.38 on the 2,163. The plan's point now holds at shipment grain, not merely at line grain: a term that hides freight is excluded, not coded as a low rate.

`SCMS from RDC` makes up the bulk of the weighed set, with 3,193 shipments at a median of 5.0502, below the overall median. The largest vendor is not the high rate. The vendor file is sorted so that the eligible medians form the ranking and the small-n rows follow them.

## Mode control and the weight band

The most common mode by shipment count, not by line count and not by rate, is **Air**: 4,541 shipments, 4,096 weighed. `kpi_controls.csv`.

The size control is one stated band: **weight ≥ 500 kg and weight ≤ 5,000 kg**, inclusive, on the weighed set. The edges are fixed in the script rather than re-estimated from a quantile on each run. The reasoning behind them, measured on `shipment_rollup.csv`: the weighed-set weight median is **1054.5** kg, the 25th percentile **210.25**, the 75th **3335.75**, and the maximum **857354**. Shipments at or under 100 kg number **1,026** in the weighed set, and their median freight per kilogram is **30.430045283018863**, against 7.26 overall; that left tail rests on a small denominator. 500 kg starts above it while still containing the median weight, and 5,000 kg sits above the 75th percentile and well below the long right tail. Inside the band, every named mode still has at least 20 weighed shipments, which is the condition the script checks before it will use the band as a control. Blank has 102 as well.

| Mode inside 500–5,000 kg | Weighed n | Median freight per kg | Mean |
|---|---:|---:|---:|
| Air | 1,971 | 7.091310572687225 | 8.421810441765968 |
| Air Charter | 172 | 6.426378331512651 | 9.011044615811002 |
| (blank) | 102 | 3.668980078310588 | 3.9802590607205914 |
| Truck | 506 | 3.280690194237653 | 3.7922701382694255 |
| Ocean | 105 | 2.2482072238333775 | 3.775041113059553 |

1,971 + 172 + 102 + 506 + 105 = **2,856**. `kpi_by_mode_weight_band.csv`. This file's population is already the weighed band, so the exclusion columns are 0 and the shipment count equals the weighed n; the exclusions happened before the band. Air's median remains above air charter, truck, and ocean, so holding weight inside this band does not reduce the mode gap to "you only pay for kilograms." The air mean and the air median are close here (8.42 and 7.09); the wild air mean of 33.5 came from the shipments outside this band.

The reference median for a vendor or a country is the air median inside the band: **7.091310572687225**, n = **1,971**.

Country and vendor medians inside all Air shipments are in `kpi_by_country_within_top_mode.csv` and `kpi_by_vendor_within_top_mode.csv`; the same medians inside Air and the weight band are in `kpi_by_country_within_top_mode_weight_band.csv` and `kpi_by_vendor_within_top_mode_weight_band.csv`. `kpi_control_survival.csv` places the three medians on one row for every vendor and country with at least 20 weighed shipments on the whole file.

A high uncontrolled median **does not survive** unless the weighed n inside Air and the band is at least 20, and I do not call the shipment expensive when that count fails. Once the count is met, "above the reference" means the controlled median is higher than that of the typical air shipment of similar weight. It is still not a savings number.

### Looks expensive only from mix

These names lead the uncontrolled ranking (weighed n ≥ 20 on the whole file), yet none has 20 weighed shipments inside Air and the 500–5,000 kg band. The mode control does not rescue them, since they are already air; it is the weight control they fail. They are not called expensive.

| | Uncontrolled weighed n | Uncontrolled median | Air weighed n | Air median | Air and band n |
|---|---:|---:|---:|---:|---:|
| Botswana | 62 | 38.938094117647054 | 58 | 47.96321428571429 | **7** |
| Sudan | 42 | 37.069165120593695 | 42 | 37.069165120593695 | **0** |
| Orasure Technologies Inc. | 44 | 31.133506944444445 | 44 | 31.133506944444445 | **1** |
| South Sudan | 59 | 20.859532710280373 | 58 | 21.35849118735495 | **10** |
| Hoffmann-La Roche ltd Basel | 21 | 18.276129032258062 | 21 | 18.276129032258062 | **1** |
| BIO-RAD LABORATORIES (FRANCE) | 25 | 17.249906542056074 | 25 | 17.249906542056074 | **11** |
| Namibia | 80 | 13.911916971916972 | 76 | 15.907426229508197 | **18** |
| ASPEN PHARMACARE | 29 | 10.988888888888889 | 29 | 10.988888888888889 | **1** |

Sudan has no weighed air shipment in the band at all, so there is no controlled median to quote; the blank cell sits in the survival file. Namibia, at 18, falls under the threshold by design, because a median on 18 shipments is not a ranking.

### What stays above the reference

Vendors with weighed n ≥ 20 inside Air and the band, and a median above 7.091310572687225: six in all, marked `above_reference_median` = 1 on the survival file.

| Vendor | Uncontrolled n | Uncontrolled median | Air + band n | Air + band median |
|---|---:|---:|---:|---:|
| Orgenics, Ltd | 600 | 17.2308784215912 | 390 | **15.1159699363971** |
| Trinity Biotech, Plc | 267 | 15.04304347826087 | 87 | 10.51028 |
| SHANGHAI KEHUA BIOENGINEERING CO.,LTD.  (KHB) | 70 | 12.109739751336452 | 39 | 10.048692449355432 |
| Standard Diagnostics, Inc. | 93 | 10.584032634032635 | 56 | 8.343782485555783 |
| CHEMBIO DIAGNOSTIC SYSTEMS, INC. | 103 | 9.375661861074706 | 50 | 7.662294440146512 |
| ABBVIE LOGISTICS (FORMERLY ABBOTT LOGISTICS BV) | 307 | 11.528687258687258 | 102 | 7.277169131510279 |

Orgenics is the vendor whose high median survives both controls: 390 shipments at a median of 15.12 against a reference of 7.09, with an uncontrolled median of 17.23, so the level is not an artifact of a few light shipments. That is the one vendor I would call high on this scorecard. Trinity Biotech and Shanghai Kehua stay above the reference with n of 87 and 39, so they are not "only mix," although the controlled gap is smaller than the uncontrolled ranking suggests; I report those medians without hanging the same word on them. Standard Diagnostics, Chembio, and Abbvie clear the reference by less. Abbvie's controlled median is 7.28 against 7.09, which is above the reference but does not make it an expensive vendor.

Twelve vendors clear the n threshold inside the control and sit **at or below** the reference, including `SCMS from RDC` (612 shipments, median 5.655085537731795). Surviving the control is not the same as being high.

Countries with weighed n ≥ 20 inside Air and the band, and a median above the reference: ten in all, none of them the uncontrolled leader. Botswana, Sudan, and South Sudan lead the uncontrolled list, and they appear in the mix table above.

| Country | Uncontrolled n | Uncontrolled median | Air + band n | Air + band median |
|---|---:|---:|---:|---:|
| Nigeria | 763 | 7.822093189964158 | 221 | 11.5811377245509 |
| Zimbabwe | 319 | 4.820584795321638 | 70 | 10.612830660007575 |
| Guyana | 155 | 16.5646 | 22 | 10.267478869134363 |
| Congo, DRC | 104 | 15.964528005701299 | 28 | 9.970426731415694 |
| Kenya | 91 | 9.86310533515732 | 62 | 9.946519009203865 |
| Zambia | 516 | 3.998223575135112 | 131 | 9.60243131351148 |
| Haiti | 395 | 11.488933333333334 | 115 | 9.557405032067095 |
| Rwanda | 349 | 9.95034965034965 | 145 | 9.036693191865606 |
| Cameroon | 55 | 10.990923535253229 | 31 | 8.79720088161209 |
| Burundi | 56 | 13.832056277056278 | 21 | 7.684322344322345 |

Guyana and Congo, DRC are the two uncontrolled leaders that still clear n ≥ 20 and still sit above the reference. Their controlled medians (10.27 and 9.97) are lower than the uncontrolled ones (16.56 and 15.96), so part of that lead was lighter freight. What remains is above the reference, on counts of 22 and 28, just over the threshold; I do not call either country expensive on that margin. Nigeria has the highest eligible median inside the control (11.58, n = 221), while its uncontrolled median, 7.82, sat next to the overall median. Mix hid a higher air mid-weight rate; it did not make Nigeria the expensive country on the uncontrolled list, and I do not relabel it as one. Zimbabwe and Zambia move the other way, from uncontrolled medians of 4.82 and 4.00 to controlled medians of 10.61 and 9.60: mix made them look cheap. The scorecard says so, without turning the correction into a savings claim.

No country is called expensive. The names that looked expensive on the uncontrolled median do not survive the weight band.

## Hypotheses from the plan

These were descriptive claims the plan allowed this stage to support or reject. They are not causal, and they are not a regression.

- Air, and air charter, will show a higher median freight per kilogram than ocean or truck. **Supported on the weighed set.** Air at 10.02401980861159 (n = 4,096) and air charter at 4.317785194174758 (n = 423) both sit above truck at 2.5032950842130273 (n = 1,162) and ocean at 1.6810197953137624 (n = 282), although air charter is not above air. The same order holds inside 500–5,000 kg: air 7.091310572687225 (n = 1,971), air charter 6.426378331512651 (n = 172), truck 3.280690194237653 (n = 506), ocean 2.2482072238333775 (n = 105).
- Weight and cargo value move the dollar bill, and mode still matters once weight is held roughly constant. **Supported as a description, inside one band.** The light tail (weight ≤ 100 kg, n = 1,026) has a median freight per kg of 30.430045283018863. Inside 500–5,000 kg, the mean and the median move together, and the mode order does not collapse. This is not the regression; Construct is where "held constant" becomes a model rather than a single band.
- `Vendor INCO Term` changes what freight is visible, and a term that often says included in the commodity cost is not a cheap term. **Supported at shipment grain.** DDP: 313 / 616 shipments are included-in-price and out of the priced set, so the weighed median of 1.4414988381608416 describes the 296 DDP shipments with numeric freight, not a cheap DDP rate. EXW: 15 / 2,320 included, with a weighed median of 11.377721893491124 on 2,163. The phrase was not set to zero.
- A vendor, site, or country can look expensive only because of mix. **Supported for the names in the mix table**: Botswana, Sudan, South Sudan, Namibia, Orasure, Hoffmann-La Roche, BIO-RAD, and Aspen. Site was not tested, since manufacturing site is not on the scorecard. Orgenics is the vendor that does not fit this hypothesis: its high median persists inside air and the weight band.
- A savings case on a mode shift. **Out of scope for this stage.** It belongs to Execute, and only after someone states which shipments could actually change mode; this page does not price that scenario.

## SQL

`sql/kpi_freight.sql` still opens with the line-level classification and the raw-string gate, and those queries explain why no rate on the raw string appears in the file. The comments now state that the accepted rule is the Yes line, and the second half of the file implements that rollup.

SQLite has no `MEDIAN()` aggregate. The median in the file is the middle value, or the average of the two middle values, ordered by the rate, which is the same rule pandas uses. `CAST` is applied only after the plain-decimal test, and to `Line Item Value`, which is a plain decimal on every row; it is never applied to a See pointer.

What the SQL computes, and what this run matched to the Python scorecard (`sql_check_match.csv`, `matched_python` = 1): Yes-line rows and distinct `ASN/DN #` (7,030 and 7,030), priced 6,198, weighed 6,174, freight-to-value 6,186, included 593, invoiced 239, see-on-the-Yes-line 0, weight not numeric 23, weight not positive 1, value sum ≤ 0 on 15 shipments with 12 of those priced, the priced freight total, the weighed median and mean of freight per kilogram, the freight-to-value median and mean, and the weighed n, median, and mean by shipment mode including `(blank)`. The class counts, the gate (1,299 and 1,322, and 0 shipments with two numeric strings), and the line-level mode and INCO counts still match as well.

What the SQL does not compute: the country and vendor rankings, the weight band, the quantiles other than the median, and the small-n file, all of which belong to the Python scorecard. The delivery-date window is still absent from the SQL file, because SQLite `date()` does not parse `2-Jun-06`; the window remains the Python parse in check 8.

## What this stage still does not do

No regression, no savings scenario, no Tableau workbook, and no executive summary. Key Findings, Recommendation, and Impact on the project README remain empty by design; they belong to Execute.

Manufacturing site remains unresolved, deliberately: 880 / 7,030 shipments have more than one site, and the scorecard does not pick one.

Insurance is not in the headline, blank shipment mode is not a mode, and non-numeric freight is not a zero. The weight band is one stated control, not every possible way to hold size constant.

## Before Construct

The rollup rule is no longer the open question. What remains open are the questions Construct must answer without quietly changing the denominator.

- The outcome of a regression, if one is fit, is freight per kilogram on the weighed set of 6,174: not the raw dollar bill, and not a mean filled in with zeros for the 593 included and 239 invoiced shipments.
- Those 832 shipments, the 23 captured-separately weights, and `ASN-22365` stay out of that outcome and stay counted. They are not a residual to impute.
- Freight-to-value, if used as a second description, keeps the 6,186 and does not divide by the 12 non-positive priced sums. The mean of that ratio is not a target; the median is.
- Manufacturing site needs its own rule before it can become a feature; mode, vendor, country, and INCO term do not. Cardinality is still 73 vendors, 43 countries, and 88 sites. The ranking threshold of 20 weighed shipments is a scorecard rule, not yet a pooling rule for a model.
- Orgenics is the vendor whose high median survived air and the 500–5,000 kg band. That is a description, and a coefficient is not a saving. A mode-shift scenario belongs to Execute, on a stated set of shipments, beside the shipments that were excluded and beside the fact that the extract covers deliveries from 2006-05-02 through 2015-09-14.
- The dollars are historical; nothing on this page is a current lane rate.