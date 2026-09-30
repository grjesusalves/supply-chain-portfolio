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
    dashboards/logistics_weekly.html

The HTML page is one executive page for a historical extract. It is not a
live feed. It shows the seven items from the plan and nothing else.
It does not recommend a carrier, a warehouse, or a dollar impact.

The script does not commit.
"""

from __future__ import annotations

import base64
import io
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
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


def apply_style():
    """Same plain matplotlib as Analyze. No seaborn. Labels say the unit."""
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


def fig_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def style_time_axis(ax, interval=3, rotate=False):
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=interval))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.grid(axis="y")
    for label in ax.get_xticklabels():
        label.set_fontsize(9)
        if rotate:
            label.set_rotation(30)
            label.set_ha("right")


def money(cents):
    """Reais from integer cents, two decimals, thousands separators."""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    whole, frac = divmod(cents, 100)
    return f"{sign}R${whole:,}.{frac:02d}"


def fmt_days(value):
    return f"{value:.1f}"


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


def _dates(weekly):
    return pd.to_datetime(weekly["week_start"])


def _weekly_axis(weekly):
    """One point per Monday from the first purchase week to the last.

    Weeks with no purchase are missing from the extract on purpose: there is
    no order_purchase_timestamp to attach them to. Plotting only the rows
    that exist would draw a line across those gaps. Reindexing to every
    Monday leaves a blank, which is not a zero.
    """
    frame = weekly.copy()
    frame["week_start"] = pd.to_datetime(frame["week_start"])
    frame = frame.set_index("week_start").sort_index()
    full = pd.date_range(frame.index.min(), frame.index.max(), freq="W-MON")
    return frame.reindex(full)


def chart_orders(weekly):
    fig, ax = plt.subplots(figsize=(11.2, 4.6))
    axis = _weekly_axis(weekly)
    x = axis.index
    y = axis["orders_purchased"].astype(float)
    ax.plot(x, y, color="#1f4e79", linewidth=1.6, zorder=3)
    ax.set_ylabel("Orders")
    ax.set_xlabel("Week of purchase (week starts Monday)")
    style_time_axis(ax)
    total = int(weekly["orders_purchased"].sum())
    ax.set_title(
        f"{total:,} orders purchased in this extract. The line counts every status, not only delivered orders.",
        loc="left",
    )
    fig.tight_layout()
    return fig_b64(fig)


def chart_days(weekly, med_p2d, med_tr):
    fig, ax = plt.subplots(figsize=(11.2, 4.8))
    axis = _weekly_axis(weekly)
    x = axis.index
    p2d = axis["median_purchase_to_door_days"].astype(float)
    tr = axis["median_transit_days"].astype(float)
    ax.plot(x, p2d, color="#1f4e79", linewidth=1.6, label="Median purchase-to-door", zorder=3)
    ax.plot(x, tr, color="#e07a3d", linewidth=1.6, label="Median transit (carrier to door)", zorder=3)
    ax.set_ylabel("Days")
    ax.set_xlabel("Week of purchase (week starts Monday)")
    style_time_axis(ax)
    ax.legend(loc="upper right")
    ax.set_title(
        f"Median purchase-to-door is {med_p2d:.1f} days. Median transit is {med_tr:.1f} days. "
        "A week with no delivery is blank, not zero.",
        loc="left",
    )
    fig.tight_layout()
    return fig_b64(fig)


def chart_ontime(weekly, on_time_n, delivered_n):
    fig, ax = plt.subplots(figsize=(11.2, 4.6))
    axis = _weekly_axis(weekly)
    x = axis.index
    rate = axis["on_time_rate"].astype(float) * 100
    ax.plot(x, rate, color="#1f4e79", linewidth=1.6, zorder=3)
    ax.set_ylabel("Percent of delivered orders")
    ax.set_xlabel("Week of purchase (week starts Monday)")
    style_time_axis(ax)
    ax.set_ylim(0, 100)
    pct = 100.0 * on_time_n / delivered_n
    ax.set_title(
        f"On time by calendar date: {on_time_n:,} / {delivered_n:,} delivered orders ({pct:.1f}%).",
        loc="left",
    )
    fig.tight_layout()
    return fig_b64(fig)


def chart_freight(weekly, cents, med_freight, n_items):
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.8))
    axis = _weekly_axis(weekly)
    x = axis.index
    total = axis["freight_total_brl"].replace("", np.nan).astype(float)
    med = axis["median_freight_brl"].replace("", np.nan).astype(float)
    axes[0].plot(x, total, color="#1f4e79", linewidth=1.6, zorder=3)
    axes[1].plot(x, med, color="#0f766e", linewidth=1.6, zorder=3)
    axes[0].set_ylabel("Reais")
    axes[1].set_ylabel("Reais per item")
    for ax in axes:
        ax.set_xlabel("Week of purchase")
        # Half-width panels. A 3-month tick collides. Six months, tilted, stays readable.
        style_time_axis(ax, interval=6, rotate=True)
    axes[0].set_title("Total freight", loc="left", fontsize=11)
    axes[1].set_title("Median freight per item", loc="left", fontsize=11)
    # Matplotlib treats $ as mathtext. The reais sign has to be escaped or the
    # title collapses into one word.
    title = (
        f"Delivered-item freight is {money(cents)}. "
        f"Median freight per item is R${med_freight:.2f} on {n_items:,} items."
    )
    fig.suptitle(
        title.replace("$", chr(92) + "$"),
        x=0.01,
        ha="left",
        fontsize=12,
        fontweight="semibold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    return fig_b64(fig)


def chart_cross(weekly, cross_n, n_items):
    fig, ax = plt.subplots(figsize=(11.2, 4.6))
    axis = _weekly_axis(weekly)
    x = axis.index
    share = axis["cross_state_share"].astype(float) * 100
    ax.plot(x, share, color="#1f4e79", linewidth=1.6, zorder=3)
    ax.set_ylabel("Percent of delivered items")
    ax.set_xlabel("Week of purchase (week starts Monday)")
    style_time_axis(ax)
    ax.set_ylim(0, 100)
    pct = 100.0 * cross_n / n_items
    ax.set_title(
        f"{cross_n:,} of {n_items:,} delivered items cross a state line ({pct:.1f}%).",
        loc="left",
    )
    fig.tight_layout()
    return fig_b64(fig)


def chart_states(states):
    """Shares, so 96,096 people and 3,095 sellers can sit on one axis.
    The share denominator is distinct people, not the sum of state rows.
    """
    fig, ax = plt.subplots(figsize=(11.2, 8.2))
    top = states.sort_values(["customer_people", "state"], ascending=[True, False])
    ys = np.arange(len(top))
    h = 0.38
    ax.barh(
        ys + h / 2,
        top["people_share"] * 100,
        h,
        label="Customer people",
        color="#1f4e79",
        zorder=3,
    )
    ax.barh(
        ys - h / 2,
        top["seller_share"] * 100,
        h,
        label="Sellers",
        color="#e07a3d",
        zorder=3,
    )
    ax.set_yticks(ys)
    ax.set_yticklabels(top["state"].tolist())
    ax.set_xlabel("Percent of all customer people, or of all sellers")
    ax.grid(axis="x")
    ax.legend(loc="lower right")
    sp = states.loc[states["state"] == "SP"].iloc[0]
    ax.set_title(
        f"São Paulo has {sp['seller_share'] * 100:.1f}% of sellers and "
        f"{sp['people_share'] * 100:.1f}% of customer people.",
        loc="left",
    )
    fig.tight_layout()
    return fig_b64(fig)


def band_table_html(bands):
    rows = []
    for r in bands.to_dict("records"):
        rows.append(
            "<tr>"
            f"<td>{r['band_label']}</td>"
            f"<td class='num'>{int(r['orders']):,}</td>"
            f"<td class='num'>{r['median_purchase_to_door_days']:.1f}</td>"
            f"<td class='num'>{r['median_transit_days']:.1f}</td>"
            f"<td class='num'>{r['median_freight_brl']:.2f}</td>"
            "</tr>"
        )
    body = "\n".join(rows)
    return f"""
