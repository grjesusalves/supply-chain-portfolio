#!/usr/bin/env python3
"""Analyze stage: late-delivery scorecard for the DataCo order lines.

This script checks the label and writes the KPI tables. It does not fit a
classifier, a baseline, or a threshold. Those belong to Construct.

Run from the repo root:
    python 03-late-delivery-risk/src/analyze_late_delivery.py

Run from the project folder (03-late-delivery-risk):
    python src/analyze_late_delivery.py

Paths are anchored to this file, not to the shell's current directory, so
either command reads the same raw CSV and writes the same outputs.

Input (git-ignored, already on disk; this script does not copy it):
    03-late-delivery-risk/data/raw/DataCoSupplyChainDataset.csv
    Latin-1. tokenized_access_logs.csv is a different question and is not read.

Outputs under 03-late-delivery-risk/:
    data/processed/*.csv   small aggregate tables only
    images/late_rate_by_shipping_mode.png
    images/real_days_by_shipping_mode.png

No output is row-level. Names, email, password, and street are not written.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save files; do not open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Anchored to this file so a run from the repo root and a run from the
# project folder write the same place. parents[1] is 03-late-delivery-risk.
PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw" / "DataCoSupplyChainDataset.csv"
PROC = PROJECT / "data" / "processed"
IMG = PROJECT / "images"

# The plan's expected shape. A different extract is a different question.
EXPECTED_ROWS = 180_519
EXPECTED_COLS = 53

# Personal-data columns. They are not predictors we want, and a public
# portfolio file should not carry them. The script never selects them into
# an output frame. The block below is the check, not the feature policy.
PII_COLUMNS = (
    "Customer Fname",
    "Customer Lname",
    "Customer Email",
    "Customer Password",
    "Customer Street",
)

# Also never write these. Street-level and precise location sit next to the
# name fields. Order City / Order State are high-cardinality geography, not
# written here either; the cardinality table records only the counts.
LOCATION_COLUMNS = (
    "Customer City",
    "Customer State",
    "Customer Country",
    "Customer Zipcode",
    "Latitude",
    "Longitude",
    "Order Zipcode",
)

# Known when the order is placed, from the plan. Nulls on this set are the
# ones that would change a model. Outcome fields are deliberately absent.
CANDIDATE_FEATURES = (
    "Shipping Mode",
    "Days for shipment (scheduled)",
    "Order Region",
    "Market",
    "Order Country",
    "Category Name",
    "Department Name",
    "Product Name",
    "Customer Segment",
    "Order Item Quantity",
    "Order Item Product Price",
    "Product Price",
    "Sales",
    "Sales per customer",
    "Order Item Total",
    "Order Item Discount",
    "Order Item Discount Rate",
    "order date (DateOrders)",
)

# Delivery Status value the plan removes from the KPI denominator.
# A cancel is not an on-time delivery and not a late delivery.
CANCELED = "Shipping canceled"

# Columns that must be constant inside an Order Id before we refuse to
# publish a second, order-level KPI. If any of these vary, line grain and
# order grain answer different questions and both have to be shown.
WITHIN_ORDER_COLUMNS = (
    "Shipping Mode",
    "Late_delivery_risk",
    "Days for shipping (real)",
    "Days for shipment (scheduled)",
    "Delivery Status",
)


def load_raw(path: Path) -> pd.DataFrame:
    """Read the order-line file as Latin-1 and refuse a different shape.

    UTF-8 is tried first only to prove it is the wrong codec. The bytes
    include Latin-1 characters (accents in city and product names). A UTF-8
    read fails, which is why the data note specifies latin-1. The frame
    that is analyzed is the Latin-1 read, not a replacement encoding.
    """
    if path.name != "DataCoSupplyChainDataset.csv":
        raise SystemExit(f"refusing to read {path.name}")
    if "tokenized_access_logs" in str(path):
        raise SystemExit("access logs are out of scope")
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

    df = pd.read_csv(path, encoding="latin-1")
    if df.shape != (EXPECTED_ROWS, EXPECTED_COLS):
        raise SystemExit(f"shape changed: {df.shape}")
    missing = [c for c in WITHIN_ORDER_COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(f"missing columns: {missing}")
    return df


def exact_median(series: pd.Series) -> int:
    """Median only when the two central observations are the same day.

    With an even count, the usual median averages the two middle values.
    Averaging day 1 and day 2 into 1.5 would be a number no shipment took.
    This file's published groups do not do that. If a future extract does,
    stop rather than print a half-day as if it were the typical shipment.
    """
    values = np.sort(series.to_numpy())
    n = len(values)
    if n == 0:
        raise SystemExit("median of an empty group")
    if n % 2 == 1:
        low = high = values[n // 2]
    else:
        low = values[n // 2 - 1]
        high = values[n // 2]
    if low != high:
        raise SystemExit(
            f"median would average {int(low)} and {int(high)}; not hiding that"
        )
    return int(low)


def rate_table(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Late rate, line count, and slip for one cut of the KPI population.

    lines is the denominator. late_lines is the numerator. The rate without
    the count is how a small category gets mistaken for a driver. Sorted by
    rate descending, then by lines descending, so ties show the larger group
    first. Median slip is exact_median: both middle values are the same day.
    """
    rows = []
    for name, sub in df.groupby(group_col, sort=False, dropna=False):
        slip = sub["slip"]
        lead = sub["Days for shipping (real)"]
        lines = int(len(sub))
        late_lines = int(sub["Late_delivery_risk"].sum())
        slip_sum = int(slip.sum())
        lead_sum = int(lead.sum())
        rows.append(
            {
                group_col: name,
                "lines": lines,
                "late_lines": late_lines,
                "on_time_lines": lines - late_lines,
                "late_rate": late_lines / lines,
                "median_slip": exact_median(slip),
                "mean_slip": slip_sum / lines,
                "slip_sum": slip_sum,
                "median_lead": exact_median(lead),
                "mean_lead": lead_sum / lines,
                "lead_sum": lead_sum,
            }
        )
    out = pd.DataFrame(rows)
    out = out.sort_values(
        ["late_rate", "lines", group_col], ascending=[False, False, True]
    ).reset_index(drop=True)
    return out


