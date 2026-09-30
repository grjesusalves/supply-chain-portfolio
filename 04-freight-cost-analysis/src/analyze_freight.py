#!/usr/bin/env python3
"""Analyze stage: freight-cost scorecard for the USAID SCMS delivery lines.

This script checks the grain and classifies the freight and weight text.
It does not roll a delivery note up to one freight figure unless freight
and weight are each constant inside that note. It does not fit a regression,
and it does not price a savings scenario. Those belong to Construct and Execute.

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

No output is the full line extract. A shipment-level cost table is written
only when the constancy gate passes. This run does not average conflicting
freight strings, and it does not treat a "See ASN/DN" pointer as zero.
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


def value_check(df: pd.DataFrame) -> pd.DataFrame:
    """Line-item value is a number on every row. Shipment sums are not taken.

    The plan confirms the sum on shipments that are kept. None are kept,
    because the grain gate failed. A zero line is still reported, because a
    later freight-to-value ratio cannot divide by a non-positive sum, and
    hiding the zeros would make that check look finished.
    """
    if not df["Line Item Value"].map(is_plain_number).all():
        bad = int((~df["Line Item Value"].map(is_plain_number)).sum())
        raise SystemExit(f"line item value is not a plain number on {bad} rows")
    values = df["Line Item Value"].map(float)
    zero_lines = int((values == 0).sum())
    negative_lines = int((values < 0).sum())
    # Diagnostic only: the sum a rollup would have used. Not a KPI.
    sums = df.assign(_v=values).groupby("ASN/DN #", dropna=False)["_v"].sum()
    return pd.DataFrame(
        [
            {
                "lines": int(len(df)),
                "lines_plain_number": int(len(df)),
                "lines_positive": int((values > 0).sum()),
                "lines_zero": zero_lines,
                "lines_negative": negative_lines,
                "shipments_kept_for_freight_to_value": 0,
                "reason_none_kept": "constancy gate failed; no shipment rollup",
                "diagnostic_shipments_if_lines_were_summed": int(len(sums)),
                "diagnostic_shipments_with_value_sum_le_0": int((sums <= 0).sum()),
                "diagnostic_shipments_with_value_sum_gt_0": int((sums > 0).sum()),
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
    """The gate. Rates are computed only when this row says the gate passed.

    Passing means every shipment has one freight string and one weight string.
    A pointer that differs from the numeric line is not constant, even when
    the pointer cites that same note.
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
                    "computed"
                    if passed
                    else "not computed; freight or weight is not constant inside ASN/DN, and no rollup rule was invented"
                ),
            }
        ]
    )


def save_csv(df: pd.DataFrame, name: str) -> Path:
    """Write a small aggregate. Refuse a line-level dump of the extract."""
    if len(df) > 500:
        raise SystemExit(f"{name} has {len(df)} rows; refusing a line-level extract")
    path = PROC / name
    df.to_csv(path, index=False)
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


def verify_sql(df: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
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

    result.insert(0, "matched_python", 1)
    return result


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
    if int(status["gate_passed"].iloc[0]) != 0:
        raise SystemExit(
            "gate passed; this script has no shipment-rate path yet. "
            "Do not invent one in the same commit that expected a failure, "
            "and do not leave a passing gate unmeasured."
        )
    # The failure path is the one this extract takes. A future file that
    # passes the gate must grow an explicit rate section. Until then the
    # absence of kpi_by_mode.csv is the result, not an oversight.
    forbidden = list(PROC.glob("kpi_*.csv"))
    if forbidden:
        raise SystemExit(f"refusing to leave a rate file in place: {forbidden}")

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
        save_csv(value_check(df), "line_item_value_check.csv"),
        save_csv(numeric_range_notes(df), "numeric_range_notes.csv"),
        save_csv(zero_weight_lines(df), "zero_weight_lines.csv"),
        save_csv(manufacturing_site_mix(df), "manufacturing_site_mix.csv"),
    ]

    sql_result = verify_sql(df, patterns)
    written.append(save_csv(sql_result, "sql_check_match.csv"))
    save_charts(freight_classes, patterns)

    print(
        "confirmation "
        f"rows={EXPECTED_ROWS} cols={EXPECTED_COLS} encoding=latin-1 "
        f"shipments={int(df['ASN/DN #'].nunique())} "
        f"gate_passed={int(status['gate_passed'].iloc[0])} "
        f"freight_not_constant={int(status['shipments_freight_not_constant'].iloc[0])} "
        f"weight_not_constant={int(status['shipments_weight_not_constant'].iloc[0])} "
        f"files={len(written)} charts=2"
    )
    print(f"processed_dir={PROC}")
    print(f"images_dir={IMG}")


if __name__ == "__main__":
    main()
