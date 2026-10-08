#!/usr/bin/env python3
"""Build the executive weekly logistics page from the processed extracts.

Run from anywhere (paths are anchored to this file):
    python3 src/build_dashboard.py

construct_logistics.py calls build() at the end of its run, so a full
rebuild from raw data still produces this page. This file can also run on
its own, because everything it draws is already in data/processed.

What it reads (it does not recompute any metric):
    data/processed/weekly_scorecard.csv     one row per purchase week
    data/processed/distance_bands.csv       the five frozen bands
    data/processed/distance_band_summary.csv  Analyze band table, same grain
                                              as distance_bands.csv; used
                                              only for handling and on-time
    data/processed/state_coverage.csv       one row per state
    data/processed/analyze_summary.json     extract-level medians and dates

Also reads:
    src/dashboard_assets/page.js, src/dashboard_assets/interactive.css

What it writes:
    dashboards/logistics_weekly.html
    ../docs/05-logistics-dashboard/index.html  (byte-identical copy, the
                                                GitHub Pages copy)

Design rules this script follows:
    - One self-contained page. Charts are inline SVG written by hand here,
      so there is no CDN, no JavaScript library and no image to break.
    - Interactive layer (tooltips, weekly date range, band highlight, state
      picker and sort) is plain JS and CSS from src/dashboard_assets/,
      inlined into the page. The data it reads is a JSON block built here
      from the same extracts (page_data). The script only positions marks
      and sums additive weekly counts; it never computes a median. Without
      JS the page still shows the static charts.
    - The three extracts are never joined. Week, band and state are
      different grains; each exhibit reads exactly one of them.
    - A Monday with no purchase is a gap in the line, not a zero. A week
      with purchases and no delivered order leaves days and on-time blank.
    - Every number on the page is formatted from the extracts and then
      compared with the locked figures in EXPECTED. Any disagreement stops
      the run before a file is written.
    - Currency is BRL. No conversion, no savings, no forecast, no review
      score, no causal claim.
"""

from __future__ import annotations

import html
import json
import re
import math
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
PROC = PROJECT / "data" / "processed"
DASH = PROJECT / "dashboards"
DOCS = PROJECT.parent / "docs" / "05-logistics-dashboard"

REPO_URL = "https://github.com/grjesusalves/supply-chain-portfolio"
PROJECT_URL = REPO_URL + "/tree/main/05-logistics-dashboard"
BLOB_URL = REPO_URL + "/blob/main/05-logistics-dashboard/"

# ---------------------------------------------------------------------------
# Locked figures, as they must read on the page. These are the numbers in the
# Analyze and Execute reports. The page formats its own numbers from the
# extracts and compares the strings, so a rounding drift is also caught.
# ---------------------------------------------------------------------------
EXPECTED = {
    "delivered_orders": "96,470",
    "delivered_items": "110,189",
    "median_p2d": "10.2",
    "median_transit": "7.1",
    "median_handling": "1.8",
    "on_time_n": "89,936",
    "on_time_pct": "93.2%",
    "cross_n": "70,328",
    "cross_pct": "63.8%",
    "freight_total": "R$2,202,835.80",
    "median_freight": "R$16.26",
    "weeks": 101,
    "band_orders": ["11,672", "12,832", "30,258", "25,829", "15,401"],
    "band_p2d": ["4.9", "6.5", "10.0", "12.1", "16.4"],
    "band_transit": ["2.0", "3.4", "7.0", "8.8", "13.2"],
    "band_handling_range": ("1.7", "1.9"),
    "band_ontime": ["95.6%", "95.3%", "93.6%", "92.9%", "89.6%"],
    "band_freight": ["R$9.06", "R$11.92", "R$15.70", "R$17.75", "R$25.38"],
    "sp_people": "41.9%",
    "sp_sellers": "59.7%",
    "no_seller_states": ["AL", "AP", "RR", "TO"],
    "first_delivered_purchase": "15 Sep 2016",
    "last_delivered_purchase": "29 Aug 2018",
}

BAND_CODES = ["0-50", "50-200", "200-500", "500-1000", "1000+"]
# Short labels for chart rows. The CSV label "1,000 km or more" is kept in
# the table; the chart uses "1,000+ km" so the row label fits.
BAND_SHORT = ["0–50 km", "50–200 km", "200–500 km", "500–1,000 km", "1,000+ km"]

STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins",
}

# Palette (dark theme). Near-black page, slightly lifted dark-grey panels,
# white primary text, light-grey secondary text. One light steel-blue series
# colour replaces the old navy, one coral accent replaces the old crimson for
# the single thing each exhibit wants the reader to see, and a gold detail is
# used sparingly for exhibit tags, the hint and focus rings. Every text and
# mark colour is checked for contrast against the background it sits on
# (WCAG AA: 4.5:1 for text, 3:1 for large text and chart marks) in
# contrast_checks() before the page is written.
BG = "#0B0B0D"          # page background
SURFACE = "#151518"     # KPI strip, panels, tooltip, controls
SURFACE2 = "#1D1D22"    # hover / pressed surfaces
BORDER = "#2C2C34"      # subtle panel borders
RULE = "#34343D"        # section rules and table lines
HEAD = "#FFFFFF"        # headings and headline numbers
BODY = "#D9DDE3"        # paragraph text
TEXT = "#F2F3F5"        # chart labels (was ink)
TEXT2 = "#B8BEC8"       # secondary text and labels
MUTED = "#9299A5"       # axis ticks, notes, source lines
SERIES = "#7DB4EA"      # primary data series (was navy)
CONTEXT = "#6F7683"     # context marks: all purchases, handling bars
ROWLINE = "#26262D"     # faint row separators inside charts
GRID = "#25252C"        # gridlines
AXIS = "#6A6A76"        # zero baselines and axis ticks
ACCENT = "#FF6B61"      # emphasis: 1,000+ km band, sellers, the low week
ACCENT_BG = "#3A1B1E"   # tinted band behind the annotated week
GOLD = "#E8B44E"        # sparing detail colour
GAP_BG = "#121216"      # hatch for weeks with no purchase
GAP_LINE = "#34343E"
ROW_HI = "#1A1E26"      # SP / RJ / PR rows
ROW_NOSELL = "#2B181B"  # states with customers and no sellers
SEL_BG = "#22354D"      # selected state row
ON_BG = "#1B2635"       # selected band row

# Tiny inline favicon (three bars), so the browser does not request
# /favicon.ico and log a 404. '#' must be URL-encoded inside a data URI.
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
    "%3Crect width='16' height='16' rx='3' fill='%230B0B0D'/%3E"
    "%3Cpath d='M3 13h2.5V8H3zm3.75 0h2.5V3h-2.5zm3.75 0H13V6h-2.5z' fill='%237DB4EA'/%3E%3C/svg%3E"
)