def order_constancy(df: pd.DataFrame) -> pd.DataFrame:
    """Whether the shipping outcome is one fact per order or one per line.

    The flag is stored on the line. If two lines on the same Order Id
    disagreed, an order-level late rate would need a rule this stage does
    not invent. nunique > 1 is that disagreement.
    """
    nunique = df.groupby("Order Id")[list(WITHIN_ORDER_COLUMNS)].nunique()
    lines_per_order = df.groupby("Order Id").size()
    row = {
        "rows": int(len(df)),
        "distinct_order_id": int(df["Order Id"].nunique()),
        "distinct_order_item_id": int(df["Order Item Id"].nunique()),
        "duplicate_order_item_id": int(df["Order Item Id"].duplicated().sum()),
        "min_lines_per_order": int(lines_per_order.min()),
        "max_lines_per_order": int(lines_per_order.max()),
    }
    for col in WITHIN_ORDER_COLUMNS:
        row[f"orders_where_{col}_varies"] = int((nunique[col] > 1).sum())
    return pd.DataFrame([row])


def lines_per_order_table(df: pd.DataFrame) -> pd.DataFrame:
    """How many orders have 1 line, 2 lines, and so on. Counts only."""
    sizes = df.groupby("Order Id").size()
    counts = sizes.value_counts().sort_index()
    out = pd.DataFrame(
        {"lines_on_the_order": counts.index.astype(int), "orders": counts.to_numpy()}
    )
    out["line_rows"] = out["lines_on_the_order"] * out["orders"]
    return out


