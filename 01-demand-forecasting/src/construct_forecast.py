#!/usr/bin/env python3
"""Construct stage: 28-day forecast for FOODS at store CA_3.

Scope (fixed before this script is run):
    Category FOODS, store CA_3 only. One series per item.
    Horizon: 28 days.
    Holdout: d_1914 through d_1941 (2016-04-25 through 2016-05-22).
    Train labels: d_1 through d_1913 only.
    Target: daily unit sales.

Two forecasts, same holdout, no holdout actuals in either one:
    1. Seasonal naive (lag-28). The forecast for a holdout day is the
       actual from 28 days earlier, which is the same weekday four weeks
       back. For this horizon that window is d_1886 through d_1913, the
       28 days immediately before the holdout.
    2. LightGBM, direct multi-step. Every sales feature is a lag of 28
       days or more, so the same columns can be filled for all 28 holdout
       days from history that ends on d_1913. Lags 1-27 are not used.

Run from anywhere:
    python 01-demand-forecasting/src/construct_forecast.py

Requires: pandas, numpy, matplotlib, lightgbm, openpyxl.
The model is fit with lightgbm.train (the native API), not the sklearn wrapper.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save files; do not open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import lightgbm as lgb
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

# Paths are anchored to this file so the script works no matter the shell cwd.
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
IMG = ROOT / "images"
REPORTS = ROOT / "reports"

# Last training day column is d_1913 (0-based index 1912).
# First holdout day column is d_1914 (0-based index 1913).
LAST_TRAIN_INDEX = 1912  # d_1913
HOLDOUT_START_INDEX = 1913  # d_1914
N_DAYS = 1941
HORIZON = 28
# Rolling mean of 28 days ending at lag 28 reads back to t-55.
# Index 55 is the first target day with every sales feature complete.
FIRST_FEATURE_INDEX = 55

# Early-stopping check is the 28 days before the holdout, never the holdout.
# Those days are still training labels. They are only held out of the first
# fit so the tree count is chosen without looking at d_1914-d_1941.
EARLY_STOP_DAYS = 28
EARLY_STOP_ROUNDS = 40
MAX_TREES = 400

WEEKDAY_ORDER = [
    "Saturday",
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
]

# Column order is the order LightGBM sees. wday and month are passed as
# categorical features by name, so a tree does not treat Saturday (1) as
# "less than" Friday (7).
FEATURE_NAMES = [
    "lag_28",
    "lag_35",
    "lag_42",
    "roll_mean_7_ending_lag28",
    "roll_mean_28_ending_lag28",
    "wday",
    "month",
    "snap_CA",
    "event_flag",
    "sell_price",
]


def load_foods_ca3() -> pd.DataFrame:
    """Read evaluation sales and keep FOODS at CA_3.

    The file is wide (one row per item-store, one column per day) and holds
    all ten stores. Chunking lets us drop the other rows before concatenating.
    """
    pieces = []
    path = RAW / "sales_train_evaluation.csv"
    for chunk in pd.read_csv(path, chunksize=5_000):
        keep = chunk[(chunk["store_id"] == "CA_3") & (chunk["cat_id"] == "FOODS")]
        if len(keep):
            pieces.append(keep)
    sales = pd.concat(pieces, ignore_index=True)
    if sales.empty:
        raise SystemExit("No FOODS rows at CA_3. Check the raw sales file.")
    if sales["item_id"].duplicated().any():
        raise SystemExit("Duplicate item_id inside FOODS at CA_3.")
    # Stable order so the prediction file does not depend on file order.
    sales = sales.sort_values("item_id").reset_index(drop=True)
    return sales


def load_calendar() -> pd.DataFrame:
    """One row per day, aligned to d_1 ... d_1941 by the 'd' column."""
    calendar = pd.read_csv(RAW / "calendar.csv")
    calendar["date"] = pd.to_datetime(calendar["date"])
    calendar = calendar.set_index("d")
    expected = [f"d_{i}" for i in range(1, N_DAYS + 1)]
    missing = [name for name in expected if name not in calendar.index]
    if missing:
        raise SystemExit(f"calendar.csv is missing day keys, first: {missing[:3]}")
    # One row per day column, in d_1, d_2, ... order. Not the file's order.
    return calendar.loc[expected].reset_index()


def load_prices(item_ids: np.ndarray, week_ids: np.ndarray) -> np.ndarray:
    """Weekly price for each item and each day, NaN when that week has no row.

    sell_prices is item-store-week, not item-store-day. We attach the price
    of the week that contains the target day. Weeks before the item is listed
    have no row; those stay NaN. We do not fill them with a later week's price,
    because that would invent a shelf price for a week the item was not sold.
    """
    wanted_items = set(item_ids.tolist())
    wanted_weeks = set(int(w) for w in np.unique(week_ids))
    pieces = []
    path = RAW / "sell_prices.csv"
    for chunk in pd.read_csv(path, chunksize=500_000):
        keep = chunk[(chunk["store_id"] == "CA_3") & (chunk["item_id"].isin(wanted_items))]
        if len(keep):
            pieces.append(keep)
    prices = pd.concat(pieces, ignore_index=True)
    prices = prices[prices["wm_yr_wk"].isin(wanted_weeks)]
    if prices.duplicated(["item_id", "wm_yr_wk"]).any():
        raise SystemExit("Duplicate item-week price at CA_3.")

    wide = prices.pivot(index="item_id", columns="wm_yr_wk", values="sell_price")
    wide = wide.reindex(item_ids)
    # Day j gets the price column of its Walmart week. Missing column -> NaN.
    week_to_price = {}
    for week in wide.columns:
        week_to_price[int(week)] = wide[week].to_numpy(dtype=np.float64)
    price_by_day = np.full((len(item_ids), N_DAYS), np.nan, dtype=np.float64)
    for day_index, week in enumerate(week_ids):
        column = week_to_price.get(int(week))
        if column is not None:
            price_by_day[:, day_index] = column
    return price_by_day


def rolling_mean_ending_at(csum: np.ndarray, end_index: np.ndarray, window: int) -> np.ndarray:
    """Mean of `window` sales days ending at each index in end_index.

    csum is the cumulative sum of sales along the day axis, per item.
    end_index is shared by every item. The window is end_index-window+1
    through end_index, inclusive. Caller must guarantee the start is >= 0.
    """
    start_index = end_index - window + 1
    if int(start_index.min()) < 0:
        raise SystemExit("Rolling window reaches before d_1. Move the first target day later.")
    right = csum[:, end_index]
    left = np.zeros_like(right)
    has_prior = start_index > 0
    if np.any(has_prior):
        left[:, has_prior] = csum[:, start_index[has_prior] - 1]
    return (right - left) / float(window)


def build_feature_matrix(
    sales: np.ndarray,
    csum: np.ndarray,
    calendar: pd.DataFrame,
    price_by_day: np.ndarray,
    day_index: np.ndarray,
) -> np.ndarray:
    """Features for each item on each day in day_index.

    Shape of the return is (n_items * n_days, n_features), item-major:
    all selected days for item 0, then item 1, and so on.

    Sales features use only day t-28 or earlier. That is the leakage rule.
    Calendar features are the target day's own calendar, which is known
    before the day happens. Price is the target week's price, not a sales lag.
    """
    # lag_28: units on the same weekday four weeks before the target day.
    # This is also the seasonal-naive forecast. At a 28-day horizon it is
    # the most recent same-weekday actual that is always already observed.
    lag_28 = sales[:, day_index - 28]
    # lag_35: same weekday five weeks back. Gives the tree a second look at
    # the weekly cycle so one odd week is not the whole story.
    lag_35 = sales[:, day_index - 35]
    # lag_42: same weekday six weeks back. A third point, still outside the
    # horizon, so it can be filled for every holdout day without recursion.
    lag_42 = sales[:, day_index - 42]
    # 7-day mean ending on the lag-28 day (that day and the six before it).
    # "Ending at lag 28" keeps lags 1-27 out of the window. Those lags would
    # fall inside the horizon for a 28-day-ahead origin.
    end_at_lag_28 = day_index - 28
    roll_7 = rolling_mean_ending_at(csum, end_at_lag_28, 7)
    # 28-day mean ending on the same lag-28 day. A month of level, shifted
    # with the target so a direct (non-recursive) forecast stays legal.
    roll_28 = rolling_mean_ending_at(csum, end_at_lag_28, 28)

    # Calendar of the target day. Known in advance; not computed from sales.
    # wday is Walmart's weekday: 1=Saturday ... 7=Friday.
    wday = np.broadcast_to(calendar.loc[day_index, "wday"].to_numpy(dtype=np.float64), lag_28.shape)
    month = np.broadcast_to(calendar.loc[day_index, "month"].to_numpy(dtype=np.float64), lag_28.shape)
    # snap_CA is 1 on the 1st-10th of the month in California. Analyze showed
    # food volume is higher on those days, so the flag is in the model.
    snap = np.broadcast_to(calendar.loc[day_index, "snap_CA"].to_numpy(dtype=np.float64), lag_28.shape)
    # 1 if either event slot is filled (holiday, sporting event, religious day).
    # One flag rather than one column per event name: most names are rare.
    name_1 = calendar.loc[day_index, "event_name_1"]
    name_2 = calendar.loc[day_index, "event_name_2"]
    event = ((name_1.notna() & name_1.ne("")) | (name_2.notna() & name_2.ne(""))).to_numpy(dtype=np.float64)
    event = np.broadcast_to(event, lag_28.shape)
    # Price of the Walmart week that contains the target day. NaN if that
    # item has no price row yet. LightGBM can split on missing; we do not
    # impute a future price.
    price = price_by_day[:, day_index]

    columns = [lag_28, lag_35, lag_42, roll_7, roll_28, wday, month, snap, event, price]
    # Stack item-major. Each array is (n_items, n_days); C order matches that.
    flat = [column.reshape(-1, 1) for column in columns]
    return np.hstack(flat).astype(np.float32)


def assert_holdout_features_do_not_cross_origin(day_index: np.ndarray) -> None:
    """Fail the run if a holdout sales feature would read a holdout actual.

    The newest sales day any feature may touch is the lag-28 day of the last
    holdout day, which is d_1913 (index 1912). Lags 35 and 42 and both
    rolling windows end at or before that same lag-28 day.
    """
    newest_sales_index = int((day_index - 28).max())
    if newest_sales_index > LAST_TRAIN_INDEX:
        raise SystemExit(
            f"Leakage: a holdout feature reads day index {newest_sales_index}, "
            f"which is after d_1913."
        )
    if newest_sales_index != LAST_TRAIN_INDEX:
        raise SystemExit(
            f"Expected the newest lag-28 source to be d_1913, got index {newest_sales_index}."
        )
    oldest_needed = int((day_index - 55).min())  # start of the 28-day window ending at lag 28
    if oldest_needed < 0:
        raise SystemExit("Holdout rolling window starts before d_1.")


def score_block(actual: np.ndarray, forecast: np.ndarray, weekday: np.ndarray, model_name: str) -> list[dict]:
    """MAPE on positive-actual item-days, plus WAPE and bias on every item-day.

    MAPE = mean(|forecast - actual| / actual) where actual > 0.
    A zero actual would make that ratio undefined, so those days are left
    out of MAPE only. They stay in WAPE and bias.

    WAPE = sum(|forecast - actual|) / sum(actual). This is the volume-weighted
    score: a high-unit item moves it more than a one-unit item.

    bias = sum(forecast - actual) / sum(actual). Positive means the forecast
    is high in total units. Negative means it is low.
    """
    actual = np.asarray(actual, dtype=np.float64)
    forecast = np.asarray(forecast, dtype=np.float64)
    error = forecast - actual
    abs_error = np.abs(error)
    positive = actual > 0

    def one(mask: np.ndarray, slice_name: str, weekday_name: str) -> dict:
        actual_m = actual[mask]
        error_m = error[mask]
        abs_m = abs_error[mask]
        positive_m = positive[mask]
        sum_actual = float(actual_m.sum())
        if sum_actual == 0:
            raise SystemExit(f"No actual units for {model_name} / {weekday_name}.")
        if not np.any(positive_m):
            mape = float("nan")
        else:
            mape = float(np.mean(abs_m[positive_m] / actual_m[positive_m]))
        sum_abs = float(abs_m.sum())
        sum_error = float(error_m.sum())
        return {
            "model": model_name,
            "slice": slice_name,
            "weekday": weekday_name,
            "mape": mape,
            "wape": sum_abs / sum_actual,
            "bias": sum_error / sum_actual,
            "n_item_days": int(mask.sum()),
            "n_positive_days": int(positive_m.sum()),
            "sum_actual": sum_actual,
            "sum_abs_error": sum_abs,
            "sum_error": sum_error,
        }

    rows = [one(np.ones(len(actual), dtype=bool), "overall", "all")]
    for name in WEEKDAY_ORDER:
        rows.append(one(weekday == name, "weekday", name))
    return rows


def save_charts(dates: pd.DatetimeIndex, actual: np.ndarray, baseline: np.ndarray, lgbm: np.ndarray) -> None:
    """Two charts of the 28 holdout days, summed across every FOODS item at CA_3."""
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 11,
        }
    )
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(dates, actual, label="Actual", color="#222222", linewidth=2.0)
    ax.plot(dates, baseline, label="Seasonal naive (lag-28)", color="#4C78A8", linewidth=1.7)
    ax.plot(dates, lgbm, label="LightGBM", color="#F58518", linewidth=1.7)
    ax.set_ylabel("Units (all FOODS items at CA_3)")
    ax.set_xlabel("Day")
    ax.set_title("CA_3 FOODS holdout: daily actual vs both forecasts")
    ax.legend(frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(IMG / "ca3_foods_forecast_vs_actual.png", dpi=120)
    plt.close(fig)

    # Error chart: daily total forecast minus daily total actual.
    # Above zero means that day's forecast was high.
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.plot(dates, baseline - actual, label="Seasonal naive error", color="#4C78A8", linewidth=1.7)
    ax.plot(dates, lgbm - actual, label="LightGBM error", color="#F58518", linewidth=1.7)
    ax.set_ylabel("Forecast minus actual (units)")
    ax.set_xlabel("Day")
    ax.set_title("CA_3 FOODS holdout: daily total error")
    ax.legend(frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(IMG / "ca3_foods_daily_error.png", dpi=120)
    plt.close(fig)


def save_excel(
    item_id: str,
    dept_id: str,
    train_units: float,
    holdout_actual_item: np.ndarray,
    dates: pd.Series,
    weekdays: pd.Series,
    snap: pd.Series,
    baseline_item: np.ndarray,
    lgbm_item: np.ndarray,
    source_dates: pd.Series,
    source_weekdays: pd.Series,
    source_actual: np.ndarray,
    item_metrics: pd.DataFrame,
) -> None:
    """One item, one store: the lag-28 baseline next to the LightGBM forecast.

    The item is the highest-volume FOODS item at CA_3 on training days only
    (d_1 through d_1913). The holdout is not used to pick it.
    """
    holdout = pd.DataFrame(
        {
            "date": dates.dt.strftime("%Y-%m-%d").to_numpy(),
            "weekday": weekdays.to_numpy(),
            "snap_CA": snap.to_numpy(),
            "actual_units": holdout_actual_item.astype(int),
            "baseline_lag28": baseline_item.astype(int),
            "lightgbm": lgbm_item,
        }
    )
    source = pd.DataFrame(
        {
            "date": source_dates.dt.strftime("%Y-%m-%d").to_numpy(),
            "weekday": source_weekdays.to_numpy(),
            "actual_units": source_actual.astype(int),
            "note": "This actual is the lag-28 baseline of the holdout day 28 days later.",
        }
    )
    notes = pd.DataFrame(
        [
            ("item_id", item_id),
            ("dept_id", dept_id),
            ("store_id", "CA_3"),
            ("cat_id", "FOODS"),
            ("why_this_item", "Highest sum of units on d_1 through d_1913 at CA_3 among FOODS. Holdout units were not used to choose it."),
            ("train_units_d1_through_d1913", int(train_units)),
            ("holdout", "d_1914 through d_1941, 2016-04-25 through 2016-05-22"),
            ("baseline", "Seasonal naive: actual units from 28 days earlier (same weekday, four weeks back)."),
            ("lightgbm", "Direct 28-day LightGBM fit on all FOODS items at CA_3. This sheet is that model's forecast for this one item."),
            ("leakage_rule", "No holdout actual is a feature or a training label. Sales features are lag 28 or older."),
        ],
        columns=["field", "value"],
    )

    path = REPORTS / "ca3_foods_one_item_forecast.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        notes.to_excel(writer, sheet_name="Notes", index=False)
        holdout.to_excel(writer, sheet_name="Holdout", index=False)
        item_metrics.to_excel(writer, sheet_name="Item metrics", index=False)
        source.to_excel(writer, sheet_name="Lag28 source", index=False)
        book = writer.book
        sheet = book["Holdout"]
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        # Line chart: actual, baseline, LightGBM across the 28 dates.
        chart = LineChart()
        chart.title = f"{item_id} at CA_3: holdout units"
        chart.y_axis.title = "Units"
        chart.x_axis.title = "Date"
        chart.height = 8
        chart.width = 18
        chart.legend.position = "b"
        data = Reference(sheet, min_col=4, max_col=6, min_row=1, max_row=1 + HORIZON)
        cats = Reference(sheet, min_col=1, min_row=2, max_row=1 + HORIZON)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        sheet.add_chart(chart, "A32")
        for worksheet in book.worksheets:
            for column_cells in worksheet.columns:
                length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
                worksheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(length + 2, 88)


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    sales_frame = load_foods_ca3()
    n_items = len(sales_frame)
    if n_items != 1437:
        raise SystemExit(f"Expected 1,437 FOODS series at CA_3, found {n_items}.")
    item_ids = sales_frame["item_id"].to_numpy()
    dept_ids = sales_frame["dept_id"].to_numpy()
    day_cols = [f"d_{i}" for i in range(1, N_DAYS + 1)]
    # float64 so the cumulative sums used for rolling means are exact integers
    # stored as floats (daily units are small integers).
    sales = sales_frame[day_cols].to_numpy(dtype=np.float64)
    csum = np.cumsum(sales, axis=1)

    calendar = load_calendar()
    if len(calendar) != N_DAYS:
        raise SystemExit(f"Calendar alignment has {len(calendar)} days, expected {N_DAYS}.")
    # Confirm the holdout the plan named, rather than trusting a comment.
    holdout_index = np.arange(HOLDOUT_START_INDEX, HOLDOUT_START_INDEX + HORIZON)
    if int(holdout_index.max()) != N_DAYS - 1:
        raise SystemExit("Holdout does not end on d_1941.")
    start_date = pd.Timestamp(calendar.loc[HOLDOUT_START_INDEX, "date"])
    end_date = pd.Timestamp(calendar.loc[int(holdout_index.max()), "date"])
    if start_date != pd.Timestamp("2016-04-25") or end_date != pd.Timestamp("2016-05-22"):
        raise SystemExit(f"Holdout dates are {start_date.date()} to {end_date.date()}, not the planned window.")
    if calendar.loc[HOLDOUT_START_INDEX, "weekday"] != "Monday":
        raise SystemExit("d_1914 is not Monday in this calendar file.")
    if calendar.loc[int(holdout_index.max()), "weekday"] != "Sunday":
        raise SystemExit("d_1941 is not Sunday in this calendar file.")

    price_by_day = load_prices(item_ids, calendar["wm_yr_wk"].to_numpy())
    assert_holdout_features_do_not_cross_origin(holdout_index)

    # Training targets: every day whose features are complete, through d_1913.
    # The last EARLY_STOP_DAYS of that span are the early-stopping check.
    model_index = np.arange(FIRST_FEATURE_INDEX, LAST_TRAIN_INDEX + 1)
    if len(model_index) <= EARLY_STOP_DAYS:
        raise SystemExit("Not enough pre-holdout days to train and early-stop.")
    print(f"Series: {n_items} FOODS items at CA_3")
    print(f"Feature days for fitting: d_{FIRST_FEATURE_INDEX + 1} through d_{LAST_TRAIN_INDEX + 1}")
    print(f"Early-stopping days: d_{int(model_index[-EARLY_STOP_DAYS]) + 1} through d_{LAST_TRAIN_INDEX + 1}")
    print(f"Holdout: d_{HOLDOUT_START_INDEX + 1} through d_{int(holdout_index.max()) + 1} ({start_date.date()} to {end_date.date()})")

    x_model = build_feature_matrix(sales, csum, calendar, price_by_day, model_index)
    y_model = sales[:, model_index].reshape(-1).astype(np.float64)
    n_model_days = len(model_index)
    row_day = np.arange(n_items * n_model_days) % n_model_days
    valid_mask = row_day >= (n_model_days - EARLY_STOP_DAYS)
    train_mask = ~valid_mask
    print(f"Train rows: {int(train_mask.sum())}  early-stop rows: {int(valid_mask.sum())}")
    print(f"Holdout price missing share: {float(np.isnan(price_by_day[:, holdout_index]).mean())}")

    # First fit only chooses how many trees to grow. Its validation rows are
    # still before the holdout. The second fit uses that tree count on every
    # pre-holdout row, including the early-stopping days.
    # Native lightgbm.train, not the sklearn wrapper, so scikit-learn is not
    # required. wday and month are categorical: the split does not assume
    # that Saturday (1) is "less than" Friday (7).
    params = {
        "objective": "regression",
        "metric": "l2",
        "learning_rate": 0.05,
        "num_leaves": 63,
        "min_child_samples": 100,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "feature_fraction": 1.0,
        "seed": 42,
        "verbose": -1,
    }
    train_set = lgb.Dataset(
        x_model[train_mask],
        label=y_model[train_mask],
        feature_name=FEATURE_NAMES,
        categorical_feature=["wday", "month"],
        free_raw_data=False,
    )
    valid_set = lgb.Dataset(
        x_model[valid_mask],
        label=y_model[valid_mask],
        feature_name=FEATURE_NAMES,
        categorical_feature=["wday", "month"],
        reference=train_set,
        free_raw_data=False,
    )
    starter = lgb.train(
        params,
        train_set,
        num_boost_round=MAX_TREES,
        valid_sets=[valid_set],
        valid_names=["pre_holdout_28d"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=EARLY_STOP_ROUNDS),
            lgb.log_evaluation(period=50),
        ],
    )
    # best_iteration is the number of trees with the best validation score.
    n_trees = int(starter.best_iteration)
    if n_trees < 1:
        raise SystemExit(f"Early stopping returned {n_trees} trees.")
    print(f"Early stopping chose {n_trees} trees (cap {MAX_TREES}).")

    full_set = lgb.Dataset(
        x_model,
        label=y_model,
        feature_name=FEATURE_NAMES,
        categorical_feature=["wday", "month"],
        free_raw_data=False,
    )
    model = lgb.train(params, full_set, num_boost_round=n_trees)

    importance = pd.DataFrame(
        {
            "feature": FEATURE_NAMES,
            "gain": model.feature_importance(importance_type="gain"),
            "split": model.feature_importance(importance_type="split"),
        }
    ).sort_values("gain", ascending=False)
    print("--- FEATURE IMPORTANCE (refit model) ---")
    print(importance.to_string(index=False))

    x_holdout = build_feature_matrix(sales, csum, calendar, price_by_day, holdout_index)
    # Same leakage check on the matrix that is about to be scored: the four
    # sales-feature columns must match shifts that stop on d_1913.
    lag_28_check = sales[:, holdout_index - 28].reshape(-1)
    if not np.allclose(x_holdout[:, 0], lag_28_check.astype(np.float32)):
        raise SystemExit("Holdout lag_28 column does not match sales shifted by 28.")

    raw_pred = model.predict(x_holdout).astype(np.float64)
    n_negative = int((raw_pred < 0).sum())
    lgbm = np.maximum(raw_pred, 0.0)
    print(f"Negative LightGBM predictions clipped to 0: {n_negative} of {len(lgbm)}")

    actual = sales[:, holdout_index].reshape(-1)
    # Baseline is lag-28 of the holdout. That is d_1886..d_1913, in order,
    # repeated once per item. No holdout actual is in this shift.
    baseline = sales[:, holdout_index - 28].reshape(-1)
    if int((holdout_index - 28).min()) != HOLDOUT_START_INDEX - HORIZON:
        raise SystemExit("Baseline window is not the 28 days immediately before the holdout.")

    weekday = np.tile(calendar.loc[holdout_index, "weekday"].to_numpy(), n_items)
    # np.tile of the 28 names repeats the block per item, which matches
    # item-major flattening. Check the first item's first day.
    if weekday[0] != "Monday" or weekday[27] != "Sunday":
        raise SystemExit("Weekday alignment on the flattened holdout is wrong.")

    metric_rows = []
    metric_rows.extend(score_block(actual, baseline, weekday, "baseline_lag28"))
    metric_rows.extend(score_block(actual, lgbm, weekday, "lightgbm"))
    metrics = pd.DataFrame(metric_rows)
    metrics_path = PROC / "ca3_foods_metrics.csv"
    metrics.to_csv(metrics_path, index=False)
    print("--- METRICS ---")
    print(metrics.to_string(index=False))

    date_strings = calendar.loc[holdout_index, "date"].dt.strftime("%Y-%m-%d").to_numpy()
    predictions = pd.DataFrame(
        {
            "item_id": np.repeat(item_ids, HORIZON),
            "day": np.tile(date_strings, n_items),
            "actual": actual.astype(int),
            "baseline": baseline.astype(int),
            "lgbm": lgbm,
        }
    )
    if len(predictions) != n_items * HORIZON:
        raise SystemExit("Prediction row count is not series x horizon.")
    # One more guard: within each item, baseline on the first holdout day
    # equals that item's actual 28 days earlier, and the CSV did not shuffle.
    if int(predictions.loc[0, "baseline"]) != int(sales[0, HOLDOUT_START_INDEX - HORIZON]):
        raise SystemExit("Saved baseline does not match the pre-holdout lag.")
    pred_path = PROC / "ca3_foods_holdout_predictions.csv"
    predictions.to_csv(pred_path, index=False)

    daily_actual = sales[:, holdout_index].sum(axis=0)
    daily_baseline = baseline.reshape(n_items, HORIZON).sum(axis=0)
    daily_lgbm = lgbm.reshape(n_items, HORIZON).sum(axis=0)
    save_charts(
        pd.DatetimeIndex(calendar.loc[holdout_index, "date"]),
        daily_actual,
        daily_baseline,
        daily_lgbm,
    )
    print("--- DAILY TOTALS ---")
    daily = pd.DataFrame(
        {
            "day": date_strings,
            "weekday": calendar.loc[holdout_index, "weekday"].to_numpy(),
            "actual": daily_actual,
            "baseline": daily_baseline,
            "lgbm": daily_lgbm,
        }
    )
    print(daily.to_string(index=False))

    # Highest-volume item on training days only. Holdout units are not in this sum.
    train_units = sales[:, : LAST_TRAIN_INDEX + 1].sum(axis=1)
    best_pos = int(np.argmax(train_units))
    best_item = str(item_ids[best_pos])
    best_dept = str(dept_ids[best_pos])
    print(f"Excel item: {best_item} dept {best_dept} train units {int(train_units[best_pos])}")
    print(f"Excel item holdout units {int(sales[best_pos, holdout_index].sum())}")

    item_actual = sales[best_pos, holdout_index]
    item_baseline = sales[best_pos, holdout_index - 28]
    item_lgbm = lgbm.reshape(n_items, HORIZON)[best_pos]
    item_weekday = calendar.loc[holdout_index, "weekday"].to_numpy()
    item_metrics = pd.DataFrame(
        score_block(item_actual, item_baseline, item_weekday, "baseline_lag28")
        + score_block(item_actual, item_lgbm, item_weekday, "lightgbm")
    )
    # The one-item sheet only needs the overall row; weekday is in the main metrics file.
    item_metrics_overall = item_metrics.loc[item_metrics["slice"] == "overall"].copy()
    source_index = holdout_index - HORIZON
    save_excel(
        best_item,
        best_dept,
        float(train_units[best_pos]),
        item_actual,
        calendar.loc[holdout_index, "date"].reset_index(drop=True),
        calendar.loc[holdout_index, "weekday"].reset_index(drop=True),
        calendar.loc[holdout_index, "snap_CA"].reset_index(drop=True),
        item_baseline,
        item_lgbm,
        calendar.loc[source_index, "date"].reset_index(drop=True),
        calendar.loc[source_index, "weekday"].reset_index(drop=True),
        sales[best_pos, source_index],
        item_metrics_overall,
    )
    print(f"Wrote {pred_path}")
    print(f"Wrote {metrics_path}")
    print(f"Wrote {IMG / 'ca3_foods_forecast_vs_actual.png'}")
    print(f"Wrote {IMG / 'ca3_foods_daily_error.png'}")
    print(f"Wrote {REPORTS / 'ca3_foods_one_item_forecast.xlsx'}")
    print(f"Trees {n_trees} negative_clipped {n_negative}")


if __name__ == "__main__":
    main()