def _luminance(hex_colour):
    rgb = [int(hex_colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg, bg):
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def contrast_checks():
    """WCAG AA on the dark palette, for every pairing the page uses.
    Text needs 4.5:1; large text and chart marks need 3:1. A miss stops the
    build, like a number mismatch does.
    """
    text_pairs = [
        ("HEAD on BG", HEAD, BG), ("BODY on BG", BODY, BG), ("BODY on SURFACE", BODY, SURFACE),
        ("TEXT on BG", TEXT, BG), ("TEXT2 on BG", TEXT2, BG), ("TEXT2 on SURFACE", TEXT2, SURFACE),
        ("MUTED on BG", MUTED, BG), ("MUTED on SURFACE", MUTED, SURFACE),
        ("MUTED on footer", MUTED, "#111114"), ("TEXT2 on footer", TEXT2, "#111114"),
        ("SERIES text on BG", SERIES, BG), ("ACCENT text on BG", ACCENT, BG),
        ("ACCENT text on SURFACE", ACCENT, SURFACE), ("GOLD text on BG", GOLD, BG),
        ("TEXT on ROW_HI", TEXT, ROW_HI), ("ACCENT on ROW_NOSELL", ACCENT, ROW_NOSELL),
        ("TEXT on SEL_BG", TEXT, SEL_BG), ("TEXT on ON_BG", TEXT, ON_BG),
        ("ACCENT on ON_BG", ACCENT, ON_BG), ("ACCENT on ACCENT_BG", ACCENT, ACCENT_BG),
        ("BG on SERIES (pressed button)", BG, SERIES), ("BG on ACCENT (pressed chip)", BG, ACCENT),
        ("TEXT on SURFACE2 (tooltip)", TEXT, SURFACE2),
    ]
    mark_pairs = [
        ("SERIES mark on BG", SERIES, BG), ("CONTEXT mark on BG", CONTEXT, BG),
        ("ACCENT mark on BG", ACCENT, BG), ("AXIS on BG", AXIS, BG),
        ("SERIES mark on ROW_HI", SERIES, ROW_HI), ("CONTEXT mark on SURFACE", CONTEXT, SURFACE),
    ]
    for label, fg, bg, need in [(*t, 4.5) for t in text_pairs] + [(*t, 3.0) for t in mark_pairs]:
        r = contrast(fg, bg)
        if r < need:
            fail(f"contrast {label}: {r:.2f} < {need}")
    print(f"CHECK contrast (WCAG AA): PASS {len(text_pairs)} text pairs, {len(mark_pairs)} mark pairs")


def fail(message):
    """Stop before writing anything. Same rule as construct_logistics."""
    print("DISAGREEMENT", message)
    raise SystemExit(1)


def esc(text):
    return html.escape(str(text), quote=True)


def n0(x):
    return f"{int(x):,}"


def d1(x):
    return f"{float(x):.1f}"


def pct1(num, den):
    return f"{100.0 * num / den:.1f}%"


def brl(x):
    return f"R${float(x):,.2f}"


def brl_from_cents(cents):
    whole, frac = divmod(int(cents), 100)
    return f"R${whole:,}.{frac:02d}"


def fmt_date(ts):
    """'26 Feb 2018' without a leading zero on the day."""
    ts = pd.Timestamp(ts)
    return f"{ts.day} {ts.strftime('%b %Y')}"


# ---------------------------------------------------------------------------
# Load and check
# ---------------------------------------------------------------------------
def load():
    # freight_total_brl is read as text so the total is summed in exact
    # cents, not as binary floats.
    weekly = pd.read_csv(
        PROC / "weekly_scorecard.csv", dtype={"freight_total_brl": str}
    )
    bands = pd.read_csv(PROC / "distance_bands.csv").sort_values("band_order")
    band_summary = pd.read_csv(PROC / "distance_band_summary.csv")
    states = pd.read_csv(PROC / "state_coverage.csv")
    summary = json.loads((PROC / "analyze_summary.json").read_text(encoding="utf-8"))
    return weekly, bands, band_summary, states, summary


def compute(weekly, bands, band_summary, states, summary):
    """Format every page number from the extracts. No metric is re-derived
    from raw data here; sums are of counts that the extracts already hold,
    and medians are read, never averaged across weeks.
    """
    m = {}
    delivered = int(weekly["delivered_orders"].fillna(0).sum())
    items = int(weekly["delivered_items"].fillna(0).sum())
    on_time = int(weekly["on_time_orders"].fillna(0).sum())
    cross = int(weekly["cross_state_items"].fillna(0).sum())
    cents = sum(
        int(Decimal(s) * 100)
        for s in weekly["freight_total_brl"].dropna()
        if str(s).strip() != ""
    )
    med = summary["medians"]
    m["delivered_orders"] = n0(delivered)
    m["delivered_items"] = n0(items)
    m["on_time_n"] = n0(on_time)
    m["on_time_pct"] = pct1(on_time, delivered)
    m["cross_n"] = n0(cross)
    m["cross_pct"] = pct1(cross, items)
    m["freight_total"] = brl_from_cents(cents)
    # Extract-level medians are computed on orders/items by Analyze. The
    # weekly medians are never averaged to stand in for them.
    m["median_p2d"] = d1(med["res_med_p2d"][0]["median_x"])
    m["median_transit"] = d1(med["res_med_transit_nonneg"][0]["median_x"])
    m["median_handling"] = d1(med["res_med_handling_nonneg"][0]["median_x"])
    m["median_freight"] = brl(med["res_med_freight"][0]["median_x"])
    m["weeks"] = len(weekly)

    if list(bands["band"]) != BAND_CODES:
        fail(f"band order {list(bands['band'])}")
    # distance_band_summary.csv is the Analyze table at the SAME grain (one
    # row per band). It is not a join across grains. Check that the columns
    # both files carry agree before taking handling and on-time from it.
    bs = band_summary.set_index("band").loc[BAND_CODES]
    for code, row in zip(BAND_CODES, bands.to_dict("records")):
        s = bs.loc[code]
        if int(s["orders"]) != int(row["orders"]):
            fail(f"band {code} orders differ between band extracts")
        if abs(s["median_purchase_to_door"] - row["median_purchase_to_door_days"]) > 1e-9:
            fail(f"band {code} p2d differs between band extracts")
        if abs(s["median_transit_nonneg"] - row["median_transit_days"]) > 1e-9:
            fail(f"band {code} transit differs between band extracts")
        if abs(float(s["median_freight"]) - float(row["median_freight_brl"])) > 1e-9:
            fail(f"band {code} freight differs between band extracts")
    m["band_orders"] = [n0(x) for x in bands["orders"]]
    m["band_p2d"] = [d1(x) for x in bands["median_purchase_to_door_days"]]
    m["band_transit"] = [d1(x) for x in bands["median_transit_days"]]
    m["band_handling"] = [d1(x) for x in bs["median_handling_nonneg"]]
    m["band_handling_range"] = (min(m["band_handling"]), max(m["band_handling"]))
    m["band_ontime"] = [
        pct1(int(n), int(o)) for n, o in zip(bs["on_time_n"], bs["orders"])
    ]
    m["band_freight"] = [brl(x) for x in bands["median_freight_brl"]]

    st = states.set_index("state")
    m["sp_people"] = f"{100 * st.loc['SP', 'people_share']:.1f}%"
    m["sp_sellers"] = f"{100 * st.loc['SP', 'seller_share']:.1f}%"
    m["no_seller_states"] = sorted(
        states.loc[(states["sellers"] == 0) & (states["customer_people"] > 0), "state"]
    )
    dates = summary["snapshot"]["res_dates"][0]
    m["first_delivered_purchase"] = fmt_date(dates["min_purchase_population"])
    m["last_delivered_purchase"] = fmt_date(dates["max_purchase_population"])

    for key, want in EXPECTED.items():
        got = m[key]
        if isinstance(want, list):
            got = list(got)
        if got != want:
            fail(f"{key}: page would show {got!r}, locked value is {want!r}")
        print(f"CHECK {key}: PASS {got}")
    return m


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------
def svg_text(x, y, text, size=12, fill=TEXT2, anchor="start", weight=400,
             extra=""):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
        f'text-anchor="{anchor}" font-weight="{weight}"{extra}>{esc(text)}</text>'
    )


def nice_ceiling(value, step):
    return step * math.ceil(value / step)


