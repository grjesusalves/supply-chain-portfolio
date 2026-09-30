#!/usr/bin/env python3
"""Construct stage: late-delivery baselines and two classifiers.

Fits the two baselines the plan required, then a logistic regression and
one random forest. Scores them on held-out orders. Does not pick a
threshold, a dollar cost, or a dashboard. Those belong to Execute.

Run from the repo root:
    python 03-late-delivery-risk/src/construct_late_delivery.py

Run from the project folder (03-late-delivery-risk):
    python src/construct_late_delivery.py

Needs pandas, numpy, matplotlib, and scikit-learn. This run used
scikit-learn 1.9.1. If `import sklearn` fails:

    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install scikit-learn
    .venv/bin/python src/construct_late_delivery.py

Paths are anchored to this file, not to the shell's current directory.

Input (git-ignored, already on disk; this script does not copy it):
    03-late-delivery-risk/data/raw/DataCoSupplyChainDataset.csv
    Latin-1. tokenized_access_logs.csv is a different question and is not read.

Outputs under 03-late-delivery-risk/:
    data/processed/construct_*.csv   small aggregate tables only
    images/test_auc_ap_by_model.png

No output is row-level. Names, email, password, and street are not written.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save a file; do not open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Anchored to this file so a run from the repo root and a run from the
# project folder write the same place. parents[1] is 03-late-delivery-risk.
PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw" / "DataCoSupplyChainDataset.csv"
PROC = PROJECT / "data" / "processed"
IMG = PROJECT / "images"

# The plan's expected shape. A different extract is a different question.
EXPECTED_ROWS = 180_519
EXPECTED_COLS = 53
# Analyze counted this population. The script stops if the filter drifts.
EXPECTED_KPI_LINES = 172_765
EXPECTED_KPI_LATE = 98_977

# Delivery Status value the plan removes from the denominator.
# A cancel is not an on-time delivery and not a late delivery.
CANCELED = "Shipping canceled"

# One split, fixed before any score is read. test_size is the share of
# Order Id values, not the share of lines. Lines follow the orders.
TEST_SIZE = 0.2
RANDOM_STATE = 42

# Logistic penalty. In scikit-learn 1.8+ l1_ratio 0 is L2 (ridge).
# C=1 is the library default. It is not tuned on the test set.
# L2 is why a shipping mode that is always late still gets a finite
# coefficient: the unpenalized MLE would run off to infinity.
LOGISTIC_C = 1.0
LOGISTIC_L1_RATIO = 0.0
LOGISTIC_MAX_ITER = 2000

# One tree model, not a search. 200 trees and a 50-line leaf are fixed
# here, before the test score exists. n_jobs is 1 so a second run on the
# same file does not move an importance by a parallel reduction order.
RF_TREES = 200
RF_MIN_LEAF = 50

# Personal-data columns. They are not features, and a public portfolio
# file should not carry them. The save helper refuses these names.
PII_COLUMNS = (
    "Customer Fname",
    "Customer Lname",
    "Customer Email",
    "Customer Password",
    "Customer Street",
)

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
DOWS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

# The model matrix. Shipping Mode is the promise. Scheduled days are not
# here: they are a 1:1 relabel of the mode (Same Day 0, First Class 1,
# Second Class 2, Standard Class 4), and putting both in the logistic
# model would double-count one fact.
# Order Region, not Market: Market is the rollup of region, and 23
# regions is a one-hot a logistic model can carry. Using both would
# double-count the place.
# Category Name, not Department Name: department is the rollup of
# category. 50 categories is still a one-hot, not a huge one. The one
# name that sits in two departments (Electronics) is not a reason to
# encode both hierarchies.
CAT_COLS = [
    "Shipping Mode",
    "Order Region",
    "Category Name",
    "Customer Segment",
    "order_month",
    "order_dow",
]
# Quantity, unit price, dollar discount. Sales, the other price column,
# the discount rate, and the line total are the same facts rewritten.
# The redundancy check below stops the script if that identity breaks.
NUM_COLS = [
    "Order Item Quantity",
    "Order Item Product Price",
    "Order Item Discount",
]

# Reference level for Shipping Mode. Standard Class is the largest mode
# and the one whose promise is usually met, so a coefficient is the
# change versus that promise, not versus an alphabetical accident.
MODE_REFERENCE = "Standard Class"


def load_raw(path: Path) -> pd.DataFrame:
    """Read the order-line file as Latin-1 and refuse a different shape.

    UTF-8 is tried first only to prove it is the wrong codec. The bytes
    include Latin-1 characters. A UTF-8 read fails, which is why the data
    note specifies latin-1. The frame that is modeled is the Latin-1 read.
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
    return df


