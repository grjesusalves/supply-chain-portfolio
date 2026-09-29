#!/usr/bin/env python3
"""Analyze stage: ABC volume and forecast-error size for CA_3 FOODS.

This script describes the holdout. It does not compute a reorder point, a
safety stock, an order quantity, an EOQ, a Solver model, or a simulation.

Run from anywhere:
    python 02-inventory-optimization/src/analyze_inventory.py

Input (already in the repo, not a raw CSV):
    01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv

Outputs under 02-inventory-optimization/:
    data/processed/abc_classes.csv
    data/processed/abc_class_summary.csv
    data/processed/forecast_errors.csv
    data/processed/forecast_error_summary.csv
    data/processed/seven_day_blocks.csv
    images/abc_cumulative_share.png
    images/daily_forecast_error_hist.png
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save files; do not open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Paths are anchored to this file so the script works no matter the shell cwd.
PROJECT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
FORECAST = (
    REPO
    / "01-demand-forecasting"
    / "data"
    / "processed"
    / "ca3_foods_holdout_predictions.csv"
)
PROC = PROJECT / "data" / "processed"
IMG = PROJECT / "images"

# Plan decision, not a result of this file: class A is the prefix of items,
# ranked by actual holdout units, whose cumulative share reaches 80% of units.
# B is the next slice of that same ranking until the cumulative share reaches
# 95%. C is the rest. These are shares of units, not a headcount chosen first.
A_CUTOFF = 0.80
B_CUTOFF = 0.95

# Plan decision: lead time is a fixed 7-day assumption, with no variability.
# The number is used here only to cut the 28-day holdout into windows of that
# length so the width of a 7-day forecast miss can be described. It is not
# multiplied by a standard deviation, and it is not a safety stock.
LEAD_TIME_DAYS = 7
HOLDOUT_DAYS = 28


def load_forecast(path: Path) -> pd.DataFrame:
    """Read the Project 1 holdout file and check the shape the plan stated.

    Columns are daily unit sales. sell_price is not loaded. The shelf price
    is what the shopper paid, not the unit cost, and there is no holding-cost
    rate to turn a price into a cost. Ranking or scoring in dollars would
    invent that cost. This stage stays in units.
    """
    if not path.is_file():
        raise SystemExit(f"missing forecast file: {path}")
    df = pd.read_csv(path)
    expected = ["item_id", "day", "actual", "baseline", "lgbm"]
    if list(df.columns) != expected:
        raise SystemExit(f"unexpected columns: {list(df.columns)}")
    if df.isna().any().any():
        raise SystemExit("forecast file has missing values")
    df["day"] = pd.to_datetime(df["day"])
    df["actual"] = df["actual"].astype(np.int64)
    df["baseline"] = df["baseline"].astype(np.int64)
    df["lgbm"] = df["lgbm"].astype(np.float64)
    n_items = df["item_id"].nunique()
    n_days = df["day"].nunique()
    if len(df) != n_items * n_days:
        raise SystemExit("item-day rows are not a complete grid")
    if df.duplicated(["item_id", "day"]).any():
        raise SystemExit("duplicate item-day rows")
    if n_items != 1437 or n_days != HOLDOUT_DAYS or len(df) != 40236:
        raise SystemExit(
            f"shape changed: items={n_items} days={n_days} rows={len(df)}"
        )
    days = np.sort(df["day"].unique())
    if days[0] != np.datetime64("2016-04-25") or days[-1] != np.datetime64("2016-05-22"):
        raise SystemExit(f"holdout dates changed: {days[0]} .. {days[-1]}")
    gaps = np.diff(days).astype("timedelta64[D]").astype(np.int64)
    if not np.all(gaps == 1):
        raise SystemExit("holdout days are not consecutive")
    return df


def add_errors(df: pd.DataFrame) -> pd.DataFrame:
    """Signed error is the planning forecast minus actual.

    Positive means lgbm sat above the units that sold that day. That is the
    same direction as a high bias: sum(lgbm) - sum(actual) > 0 when the
    forecast is high in total. The other subtraction would make a high
    forecast look negative and would fight the plan's wording. The bias is
    not subtracted out of lgbm. The forecast is used as-is.
    """
    out = df.copy()
    out["error"] = out["lgbm"] - out["actual"]
    out["abs_error"] = out["error"].abs()
    out["baseline_error"] = out["baseline"] - out["actual"]
    out["baseline_abs_error"] = out["baseline_error"].abs()
    return out


def per_item_errors(df: pd.DataFrame) -> pd.DataFrame:
    """One row per item. daily_error_std is the sample std of daily errors.

    Divisor is n_days - 1 (pandas default). With 28 days that is the ordinary
    sample standard deviation of (lgbm - actual) on that item. It is a
    day-level spread, not a 7-day spread. MAE is the mean of |lgbm - actual|
    on that item's days, in units per day. bias is sum(lgbm) - sum(actual),
    in units over the whole holdout, not per day and not divided by actual.
    """
    grouped = df.groupby("item_id", sort=False)
    per = grouped.agg(
        n_days=("day", "nunique"),
        sum_actual=("actual", "sum"),
        sum_lgbm=("lgbm", "sum"),
        bias=("error", "sum"),
        mae=("abs_error", "mean"),
        daily_error_std=("error", "std"),
    ).reset_index()
    if not np.all(per["n_days"].to_numpy() == HOLDOUT_DAYS):
        raise SystemExit("an item does not have 28 days")
    # bias is defined as sum(lgbm) - sum(actual). The aggregation must match.
    if not np.allclose(per["bias"], per["sum_lgbm"] - per["sum_actual"]):
        raise SystemExit("per-item bias is not sum(lgbm) - sum(actual)")
    return per


def assign_abc(per: pd.DataFrame) -> pd.DataFrame:
    """Rank by actual holdout units and cut the cumulative share at 80% and 95%.

    Highest unit volume is first. item_id ascending is only a stable file
    order. It is not a rank. Share is that item's units divided by all
    holdout units. Cumulative share is the running sum in this order.

    Class A is every item with at least as many holdout units as the first
    item whose cumulative share reaches 80%. That item is included, because
    stopping one item earlier would leave the class short of 80%. Every other
    item with that same unit count is included too. Splitting the tie would
    let item_id, not units, decide who is in A. Class B is the same rule on
    what remains: the next volumes until the cumulative share reaches 95%,
    and the whole tie at that volume. Class C is whatever is left. The rank
    is units, not units times sell_price.
    """
    abc = per[["item_id", "sum_actual"]].copy()
    abc = abc.rename(columns={"sum_actual": "holdout_units"})
    abc = abc.sort_values(
        ["holdout_units", "item_id"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    units = abc["holdout_units"].to_numpy(dtype=np.int64)
    total = float(units.sum())
    if total <= 0:
        raise SystemExit("holdout units sum to zero")
    # cumsum of the integer counts, then one division, so the last share is 1.
    cumulative_units = np.cumsum(units)
    abc["share"] = units / total
    abc["cumulative_share"] = cumulative_units / total
    if not np.isclose(abc["cumulative_share"].iloc[-1], 1.0):
        raise SystemExit("cumulative share does not end at 1")
    cum = abc["cumulative_share"].to_numpy()
    cross_a = int(np.flatnonzero(cum >= A_CUTOFF)[0])
    a_units = int(units[cross_a])
    # Same volume as the item that crosses 80% stays in A. item_id does not
    # move a tied item into B.
    in_a = units >= a_units
    rest = np.flatnonzero(~in_a)
    if len(rest) == 0:
        raise SystemExit("every item fell in class A")
    hits_b = np.flatnonzero(cum[rest] >= B_CUTOFF)
    if len(hits_b) == 0:
        raise SystemExit("cumulative share never reaches 95%")
    cross_b = int(rest[int(hits_b[0])])
    b_units = int(units[cross_b])
    if b_units >= a_units:
        raise SystemExit("class B volume is not below class A volume")
    in_b = (~in_a) & (units >= b_units)
    classes = np.full(len(abc), "C", dtype=object)
    classes[in_a] = "A"
    classes[in_b] = "B"
    # A then B then C in the unit ranking. A later row must not jump back.
    order = {"A": 0, "B": 1, "C": 2}
    ranks = np.array([order[label] for label in classes], dtype=np.int64)
    if np.any(np.diff(ranks) < 0):
        raise SystemExit("class labels are not in A, then B, then C order")
    abc["abc_class"] = classes
    abc.attrs["cross_a"] = cross_a
    abc.attrs["cross_b"] = cross_b
    abc.attrs["a_units"] = a_units
    abc.attrs["b_units"] = b_units
    abc.attrs["n_at_a_units"] = int(np.sum(units == a_units))
    abc.attrs["n_at_b_units"] = int(np.sum(units == b_units))
    abc.attrs["last_a"] = int(np.flatnonzero(in_a)[-1])
    abc.attrs["last_b"] = int(np.flatnonzero(in_b)[-1])
    return abc


def class_summary(abc: pd.DataFrame) -> pd.DataFrame:
    """Item counts and unit shares by class. item_share is count, not volume."""
    total_units = float(abc["holdout_units"].sum())
    total_items = float(len(abc))
    rows = []
    for label in ["A", "B", "C"]:
        part = abc.loc[abc["abc_class"] == label]
        units = float(part["holdout_units"].sum())
        n_items = int(len(part))
        rows.append(
            {
                "abc_class": label,
                "n_items": n_items,
                "holdout_units": units,
                "unit_share": units / total_units,
                "item_share": n_items / total_items,
            }
        )
    out = pd.DataFrame(rows)
    if not np.isclose(out["unit_share"].sum(), 1.0):
        raise SystemExit("class unit shares do not sum to 1")
    if int(out["n_items"].sum()) != len(abc):
        raise SystemExit("class item counts do not sum to all items")
    return out


def seven_day_blocks(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Four non-overlapping 7-day blocks, in calendar order.

    The holdout is 28 consecutive days, so it divides into four windows of
    the assumed lead time. Overlapping windows would reuse the same days and
    are not used. block error = sum(lgbm) - sum(actual) inside the window.
    That describes a 7-day miss. It is not safety stock, and it is not the
    daily standard deviation times sqrt(7).
    """
    days = list(np.sort(df["day"].unique()))
    if len(days) != HOLDOUT_DAYS or HOLDOUT_DAYS % LEAD_TIME_DAYS != 0:
        raise SystemExit("holdout length is not a multiple of 7 days")
    n_blocks = HOLDOUT_DAYS // LEAD_TIME_DAYS
    day_to_block = {day: i // LEAD_TIME_DAYS for i, day in enumerate(days)}
    labeled = df.copy()
    labeled["block"] = labeled["day"].map(day_to_block)
    ranges = []
    for block in range(n_blocks):
        block_days = [day for day, b in day_to_block.items() if b == block]
        start = pd.Timestamp(min(block_days))
        end = pd.Timestamp(max(block_days))
        ranges.append(
            {
                "block": block,
                "start_day": start.strftime("%Y-%m-%d"),
                "end_day": end.strftime("%Y-%m-%d"),
                "n_days": len(block_days),
            }
        )
    block_calendar = pd.DataFrame(ranges)
    if not np.all(block_calendar["n_days"].to_numpy() == LEAD_TIME_DAYS):
        raise SystemExit("a 7-day block does not have 7 days")
    summed = labeled.groupby(["item_id", "block"], as_index=False).agg(
        sum_actual=("actual", "sum"),
        sum_lgbm=("lgbm", "sum"),
        sum_error=("error", "sum"),
    )
    # Sum of daily (lgbm - actual) equals the 7-day forecast total minus the
    # 7-day actual total. Keep that identity explicit.
    summed["seven_day_error"] = summed["sum_lgbm"] - summed["sum_actual"]
    if not np.allclose(summed["seven_day_error"], summed["sum_error"]):
        raise SystemExit("7-day error is not the sum of daily errors")
    return block_calendar, summed


def scope_metrics(
    scope: str,
    daily: pd.DataFrame,
    per: pd.DataFrame,
    blocks: pd.DataFrame,
    total_actual: float,
) -> dict:
    """Same definitions on one scope (overall or one ABC class).

    WAPE = sum(|lgbm - actual|) / sum(actual), zeros included. Bias share =
    (sum(lgbm) - sum(actual)) / sum(actual). Both match the Project 1
    definitions. MAE and daily_error_std pool item-days, so a busy day and a
    quiet day each count once. The median item stats do not let one huge item
    set the width. None of these is a safety stock.
    """
    sum_actual = float(daily["actual"].sum())
    sum_lgbm = float(daily["lgbm"].sum())
    sum_abs = float(daily["abs_error"].sum())
    bias_units = float(daily["error"].sum())
    if sum_actual <= 0:
        raise SystemExit(f"{scope}: actual units are zero")
    if not np.isclose(bias_units, sum_lgbm - sum_actual):
        raise SystemExit(f"{scope}: bias identity failed")
    block_err = blocks["seven_day_error"].to_numpy(dtype=np.float64)
    return {
        "scope": scope,
        "n_items": int(per["item_id"].nunique()),
        "n_item_days": int(len(daily)),
        "sum_actual": sum_actual,
        "sum_lgbm": sum_lgbm,
        "sum_abs_error": sum_abs,
        "bias_units": bias_units,
        "bias_share_of_units": bias_units / sum_actual,
        "wape": sum_abs / sum_actual,
        "mae": float(daily["abs_error"].mean()),
        "daily_error_std": float(daily["error"].std(ddof=1)),
        "daily_error_median": float(daily["error"].median()),
        "daily_error_min": float(daily["error"].min()),
        "daily_error_max": float(daily["error"].max()),
        "daily_error_p01": float(daily["error"].quantile(0.01)),
        "daily_error_p99": float(daily["error"].quantile(0.99)),
        "median_item_mae": float(per["mae"].median()),
        "median_item_daily_error_std": float(per["daily_error_std"].median()),
        "share_item_days_positive_error": float((daily["error"] > 0).mean()),
        "share_item_days_negative_error": float((daily["error"] < 0).mean()),
        "unit_share": sum_actual / total_actual,
        "baseline_sum_abs_error": float(daily["baseline_abs_error"].sum()),
        "baseline_bias_units": float(daily["baseline_error"].sum()),
        "baseline_wape": float(daily["baseline_abs_error"].sum()) / sum_actual,
        "baseline_bias_share_of_units": float(daily["baseline_error"].sum()) / sum_actual,
        "seven_day_n_item_blocks": int(len(blocks)),
        "seven_day_error_mean": float(block_err.mean()),
        "seven_day_error_std": float(pd.Series(block_err).std(ddof=1)),
        "seven_day_error_mae": float(np.mean(np.abs(block_err))),
        "seven_day_mean_actual": float(blocks["sum_actual"].mean()),
        "seven_day_mean_lgbm": float(blocks["sum_lgbm"].mean()),
    }


def plot_abc(abc: pd.DataFrame, path: Path) -> None:
    """Cumulative unit curve with the 80% and 95% cuts drawn on it."""
    rank = np.arange(1, len(abc) + 1)
    n_a = int((abc["abc_class"] == "A").sum())
    n_b = int((abc["abc_class"] == "B").sum())
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.plot(rank, abc["cumulative_share"], color="#0B3A6A", lw=1.6)
    ax.axhline(A_CUTOFF, color="#B85C38", ls="--", lw=1.0, label="80% of units")
    ax.axhline(B_CUTOFF, color="#2F6F4E", ls="--", lw=1.0, label="95% of units")
    ax.axvline(n_a, color="#B85C38", ls=":", lw=1.0, label=f"End of class A (item {n_a})")
    ax.axvline(
        n_a + n_b,
        color="#2F6F4E",
        ls=":",
        lw=1.0,
        label=f"End of class B (item {n_a + n_b})",
    )
    ax.set_xlim(1, len(abc))
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Items ranked by actual holdout units (busiest first)")
    ax.set_ylabel("Cumulative share of holdout units")
    ax.set_title("CA_3 FOODS holdout: how fast unit volume accumulates")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_errors(df: pd.DataFrame, class_a: set[str], path: Path) -> None:
    """Histogram of daily (lgbm - actual). Axis is the 1st to 99th percentile.

    The tails beyond that window are real and are reported as min and max in
    the summary table. They are left off the axis so the body of the
    distribution is readable. Positive bars are days the forecast was high.
    """
    err_all = df["error"].to_numpy(dtype=np.float64)
    err_a = df.loc[df["item_id"].isin(class_a), "error"].to_numpy(dtype=np.float64)
    lo = float(np.quantile(err_all, 0.01))
    hi = float(np.quantile(err_all, 0.99))
    bins = np.linspace(lo, hi, 41)
    # Shared x so the widths can be compared. Separate y axes: class A has
    # fewer item-days, and a shared count axis would flatten its shape.
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2), sharex=True, sharey=False)
    panels = (
        (axes[0], err_all, "All items", "#4C78A8"),
        (axes[1], err_a, "Class A only", "#E07A3D"),
    )
    for ax, values, title, color in panels:
        ax.hist(values, bins=bins, color=color, edgecolor="white", linewidth=0.3)
        ax.axvline(0, color="#222222", lw=1.0)
        ax.set_title(title)
        ax.set_xlabel("Daily error (lgbm − actual), units")
    axes[0].set_ylabel("Item-days")
    fig.suptitle(
        "Daily forecast error on the holdout (axis: 1st to 99th percentile)",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)

    df = add_errors(load_forecast(FORECAST))
    per = per_item_errors(df)
    abc = assign_abc(per)
    summary_abc = class_summary(abc)
    block_calendar, block_errors = seven_day_blocks(df)

    class_by_item = abc.set_index("item_id")["abc_class"]
    per = per.merge(abc[["item_id", "abc_class"]], on="item_id", how="left")
    if per["abc_class"].isna().any():
        raise SystemExit("an item has no ABC class")

    total_actual = float(df["actual"].sum())
    # Overall row is the whole file. Class rows use the same formulas on the
    # items in that class only. Denominators are that scope's own actual units.
    scope_frames = [("overall", df["item_id"].unique())]
    for label in ["A", "B", "C"]:
        scope_frames.append((label, abc.loc[abc["abc_class"] == label, "item_id"]))

    rows = []
    for scope, item_ids in scope_frames:
        item_ids = set(item_ids)
        daily = df.loc[df["item_id"].isin(item_ids)]
        per_scope = per.loc[per["item_id"].isin(item_ids)]
        blocks = block_errors.loc[block_errors["item_id"].isin(item_ids)]
        rows.append(scope_metrics(scope, daily, per_scope, blocks, total_actual))
    summary = pd.DataFrame(rows)

    # Class unit totals in the error summary must match the ABC file.
    for label in ["A", "B", "C"]:
        from_abc = float(
            summary_abc.loc[summary_abc["abc_class"] == label, "holdout_units"].iloc[0]
        )
        from_err = float(summary.loc[summary["scope"] == label, "sum_actual"].iloc[0])
        if not np.isclose(from_abc, from_err):
            raise SystemExit(f"class {label} units disagree between ABC and errors")

    abc_out = abc[
        ["item_id", "holdout_units", "share", "cumulative_share", "abc_class"]
    ]
    # Rank order is the file order: busiest item first. cumulative_share only
    # makes sense in that order.
    abc_out.to_csv(PROC / "abc_classes.csv", index=False)
    summary_abc.to_csv(PROC / "abc_class_summary.csv", index=False)

    errors_out = per[
        ["item_id", "n_days", "sum_actual", "sum_lgbm", "bias", "mae", "daily_error_std"]
    ].sort_values("item_id", kind="mergesort")
    errors_out.to_csv(PROC / "forecast_errors.csv", index=False)
    summary.to_csv(PROC / "forecast_error_summary.csv", index=False)
    block_calendar.to_csv(PROC / "seven_day_blocks.csv", index=False)

    plot_abc(abc, IMG / "abc_cumulative_share.png")
    class_a_ids = set(abc.loc[abc["abc_class"] == "A", "item_id"])
    plot_errors(df, class_a_ids, IMG / "daily_forecast_error_hist.png")

    # Stdout is for the report writer. The CSVs are the record.
    print(
        "A_volume",
        abc.attrs["a_units"],
        "n_tied",
        abc.attrs["n_at_a_units"],
        "cross_item",
        abc.loc[abc.attrs["cross_a"], "item_id"],
        "cross_cum",
        float(abc.loc[abc.attrs["cross_a"], "cumulative_share"]),
        "last_A",
        abc.loc[abc.attrs["last_a"], "item_id"],
        "last_A_cum",
        float(abc.loc[abc.attrs["last_a"], "cumulative_share"]),
        "before_A_volume",
        abc.loc[abc.attrs["cross_a"] - 1, "item_id"],
        "before_units",
        int(abc.loc[abc.attrs["cross_a"] - 1, "holdout_units"]),
        "before_cum",
        float(abc.loc[abc.attrs["cross_a"] - 1, "cumulative_share"]),
    )
    print(
        "B_volume",
        abc.attrs["b_units"],
        "n_tied",
        abc.attrs["n_at_b_units"],
        "cross_item",
        abc.loc[abc.attrs["cross_b"], "item_id"],
        "cross_cum",
        float(abc.loc[abc.attrs["cross_b"], "cumulative_share"]),
        "last_B",
        abc.loc[abc.attrs["last_b"], "item_id"],
        "last_B_cum",
        float(abc.loc[abc.attrs["last_b"], "cumulative_share"]),
    )
    print(summary_abc.to_string(index=False))
    print(summary.to_string(index=False))
    print("top15")
    print(abc_out.head(15).to_string(index=False))
    print("class_by_item_check", class_by_item.nunique())


if __name__ == "__main__":
    main()