# ---------------------------------------------------------------------------
# Exhibit 1: weekly trend, three stacked panels on one time axis
# ---------------------------------------------------------------------------
def weekly_svg(weekly, m, width, compact):
    """Orders, median purchase-to-door and on-time on a shared week axis.

    The week axis is every Monday from the first purchase week to the last.
    Mondays missing from the extract (no purchase at all) are shaded as gaps.
    Lines break at any blank, so a missing week is never drawn as zero.
    """
    frame = weekly.copy()
    frame["week_start"] = pd.to_datetime(frame["week_start"])
    frame = frame.set_index("week_start").sort_index()
    mondays = pd.date_range(frame.index.min(), frame.index.max(), freq="W-MON")
    full = frame.reindex(mondays)
    missing = [d for d in mondays if d not in frame.index]

    t0 = mondays[0]
    t1 = mondays[-1] + pd.Timedelta(days=7)
    left = 44 if compact else 56
    right = 44 if compact else 92  # room for the extract-level reference labels
    plot_w = width - left - right
    span = (t1 - t0).days

    def X(day):
        return left + (pd.Timestamp(day) - t0).days / span * plot_w

    week_w = 7 / span * plot_w
    fs = 11 if compact else 12
    title_fs = 11 if compact else 12.5

    # The week annotated in panels 2 and 3: the lowest weekly on-time rate
    # among weeks with at least 100 delivered orders. The threshold keeps a
    # one-order week (0% or 100%) from being the "worst week".
    busy = full[full["delivered_orders"] >= 100]
    low_week = busy["on_time_rate"].idxmin()
    low_rate = busy.loc[low_week, "on_time_rate"]
    low_days = busy.loc[low_week, "median_purchase_to_door_days"]
    peak_week = full["delivered_orders"].idxmax()
    peak_orders = full.loc[peak_week, "delivered_orders"]

    max_orders = full["orders_purchased"].max()
    panels = [
        dict(key="orders", h=128 if compact else 150, lo=0,
             hi=nice_ceiling(max_orders * 1.05, 500), ticks=[0, 1000, 2000, 3000],
             fmt=lambda v: f"{int(v):,}"),
        dict(key="days", h=112 if compact else 128, lo=0, hi=20,
             ticks=[0, 5, 10, 15, 20], fmt=lambda v: f"{int(v)}"),
        dict(key="ontime", h=112 if compact else 128, lo=70, hi=100,
             ticks=[70, 80, 90, 100], fmt=lambda v: f"{int(v)}%"),
    ]
    title_gap = 34 if compact else 36
    panel_gap = 18
    y = 0
    for p in panels:
        y += title_gap
        p["top"] = y
        p["bottom"] = y + p["h"]
        y = p["bottom"] + panel_gap
    axis_y = panels[-1]["bottom"]
    height = axis_y + (30 if compact else 34)

    def Y(p, v):
        v = min(max(v, p["lo"]), p["hi"])
        return p["bottom"] - (v - p["lo"]) / (p["hi"] - p["lo"]) * p["h"]

    out = []
    # Gap shading: merge consecutive missing Mondays into runs.
    runs = []
    for d in missing:
        if runs and (d - runs[-1][1]).days == 7:
            runs[-1][1] = d
        else:
            runs.append([d, d])
    for p in panels:
        for a, b in runs:
            x0 = X(a)
            x1 = X(b + pd.Timedelta(days=7))
            out.append(
                f'<rect x="{x0:.1f}" y="{p["top"]:.1f}" width="{x1 - x0:.1f}" '
                f'height="{p["h"]:.1f}" fill="url(#gap-{width})"/>'
            )
    # Highlight band for the annotated week, panels 2 and 3 only.
    for p in panels[1:]:
        out.append(
            f'<rect x="{X(low_week) - 1:.1f}" y="{p["top"]:.1f}" '
            f'width="{week_w + 2:.1f}" height="{p["h"]:.1f}" fill="{ACCENT_BG}"/>'
        )

    # Grid lines, y labels, year separators.
    years = [pd.Timestamp(f"{yr}-01-01") for yr in (2017, 2018)]
    for p in panels:
        for t in p["ticks"]:
            yy = Y(p, t)
            stroke = AXIS if t == p["lo"] else GRID
            out.append(
                f'<line x1="{left}" x2="{left + plot_w:.1f}" y1="{yy:.1f}" '
                f'y2="{yy:.1f}" stroke="{stroke}" stroke-width="1"/>'
            )
            out.append(svg_text(left - 8, yy + 4, p["fmt"](t), fs, MUTED, "end"))
        for yr in years:
            out.append(
                f'<line x1="{X(yr):.1f}" x2="{X(yr):.1f}" y1="{p["top"]:.1f}" '
                f'y2="{p["bottom"]:.1f}" stroke="{CONTEXT}" stroke-dasharray="2 3"/>'
            )

    # Panel titles with inline keys (direct labels instead of a legend).
    p1, p2, p3 = panels
    t_y = lambda p: p["top"] - (12 if compact else 14)
    if compact:
        out.append(
            f'<text x="0" y="{t_y(p1):.1f}" font-size="{title_fs}" fill="{TEXT}" font-weight="600">'
            f'Orders per week <tspan fill="{SERIES}">■ delivered</tspan> '
            f'<tspan fill="{MUTED}">■ all purchases</tspan></text>'
        )
    else:
        out.append(
            f'<text x="0" y="{t_y(p1):.1f}" font-size="{title_fs}" fill="{TEXT}" font-weight="600">'
            f'Orders per week, by purchase week  '
            f'<tspan fill="{SERIES}" font-weight="500">■ delivered orders</tspan>  '
            f'<tspan fill="{MUTED}" font-weight="500">■ all purchases, any status</tspan></text>'
        )
    out.append(svg_text(0, t_y(p2), "Median purchase-to-door, days" if not compact
                        else "Median purchase-to-door, days", title_fs, TEXT, weight=600))
    out.append(svg_text(0, t_y(p3), "On-time rate, % of delivered orders (calendar date)"
                        if not compact else "On-time rate, % of delivered", title_fs,
                        TEXT, weight=600))

    # Panel 1: purchased bars behind delivered bars. Both are counts that
    # exist in the extract; no week is filled in.
    bw = week_w * 0.78
    for d, row in full.iterrows():
        if pd.isna(row["orders_purchased"]):
            continue
        x = X(d) + (week_w - bw) / 2
        yp = Y(p1, row["orders_purchased"])
        out.append(
            f'<rect x="{x:.2f}" y="{yp:.2f}" width="{bw:.2f}" '
            f'height="{p1["bottom"] - yp:.2f}" fill="{CONTEXT}"/>'
        )
        if not pd.isna(row["delivered_orders"]):
            yd = Y(p1, row["delivered_orders"])
            out.append(
                f'<rect x="{x:.2f}" y="{yd:.2f}" width="{bw:.2f}" '
                f'height="{p1["bottom"] - yd:.2f}" fill="{SERIES}"/>'
            )

    # Lines that break at blanks. An isolated week gets a dot so it is not
    # silently dropped.
    def line(p, col, scale=1.0, color=SERIES):
        segs, cur = [], []
        for d, v in full[col].items():
            if pd.isna(v):
                if cur:
                    segs.append(cur)
                cur = []
            else:
                cur.append((X(d) + week_w / 2, Y(p, v * scale)))
        if cur:
            segs.append(cur)
        parts = []
        for seg in segs:
            if len(seg) == 1:
                parts.append(
                    f'<circle cx="{seg[0][0]:.1f}" cy="{seg[0][1]:.1f}" r="2.2" fill="{color}"/>'
                )
            else:
                pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in seg)
                parts.append(
                    f'<polyline points="{pts}" fill="none" stroke="{color}" '
                    f'stroke-width="{1.6 if compact else 1.8}" stroke-linejoin="round"/>'
                )
        return parts

    # Extract-level reference lines, labelled in the right margin.
    p2d = float(m["median_p2d"])
    ot = float(m["on_time_pct"].rstrip("%"))
    for p, v, label in ((p2), p2d, ("Full-period median", f"{m['median_p2d']} days")), \
                       ((p3), ot, ("Full-period rate", m["on_time_pct"])):
        yy = Y(p, v)
        out.append(
            f'<line x1="{left}" x2="{left + plot_w + 6:.1f}" y1="{yy:.1f}" y2="{yy:.1f}" '
            f'stroke="{TEXT2}" stroke-width="1" stroke-dasharray="4 3"/>'
        )
        if compact:
            out.append(svg_text(left + plot_w + 8, yy + 4, label[1].replace(" days", "d"),
                                fs, TEXT2, weight=600))
        else:
            out.append(svg_text(left + plot_w + 10, yy - 3, label[0], 11, MUTED))
            out.append(svg_text(left + plot_w + 10, yy + 11, label[1], 12, TEXT2, weight=600))

    out += line(p2, "median_purchase_to_door_days")
    out += line(p3, "on_time_rate", scale=100)

    # Values outside the panel range are pinned to the edge with a marker and
    # their true value, instead of stretching the axis for a one-order week.
    for p, col, scale in ((p2, "median_purchase_to_door_days", 1), (p3, "on_time_rate", 100)):
        for d, row in full.iterrows():
            v = row[col]
            if pd.isna(v):
                continue
            v = v * scale
            if v > p["hi"] or v < p["lo"]:
                cx = X(d) + week_w / 2
                above = v > p["hi"]
                cy = p["top"] + 4 if above else p["bottom"] - 4
                tri = (f"{cx - 4:.1f},{cy + 3:.1f} {cx + 4:.1f},{cy + 3:.1f} {cx:.1f},{cy - 4:.1f}"
                       if above else
                       f"{cx - 4:.1f},{cy - 3:.1f} {cx + 4:.1f},{cy - 3:.1f} {cx:.1f},{cy + 4:.1f}")
                out.append(f'<polygon points="{tri}" fill="{TEXT2}"/>')
                n_del = int(row["delivered_orders"])
                txt = (f"{v:.1f} days, {n_del} order" if scale == 1 else
                       f"{v:.0f}%, {n_del} order") + ("" if n_del == 1 else "s")
                ty = cy + 4 if above else cy - 1
                out.append(svg_text(cx + 7, ty, txt, fs - 1, TEXT2))

    # Annotations: peak week (panel 1) and the low on-time week (2 and 3).
    px = X(peak_week) + week_w / 2
    py = Y(p1, peak_orders)
    pk_txt = (f"Peak: {int(peak_orders):,} delivered, week of {fmt_date(peak_week)}"
              if not compact else f"Peak {int(peak_orders):,}, wk of {fmt_date(peak_week)[:-5]}")
    # Desktop: label to the left of the peak bar. Mobile: to the right, so it
    # does not run into the "No purchases" label over the 2016 gap.
    if compact:
        out.append(svg_text(px + 6, py + 9, pk_txt, fs, TEXT, "start", 500))
    else:
        out.append(svg_text(px - 8, py + 10, pk_txt, fs, TEXT, "end", 500))

    lx = X(low_week) + week_w / 2
    out.append(
        f'<circle cx="{lx:.1f}" cy="{Y(p3, low_rate * 100):.1f}" r="3.6" fill="{ACCENT}"/>'
    )
    out.append(
        f'<circle cx="{lx:.1f}" cy="{Y(p2, low_days):.1f}" r="3.6" fill="{ACCENT}"/>'
    )
    week_txt = f"week of {fmt_date(low_week)}"
    out.append(svg_text(lx - 9, Y(p3, low_rate * 100) + 4,
                        f"{100 * low_rate:.1f}%" + ("" if compact else f", {week_txt}"),
                        fs, ACCENT, "end", 600))
    out.append(svg_text(lx - 9, Y(p2, low_days) - 4,
                        f"{low_days:.1f} days" + ("" if compact else f", {week_txt}"),
                        fs, ACCENT, "end", 600))

    # Gap and tail labels, panel 1, so the reader knows why a stretch is empty.
    if runs:
        longest = max(runs, key=lambda r: (r[1] - r[0]).days)
        gx = X(longest[0])
        out.append(svg_text(gx, p1["top"] + 12, "No purchases:", fs - 1, TEXT2, weight=600))
        out.append(svg_text(gx, p1["top"] + 25, "gap, not zero", fs - 1, TEXT2))
    no_del = full[full["orders_purchased"].notna() & full["delivered_orders"].isna()]
    tail = no_del[no_del.index > pd.Timestamp("2018-01-01")]
    if len(tail):
        tx = X(tail.index[0])
        out.append(
            f'<line x1="{tx:.1f}" x2="{X(tail.index[-1]) + week_w:.1f}" y1="{p2["bottom"] - 6:.1f}" '
            f'y2="{p2["bottom"] - 6:.1f}" stroke="{MUTED}" stroke-width="1"/>'
        )
        if not compact:
            # Top-right of the panel: late-2018 weekly medians stay well
            # below 15 days, so this corner is empty.
            xr = left + plot_w
            out.append(svg_text(xr, p2["top"] + 12, "Sep–Oct 2018: purchases but no", fs - 1, TEXT2, "end"))
            out.append(svg_text(xr, p2["top"] + 25, "delivered order, left blank ↓", fs - 1, TEXT2, "end"))

    # X axis: quarters on desktop, half-years on mobile.
    step = 6 if compact else 3
    tick = pd.Timestamp("2016-10-01")
    while tick <= t1:
        if tick.month in ((1, 7) if compact else (1, 4, 7, 10)):
            xx = X(tick)
            if left <= xx <= left + plot_w:
                out.append(
                    f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{axis_y:.1f}" y2="{axis_y + 5:.1f}" stroke="{MUTED}"/>'
                )
                label = tick.strftime("%b '%y") if compact else tick.strftime("%b %Y")
                out.append(svg_text(xx, axis_y + 18, label, fs, MUTED, "middle"))
        tick = tick + pd.DateOffset(months=1)
    out.append(svg_text(left + plot_w, axis_y + (30 if compact else 32),
                        "Week of purchase (weeks start Monday)", fs - 1, MUTED, "end")
               if not compact else "")

    defs = (
        f'<defs><pattern id="gap-{width}" width="6" height="6" patternUnits="userSpaceOnUse" '
        f'patternTransform="rotate(45)"><rect width="6" height="6" fill="{GAP_BG}"/>'
        f'<line x1="0" y1="0" x2="0" y2="6" stroke="{GAP_LINE}" stroke-width="2"/></pattern></defs>'
    )
    return (
        f'<svg viewBox="0 0 {width} {height + (6 if not compact else 0)}" role="img" '
        f'aria-label="Weekly delivered orders, median purchase-to-door days and on-time rate">'
        f"{defs}{''.join(out)}</svg>"
    ), dict(low_week=low_week, low_rate=low_rate, low_days=low_days,
            peak_week=peak_week, peak_orders=peak_orders, n_missing=len(missing),
            n_no_delivery=len(full[full["orders_purchased"].notna() & full["delivered_orders"].isna()]))