def kpi_population(df: pd.DataFrame) -> pd.DataFrame:
    """Non-canceled lines, and stop if the flag no longer matches the days.

    The target stays Late_delivery_risk. On this population Analyze found
    it equals real days > scheduled days, with zero disagreements. Canceled
    lines are the only disagreements, and the flag marks every one of them
    0. They stay out of training and scoring. Real days are used here as a
    check, then they are not a feature.
    """
    kpi = df[df["Delivery Status"] != CANCELED].copy()
    if len(kpi) != EXPECTED_KPI_LINES:
        raise SystemExit(f"KPI lines changed: {len(kpi)}")
    slip = kpi["Days for shipping (real)"] - kpi["Days for shipment (scheduled)"]
    day_late = (slip > 0).astype(int)
    disagreements = int((kpi["Late_delivery_risk"].to_numpy() != day_late.to_numpy()).sum())
    if disagreements != 0:
        raise SystemExit(
            "flag and real>scheduled disagree on non-canceled lines; "
            "do not fit a model until the target is rewritten"
        )
    late = int(kpi["Late_delivery_risk"].sum())
    if late != EXPECTED_KPI_LATE:
        raise SystemExit(f"KPI late lines changed: {late}")
    # Shipping mode and scheduled days are one fact. Both columns in X
    # would be the same dummy twice. Refuse to continue if a mode grows
    # a second scheduled value.
    pairs = (
        kpi.groupby("Shipping Mode", sort=False)["Days for shipment (scheduled)"]
        .nunique()
    )
    if int(pairs.max()) != 1 or kpi["Shipping Mode"].nunique() != 4:
        raise SystemExit("scheduled days are no longer a relabel of Shipping Mode")
    return kpi


def add_calendar(kpi: pd.DataFrame) -> pd.DataFrame:
    """Month and day of week from the order timestamp only.

    The shipping timestamp is the outcome clock: Analyze showed its
    calendar-day gap equals real days on every row. It is not parsed here.
    Month and weekday are categories, not integers, so December is not
    treated as twelve times January.
    """
    parsed = pd.to_datetime(
        kpi["order date (DateOrders)"],
        format="%m/%d/%Y %H:%M",
        errors="coerce",
    )
    if parsed.isna().any():
        raise SystemExit("order date did not match %m/%d/%Y %H:%M")
    out = kpi.copy()
    out["order_month"] = parsed.dt.month.map(lambda m: MONTHS[m - 1])
    out["order_dow"] = parsed.dt.dayofweek.map(lambda d: DOWS[d])
    return out


