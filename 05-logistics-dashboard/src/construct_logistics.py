#!/usr/bin/env python3
"""Construct stage: the weekly logistics page, on the Analyze definitions.

Run from the project folder (05-logistics-dashboard):
    python3 src/construct_logistics.py

Paths are anchored to this file, not to the shell's current directory.
The script imports analyze_logistics and runs sql/kpi_analyze.sql first.
The centroid and the haversine stay in that file. This script does not
define a second one.

What this stage freezes:
    The five distance bands Analyze proposed. Right-open, last band holds
    the tail: 0-50, 50-200, 200-500, 500-1000, 1000+ km. They are not
    retuned after the chart is drawn.

What this stage writes:
    data/processed/weekly_scorecard.csv
    data/processed/distance_bands.csv
    data/processed/state_coverage.csv
    dashboards/logistics_weekly.html   (via build_dashboard.py)

The HTML page is one executive page for a historical extract. It is not a
live feed. It is drawn by src/build_dashboard.py from the processed CSVs
(called at the end of this script), which also copies it to
docs/05-logistics-dashboard/index.html for GitHub Pages. It does not
recommend a carrier, a warehouse, or a dollar impact.

The script does not commit.
"""

from __future__ import annotations

import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

# Same module the Analyze stage ran. band_of, the load, and the SQL path
# live there. Importing them is the reuse. Copying the haversine into this
# file would be a second definition.
import analyze_logistics as az

PROJECT = Path(__file__).resolve().parents[1]
PROC = PROJECT / "data" / "processed"
DASH = PROJECT / "dashboards"
SQL_PATH = PROJECT / "sql" / "kpi_construct.sql"
DB_PATH = Path("/tmp/olist_logistics_construct.sqlite")

# Locked totals from Analyze. If a rebuilt total disagrees, the script stops.
# It does not rewrite the page to match a different denominator.
LOCKED = {
    "orders_purchased": 99441,
    "delivered_orders": 96470,
    "delivered_items": 110189,
    "orders_with_distance": 95992,
    "items_with_distance": 109651,
    "on_time_orders": 89936,
    "cross_state_items": 70328,
    "freight_cents": 220283580,
    "transit_orders": 96446,
    "customer_people": 96096,
    "sellers": 3095,
    "state_people_links": 96136,
    "median_p2d": 10.217476851539686,
    "median_transit": 7.10031250026077,
    "median_freight": 16.26,
    "band_orders": {
        "0-50": 11672,
        "50-200": 12832,
        "200-500": 30258,
        "500-1000": 25829,
        "1000+": 15401,
    },
    "band_items": {
        "0-50": 13449,
        "50-200": 14708,
        "200-500": 34748,
        "500-1000": 29495,
        "1000+": 17251,
    },
    "band_p2d": {
        "0-50": 4.901296296156943,
        "50-200": 6.466655092546716,
        "200-500": 9.972876157378778,
        "500-1000": 12.127638888545334,
        "1000+": 16.365196759346873,
    },
    "band_transit": {
        "0-50": 1.9568981481716037,
        "50-200": 3.3847916671074927,
        "200-500": 6.957164351828396,
        "500-1000": 8.759131944505498,
        "1000+": 13.198749999981374,
    },
    "band_freight": {
        "0-50": 9.06,
        "50-200": 11.92,
        "200-500": 15.7,
        "500-1000": 17.75,
        "1000+": 25.38,
    },
    "sp_people": 40302,
    "sp_sellers": 1849,
}


def fail(message):
    """Stop. Do not write extracts that disagree with Analyze."""
    print("DISAGREEMENT", message)
    raise SystemExit(1)


def close_enough(got, expected, tol=1e-9):
    if got is None or expected is None:
        return False
    return abs(float(got) - float(expected)) <= tol


def qdf(con, sql):
    return pd.read_sql_query(sql, con)


def one(con, sql):
    row = con.execute(sql).fetchone()
    if row is None:
        return None
    if len(row) == 1:
        return row[0]
    return row