def day_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Every combination of status, mode, flag, and the day comparison.

    slip > 0 is the day-rule for late. A row is a disagreement when the
    flag and that rule differ. The table keeps the agreeing patterns too,
    including Advance shipping (slip negative, flag 0) and Shipping on time
    (slip 0, flag 0), so a canceled disagreement is not the only pattern
    a reader can see. Counts must sum to the file.
    """
    work = df.copy()
    work["real_exceeds_scheduled"] = (work["slip"] > 0).astype(int)
    work["flag_matches_day_rule"] = (
        work["Late_delivery_risk"] == work["real_exceeds_scheduled"]
    ).astype(int)
    grouped = (
        work.groupby(
            [
                "Delivery Status",
                "Shipping Mode",
                "Late_delivery_risk",
                "Days for shipping (real)",
                "Days for shipment (scheduled)",
                "slip",
                "real_exceeds_scheduled",
                "flag_matches_day_rule",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="lines")
    )
    grouped = grouped.sort_values(
        ["flag_matches_day_rule", "Delivery Status", "Shipping Mode", "slip", "lines"],
        ascending=[True, True, True, True, False],
    ).reset_index(drop=True)
    if int(grouped["lines"].sum()) != len(df):
        raise SystemExit("day-pattern counts do not cover every line")
    return grouped


def kpi_population(df: pd.DataFrame) -> pd.DataFrame:
    """Non-canceled lines. This is the only population a late rate is for.

    The plan fixed the denominator before this script ran: drop Shipping
    canceled. The all-lines share is written beside it, labeled not_the_kpi,
    so a 54% figure from a notebook that left cancels in is not silently
    reused. It is not the rate this project states.
    """
    rows = []
    for label, sub in (
        ("kpi_non_canceled_lines", df[df["Delivery Status"] != CANCELED]),
        ("not_the_kpi_all_lines", df),
    ):
        lines = int(len(sub))
        late_lines = int(sub["Late_delivery_risk"].sum())
        slip = sub["slip"]
        lead = sub["Days for shipping (real)"]
        rows.append(
            {
                "population": label,
                "lines": lines,
                "late_lines": late_lines,
                "on_time_lines": lines - late_lines,
                "late_rate": late_lines / lines,
                "on_time_rate": (lines - late_lines) / lines,
                "median_lead": exact_median(lead),
                "mean_lead": int(lead.sum()) / lines,
                "lead_sum": int(lead.sum()),
                "median_slip": exact_median(slip),
                "mean_slip": int(slip.sum()) / lines,
                "slip_sum": int(slip.sum()),
            }
        )
    return pd.DataFrame(rows)


def order_grain_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    """Unweighted order rate, computed only to show we are not hiding it.

    Lines do not disagree inside an order, so the plan does not ask for a
    second KPI. The order rate still differs in principle, because a 5-line
    order counts once here and five times at line grain. One row per order
    uses the constant flag. Canceled orders are out, for the same reason
    canceled lines are out.
    """
    orders = (
        df.groupby("Order Id", sort=False)
        .agg(
            delivery_status=("Delivery Status", "first"),
            late_delivery_risk=("Late_delivery_risk", "first"),
            lines=("Order Item Id", "size"),
        )
        .reset_index()
    )
    # first() is safe only because constancy was already required.
    kpi_orders = orders[orders["delivery_status"] != CANCELED]
    lines = int(len(kpi_orders))
    late_lines = int(kpi_orders["late_delivery_risk"].sum())
    return pd.DataFrame(
        [
            {
                "population": "sensitivity_non_canceled_orders_not_the_kpi",
                "orders": lines,
                "late_orders": late_lines,
                "on_time_orders": lines - late_lines,
                "late_rate": late_lines / lines,
                "why_not_the_kpi": (
                    "lines inside an Order Id do not disagree on the flag; "
                    "the published KPI stays at line grain"
                ),
            }
        ]
    )


def null_table(df: pd.DataFrame) -> pd.DataFrame:
    """Null count for every column. Candidate features are flagged.

    A null on a candidate feature would have to be handled before a model.
    A null on a personal-data column is not a modeling problem because that
    column is not a feature. Product Description is entirely empty; it is
    not on the candidate list.
    """
    rows = []
    n = len(df)
    for col in df.columns:
        nulls = int(df[col].isna().sum())
        rows.append(
            {
                "column_name": col,
                "null_count": nulls,
                "null_share": nulls / n,
                "distinct_non_null": int(df[col].nunique(dropna=True)),
                "is_candidate_feature": int(col in CANDIDATE_FEATURES),
                "is_personal_data": int(col in PII_COLUMNS),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["null_count", "column_name"], ascending=[False, True]
    ).reset_index(drop=True)


def cardinality_table(df: pd.DataFrame) -> pd.DataFrame:
    """Distinct levels for the cuts Construct might one-hot.

    Order City and Order State are in this table because a one-hot of
    thousands of levels memorizes rare places. The count is the warning.
    The level names are not written for city and state; only the number.
    """
    columns = [
        "Order Region",
        "Market",
        "Category Name",
        "Department Name",
        "Product Name",
        "Order Country",
        "Order City",
        "Order State",
        "Customer Segment",
        "Shipping Mode",
        "Delivery Status",
        "Order Status",
    ]
    rows = []
    for col in columns:
        rows.append(
            {
                "column_name": col,
                "distinct_values": int(df[col].nunique(dropna=False)),
            }
        )
    return pd.DataFrame(rows)


def high_cardinality_tails(df: pd.DataFrame) -> pd.DataFrame:
    """How many levels are rare. One-hot treats a 1-line city as a feature.

    Computed on all lines, which is the column Construct would encode if it
    ignored the cancel filter. distinct_values matches cardinality_table.
    """
    rows = []
    for col in ("Product Name", "Order Country", "Order City", "Order State"):
        sizes = df.groupby(col, dropna=False).size()
        # The two central levels can have different line counts. Report both.
        # Averaging them would invent a level size no name actually has.
        ordered = np.sort(sizes.to_numpy())
        n_levels = len(ordered)
        if n_levels % 2 == 1:
            med_low = med_high = int(ordered[n_levels // 2])
        else:
            med_low = int(ordered[n_levels // 2 - 1])
            med_high = int(ordered[n_levels // 2])
        rows.append(
            {
                "column_name": col,
                "distinct_values": int(n_levels),
                "min_lines": int(sizes.min()),
                "median_lines_low": med_low,
                "median_lines_high": med_high,
                "max_lines": int(sizes.max()),
                "levels_with_1_line": int((sizes == 1).sum()),
                "levels_with_under_30_lines": int((sizes < 30).sum()),
            }
        )
    return pd.DataFrame(rows)


def whitespace_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Labels whose stored spelling has a trailing or doubled space.

    Stripping does not merge two different names in this file: the distinct
    count after a strip-and-collapse equals the raw distinct count. The
    strings still have to be kept as stored, or a dashboard filter will
    miss them. The table lists the raw spelling and the line count.
    """
    rows = []
    for col in ("Category Name", "Department Name", "Order Region", "Product Name"):
        raw_n = int(df[col].nunique())
        normalized = df[col].str.strip().str.replace(r"\s+", " ", regex=True)
        if int(normalized.nunique()) != raw_n:
            raise SystemExit(f"normalizing {col} would merge levels")
        for value, n in df[col].value_counts().items():
            if value != value.strip() or "  " in value:
                rows.append(
                    {
                        "column_name": col,
                        "stored_value": value,
                        "lines": int(n),
                        "normalized_distinct_equals_raw": 1,
                    }
                )
    return pd.DataFrame(rows)