def redundancy_tables(kpi: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Show why some allowed columns are still left out of X.

    These are identities on the KPI population, not model scores. A later
    extract that breaks an identity should stop rather than drop a column
    that has become a second measurement.
    """
    sales_vs_qty_price = (
        kpi["Sales"] - kpi["Order Item Quantity"] * kpi["Order Item Product Price"]
    ).abs()
    total_vs_net = (
        kpi["Order Item Total"] - (kpi["Sales"] - kpi["Order Item Discount"])
    ).abs()
    rate_vs_ratio = (
        kpi["Order Item Discount Rate"] - kpi["Order Item Discount"] / kpi["Sales"]
    ).abs()
    price_gap = (kpi["Product Price"] - kpi["Order Item Product Price"]).abs()
    pay_gap = (kpi["Sales per customer"] - kpi["Order Item Total"]).abs()

    checks = pd.DataFrame(
        [
            {
                "check": "product_price_vs_order_item_product_price",
                "max_abs_diff": float(price_gap.max()),
                "lines": int(len(kpi)),
                "kept_column": "Order Item Product Price",
                "why": "identical on this population; one price column",
            },
            {
                "check": "sales_vs_quantity_times_price",
                "max_abs_diff": float(sales_vs_qty_price.max()),
                "lines": int(len(kpi)),
                "kept_column": "Order Item Quantity and Order Item Product Price",
                "why": "Sales is quantity times price, up to float noise",
            },
            {
                "check": "sales_per_customer_vs_order_item_total",
                "max_abs_diff": float(pay_gap.max()),
                "lines": int(len(kpi)),
                "kept_column": "neither; net of discount is price, quantity, discount",
                "why": "the two pay columns are the same number",
            },
            {
                "check": "order_item_total_vs_sales_minus_discount",
                "max_abs_diff": float(total_vs_net.max()),
                "lines": int(len(kpi)),
                "kept_column": "Order Item Discount",
                "why": "line total is sales minus the dollar discount, to the cent",
            },
            {
                "check": "discount_rate_vs_discount_over_sales",
                "max_abs_diff": float(rate_vs_ratio.max()),
                "lines": int(len(kpi)),
                "kept_column": "Order Item Discount",
                "why": "the rate is the dollar discount over sales, up to rounding",
            },
        ]
    )
    if float(price_gap.max()) != 0.0 or float(pay_gap.max()) != 0.0:
        raise SystemExit("a price or pay column diverged; do not drop it")
    if float(sales_vs_qty_price.max()) > 0.01:
        raise SystemExit("Sales is not quantity times price; do not treat them as one fact")
    if float(total_vs_net.max()) > 0.02:
        raise SystemExit("line total is not sales minus discount; do not drop it")
    if float(rate_vs_ratio.max()) > 0.01:
        raise SystemExit("discount rate is not discount over sales; do not drop it")

    # Cardinality on the KPI population, which is the one-hot the model
    # would actually build. City and state are huge. Product name and
    # country are long enough to memorize rare levels next to category
    # and region, which already carry type and place.
    card_cols = [
        ("Shipping Mode", "kept"),
        ("Order Region", "kept"),
        ("Market", "dropped; rollup of Order Region"),
        ("Category Name", "kept"),
        ("Department Name", "dropped; rollup of Category Name"),
        ("Customer Segment", "kept"),
        ("Product Name", "dropped; long one-hot beside category"),
        ("Order Country", "dropped; long one-hot beside region"),
        ("Order City", "dropped; huge one-hot"),
        ("Order State", "dropped; huge one-hot"),
        (
            "Order Status",
            "dropped; CANCELED and SUSPECTED_FRAUD are exactly Shipping canceled",
        ),
    ]
    card_rows = []
    for col, decision in card_cols:
        card_rows.append(
            {
                "column_name": col,
                "distinct_values_kpi": int(kpi[col].nunique(dropna=False)),
                "decision": decision,
            }
        )
    cardinality = pd.DataFrame(card_rows)

    # Department is the rollup, except one category name in two departments.
    # That exception is recorded. It is not a reason to one-hot both.
    nunique_dept = kpi.groupby("Category Name", sort=False)["Department Name"].nunique()
    broken = nunique_dept[nunique_dept > 1]
    if len(broken) != 1 or broken.index[0] != "Electronics":
        raise SystemExit(f"category/department nesting changed: {list(broken.index)}")
    elec = (
        kpi.loc[kpi["Category Name"] == "Electronics"]
        .groupby("Department Name", sort=False)
        .agg(lines=("Late_delivery_risk", "size"), late_lines=("Late_delivery_risk", "sum"))
        .reset_index()
    )
    elec.insert(0, "Category Name", "Electronics")
    elec["late_lines"] = elec["late_lines"].astype(int)
    elec["lines"] = elec["lines"].astype(int)
    return checks, cardinality, elec


def most_frequent(series: pd.Series) -> str:
    """Training mode of a column. Ties break on the sorted label, not on row order."""
    counts = series.value_counts(dropna=False)
    top = counts.max()
    names = sorted((str(v) for v in counts[counts == top].index))
    return names[0]


def category_lists(train: pd.DataFrame) -> dict[str, list[str]]:
    """Put the reference level first. OneHotEncoder drop='first' drops it.

    Levels are learned on the training orders only. A test level that
    never appeared in training is not added here; the encoder maps it to
    the reference (all zeros) and the unseen-count table records it.
    Shipping Mode's reference is Standard Class on purpose. The other
    references are the most common training level, so a coefficient is
    versus the usual case rather than versus an arbitrary alphabet level.
    """
    lists: dict[str, list[str]] = {}
    lists["Shipping Mode"] = [MODE_REFERENCE] + sorted(
        str(v) for v in train["Shipping Mode"].unique() if str(v) != MODE_REFERENCE
    )
    for col in CAT_COLS:
        if col == "Shipping Mode":
            continue
        ref = most_frequent(train[col])
        rest = sorted(str(v) for v in train[col].unique() if str(v) != ref)
        lists[col] = [ref] + rest
    return lists


def make_matrix(cat_lists: dict[str, list[str]], drop_reference: bool, scale: bool):
    """One design matrix.

    Logistic drops the reference level. Without that drop the mode dummies
    and the intercept are the same column twice, and the coefficient is
    not 'versus Standard Class'. The tree keeps every level, because a
    dropped level would hide that level in the importance list.

    Numeric columns are scaled for the logistic model only, and the scaler
    is fit on training rows inside the pipeline. A price coefficient is
    then per training standard deviation, which is comparable to a 0/1
    mode switch. The tree splits on the raw units; scaling would not
    change its cuts and would make the raw importance harder to name.
    """
    encoder = OneHotEncoder(
        categories=[cat_lists[c] for c in CAT_COLS],
        drop="first" if drop_reference else None,
        handle_unknown="ignore",
        sparse_output=False,
        dtype=np.float64,
    )
    numeric = StandardScaler() if scale else "passthrough"
    pre = ColumnTransformer(
        transformers=[
            ("cat", encoder, CAT_COLS),
            ("num", numeric, NUM_COLS),
        ],
        remainder="drop",
    )
    return pre


def unseen_categories(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Test levels that were not in training. They are coded as the reference."""
    rows = []
    for col in CAT_COLS:
        known = set(train[col].astype(str))
        test_values = test[col].astype(str)
        mask = ~test_values.isin(known)
        n = int(mask.sum())
        rows.append(
            {
                "column_name": col,
                "test_lines_with_unseen_level": n,
                "unseen_levels": int(test_values[mask].nunique()) if n else 0,
            }
        )
    return pd.DataFrame(rows)


def top_share_mask(scores: np.ndarray, share: float, tie: np.ndarray) -> tuple[np.ndarray, int]:
    """Flag the top share of scores. Ties do not look at the label.

    k is round-half-up of share times the test line count. The share is
    the training late rate, so every model is asked to flag about as many
    lines as were late in training. That is not an operating threshold.
    Execute still has to pick one.

    Equal scores are ordered by a seeded shuffle (tie), not by Order Id
    and not by the late flag. Order Id can follow time. Using it as the
    tie-break would pretend a smaller id is a risk score. Inside one
    shipping mode the mode baseline has a single score, so this cutoff
    slices that mode. The slice is arbitrary. The baseline cannot rank
    inside a mode.
    """
    n = len(scores)
    k = int(np.floor(share * n + 0.5))
    if k < 0:
        k = 0
    if k > n:
        k = n
    # lexsort: last key is primary. Higher score first, then the seeded tie.
    order = np.lexsort((tie, -np.asarray(scores, dtype=float)))
    mask = np.zeros(n, dtype=bool)
    if k:
        mask[order[:k]] = True
    return mask, k


def score_block(
    name: str,
    y_true: np.ndarray,
    scores: np.ndarray,
    train_late_rate: float,
    tie: np.ndarray,
) -> tuple[dict, dict]:
    """Test-set ranking scores and the two recalls. No accuracy.

    Recall at 0.5 treats the score as a probability and flags scores at
    or above one half. The rate-matched recall flags the top training-late-rate
    share instead, so a constant score of 0.57 is not rewarded for sitting
    above 0.5. Both are descriptions. Neither is the threshold Execute will use.
    """
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    late = int(y_true.sum())
    if late == 0 or late == len(y_true):
        raise SystemExit(f"{name}: test set has one class; AUC is undefined")
    pred = scores >= 0.5
    tp = int(np.sum(pred & (y_true == 1)))
    fp = int(np.sum(pred & (y_true == 0)))
    fn = int(np.sum(~pred & (y_true == 1)))
    tn = int(np.sum(~pred & (y_true == 0)))
    mask, k = top_share_mask(scores, train_late_rate, tie)
    tp_k = int(np.sum(mask & (y_true == 1)))
    metrics = {
        "model": name,
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "average_precision": float(average_precision_score(y_true, scores)),
        "recall_at_0_5": tp / late,
        "tp_at_0_5": tp,
        "fp_at_0_5": fp,
        "fn_at_0_5": fn,
        "tn_at_0_5": tn,
        "flagged_at_0_5": int(pred.sum()),
        "late_lines": late,
        "test_lines": int(len(y_true)),
        "recall_at_rate_matched": tp_k / late,
        "tp_at_rate_matched": tp_k,
        "flagged_at_rate_matched": k,
    }
    confusion = {
        "model": name,
        "threshold": 0.5,
        "note": "not the decision; Execute picks the threshold",
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
    }
    return metrics, confusion


def by_mode_rows(
    name: str,
    modes: np.ndarray,
    y_true: np.ndarray,
    scores: np.ndarray,
    mask_matched: np.ndarray,
) -> list[dict]:
    """How each model treats the four promises on the test lines.

    First Class does not vary, so ROC AUC inside it is undefined. The
    mode baseline has one score per mode, so its within-mode AUC is 0.5
    wherever both classes exist: it cannot order two lines that share a
    mode. A real model beats the mode only if it ranks inside the modes
    that still vary.
    """
    rows = []
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    for mode in ["First Class", "Second Class", "Same Day", "Standard Class"]:
        sel = modes == mode
        y = y_true[sel]
        s = scores[sel]
        late = int(y.sum())
        lines = int(sel.sum())
        pred = s >= 0.5
        both = late not in (0, lines)
        rows.append(
            {
                "model": name,
                "shipping_mode": mode,
                "test_lines": lines,
                "test_late_lines": late,
                "test_late_rate": late / lines if lines else np.nan,
                "mean_score": float(s.mean()) if lines else np.nan,
                "flagged_at_0_5": int(pred.sum()),
                "tp_at_0_5": int(np.sum(pred & (y == 1))),
                "recall_at_0_5": (int(np.sum(pred & (y == 1))) / late) if late else np.nan,
                "flagged_at_rate_matched": int(mask_matched[sel].sum()),
                "tp_at_rate_matched": int(np.sum(mask_matched[sel] & (y == 1))),
                "recall_at_rate_matched": (
                    int(np.sum(mask_matched[sel] & (y == 1))) / late
                )
                if late
                else np.nan,
                "roc_auc": float(roc_auc_score(y, s)) if both else np.nan,
                "average_precision": float(average_precision_score(y, s)) if both else np.nan,
            }
        )
    return rows


def split_feature_name(name: str) -> tuple[str, str]:
    """Map a transformed column back to the original field and the level."""
    for col in sorted(CAT_COLS, key=len, reverse=True):
        prefix = col + "_"
        if name.startswith(prefix):
            return col, name[len(prefix) :]
    if name in NUM_COLS:
        return name, ""
    raise SystemExit(f"unexpected feature name: {name}")


def save_csv(df: pd.DataFrame, name: str) -> Path:
    """Write one aggregate CSV and refuse personal-data column names.

    A row count near the raw file size means a line-level extract leaked.
    Predictions are not saved. The metrics tables are small on purpose.
    """
    blocked = set(PII_COLUMNS)
    hit = blocked.intersection(df.columns)
    if hit:
        raise SystemExit(f"{name} would write personal data columns: {sorted(hit)}")
    if len(df) > 5000:
        raise SystemExit(f"{name} has {len(df)} rows; refusing a line-level extract")
    path = PROC / name
    df.to_csv(path, index=False)
    return path


def save_chart(metrics: pd.DataFrame) -> None:
    """ROC AUC and average precision for the four models, test set only.

    The bar labels are rounded to three decimals so they fit. The CSV and
    the report keep the unrounded scores. This chart is not a threshold.
    """
    IMG.mkdir(parents=True, exist_ok=True)
    order = [
        "majority_baseline",
        "shipping_mode_baseline",
        "logistic_regression",
        "random_forest",
    ]
    labels = [
        "Majority\nbaseline",
        "Shipping-mode\nbaseline",
        "Logistic\nregression",
        "Random\nforest",
    ]
    plot = metrics.set_index("model").loc[order]
    x = np.arange(len(order))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    b1 = ax.bar(x - width / 2, plot["roc_auc"].to_numpy(), width=width, label="ROC AUC")
    b2 = ax.bar(
        x + width / 2,
        plot["average_precision"].to_numpy(),
        width=width,
        label="Average precision",
    )
    for bars in (b1, b2):
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.015,
                f"{height:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Test score")
    # The mode baseline has four distinct scores. Its average precision
    # steps once per mode, which is a harsher reading of a tie than a
    # ranking inside the mode. The report says so. The labels here are
    # still the unadjusted test scores, rounded to three decimals.
    ax.set_title("Test ROC AUC and average precision")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(IMG / "test_auc_ap_by_model.png", dpi=120)
    plt.close(fig)


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    raw = load_raw(RAW)
    kpi = add_calendar(kpi_population(raw))
    checks, cardinality, elec = redundancy_tables(kpi)

    # y and the group id are taken off before the matrix is built so a
    # later column list cannot pull the target back in. Delivery Status,
    # real days, the shipping date, and Order Status are not in CAT_COLS
    # or NUM_COLS. Order Status is out because CANCELED and SUSPECTED_FRAUD
    # are exactly the Shipping canceled lines: the column encodes the
    # delivery outcome the filter already removed. The remaining statuses
    # are process states, not on the plan's order-time list.
    y = kpi["Late_delivery_risk"].to_numpy().astype(int)
    groups = kpi["Order Id"].to_numpy()
    modes = kpi["Shipping Mode"].to_numpy()
    banned_in_x = {
        "Late_delivery_risk",
        "Delivery Status",
        "Days for shipping (real)",
        "shipping date (DateOrders)",
        "Days for shipment (scheduled)",
        "Order Status",
        "Market",
        "Department Name",
        "Product Name",
        "Order City",
        "Order State",
        "Order Country",
        *PII_COLUMNS,
    }
    if banned_in_x.intersection(CAT_COLS + NUM_COLS):
        raise SystemExit("feature list contains a banned column")

    # Grouped split: lines on one order share the late flag. A random line
    # split would put one line of an order in train and another in test,
    # and the model would be scored on an order it had already seen.
    # test_size 0.2 is 20 percent of orders. The line count is whatever
    # those orders contain.
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )
    train_idx, test_idx = next(splitter.split(kpi, y, groups))
    train = kpi.iloc[train_idx]
    test = kpi.iloc[test_idx]
    y_train = y[train_idx]
    y_test = y[test_idx]
    overlap = set(train["Order Id"]).intersection(set(test["Order Id"]))
    if overlap:
        raise SystemExit(f"order leaked across the split: {len(overlap)} orders")

    train_lines = int(len(train))
    test_lines = int(len(test))
    train_orders = int(train["Order Id"].nunique())
    test_orders = int(test["Order Id"].nunique())
    train_late = int(y_train.sum())
    test_late = int(y_test.sum())
    if train_late == train_lines - train_late:
        raise SystemExit("training late count ties on-time; majority label is undefined")
    majority_label = 1 if train_late > (train_lines - train_late) else 0
    train_late_rate = train_late / train_lines

    # Same tie-break for every model. Seeded once, from the test length.
    tie = np.random.RandomState(RANDOM_STATE).permutation(test_lines)

    # --- 1. Majority-class baseline ---------------------------------------
    # Hard label: the training majority, for every test line. Ranking
    # score: the training late rate, a constant. ROC AUC of a constant is
    # 0.5. Average precision of a constant is the test late rate. Recall
    # at 0.5 is 1 when that constant sits above 0.5, which is every line
    # flagged, not a ranking.
    majority_scores = np.full(test_lines, train_late_rate, dtype=float)

    # --- 2. Shipping-mode baseline ----------------------------------------
    # Late rate of each mode on TRAINING rows only, applied to test.
    # This is the bar. If the other models cannot beat it, the other
    # features are not adding an operational signal.
    mode_rows = []
    rate_map = {}
    for mode, sub in train.groupby("Shipping Mode", sort=False):
        lines = int(len(sub))
        late = int(sub["Late_delivery_risk"].sum())
        rate_map[mode] = late / lines
        mode_rows.append(
            {
                "shipping_mode": mode,
                "train_lines": lines,
                "train_late_lines": late,
                "train_late_rate": late / lines,
            }
        )
    mode_table = pd.DataFrame(mode_rows)
    test_mode_rows = []
    for mode, sub in test.groupby("Shipping Mode", sort=False):
        lines = int(len(sub))
        late = int(sub["Late_delivery_risk"].sum())
        test_mode_rows.append(
            {
                "shipping_mode": mode,
                "test_lines": lines,
                "test_late_lines": late,
                "test_late_rate": late / lines,
            }
        )
    mode_table = mode_table.merge(pd.DataFrame(test_mode_rows), on="shipping_mode", how="outer")
    missing_mode = ~test["Shipping Mode"].isin(rate_map)
    if missing_mode.any():
        raise SystemExit("test mode was absent from training; baseline has no rate")
    mode_scores = test["Shipping Mode"].map(rate_map).to_numpy(dtype=float)

    # --- 3. Logistic regression -------------------------------------------
    # Reference levels from training only. Standard Class is fixed.
    cat_lists = category_lists(train)
    references = pd.DataFrame(
        [{"column_name": col, "reference_level": levels[0]} for col, levels in cat_lists.items()]
    )
    unseen = unseen_categories(train, test)

    log_pre = make_matrix(cat_lists, drop_reference=True, scale=True)
    logistic = LogisticRegression(
        C=LOGISTIC_C,
        l1_ratio=LOGISTIC_L1_RATIO,
        solver="lbfgs",
        max_iter=LOGISTIC_MAX_ITER,
        random_state=RANDOM_STATE,
    )
    log_pipe = Pipeline([("pre", log_pre), ("model", logistic)])
    log_pipe.fit(train, y_train)
    if logistic.n_iter_.max() >= LOGISTIC_MAX_ITER:
        raise SystemExit("logistic regression did not converge")
    log_scores = log_pipe.predict_proba(test)[:, 1]

    feature_names = list(log_pipe.named_steps["pre"].get_feature_names_out())
    coefs = logistic.coef_.ravel()
    if len(feature_names) != len(coefs):
        raise SystemExit("coefficient vector does not match the design matrix")
    scaler = log_pipe.named_steps["pre"].named_transformers_["num"]
    scaling_rows = []
    for col, mean, scale in zip(NUM_COLS, scaler.mean_, scaler.scale_):
        scaling_rows.append(
            {
                "column_name": col,
                "train_mean": float(mean),
                "train_scale": float(scale),
                "note": "logistic coefficient is per one training standard deviation",
            }
        )
    scaling = pd.DataFrame(scaling_rows)

    coef_rows = [
        {
            "feature": "(intercept)",
            "source_column": "(intercept)",
            "level": "",
            "coefficient": float(logistic.intercept_[0]),
            "odds_ratio": float(np.exp(logistic.intercept_[0])),
            "abs_coefficient": abs(float(logistic.intercept_[0])),
            "is_shipping_mode": 0,
        }
    ]
    for name, coef in zip(feature_names, coefs):
        # ColumnTransformer prefixes cat__ and num__. Strip those, then
        # split the one-hot name into the original column and the level.
        raw_name = name.split("__", 1)[1]
        source, level = split_feature_name(raw_name)
        coef_rows.append(
            {
                "feature": raw_name,
                "source_column": source,
                "level": level,
                "coefficient": float(coef),
                "odds_ratio": float(np.exp(coef)),
                "abs_coefficient": abs(float(coef)),
                "is_shipping_mode": int(source == "Shipping Mode"),
            }
        )
    coefficients = pd.DataFrame(coef_rows)

    # --- 4. Random forest -------------------------------------------------
    # One tree model. A forest, not gradient boosting: the plan asked for
    # interactions a single coefficient misses, and a forest's impurity
    # importance does not need a learning rate or a tree-count search.
    # This stage is not a tuning study and it does not add a fifth model.
    # No XGBoost. The full one-hot (no dropped reference) is what the
    # importance list reads. Numeric columns stay in raw units.
    rf_pre = make_matrix(cat_lists, drop_reference=False, scale=False)
    forest = RandomForestClassifier(
        n_estimators=RF_TREES,
        min_samples_leaf=RF_MIN_LEAF,
        max_features="sqrt",
        bootstrap=True,
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    rf_pipe = Pipeline([("pre", rf_pre), ("model", forest)])
    rf_pipe.fit(train, y_train)
    rf_scores = rf_pipe.predict_proba(test)[:, 1]
    rf_names = list(rf_pipe.named_steps["pre"].get_feature_names_out())
    importances = rf_pipe.named_steps["model"].feature_importances_
    if len(rf_names) != len(importances):
        raise SystemExit("importance vector does not match the design matrix")
    if abs(float(importances.sum()) - 1.0) > 1e-6:
        raise SystemExit("feature importances do not sum to 1")
    imp_rows = []
    for name, imp in zip(rf_names, importances):
        raw_name = name.split("__", 1)[1]
        source, level = split_feature_name(raw_name)
        imp_rows.append(
            {
                "feature": raw_name,
                "source_column": source,
                "level": level,
                "importance": float(imp),
            }
        )
    importance = pd.DataFrame(imp_rows).sort_values(
        ["importance", "feature"], ascending=[False, True]
    )
    importance.insert(0, "rank", np.arange(1, len(importance) + 1))
    # Summing dummies puts Shipping Mode back together. The sum favors a
    # column with more levels, because impurity can be spent across more
    # cuts. The row-level ranking above is the one that shows a single
    # mode. The grouped table is only the rollup.
    grouped = (
        importance.groupby("source_column", sort=False)["importance"]
        .sum()
        .reset_index()
        .sort_values(["importance", "source_column"], ascending=[False, True])
    )
    grouped.insert(0, "rank", np.arange(1, len(grouped) + 1))

    # --- Metrics on the TEST lines only -----------------------------------
    metric_rows = []
    confusion_rows = []
    by_mode = []
    score_book = [
        ("majority_baseline", majority_scores),
        ("shipping_mode_baseline", mode_scores),
        ("logistic_regression", log_scores),
        ("random_forest", rf_scores),
    ]
    for name, scores in score_book:
        metrics, confusion = score_block(name, y_test, scores, train_late_rate, tie)
        mask, k_check = top_share_mask(scores, train_late_rate, tie)
        if k_check != metrics["flagged_at_rate_matched"]:
            raise SystemExit("rate-matched count drifted")
        metric_rows.append(metrics)
        confusion_rows.append(confusion)
        by_mode.extend(by_mode_rows(name, test["Shipping Mode"].to_numpy(), y_test, scores, mask))
    metrics_df = pd.DataFrame(metric_rows)
    mode_auc = float(
        metrics_df.loc[metrics_df["model"] == "shipping_mode_baseline", "roc_auc"].iloc[0]
    )
    mode_ap = float(
        metrics_df.loc[
            metrics_df["model"] == "shipping_mode_baseline", "average_precision"
        ].iloc[0]
    )
    mode_r05 = float(
        metrics_df.loc[metrics_df["model"] == "shipping_mode_baseline", "recall_at_0_5"].iloc[0]
    )
    mode_rm = float(
        metrics_df.loc[
            metrics_df["model"] == "shipping_mode_baseline", "recall_at_rate_matched"
        ].iloc[0]
    )
    metrics_df["auc_minus_mode_baseline"] = metrics_df["roc_auc"] - mode_auc
    metrics_df["ap_minus_mode_baseline"] = metrics_df["average_precision"] - mode_ap
    metrics_df["recall_0_5_minus_mode_baseline"] = metrics_df["recall_at_0_5"] - mode_r05
    metrics_df["recall_matched_minus_mode_baseline"] = (
        metrics_df["recall_at_rate_matched"] - mode_rm
    )

    # The mode baseline has one score per mode, so thousands of test lines
    # are tied. roc_auc_score and average_precision_score step once per
    # distinct score. For average precision that step uses the precision
    # after the whole tie, which is the same number you get by counting
    # the on-time lines in the mode before the late ones. A model that
    # only jitters inside the mode, without reordering the modes, gets a
    # higher average precision from that convention alone. The shuffle
    # below is the same seeded tie-break as the rate-matched cutoff. It
    # does not use the label. The jitter is half the smallest gap between
    # mode scores, so a Standard Class line cannot pass a Same Day line.
    distinct = np.sort(np.unique(mode_scores))
    mode_gap = float(np.diff(distinct).min())
    jitter = (tie.astype(float) + 1.0) / (test_lines + 1.0) * (mode_gap * 0.5)
    shaken = mode_scores + jitter
    for higher in distinct[1:]:
        lower_max = float(shaken[mode_scores < higher].max()) if np.any(mode_scores < higher) else -np.inf
        higher_min = float(shaken[mode_scores == higher].min())
        if higher_min <= lower_max:
            raise SystemExit("within-mode shuffle reordered the modes")
    tie_sensitivity = pd.DataFrame(
        [
            {
                "scoring": "ties_kept",
                "roc_auc": float(roc_auc_score(y_test, mode_scores)),
                "average_precision": float(average_precision_score(y_test, mode_scores)),
                "note": "one step per shipping mode; this is the published baseline",
            },
            {
                "scoring": "within_mode_seeded_shuffle",
                "roc_auc": float(roc_auc_score(y_test, shaken)),
                "average_precision": float(average_precision_score(y_test, shaken)),
                "note": "modes stay in the same order; lines inside a mode are shuffled with random_state 42",
            },
        ]
    )

    split_df = pd.DataFrame(
        [
            {
                "population_lines": EXPECTED_KPI_LINES,
                "population_late_lines": EXPECTED_KPI_LATE,
                "population_late_rate": EXPECTED_KPI_LATE / EXPECTED_KPI_LINES,
                "train_lines": train_lines,
                "test_lines": test_lines,
                "train_orders": train_orders,
                "test_orders": test_orders,
                "train_late_lines": train_late,
                "test_late_lines": test_late,
                "train_on_time_lines": train_lines - train_late,
                "test_on_time_lines": test_lines - test_late,
                "train_late_rate": train_late_rate,
                "test_late_rate": test_late / test_lines,
                "overlapping_orders": 0,
                "test_size_param": TEST_SIZE,
                "test_size_means": "share of Order Id values",
                "random_state": RANDOM_STATE,
                "majority_label": majority_label,
                "rate_matched_flagged": int(metrics_df["flagged_at_rate_matched"].iloc[0]),
                "rate_matched_share": int(metrics_df["flagged_at_rate_matched"].iloc[0])
                / test_lines,
            }
        ]
    )
    run_df = pd.DataFrame(
        [
            {
                "sklearn_version": __import__("sklearn").__version__,
                "logistic_C": LOGISTIC_C,
                "logistic_l1_ratio": LOGISTIC_L1_RATIO,
                "logistic_penalty": "L2 (l1_ratio 0)",
                "logistic_max_iter": LOGISTIC_MAX_ITER,
                "logistic_n_iter": int(logistic.n_iter_.max()),
                "rf_trees": RF_TREES,
                "rf_min_samples_leaf": RF_MIN_LEAF,
                "rf_max_features": "sqrt",
                "random_state": RANDOM_STATE,
            }
        ]
    )

    written = [
        save_csv(split_df, "construct_split.csv"),
        save_csv(metrics_df, "construct_metrics.csv"),
        save_csv(pd.DataFrame(confusion_rows), "construct_confusion_0_5.csv"),
        save_csv(coefficients, "construct_coefficients.csv"),
        save_csv(importance, "construct_importances.csv"),
        save_csv(grouped, "construct_importances_grouped.csv"),
        save_csv(mode_table, "construct_mode_rates.csv"),
        save_csv(tie_sensitivity, "construct_mode_tie_sensitivity.csv"),
        save_csv(pd.DataFrame(by_mode), "construct_metrics_by_mode.csv"),
        save_csv(references, "construct_reference_levels.csv"),
        save_csv(scaling, "construct_numeric_scaling.csv"),
        save_csv(unseen, "construct_unseen_categories.csv"),
        save_csv(checks, "construct_feature_redundancy.csv"),
        save_csv(cardinality, "construct_cardinality_kpi.csv"),
        save_csv(elec, "construct_electronics_departments.csv"),
        save_csv(run_df, "construct_run.csv"),
    ]
    save_chart(metrics_df)

    for path in written:
        header = path.read_text(encoding="utf-8").splitlines()[0]
        for banned in PII_COLUMNS:
            if banned in header:
                raise SystemExit(f"{path.name} header contains {banned}")

    print(
        "confirmation "
        f"kpi={EXPECTED_KPI_LATE}/{EXPECTED_KPI_LINES} "
        f"train_lines={train_lines} test_lines={test_lines} "
        f"train_orders={train_orders} test_orders={test_orders} "
        f"train_late={train_late}/{train_lines} "
        f"test_late={test_late}/{test_lines} "
        f"files={len(written)} chart=1"
    )
    print(metrics_df.to_string(index=False))
    print(f"processed_dir={PROC}")
    print(f"images_dir={IMG}")


if __name__ == "__main__":
    main()