<table>
  <thead>
    <tr>
      <th>Distance</th>
      <th class="num">Orders</th>
      <th class="num">Median purchase-to-door (days)</th>
      <th class="num">Median transit (days)</th>
      <th class="num">Median freight per item (reais)</th>
    </tr>
  </thead>
  <tbody>
    {body}
  </tbody>
</table>
"""


def write_html(weekly, bands, states, med):
    """One page. Seven sections. No review score, no freight per kilogram,
    no handling chart, no recommendation.
    """
    apply_style()
    n_orders = int(weekly["orders_purchased"].sum())
    n_delivered = int(weekly["delivered_orders"].fillna(0).sum())
    n_items = int(weekly["delivered_items"].fillna(0).sum())
    on_time_n = int(weekly["on_time_orders"].fillna(0).sum())
    cross_n = int(weekly["cross_state_items"].fillna(0).sum())
    cents = int(
        (
            weekly["freight_total_brl"].replace("", np.nan).dropna().astype(float) * 100
        )
        .round()
        .sum()
    )
    # The cents check already passed on the SQL integer. Re-derive the page
    # total from that integer via the two-decimal strings, then confirm.
    if cents != LOCKED["freight_cents"]:
        fail(f"HTML freight cents {cents} != {LOCKED['freight_cents']}")

    blank_weeks = int(weekly["delivered_orders"].isna().sum())
    first = weekly["week_start"].iloc[0]
    last = weekly["week_start"].iloc[-1]
    n_weeks = len(weekly)
    span = pd.date_range(pd.to_datetime(first), pd.to_datetime(last), freq="W-MON")
    gap_weeks = len(span) - n_weeks
    band_orders = int(bands["orders"].sum())
    band_items = int(bands["items"].sum())

    img = {
        "orders": chart_orders(weekly),
        "days": chart_days(weekly, med["median_p2d"], med["median_transit"]),
        "ontime": chart_ontime(weekly, on_time_n, n_delivered),
        "freight": chart_freight(weekly, cents, med["median_freight"], n_items),
        "cross": chart_cross(weekly, cross_n, n_items),
        "states": chart_states(states),
    }
    table = band_table_html(bands)
    on_pct = 100.0 * on_time_n / n_delivered
    cross_pct = 100.0 * cross_n / n_items
    sp = states.loc[states["state"] == "SP"].iloc[0]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Weekly operating review — logistics (historical extract)</title>
<style>
  body {{
    margin: 0;
    background: #f7f7f5;
    color: #1a1a1a;
    font: 16px/1.45 "Segoe UI", "Source Sans 3", Helvetica, Arial, sans-serif;
  }}
  main {{
    max-width: 1080px;
    margin: 0 auto;
    padding: 28px 22px 64px;
    background: white;
  }}
  h1 {{
    font-size: 26px;
    line-height: 1.25;
    margin: 0 0 8px;
  }}
  h2 {{
    font-size: 18px;
    margin: 28px 0 6px;
  }}
  p {{ margin: 0 0 10px; }}
  .kicker {{
    color: #444;
    font-size: 14px;
    margin-bottom: 18px;
  }}
  img {{ width: 100%; height: auto; }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin-top: 8px;
  }}
  th, td {{
    padding: 7px 8px;
    border-bottom: 1px solid #e4e4e4;
    vertical-align: bottom;
  }}
  th {{
    border-bottom: 2px solid #333;
    font-weight: 600;
    font-size: 14px;
  }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .note {{
    color: #444;
    font-size: 13px;
    margin-top: 8px;
  }}
  section {{ padding-bottom: 8px; border-bottom: 1px solid #eee; }}
</style>
</head>
<body>
<main>
  <h1>Weekly operating review — logistics</h1>
  <p class="kicker">
    Historical extract of Olist Brazilian e-commerce. Not a live feed.
    Delivered purchases run from 15 Sep 2016 through 29 Aug 2018.
    All purchases in the file run from 4 Sep 2016 through 17 Oct 2018.
    Currency is Brazilian reais. Nothing on this page is converted.
  </p>

  <section>
    <h2>1. Orders purchased that week</h2>
    <p>
      {n_orders:,} orders were purchased, across {n_weeks} weeks starting Monday
      {first} through Monday {last}.
      This count is every order, not only the {n_delivered:,} that were delivered.
    </p>
    <img alt="Orders purchased each week" src="data:image/png;base64,{img['orders']}">
    <p class="note">
      The first point is the Monday of the week that contains 4 Sep 2016, which is a Sunday,
      so that Monday is 29 Aug 2016. The last week is partial too.
      {blank_weeks} of these weeks have purchases and no delivered order. They stay on this chart,
      and the time charts below leave them blank.
      {gap_weeks} Mondays between the first and last purchase week have no purchase.
      Those are gaps in the line, not zeros.
    </p>
  </section>

  <section>
    <h2>2. Median purchase-to-door days, and median transit days</h2>
    <p>
      On {n_delivered:,} delivered orders, median purchase-to-door time is
      {med['median_p2d']:.1f} days and median transit, carrier to door, is
      {med['median_transit']:.1f} days.
      Each point is that week’s median, not a mean, and not an average of other weeks.
    </p>
    <img alt="Median purchase-to-door days and median transit days by week" src="data:image/png;base64,{img['days']}">
    <p class="note">
      Transit omits negative carrier-to-door durations (23 orders in the extract).
      Those orders stay in the purchase-to-door median and in the delivered order count.
      A week with no delivered order is left blank. It is not drawn as zero days.
    </p>
  </section>

  <section>
    <h2>3. On-time rate against the estimated delivery date</h2>
    <p>
      {on_time_n:,} of {n_delivered:,} delivered orders ({on_pct:.1f}%) arrived on or before
      the estimate’s calendar date. The estimate is stored at midnight, so the comparison
      is the calendar date, not the timestamp.
    </p>
    <img alt="On-time rate by week" src="data:image/png;base64,{img['ontime']}">
    <p class="note">
      The rate is on-time orders divided by delivered orders that week.
      It is not a substitute for the days in the previous section.
    </p>
  </section>

  <section>
    <h2>4. Total freight and median freight per item</h2>
    <p>
      Delivered items, {n_items:,} of them, carry {money(cents)} of freight.
      The median item is R${med['median_freight']:.2f}.
      Items with no distance stay in this total. They are not in the band table.
    </p>
    <img alt="Total freight and median freight per item by week" src="data:image/png;base64,{img['freight']}">
    <p class="note">
      Freight is the item, in reais. Undelivered orders are not given a freight line on this page.
    </p>
  </section>

  <section>
    <h2>5. Share of items that cross a state line</h2>
    <p>
      {cross_n:,} of {n_items:,} delivered items ({cross_pct:.1f}%) have a customer state
      different from the seller state.
    </p>
    <img alt="Cross-state share of delivered items by week" src="data:image/png;base64,{img['cross']}">
  </section>

  <section>
    <h2>6. Distance bands</h2>
    <p>
      {band_orders:,} delivered orders have a distance. The order’s band is its farthest seller.
      Median freight is the item’s own distance, on {band_items:,} items.
      {n_delivered - band_orders:,} delivered orders have no distance. They are not in this table.
    </p>
    {table}
    <p class="note">
      Bands are frozen: 0–50, 50–200, 200–500, 500–1,000, and 1,000 kilometers or more.
      Cuts are right-open, so 50 kilometers is in 50–200. The last band includes the tail.
      The cuts are not moved to make the table smoother.
    </p>
  </section>

  <section>
    <h2>7. Customers by state, next to sellers by state</h2>
    <p>
      {LOCKED['customer_people']:,} customer people and {LOCKED['sellers']:,} sellers.
      São Paulo is {sp['people_share'] * 100:.1f}% of the people
      ({int(sp['customer_people']):,} / {LOCKED['customer_people']:,})
      and {sp['seller_share'] * 100:.1f}% of the sellers
      ({int(sp['sellers']):,} / {LOCKED['sellers']:,}).
    </p>
    <img alt="Customer people and sellers by state" src="data:image/png;base64,{img['states']}">
    <p class="note">
      People are counted once per state they appear in, so the state rows sum to more than
      {LOCKED['customer_people']:,} distinct people. The percents use the distinct-people
      denominator and the full seller table. Alagoas, Amapá, Roraima, and Tocantins have
      customers and no sellers. This is coverage, not a warehouse site.
    </p>
  </section>
</main>
</body>
</html>
"""
    path = DASH / "logistics_weekly.html"
    path.write_text(html, encoding="utf-8")
    print(f"WROTE {path} bytes={path.stat().st_size}")
    return path


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
    write_html(weekly, bands, states, med)
    con.close()
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