# ---------------------------------------------------------------------------
# Exhibit 2: distance bands (one extract at band grain)
# ---------------------------------------------------------------------------
def band_attrs(i, code, m):
    """Each band row is one focusable, clickable group. The same data-band
    code is on the matching row in all three exhibits and in the table, so a
    click highlights the band everywhere. Band grain only; nothing is joined.
    """
    label = (
        f"{BAND_SHORT[i]}: {m['band_orders'][i]} delivered orders, median handling "
        f"{m['band_handling'][i]} days, median transit {m['band_transit'][i]} days, "
        f"median purchase-to-door {m['band_p2d'][i]} days, on time {m['band_ontime'][i]}, "
        f"median freight per item {m['band_freight'][i]}. Press Enter to highlight this band."
    )
    return (
        f'class="band-mark" data-band="{code}" tabindex="0" role="button" '
        f'aria-pressed="false" aria-label="{esc(label)}"'
    )


def hit_rect(x, y, w, h):
    # Invisible hit area for hover, tap and the keyboard focus ring. It is
    # painted (fill-opacity 0, not fill none) so it receives pointer events.
    return (f'<rect class="hit" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{ON_BG}" fill-opacity="0"/>')


def days_split_svg(bands, band_summary, m):
    """Handling and transit medians side by side per band.

    Not stacked: medians of two legs do not add up to the median of the
    whole wait, so a stacked bar would draw a total that was never measured.
    """
    bs = band_summary.set_index("band").loc[BAND_CODES]
    W, left, right = 380, 92, 44
    row_h, bar_h, gap = 44, 12, 3
    top = 14
    H = top + row_h * 5 + 34
    xmax = 14.0
    X = lambda v: left + v / xmax * (W - left - right)
    out = []
    for t in (0, 5, 10):
        out.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top - 4}" y2="{top + row_h * 5}" stroke="{GRID}"/>')
        out.append(svg_text(X(t), top + row_h * 5 + 16, f"{t}", 11, MUTED, "middle"))
    out.append(svg_text(W - right, top + row_h * 5 + 30, "Median days", 11, MUTED, "end"))
    for i, code in enumerate(BAND_CODES):
        y0 = top + i * row_h + 6
        hand = float(bs.loc[code, "median_handling_nonneg"])
        tran = float(bands.iloc[i]["median_transit_days"])
        last = i == 4
        out.append(f"<g {band_attrs(i, code, m)}>")
        out.append(hit_rect(0, y0 - 9, W, row_h))
        out.append(svg_text(0, y0 + bar_h + 3, BAND_SHORT[i], 12, TEXT, weight=600 if last else 400))
        out.append(f'<rect x="{left}" y="{y0:.1f}" width="{X(hand) - left:.1f}" height="{bar_h}" fill="{CONTEXT}"/>')
        out.append(f'<rect x="{left}" y="{y0 + bar_h + gap:.1f}" width="{X(tran) - left:.1f}" height="{bar_h}" fill="{ACCENT if last else SERIES}"/>')
        h_lab = f"{hand:.1f}" + (" handling" if i == 0 else "")
        t_lab = f"{tran:.1f}" + (" transit" if i == 0 else "")
        out.append(svg_text(X(hand) + 5, y0 + bar_h - 2, h_lab, 11, TEXT2))
        out.append(svg_text(X(tran) + 5, y0 + 2 * bar_h + gap - 2, t_lab, 11,
                            ACCENT if last else SERIES, weight=600))
        out.append("</g>")
    return f'<svg viewBox="0 0 {W} {H}" role="group" aria-label="Median handling and transit days by distance band">{"".join(out)}</svg>'


def ontime_svg(bands, band_summary, m):
    """Dot plot on a 85-100% scale. Dots, not bars, because the axis does not
    start at zero; the median wait sits next to each rate so the two are read
    together.
    """
    bs = band_summary.set_index("band").loc[BAND_CODES]
    W, left, right = 380, 92, 70
    row_h, top = 44, 26
    H = top + row_h * 5 + 20
    lo, hi = 85.0, 100.0
    X = lambda v: left + (v - lo) / (hi - lo) * (W - left - right)
    out = []
    for t in (85, 90, 95, 100):
        out.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top - 6}" y2="{top + row_h * 5 - 10}" stroke="{GRID}"/>')
        out.append(svg_text(X(t), top + row_h * 5 + 6, f"{t}%", 11, MUTED, "middle"))
    overall = float(m["on_time_pct"].rstrip("%"))
    out.append(f'<line x1="{X(overall):.1f}" x2="{X(overall):.1f}" y1="{top - 6}" y2="{top + row_h * 5 - 10}" stroke="{TEXT2}" stroke-dasharray="3 3"/>')
    out.append(svg_text(X(overall), top - 12, f"{m['on_time_pct']} overall", 11, TEXT2, "middle"))
    out.append(svg_text(W, top - 12, "Median wait", 11, TEXT2, "end", 600))
    for i, code in enumerate(BAND_CODES):
        yc = top + i * row_h + 12
        rate = 100.0 * int(bs.loc[code, "on_time_n"]) / int(bs.loc[code, "orders"])
        last = i == 4
        color = ACCENT if last else SERIES
        out.append(f"<g {band_attrs(i, code, m)}>")
        out.append(hit_rect(0, yc - row_h / 2, W, row_h))
        out.append(f'<line x1="{left}" x2="{W - right + 6}" y1="{yc}" y2="{yc}" stroke="{ROWLINE}"/>')
        out.append(svg_text(0, yc + 4, BAND_SHORT[i], 12, TEXT, weight=600 if last else 400))
        out.append(f'<circle cx="{X(rate):.1f}" cy="{yc}" r="6" fill="{color}"/>')
        out.append(svg_text(X(rate) - 10, yc + 4, m["band_ontime"][i], 12, color, "end", 600))
        out.append(svg_text(W, yc + 4, f"{m['band_p2d'][i]} days", 12,
                            ACCENT if last else TEXT, "end", 700 if last else 400))
        out.append("</g>")
    return f'<svg viewBox="0 0 {W} {H}" role="group" aria-label="On-time rate and median wait by distance band">{"".join(out)}</svg>'


def freight_svg(bands, m):
    """Median freight per item by band, bars from zero, BRL."""
    W, left, right = 380, 92, 64
    row_h, bar_h, top = 44, 18, 8
    H = top + row_h * 5 + 34
    xmax = 28.0
    X = lambda v: left + v / xmax * (W - left - right)
    out = []
    for t in (0, 10, 20):
        out.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top - 2}" y2="{top + row_h * 5}" stroke="{GRID}"/>')
        out.append(svg_text(X(t), top + row_h * 5 + 16, f"R${t}", 11, MUTED, "middle"))
    out.append(svg_text(W - right, top + row_h * 5 + 30, "Median freight per item, BRL", 11, MUTED, "end"))
    for i, code in enumerate(BAND_CODES):
        y0 = top + i * row_h + 10
        v = float(bands.iloc[i]["median_freight_brl"])
        last = i == 4
        color = ACCENT if last else SERIES
        out.append(f"<g {band_attrs(i, code, m)}>")
        out.append(hit_rect(0, y0 - (row_h - bar_h) / 2, W, row_h))
        out.append(svg_text(0, y0 + bar_h - 4, BAND_SHORT[i], 12, TEXT, weight=600 if last else 400))
        out.append(f'<rect x="{left}" y="{y0}" width="{X(v) - left:.1f}" height="{bar_h}" fill="{color}"/>')
        out.append(svg_text(X(v) + 6, y0 + bar_h - 4, m["band_freight"][i], 12, color, weight=600))
        out.append("</g>")
    return f'<svg viewBox="0 0 {W} {H}" role="group" aria-label="Median freight per item by distance band">{"".join(out)}</svg>'


# ---------------------------------------------------------------------------
# Exhibit 3: coverage dumbbell (one extract at state grain)
# ---------------------------------------------------------------------------
HIGHLIGHT_STATES = {"SP", "RJ", "PR"}
COV_TOP, COV_ROW_H = 46, 20


