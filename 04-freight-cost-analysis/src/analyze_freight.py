#!/usr/bin/env python3
"""Analyze stage: freight-cost scorecard for the USAID SCMS delivery lines.

This script checks the grain and classifies the freight and weight text.
The raw-string constancy gate is recorded even when it fails. On this
extract it fails, because a See pointer is not the same string as the
number it cites. The accepted rule, after that gate, is the Yes line:
one shipment per ASN/DN, freight string and weight string taken from the
single First Line Designation = Yes line. Text is not zeroed and lines
are not averaged. The script then writes the scorecard the plan reserved
for after the gate.

It does not fit a regression, and it does not price a savings scenario.
Those belong to Construct and Execute.

Run from the repo root:
    python 04-freight-cost-analysis/src/analyze_freight.py

Run from the project folder (04-freight-cost-analysis):
    python src/analyze_freight.py

Paths are anchored to this file, not to the shell's current directory, so
either command reads the same raw CSV and writes the same outputs.

Input (git-ignored, already on disk; this script does not copy it):
    04-freight-cost-analysis/data/raw/SCMS_Delivery_History_Dataset.csv
    Latin-1.

Outputs under 04-freight-cost-analysis/:
    data/processed/*.csv   small aggregate tables only
    images/freight_class_by_line.png
    images/freight_text_patterns_by_shipment.png
    images/freight_per_kg_by_mode.png

No output is the full line extract. The shipment table is one row per
ASN/DN under the Yes-line rule, not a second copy of the line file.
This run does not average conflicting freight strings, and it does not
treat a "See ASN/DN" pointer, an included-in-price phrase, or
"Invoiced Separately" as zero.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save files; do not open a window
import matplotlib.pyplot as plt
import pandas as pd

# Anchored to this file so a run from the repo root and a run from the
# project folder write the same place. parents[1] is 04-freight-cost-analysis.
PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw" / "SCMS_Delivery_History_Dataset.csv"
PROC = PROJECT / "data" / "processed"
IMG = PROJECT / "images"
SQL_PATH = PROJECT / "sql" / "kpi_freight.sql"

# The plan's expected shape. A different extract is a different question.
EXPECTED_ROWS = 10_324
EXPECTED_COLS = 33

# Plain decimal only. float("See ASN") must not become a number, and
# CAST in SQLite turns that text into 0, which is why the SQL predicate
# below is a character test rather than a cast. The same shape is what
# the SQL file accepts, so the two counts can be compared.
PLAIN_NUMBER = re.compile(r"^[0-9]+(\.[0-9]+)?$")

# Delivery dates in this file are day-Mon-yy (2-Jun-06). %y maps 00-68 to
# 2000-2068. That pivot is safe only if every parsed year lands in the
# 2000s, which the script checks. A 19xx result would be a different file.
DELIVERY_DATE_FORMAT = "%d-%b-%y"
DELIVERY_DATE_COLUMNS = (
    "Scheduled Delivery Date",
    "Delivered to Client Date",
    "Delivery Recorded Date",
)

# These two are not the window. They mix real dates with sentinel labels.
# They are counted so a failed parse is visible, not dropped.
OTHER_DATE_COLUMNS = (
    "PQ First Sent to Client Date",
    "PO Sent to Vendor Date",
)

SEE_POINTER = re.compile(r"^See (ASN|DN)-([0-9]+) \(ID#:([0-9]+)\)$")

FREIGHT_INCLUDED = "Freight Included in Commodity Cost"
FREIGHT_INVOICED = "Invoiced Separately"
WEIGHT_CAPTURED = "Weight Captured Separately"

# Accepted on 2026-09-29, after the raw-string gate failed. The Yes line is
# the shipment's freight string and weight string. See the comment on
# yes_line_rollup for why that is a rule and not an average.
ACCEPTED_RULE = "yes_line"
ACCEPTED_RULE_DATE = "2026-09-29"

# Cuts with fewer weighed shipments than this stay in the tables and in
# kpi_small_n.csv, and they are kept out of the ranking. A median on
# n = 3 is not a vendor comparison.
RANK_MIN_WEIGHED = 20

# Stated size control. Fixed edges, not a quantile recomputed each run,
# so "roughly the same weight" is a sentence someone can repeat.
# 500 kg to 5,000 kg inclusive sits around the weighed-set median weight
# (about 1,055 kg) and above the light shipments whose per-kilogram rate
# is mostly a small denominator. The upper edge drops the long tail
# (weights run into the hundreds of thousands of kilograms) without
# emptying ocean or truck. yes_line_rollup checks that every named mode
# still has at least RANK_MIN_WEIGHED weighed shipments inside the band.
WEIGHT_BAND_LO_KG = 500.0
WEIGHT_BAND_HI_KG = 5000.0

# Fields a shipment rollup would have to copy. Freight and weight are the
# gate. The others are recorded so a later stage does not assume they are
# constant just because the note id is shared.
CONSTANCY_COLUMNS = (
    "Freight Cost (USD)",
    "Weight (Kilograms)",
    "Shipment Mode",
    "Vendor",
    "Country",
    "Vendor INCO Term",
    "Manufacturing Site",
    "First Line Designation",
    "Managed By",
    "Fulfill Via",
    "Product Group",
)


def load_raw(path: Path) -> pd.DataFrame:
    """Read the delivery-line file as Latin-1 text and refuse a different shape.

    Every freight and weight value stays a string. A numeric dtype would
    turn the non-numeric labels into NaN and hide the thing this stage
    has to count. UTF-8 is tried first only to prove it is the wrong codec.
    """
    if path.name != "SCMS_Delivery_History_Dataset.csv":
        raise SystemExit(f"refusing to read {path.name}")
    if not path.is_file():
        raise SystemExit(f"missing raw file: {path}")

    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        utf8_ok = False
    else:
        utf8_ok = True
    if utf8_ok:
        raise SystemExit("file decoded as UTF-8; the Latin-1 premise is stale")

    df = pd.read_csv(path, encoding="latin-1", dtype=str)
    if df.shape != (EXPECTED_ROWS, EXPECTED_COLS):
        raise SystemExit(f"shape changed: {df.shape}")
    required = [
        "ID",
        "ASN/DN #",
        "Country",
        "Vendor",
        "Vendor INCO Term",
        "Shipment Mode",
        "Manufacturing Site",
        "First Line Designation",
        "Line Item Value",
        "Weight (Kilograms)",
        "Freight Cost (USD)",
        *DELIVERY_DATE_COLUMNS,
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"missing columns: {missing}")
    return df


def is_plain_number(value: object) -> bool:
    """True only for an unadorned decimal string. Text is not zero."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return PLAIN_NUMBER.fullmatch(str(value)) is not None


def freight_class(value: object) -> str:
    """Bucket one freight cell. The buckets are labels, not dollars.

    'Freight Included in Commodity Cost' is not a free shipment. A See
    pointer is not a second charge and not a zero. Anything that is not
    one of the known labels stays 'other' so a new phrase cannot vanish
    into a catch-all that we then treat as numeric.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "blank"
    text = str(value)
    if is_plain_number(text):
        return "numeric"
    if text == FREIGHT_INCLUDED:
        return "included_in_price"
    if text == FREIGHT_INVOICED:
        return "invoiced_separately"
    if SEE_POINTER.fullmatch(text):
        return "see_another_note"
    return "other"


def weight_class(value: object) -> str:
    """Bucket one weight cell. Same rule as freight: text is not zero."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "blank"
    text = str(value)
    if is_plain_number(text):
        return "numeric"
    if text == WEIGHT_CAPTURED:
        return "captured_separately"
    if SEE_POINTER.fullmatch(text):
        return "see_another_note"
    return "other"