def hierarchy_exceptions(df: pd.DataFrame) -> pd.DataFrame:
    """Places where a name is not a one-to-one parent of the finer id.

    Category Name is the feature the plan allows. It is not a clean child
    of Department Name: Electronics is two category ids in two departments.
    Encoding the name glues those together. Encoding the id splits them.
    Regions do not cross markets. The one country that covers several
    regions is listed so Order Country is not treated as a region rename.
    """
    rows = []
    cat = (
        df.groupby(["Category Name", "Category Id", "Department Name"], dropna=False)
        .size()
        .reset_index(name="lines")
    )
    multi = cat.groupby("Category Name")["Department Name"].nunique()
    multi_names = multi[multi > 1].index
    for _, rec in cat[cat["Category Name"].isin(multi_names)].iterrows():
        rows.append(
            {
                "check": "category_name_in_more_than_one_department",
                "name": rec["Category Name"],
                "category_id": int(rec["Category Id"]),
                "parent": rec["Department Name"],
                "lines_all_rows": int(rec["lines"]),
            }
        )
    country = (
        df.groupby(["Order Country", "Order Region", "Market"], dropna=False)
        .size()
        .reset_index(name="lines")
    )
    multi_c = country.groupby("Order Country")["Order Region"].nunique()
    multi_countries = multi_c[multi_c > 1].index
    for _, rec in country[country["Order Country"].isin(multi_countries)].iterrows():
        rows.append(
            {
                "check": "order_country_in_more_than_one_region",
                "name": rec["Order Country"],
                "category_id": pd.NA,
                "parent": f"{rec['Order Region']} | {rec['Market']}",
                "lines_all_rows": int(rec["lines"]),
            }
        )
    regions_crossing = int((df.groupby("Order Region")["Market"].nunique() > 1).sum())
    if regions_crossing != 0:
        raise SystemExit("an Order Region sits in more than one Market")
    return pd.DataFrame(rows)