def check_against_analyze(con):
    """The construct queries must match the Analyze result tables, and those
    tables must still match the locked report figures. A miss stops the run
    before any CSV or HTML is written.
    """
    orders_purchased = one(con, "SELECT SUM(orders_purchased) FROM res_weekly")
    delivered = one(con, "SELECT SUM(delivered_orders) FROM res_weekly")
    on_time = one(con, "SELECT SUM(on_time_orders) FROM res_weekly")
    transit_n = one(con, "SELECT SUM(transit_orders) FROM res_weekly")
    items = one(con, "SELECT SUM(delivered_items) FROM res_weekly")
    cross = one(con, "SELECT SUM(cross_state_items) FROM res_weekly")
    cents = one(con, "SELECT SUM(freight_cents) FROM res_weekly")
    band_orders = one(con, "SELECT SUM(orders) FROM res_distance_band")
    band_items = one(con, "SELECT SUM(items) FROM res_distance_band")

    # Analyze tables in the same connection. Same population, same haversine.
    az_orders = one(con, "SELECT COUNT(*) FROM orders")
    az_delivered = one(con, "SELECT COUNT(*) FROM delivered_order")
    az_items = one(con, "SELECT COUNT(*) FROM delivered_item")
    az_dist_orders = one(
        con, "SELECT COUNT(*) FROM delivered_order WHERE max_distance_km IS NOT NULL"
    )
    az_dist_items = one(
        con, "SELECT COUNT(*) FROM delivered_item WHERE distance_km IS NOT NULL"
    )
    az_on_time = one(con, "SELECT on_time_date_n FROM res_ontime")
    az_cross = one(con, "SELECT cross_state_n FROM res_cross_state")
    az_cents = one(con, "SELECT delivered_freight_cents FROM res_money")
    az_transit = one(con, "SELECT n FROM res_med_transit_nonneg")
    az_p2d = one(con, "SELECT median_x FROM res_med_p2d")
    az_tr = one(con, "SELECT median_x FROM res_med_transit_nonneg")
    az_fr = one(con, "SELECT median_x FROM res_med_freight")

    pairs = [
        ("orders purchased", orders_purchased, az_orders, LOCKED["orders_purchased"]),
        ("delivered orders in weekly time metrics", delivered, az_delivered, LOCKED["delivered_orders"]),
        ("on-time orders", on_time, az_on_time, LOCKED["on_time_orders"]),
        ("non-negative transit orders", transit_n, az_transit, LOCKED["transit_orders"]),
        ("delivered items", items, az_items, LOCKED["delivered_items"]),
        ("cross-state items", cross, az_cross, LOCKED["cross_state_items"]),
        ("freight cents", cents, az_cents, LOCKED["freight_cents"]),
        ("band orders", band_orders, az_dist_orders, LOCKED["orders_with_distance"]),
        ("band items", band_items, az_dist_items, LOCKED["items_with_distance"]),
    ]
    for label, got, analyze_value, locked in pairs:
        if int(got) != int(analyze_value) or int(got) != int(locked):
            fail(
                f"{label}: construct={got} analyze={analyze_value} locked={locked}"
            )
        print(f"CHECK {label}: PASS {int(got)}")

    if not close_enough(az_p2d, LOCKED["median_p2d"]):
        fail(f"median purchase-to-door: analyze={az_p2d} locked={LOCKED['median_p2d']}")
    if not close_enough(az_tr, LOCKED["median_transit"]):
        fail(f"median transit: analyze={az_tr} locked={LOCKED['median_transit']}")
    if not close_enough(az_fr, LOCKED["median_freight"], tol=1e-9):
        fail(f"median freight: analyze={az_fr} locked={LOCKED['median_freight']}")
    print(
        "CHECK overall medians: PASS "
        f"p2d={az_p2d} transit={az_tr} freight={az_fr}"
    )

    # The page bands must equal the Analyze band medians, not a rounded copy.
    az_band_p2d = {
        r["band"]: r["median_x"]
        for r in qdf(con, "SELECT band, median_x FROM res_med_p2d_band").to_dict("records")
    }
    az_band_tr = {
        r["band"]: r["median_x"]
        for r in qdf(con, "SELECT band, median_x FROM res_med_transit_band").to_dict("records")
    }
    az_band_fr = {
        r["band"]: r["median_x"]
        for r in qdf(con, "SELECT band, median_x FROM res_med_freight_band").to_dict("records")
    }
    bands = qdf(con, "SELECT * FROM res_distance_band")
    if list(bands["band"]) != az.BANDS:
        fail(f"band order {list(bands['band'])} != {az.BANDS}")
    for row in bands.to_dict("records"):
        band = row["band"]
        if int(row["orders"]) != LOCKED["band_orders"][band]:
            fail(f"band {band} orders {row['orders']} != {LOCKED['band_orders'][band]}")
        if int(row["items"]) != LOCKED["band_items"][band]:
            fail(f"band {band} items {row['items']} != {LOCKED['band_items'][band]}")
        if not close_enough(row["median_purchase_to_door_days"], az_band_p2d[band]):
            fail(f"band {band} p2d construct != analyze")
        if not close_enough(row["median_purchase_to_door_days"], LOCKED["band_p2d"][band]):
            fail(
                f"band {band} p2d {row['median_purchase_to_door_days']} "
                f"!= locked {LOCKED['band_p2d'][band]}"
            )
        if not close_enough(row["median_transit_days"], az_band_tr[band]):
            fail(f"band {band} transit construct != analyze")
        if not close_enough(row["median_transit_days"], LOCKED["band_transit"][band]):
            fail(f"band {band} transit != locked")
        if not close_enough(row["median_freight_brl"], az_band_fr[band]):
            fail(f"band {band} freight construct != analyze")
        if not close_enough(row["median_freight_brl"], LOCKED["band_freight"][band], tol=1e-9):
            fail(
                f"band {band} freight {row['median_freight_brl']} "
                f"!= locked {LOCKED['band_freight'][band]}"
            )
        print(
            f"CHECK band {band}: PASS orders={int(row['orders'])} "
            f"items={int(row['items'])}"
        )

    # Python band_of is the same function Analyze used. A mismatch means the
    # SQL cuts and the Python cuts have forked.
    order_bands = qdf(
        con,
        "SELECT max_distance_km, order_band FROM delivered_order "
        "WHERE max_distance_km IS NOT NULL",
    )
    mapped = order_bands["max_distance_km"].map(az.band_of)
    n_mismatch = int((mapped != order_bands["order_band"]).sum())
    if n_mismatch:
        fail(f"order band SQL and analyze band_of disagree on {n_mismatch} orders")
    print("CHECK band_of matches order_band: PASS")

    people = one(con, "SELECT COUNT(DISTINCT customer_unique_id) FROM customers")
    sellers = one(con, "SELECT COUNT(*) FROM sellers")
    people_links = one(con, "SELECT SUM(customer_people) FROM res_state_coverage")
    seller_sum = one(con, "SELECT SUM(sellers) FROM res_state_coverage")
    if int(people) != LOCKED["customer_people"] or int(sellers) != LOCKED["sellers"]:
        fail(f"people/sellers {people}/{sellers}")
    if int(people_links) != LOCKED["state_people_links"] or int(seller_sum) != LOCKED["sellers"]:
        fail(f"state sums people_links={people_links} sellers={seller_sum}")
    sp = one(
        con,
        "SELECT customer_people, sellers FROM res_state_coverage WHERE state = 'SP'",
    )
    if int(sp[0]) != LOCKED["sp_people"] or int(sp[1]) != LOCKED["sp_sellers"]:
        fail(f"SP people/sellers {sp}")
    # The construct state query must match Analyze's res_state on the two
    # columns the page draws. Orders are not on this page.
    compare = one(
        con,
        """
        SELECT COUNT(*) FROM res_state_coverage c
        JOIN res_state a ON a.state = c.state
        WHERE c.customer_people != a.customer_people
           OR c.sellers != a.sellers
        """,
    )
    n_states_a = one(con, "SELECT COUNT(*) FROM res_state")
    n_states_c = one(con, "SELECT COUNT(*) FROM res_state_coverage")
    if int(compare) != 0 or int(n_states_a) != int(n_states_c):
        fail(f"state coverage disagrees with res_state mismatches={compare}")
    print(
        f"CHECK state coverage: PASS states={int(n_states_c)} "
        f"people={int(people)} sellers={int(sellers)} SP={int(sp[0])}/{int(sp[1])}"
    )

    unit = one(con, "SELECT km_one_degree_lat FROM res_haversine_unit")
    if not (110.0 < unit < 112.0):
        fail(f"haversine unit check {unit}")
    print(f"CHECK haversine unit km: PASS {unit}")

    return {
        "median_p2d": float(az_p2d),
        "median_transit": float(az_tr),
        "median_freight": float(az_fr),
        "haversine_unit_km": float(unit),
    }


