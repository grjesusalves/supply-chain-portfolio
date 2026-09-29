#!/usr/bin/env python3
"""Analyze stage: describe California unit sales before any forecast is fit.

This script does not train a model, tune a parameter, or score a forecast.
It checks the California slice of the M5 files and writes small tables and charts
so the Construct stage knows what it is walking into.

Run from anywhere:
    python 01-demand-forecasting/src/analyze_ca.py

Inputs (git-ignored, already downloaded):
    data/raw/sales_train_evaluation.csv
    data/raw/sales_train_validation.csv
    data/raw/calendar.csv
    data/raw/sell_prices.csv

Outputs:
    data/processed/*.csv   small summary tables
    images/*.png           charts
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save files; do not open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Paths are anchored to this file so the script works no matter the shell cwd.
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
IMG = ROOT / "images"

# Plan scope: the four California stores only. No Texas, no Wisconsin.
CA_STORES = ["CA_1", "CA_2", "CA_3", "CA_4"]

# Walmart's week starts on Saturday (wday 1), not Monday.
WEEKDAY_ORDER = [
    "Saturday",
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
]


def day_number(column_name: str) -> int:
    """Turn a sales column name like 'd_1941' into the integer 1941."""
    return int(column_name.split("_")[1])


def load_calendar() -> pd.DataFrame:
    """One row per calendar date. This is how a 'd_123' column becomes a real day."""
    calendar = pd.read_csv(RAW / "calendar.csv")
    calendar["date"] = pd.to_datetime(calendar["date"])
    # Empty event cells are missing, not a blank string. Treat "no event" as blank
    # so later filters do not have to special-case NaN.
    for column in ["event_name_1", "event_type_1", "event_name_2", "event_type_2"]:
        calendar[column] = calendar[column].fillna("")
    return calendar


def load_ca_sales(filename: str) -> pd.DataFrame:
    """Read one sales file and keep only the four California stores.

    The file is wide: one row per item-store, one column per day. We read it in
    chunks so we can drop the other six stores before holding the whole frame.
    """
    path = RAW / filename
    pieces = []
    for chunk in pd.read_csv(path, chunksize=5_000):
        pieces.append(chunk[chunk["store_id"].isin(CA_STORES)])
    sales = pd.concat(pieces, ignore_index=True)
    if not sales["id"].is_unique:
        raise SystemExit(f"{filename}: duplicate id values inside the CA filter")
    return sales


def day_columns(frame: pd.DataFrame) -> list[str]:
    """Day columns in chronological order (d_1, d_2, ...), not alphabetical order."""
    columns = [c for c in frame.columns if c.startswith("d_")]
    return sorted(columns, key=day_number)


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Calendar, then the evaluation file (the one that includes the holdout).
    # ------------------------------------------------------------------
    print("Loading calendar...")
    calendar = load_calendar()

    print("Loading California rows from sales_train_evaluation...")
    sales = load_ca_sales("sales_train_evaluation.csv")
    days = day_columns(sales)

    # Every d_ column we are about to sum must exist on the calendar, or a
    # 'weekday' or 'snap' label would silently drop days.
    calendar_days = set(calendar["d"])
    missing_from_calendar = [c for c in days if c not in calendar_days]
    if missing_from_calendar:
        raise SystemExit(f"Calendar is missing day ids: {missing_from_calendar[:5]}")

    # Align the calendar to the sales columns, left to right, same order as `days`.
    day_meta = calendar.set_index("d").loc[days].reset_index()
    if len(day_meta) != len(days):
        raise SystemExit("Calendar alignment dropped days")

    n_series = len(sales)
    n_days = len(days)
    n_items = sales["item_id"].nunique()
    items_per_store = sales.groupby("store_id")["item_id"].nunique().sort_index()
    stores_seen = sorted(sales["store_id"].unique())
    states_seen = sorted(sales["state_id"].unique())

    # The numeric block is what we aggregate. int32 is enough for item-day units
    # and uses half the memory of pandas' default int64.
    units = sales[days].to_numpy(dtype=np.int32)
    if units.shape != (n_series, n_days):
        raise SystemExit(f"Unexpected units shape {units.shape}")

    missing_cells = int(np.isnan(sales[days].to_numpy(dtype=float)).sum())

    # ------------------------------------------------------------------
    # 1. Shape: how many series, which dates, how many zeros.
    # ------------------------------------------------------------------
    first_day = day_meta.iloc[0]
    last_day = day_meta.iloc[-1]
    # A zero cell is a day this item-store recorded 0 units. It is not the same
    # thing as a missing cell. M5 almost never leaves the cell blank.
    zero_cells = int((units == 0).sum())
    total_cells = int(units.size)
    zero_share = zero_cells / total_cells

    # A statewide closed day would be a date when all four stores sell nothing.
    # Count those separately so they are not read as ordinary zero demand.
    # Christmas is NOT that pattern here: two stores go to zero and the other
    # two record a handful of units. That check is saved on its own below.
    daily_total = units.sum(axis=0).astype(np.int64)
    closed_mask = daily_total == 0
    closed_dates = day_meta.loc[closed_mask, "date"]
    zero_cells_ex_closed = int((units[:, ~closed_mask] == 0).sum())
    cells_ex_closed = int(units[:, ~closed_mask].size)

    print(
        f"Series={n_series} items={n_items} days={n_days} "
        f"range={first_day['date'].date()}..{last_day['date'].date()} "
        f"missing={missing_cells} zero_share={zero_share:.6f}"
    )

    # ------------------------------------------------------------------
    # Validation file must tell the same history. The plan's train window is
    # d_1..d_1913. If the two files disagree, we would be mixing two histories.
    # ------------------------------------------------------------------
    print("Loading California rows from sales_train_validation for the overlap check...")
    validation = load_ca_sales("sales_train_validation.csv")
    val_days = [c for c in days if day_number(c) <= 1913]
    # The id column is not a join key across files: evaluation rows end in
    # "_evaluation" and validation rows end in "_validation". The item-store
    # pair is the same series in both files.
    key = ["item_id", "store_id"]
    if sales.duplicated(key).any() or validation.duplicated(key).any():
        raise SystemExit("item_id + store_id is not unique inside a CA sales file")
    eval_overlap = sales.set_index(key)[val_days].sort_index()
    val_overlap = validation.set_index(key)[val_days].sort_index()
    if not eval_overlap.index.equals(val_overlap.index):
        raise SystemExit("Validation and evaluation do not have the same CA item-store keys")
    mismatch_cells = int(
        (eval_overlap.to_numpy(dtype=np.int32) != val_overlap.to_numpy(dtype=np.int32)).sum()
    )
    print(f"Validation overlap mismatches: {mismatch_cells}")
    del validation, eval_overlap, val_overlap

    # ------------------------------------------------------------------
    # Per-series selling behavior. "Sells on a day" means units > 0.
    # Leading zeros (item not listed yet) are not the same as intermittent demand
    # after the item starts selling, so we measure both.
    # ------------------------------------------------------------------
    sold = units > 0
    days_with_sale = sold.sum(axis=1).astype(np.int32)
    # argmax on a boolean row returns the first True. All-zero rows also return 0,
    # so those series are handled on their own and not treated as "started on d_1".
    has_any_sale = days_with_sale > 0
    first_sale_index = np.where(has_any_sale, sold.argmax(axis=1), -1)
    leading_zero_cells = int(first_sale_index[has_any_sale].sum())
    all_zero_series = int((~has_any_sale).sum())

    # After the first positive day, how often does the series still sell?
    # Series that never sell stay in the "fewer than half" group.
    active_sale_rate = np.empty(n_series, dtype=np.float64)
    for i in range(n_series):
        start = first_sale_index[i]
        if start < 0:
            active_sale_rate[i] = 0.0
        else:
            active_sale_rate[i] = sold[i, start:].mean()
    full_sale_rate = days_with_sale / n_days

    cat = sales["cat_id"].to_numpy()
    dept = sales["dept_id"].to_numpy()
    store = sales["store_id"].to_numpy()

    def intermittency_table() -> pd.DataFrame:
        """Share of series that are positive on fewer than half of days."""
        rows = []

        def add_row(label_type: str, label: str, mask: np.ndarray) -> None:
            m = mask
            n = int(m.sum())
            rows.append(
                {
                    "slice_type": label_type,
                    "slice": label,
                    "n_series": n,
                    "series_positive_on_fewer_than_half_of_all_days": int(
                        (full_sale_rate[m] < 0.5).sum()
                    ),
                    "share_fewer_than_half_of_all_days": float((full_sale_rate[m] < 0.5).mean())
                    if n
                    else np.nan,
                    "series_positive_on_fewer_than_half_of_days_after_first_sale": int(
                        (active_sale_rate[m] < 0.5).sum()
                    ),
                    "share_fewer_than_half_after_first_sale": float(
                        (active_sale_rate[m] < 0.5).mean()
                    )
                    if n
                    else np.nan,
                    "all_zero_series": int((~has_any_sale[m]).sum()),
                    "median_share_of_days_with_a_sale": float(np.median(full_sale_rate[m]))
                    if n
                    else np.nan,
                    "median_share_of_days_with_a_sale_after_first_sale": float(
                        np.median(active_sale_rate[m])
                    )
                    if n
                    else np.nan,
                }
            )

        add_row("all", "CA", np.ones(n_series, dtype=bool))
        for name in sorted(pd.unique(cat)):
            add_row("category", name, cat == name)
        for name in CA_STORES:
            add_row("store", name, store == name)
        return pd.DataFrame(rows)

    intermittency = intermittency_table()

    # ------------------------------------------------------------------
    # Daily frame: one row per date, with the California total and labels we
    # need for weekday, month, SNAP, and the holdout.
    # ------------------------------------------------------------------
    daily = day_meta[
        ["d", "date", "wm_yr_wk", "weekday", "wday", "month", "year", "snap_CA",
         "event_name_1", "event_type_1", "event_name_2", "event_type_2"]
    ].copy()
    daily["total_units"] = daily_total
    daily["is_closed"] = closed_mask

    # Category totals per day, same column order as `days`.
    for category in ["FOODS", "HOBBIES", "HOUSEHOLD"]:
        daily[f"units_{category}"] = units[cat == category].sum(axis=0).astype(np.int64)

    # Store totals per day.
    for store_id in CA_STORES:
        daily[f"units_{store_id}"] = units[store == store_id].sum(axis=0).astype(np.int64)

    # ------------------------------------------------------------------
    # 2. Weekly seasonality. Average of the statewide daily total, by weekday.
    # Using the daily total (not the mean of a single item) is what a planner
    # sees: Saturday is a different day from Tuesday for the state as a whole.
    # ------------------------------------------------------------------
    weekday = (
        daily.groupby(["wday", "weekday"], as_index=False)
        .agg(
            n_days=("total_units", "size"),
            avg_daily_units=("total_units", "mean"),
            total_units=("total_units", "sum"),
        )
        .sort_values("wday")
    )
    # Christmas is a structural zero and it lands on whichever weekday Dec 25 was.
    # Show the same average with those closed days removed so one holiday does
    # not look like a weekday effect.
    open_days = daily.loc[~daily["is_closed"]]
    weekday_open = (
        open_days.groupby(["wday", "weekday"], as_index=False)
        .agg(
            n_open_days=("total_units", "size"),
            avg_daily_units_ex_closed=("total_units", "mean"),
        )
        .sort_values("wday")
    )
    weekday = weekday.merge(weekday_open, on=["wday", "weekday"])
    overall_avg = float(daily["total_units"].mean())
    weekday["vs_all_days_avg"] = weekday["avg_daily_units"] / overall_avg
    weekday["avg_units_per_series"] = weekday["avg_daily_units"] / n_series

    # Correlation of the statewide daily total with itself 7 and 28 days later.
    # This is a description of the series, not a fitted model. A high lag-7
    # correlation is the weekly repeat. Lag-28 should keep a lot of it because
    # 28 is exactly four weeks, so the weekday still matches.
    centered = daily_total.astype(np.float64)
    centered = centered - centered.mean()

    def lag_corr(lag: int) -> float:
        return float(np.corrcoef(centered[:-lag], centered[lag:])[0, 1])

    corr_lag_7 = lag_corr(7)
    corr_lag_28 = lag_corr(28)

    # ------------------------------------------------------------------
    # 3. Trend: month and Walmart week. Partial months (the history starts
    # Jan 29) must not be read as a demand crash, so we keep n_days and the
    # average per day next to the raw total.
    # ------------------------------------------------------------------
    daily["year_month"] = daily["date"].dt.to_period("M").astype(str)
    monthly = (
        daily.groupby("year_month", as_index=False)
        .agg(
            n_days=("total_units", "size"),
            total_units=("total_units", "sum"),
            avg_daily_units=("total_units", "mean"),
        )
    )
    annual = (
        daily.groupby("year", as_index=False)
        .agg(
            n_days=("total_units", "size"),
            total_units=("total_units", "sum"),
            avg_daily_units=("total_units", "mean"),
        )
    )

    weekly = (
        daily.groupby("wm_yr_wk", as_index=False)
        .agg(
            n_days=("total_units", "size"),
            week_start=("date", "min"),
            week_end=("date", "max"),
            total_units=("total_units", "sum"),
            avg_daily_units=("total_units", "mean"),
        )
    )
    weekly["complete_week"] = weekly["n_days"] == 7

    # When does each store actually start selling? A late open would look like
    # a level shift in the state total.
    store_start_rows = []
    for store_id in CA_STORES:
        column = f"units_{store_id}"
        positive = daily.loc[daily[column] > 0, "date"]
        store_start_rows.append(
            {
                "store_id": store_id,
                "first_positive_date": positive.min().date().isoformat(),
                "last_positive_date": positive.max().date().isoformat(),
                "zero_total_days": int((daily[column] == 0).sum()),
            }
        )
    store_start = pd.DataFrame(store_start_rows)

    # ------------------------------------------------------------------
    # 4. SNAP. snap_CA is a property of the date, not of the item.
    # Compare the average statewide daily total on snap days vs other days.
    # Then the same split inside each category: food should move, hobbies less.
    # ------------------------------------------------------------------
    def snap_block(frame: pd.DataFrame, value_column: str, slice_name: str) -> list[dict]:
        rows = []
        for snap_value, label in [(1, "snap"), (0, "non_snap")]:
            part = frame.loc[frame["snap_CA"] == snap_value, value_column]
            rows.append(
                {
                    "slice": slice_name,
                    "snap": label,
                    "n_days": int(part.shape[0]),
                    "avg_daily_units": float(part.mean()),
                    "total_units": int(part.sum()),
                }
            )
        snap_avg = rows[0]["avg_daily_units"]
        non_avg = rows[1]["avg_daily_units"]
        for row in rows:
            row["lift_vs_non_snap"] = snap_avg / non_avg - 1.0
        return rows

    snap_rows = []
    snap_rows.extend(snap_block(daily, "total_units", "CA_all"))
    for category in ["FOODS", "HOBBIES", "HOUSEHOLD"]:
        snap_rows.extend(snap_block(daily, f"units_{category}", category))
    # Closed days sit in the non-snap side (Christmas is not a SNAP day) and
    # pull that average down a little. Repeat the comparison without them.
    open_only = daily.loc[~daily["is_closed"]].copy()
    snap_rows.extend(snap_block(open_only, "total_units", "CA_all_ex_closed"))
    for category in ["FOODS", "HOBBIES", "HOUSEHOLD"]:
        snap_rows.extend(snap_block(open_only, f"units_{category}", f"{category}_ex_closed"))
    snap_table = pd.DataFrame(snap_rows)

    # Which calendar days of the month are SNAP in California? State the pattern
    # from the file rather than from memory of the program rules.
    daily["day_of_month"] = daily["date"].dt.day
    snap_by_dom = (
        daily.groupby("day_of_month", as_index=False)
        .agg(n_days=("snap_CA", "size"), n_snap=("snap_CA", "sum"))
    )
    snap_by_dom["snap_share"] = snap_by_dom["n_snap"] / snap_by_dom["n_days"]

    # ------------------------------------------------------------------
    # 5 and 6 and 7. Zeros, stores, categories, departments.
    # ------------------------------------------------------------------
    def zero_share_row(mask: np.ndarray, slice_type: str, slice_name: str) -> dict:
        block = units[mask]
        return {
            "slice_type": slice_type,
            "slice": slice_name,
            "n_series": int(mask.sum()),
            "n_cells": int(block.size),
            "zero_cells": int((block == 0).sum()),
            "zero_share": float((block == 0).mean()),
            "total_units": int(block.sum()),
        }

    zero_rows = [zero_share_row(np.ones(n_series, dtype=bool), "all", "CA")]
    for name in ["FOODS", "HOBBIES", "HOUSEHOLD"]:
        zero_rows.append(zero_share_row(cat == name, "category", name))
    for name in CA_STORES:
        zero_rows.append(zero_share_row(store == name, "store", name))
    for category in ["FOODS", "HOBBIES", "HOUSEHOLD"]:
        for store_id in CA_STORES:
            zero_rows.append(
                zero_share_row((cat == category) & (store == store_id), "category_store", f"{category}|{store_id}")
            )
    for name in sorted(pd.unique(dept)):
        zero_rows.append(zero_share_row(dept == name, "department", name))
    zero_table = pd.DataFrame(zero_rows)

    store_totals = (
        zero_table.loc[zero_table["slice_type"] == "store", ["slice", "n_series", "total_units", "zero_share"]]
        .rename(columns={"slice": "store_id"})
        .sort_values("store_id")
    )
    store_totals["share_of_ca_units"] = store_totals["total_units"] / store_totals["total_units"].sum()

    category_totals = (
        zero_table.loc[zero_table["slice_type"] == "category", ["slice", "n_series", "total_units", "zero_share"]]
        .rename(columns={"slice": "cat_id"})
        .sort_values("total_units", ascending=False)
    )
    category_totals["share_of_ca_units"] = (
        category_totals["total_units"] / category_totals["total_units"].sum()
    )

    dept_totals = (
        zero_table.loc[
            zero_table["slice_type"] == "department",
            ["slice", "n_series", "total_units", "zero_share"],
        ]
        .rename(columns={"slice": "dept_id"})
        .sort_values("total_units", ascending=False)
    )
    dept_totals["cat_id"] = dept_totals["dept_id"].str.split("_").str[0]
    dept_totals["share_of_ca_units"] = dept_totals["total_units"] / dept_totals["total_units"].sum()

    # ------------------------------------------------------------------
    # Holdout calendar check. The plan names d_1914..d_1941. Confirm the dates,
    # events, SNAP run, and which Walmart weeks are partial.
    # ------------------------------------------------------------------
    holdout = daily.loc[daily["d"].map(day_number).between(1914, 1941)].copy()
    if len(holdout) != 28:
        raise SystemExit(f"Expected 28 holdout days, found {len(holdout)}")
    holdout_weeks = (
        holdout.groupby("wm_yr_wk", as_index=False)
        .agg(n_days=("d", "size"), start=("date", "min"), end=("date", "max"))
    )
    holdout_weeks["partial"] = holdout_weeks["n_days"] < 7

    # ------------------------------------------------------------------
    # Excel pair and a worked lag-28 example.
    # The spreadsheet in Construct is one category at one store, summed to a
    # daily total, because an item-level series is mostly zeros and will not
    # show the weekly shape. Pick the highest-volume category, then the store
    # where that category sells the most units. That choice is frozen here.
    # ------------------------------------------------------------------
    top_category = str(category_totals.iloc[0]["cat_id"])
    cat_store = zero_table.loc[
        zero_table["slice"].str.startswith(top_category + "|")
    ].sort_values("total_units", ascending=False)
    excel_store = cat_store.iloc[0]["slice"].split("|")[1]
    excel_mask = (cat == top_category) & (store == excel_store)
    excel_daily = units[excel_mask].sum(axis=0).astype(np.int64)
    excel_zero_days = int((excel_daily == 0).sum())

    # Lag-28 worked example on one item-store inside that pair: the item that
    # sold the most units, so the copied week is not a string of zeros.
    # For holdout day d_t the seasonal naive is the actual on d_{t-28}.
    # d_1914 copies d_1886. d_1941 copies d_1913. All of those source days are
    # inside the training window (through d_1913). No test actual is used.
    item_units = units[excel_mask].sum(axis=1)
    excel_index = np.flatnonzero(excel_mask)
    example_pos = excel_index[int(np.argmax(item_units))]
    example_id = sales.iloc[example_pos]
    holdout_day_numbers = list(range(1914, 1942))
    example_rows = []
    series_units = units[example_pos]
    for day_n in holdout_day_numbers:
        source_n = day_n - 28
        example_rows.append(
            {
                "id": example_id["id"],
                "item_id": example_id["item_id"],
                "store_id": example_id["store_id"],
                "cat_id": example_id["cat_id"],
                "holdout_d": f"d_{day_n}",
                "holdout_date": day_meta.loc[days.index(f"d_{day_n}"), "date"].date().isoformat(),
                "actual_units": int(series_units[day_n - 1]),
                "lag28_source_d": f"d_{source_n}",
                "lag28_source_date": day_meta.loc[
                    days.index(f"d_{source_n}"), "date"
                ].date().isoformat(),
                "lag28_forecast_units": int(series_units[source_n - 1]),
            }
        )
    lag28_example = pd.DataFrame(example_rows)

    # ------------------------------------------------------------------
    # 8. Prices. Weekly, not daily. Join key is item_id + store_id + wm_yr_wk.
    # We only ask whether California is covered. We do not build a feature.
    # ------------------------------------------------------------------
    print("Loading California sell_prices...")
    price_pieces = []
    for chunk in pd.read_csv(RAW / "sell_prices.csv", chunksize=1_000_000):
        price_pieces.append(chunk[chunk["store_id"].isin(CA_STORES)])
    prices = pd.concat(price_pieces, ignore_index=True)
    prices["wm_yr_wk"] = prices["wm_yr_wk"].astype(np.int32)
    n_price_rows = len(prices)
    n_price_dup_keys = int(prices.duplicated(["store_id", "item_id", "wm_yr_wk"]).sum())
    n_null_price = int(prices["sell_price"].isna().sum())

    sales_weeks = np.sort(daily["wm_yr_wk"].unique().astype(np.int32))
    price_weeks = np.sort(prices["wm_yr_wk"].unique())

    series_keys = sales[["item_id", "store_id"]].drop_duplicates()
    price_span = (
        prices.groupby(["store_id", "item_id"], as_index=False)
        .agg(
            first_price_week=("wm_yr_wk", "min"),
            last_price_week=("wm_yr_wk", "max"),
            n_distinct_price_weeks=("wm_yr_wk", "nunique"),
        )
    )
    series_price = series_keys.merge(price_span, on=["store_id", "item_id"], how="left")
    n_series_with_no_price = int(series_price["first_price_week"].isna().sum())

    # Full grid: every CA item-store × every Walmart week that appears between
    # d_1 and d_1941. A missing cell can mean "not listed yet", "hole in the
    # middle", or "no row after the last posted price".
    week_frame = pd.DataFrame({"wm_yr_wk": sales_weeks})
    grid = series_keys.merge(week_frame, how="cross")
    price_keys = prices[["store_id", "item_id", "wm_yr_wk"]].drop_duplicates()
    grid = grid.merge(price_keys, on=["store_id", "item_id", "wm_yr_wk"], how="left", indicator=True)
    grid = grid.merge(series_price, on=["store_id", "item_id"], how="left")
    covered = grid["_merge"] == "both"
    never_listed = grid["first_price_week"].isna()
    before_first = (~never_listed) & (grid["wm_yr_wk"] < grid["first_price_week"])
    interior_hole = (
        (~covered)
        & (~never_listed)
        & (grid["wm_yr_wk"] >= grid["first_price_week"])
        & (grid["wm_yr_wk"] <= grid["last_price_week"])
    )
    after_last = (~covered) & (~never_listed) & (grid["wm_yr_wk"] > grid["last_price_week"])
    # Safety: the four missing buckets plus covered must account for every cell.
    accounted = int(covered.sum() + never_listed.sum() + before_first.sum() + interior_hole.sum() + after_last.sum())
    if accounted != len(grid):
        raise SystemExit(f"Price grid buckets do not add up: {accounted} vs {len(grid)}")

    # Weeks in the price file that are not between d_1 and d_1941. These are
    # the weeks after the history ends (the unpublished horizon), not holes.
    sales_week_set = set(sales_weeks.tolist())
    prices_outside_sales_weeks = int((~prices["wm_yr_wk"].isin(sales_week_set)).sum())

    # A price gap only matters if units were sold in it. Align each series' first
    # price week to its daily history and count units on earlier days.
    first_week_aligned = (
        sales[["store_id", "item_id"]]
        .merge(
            series_price[["store_id", "item_id", "first_price_week"]],
            on=["store_id", "item_id"],
            how="left",
        )["first_price_week"]
        .to_numpy()
    )
    if np.isnan(first_week_aligned.astype(float)).any():
        raise SystemExit("A CA series has no first price week; cannot compare sales to prices")
    first_week_aligned = first_week_aligned.astype(np.int32)
    before_price_days = day_meta["wm_yr_wk"].to_numpy(dtype=np.int32)[None, :] < first_week_aligned[:, None]
    units_before_first_price = int(units[before_price_days].sum())
    positive_cells_before_first_price = int(((units > 0) & before_price_days).sum())

    price_summary = pd.DataFrame(
        [
            {"metric": "ca_price_rows", "value": n_price_rows},
            {"metric": "duplicate_item_store_week_keys", "value": n_price_dup_keys},
            {"metric": "null_sell_price", "value": n_null_price},
            {"metric": "ca_stores_in_prices", "value": prices["store_id"].nunique()},
            {"metric": "price_week_min", "value": int(price_weeks.min())},
            {"metric": "price_week_max", "value": int(price_weeks.max())},
            {"metric": "sales_week_min", "value": int(sales_weeks.min())},
            {"metric": "sales_week_max", "value": int(sales_weeks.max())},
            {"metric": "n_sales_weeks", "value": int(len(sales_weeks))},
            {"metric": "item_store_series_with_no_price_row", "value": n_series_with_no_price},
            {"metric": "full_grid_cells", "value": int(len(grid))},
            {"metric": "full_grid_cells_with_price", "value": int(covered.sum())},
            {"metric": "full_grid_coverage", "value": float(covered.mean())},
            {"metric": "cells_item_never_listed", "value": int(never_listed.sum())},
            {"metric": "cells_before_first_price", "value": int(before_first.sum())},
            {"metric": "cells_interior_hole", "value": int(interior_hole.sum())},
            {"metric": "cells_after_last_price", "value": int(after_last.sum())},
            {"metric": "price_rows_whose_week_is_outside_sales_span", "value": prices_outside_sales_weeks},
            {"metric": "units_on_days_before_first_price", "value": units_before_first_price},
            {"metric": "positive_cells_before_first_price", "value": positive_cells_before_first_price},
        ]
    )
    # Keep integers as integers in the CSV. A mixed float column would print
    # 2708822 as 2.708822e+06 and a reader could not recover the count.
    def _metric_text(value):
        if isinstance(value, float) and not value.is_integer():
            return format(value, ".12g")
        return str(int(value))

    price_summary["value"] = price_summary["value"].map(_metric_text)

    # Release lag: share of series whose first price week is after the first sales week.
    listed = series_price.dropna(subset=["first_price_week"])
    n_listed_after_start = int((listed["first_price_week"] > int(sales_weeks.min())).sum())
    n_still_priced_at_end = int((listed["last_price_week"] >= int(sales_weeks.max())).sum())

    # ------------------------------------------------------------------
    # Key-value sheet used by the write-up. Every number in the report should
    # be traceable to this file or to one of the tables below.
    # ------------------------------------------------------------------
    ca_units = int(daily_total.sum())
    snap_all = snap_table.loc[snap_table["slice"] == "CA_all"].set_index("snap")
    shape_rows = [
        ("n_series", n_series),
        ("n_items", n_items),
        ("n_stores", len(stores_seen)),
        ("stores", ",".join(stores_seen)),
        ("states", ",".join(states_seen)),
        ("items_per_store_min", int(items_per_store.min())),
        ("items_per_store_max", int(items_per_store.max())),
        ("n_days", n_days),
        ("d_start", days[0]),
        ("d_end", days[-1]),
        ("date_start", first_day["date"].date().isoformat()),
        ("date_end", last_day["date"].date().isoformat()),
        ("weekday_start", first_day["weekday"]),
        ("weekday_end", last_day["weekday"]),
        ("missing_cells", missing_cells),
        ("total_cells", total_cells),
        ("zero_cells", zero_cells),
        ("zero_share", zero_share),
        ("closed_days", int(closed_mask.sum())),
        ("closed_dates", ",".join(d.date().isoformat() for d in closed_dates)),
        ("zero_share_ex_closed", zero_cells_ex_closed / cells_ex_closed),
        ("leading_zero_cells", leading_zero_cells),
        ("all_zero_series", all_zero_series),
        ("total_units", ca_units),
        ("avg_daily_units", float(daily_total.mean())),
        ("validation_overlap_mismatch_cells", mismatch_cells),
        ("corr_daily_total_lag_7", corr_lag_7),
        ("corr_daily_total_lag_28", corr_lag_28),
        ("snap_days", int(snap_all.loc["snap", "n_days"])),
        ("non_snap_days", int(snap_all.loc["non_snap", "n_days"])),
        ("snap_avg_daily_units", float(snap_all.loc["snap", "avg_daily_units"])),
        ("non_snap_avg_daily_units", float(snap_all.loc["non_snap", "avg_daily_units"])),
        ("snap_lift", float(snap_all.loc["snap", "lift_vs_non_snap"])),
        ("excel_category", top_category),
        ("excel_store", excel_store),
        ("excel_series_count", int(excel_mask.sum())),
        ("excel_total_units", int(excel_daily.sum())),
        ("excel_zero_aggregate_days", excel_zero_days),
        ("lag28_example_id", example_id["id"]),
        ("n_series_listed_after_first_sales_week", n_listed_after_start),
        ("n_series_with_price_covering_last_sales_week", n_still_priced_at_end),
        ("n_series_with_any_price", int(listed.shape[0])),
    ]
    # Per-store item counts, so the "same catalog" assumption is a number.
    for store_id, count in items_per_store.items():
        shape_rows.append((f"n_items_{store_id}", int(count)))

    shape = pd.DataFrame(shape_rows, columns=["metric", "value"])

    # ------------------------------------------------------------------
    # Save tables. These are small on purpose; the raw CSVs stay untracked.
    # ------------------------------------------------------------------
    shape.to_csv(PROC / "ca_shape_summary.csv", index=False)
    weekday.to_csv(PROC / "ca_weekday_avg.csv", index=False)
    monthly.to_csv(PROC / "ca_monthly_totals.csv", index=False)
    annual.to_csv(PROC / "ca_annual_totals.csv", index=False)
    weekly.to_csv(PROC / "ca_weekly_totals.csv", index=False)
    snap_table.to_csv(PROC / "ca_snap_comparison.csv", index=False)
    snap_by_dom.to_csv(PROC / "ca_snap_by_day_of_month.csv", index=False)
    intermittency.to_csv(PROC / "ca_intermittency.csv", index=False)
    store_totals.to_csv(PROC / "ca_store_totals.csv", index=False)
    category_totals.to_csv(PROC / "ca_category_totals.csv", index=False)
    dept_totals.to_csv(PROC / "ca_dept_totals.csv", index=False)
    zero_table.to_csv(PROC / "ca_zero_share.csv", index=False)
    price_summary.to_csv(PROC / "ca_price_coverage.csv", index=False)
    store_start.to_csv(PROC / "ca_store_start.csv", index=False)
    holdout[
        ["d", "date", "weekday", "wday", "wm_yr_wk", "snap_CA", "event_name_1", "event_name_2", "total_units"]
    ].to_csv(PROC / "ca_holdout_days.csv", index=False)
    holdout_weeks.to_csv(PROC / "ca_holdout_weeks.csv", index=False)
    lag28_example.to_csv(PROC / "ca_lag28_example.csv", index=False)
    # Christmas (Dec 25), not Orthodox Christmas. Store totals show the
    # near-shutdown: some stores hit 0, others record a handful of units.
    christmas = daily.loc[
        daily["event_name_1"].eq("Christmas") | daily["event_name_2"].eq("Christmas"),
        ["d", "date", "weekday", "total_units"] + [f"units_{s}" for s in CA_STORES],
    ].copy()
    christmas.to_csv(PROC / "ca_christmas_store_totals.csv", index=False)

    # ------------------------------------------------------------------
    # Charts. Four pictures, each answering one question from the tables.
    # ------------------------------------------------------------------
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 11,
        }
    )

    # 1. Weekday bars, Walmart week order (Saturday through Friday).
    fig, ax = plt.subplots(figsize=(8, 4.5))
    plot_wd = weekday.set_index("weekday").loc[WEEKDAY_ORDER]
    ax.bar(WEEKDAY_ORDER, plot_wd["avg_daily_units"] / 1000, color="#4C78A8")
    ax.set_ylabel("Average CA units per day (thousands)")
    ax.set_title("Weekend is high, midweek is low (Sunday peak, Wednesday trough)")
    ax.set_ylim(0, plot_wd["avg_daily_units"].max() / 1000 * 1.15)
    fig.tight_layout()
    fig.savefig(IMG / "ca_weekday_seasonality.png", dpi=120)
    plt.close(fig)

    # 2. Monthly average daily units, so a short month is not a fake dip.
    fig, ax = plt.subplots(figsize=(9, 4.5))
    month_x = pd.to_datetime(monthly["year_month"])
    ax.plot(month_x, monthly["avg_daily_units"] / 1000, color="#4C78A8", linewidth=1.6)
    ax.set_ylabel("Average CA units per day (thousands)")
    ax.set_title("Average daily units rose from 2011 to 2016, with a summer peak each year")
    ax.set_xlabel("Month")
    fig.tight_layout()
    fig.savefig(IMG / "ca_monthly_trend.png", dpi=120)
    plt.close(fig)

    # 3. SNAP vs non-SNAP average daily units, by category.
    fig, ax = plt.subplots(figsize=(8, 4.5))
    categories = ["FOODS", "HOUSEHOLD", "HOBBIES"]
    snap_means = []
    non_means = []
    for category in categories:
        part = snap_table.loc[snap_table["slice"] == category].set_index("snap")
        snap_means.append(part.loc["snap", "avg_daily_units"] / 1000)
        non_means.append(part.loc["non_snap", "avg_daily_units"] / 1000)
    x = np.arange(len(categories))
    width = 0.38
    ax.bar(x - width / 2, non_means, width, label="Non-SNAP day", color="#B0B0B0")
    ax.bar(x + width / 2, snap_means, width, label="SNAP day", color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel("Average units per day (thousands)")
    food_lift = float(snap_table.loc[snap_table["slice"] == "FOODS", "lift_vs_non_snap"].iloc[0])
    household_lift = float(
        snap_table.loc[snap_table["slice"] == "HOUSEHOLD", "lift_vs_non_snap"].iloc[0]
    )
    hobbies_lift = float(
        snap_table.loc[snap_table["slice"] == "HOBBIES", "lift_vs_non_snap"].iloc[0]
    )
    ax.set_title(
        f"SNAP lift: FOODS {food_lift:.1%}, HOUSEHOLD {household_lift:.1%}, HOBBIES {hobbies_lift:.1%}"
    )
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(IMG / "ca_snap_by_category.png", dpi=120)
    plt.close(fig)

    # 4. Where the units are: store and category.
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5))
    store_plot = store_totals.sort_values("store_id")
    axes[0].bar(store_plot["store_id"], store_plot["total_units"] / 1e6, color="#4C78A8")
    axes[0].set_ylabel("Total units, 2011–2016 (millions)")
    axes[0].set_title("Units by store")
    cat_plot = category_totals.sort_values("total_units", ascending=True)
    axes[1].barh(cat_plot["cat_id"], cat_plot["total_units"] / 1e6, color="#54A24B")
    axes[1].set_xlabel("Total units (millions)")
    axes[1].set_title("Units by category")
    fig.tight_layout()
    fig.savefig(IMG / "ca_volume_by_store_and_category.png", dpi=120)
    plt.close(fig)

    # Console recap so the write-up can be checked against a single run.
    print("--- ANNUAL ---")
    print(annual.to_string(index=False))
    print("--- WEEKDAY ---")
    print(weekday.to_string(index=False))
    print("--- SNAP ---")
    print(snap_table.to_string(index=False))
    print("--- INTERMITTENCY ---")
    print(intermittency.to_string(index=False))
    print("--- STORES ---")
    print(store_totals.to_string(index=False))
    print(store_start.to_string(index=False))
    print("--- CATEGORY ---")
    print(category_totals.to_string(index=False))
    print(dept_totals.to_string(index=False))
    print("--- PRICE ---")
    print(price_summary.to_string(index=False))
    print("--- HOLDOUT ---")
    print(holdout_weeks.to_string(index=False))
    print("holdout", holdout["date"].min().date(), holdout["date"].max().date())
    print("snap holdout days", int(holdout["snap_CA"].sum()))
    print("excel", top_category, excel_store, "zero aggregate days", excel_zero_days)
    print("example", example_id["id"])
    print("corr", corr_lag_7, corr_lag_28)
    print("Wrote tables to", PROC)
    print("Wrote charts to", IMG)


if __name__ == "__main__":
    main()