def mode_schedule_map(df: pd.DataFrame) -> pd.DataFrame:
    """Scheduled days against Shipping Mode, on every line.

    The promise is known at order time, canceled or not, so the map is
    checked on the full file. One scheduled value per mode means the two
    columns are the same fact written twice. A model that takes both
    double-counts the promise.
    """
    grouped = (
        df.groupby(["Shipping Mode", "Days for shipment (scheduled)"], dropna=False)
        .size()
        .reset_index(name="lines")
        .sort_values("Days for shipment (scheduled)")
        .reset_index(drop=True)
    )
    if grouped["Shipping Mode"].duplicated().any():
        raise SystemExit("Shipping Mode is not a one-to-one relabeling of scheduled days")
    if grouped["Days for shipment (scheduled)"].duplicated().any():
        raise SystemExit("two modes share one scheduled-day value")
    return grouped


def real_days_by_mode(kpi: pd.DataFrame) -> pd.DataFrame:
    """Actual days inside each mode, on the KPI population only.

    The late rate by mode is a consequence of this grid: the promise is a
    single scheduled value, and real days only take a few integers. First
    Class has nowhere to land except past its promise if real days are
    always 2 and the promise is 1. That is a description of this file, not
    a claim that a faster carrier would not help.
    """
    grouped = (
        kpi.groupby(
            [
                "Shipping Mode",
                "Days for shipment (scheduled)",
                "Days for shipping (real)",
                "Delivery Status",
                "Late_delivery_risk",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="lines")
    )
    grouped["slip"] = (
        grouped["Days for shipping (real)"] - grouped["Days for shipment (scheduled)"]
    )
    return grouped.sort_values(
        ["Days for shipment (scheduled)", "Days for shipping (real)", "Delivery Status"]
    ).reset_index(drop=True)


def mode_market_table_region(kpi: pd.DataFrame) -> pd.DataFrame:
    """Late rate by mode inside region. Same grain as the market cross-tab.

    Kept so the worst and best regions can be opened by mode without a
    second pass over the raw file. 23 x 4 is still an aggregate.
    """
    rows = []
    for (region, mode), sub in kpi.groupby(["Order Region", "Shipping Mode"], sort=False):
        lines = int(len(sub))
        late_lines = int(sub["Late_delivery_risk"].sum())
        rows.append(
            {
                "Order Region": region,
                "Market": sub["Market"].iloc[0],
                "Shipping Mode": mode,
                "lines": lines,
                "late_lines": late_lines,
                "late_rate": late_lines / lines,
                "median_slip": exact_median(sub["slip"]),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["Order Region", "Shipping Mode"], ascending=[True, True]
    ).reset_index(drop=True)


def mode_market_table(kpi: pd.DataFrame) -> pd.DataFrame:
    """Late rate by mode inside market. The mix check the plan asked for.

    If market only looked different because it used a different mode mix,
    the rate inside a mode would be flat across markets. A remaining gap
    is descriptive. It is not a causal effect of the market.
    """
    rows = []
    for (market, mode), sub in kpi.groupby(["Market", "Shipping Mode"], sort=False):
        lines = int(len(sub))
        late_lines = int(sub["Late_delivery_risk"].sum())
        rows.append(
            {
                "Market": market,
                "Shipping Mode": mode,
                "lines": lines,
                "late_lines": late_lines,
                "late_rate": late_lines / lines,
                "median_slip": exact_median(sub["slip"]),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["Shipping Mode", "late_rate", "lines"], ascending=[True, False, False]
    ).reset_index(drop=True)


def region_mix_gap(kpi: pd.DataFrame, by_mode: pd.DataFrame) -> pd.DataFrame:
    """Actual region late rate minus the rate its mode mix would imply.

    Expected rate = sum over modes of (this region's share of that mode
    times the overall late rate of that mode). The overall mode rate
    includes the region, so this is not a held-out adjustment. It answers
    only whether the region ranking is the mode mix in disguise. A large
    gap on a small region is still a small region.
    """
    overall = by_mode.set_index("Shipping Mode")["late_rate"]
    rows = []
    for region, sub in kpi.groupby("Order Region", sort=False):
        lines = int(len(sub))
        late_lines = int(sub["Late_delivery_risk"].sum())
        shares = sub.groupby("Shipping Mode").size()
        expected = 0.0
        for mode, n_mode in shares.items():
            expected += (int(n_mode) / lines) * float(overall.loc[mode])
        actual = late_lines / lines
        market = sub["Market"].iloc[0]
        rows.append(
            {
                "Order Region": region,
                "Market": market,
                "lines": lines,
                "late_lines": late_lines,
                "late_rate": actual,
                "rate_implied_by_mode_mix": expected,
                "gap_actual_minus_implied": actual - expected,
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["late_rate", "lines"], ascending=[False, False]
    ).reset_index(drop=True)


def shipping_date_check(df: pd.DataFrame) -> pd.DataFrame:
    """Prove which date is the outcome clock before either date is a feature.

    The plan allows calendar parts of the order date and forbids the
    shipping date if that date is when the goods actually moved. The
    calendar-day gap (date part, not a 24-hour truncation) equals Days for
    shipping (real) on every row, and the shipping timestamp is never
    before the order timestamp. That is the outcome field. A 24-hour
    truncation does not match, because some 1-day shipments cross midnight
    in under 24 hours. The match that matters is the calendar day, which
    is how the real-days column is built.
    """
    order_dt = pd.to_datetime(
        df["order date (DateOrders)"], format="%m/%d/%Y %H:%M"
    )
    ship_dt = pd.to_datetime(
        df["shipping date (DateOrders)"], format="%m/%d/%Y %H:%M"
    )
    # Month/day order is forced by the format. The first number never
    # exceeds 12 and the second number often exceeds 12, which is why
    # day-first parsing would be wrong. The format string records that.
    calendar_days = (ship_dt.dt.normalize() - order_dt.dt.normalize()).dt.days
    clock_days = (ship_dt - order_dt).dt.days
    match_calendar = int((calendar_days == df["Days for shipping (real)"]).sum())
    match_clock = int((clock_days == df["Days for shipping (real)"]).sum())
    if match_calendar != len(df):
        raise SystemExit("shipping date is not the real-days clock")
    if int((ship_dt < order_dt).sum()) != 0:
        raise SystemExit("shipping timestamp precedes the order timestamp")
    summary = pd.DataFrame(
        [
            {
                "rows": int(len(df)),
                "order_date_min": str(order_dt.min()),
                "order_date_max": str(order_dt.max()),
                "shipping_date_min": str(ship_dt.min()),
                "shipping_date_max": str(ship_dt.max()),
                "calendar_day_gap_equals_real_days": match_calendar,
                "truncated_24h_gap_equals_real_days": match_clock,
                "shipping_before_order": 0,
            }
        ]
    )
    # The rows the 24-hour truncation misses. Kept as a count by the two
    # day values, not as timestamps, so the file stays an aggregate.
    mismatch = pd.DataFrame(
        {
            "truncated_24h_gap": clock_days.to_numpy(),
            "real_days": df["Days for shipping (real)"].to_numpy(),
        }
    )
    mismatch = mismatch.loc[
        mismatch["truncated_24h_gap"] != mismatch["real_days"]
    ]
    mismatch_counts = (
        mismatch.groupby(["truncated_24h_gap", "real_days"], dropna=False)
        .size()
        .reset_index(name="lines")
    )
    return summary, mismatch_counts


def canceled_vs_order_status(df: pd.DataFrame) -> pd.DataFrame:
    """Which Order Status values are the Shipping canceled lines.

    The KPI filter is Delivery Status, not Order Status. This table shows
    they are the same lines: the canceled delivery status is exactly two
    order statuses, and those statuses have no other delivery status.
    """
    ct = pd.crosstab(df["Order Status"], df["Delivery Status"])
    ct.index.name = "order_status"
    return ct.reset_index()


def save_csv(df: pd.DataFrame, name: str) -> Path:
    """Write one aggregate CSV and refuse personal-data column names."""
    blocked = set(PII_COLUMNS) | set(LOCATION_COLUMNS)
    hit = blocked.intersection(df.columns)
    if hit:
        raise SystemExit(f"{name} would write personal data columns: {sorted(hit)}")
    # No frame in this script is row-level. A row count near the raw file
    # size means a filter was forgotten and the line extract leaked.
    if len(df) > 5000:
        raise SystemExit(f"{name} has {len(df)} rows; refusing a line-level extract")
    path = PROC / name
    df.to_csv(path, index=False)
    return path


def save_charts(by_mode: pd.DataFrame, days: pd.DataFrame, overall_rate: float) -> None:
    """Two charts. The rate chart is the scorecard. The days chart is why.

    Default matplotlib colors. No theme. The rate sort is the business
    sort (worst promise first). The days chart is in promise order
    (Same Day, First, Second, Standard) so the scheduled day and the
    actual days can be read together.
    """
    IMG.mkdir(parents=True, exist_ok=True)

    plot = by_mode.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.barh(plot["Shipping Mode"], plot["late_rate"], color="#4C78A8")
    # The line is the KPI rate. The legend does not round it to 3 decimals,
    # which would print 0.573 for a rate whose next digit is 2.
    ax.axvline(
        overall_rate,
        color="#333333",
        linestyle="--",
        linewidth=1,
        label="all non-canceled lines",
    )
    for i, rec in enumerate(plot.itertuples(index=False)):
        ax.text(
            rec.late_rate + 0.02,
            i,
            f"{rec.late_lines:,} / {rec.lines:,}",
            va="center",
            fontsize=9,
        )
    ax.set_xlim(0, 1.38)
    ax.set_xlabel("Late rate")
    ax.set_title("Late rate by shipping mode, non-canceled lines")
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(IMG / "late_rate_by_shipping_mode.png", dpi=120)
    plt.close(fig)

    order = ["Same Day", "First Class", "Second Class", "Standard Class"]
    counts = (
        days.groupby(["Shipping Mode", "Days for shipping (real)"], sort=False)["lines"]
        .sum()
        .unstack("Shipping Mode")
        .reindex(columns=order)
        .fillna(0)
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    x = np.arange(len(counts.index))
    width = 0.18
    for i, mode in enumerate(order):
        ax.bar(x + (i - 1.5) * width, counts[mode].to_numpy(), width=width, label=mode)
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(v)) for v in counts.index])
    ax.set_xlabel("Days for shipping (real)")
    ax.set_ylabel("Lines")
    ax.set_title("Actual shipping days by mode, non-canceled lines")
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(IMG / "real_days_by_shipping_mode.png", dpi=120)
    plt.close(fig)


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    df = load_raw(RAW)
    df["slip"] = df["Days for shipping (real)"] - df["Days for shipment (scheduled)"]

    constancy = order_constancy(df)
    vary_cols = [c for c in constancy.columns if c.startswith("orders_where_")]
    if int(constancy[vary_cols].to_numpy().sum()) != 0:
        raise SystemExit("lines inside an order disagree; order grain is required")

    kpi = df[df["Delivery Status"] != CANCELED].copy()
    # The day-rule and the flag are allowed to disagree on canceled lines.
    # On the KPI population they must agree, or the target decision stops.
    day_late = (kpi["slip"] > 0).astype(int)
    disagreements_in_kpi = int((kpi["Late_delivery_risk"] != day_late).sum())
    if disagreements_in_kpi != 0:
        raise SystemExit(
            "flag and real>scheduled disagree on non-canceled lines; "
            "do not fit a model until the target is rewritten"
        )

    ship_summary, ship_mismatch = shipping_date_check(df)
    by_mode = rate_table(kpi, "Shipping Mode")
    by_region = rate_table(kpi, "Order Region")
    by_market = rate_table(kpi, "Market")
    by_category = rate_table(kpi, "Category Name")
    by_department = rate_table(kpi, "Department Name")
    overall = kpi_population(df)
    kpi_row = overall.loc[overall["population"] == "kpi_non_canceled_lines"].iloc[0]

    written = [
        save_csv(constancy, "order_id_constancy.csv"),
        save_csv(lines_per_order_table(df), "lines_per_order.csv"),
        save_csv(day_patterns(df), "flag_vs_day_patterns.csv"),
        save_csv(overall, "kpi_overall.csv"),
        save_csv(order_grain_sensitivity(df), "order_grain_sensitivity.csv"),
        save_csv(by_mode, "late_rate_by_shipping_mode.csv"),
        save_csv(by_region, "late_rate_by_order_region.csv"),
        save_csv(by_market, "late_rate_by_market.csv"),
        save_csv(by_category, "late_rate_by_category.csv"),
        save_csv(by_department, "late_rate_by_department.csv"),
        save_csv(mode_market_table(kpi), "late_rate_by_mode_and_market.csv"),
        save_csv(mode_market_table_region(kpi), "late_rate_by_mode_and_region.csv"),
        save_csv(region_mix_gap(kpi, by_mode), "region_rate_vs_mode_mix.csv"),
        save_csv(real_days_by_mode(kpi), "real_days_by_shipping_mode.csv"),
        save_csv(mode_schedule_map(df), "scheduled_days_by_shipping_mode.csv"),
        save_csv(null_table(df.drop(columns=["slip"])), "null_counts.csv"),
        save_csv(cardinality_table(df), "cardinality.csv"),
        save_csv(high_cardinality_tails(df), "high_cardinality_tails.csv"),
        save_csv(whitespace_labels(df), "whitespace_labels.csv"),
        save_csv(hierarchy_exceptions(df), "label_hierarchy_exceptions.csv"),
        save_csv(ship_summary, "shipping_date_check.csv"),
        save_csv(ship_mismatch, "shipping_date_clock_mismatch.csv"),
        save_csv(canceled_vs_order_status(df), "order_status_by_delivery_status.csv"),
    ]
    save_charts(by_mode, real_days_by_mode(kpi), float(kpi_row["late_rate"]))

    # Re-read headers. The check is on what landed on disk, not on the frames.
    for path in written:
        header = path.read_text(encoding="utf-8").splitlines()[0]
        for banned in PII_COLUMNS:
            if banned in header:
                raise SystemExit(f"{path.name} header contains {banned}")

    late = int(kpi_row["late_lines"])
    lines = int(kpi_row["lines"])
    # df gained a slip column in memory. The file check is the 53-column read.
    print(
        "confirmation "
        f"rows={EXPECTED_ROWS} cols={EXPECTED_COLS} encoding=latin-1 "
        f"kpi_late={late}/{lines} "
        f"files={len(written)} charts=2"
    )
    print(f"processed_dir={PROC}")
    print(f"images_dir={IMG}")


if __name__ == "__main__":
    main()