def coverage_svg(states, no_seller):
    """Customer share and seller share per state on one 0-67% axis.

    Shares come straight from people_share and seller_share. They are not
    recomputed from customer_people, whose rows sum to 96,136 (39 people
    appear in two states); the distinct-people denominator is 96,096.

    Each state is one <g> drawn around y = 0 and moved into place with a CSS
    transform. The page script re-sorts by changing only that transform, so
    the marks themselves are never redrawn or recomputed in the browser.
    """
    df = states.sort_values(["people_share", "state"], ascending=[False, True]).reset_index(drop=True)
    W, left, right = 420, 38, 14
    row_h, top = COV_ROW_H, COV_TOP
    n = len(df)
    H = top + row_h * n + 34
    xmax = 0.67  # headroom so the SP 59.7% label stays inside the frame
    X = lambda v: left + v / xmax * (W - left - right)
    out = []
    # Fixed key at the top. It no longer sits on the first row, because the
    # first row changes when the reader re-sorts.
    ky = 12
    out.append(f'<circle cx="{left + 5}" cy="{ky}" r="4.6" fill="{SERIES}"/>')
    out.append(svg_text(left + 14, ky + 4, "Customer share", 12, SERIES, weight=700))
    out.append(f'<circle cx="{left + 130}" cy="{ky}" r="4.6" fill="{ACCENT}"/>')
    out.append(svg_text(left + 139, ky + 4, "Seller share", 12, ACCENT, weight=700))
    out.append(f'<circle cx="{left + 236}" cy="{ky}" r="4.2" fill="{BG}" stroke="{ACCENT}" stroke-width="1.8"/>')
    out.append(svg_text(left + 245, ky + 4, "no sellers", 12, ACCENT, extra=' font-style="italic"'))
    y_last = top + row_h * (n - 1)
    for t in (0, 10, 20, 30, 40, 50, 60):
        out.append(f'<line x1="{X(t / 100):.1f}" x2="{X(t / 100):.1f}" y1="{top - row_h / 2:.1f}" y2="{y_last + row_h / 2:.1f}" stroke="{GRID}"/>')
        out.append(svg_text(X(t / 100), y_last + row_h / 2 + 16, f"{t}%", 11, MUTED, "middle"))
    out.append(svg_text(W - right, y_last + row_h / 2 + 32,
                        "Share of all customer people, or of all sellers", 11, MUTED, "end"))
    for i, r in df.iterrows():
        yc = top + i * row_h
        st = r["state"]
        hi_row = st in HIGHLIGHT_STATES
        none = st in no_seller
        name = STATE_NAMES[st]
        pv = f"{100 * r['people_share']:.1f}%"
        sv = f"{100 * r['seller_share']:.1f}%"
        aria = (f"{name} ({st}): {int(r['customer_people']):,} customer people, {pv} of all; "
                f"{int(r['sellers']):,} sellers, {sv} of all. Press Enter to select.")
        out.append(
            f'<g class="st-row" data-state="{st}" tabindex="0" role="button" aria-pressed="false" '
            f'aria-label="{esc(aria)}" style="transform:translate(0px,{yc}px)">'
        )
        bg = ROW_HI if hi_row else (ROW_NOSELL if none else BG)
        out.append(f'<rect class="rowbg" x="0" y="{-row_h / 2}" width="{W}" height="{row_h}" fill="{bg}" fill-opacity="{1 if (hi_row or none) else 0}"/>')
        out.append(f'<rect class="selbg" x="0.5" y="{-row_h / 2 + 0.5}" width="{W - 1}" height="{row_h - 1}" fill="{SEL_BG}" stroke="{SERIES}" stroke-width="1"/>')
        out.append(svg_text(0, 4, st, 12, TEXT if (hi_row or none) else TEXT2,
                            weight=700 if (hi_row or none) else 400))
        xp, xs = X(r["people_share"]), X(r["seller_share"])
        out.append(f'<line x1="{min(xp, xs):.1f}" x2="{max(xp, xs):.1f}" y1="0" y2="0" stroke="{CONTEXT}" stroke-width="2.5"/>')
        out.append(f'<circle cx="{xp:.1f}" cy="0" r="4.6" fill="{SERIES}"/>')
        if none:
            # Hollow ring at zero, drawn on top so it stays visible.
            out.append(f'<circle cx="{xs:.1f}" cy="0" r="4.4" fill="{BG}" stroke="{ACCENT}" stroke-width="1.8"/>')
            out.append(svg_text(X(0.025), 4, "customers, no sellers", 12, ACCENT, extra=' font-style="italic"'))
        else:
            out.append(f'<circle cx="{xs:.1f}" cy="0" r="4.6" fill="{ACCENT}"/>')
        if hi_row:
            # Value labels on the three highlighted states only. The larger
            # share is labelled right of its dot. The smaller one goes left
            # of its dot when there is room (SP); otherwise it follows the
            # larger label in its own colour (RJ, PR), so no label sits on a dot.
            big_x, small_x = max(xp, xs), min(xp, xs)
            big_txt, big_col = (sv, ACCENT) if xs >= xp else (pv, SERIES)
            small_txt, small_col = (pv, SERIES) if xs >= xp else (sv, ACCENT)
            if small_x - 46 > left + 4:
                out.append(svg_text(small_x - 8, 4, small_txt, 12, small_col, "end", 600))
                out.append(svg_text(big_x + 8, 4, big_txt, 12, big_col, "start", 600))
            else:
                out.append(
                    f'<text x="{big_x + 8:.1f}" y="4" font-size="12" font-weight="600">'
                    f'<tspan fill="{big_col}">{big_txt}</tspan>'
                    f'<tspan fill="{MUTED}" font-weight="400"> vs </tspan>'
                    f'<tspan fill="{small_col}">{small_txt}</tspan></text>'
                )
        out.append("</g>")
    return (f'<svg id="cov-svg" data-top="{top}" data-rowh="{row_h}" viewBox="0 0 {W} {H}" '
            f'role="group" aria-label="Customer share and seller share by state">{"".join(out)}</svg>')


# ---------------------------------------------------------------------------
# Embedded data for the page script
# ---------------------------------------------------------------------------
def page_data(weekly, bands, band_summary, states, m):
    """Everything the browser needs, as JSON, one block per extract.

    The three extracts stay separate keys (weeks, bands, states); the script
    never looks one up in another. Display strings are formatted here in
    Python, with the same helpers as the static page, so a tooltip cannot
    round differently from the table next to it. Raw numbers are included
    only where the script must position a mark or sum weekly counts.
    """
    frame = weekly.copy()
    frame["week_start"] = pd.to_datetime(frame["week_start"])
    frame = frame.set_index("week_start").sort_index()
    mondays = pd.date_range(frame.index.min(), frame.index.max(), freq="W-MON")

    def num(v, cast=float):
        return None if pd.isna(v) else cast(v)

    weeks = []
    for d in mondays:
        if d not in frame.index:
            # A Monday with no purchase: a gap, never a zero.
            weeks.append({"d": d.strftime("%Y-%m-%d"), "s": "gap", "lab": {"d": fmt_date(d)}})
            continue
        r = frame.loc[d]
        delivered = num(r["delivered_orders"], int)
        rec = {
            "d": d.strftime("%Y-%m-%d"),
            # nodel: purchases but no delivered order, so days, on-time,
            # freight and cross-state stay blank (None), not zero.
            "s": "ok" if delivered is not None else "nodel",
            "p": int(r["orders_purchased"]),
            "n": delivered,
            "m": num(r["median_purchase_to_door_days"]),
            "r": num(r["on_time_rate"]),
            "o": num(r["on_time_orders"], int),
            "it": num(r["delivered_items"], int),
            "ci": num(r["cross_state_items"], int),
        }
        lab = {"d": fmt_date(d), "p": n0(rec["p"])}
        if delivered is not None:
            lab.update(n=n0(delivered), m=d1(rec["m"]), r=f"{100 * rec['r']:.1f}%", o=n0(rec["o"]))
        rec["lab"] = lab
        weeks.append(rec)

    # Guards on the embedded block: the weekly counts the script will sum
    # must reproduce the locked full-period totals exactly.
    ok = [w for w in weeks if w["s"] == "ok"]
    checks = {
        "json purchase weeks": (sum(w["s"] != "gap" for w in weeks), EXPECTED["weeks"]),
        "json gap Mondays": (sum(w["s"] == "gap" for w in weeks), 11),
        "json weeks without delivery": (sum(w["s"] == "nodel" for w in weeks), 10),
        "json delivered orders": (n0(sum(w["n"] for w in ok)), EXPECTED["delivered_orders"]),
        "json on-time orders": (n0(sum(w["o"] for w in ok)), EXPECTED["on_time_n"]),
        "json delivered items": (n0(sum(w["it"] for w in ok)), EXPECTED["delivered_items"]),
        "json cross-state items": (n0(sum(w["ci"] for w in ok)), EXPECTED["cross_n"]),
        "json on-time rate from weekly sums": (
            pct1(sum(w["o"] for w in ok), sum(w["n"] for w in ok)), EXPECTED["on_time_pct"]),
        "json cross-state share from weekly sums": (
            pct1(sum(w["ci"] for w in ok), sum(w["it"] for w in ok)), EXPECTED["cross_pct"]),
    }
    for label, (got, want) in checks.items():
        if got != want:
            fail(f"{label}: {got} != {want}")
        print(f"CHECK {label}: PASS {got}")

    idx = {w["d"]: i for i, w in enumerate(weeks)}
    busy = [i for i, w in enumerate(weeks) if w["s"] == "ok" and w["n"] >= 100]
    low_idx = min(busy, key=lambda i: weeks[i]["r"])
    peak_idx = max((i for i, w in enumerate(weeks) if w["s"] == "ok"), key=lambda i: weeks[i]["n"])

    def preset(lo, hi):
        sel = [i for i, w in enumerate(weeks) if lo <= w["d"] < hi]
        return [sel[0], sel[-1]]

    band_rows = []
    for i, r in enumerate(bands.to_dict("records")):
        band_rows.append({
            "code": BAND_CODES[i], "label": r["band_label"], "short": BAND_SHORT[i],
            "orders": m["band_orders"][i], "items": n0(r["items"]),
            "hand": m["band_handling"][i], "tran": m["band_transit"][i],
            "door": m["band_p2d"][i], "ot": m["band_ontime"][i], "fr": m["band_freight"][i],
        })

    state_rows = []
    for r in states.to_dict("records"):
        state_rows.append({
            "code": r["state"], "name": STATE_NAMES[r["state"]],
            "people": n0(r["customer_people"]), "sellers": n0(r["sellers"]),
            "ps": r["people_share"], "ss": r["seller_share"],
            "psl": f"{100 * r['people_share']:.1f}%", "ssl": f"{100 * r['seller_share']:.1f}%",
        })

    return {
        "weeks": weeks,
        "ordersHi": int(nice_ceiling(max(w.get("p") or 0 for w in weeks) * 1.05, 500)),
        "lowIdx": low_idx, "peakIdx": peak_idx,
        "presets": {
            "all": [0, len(weeks) - 1],
            "2017": preset("2017-01-01", "2018-01-01"),
            "2018": preset("2018-01-01", "2019-01-01"),
        },
        # Reference lines sit at the displayed full-period figures; the label
        # next to each is the locked string itself.
        "ref": {"p2d": float(m["median_p2d"]), "p2dLab": m["median_p2d"],
                "ot": float(m["on_time_pct"].rstrip("%")), "otLab": m["on_time_pct"]},
        "bands": band_rows,
        "states": state_rows,
        "colors": {"series": SERIES, "text": TEXT, "text2": TEXT2, "muted": MUTED, "context": CONTEXT,
                   "rowline": ROWLINE, "grid": GRID, "axis": AXIS, "accent": ACCENT, "accentBg": ACCENT_BG,
                   "bg": BG, "gapBg": GAP_BG, "gapLine": GAP_LINE},
    }



# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
CSS = """
:root{color-scheme:dark;--bg:%(BG)s;--surface:%(SURFACE)s;--surface2:%(SURFACE2)s;--border:%(BORDER)s;
--rule:%(RULE)s;--head:%(HEAD)s;--body:%(BODY)s;--text:%(TEXT)s;--text2:%(TEXT2)s;--muted:%(MUTED)s;
--series:%(SERIES)s;--context:%(CONTEXT)s;--rowline:%(ROWLINE)s;--accent:%(ACCENT)s;--gold:%(GOLD)s;
--on-bg:%(ON_BG)s;
--serif:Georgia,"Iowan Old Style","Palatino Linotype","Source Serif 4","Noto Serif",serif;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%%;background:#000}
body{margin:0;background:#000;color:var(--body);font:15px/1.55 var(--sans);
font-variant-numeric:tabular-nums}
.page{max-width:1200px;margin:0 auto;background:var(--bg);box-shadow:0 0 0 1px var(--border)}
.mast{background:var(--surface);border-bottom:1px solid var(--border);color:var(--text2);padding:11px 48px;display:flex;justify-content:space-between;
gap:16px;font-size:11.5px;letter-spacing:.08em;text-transform:uppercase}
.mast b{color:var(--head);font-weight:600}
.mast .live{color:var(--accent)}
header{padding:40px 48px 8px}
.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--gold);font-weight:700;margin:0 0 12px}
h1{font-family:var(--serif);font-weight:700;color:var(--head);font-size:34px;line-height:1.18;margin:0 0 14px;max-width:1000px;letter-spacing:-.005em}
.dek{font-size:18px;line-height:1.5;color:var(--body);max-width:980px;margin:0 0 16px}
.meta{font-size:12.5px;color:var(--text2);margin:0;padding:12px 0 0;border-top:1px solid var(--rule);display:flex;flex-wrap:wrap;gap:6px 22px}
.meta span{white-space:nowrap}
.meta b{color:var(--head)}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:0;margin:22px 48px 6px;background:var(--surface);border:1px solid var(--border);border-top:3px solid var(--series);border-radius:0 0 4px 4px}
.kpi{padding:16px 18px 16px;border-right:1px solid var(--border)}
.kpi:last-child{border-right:0}
.kpi .k{font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--text2);font-weight:600;margin:0 0 6px;min-height:2.7em;line-height:1.35}
.kpi .v{font-size:31px;line-height:1.1;font-weight:650;color:var(--head);margin:0 0 6px;letter-spacing:-.01em}
.kpi .v small{font-size:16px;font-weight:500;color:var(--text2);margin-left:3px}
.kpi .c{font-size:12.5px;line-height:1.4;color:var(--text2);margin:0}
section{padding:34px 48px 30px;border-top:1px solid var(--rule)}
section:first-of-type{border-top:0}
.sec-label{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700;margin:0 0 8px}
h2{font-family:var(--serif);font-weight:700;color:var(--head);font-size:23px;line-height:1.28;margin:0 0 8px;max-width:980px}
.lede{color:var(--body);margin:0 0 20px;max-width:900px}
.exhibit{margin:0}
.ex-tag{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);font-weight:700;margin:0 0 3px}
.ex-title{font-size:15px;font-weight:650;color:var(--head);margin:0 0 12px;line-height:1.35}
.source{font-size:11.5px;color:var(--muted);margin:10px 0 0;line-height:1.45}
svg{display:block;width:100%%;height:auto;font-family:var(--sans);overflow:visible}
.wk-mobile{display:none}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:28px 36px}
.grid3 .exhibit{display:flex;flex-direction:column}
.grid3 .exhibit .ex-title{min-height:42px}
.cov{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,5fr);gap:40px;align-items:start}
.cov .exhibit svg{max-width:520px}
.callouts{display:grid;gap:0;background:var(--surface);border:1px solid var(--border);border-top:3px solid var(--series);padding:0 18px;border-radius:0 0 4px 4px}
.co{padding:14px 0 14px;border-bottom:1px solid var(--border)}
.co:last-child{border-bottom:0}
.co .big{font-size:26px;font-weight:650;color:var(--head);line-height:1.1;margin:0 0 4px}
.co .big.acc{color:var(--accent)}
.co .big span{color:var(--text2)!important}
.co p{margin:0;color:var(--body);font-size:14px}
.co b{color:var(--head)}
table{border-collapse:collapse;width:100%%;font-size:13.5px;margin:26px 0 0;color:var(--text)}
th,td{padding:8px 10px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{font-size:11.5px;letter-spacing:.04em;text-transform:uppercase;color:var(--text2);font-weight:600;border-bottom:1.5px solid var(--series);vertical-align:bottom;white-space:normal}
tbody tr:hover td{background:var(--surface)}
tbody tr:last-child td{color:var(--accent);font-weight:600}
.tablewrap{overflow-x:auto}
.short{display:none}
.watch{margin:0 48px 34px;background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--accent);padding:26px 30px 24px}
.watch h2{margin:0 0 4px}
.watch .lede{margin:0 0 18px}
.watch ol{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:26px}
.watch li{counter-increment:w;position:relative;padding-top:38px}
.watch li::before{content:counter(w);position:absolute;top:0;left:0;width:26px;height:26px;border-radius:50%%;background:var(--series);color:var(--bg);font-weight:700;font-size:13px;display:flex;align-items:center;justify-content:center}
.watch li h3{font-size:15.5px;margin:0 0 6px;color:var(--head);line-height:1.35}
.watch li p{margin:0;font-size:14px;color:var(--body)}
.watch .fine{font-size:12px;color:var(--text2);margin:18px 0 0}
footer{background:#111114;border-top:1px solid var(--rule);padding:30px 48px 36px;font-size:12.5px;color:var(--text2)}
footer h4{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--head);margin:0 0 8px}
.fgrid{display:grid;grid-template-columns:3fr 2fr;gap:26px 44px}
footer dl{margin:0;display:grid;grid-template-columns:max-content 1fr;gap:5px 14px}
footer dt{font-weight:600;color:var(--head)}
footer dd{margin:0}
footer ul{margin:0;padding-left:18px}
footer li{margin:0 0 5px}
footer li::marker{color:var(--muted)}
.foot-bottom{margin-top:22px;padding-top:14px;border-top:1px solid var(--rule);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;color:var(--muted)}
a{color:var(--series);text-underline-offset:2px}
a:hover{color:var(--head)}
a:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
@media (max-width:1080px){.grid3{grid-template-columns:1fr 1fr}.watch ol{grid-template-columns:1fr}}
@media (max-width:760px){
 body{font-size:14.5px}
 .mast{padding:9px 18px;font-size:10px;flex-direction:column;gap:2px}
 header{padding:24px 18px 4px}
 h1{font-size:25px}
 .dek{font-size:16px}
 .meta{gap:4px 14px}
 .kpis{grid-template-columns:1fr 1fr;margin:18px 18px 4px}
 .kpi{padding:12px 12px;border-right:0;border-bottom:1px solid var(--border)}
 .kpi:nth-child(odd){border-right:1px solid var(--border)}
 .kpi:last-child{grid-column:1 / -1;border-bottom:0;border-right:0}
 .kpi .v{font-size:25px}
 section{padding:26px 18px 22px}
 h2{font-size:19.5px}
 .wk-desktop{display:none}.wk-mobile{display:block}
 .grid3{grid-template-columns:1fr;gap:30px}
 .grid3 .exhibit .ex-title{min-height:0}
 .cov{grid-template-columns:1fr;gap:20px}
 .watch{margin:0 0 26px;padding:22px 18px;border-left-width:4px;border-right:0}
 footer{padding:24px 18px 28px}
 .fgrid{grid-template-columns:1fr}
 table{font-size:11.5px;margin-top:22px}
 th,td{padding:7px 3px}
 td:first-child{white-space:nowrap}
 thead th{font-size:9px;letter-spacing:.02em}
 .full{display:none}.short{display:inline}
 footer dl{grid-template-columns:1fr}
 footer dd{margin-bottom:6px}
}
@media print{.wk-mobile{display:none}.wk-desktop{display:block}}
""" % dict(BG=BG, SURFACE=SURFACE, SURFACE2=SURFACE2, BORDER=BORDER, RULE=RULE, HEAD=HEAD,
           BODY=BODY, TEXT=TEXT, TEXT2=TEXT2, MUTED=MUTED, SERIES=SERIES, CONTEXT=CONTEXT,
           ROWLINE=ROWLINE, ACCENT=ACCENT, GOLD=GOLD, ON_BG=ON_BG)


# The interactive layer lives in two plain source files next to this script
# and is inlined into the page, so the published HTML is still one file with
# no CDN. Vanilla JS, no library: the charts are the SVG drawn above.
ASSETS = Path(__file__).resolve().parent / "dashboard_assets"


