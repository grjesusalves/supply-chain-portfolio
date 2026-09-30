#!/usr/bin/env python3
"""Analyze stage: Olist logistics network, distance, delivery time, freight.

This script checks the grain and writes the KPI tables. It does not build
the dashboard and it does not freeze distance bands. Those belong to Construct.

Run from the repo root:
    python 05-logistics-dashboard/src/analyze_logistics.py

Run from the project folder (05-logistics-dashboard):
    python src/analyze_logistics.py

Paths are anchored to this file, not to the shell's current directory.
data/raw/ is read relative to the project directory (the parent of src/).

Why a centroid:
    Geolocation has many points per zip prefix. The mean latitude and mean
    longitude are taken per prefix before any join. Joining the raw points
    would multiply items. The mean is the rule Plan locked. Missing prefixes
    are left missing. They are not filled with a state average, because a
    filled distance would invent the pattern this stage is measuring.

Why the grain:
    Freight and seller live on the order item, so freight versus distance
    stays on (order_id, order_item_id). The customer waits once, so
    purchase-to-door stays on the order. A multi-seller order uses the
    farthest item distance. Freight does not use that max.

Why delivered-only:
    Time and freight describe a completed delivery. The population is
    order_status = 'delivered', a delivered-to-customer timestamp present,
    and that timestamp after the purchase timestamp. Other statuses are
    counted and then left out of the medians.

Distance is haversine kilometers, earth radius 6371, between the customer
zip-prefix centroid and the seller zip-prefix centroid. Not road distance.

The executed SQL lives in sql/kpi_analyze.sql. This script loads the CSVs,
runs that file, and writes aggregate tables and charts. It does not commit.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# parents[1] is 05-logistics-dashboard, whether the shell is the repo root
# or the project folder.
PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw"
PROC = PROJECT / "data" / "processed"
IMG = PROJECT / "images"
SQL_PATH = PROJECT / "sql" / "kpi_analyze.sql"
DB_PATH = Path("/tmp/olist_logistics_analyze.sqlite")

# Inventory in data/README.md. The files win if these disagree.
EXPECTED = {
    "olist_customers_dataset.csv": (99441, 5),
    "olist_geolocation_dataset.csv": (1000163, 5),
    "olist_order_items_dataset.csv": (112650, 7),
    "olist_order_payments_dataset.csv": (103886, 5),
    "olist_order_reviews_dataset.csv": (99224, 7),
    "olist_orders_dataset.csv": (99441, 8),
    "olist_products_dataset.csv": (32951, 9),
    "olist_sellers_dataset.csv": (3095, 4),
    "product_category_name_translation.csv": (71, 2),
}

# Columns loaded into SQLite. City is not loaded. Reviews, payments, and the
# category translation are counted in the inventory check and not loaded.
# They do not answer this question.
LOAD = {
    "orders": (
        "olist_orders_dataset.csv",
        [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    ),
    "customers": (
        "olist_customers_dataset.csv",
        [
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_state",
        ],
    ),
    "sellers": (
        "olist_sellers_dataset.csv",
        ["seller_id", "seller_zip_code_prefix", "seller_state"],
    ),
    "items": (
        "olist_order_items_dataset.csv",
        ["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"],
    ),
    "products": (
        "olist_products_dataset.csv",
        ["product_id", "product_weight_g"],
    ),
    "geo": (
        "olist_geolocation_dataset.csv",
        ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
    ),
}

# Proposed bands. Right-open except the last, which holds the tail.
# 50 km is in 50-200. These are not frozen. See the report.
BANDS = ["0-50", "50-200", "200-500", "500-1000", "1000+"]
BAND_LABELS = ["0–50", "50–200", "200–500", "500–1,000", "1,000+"]

# Brazil box from Plan. Boundary is inside. Used only as a count, not a filter.
BRAZIL_LAT = (-34.0, 6.0)
BRAZIL_LNG = (-74.0, -32.0)


def inventory_counts():
    """Row counts with the csv module, so a quoted newline is not a new row."""
    rows = []
    for name, (exp_n, exp_c) in EXPECTED.items():
        path = RAW / name
        # utf-8-sig strips a BOM if one is present, without changing the row count.
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            n = sum(1 for _ in reader)
        rows.append(
            {
                "file": name,
                "rows": n,
                "columns": len(header),
                "expected_rows": exp_n,
                "expected_columns": exp_c,
                "match": n == exp_n and len(header) == exp_c,
            }
        )
    return rows


def load_tables(con):
    """Load the six tables the question needs, as TEXT, blank cells as NULL.

    Text keeps freight at two decimals and keeps zip prefixes as written,
    including the missing leading zeros. SQL pads the prefix. Pandas is not
    used here, so a float conversion cannot round a cent.
    """
    loaded = {}
    for table, (filename, columns) in LOAD.items():
        path = RAW / filename
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in columns if c not in reader.fieldnames]
            if missing:
                raise SystemExit(f"{filename} is missing columns {missing}")
            con.execute(f"DROP TABLE IF EXISTS {table}")
            con.execute(
                f"CREATE TABLE {table} ({', '.join(c + ' TEXT' for c in columns)})"
            )
            placeholders = ",".join(["?"] * len(columns))
            sql = f"INSERT INTO {table} VALUES ({placeholders})"
            batch = []
            n = 0
            for row in reader:
                batch.append(tuple(row[c] if row[c] != "" else None for c in columns))
                if len(batch) >= 50000:
                    con.executemany(sql, batch)
                    n += len(batch)
                    batch = []
            if batch:
                con.executemany(sql, batch)
                n += len(batch)
        loaded[table] = n
    con.commit()
    return loaded


def execute_sql(con):
    script = SQL_PATH.read_text(encoding="utf-8")
    con.executescript(script)


def qdf(con, sql):
    return pd.read_sql_query(sql, con)


def one(con, sql):
    row = con.execute(sql).fetchone()
    if row is None:
        return None
    if len(row) == 1:
        return row[0]
    return row


def rank_quantile(values, p):
    """Observed-value quantile. Rank ceil(p * n), 1-based, on the sorted array.

    p = 0 is the minimum. p = 1 is the maximum. This returns a value that is
    in the data. It is not the KPI median: when the count is even, the KPI
    median averages the two central rows, and this function does not.
    """
    a = np.sort(np.asarray(values, dtype=float))
    a = a[~np.isnan(a)]
    n = int(a.size)
    if n == 0:
        return None, 0
    if p <= 0:
        return float(a[0]), n
    if p >= 1:
        return float(a[-1]), n
    rank = int(np.ceil(p * n))
    rank = min(max(rank, 1), n)
    return float(a[rank - 1]), n


def band_of(km):
    """Same cuts as sql/kpi_analyze.sql. None if the distance is missing."""
    if km is None or (isinstance(km, float) and np.isnan(km)):
        return None
    if km < 50:
        return "0-50"
    if km < 200:
        return "50-200"
    if km < 500:
        return "200-500"
    if km < 1000:
        return "500-1000"
    return "1000+"


def json_ready(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def write_charts(days, freight, state, distances, summary):
    """Plain matplotlib. No seaborn style. Titles are sentences from the numbers."""
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.titleweight": "semibold",
            "axes.labelsize": 11,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#333333",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "grid.color": "#d9d9d9",
            "grid.linewidth": 0.7,
            "legend.frameon": False,
        }
    )
    x = np.arange(len(BANDS))
    labels = BAND_LABELS

    # Days: order grain, farthest seller. Handling and transit use non-negative legs.
    fig, ax = plt.subplots(figsize=(11.2, 6.0))
    width = 0.25
    series = [
        ("Median purchase-to-door", days["median_p2d"], "#1f4e79"),
        ("Median transit (carrier to door)", days["median_transit"], "#e07a3d"),
        ("Median handling (approval to carrier)", days["median_handling"], "#6b7280"),
    ]
    for i, (name, vals, color) in enumerate(series):
        bars = ax.bar(x + (i - 1) * width, vals, width, label=name, color=color, zorder=3)
        for b, v in zip(bars, vals):
            ax.annotate(
                f"{v:.1f}",
                (b.get_x() + b.get_width() / 2, b.get_height()),
                ha="center",
                va="bottom",
                fontsize=8,
                xytext=(0, 2),
                textcoords="offset points",
            )
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Distance band of the farthest seller (kilometers)")
    ax.set_ylabel("Days")
    ax.grid(axis="y")
    ax.set_ylim(0, max(days["median_p2d"]) * 1.22)
    ax.legend(loc="upper left")
    t0 = days["median_transit"][0]
    t1 = days["median_transit"][-1]
    hmin = min(days["median_handling"])
    hmax = max(days["median_handling"])
    title = (
        f"Median transit rises from {t0:.1f} to {t1:.1f} days across bands; "
        f"handling stays between {hmin:.1f} and {hmax:.1f} days."
    )
    ax.set_title(title, loc="left")
    fig.tight_layout()
    fig.savefig(IMG / "median_days_by_distance_band.png", dpi=140)
    plt.close(fig)

    # Freight: item grain, the item's own distance. Two units, two panels.
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.6))
    axes[0].bar(x, freight["median_freight"], color="#1f4e79", zorder=3)
    axes[1].bar(x, freight["median_fpk"], color="#0f766e", zorder=3)
    for ax, vals, ylabel in (
        (axes[0], freight["median_freight"], "Reais per item"),
        (axes[1], freight["median_fpk"], "Reais per kilogram"),
    ):
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=0)
        ax.set_xlabel("Distance band of this item (kilometers)")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y")
        ax.set_ylim(0, max(vals) * 1.2)
        for i, v in enumerate(vals):
            ax.annotate(f"{v:.1f}", (i, v), ha="center", va="bottom", fontsize=8, xytext=(0, 2), textcoords="offset points")
    fig.suptitle(freight["title"], x=0.01, ha="left", fontsize=12, fontweight="semibold")
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(IMG / "median_freight_by_distance_band.png", dpi=140)
    plt.close(fig)

    # Customers versus sellers. Shares, so the different headcounts share an axis.
    fig, ax = plt.subplots(figsize=(11.2, 6.0))
    top = state.head(10).copy()
    xs = np.arange(len(top))
    w = 0.38
    b1 = ax.bar(xs - w / 2, top["people_pct"], w, label="Customer people", color="#1f4e79", zorder=3)
    b2 = ax.bar(xs + w / 2, top["seller_pct"], w, label="Sellers", color="#e07a3d", zorder=3)
    for bars in (b1, b2):
        for b in bars:
            h = b.get_height()
            ax.annotate(
                f"{h:.1f}",
                (b.get_x() + b.get_width() / 2, h),
                ha="center",
                va="bottom",
                fontsize=7.5,
                xytext=(0, 2),
                textcoords="offset points",
            )
    ax.set_xticks(xs)
    ax.set_xticklabels(top["state"].tolist())
    ax.set_xlabel("State, top 10 by customer people")
    ax.set_ylabel("Percent of all customer people, or of all sellers")
    ax.grid(axis="y")
    ax.set_ylim(0, max(top["people_pct"].max(), top["seller_pct"].max()) * 1.22)
    ax.legend(loc="upper right")
    sp = state.loc[state["state"] == "SP"].iloc[0]
    title = (
        f"São Paulo has {sp['seller_pct']:.1f}% of sellers and {sp['people_pct']:.1f}% of customer people."
    )
    ax.set_title(title, loc="left")
    fig.text(
        0.01,
        0.012,
        "Shares of 96,096 people and 3,095 sellers. AL, AP, RR, and TO have customers and no sellers.",
        fontsize=8,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(IMG / "customers_vs_sellers_by_state.png", dpi=140)
    plt.close(fig)

    # Histogram on a kilometer axis. Bars are 100 km wide and touch.
    # A gap, then one bar for 2,000 km and above, so the tail is on the
    # chart and is not dropped from the metric.
    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    d = np.asarray(distances, dtype=float)
    edges = list(range(0, 2001, 100))
    counts = [int(np.sum((d >= lo) & (d < hi))) for lo, hi in zip(edges[:-1], edges[1:])]
    overflow = int(np.sum(d >= 2000))
    ax.bar(edges[:-1], counts, width=100, align="edge", color="#1f4e79", zorder=3)
    ax.bar([2120], [overflow], width=100, align="edge", color="#94a3b8", zorder=3)
    top = max(counts) * 1.14
    ax.set_ylim(0, top)
    for km in (50, 200, 500, 1000):
        ax.axvline(km, color="#b91c1c", linewidth=1.0, zorder=4)
        ax.text(km + 8, top * 0.98, f"{km:g} km", color="#b91c1c", fontsize=8, ha="left", va="top")
    ax.set_xlim(0, 2300)
    ax.set_xticks([0, 500, 1000, 1500, 2000, 2170])
    ax.set_xticklabels(["0", "500", "1,000", "1,500", "2,000", "2,000+"])
    ax.set_xlabel("Distance (kilometers)")
    ax.set_ylabel("Delivered items")
    ax.grid(axis="y")
    med = summary["item_distance_median"]
    ax.set_title(
        f"Half of these items are within {med:.0f} kilometers. Red lines mark the proposed cuts.",
        loc="left",
    )
    ax.annotate(
        f"{overflow:,} items at 2,000 km or more, still in the metrics",
        xy=(2170, overflow),
        xytext=(1280, top * 0.62),
        fontsize=8,
        arrowprops={"arrowstyle": "->", "color": "#333333"},
    )
    fig.tight_layout()
    fig.savefig(IMG / "item_distance_distribution.png", dpi=140)
    plt.close(fig)
    return {"days_title": title}

    return {
        "days_title": title if False else None,
    }


def main():
    PROC.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    failures = []

    inventory = inventory_counts()
    pd.DataFrame(inventory).to_csv(PROC / "inventory_checks.csv", index=False)
    for row in inventory:
        status = "PASS" if row["match"] else "FAIL"
        if not row["match"]:
            failures.append(row["file"])
        print(
            f"CHECK inventory {row['file']}: {status} "
            f"rows={row['rows']} cols={row['columns']} "
            f"readme={row['expected_rows']}x{row['expected_columns']}"
        )

    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA synchronous = OFF")
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA temp_store = MEMORY")
    loaded = load_tables(con)
    print("LOADED", json.dumps(loaded))

    # Key uniqueness. A duplicate key would let a later join multiply rows.
    key_checks = {
        "orders.order_id": "SELECT COUNT(*), COUNT(DISTINCT order_id) FROM orders",
        "customers.customer_id": "SELECT COUNT(*), COUNT(DISTINCT customer_id) FROM customers",
        "sellers.seller_id": "SELECT COUNT(*), COUNT(DISTINCT seller_id) FROM sellers",
        "products.product_id": "SELECT COUNT(*), COUNT(DISTINCT product_id) FROM products",
    }
    for name, sql in key_checks.items():
        n, d = con.execute(sql).fetchone()
        print(f"CHECK unique {name}: {'PASS' if n == d else 'FAIL'} rows={n} distinct={d}")
        if n != d:
            raise SystemExit(f"Duplicate key in {name}")

    execute_sql(con)

    unit = one(con, "SELECT km_one_degree_lat FROM res_haversine_unit")
    print(f"CHECK haversine 1 degree lat: {unit}")
    if not (110.0 < unit < 112.0):
        raise SystemExit("Haversine unit check failed")

    fan = qdf(con, "SELECT * FROM res_fanout").iloc[0].to_dict()
    print("FANOUT", {k: json_ready(v) for k, v in fan.items()})
    if int(fan["items_before"]) != int(fan["items_after"]):
        raise SystemExit(
            f"Geolocation join changed the item count: {fan['items_before']} -> {fan['items_after']}"
        )
    if int(fan["centroid_rows"]) != int(fan["centroid_prefixes"]):
        raise SystemExit("Centroid table is not one row per prefix")
    if int(fan["rows_if_customer_geo_not_collapsed"]) <= int(fan["items_before"]):
        raise SystemExit("Expected the uncollapsed customer geolocation join to grow")

    # Band labels in SQL must match band_of(). If they drift, the chart is wrong.
    order_bands = qdf(
        con,
        "SELECT max_distance_km, order_band FROM delivered_order WHERE max_distance_km IS NOT NULL",
    )
    mapped = order_bands["max_distance_km"].map(band_of)
    n_mismatch = int((mapped != order_bands["order_band"]).sum())
    print(f"CHECK order band labels match Python cuts: {'PASS' if n_mismatch == 0 else 'FAIL'} mismatches={n_mismatch}")
    if n_mismatch:
        raise SystemExit("Order band SQL and Python cuts disagree")
    item_bands = qdf(
        con,
        "SELECT distance_km, item_band FROM delivered_item WHERE distance_km IS NOT NULL",
    )
    mapped_i = item_bands["distance_km"].map(band_of)
    n_mismatch_i = int((mapped_i != item_bands["item_band"]).sum())
    print(f"CHECK item band labels match Python cuts: {'PASS' if n_mismatch_i == 0 else 'FAIL'} mismatches={n_mismatch_i}")
    if n_mismatch_i:
        raise SystemExit("Item band SQL and Python cuts disagree")

    # Nearest versus farthest: how many orders would change band. Not a second KPI.
    pair = qdf(
        con,
        """
        SELECT max_distance_km, min_distance_km, n_sellers, order_band
        FROM delivered_order
        WHERE max_distance_km IS NOT NULL AND min_distance_km IS NOT NULL
        """,
    )
    pair["min_band"] = pair["min_distance_km"].map(band_of)
    changed = pair["min_band"] != pair["order_band"]
    multi = pair["n_sellers"] > 1
    band_sensitivity = {
        "orders_with_both_distances": int(len(pair)),
        "orders_band_would_change_if_nearest": int(changed.sum()),
        "multi_seller_orders_with_both_distances": int(multi.sum()),
        "multi_seller_band_would_change": int((changed & multi).sum()),
    }
    print("BAND_SENSITIVITY", json.dumps(band_sensitivity))

    tables = [
        "res_order_status",
        "res_door_by_status",
        "res_orders_without_items",
        "res_dates",
        "res_zip_match",
        "res_brazil",
        "res_grain",
        "res_population",
        "res_distance_tail",
        "res_legs",
        "res_ontime",
        "res_money",
        "res_cross_state",
        "res_order_overall",
        "res_item_overall",
        "res_orders_after_population",
    ]
    snapshot = {}
    for name in tables:
        frame = qdf(con, f"SELECT * FROM {name}")
        snapshot[name] = frame.to_dict(orient="records")
        print(f"\nTABLE {name}")
        print(frame.to_string(index=False))

    outside = qdf(con, "SELECT * FROM res_centroids_outside")
    outside.to_csv(PROC / "centroids_outside_brazil.csv", index=False)
    print("\nTABLE res_centroids_outside")
    print(outside.to_string(index=False))

    med_names = [
        "res_med_p2d",
        "res_med_approval",
        "res_med_handling_nonneg",
        "res_med_handling_all",
        "res_med_transit_nonneg",
        "res_med_transit_all",
        "res_med_freight",
        "res_med_fpk",
        "res_med_item_km",
        "res_med_order_km",
        "res_med_weight",
        "res_med_freight_over_price",
        "res_med_price",
    ]
    medians = {}
    print("\nMEDIANS")
    for name in med_names:
        frame = qdf(con, f"SELECT * FROM {name}")
        medians[name] = frame.to_dict(orient="records")
        print(name, frame.to_dict(orient="records"))

    band_median_names = [
        "res_med_p2d_band",
        "res_med_approval_band",
        "res_med_handling_band",
        "res_med_transit_band",
        "res_med_order_km_band",
        "res_med_freight_band",
        "res_med_fpk_band",
        "res_med_item_km_band",
        "res_med_weight_band",
        "res_med_km_by_cross",
    ]
    band_medians = {}
    for name in band_median_names:
        frame = qdf(con, f"SELECT * FROM {name}")
        band_medians[name] = frame.to_dict(orient="records")
        print(f"\nTABLE {name}")
        print(frame.to_string(index=False))

    order_stats = qdf(con, "SELECT * FROM res_order_band_stats")
    item_stats = qdf(con, "SELECT * FROM res_item_band_stats")
    state = qdf(con, "SELECT * FROM res_state")
    seller_deliv = qdf(con, "SELECT * FROM res_seller_delivered_state")

    def med_map(records):
        return {r["band"]: r for r in records}

    p2d_b = med_map(band_medians["res_med_p2d_band"])
    tr_b = med_map(band_medians["res_med_transit_band"])
    ha_b = med_map(band_medians["res_med_handling_band"])
    ap_b = med_map(band_medians["res_med_approval_band"])
    okm_b = med_map(band_medians["res_med_order_km_band"])
    fr_b = med_map(band_medians["res_med_freight_band"])
    fpk_b = med_map(band_medians["res_med_fpk_band"])
    ikm_b = med_map(band_medians["res_med_item_km_band"])
    wt_b = med_map(band_medians["res_med_weight_band"])
    os_map = {r["band"]: r for r in order_stats.to_dict(orient="records")}
    is_map = {r["band"]: r for r in item_stats.to_dict(orient="records")}

    band_rows = []
    for band in BANDS:
        o = os_map[band]
        it = is_map[band]
        band_rows.append(
            {
                "band": band,
                "orders": int(o["n"]),
                "order_median_km": okm_b[band]["median_x"],
                "order_mean_km": o["mean_km"],
                "median_purchase_to_door": p2d_b[band]["median_x"],
                "p2d_low_central": p2d_b[band]["low_central"],
                "p2d_high_central": p2d_b[band]["high_central"],
                "p2d_n": int(p2d_b[band]["n"]),
                "mean_purchase_to_door": o["mean_p2d"],
                "median_transit_nonneg": tr_b[band]["median_x"],
                "transit_n": int(tr_b[band]["n"]),
                "mean_transit_nonneg": o["mean_transit_nonneg"],
                "transit_neg_n": int(o["transit_neg_n"]),
                "median_handling_nonneg": ha_b[band]["median_x"],
                "handling_n": int(ha_b[band]["n"]),
                "mean_handling_nonneg": o["mean_handling_nonneg"],
                "handling_neg_n": int(o["handling_neg_n"]),
                "median_approval": ap_b[band]["median_x"],
                "approval_n": int(ap_b[band]["n"]),
                "mean_approval": o["mean_approval"],
                "on_time_n": int(o["on_time_n"]),
                "on_time_rate": o["on_time_n"] / o["n"],
                "items": int(it["n"]),
                "item_median_km": ikm_b[band]["median_x"],
                "item_mean_km": it["mean_km"],
                "median_freight": fr_b[band]["median_x"],
                "mean_freight": it["mean_freight"],
                "freight_cents": int(it["freight_cents"]),
                "fpk_n": int(fpk_b[band]["n"]),
                "median_fpk": fpk_b[band]["median_x"],
                "mean_fpk": it["mean_fpk"],
                "median_weight_g": wt_b[band]["median_x"],
                "mean_weight_g": it["mean_weight_g"],
                "cross_n": int(it["cross_n"]),
                "cross_share": it["cross_n"] / it["n"],
            }
        )
    band_df = pd.DataFrame(band_rows)
    band_df.to_csv(PROC / "distance_band_summary.csv", index=False)
    print("\nBAND TABLE")
    print(band_df.to_string(index=False))

    grain = snapshot["res_grain"][0]
    people_n = int(grain["distinct_people"])
    seller_n = int(grain["sellers"])
    order_n = int(grain["orders"])
    delivered_n = int(snapshot["res_population"][0]["delivered_orders"])
    state["people_share"] = state["customer_people"] / people_n
    state["seller_share"] = state["sellers"] / seller_n
    state["order_share"] = state["orders"] / order_n
    state["delivered_order_share"] = state["delivered_orders"] / delivered_n
    state["people_pct"] = state["people_share"] * 100
    state["seller_pct"] = state["seller_share"] * 100
    state = state.sort_values(["customer_people", "state"], ascending=[False, True])
    state.to_csv(PROC / "state_summary.csv", index=False)
    seller_deliv.to_csv(PROC / "sellers_with_delivered_item_by_state.csv", index=False)

    distances = qdf(
        con, "SELECT distance_km FROM delivered_item WHERE distance_km IS NOT NULL"
    )["distance_km"].to_numpy()
    order_distances = qdf(
        con,
        "SELECT max_distance_km FROM delivered_order WHERE max_distance_km IS NOT NULL",
    )["max_distance_km"].to_numpy()

    def dist_table(arr, label):
        out = []
        for p in (0, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, 1):
            val, n = rank_quantile(arr, p)
            out.append({"distribution": label, "p": p, "rank_quantile_km": val, "n": n})
        return out

    pct_rows = dist_table(distances, "delivered_item_distance") + dist_table(
        order_distances, "delivered_order_max_distance"
    )
    pd.DataFrame(pct_rows).to_csv(PROC / "distance_percentiles.csv", index=False)
    print("\nPERCENTILES rank rule ceil(p*n)")
    print(pd.DataFrame(pct_rows).to_string(index=False))

    # Histogram counts, 100 km bins, last bin is 2000 km and above. Not a drop.
    hist_rows = []
    edges = list(range(0, 2001, 100))
    for lo, hi in zip(edges[:-1], edges[1:]):
        hist_rows.append(
            {
                "lo_km": lo,
                "hi_km_exclusive": hi,
                "items": int(np.sum((distances >= lo) & (distances < hi))),
            }
        )
    hist_rows.append(
        {
            "lo_km": 2000,
            "hi_km_exclusive": None,
            "items": int(np.sum(distances >= 2000)),
        }
    )
    pd.DataFrame(hist_rows).to_csv(PROC / "distance_histogram_100km.csv", index=False)

    item_med = float(medians["res_med_item_km"][0]["median_x"])
    fpk_vals = [r["median_fpk"] for r in band_rows]
    freight_vals = [r["median_freight"] for r in band_rows]
    # The second band is 50-200. A dip there is part of the sentence, not a smooth slope.
    freight_title = (
        "Median freight per item rises in every longer band. "
        "Freight per kilogram dips in the 50–200 km band, then rises."
    )
    freight_rises = all(b > a for a, b in zip(freight_vals, freight_vals[1:]))
    fpk_dip = fpk_vals[1] < fpk_vals[0] and all(b > a for a, b in zip(fpk_vals[1:], fpk_vals[2:]))
    if not (freight_rises and fpk_dip):
        freight_title = (
            "Median freight per item and median freight per kilogram by distance band."
        )

    people_links = int(state["customer_people"].sum())
    extra_links = people_links - people_n
    zero_seller = state.loc[state["sellers"] == 0, "state"].tolist()
    state_note = (
        f"People shares use {people_n:,} customer people as the denominator. "
        f"State counts sum to {people_links:,} because {int(grain['people_with_more_than_one_state'])} people appear in more than one state. "
        f"Seller shares use all {seller_n:,} sellers. "
        f"{len(zero_seller)} states have customers and no sellers: {', '.join(zero_seller)}."
    )

    summary_for_charts = {
        "item_distance_median": item_med,
        "state_chart_note": state_note,
    }
    write_charts(
        {
            "median_p2d": [r["median_purchase_to_door"] for r in band_rows],
            "median_transit": [r["median_transit_nonneg"] for r in band_rows],
            "median_handling": [r["median_handling_nonneg"] for r in band_rows],
        },
        {
            "median_freight": freight_vals,
            "median_fpk": fpk_vals,
            "title": freight_title,
        },
        state,
        distances,
        summary_for_charts,
    )

    # Largest gap between all-order state share and delivered-order state share.
    mix_gap = (state["order_share"] - state["delivered_order_share"]).abs()
    mix = {
        "max_abs_share_gap": float(mix_gap.max()),
        "state_at_max_gap": state.loc[mix_gap.idxmax(), "state"],
    }
    print("STATE_MIX_GAP", json.dumps(mix))

    payload = {
        "inventory": inventory,
        "loaded": loaded,
        "fanout": {k: json_ready(v) for k, v in fan.items()},
        "haversine_one_degree_lat_km": unit,
        "band_sensitivity": band_sensitivity,
        "snapshot": snapshot,
        "medians": medians,
        "band_medians": band_medians,
        "band_table": band_rows,
        "percentiles": pct_rows,
        "histogram_100km": hist_rows,
        "state_chart_note": state_note,
        "freight_chart_title": freight_title,
        "state_mix_gap": mix,
        "failures": failures,
        "brazil_box": {"lat": list(BRAZIL_LAT), "lng": list(BRAZIL_LNG)},
    }
    # default=str catches anything leftover; floats stay floats via the encoder below.
    def encode(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(o)
        raise TypeError(type(o))

    (PROC / "analyze_summary.json").write_text(
        json.dumps(payload, indent=2, default=encode),
        encoding="utf-8",
    )

    print("\nCHART_TITLES")
    print("freight:", freight_title)
    print("state note:", state_note)
    print("item distance median km:", repr(item_med))
    print("FAILURES", failures)
    print("WROTE", SQL_PATH)
    print("DB", DB_PATH)
    if failures:
        print("DATA CHECK FAILURES (script still wrote outputs):", failures)
    print("DONE")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