def write_extracts(con):
    weekly = qdf(con, "SELECT * FROM res_weekly ORDER BY week_start")
    bands = qdf(con, "SELECT * FROM res_distance_band ORDER BY band_order")
    states = qdf(con, "SELECT * FROM res_state_coverage")

    # Reais from integer cents. Two decimals, not a binary float of the sum.
    weekly.insert(
        weekly.columns.get_loc("freight_cents") + 1,
        "freight_total_brl",
        weekly["freight_cents"].apply(
            lambda c: "" if pd.isna(c) else f"{Decimal(int(c)) / Decimal(100):.2f}"
        ),
    )
    weekly = weekly.drop(columns=["freight_cents"])

    # Tableau reads blanks as null. A zero would say the delivery was instant.
    weekly_path = PROC / "weekly_scorecard.csv"
    band_path = PROC / "distance_bands.csv"
    state_path = PROC / "state_coverage.csv"
    weekly.to_csv(weekly_path, index=False, na_rep="")
    bands.to_csv(band_path, index=False, na_rep="")
    states.to_csv(state_path, index=False, na_rep="")
    print(f"WROTE {weekly_path} rows={len(weekly)}")
    print(f"WROTE {band_path} rows={len(bands)}")
    print(f"WROTE {state_path} rows={len(states)}")
    return weekly, bands, states


def main():
    PROC.mkdir(parents=True, exist_ok=True)
    DASH.mkdir(parents=True, exist_ok=True)
    if not SQL_PATH.exists():
        fail(f"missing {SQL_PATH}")
    if not az.SQL_PATH.exists():
        fail(f"missing {az.SQL_PATH}")

    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA synchronous = OFF")
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA temp_store = MEMORY")

    # Same loader and the same Analyze SQL. Zip prefixes stay text. The
    # haversine is the expression in kpi_analyze.sql, not a Python copy.
    loaded = az.load_tables(con)
    print("LOADED", loaded)
    az.execute_sql(con)
    con.executescript(SQL_PATH.read_text(encoding="utf-8"))

    med = check_against_analyze(con)
    weekly, bands, states = write_extracts(con)
    # The page is drawn by build_dashboard.py from the CSVs just written,
    # so a full rebuild and a page-only rebuild produce the same HTML. It
    # re-checks every locked figure before it writes anything.
    import build_dashboard

    build_dashboard.build()
    con.close()
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