def json_for_script(data):
    """JSON safe to place inside <script>: '</' cannot close the tag."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def page_html(weekly, bands, band_summary, states, summary, m):
    wk_desktop, info = weekly_svg(weekly, m, 1100, compact=False)
    wk_mobile, _ = weekly_svg(weekly, m, 380, compact=True)
    split = days_split_svg(bands, band_summary, m)
    ontime = ontime_svg(bands, band_summary, m)
    freight = freight_svg(bands, m)
    cover = coverage_svg(states, m["no_seller_states"])
    data = page_data(weekly, bands, band_summary, states, m)
    js = (ASSETS / "page.js").read_text(encoding="utf-8")
    css2 = (ASSETS / "interactive.css").read_text(encoding="utf-8")
    state_options = "".join(
        f'<option value="{c}">{esc(STATE_NAMES[c])} ({c})</option>' for c in sorted(states["state"])
    )
    chips = "".join(
        f'<button type="button" data-chip="{c}" aria-pressed="false">{esc(BAND_SHORT[i])}</button>'
        for i, c in enumerate(BAND_CODES)
    )

    st = states.set_index("state")
    share = lambda s, col: f"{100 * st.loc[s, col]:.1f}%"
    hand_lo, hand_hi = m["band_handling_range"]
    low_week = fmt_date(info["low_week"])
    first, last = m["first_delivered_purchase"], m["last_delivered_purchase"]
    no_seller_names = ", ".join(f"{STATE_NAMES[s]} ({s})" for s in ["AL", "TO", "AP", "RR"])
    bs = band_summary.set_index("band").loc[BAND_CODES]

    rows = []
    for i, r in enumerate(bands.to_dict("records")):
        rows.append(
            f'<tr class="band-row" data-band="{BAND_CODES[i]}" tabindex="0">'
            f"<td><span class=\"full\">{esc(r['band_label'])}</span><span class=\"short\">{esc(BAND_SHORT[i].replace(" km", ""))}</span></td>"
            f"<td>{m['band_orders'][i]}</td>"
            f"<td>{m['band_p2d'][i]}</td>"
            f"<td>{m['band_handling'][i]}</td>"
            f"<td>{m['band_transit'][i]}</td>"
            f"<td>{m['band_ontime'][i]}</td>"
            f"<td>{m['band_freight'][i]}</td>"
            "</tr>"
        )
    band_rows = "\n".join(rows)
    source = ("Source: Olist Brazilian E-Commerce Public Dataset (historical extract); "
              "author analysis.")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="{BG}">
<link rel="icon" href="{FAVICON}">
<title>Logistics network review: distance, delivery time and freight (Olist, historical extract)</title>
<meta name="description" content="Weekly operating review of a historical Olist extract: delivered purchases {first} to {last}. Distance, delivery time, on-time rate, freight and state coverage.">
<style>{CSS}{css2}</style>
</head>
<body>
<div class="page">
<div class="mast"><span><b>Logistics network review</b> &nbsp;·&nbsp; Weekly operating review</span><span class="live">Historical extract, not a live feed</span></div>

<header>
  <p class="eyebrow">Olist Brazilian e-commerce · delivered purchases {first} – {last}</p>
  <h1>The farther the haul, the longer the wait: median delivery rises from {m['band_p2d'][0]} to {m['band_p2d'][4]} days, and the extra days sit in transit, not in seller handling</h1>
  <p class="dek">Sellers cluster in São Paulo ({m['sp_sellers']} of sellers against {m['sp_people']} of customers) and {m['cross_pct']} of delivered items cross a state line. A {m['on_time_pct']} on-time rate looks healthy, but it is measured against a delivery promise that stretches with distance, so leadership should read days and on-time side by side.</p>
  <p class="meta">
    <span>Weekly review of a <b>historical extract</b>, not a live feed</span>
    <span>{m['weeks']} purchase weeks</span>
    <span>Distances: zip-centroid straight-line km</span>
    <span>Currency: BRL (R$), not converted</span>
    <span class="hint" data-js hidden>Interactive: hover, filter, click</span>
  </p>
</header>

<p class="kpi-tag">Full period · {first} – {last} · not changed by any filter</p>
<div class="kpis">
  <div class="kpi"><p class="k">Delivered orders</p><p class="v">{m['delivered_orders']}</p><p class="c">{m['delivered_items']} delivered items, purchased {first} – {last}</p></div>
  <div class="kpi"><p class="k">Median purchase-to-door</p><p class="v">{m['median_p2d']}<small>days</small></p><p class="c">Transit {m['median_transit']} days · seller handling {m['median_handling']} days</p></div>
  <div class="kpi"><p class="k">On-time rate</p><p class="v">{m['on_time_pct']}</p><p class="c">{m['on_time_n']} / {m['delivered_orders']} delivered by the estimated calendar date</p></div>
  <div class="kpi"><p class="k">Items crossing a state</p><p class="v">{m['cross_pct']}</p><p class="c">{m['cross_n']} / {m['delivered_items']} delivered items; seller state ≠ customer state</p></div>
  <div class="kpi"><p class="k">Median freight per item</p><p class="v">{m['median_freight']}</p><p class="c">{m['freight_total']} total freight on delivered items</p></div>
</div>

<section>
  <p class="sec-label">1 · Weekly trend</p>
  <h2>Service is not steady week to week: in the week of {low_week} the median wait reached {info['low_days']:.1f} days and only {100 * info['low_rate']:.1f}% arrived on time, against {m['median_p2d']} days and {m['on_time_pct']} for the whole extract</h2>
  <p class="lede">Volume built through 2017 and peaked at {int(info['peak_orders']):,} delivered orders in the week of {fmt_date(info['peak_week'])}. The extract-level figures are computed on orders, not averaged across weeks, so a good total can hide weak weeks.</p>
  <figure class="exhibit">
    <p class="ex-tag">Exhibit 1</p>
    <p class="ex-title">Weekly orders, median purchase-to-door and on-time rate, {m['weeks']} purchase weeks</p>
    <div class="ctrl" id="wk-ctrl" data-js hidden>
      <span><span class="lbl">Range</span><span class="seg" role="group" aria-label="Date range presets"><button type="button" data-preset="all" aria-pressed="true">All</button><button type="button" data-preset="2017" aria-pressed="false">2017</button><button type="button" data-preset="2018" aria-pressed="false">2018</button></span></span>
      <span class="rng"><label class="lbl" for="wk-from">From</label><input type="range" id="wk-from" min="0" step="1" value="0"><output id="wk-from-out" for="wk-from"></output></span>
      <span class="rng"><label class="lbl" for="wk-to">To</label><input type="range" id="wk-to" min="0" step="1"><output id="wk-to-out" for="wk-to"></output></span>
    </div>
    <p class="summary" id="wk-summary" data-js hidden aria-live="polite"></p>
    <div id="wk-host" tabindex="0" role="group" aria-label="Weekly trend chart. Hover or tap a week, or use the left and right arrow keys, to read its values.">
      <div class="wk-desktop">{wk_desktop}</div>
      <div class="wk-mobile">{wk_mobile}</div>
    </div>
    <span class="vh" id="wk-live" aria-live="polite"></span>
    <p class="source">Note: Each point is that week’s median or rate on delivered orders purchased that week. Hatched columns are the {info['n_missing']} Mondays with no purchase (gaps, not zeros). {info['n_no_delivery']} weeks have purchases but no delivered order; their days and on-time are left blank. Values outside a panel’s range are pinned to its edge and labelled. Hover or tap a week (or focus the chart and use ← →) to read it; the range controls rescale the time axis of all three panels together, and the y-axes stay fixed. The last weeks before {last} hold only orders already delivered when the extract ends, so read them with care. {source}</p>
  </figure>
</section>

<section>
  <p class="sec-label">2 · Distance</p>
  <h2>Longer hauls come with longer waits and higher freight, and the extra days are in transit: seller handling stays at {hand_lo}–{hand_hi} days in every band</h2>
  <p class="lede">Each delivered order is placed in a band by its farthest seller (zip-centroid straight-line km, not road distance). Freight uses each item’s own distance. These are differences inside this extract, not days or reais the business would get back.</p>
  <div class="ctrl" id="band-ctrl" data-js hidden>
    <span><span class="lbl">Highlight band</span><span class="seg" role="group" aria-label="Highlight a distance band"><button type="button" data-chip="all" aria-pressed="true">All</button>{chips}</span></span>
  </div>
  <p class="st-readout" id="band-readout" data-js hidden aria-live="polite"></p>
  <div class="grid3">
    <figure class="exhibit">
      <p class="ex-tag">Exhibit 2a</p>
      <p class="ex-title">Transit rises from {m['band_transit'][0]} to {m['band_transit'][4]} days; handling barely moves</p>
      {split}
      <p class="source">Median days per leg. Handling = approval to carrier handoff; transit = carrier to door. Medians of each leg do not add up to the purchase-to-door median, so the bars are not stacked. Negative durations are excluded from each leg.</p>
    </figure>
    <figure class="exhibit">
      <p class="ex-tag">Exhibit 2b</p>
      <p class="ex-title">On-time slips only from {m['band_ontime'][0]} to {m['band_ontime'][4]} while the median wait goes from {m['band_p2d'][0]} to {m['band_p2d'][4]} days</p>
      {ontime}
      <p class="source">On time = delivered on or before the estimated delivery date (calendar date). Scale starts at 85%; dots, not bars, for that reason. Right column: median purchase-to-door days.</p>
    </figure>
    <figure class="exhibit">
      <p class="ex-tag">Exhibit 2c</p>
      <p class="ex-title">Median freight per item rises from {m['band_freight'][0]} to {m['band_freight'][4]} with distance</p>
      {freight}
      <p class="source">Median freight per delivered item, BRL, banded by the item’s own distance. Item weight also differs by band; this describes the extract and is not a price curve.</p>
    </figure>
  </div>
  <div class="tablewrap">
  <table>
    <thead><tr><th><span class="full">Distance band</span><span class="short">Band, km</span></th><th><span class="full">Delivered orders</span><span class="short">Orders</span></th><th><span class="full">Median purchase-to-door (days)</span><span class="short">Door</span></th><th><span class="full">Median handling (days)</span><span class="short">Handl.</span></th><th><span class="full">Median transit (days)</span><span class="short">Transit</span></th><th>On time</th><th><span class="full">Median freight per item</span><span class="short">Freight/ item</span></th></tr></thead>
    <tbody>
{band_rows}
    </tbody>
  </table>
  </div>
  <p class="source">Days are medians. Bands are frozen and right-open (50 km falls in 50–200). 95,992 delivered orders and 109,651 items have a distance; the other 478 orders and 538 items stay in the totals above and out of this table. {source}</p>
</section>

<section>
  <p class="sec-label">3 · Coverage</p>
  <h2>Sellers cluster in São Paulo, with {m['sp_sellers']} of sellers against {m['sp_people']} of customers, and {m['cross_pct']} of delivered items cross a state line</h2>
  <p class="lede">Customer and seller shares by state show where coverage is thin. Four states have customers and no sellers at all.</p>
  <div class="cov">
    <figure class="exhibit">
      <p class="ex-tag">Exhibit 3</p>
      <p class="ex-title">Share of customers vs share of sellers, by state (27 states)</p>
      <div class="ctrl" id="cov-ctrl" data-js hidden>
        <span><span class="lbl">Sort</span><span class="seg" role="group" aria-label="Sort states"><button type="button" data-sort="people" aria-pressed="true">Customer share</button><button type="button" data-sort="sellers" aria-pressed="false">Seller share</button><button type="button" data-sort="gap" aria-pressed="false">Gap</button></span></span>
        <label><span class="lbl">State</span><select id="st-pick"><option value="">None</option>{state_options}</select></label>
      </div>
      <p class="st-readout" id="st-readout" data-js hidden aria-live="polite"></p>
      {cover}
      <p class="source">Customer share = distinct customer people in the state ÷ 96,096; seller share = sellers in the state ÷ 3,095. Gap sort = customer share minus seller share, most customer-heavy first. {source}</p>
    </figure>
    <div class="callouts">
      <div class="co"><p class="big acc">{share('SP', 'seller_share')} <span style="color:var(--text2);font-weight:500;font-size:17px">of sellers</span></p><p><b>São Paulo</b> holds {share('SP', 'seller_share')} of sellers but {share('SP', 'people_share')} of customer people.</p></div>
      <div class="co"><p class="big">{share('RJ', 'people_share')} <span style="color:var(--text2);font-weight:500;font-size:17px">vs {share('RJ', 'seller_share')}</span></p><p><b>Rio de Janeiro</b> is {share('RJ', 'people_share')} of customers and only {share('RJ', 'seller_share')} of sellers.</p></div>
      <div class="co"><p class="big">{share('PR', 'seller_share')} <span style="color:var(--text2);font-weight:500;font-size:17px">vs {share('PR', 'people_share')}</span></p><p><b>Paraná</b> runs the other way: {share('PR', 'seller_share')} of sellers, {share('PR', 'people_share')} of customers.</p></div>
      <div class="co"><p class="big acc">4 states</p><p>{no_seller_names} have customers and no sellers.</p></div>
      <div class="co"><p class="big">{m['cross_pct']}</p><p>of delivered items cross a state line ({m['cross_n']} / {m['delivered_items']}).</p></div>
    </div>
  </div>
</section>

<div class="watch">
  <p class="sec-label">For the weekly review</p>
  <h2>What leadership should watch</h2>
  <p class="lede">Three separate conversations. None of them is a savings estimate.</p>
  <ol>
    <li><h3>Coverage is uneven, and {m['cross_pct']} of items cross a state</h3><p>São Paulo has {m['sp_sellers']} of sellers and {m['sp_people']} of customers; four states have customers and no sellers. Track where coverage is thin. This is a coverage view, not a case for a new building.</p></li>
    <li><h3>The extra days are in transit, not handling</h3><p>Median transit runs from {m['band_transit'][0]} days under 50 km to {m['band_transit'][4]} days at 1,000+ km, while seller handling stays at {hand_lo}–{hand_hi} days. When a destination is slow, take it to the transit conversation, not a seller-handling program.</p></li>
    <li><h3>The promise stretches, so on-time can look fine while the wait is long</h3><p>On-time is {m['on_time_pct']} overall and {m['band_ontime'][4]} in the 1,000+ km band, where the median wait is {m['band_p2d'][4]} days. Report median days next to the on-time rate, never the rate alone.</p></li>
  </ol>
  <p class="fine">All figures describe this historical extract. No forecast, savings figure or causal effect is implied, and nothing is converted from BRL.</p>
</div>

<footer>
  <div class="fgrid">
    <div>
      <h4>Definitions</h4>
      <dl>
        <dt>Delivered order</dt><dd>Order with status delivered and a door (customer delivery) timestamp after purchase: {m['delivered_orders']} orders, {m['delivered_items']} items.</dd>
        <dt>Purchase-to-door</dt><dd>Purchase timestamp to door timestamp, in days. Headline is the median.</dd>
        <dt>Handling</dt><dd>Payment approval to carrier handoff. Negative durations excluded from the median.</dd>
        <dt>Transit</dt><dd>Carrier handoff to door. Negative durations (23 orders) excluded from the median.</dd>
        <dt>On time</dt><dd>Delivered on or before the estimated delivery date, compared by calendar date ({m['on_time_n']} / {m['delivered_orders']}).</dd>
        <dt>Cross-state item</dt><dd>Delivered item whose seller state differs from the customer state.</dd>
        <dt>Distance</dt><dd>Straight-line km between zip-prefix centroids of seller and customer. Not road distance.</dd>
        <dt>Distance band</dt><dd>0–50, 50–200, 200–500, 500–1,000, 1,000+ km, right-open, frozen. Orders use the farthest seller; freight uses the item’s own distance.</dd>
        <dt>Freight</dt><dd>Freight value on delivered items, BRL. Total {m['freight_total']}; median per item {m['median_freight']}.</dd>
        <dt>Week</dt><dd>Purchase week starting Monday. Weeks with no purchase are gaps, not zeros.</dd>
      </dl>
    </div>
    <div>
      <h4>Data source</h4>
      <p style="margin:0 0 16px">Olist Brazilian E-Commerce Public Dataset (Olist; also published on Kaggle as olistbr/brazilian-ecommerce). Used for non-commercial purposes with attribution. Historical extract: delivered purchases {first} to {last}; all purchases in the file run 4 Sep 2016 to 17 Oct 2018.</p>
      <h4>Method notes</h4>
      <ul>
        <li>Medians use the two-central-value rule and are computed on orders or items, never averaged across weeks.</li>
        <li>Customer shares use the distinct-people denominator (96,096); state rows sum to 96,136 because 39 people appear in two states.</li>
        <li>Week, band and state are different grains and are shown in separate exhibits; they are not joined.</li>
        <li>Review scores are out of scope for this page.</li>
        <li>Filters, ranges, sorting and highlights only change the view. They do not change any definition, population or full-period figure; a selected range shows sums and ratios of weekly counts, never a median of weekly medians.</li>
      </ul>
      <h4 style="margin-top:16px">Read more</h4>
      <ul>
        <li><a href="{PROJECT_URL}">Project folder and code on GitHub</a></li>
        <li><a href="{BLOB_URL}reports/executive-summary.md">Executive summary</a> · <a href="{BLOB_URL}reports/business-report.md">Business report</a></li>
        <li><a href="{BLOB_URL}reports/02-analyze.md">Analyze</a> · <a href="{BLOB_URL}reports/03-construct.md">Construct</a> · <a href="{BLOB_URL}reports/04-execute.md">Execute</a></li>
      </ul>
    </div>
  </div>
  <div class="foot-bottom"><span>Built by Alves · MS Business Analytics · supply-chain analytics portfolio</span><span>Generated by src/build_dashboard.py from data/processed extracts</span></div>
</footer>
</div>
<div id="tip" role="tooltip" hidden></div>
<script type="application/json" id="dash-data">{json_for_script(data)}</script>
<script>
{js}
</script>
</body>
</html>
"""