def class_counts(series: pd.Series, class_col: str) -> pd.DataFrame:
    """Line counts for one classification. The denominator is every line."""
    counts = series.value_counts(dropna=False)
    rows = []
    for name, n in counts.items():
        rows.append(
            {
                class_col: name,
                "lines": int(n),
                "share_of_lines": int(n) / EXPECTED_ROWS,
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(["lines", class_col], ascending=[False, True]).reset_index(drop=True)


def constancy_table(df: pd.DataFrame) -> pd.DataFrame:
    """How many shipments do not share one string on each field.

    nunique counts distinct strings, including a null as its own value.
    A shipment of one line is constant by definition. The gate uses freight
    and weight only; the other rows are there so mix is not discovered later
    by accident.
    """
    grouped = df.groupby("ASN/DN #", dropna=False)
    shipments = int(grouped.ngroups)
    rows = []
    for col in CONSTANCY_COLUMNS:
        nunique = grouped[col].nunique(dropna=False)
        disagree = int((nunique > 1).sum())
        rows.append(
            {
                "column_name": col,
                "shipments": shipments,
                "shipments_not_constant": disagree,
                "shipments_constant": shipments - disagree,
                "is_money_gate": int(col in ("Freight Cost (USD)", "Weight (Kilograms)")),
            }
        )
    return pd.DataFrame(rows)


def lines_per_shipment(df: pd.DataFrame) -> pd.DataFrame:
    """Distribution of line counts. A delivery note is not a row."""
    sizes = df.groupby("ASN/DN #", dropna=False).size()
    rows = []
    for n_lines, n_shipments in sizes.value_counts().sort_index().items():
        rows.append(
            {
                "lines_on_shipment": int(n_lines),
                "shipments": int(n_shipments),
                "line_rows": int(n_lines) * int(n_shipments),
            }
        )
    out = pd.DataFrame(rows)
    if int(out["shipments"].sum()) != df["ASN/DN #"].nunique():
        raise SystemExit("lines-per-shipment does not cover every ASN/DN")
    if int(out["line_rows"].sum()) != len(df):
        raise SystemExit("lines-per-shipment does not cover every row")
    return out


def _pattern_name(classes: set[str], kind: str) -> str:
    """Name a shipment by the set of labels on it, not by a chosen dollar."""
    if kind == "freight":
        mapping = {
            frozenset({"numeric"}): "constant_numeric",
            frozenset({"included_in_price"}): "constant_included_in_price",
            frozenset({"invoiced_separately"}): "constant_invoiced_separately",
            frozenset({"see_another_note"}): "constant_see_another_note",
            frozenset({"numeric", "see_another_note"}): "mixed_numeric_and_see",
            frozenset({"invoiced_separately", "see_another_note"}): "mixed_invoiced_and_see",
            frozenset({"included_in_price", "see_another_note"}): "mixed_included_and_see",
        }
    else:
        mapping = {
            frozenset({"numeric"}): "constant_numeric",
            frozenset({"captured_separately"}): "constant_captured_separately",
            frozenset({"see_another_note"}): "constant_see_another_note",
            frozenset({"numeric", "see_another_note"}): "mixed_numeric_and_see",
            frozenset({"captured_separately", "see_another_note"}): "mixed_captured_and_see",
            frozenset({"captured_separately", "numeric"}): "mixed_captured_and_numeric",
        }
    key = frozenset(classes)
    return mapping.get(key, "other:" + "+".join(sorted(key)))


def shipment_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """One row per shipment describing the text pattern, not a cost.

    This is the gate worksheet. A mixed pattern means the strings disagree,
    so that shipment cannot contribute a freight figure under the locked
    rule. Constant patterns are still not a priced set: 'included in price'
    is constant and still not a number.
    """
    rows = []
    for asn, sub in df.groupby("ASN/DN #", dropna=False, sort=False):
        freight_classes = set(sub["freight_class"])
        weight_classes = set(sub["weight_class"])
        numeric_freight = {
            v for v in sub["Freight Cost (USD)"] if is_plain_number(v)
        }
        numeric_weight = {
            v for v in sub["Weight (Kilograms)"] if is_plain_number(v)
        }
        yes = sub[sub["First Line Designation"] == "Yes"]
        rows.append(
            {
                "asn_dn": asn,
                "lines": int(len(sub)),
                "freight_pattern": _pattern_name(freight_classes, "freight"),
                "weight_pattern": _pattern_name(weight_classes, "weight"),
                "distinct_numeric_freight_strings": len(numeric_freight),
                "distinct_numeric_weight_strings": len(numeric_weight),
                "yes_lines": int(len(yes)),
                "yes_freight_class": (
                    yes["freight_class"].iloc[0] if len(yes) == 1 else "not_exactly_one_yes"
                ),
                "yes_weight_class": (
                    yes["weight_class"].iloc[0] if len(yes) == 1 else "not_exactly_one_yes"
                ),
            }
        )
    out = pd.DataFrame(rows)
    if len(out) != df["ASN/DN #"].nunique():
        raise SystemExit("pattern table missed a shipment")
    return out


def pattern_summary(patterns: pd.DataFrame) -> pd.DataFrame:
    """Shipment counts for each freight-pattern × weight-pattern pair.

    The asn id is not written here. The summary is the published table.
    """
    grouped = (
        patterns.groupby(["freight_pattern", "weight_pattern"], dropna=False)
        .agg(
            shipments=("asn_dn", "size"),
            line_rows=("lines", "sum"),
            shipments_with_two_numeric_freights=(
                "distinct_numeric_freight_strings",
                lambda s: int((s > 1).sum()),
            ),
            shipments_with_two_numeric_weights=(
                "distinct_numeric_weight_strings",
                lambda s: int((s > 1).sum()),
            ),
        )
        .reset_index()
    )
    grouped = grouped.sort_values(
        ["shipments", "freight_pattern", "weight_pattern"],
        ascending=[False, True, True],
    ).reset_index(drop=True)
    if int(grouped["shipments"].sum()) != len(patterns):
        raise SystemExit("pattern summary does not cover every shipment")
    return grouped


def disagreement_examples(df: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
    """A few whole shipments, one per mixed pattern, so the text is visible.

    The smallest shipment in each pattern is the example. A 50-line note
    would not show the pattern any more clearly than a 2-line note, and
    this file is not a dump of every disagreeing row. Columns are selected
    by name because itertuples renames spaces and punctuation.
    """
    wanted = [
        ("freight_pattern", "mixed_numeric_and_see"),
        ("freight_pattern", "mixed_invoiced_and_see"),
        ("weight_pattern", "mixed_captured_and_numeric"),
        ("weight_pattern", "mixed_captured_and_see"),
    ]
    chosen = []
    for column, name in wanted:
        pool = patterns[patterns[column] == name]
        if pool.empty:
            continue
        pool = pool.sort_values(["lines", "asn_dn"])
        asn = pool["asn_dn"].iloc[0]
        if asn not in chosen:
            chosen.append(asn)
    frames = []
    for asn in chosen:
        sub = df.loc[
            df["ASN/DN #"] == asn,
            [
                "ASN/DN #",
                "ID",
                "First Line Designation",
                "Shipment Mode",
                "Freight Cost (USD)",
                "Weight (Kilograms)",
                "freight_class",
                "weight_class",
                "Line Item Value",
            ],
        ].copy()
        sub.insert(0, "example_for", asn)
        frames.append(sub)
    if not frames:
        raise SystemExit("no disagreement examples; the gate description would be empty")
    out = pd.concat(frames, ignore_index=True)
    if len(out) > 80:
        raise SystemExit("examples grew past a readable extract; pick smaller notes")
    return out


def see_pointer_check(df: pd.DataFrame) -> pd.DataFrame:
    """What a See line points at. This is a description, not a rollup rule.

    The locked rule says: if the freight string is not constant, do not
    invent a shipment figure. The pointer check tells a later stage whether
    the disagreement is two charges or a line pointing at another line.
    """
    see = df[df["freight_class"] == "see_another_note"].copy()
    parsed = see["Freight Cost (USD)"].map(
        lambda text: SEE_POINTER.fullmatch(str(text))
    )
    if parsed.isna().any():
        raise SystemExit("a see-class freight row did not match the pointer pattern")
    weight_same = int((see["Freight Cost (USD)"] == see["Weight (Kilograms)"]).sum())
    own = 0
    id_in_file = 0
    id_is_yes_on_same_asn = 0
    ids = set(df["ID"])
    yes_id = (
        df.loc[df["First Line Designation"] == "Yes", ["ASN/DN #", "ID"]]
        .drop_duplicates()
        .set_index("ASN/DN #")["ID"]
    )
    for asn, text in zip(see["ASN/DN #"], see["Freight Cost (USD)"]):
        match = SEE_POINTER.fullmatch(str(text))
        kind, number, cited = match.group(1), match.group(2), match.group(3)
        if f"{kind}-{number}" == asn:
            own += 1
        if cited in ids:
            id_in_file += 1
        yes = yes_id.get(asn)
        if yes is not None and cited == yes:
            id_is_yes_on_same_asn += 1
    see_lines = int(len(see))
    return pd.DataFrame(
        [
            {
                "see_freight_lines": see_lines,
                "see_lines_weight_string_identical": weight_same,
                "see_lines_point_at_own_asn_dn": own,
                "see_lines_cited_id_exists": id_in_file,
                "see_lines_cited_id_is_yes_line_on_same_asn": id_is_yes_on_same_asn,
                "see_lines_that_are_first_line_yes": int(
                    (see["First Line Designation"] == "Yes").sum()
                ),
            }
        ]
    )


def first_line_marker(df: pd.DataFrame) -> pd.DataFrame:
    """The file marks exactly one line per ASN/DN as the first line.

    That marker is how the See pointers are aimed. It is recorded here so
    the structure is visible. It is not used to pick a freight dollar.
    """
    yes_count = df.groupby("ASN/DN #", dropna=False)["First Line Designation"].apply(
        lambda s: int((s == "Yes").sum())
    )
    distribution = yes_count.value_counts().sort_index()
    rows = []
    for n_yes, n_shipments in distribution.items():
        rows.append(
            {
                "yes_lines_on_shipment": int(n_yes),
                "shipments": int(n_shipments),
            }
        )
    out = pd.DataFrame(rows)
    if int(out.loc[out["yes_lines_on_shipment"] == 1, "shipments"].sum()) != len(yes_count):
        # Still write the distribution. The caller asserts the expected shape.
        pass
    return out


def yes_line_class_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Class of the text that sits on the single Yes line.

    Published as a description of where the non-pointer text lives. Not a
    priced set and not a weighed set. Shipment rates are not computed from it.
    """
    yes = df[df["First Line Designation"] == "Yes"]
    rows = []
    for label, sub in yes.groupby(["freight_class", "weight_class"], dropna=False):
        freight_name, weight_name = label
        rows.append(
            {
                "yes_freight_class": freight_name,
                "yes_weight_class": weight_name,
                "shipments": int(len(sub)),
            }
        )
    out = pd.DataFrame(rows).sort_values("shipments", ascending=False).reset_index(drop=True)
    if int(out["shipments"].sum()) != df["ASN/DN #"].nunique():
        raise SystemExit("Yes-line classes do not cover every shipment")
    return out


def null_table(df: pd.DataFrame) -> pd.DataFrame:
    """Nulls and blank strings. Blank Shipment Mode is the one the plan named."""
    rows = []
    n = len(df)
    for col in df.columns:
        if col in ("freight_class", "weight_class"):
            continue
        nulls = int(df[col].isna().sum())
        blanks = int((df[col].fillna("").str.strip() == "").sum())
        rows.append(
            {
                "column_name": col,
                "null_count": nulls,
                "blank_or_null_count": blanks,
                "blank_or_null_share": blanks / n,
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["blank_or_null_count", "column_name"], ascending=[False, True]
    ).reset_index(drop=True)


def cardinality_table(df: pd.DataFrame) -> pd.DataFrame:
    """How many distinct labels a later model would have to carry.

    Null Shipment Mode is not a level in distinct_non_null. It is counted
    beside that number so the blank is not mistaken for a mode called nan.
    """
    columns = [
        "Vendor",
        "Country",
        "Manufacturing Site",
        "Shipment Mode",
        "Vendor INCO Term",
        "Product Group",
        "Sub Classification",
        "Managed By",
        "Fulfill Via",
        "First Line Designation",
    ]
    rows = []
    for col in columns:
        rows.append(
            {
                "column_name": col,
                "distinct_non_null": int(df[col].nunique(dropna=True)),
                "null_count": int(df[col].isna().sum()),
            }
        )
    return pd.DataFrame(rows)


def whitespace_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Double spaces inside a name. Collapsing them must not quietly merge vendors.

    Cardinality for Construct uses the raw string. This table says whether
    that choice splits one vendor into two.
    """
    rows = []
    for col in ("Vendor", "Manufacturing Site", "Country", "Shipment Mode"):
        series = df[col].dropna()
        doubled = series.str.contains(r"\s{2}", regex=True)
        collapsed = series.str.replace(r"\s+", " ", regex=True)
        rows.append(
            {
                "column_name": col,
                "rows_with_double_space": int(doubled.sum()),
                "distinct_raw": int(series.nunique()),
                "distinct_if_internal_whitespace_collapsed": int(collapsed.nunique()),
            }
        )
    return pd.DataFrame(rows)


def label_counts(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Line counts for one categorical field. Not shipment counts.

    Shipment counts are omitted on purpose. The constancy gate did not pass,
    so a shipment count would require a rule for which line speaks for the note.
    """
    series = df[column].fillna("(blank)")
    # A real level whose name is (blank) would be ambiguous. There isn't one
    # in the known modes or INCO terms; refuse if that changes.
    if column == "Shipment Mode" and (df[column] == "(blank)").any():
        raise SystemExit("a shipment mode is literally named (blank)")
    counts = series.value_counts(dropna=False)
    rows = []
    for name, n in counts.items():
        rows.append(
            {
                column: name,
                "lines": int(n),
                "share_of_lines": int(n) / len(df),
                "grain": "line",
            }
        )
    return pd.DataFrame(rows)


def class_by_label(df: pd.DataFrame, column: str, class_col: str) -> pd.DataFrame:
    """Line-level class mix inside a mode or an INCO term.

    A line share is not a shipment share. See lines and repeated
    'included in commodity cost' lines make a multi-line note count more
    than once. The grain column is there so this table is not read as a rate.
    """
    frame = df.copy()
    frame["_label"] = frame[column].fillna("(blank)")
    rows = []
    for label, sub in frame.groupby("_label", dropna=False):
        for class_name, n in sub[class_col].value_counts().items():
            rows.append(
                {
                    column: label,
                    class_col: class_name,
                    "lines": int(n),
                    "lines_in_label": int(len(sub)),
                    "grain": "line",
                }
            )
    out = pd.DataFrame(rows)
    return out.sort_values(
        [column, "lines"], ascending=[True, False]
    ).reset_index(drop=True)


def date_window(df: pd.DataFrame) -> pd.DataFrame:
    """Min and max of the delivery dates. Context for the extract, not a trend.

    The format is fixed to %d-%b-%y. dateutil is not used, because a mixed
    file would then be parsed silently under a guess. Unparseable values are
    counted. They are not dropped and then forgotten.
    """
    rows = []
    for col in DELIVERY_DATE_COLUMNS:
        parsed = pd.to_datetime(df[col], format=DELIVERY_DATE_FORMAT, errors="coerce")
        failed = int(parsed.isna().sum())
        years = sorted(set(parsed.dt.year.dropna().astype(int)))
        suspicious = [year for year in years if year < 2000 or year > 2068]
        rows.append(
            {
                "column_name": col,
                "role": "delivery_window",
                "format_tried": DELIVERY_DATE_FORMAT,
                "rows": int(len(df)),
                "parsed": int(parsed.notna().sum()),
                "unparseable": failed,
                "min_date": "" if failed == len(df) else parsed.min().date().isoformat(),
                "max_date": "" if failed == len(df) else parsed.max().date().isoformat(),
                "years_before_2000_or_after_2068": len(suspicious),
            }
        )
    # Sentinel labels on the PQ/PO columns. A slash date is counted as a
    # date-shaped string, not parsed into the window. The window is the
    # delivery dates only.
    slash = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
    for col in OTHER_DATE_COLUMNS:
        series = df[col].fillna("(null)")
        rows.append(
            {
                "column_name": col,
                "role": "not_the_window",
                "format_tried": "not parsed; mixed labels",
                "rows": int(len(df)),
                "parsed": int(series.map(lambda v: bool(slash.fullmatch(str(v)))).sum()),
                "unparseable": int((~series.map(lambda v: bool(slash.fullmatch(str(v))))).sum()),
                "min_date": "",
                "max_date": "",
                "years_before_2000_or_after_2068": 0,
            }
        )
    return pd.DataFrame(rows)


def other_date_labels(df: pd.DataFrame) -> pd.DataFrame:
    """The non-date labels on PQ and PO dates, so they are not a silent drop."""
    slash = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
    rows = []
    for col in OTHER_DATE_COLUMNS:
        series = df[col].fillna("(null)")
        for value, n in series.value_counts().items():
            if slash.fullmatch(str(value)):
                continue
            rows.append(
                {
                    "column_name": col,
                    "label": value,
                    "lines": int(n),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["column_name", "lines"], ascending=[True, False]
    ).reset_index(drop=True)


def value_check(df: pd.DataFrame, shipments: pd.DataFrame) -> pd.DataFrame:
    """Line-item value is a number on every row. The shipment sum is the lines.

    The raw-string gate did not keep a population. The accepted Yes-line
    rule does. Freight-to-value keeps a shipment only when the Yes-line
    freight is numeric and the sum of line-item value on the note is
    positive. The diagnostic count is every shipment whose line sum is
    not positive, whether or not freight parsed. Both counts are written.
    A zero line is not dropped from the file.
    """
    if not df["Line Item Value"].map(is_plain_number).all():
        bad = int((~df["Line Item Value"].map(is_plain_number)).sum())
        raise SystemExit(f"line item value is not a plain number on {bad} rows")
    values = df["Line Item Value"].map(float)
    zero_lines = int((values == 0).sum())
    negative_lines = int((values < 0).sum())
    # Diagnostic only: the sum a rollup would have used. Not a KPI.
    sums = df.assign(_v=values).groupby("ASN/DN #", dropna=False)["_v"].sum()
    if int((sums <= 0).sum()) != int(shipments["value_sum_not_positive"].sum()):
        raise SystemExit("line-value diagnostic does not match the Yes-line rollup")
    if set(sums.index) != set(shipments["asn_dn"]):
        raise SystemExit("line-value sums are not one per shipment in the rollup")
    return pd.DataFrame(
        [
            {
                "lines": int(len(df)),
                "lines_plain_number": int(len(df)),
                "lines_positive": int((values > 0).sum()),
                "lines_zero": zero_lines,
                "lines_negative": negative_lines,
                "shipments_kept_for_freight_to_value": int(shipments["in_freight_to_value"].sum()),
                "reason_none_kept": "",
                "kept_rule": ACCEPTED_RULE,
                "diagnostic_shipments_if_lines_were_summed": int(len(sums)),
                "diagnostic_shipments_with_value_sum_le_0": int((sums <= 0).sum()),
                "diagnostic_shipments_with_value_sum_gt_0": int((sums > 0).sum()),
                "priced_shipments_with_value_sum_le_0": int(
                    ((shipments["in_priced"] == 1) & (shipments["value_sum_not_positive"] == 1)).sum()
                ),
            }
        ]
    )


def numeric_range_notes(df: pd.DataFrame) -> pd.DataFrame:
    """Edges of the numeric strings. Not a mean, and not a per-kilogram rate.

    A zero weight cannot be a denominator. A negative freight would have to
    be excluded rather than averaged. Both are counted here so the absence
    of a rate table is not also the absence of this check.
    """
    rows = []
    for col, class_col in (
        ("Freight Cost (USD)", "freight_class"),
        ("Weight (Kilograms)", "weight_class"),
    ):
        numbers = df.loc[df[class_col] == "numeric", col].map(float)
        rows.append(
            {
                "column_name": col,
                "numeric_lines": int(len(numbers)),
                "min_value": float(numbers.min()) if len(numbers) else None,
                "max_value": float(numbers.max()) if len(numbers) else None,
                "negative_lines": int((numbers < 0).sum()),
                "zero_lines": int((numbers == 0).sum()),
                "positive_lines": int((numbers > 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def manufacturing_site_mix(df: pd.DataFrame) -> pd.DataFrame:
    """How many sites share one ASN/DN. Not a rule for which site to keep."""
    nunique = df.groupby("ASN/DN #", dropna=False)["Manufacturing Site"].nunique(dropna=False)
    rows = []
    for n_sites, n_shipments in nunique.value_counts().sort_index().items():
        rows.append(
            {
                "distinct_manufacturing_sites_on_shipment": int(n_sites),
                "shipments": int(n_shipments),
            }
        )
    return pd.DataFrame(rows)



def zero_weight_lines(df: pd.DataFrame) -> pd.DataFrame:
    """Numeric weight of zero. A per-kilogram rate cannot divide by it.

    Kept as its own rows, not a mean. Text weight is not in this table.
    """
    hit = df.loc[df["weight_class"].eq("numeric")].copy()
    hit = hit.loc[hit["Weight (Kilograms)"].map(float).eq(0)]
    keep = [
        "ID",
        "ASN/DN #",
        "First Line Designation",
        "Shipment Mode",
        "Weight (Kilograms)",
        "Freight Cost (USD)",
        "Line Item Value",
        "freight_class",
        "weight_class",
    ]
    if len(hit) > 20:
        raise SystemExit("zero-weight lines grew; look at them before writing a dump")
    return hit[keep]


def rollup_status(constancy: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
    """The raw-string gate. This row does not hold the Yes-line rates.

    Passing would mean every shipment has one freight string and one weight
    string. A pointer that differs from the numeric line is not constant,
    even when the pointer cites that same note. On this extract the gate
    fails. The failure is recorded here. The accepted Yes-line rule is a
    later step, written to the kpi files, and it does not flip this flag
    to passed.
    """
    freight = constancy.loc[
        constancy["column_name"] == "Freight Cost (USD)", "shipments_not_constant"
    ].iloc[0]
    weight = constancy.loc[
        constancy["column_name"] == "Weight (Kilograms)", "shipments_not_constant"
    ].iloc[0]
    passed = int(freight) == 0 and int(weight) == 0
    two_freight = int((patterns["distinct_numeric_freight_strings"] > 1).sum())
    two_weight = int((patterns["distinct_numeric_weight_strings"] > 1).sum())
    return pd.DataFrame(
        [
            {
                "gate_passed": int(passed),
                "shipments": int(len(patterns)),
                "shipments_freight_not_constant": int(freight),
                "shipments_weight_not_constant": int(weight),
                "shipments_with_two_distinct_numeric_freight_strings": two_freight,
                "shipments_with_two_distinct_numeric_weight_strings": two_weight,
                "median_freight_per_kg": "",
                "mean_freight_per_kg": "",
                "weighed_shipments": "",
                "reason": (
                    "raw strings are constant inside ASN/DN; rates are still the Yes-line kpi files, not this row"
                    if passed
                    else "raw-string gate failed; freight or weight is not the same string on every line of the ASN/DN. Rates are not on this row. The accepted Yes-line rule is applied after this gate and written to the kpi files."
                ),
                "accepted_rule": ACCEPTED_RULE,
                "accepted_rule_date": ACCEPTED_RULE_DATE,
            }
        ]
    )


def save_csv(df: pd.DataFrame, name: str, max_rows: int = 500) -> Path:
    """Write a table. Refuse a line-level dump of the extract.

    Aggregates stay at or under 500 rows. The shipment rollup is the one
    exception: one row per ASN/DN, which is 7,030 on this file and still
    below the 10,324 line extract. A file that reaches the line count is
    the extract under another name, and it is refused.
    """
    if len(df) >= EXPECTED_ROWS:
        raise SystemExit(f"{name} has {len(df)} rows; refusing a line-level extract")
    if len(df) > max_rows:
        raise SystemExit(f"{name} has {len(df)} rows; limit is {max_rows}")
    path = PROC / name
    df.to_csv(path, index=False, na_rep="")
    return path


def save_charts(freight_classes: pd.DataFrame, patterns: pd.DataFrame) -> None:
    """Two charts that explain the gate. Neither is a freight rate.

    A median-by-mode bar is the chart this project will want once a shipment
    figure exists. Drawing it now, from lines, would repeat a delivery-note
    charge once per line and would count a pointer as if it were a class of cost.
    """
    IMG.mkdir(parents=True, exist_ok=True)

    plot = freight_classes.sort_values("lines", ascending=True)
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.barh(plot["freight_class"], plot["lines"], color="#4C78A8")
    for i, rec in enumerate(plot.itertuples(index=False)):
        ax.text(rec.lines + 80, i, f"{rec.lines:,} lines", va="center", fontsize=9)
    ax.set_xlim(0, plot["lines"].max() * 1.28)
    ax.set_xlabel("Lines (not shipments)")
    ax.set_title("Freight text class, every line. Not a cost rate.")
    fig.tight_layout()
    fig.savefig(IMG / "freight_class_by_line.png", dpi=120)
    plt.close(fig)

    order = [
        "constant_numeric",
        "constant_included_in_price",
        "constant_invoiced_separately",
        "mixed_numeric_and_see",
        "mixed_invoiced_and_see",
    ]
    counts = (
        patterns.groupby("freight_pattern").size().reindex(order).fillna(0).astype(int)
    )
    labels = [
        "Constant: numeric",
        "Constant: included in price",
        "Constant: invoiced separately",
        "Mixed: numeric and See pointer",
        "Mixed: invoiced and See pointer",
    ]
    colors = ["#4C78A8", "#4C78A8", "#4C78A8", "#E45756", "#E45756"]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    y = list(range(len(order)))
    ax.barh(y, counts.to_numpy(), color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    for i, n in enumerate(counts.to_numpy()):
        ax.text(n + 40, i, f"{int(n):,} shipments", va="center", fontsize=9)
    ax.set_xlim(0, max(counts.to_numpy()) * 1.32)
    ax.set_xlabel("Shipments (ASN/DN #)")
    ax.set_title("Is the freight string the same on every line of the note?")
    fig.tight_layout()
    fig.savefig(IMG / "freight_text_patterns_by_shipment.png", dpi=120)
    plt.close(fig)


def _sqlite_numeric(expr: str) -> str:
    """SQL predicate matching PLAIN_NUMBER. Do not CAST text to a number.

    SQLite CAST('See ASN-1 (ID#:2)' AS REAL) is 0. A cast would turn every
    pointer into a free shipment. The GLOB tests reject letters, a second
    dot, and a dot with no digits.
    """
    return (
        f"{expr} NOT GLOB '*[^0-9.]*' "
        f"AND {expr} GLOB '*[0-9]*' "
        f"AND {expr} NOT GLOB '*.*.*' "
        f"AND {expr} NOT GLOB '.*' "
        f"AND {expr} NOT GLOB '*.'"
    )


def verify_sql(df: pd.DataFrame, patterns: pd.DataFrame, shipments: pd.DataFrame) -> pd.DataFrame:
    """Run sql/kpi_freight.sql on an in-memory copy and require the same counts.

    The SQL file is what a person would run in SQLite. This check exists so
    the file cannot drift from the Python classification. It does not create
    a database on disk.
    """
    if not SQL_PATH.is_file():
        raise SystemExit(f"missing SQL file: {SQL_PATH}")

    conn = sqlite3.connect(":memory:")
    published = df.drop(columns=["freight_class", "weight_class"])
    published.to_sql("delivery_lines", conn, index=False)

    script = SQL_PATH.read_text(encoding="utf-8")
    statements = []
    buffer: list[str] = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "":
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buffer))
            buffer = []
    if buffer:
        raise SystemExit("SQL file has an unterminated statement")

    collected = []
    for statement in statements:
        cursor = conn.execute(statement)
        if cursor.description is None:
            continue
        columns = [item[0] for item in cursor.description]
        for row in cursor.fetchall():
            collected.append(dict(zip(columns, row)))
    conn.close()

    result = pd.DataFrame(collected)
    if "check_name" not in result.columns:
        raise SystemExit("SQL checks did not return check_name")

    def one(check: str, column: str):
        hit = result.loc[result["check_name"] == check, column]
        if len(hit) != 1:
            raise SystemExit(f"SQL check {check}.{column} returned {len(hit)} rows")
        return hit.iloc[0]

    freight_not_constant = int(
        df.groupby("ASN/DN #")["Freight Cost (USD)"].nunique(dropna=False).gt(1).sum()
    )
    weight_not_constant = int(
        df.groupby("ASN/DN #")["Weight (Kilograms)"].nunique(dropna=False).gt(1).sum()
    )
    comparisons = [
        ("row_and_asn", "line_rows", EXPECTED_ROWS),
        ("row_and_asn", "shipments", int(df["ASN/DN #"].nunique())),
        ("freight_not_constant", "shipments", freight_not_constant),
        ("weight_not_constant", "shipments", weight_not_constant),
        ("two_numeric_freight", "shipments", int((patterns["distinct_numeric_freight_strings"] > 1).sum())),
        ("two_numeric_weight", "shipments", int((patterns["distinct_numeric_weight_strings"] > 1).sum())),
        ("line_value_zero", "lines", int((df["Line Item Value"] == "0").sum())),
        ("see_not_own_asn", "lines", 0),
        ("blank_shipment_mode", "lines", int(df["Shipment Mode"].isna().sum())),
    ]
    for check, column, want in comparisons:
        got = int(one(check, column))
        if got != int(want):
            raise SystemExit(f"SQL {check}.{column}={got} python={want}")

    class_map = {
        "freight_class": "freight_class",
        "weight_class": "weight_class",
    }
    for check, col in class_map.items():
        sql_counts = result.loc[result["check_name"] == check, ["class_name", "lines"]]
        py_counts = df[col].value_counts()
        if set(sql_counts["class_name"]) != set(py_counts.index):
            raise SystemExit(f"SQL {check} classes differ from Python")
        for rec in sql_counts.itertuples(index=False):
            if int(rec.lines) != int(py_counts[rec.class_name]):
                raise SystemExit(
                    f"SQL {check} {rec.class_name}={rec.lines} python={py_counts[rec.class_name]}"
                )

    for check, col in (("shipment_mode", "Shipment Mode"), ("vendor_inco_term", "Vendor INCO Term")):
        sql_counts = result.loc[result["check_name"] == check, ["label", "lines"]]
        series = df[col].fillna("(blank)")
        py_counts = series.value_counts()
        if int(sql_counts["lines"].sum()) != len(df):
            raise SystemExit(f"SQL {check} lines do not sum to the file")
        for rec in sql_counts.itertuples(index=False):
            if int(rec.lines) != int(py_counts[rec.label]):
                raise SystemExit(f"SQL {check} {rec.label}={rec.lines} python={py_counts[rec.label]}")

    for check, col, want in (
        ("cardinality", "vendor", int(df["Vendor"].nunique(dropna=True))),
        ("cardinality", "country", int(df["Country"].nunique(dropna=True))),
        ("cardinality", "manufacturing_site", int(df["Manufacturing Site"].nunique(dropna=True))),
    ):
        got = int(one(check, col))
        if got != want:
            raise SystemExit(f"SQL cardinality {col}={got} python={want}")

    # The numeric predicate itself, on the strings SQLite stored.
    probe = conn_probe = sqlite3.connect(":memory:")
    published.to_sql("delivery_lines", probe, index=False)
    freight_pred = _sqlite_numeric('"Freight Cost (USD)"')
    sql_numeric = probe.execute(
        f'SELECT COUNT(*) FROM delivery_lines WHERE {freight_pred}'
    ).fetchone()[0]
    probe.close()
    py_numeric = int(df["Freight Cost (USD)"].map(is_plain_number).sum())
    if int(sql_numeric) != py_numeric:
        raise SystemExit(f"SQL numeric predicate {sql_numeric} != python {py_numeric}")

    _check_yes_line_sql(result, shipments)
    result.insert(0, "matched_python", 1)
    return result


def _sql_one(result: pd.DataFrame, check: str, column: str):
    hit = result.loc[result["check_name"] == check, column]
    if len(hit) != 1:
        raise SystemExit(f"SQL check {check}.{column} returned {len(hit)} rows")
    return hit.iloc[0]


def _close(check: str, got, want, tol: float) -> None:
    if abs(float(got) - float(want)) > tol:
        raise SystemExit(f"SQL {check}={got} python={want}")


def _check_yes_line_sql(result: pd.DataFrame, shipments: pd.DataFrame) -> None:
    """The Yes-line rollup in sql/kpi_freight.sql matches this run.

    Counts are exact. Rates are float, so the tolerance is there for a
    different addition order, not for a different population. A miss
    raises. The SQL file is not allowed to drift from the scorecard.
    """
    weighed = shipments.loc[shipments["in_weighed"] == 1]
    ftv = shipments.loc[shipments["in_freight_to_value"] == 1]
    comparisons = [
        ("yes_freight_other", "shipments", 0),
        ("yes_line_rows", "lines", len(shipments)),
        ("yes_line_rows", "shipments", shipments["asn_dn"].nunique()),
        ("yes_priced", "shipments", int(shipments["in_priced"].sum())),
        ("yes_weighed", "shipments", int(shipments["in_weighed"].sum())),
        ("yes_freight_to_value", "shipments", int(shipments["in_freight_to_value"].sum())),
        ("yes_excluded_included", "shipments", int((shipments["exclusion_reason"] == "included_in_price").sum())),
        ("yes_excluded_invoiced", "shipments", int((shipments["exclusion_reason"] == "invoiced_separately").sum())),
        ("yes_excluded_see", "shipments", int((shipments["exclusion_reason"] == "see_another_note").sum())),
        ("yes_excluded_weight_text", "shipments", int((shipments["exclusion_reason"] == "weight_not_numeric").sum())),
        ("yes_excluded_weight_not_positive", "shipments", int((shipments["exclusion_reason"] == "weight_not_positive").sum())),
        ("yes_value_sum_le_0", "shipments", int(shipments["value_sum_not_positive"].sum())),
        ("yes_priced_value_sum_le_0", "shipments", int(((shipments["in_priced"] == 1) & (shipments["value_sum_not_positive"] == 1)).sum())),
    ]
    for check, column, want in comparisons:
        got = int(_sql_one(result, check, column))
        if got != int(want):
            raise SystemExit(f"SQL {check}.{column}={got} python={want}")

    _close(
        "yes_total_numeric_freight",
        _sql_one(result, "yes_total_numeric_freight", "total_freight"),
        float(shipments.loc[shipments["in_priced"] == 1, "freight_usd"].sum()),
        0.02,
    )
    _close(
        "yes_median_freight_per_kg",
        _sql_one(result, "yes_median_freight_per_kg", "median_rate"),
        float(weighed["freight_per_kg"].median()),
        1e-6,
    )
    _close(
        "yes_mean_freight_per_kg",
        _sql_one(result, "yes_mean_freight_per_kg", "mean_rate"),
        float(weighed["freight_per_kg"].mean()),
        1e-6,
    )
    _close(
        "yes_median_freight_to_value",
        _sql_one(result, "yes_median_freight_to_value", "median_rate"),
        float(ftv["freight_to_value"].median()),
        1e-6,
    )
    _close(
        "yes_mean_freight_to_value",
        _sql_one(result, "yes_mean_freight_to_value", "mean_rate"),
        float(ftv["freight_to_value"].mean()),
        1e-6,
    )
    sql_modes = result.loc[result["check_name"] == "yes_mode_rate", ["label", "weighed_n", "mean_rate", "median_rate"]]
    if sql_modes.empty:
        raise SystemExit("SQL yes_mode_rate returned no rows")
    for rec in sql_modes.itertuples(index=False):
        sub = weighed.loc[weighed["shipment_mode"] == rec.label, "freight_per_kg"]
        if int(rec.weighed_n) != len(sub):
            raise SystemExit(f"SQL mode {rec.label} n={rec.weighed_n} python={len(sub)}")
        _close(f"yes_mode_rate mean {rec.label}", rec.mean_rate, float(sub.mean()), 1e-6)
        _close(f"yes_mode_rate median {rec.label}", rec.median_rate, float(sub.median()), 1e-6)


def _copy_constant(df: pd.DataFrame, column: str) -> pd.Series:
    """One value per ASN/DN. Raise if the column is not constant.

    Mode, vendor, country, and INCO term passed the constancy gate. The
    Yes-line rule copies them. It does not pick a manufacturing site,
    and this helper is not called for that column. A future file that
    mixes mode inside a note has to stop, not silently take the Yes line's
    mode while another line says something else.
    """
    nunique = df.groupby("ASN/DN #", dropna=False)[column].nunique(dropna=False)
    mixed = int((nunique > 1).sum())
    if mixed != 0:
        raise SystemExit(
            f"{column} is not constant on {mixed} shipments; "
            "the Yes-line rule does not choose among them"
        )
    # The Yes line carries the only value. Null stays null here; the
    # scorecard labels a null mode as (blank) at grouping time.
    yes = df.loc[df["First Line Designation"] == "Yes", ["ASN/DN #", column]]
    if yes["ASN/DN #"].duplicated().any():
        raise SystemExit(f"more than one Yes line while copying {column}")
    return yes.set_index("ASN/DN #")[column]


def _exclusion_reason(freight_cls: str, weight_cls: str, weight_value: float | None) -> str:
    """Why a shipment is outside the weighed set. Kept is not an exclusion.

    The order is the order the sets are defined. A non-numeric freight
    string never reaches the weight checks, so an included-in-price
    shipment is not also counted as a missing weight. A numeric weight
    of zero is its own reason: the string parsed, and it still cannot
    be a denominator.
    """
    if freight_cls == "included_in_price":
        return "included_in_price"
    if freight_cls == "invoiced_separately":
        return "invoiced_separately"
    if freight_cls == "see_another_note":
        return "see_another_note"
    if freight_cls != "numeric":
        raise SystemExit(f"yes-line freight class {freight_cls} has no exclusion rule")
    if weight_cls != "numeric":
        return "weight_not_numeric"
    if weight_value is None or not (weight_value > 0):
        return "weight_not_positive"
    return "kept"


def yes_line_rollup(df: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
    """One row per ASN/DN under the accepted Yes-line rule.

    Why this rule, and why it is not an average. The raw freight string
    is not constant on 1,299 shipments and the raw weight string is not
    constant on 1,322, so the constancy gate does not pass and this
    function does not pretend it did. The strings that disagree are not
    two bills. No shipment has two different numeric freight strings or
    two different numeric weight strings (the pattern table is checked
    again here). Every shipment has exactly one First Line Designation
    = Yes line. Every See pointer cites that line's ID on the same
    ASN/DN. The user accepted, on 2026-09-29, that the Yes line's freight
    string and weight string are the shipment's strings.

    What the rule refuses. Included-in-price, invoiced separately, and a
    See pointer are not parsed and not replaced with zero. A numeric
    weight that is not positive is not a per-kilogram denominator. Line
    item value is summed across the lines of the note. Freight is not
    summed. Insurance is not read. Manufacturing site is not copied,
    because it is not constant and this rule does not pick a site.
    """
    if int((patterns["distinct_numeric_freight_strings"] > 1).sum()) != 0:
        raise SystemExit(
            "a shipment has two numeric freight strings; "
            "the Yes-line rule was accepted because that count was zero"
        )
    if int((patterns["distinct_numeric_weight_strings"] > 1).sum()) != 0:
        raise SystemExit(
            "a shipment has two numeric weight strings; "
            "the Yes-line rule was accepted because that count was zero"
        )
    yes_count = df.groupby("ASN/DN #", dropna=False)["First Line Designation"].apply(
        lambda s: int((s == "Yes").sum())
    )
    if not (yes_count == 1).all():
        raise SystemExit("Yes-line rule requires exactly one Yes line per ASN/DN")

    yes = df.loc[df["First Line Designation"] == "Yes"].copy()
    if len(yes) != df["ASN/DN #"].nunique():
        raise SystemExit("Yes-line extract is not one row per shipment")
    if yes["freight_class"].eq("other").any() or yes["weight_class"].eq("other").any():
        raise SystemExit("unclassified text on a Yes line")

    value = df["Line Item Value"].map(float)
    value_sum = df.assign(_v=value).groupby("ASN/DN #", dropna=False)["_v"].sum()
    line_count = df.groupby("ASN/DN #", dropna=False).size()

    mode = _copy_constant(df, "Shipment Mode")
    vendor = _copy_constant(df, "Vendor")
    country = _copy_constant(df, "Country")
    inco = _copy_constant(df, "Vendor INCO Term")

    yes = yes.set_index("ASN/DN #", drop=False)
    rows = []
    for asn, rec in yes.iterrows():
        freight_text = rec["Freight Cost (USD)"]
        weight_text = rec["Weight (Kilograms)"]
        freight_num = float(freight_text) if is_plain_number(freight_text) else None
        weight_num = float(weight_text) if is_plain_number(weight_text) else None
        reason = _exclusion_reason(rec["freight_class"], rec["weight_class"], weight_num)
        in_priced = int(freight_num is not None)
        in_weighed = int(reason == "kept")
        vsum = float(value_sum.loc[asn])
        in_ftv = int(in_priced == 1 and vsum > 0)
        if in_weighed and (weight_num is None or weight_num <= 0):
            raise SystemExit(f"{asn} marked weighed with a non-positive weight")
        if in_priced != int(rec["freight_class"] == "numeric"):
            raise SystemExit(f"{asn} priced flag does not match the freight class")
        rows.append(
            {
                "asn_dn": asn,
                "line_count": int(line_count.loc[asn]),
                "shipment_mode": "(blank)" if pd.isna(mode.loc[asn]) else mode.loc[asn],
                "vendor": vendor.loc[asn],
                "country": country.loc[asn],
                "vendor_inco_term": inco.loc[asn],
                "yes_line_id": rec["ID"],
                "yes_freight_text": freight_text,
                "yes_weight_text": weight_text,
                "yes_freight_class": rec["freight_class"],
                "yes_weight_class": rec["weight_class"],
                "freight_usd": freight_num,
                "weight_kg": weight_num,
                "line_item_value_sum": vsum,
                "in_priced": in_priced,
                "in_weighed": in_weighed,
                "in_freight_to_value": in_ftv,
                "freight_per_kg": (freight_num / weight_num) if in_weighed else None,
                "freight_to_value": (freight_num / vsum) if in_ftv else None,
                "exclusion_reason": reason,
                "value_sum_not_positive": int(vsum <= 0),
            }
        )
    out = pd.DataFrame(rows)
    if len(out) != df["ASN/DN #"].nunique():
        raise SystemExit("shipment rollup missed an ASN/DN")
    if out["asn_dn"].duplicated().any():
        raise SystemExit("shipment rollup has a duplicate ASN/DN")
    if "Manufacturing Site" in out.columns:
        raise SystemExit("manufacturing site leaked into the scorecard rollup")
    # Freight was not summed across lines. A priced shipment carries the
    # Yes line's number once. The exclusion reasons partition the file.
    reasons = out["exclusion_reason"].value_counts()
    if int(reasons.get("kept", 0)) != int(out["in_weighed"].sum()):
        raise SystemExit("weighed flag does not match exclusion_reason kept")
    if int(out["in_priced"].sum()) + int(out["exclusion_reason"].isin(
        ["included_in_price", "invoiced_separately", "see_another_note"]
    ).sum()) != len(out):
        raise SystemExit("priced set and freight-text exclusions do not partition the file")
    priced = out["in_priced"] == 1
    if int(priced.sum()) != int(out["in_weighed"].sum()) + int(
        out["exclusion_reason"].isin(["weight_not_numeric", "weight_not_positive"]).sum()
    ):
        raise SystemExit("weighed set and weight exclusions do not partition the priced set")
    return out


def _median(series: pd.Series) -> float | None:
    """Pandas median. Even counts average the two middle values. Empty is blank."""
    if len(series) == 0:
        return None
    return float(series.median())


def _mean(series: pd.Series) -> float | None:
    if len(series) == 0:
        return None
    return float(series.mean())


def _rate_columns(sub: pd.DataFrame) -> dict:
    """The rate fields every cut shares. Empty rates stay None, never zero."""
    weighed = sub.loc[sub["in_weighed"] == 1, "freight_per_kg"]
    ftv = sub.loc[sub["in_freight_to_value"] == 1, "freight_to_value"]
    priced = sub.loc[sub["in_priced"] == 1, "freight_usd"]
    return {
        "shipments": int(len(sub)),
        "priced_n": int(sub["in_priced"].sum()),
        "weighed_n": int(sub["in_weighed"].sum()),
        "median_freight_per_kg": _median(weighed),
        "mean_freight_per_kg": _mean(weighed),
        "freight_to_value_n": int(sub["in_freight_to_value"].sum()),
        "median_freight_to_value": _median(ftv),
        "mean_freight_to_value": _mean(ftv),
        "total_numeric_freight": float(priced.sum()) if len(priced) else 0.0,
        "excluded_included_in_price": int((sub["exclusion_reason"] == "included_in_price").sum()),
        "excluded_invoiced_separately": int((sub["exclusion_reason"] == "invoiced_separately").sum()),
        "excluded_see_another_note": int((sub["exclusion_reason"] == "see_another_note").sum()),
        "excluded_weight_not_numeric": int((sub["exclusion_reason"] == "weight_not_numeric").sum()),
        "excluded_weight_not_positive": int((sub["exclusion_reason"] == "weight_not_positive").sum()),
        "value_sum_not_positive": int(sub["value_sum_not_positive"].sum()),
        "value_sum_not_positive_among_priced": int(
            ((sub["in_priced"] == 1) & (sub["value_sum_not_positive"] == 1)).sum()
        ),
    }


def cut_kpis(shipments: pd.DataFrame, column: str) -> pd.DataFrame:
    """One row per level of a scorecard cut.

    rank_eligible is 0 when the weighed count is under RANK_MIN_WEIGHED.
    Those rows stay in this file. kpi_small_n.csv repeats them so a
    sort by median cannot be read as a ranking of tiny groups. Median
    cells are blank, not zero, when the weighed count is zero.
    """
    rows = []
    for label, sub in shipments.groupby(column, dropna=False):
        rec = {column: label}
        rec.update(_rate_columns(sub))
        rec["rank_eligible"] = int(rec["weighed_n"] >= RANK_MIN_WEIGHED)
        rows.append(rec)
    out = pd.DataFrame(rows)
    if int(out["shipments"].sum()) != len(shipments):
        raise SystemExit(f"{column} cut does not cover the population it was given")
    out = out.sort_values(
        ["rank_eligible", "median_freight_per_kg", column],
        ascending=[False, False, True],
        na_position="last",
    ).reset_index(drop=True)
    return out


def overall_kpis(shipments: pd.DataFrame) -> pd.DataFrame:
    """Long scorecard: denominators, drops, and the two headline rates.

    Freight per kilogram uses the weighed set. Freight-to-value uses
    numeric Yes-line freight and a positive sum of line-item value.
    Those populations are not the same, and both denominators are rows
    in this file. A drop is a count of shipments, not a zero rate.
    """
    rates = _rate_columns(shipments)
    weighed = shipments.loc[shipments["in_weighed"] == 1, "freight_per_kg"]
    ftv = shipments.loc[shipments["in_freight_to_value"] == 1, "freight_to_value"]
    if rates["shipments"] != (
        rates["weighed_n"]
        + rates["excluded_included_in_price"]
        + rates["excluded_invoiced_separately"]
        + rates["excluded_see_another_note"]
        + rates["excluded_weight_not_numeric"]
        + rates["excluded_weight_not_positive"]
    ):
        raise SystemExit("overall exclusions do not add up to every shipment")
    # The mean sits next to the median because the tail pulls it. The
    # mean of the weighed shipments at or below p95 is the comparison
    # that shows the pull, and it is still computed, not a comment.
    p95 = float(weighed.quantile(0.95))
    at_or_below = weighed[weighed <= p95]
    ftv_p95 = float(ftv.quantile(0.95)) if len(ftv) else None
    ftv_body = ftv[ftv <= ftv_p95] if ftv_p95 is not None else ftv
    metrics = {
        "rule": ACCEPTED_RULE,
        "rule_date": ACCEPTED_RULE_DATE,
        "shipments": rates["shipments"],
        "priced_n": rates["priced_n"],
        "weighed_n": rates["weighed_n"],
        "freight_to_value_n": rates["freight_to_value_n"],
        "excluded_included_in_price": rates["excluded_included_in_price"],
        "excluded_invoiced_separately": rates["excluded_invoiced_separately"],
        "excluded_see_another_note": rates["excluded_see_another_note"],
        "excluded_weight_not_numeric": rates["excluded_weight_not_numeric"],
        "excluded_weight_not_positive": rates["excluded_weight_not_positive"],
        "value_sum_not_positive": rates["value_sum_not_positive"],
        "value_sum_not_positive_among_priced": rates["value_sum_not_positive_among_priced"],
        "value_sum_not_positive_among_weighed": int(
            ((shipments["in_weighed"] == 1) & (shipments["value_sum_not_positive"] == 1)).sum()
        ),
        "median_freight_per_kg": rates["median_freight_per_kg"],
        "mean_freight_per_kg": rates["mean_freight_per_kg"],
        "max_freight_per_kg": float(weighed.max()) if len(weighed) else None,
        "p95_freight_per_kg": p95 if len(weighed) else None,
        "weighed_n_at_or_below_p95": int(len(at_or_below)),
        "mean_freight_per_kg_at_or_below_p95": _mean(at_or_below),
        "median_freight_to_value": rates["median_freight_to_value"],
        "mean_freight_to_value": rates["mean_freight_to_value"],
        "max_freight_to_value": float(ftv.max()) if len(ftv) else None,
        "p95_freight_to_value": ftv_p95,
        "freight_to_value_n_at_or_below_p95": int(len(ftv_body)),
        "mean_freight_to_value_at_or_below_p95": _mean(ftv_body),
        "total_numeric_freight": rates["total_numeric_freight"],
        "total_numeric_freight_weighed": float(
            shipments.loc[shipments["in_weighed"] == 1, "freight_usd"].sum()
        ),
        "rank_min_weighed": RANK_MIN_WEIGHED,
        "weight_band_lo_kg": WEIGHT_BAND_LO_KG,
        "weight_band_hi_kg": WEIGHT_BAND_HI_KG,
    }
    rows = [{"metric": key, "value": value} for key, value in metrics.items()]
    return pd.DataFrame(rows)


def quantile_table(shipments: pd.DataFrame) -> pd.DataFrame:
    """p10 through p95 of freight per kg, overall and by mode.

    The mean is on the same row so the gap is a computed comparison.
    Freight-to-value quantiles are the second metric. The populations
    match the headline: weighed set, and priced with a positive value sum.
    """
    probs = [0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
    labels = ["p10", "p25", "p50", "p75", "p90", "p95"]

    def one(metric: str, slice_name: str, series: pd.Series) -> dict:
        rec = {
            "metric": metric,
            "slice": slice_name,
            "n": int(len(series)),
            "mean": _mean(series),
            "max": float(series.max()) if len(series) else None,
        }
        if len(series) == 0:
            for label in labels:
                rec[label] = None
            return rec
        quant = series.quantile(probs)
        for label, prob in zip(labels, probs):
            rec[label] = float(quant.loc[prob])
        return rec

    rows = []
    weighed = shipments.loc[shipments["in_weighed"] == 1]
    rows.append(one("freight_per_kg", "weighed_set", weighed["freight_per_kg"]))
    for mode, sub in weighed.groupby("shipment_mode", dropna=False):
        rows.append(one("freight_per_kg", f"weighed_mode={mode}", sub["freight_per_kg"]))
    band = weighed[
        (weighed["weight_kg"] >= WEIGHT_BAND_LO_KG) & (weighed["weight_kg"] <= WEIGHT_BAND_HI_KG)
    ]
    rows.append(
        one(
            "freight_per_kg",
            f"weighed_weight_{int(WEIGHT_BAND_LO_KG)}_to_{int(WEIGHT_BAND_HI_KG)}_kg",
            band["freight_per_kg"],
        )
    )
    ftv = shipments.loc[shipments["in_freight_to_value"] == 1, "freight_to_value"]
    rows.append(one("freight_to_value", "priced_and_positive_value_sum", ftv))
    out = pd.DataFrame(rows)
    overall = out.loc[
        (out["metric"] == "freight_per_kg") & (out["slice"] == "weighed_set")
    ].iloc[0]
    headline = _median(weighed["freight_per_kg"])
    if headline is None or abs(float(overall["p50"]) - headline) > 1e-9:
        raise SystemExit("p50 of freight per kg is not the headline median")
    return out


def _most_common_mode(shipments: pd.DataFrame) -> str:
    """Mode with the most shipments, not the most lines and not the highest rate."""
    counts = shipments["shipment_mode"].value_counts()
    if counts.empty:
        raise SystemExit("no modes to control on")
    top = counts.index[0]
    if top == "(blank)":
        raise SystemExit("the most common mode is blank; refusing to control on a null")
    return str(top)


def weight_band_mask(shipments: pd.DataFrame) -> pd.Series:
    """Weighed shipments inside the stated band, inclusive on both edges."""
    return (
        (shipments["in_weighed"] == 1)
        & (shipments["weight_kg"] >= WEIGHT_BAND_LO_KG)
        & (shipments["weight_kg"] <= WEIGHT_BAND_HI_KG)
    )


def assert_band_covers_modes(shipments: pd.DataFrame) -> None:
    """The band is only a size control if each named mode still has a ranking n."""
    band = shipments.loc[weight_band_mask(shipments)]
    counts = band["shipment_mode"].value_counts()
    named = [mode for mode in shipments["shipment_mode"].unique() if mode != "(blank)"]
    short = [mode for mode in named if int(counts.get(mode, 0)) < RANK_MIN_WEIGHED]
    if short:
        raise SystemExit(
            f"weight band {WEIGHT_BAND_LO_KG}-{WEIGHT_BAND_HI_KG} leaves {short} "
            f"under {RANK_MIN_WEIGHED} weighed shipments; do not use it as the control"
        )


def control_frame(shipments: pd.DataFrame) -> pd.DataFrame:
    """Which mode, which band, and the reference median the ranking is judged against.

    The reference is the weighed Air (or whichever mode is most common)
    shipments inside the weight band. A vendor median above that number
    is above the typical shipment of the same mode and a similar weight.
    It is not, by itself, the word expensive.
    """
    mode = _most_common_mode(shipments)
    assert_band_covers_modes(shipments)
    in_mode = shipments["shipment_mode"] == mode
    in_band = weight_band_mask(shipments) & in_mode
    reference = shipments.loc[in_band, "freight_per_kg"]
    mode_shipments = int(in_mode.sum())
    rows = [
        {"metric": "most_common_mode", "value": mode},
        {"metric": "most_common_mode_shipments", "value": mode_shipments},
        {"metric": "most_common_mode_weighed_n", "value": int((in_mode & (shipments["in_weighed"] == 1)).sum())},
        {"metric": "weight_band_lo_kg", "value": WEIGHT_BAND_LO_KG},
        {"metric": "weight_band_hi_kg", "value": WEIGHT_BAND_HI_KG},
        {"metric": "weight_band_edges", "value": "inclusive"},
        {"metric": "rank_min_weighed", "value": RANK_MIN_WEIGHED},
        {"metric": "reference_population", "value": f"{mode} and weight in band"},
        {"metric": "reference_weighed_n", "value": int(in_band.sum())},
        {"metric": "reference_median_freight_per_kg", "value": _median(reference)},
        {"metric": "reference_mean_freight_per_kg", "value": _mean(reference)},
    ]
    return pd.DataFrame(rows)


def survival_table(shipments: pd.DataFrame, column: str, reference_median: float) -> pd.DataFrame:
    """Uncontrolled median next to the mode control and the mode-plus-band control.

    A row is an uncontrolled ranking candidate only when the weighed count
    on the whole file is at least RANK_MIN_WEIGHED. survives_weight_and_mode
    means the same label still has that many weighed shipments inside the
    most common mode and the stated weight band, and above_reference means
    that controlled median is above the reference median. A high
    uncontrolled median with a small controlled n does not survive.
    """
    mode = _most_common_mode(shipments)
    in_mode = shipments["shipment_mode"] == mode
    in_band = weight_band_mask(shipments) & in_mode
    rows = []
    for label, sub in shipments.groupby(column, dropna=False):
        weighed = sub.loc[sub["in_weighed"] == 1, "freight_per_kg"]
        if len(weighed) < RANK_MIN_WEIGHED:
            continue
        air = sub.loc[(sub["in_weighed"] == 1) & (sub["shipment_mode"] == mode), "freight_per_kg"]
        band = sub.loc[
            (sub["in_weighed"] == 1)
            & (sub["shipment_mode"] == mode)
            & (sub["weight_kg"] >= WEIGHT_BAND_LO_KG)
            & (sub["weight_kg"] <= WEIGHT_BAND_HI_KG),
            "freight_per_kg",
        ]
        med_band = _median(band)
        survives_n = int(len(band) >= RANK_MIN_WEIGHED)
        rows.append(
            {
                "cut": column,
                "label": label,
                "weighed_n": int(len(weighed)),
                "median_freight_per_kg": _median(weighed),
                "mean_freight_per_kg": _mean(weighed),
                "weighed_n_top_mode": int(len(air)),
                "median_freight_per_kg_top_mode": _median(air),
                "weighed_n_top_mode_weight_band": int(len(band)),
                "median_freight_per_kg_top_mode_weight_band": med_band,
                "survives_mode_and_weight_n": survives_n,
                "above_reference_median": int(
                    survives_n == 1 and med_band is not None and med_band > reference_median
                ),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        raise SystemExit(f"no {column} group reached the ranking threshold")
    # in_band is used to keep the reference definition next to this table.
    if int(in_band.sum()) == 0:
        raise SystemExit("reference band is empty")
    return out.sort_values(
        ["median_freight_per_kg", "label"], ascending=[False, True]
    ).reset_index(drop=True)


def small_n_table(parts: list[tuple[str, pd.DataFrame, str]]) -> pd.DataFrame:
    """Every cut row under the ranking threshold, still listed, not ranked."""
    frames = []
    for source, frame, column in parts:
        small = frame.loc[frame["rank_eligible"] == 0].copy()
        if small.empty:
            continue
        small.insert(0, "source", source)
        small.insert(1, "label", small[column].astype(str))
        keep = [
            "source",
            "label",
            "shipments",
            "priced_n",
            "weighed_n",
            "median_freight_per_kg",
            "mean_freight_per_kg",
            "median_freight_to_value",
            "total_numeric_freight",
            "rank_eligible",
        ]
        frames.append(small[keep])
    if not frames:
        raise SystemExit("small-n file would be empty; the threshold would be invisible")
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(
        ["source", "weighed_n", "label"], ascending=[True, True, True]
    ).reset_index(drop=True)


def save_mode_rate_chart(mode_kpi: pd.DataFrame) -> None:
    """Median freight per kg by mode. Weighed set only. Not a line chart.

    Blank mode is included and labeled, because those shipments are in
    the weighed set and hiding them would shrink the denominator. The
    title names the set and the rule so the chart cannot be read as a
    line-level mean or as the raw-string gate.
    """
    plot = mode_kpi.loc[mode_kpi["weighed_n"] > 0].sort_values(
        "median_freight_per_kg", ascending=True
    )
    if plot.empty:
        raise SystemExit("no mode has a weighed shipment; refusing an empty rate chart")
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    y = list(range(len(plot)))
    ax.barh(y, plot["median_freight_per_kg"], color="#4C78A8")
    ax.set_yticks(y)
    ax.set_yticklabels(plot["shipment_mode"])
    for i, rec in enumerate(plot.itertuples(index=False)):
        ax.text(
            rec.median_freight_per_kg,
            i,
            f"  {rec.median_freight_per_kg:.2f}   n={int(rec.weighed_n):,}",
            va="center",
            fontsize=9,
        )
    ax.set_xlim(0, float(plot["median_freight_per_kg"].max()) * 1.45)
    ax.set_xlabel("Median freight per kg (USD)")
    ax.set_title("Median freight per kg by shipment mode, weighed set, Yes-line rule")
    fig.tight_layout()
    fig.savefig(IMG / "freight_per_kg_by_mode.png", dpi=120)
    plt.close(fig)


def _reference_median(controls: pd.DataFrame) -> float:
    hit = controls.loc[controls["metric"] == "reference_median_freight_per_kg", "value"]
    if len(hit) != 1:
        raise SystemExit("control file has no reference median")
    return float(hit.iloc[0])




def write_scorecard(shipments: pd.DataFrame) -> list[Path]:
    """Write the rate tables. Every rate in these files comes from the rollup.

    The population of kpi_by_mode, kpi_by_country, kpi_by_vendor, and
    kpi_by_inco is every shipment. The within-top-mode files are every
    shipment of the most common mode. The weight-band files are the
    weighed shipments inside the stated kilogram band (and, for country
    and vendor, also inside that mode). A band file has no freight-text
    exclusions left in it, because a non-numeric weight never entered
    the band. Those exclusions are the columns on the full-population cuts.
    """
    if shipments["asn_dn"].nunique() != len(shipments):
        raise SystemExit("scorecard rollup is not one row per ASN/DN")
    overall = overall_kpis(shipments)
    controls = control_frame(shipments)
    reference = _reference_median(controls)
    mode = str(controls.loc[controls["metric"] == "most_common_mode", "value"].iloc[0])

    by_mode = cut_kpis(shipments, "shipment_mode")
    by_country = cut_kpis(shipments, "country")
    by_vendor = cut_kpis(shipments, "vendor")
    by_inco = cut_kpis(shipments, "vendor_inco_term")

    mode_pop = shipments.loc[shipments["shipment_mode"] == mode].copy()
    by_country_mode = cut_kpis(mode_pop, "country")
    by_vendor_mode = cut_kpis(mode_pop, "vendor")

    band_all = shipments.loc[weight_band_mask(shipments)].copy()
    by_mode_band = cut_kpis(band_all, "shipment_mode")
    band_mode = shipments.loc[
        weight_band_mask(shipments) & (shipments["shipment_mode"] == mode)
    ].copy()
    by_country_band = cut_kpis(band_mode, "country")
    by_vendor_band = cut_kpis(band_mode, "vendor")

    survival = pd.concat(
        [
            survival_table(shipments, "vendor", reference),
            survival_table(shipments, "country", reference),
        ],
        ignore_index=True,
    )
    small = small_n_table(
        [
            ("kpi_by_country", by_country, "country"),
            ("kpi_by_vendor", by_vendor, "vendor"),
            ("kpi_by_inco", by_inco, "vendor_inco_term"),
            ("kpi_by_country_within_top_mode", by_country_mode, "country"),
            ("kpi_by_vendor_within_top_mode", by_vendor_mode, "vendor"),
            ("kpi_by_country_within_top_mode_weight_band", by_country_band, "country"),
            ("kpi_by_vendor_within_top_mode_weight_band", by_vendor_band, "vendor"),
            ("kpi_by_mode", by_mode, "shipment_mode"),
            ("kpi_by_mode_weight_band", by_mode_band, "shipment_mode"),
        ]
    )
    quantiles = quantile_table(shipments)

    # The band population is already weighed, so its shipment count is a
    # weighed count. Say so on the file rather than letting a reader add
    # the exclusion columns and think shipments were dropped twice.
    for frame in (by_mode_band, by_country_band, by_vendor_band):
        frame.insert(1, "population", "weighed_inside_weight_band")
    by_country_mode.insert(1, "population", f"all_shipments_mode_{mode}")
    by_vendor_mode.insert(1, "population", f"all_shipments_mode_{mode}")

    return [
        save_csv(shipments, "shipment_rollup.csv", max_rows=len(shipments)),
        save_csv(overall, "kpi_overall.csv"),
        save_csv(by_mode, "kpi_by_mode.csv"),
        save_csv(by_country, "kpi_by_country.csv"),
        save_csv(by_vendor, "kpi_by_vendor.csv"),
        save_csv(by_inco, "kpi_by_inco.csv"),
        save_csv(by_country_mode, "kpi_by_country_within_top_mode.csv"),
        save_csv(by_vendor_mode, "kpi_by_vendor_within_top_mode.csv"),
        save_csv(by_country_band, "kpi_by_country_within_top_mode_weight_band.csv"),
        save_csv(by_vendor_band, "kpi_by_vendor_within_top_mode_weight_band.csv"),
        save_csv(by_mode_band, "kpi_by_mode_weight_band.csv"),
        save_csv(controls, "kpi_controls.csv"),
        save_csv(survival, "kpi_control_survival.csv"),
        save_csv(small, "kpi_small_n.csv", max_rows=800),
        save_csv(quantiles, "kpi_freight_per_kg_quantiles.csv"),
    ]



def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    df = load_raw(RAW)
    df["freight_class"] = df["Freight Cost (USD)"].map(freight_class)
    df["weight_class"] = df["Weight (Kilograms)"].map(weight_class)
    if (df["freight_class"] == "other").any() or (df["weight_class"] == "other").any():
        raise SystemExit("unclassified freight or weight text; do not hide it in other")
    if (df["freight_class"] == "blank").any() or (df["weight_class"] == "blank").any():
        raise SystemExit("blank freight or weight; the classification needs a bucket")

    constancy = constancy_table(df)
    patterns = shipment_patterns(df)
    status = rollup_status(constancy, patterns)
    # The raw-string gate is recorded above, including when it fails.
    # Failing it does not skip the rate, and passing it would not either.
    # The accepted rule is the Yes line. yes_line_rollup raises if the
    # facts that justify that rule are gone (two numeric freight strings,
    # two numeric weights, or not exactly one Yes line). That raise is
    # the opposite of a silent skip. Manufacturing site is not a scorecard
    # column. The script checks the constancy table rather than copying a site.
    site_mixed = int(
        constancy.loc[
            constancy["column_name"] == "Manufacturing Site", "shipments_not_constant"
        ].iloc[0]
    )
    if site_mixed == 0:
        raise SystemExit(
            "manufacturing site is constant on this file; the decision to leave "
            "it out of the scorecard was about the 880 mixed shipments"
        )

    summary = pattern_summary(patterns)
    pointers = see_pointer_check(df)
    if int(pointers["see_lines_point_at_own_asn_dn"].iloc[0]) != int(pointers["see_freight_lines"].iloc[0]):
        raise SystemExit("a See line points at a different ASN/DN; document that before any rule")
    if int(pointers["see_lines_cited_id_is_yes_line_on_same_asn"].iloc[0]) != int(
        pointers["see_freight_lines"].iloc[0]
    ):
        raise SystemExit("a See line does not cite the Yes line on its own note")

    yes_dist = first_line_marker(df)
    if not (
        len(yes_dist) == 1 and int(yes_dist["yes_lines_on_shipment"].iloc[0]) == 1
    ):
        raise SystemExit("First Line Designation is not exactly one Yes per ASN/DN")

    freight_classes = class_counts(df["freight_class"], "freight_class")
    weight_classes = class_counts(df["weight_class"], "weight_class")

    written = [
        save_csv(
            pd.DataFrame(
                [
                    {
                        "file": RAW.name,
                        "encoding": "latin-1",
                        "utf8_decodes": 0,
                        "rows": EXPECTED_ROWS,
                        "columns": EXPECTED_COLS,
                    }
                ]
            ),
            "shape_check.csv",
        ),
        save_csv(
            pd.DataFrame(
                [
                    {
                        "rows": int(len(df)),
                        "distinct_asn_dn": int(df["ASN/DN #"].nunique()),
                        "distinct_id": int(df["ID"].nunique()),
                        "duplicate_id_rows": int(df["ID"].duplicated().sum()),
                        "shipments_with_one_line": int(
                            (df.groupby("ASN/DN #").size() == 1).sum()
                        ),
                        "shipments_with_more_than_one_line": int(
                            (df.groupby("ASN/DN #").size() > 1).sum()
                        ),
                    }
                ]
            ),
            "grain_check.csv",
        ),
        save_csv(lines_per_shipment(df), "lines_per_asn.csv"),
        save_csv(constancy, "constancy_by_column.csv"),
        save_csv(status, "shipment_rollup_status.csv"),
        save_csv(summary, "text_pattern_by_shipment.csv"),
        save_csv(disagreement_examples(df, patterns), "disagreement_examples.csv"),
        save_csv(pointers, "see_pointer_check.csv"),
        save_csv(yes_dist, "first_line_designation.csv"),
        save_csv(yes_line_class_counts(df), "yes_line_text_class.csv"),
        save_csv(freight_classes, "freight_class_counts.csv"),
        save_csv(weight_classes, "weight_class_counts.csv"),
        save_csv(class_by_label(df, "Shipment Mode", "freight_class"), "freight_class_by_mode.csv"),
        save_csv(
            class_by_label(df, "Vendor INCO Term", "freight_class"),
            "freight_class_by_inco.csv",
        ),
        save_csv(null_table(df), "null_counts.csv"),
        save_csv(cardinality_table(df), "cardinality.csv"),
        save_csv(whitespace_labels(df), "whitespace_labels.csv"),
        save_csv(label_counts(df, "Shipment Mode"), "mode_line_counts.csv"),
        save_csv(label_counts(df, "Vendor INCO Term"), "inco_line_counts.csv"),
        save_csv(date_window(df), "date_window.csv"),
        save_csv(other_date_labels(df), "non_delivery_date_labels.csv"),
        save_csv(numeric_range_notes(df), "numeric_range_notes.csv"),
        save_csv(zero_weight_lines(df), "zero_weight_lines.csv"),
        save_csv(manufacturing_site_mix(df), "manufacturing_site_mix.csv"),
    ]

    # Accepted rule. The gate row is already in `written`. Rates follow.
    shipments = yes_line_rollup(df, patterns)
    if len(shipments) != int(status["shipments"].iloc[0]):
        raise SystemExit("rollup shipment count is not the gate's shipment count")
    written.append(save_csv(value_check(df, shipments), "line_item_value_check.csv"))
    written.extend(write_scorecard(shipments))

    sql_result = verify_sql(df, patterns, shipments)
    written.append(save_csv(sql_result, "sql_check_match.csv", max_rows=800))
    save_charts(freight_classes, patterns)
    save_mode_rate_chart(
        pd.read_csv(PROC / "kpi_by_mode.csv")
    )

    overall = pd.read_csv(PROC / "kpi_overall.csv")
    overall_map = dict(zip(overall["metric"], overall["value"]))
    print(
        "confirmation "
        f"rows={EXPECTED_ROWS} cols={EXPECTED_COLS} encoding=latin-1 "
        f"shipments={int(df['ASN/DN #'].nunique())} "
        f"gate_passed={int(status['gate_passed'].iloc[0])} "
        f"freight_not_constant={int(status['shipments_freight_not_constant'].iloc[0])} "
        f"weight_not_constant={int(status['shipments_weight_not_constant'].iloc[0])} "
        f"priced_n={overall_map['priced_n']} "
        f"weighed_n={overall_map['weighed_n']} "
        f"median_freight_per_kg={overall_map['median_freight_per_kg']} "
        f"mean_freight_per_kg={overall_map['mean_freight_per_kg']} "
        f"files={len(written)} charts=3"
    )
    print(f"processed_dir={PROC}")
    print(f"images_dir={IMG}")


if __name__ == "__main__":
    main()