def build():
    contrast_checks()
    weekly, bands, band_summary, states, summary = load()
    m = compute(weekly, bands, band_summary, states, summary)
    page = page_html(weekly, bands, band_summary, states, summary, m)

    # Last guard: every locked display string must actually be on the page.
    must_show = [v for k, v in EXPECTED.items() if isinstance(v, str)]
    for v in EXPECTED.values():
        if isinstance(v, list):
            must_show += v
    must_show += list(EXPECTED["band_handling_range"])
    # Scan the page without its script blocks, so the embedded JSON cannot
    # satisfy a check that the visible page itself fails.
    visible = re.sub(r"<script\b.*?</script>", "", page, flags=re.S)
    missing = [s for s in must_show if esc(s) not in visible]
    if missing:
        fail(f"locked figures missing from page: {missing}")
    print(f"CHECK locked figures on page: PASS ({len(must_show)} strings)")

    DASH.mkdir(parents=True, exist_ok=True)
    out = DASH / "logistics_weekly.html"
    out.write_text(page, encoding="utf-8")
    print(f"WROTE {out} bytes={out.stat().st_size}")
    # The GitHub Pages copy is the same bytes, so the live page never drifts
    # from the file in the project folder.
    if DOCS.parent.exists():
        DOCS.mkdir(parents=True, exist_ok=True)
        pub = DOCS / "index.html"
        pub.write_text(page, encoding="utf-8")
        print(f"WROTE {pub} bytes={pub.stat().st_size}")
    return out


if __name__ == "__main__":
    build()
    sys.exit(0)
