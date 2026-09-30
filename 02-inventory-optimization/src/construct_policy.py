#!/usr/bin/env python3
"""Construct stage: reorder point and safety stock for CA_3 FOODS class A.

The class cut, the error definition, and the lead-time constant come from
analyze_inventory.py. This script does not refit the forecast and it does
not open sell_price. There is no unit cost, no holding-cost rate, and no
order cost. Nothing here is a dollar.

Run from anywhere:
    python 02-inventory-optimization/src/construct_policy.py

Input (already in the repo, not a raw CSV):
    01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv
    02-inventory-optimization/data/processed/abc_classes.csv is not read.
    The class is recomputed with analyze_inventory.assign_abc so the cut
    cannot drift from a hand-edited file.

Outputs under 02-inventory-optimization/:
    src/construct_policy.py
    data/processed/policy.csv
    data/processed/policy_summary.csv
    reports/03-construct.md is written separately; this script does not
    overwrite the interview note.
    reports/03-construct-solver.xlsx
    images/class_a_safety_stock.png
"""

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save files; do not open a window
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

import analyze_inventory as inventory_analyze

# Same folders and the same lead-time constant as the analyze stage.
PROJECT = inventory_analyze.PROJECT
PROC = inventory_analyze.PROC
IMG = inventory_analyze.IMG
FORECAST = inventory_analyze.FORECAST
LEAD_TIME_DAYS = inventory_analyze.LEAD_TIME_DAYS
HOLDOUT_DAYS = inventory_analyze.HOLDOUT_DAYS

# Plan decision: the cap is a unit shortfall under 5%, strict.
# fill_rate in the outputs is units short / units demanded, not the
# fraction of units that were filled. A result of exactly 0.05 fails.
FILL_CAP = 0.05

# Dust from subtracting whole units from a fractional on-hand. A gap this
# small is not a stockout. It is not a service-level tolerance.
SHORT_EPS = 1e-8

# Ties on average on-hand closer than this are treated as the same
# inventory. The smaller safety stock wins the tie so the buffer is not padded.
ON_HAND_TIE = 1e-8

EXAMPLE_ITEM = "FOODS_3_090"

# Fills used in the workbook so the decision, the objective, and the cap
# are visible without reading the note.
FILL_DECISION = PatternFill("solid", fgColor="FFF2CC")
FILL_OBJECTIVE = PatternFill("solid", fgColor="E2EFDA")
FILL_CONSTRAINT = PatternFill("solid", fgColor="FCE4D6")
FILL_HEADER = PatternFill("solid", fgColor="0B3A6A")
FONT_HEADER = Font(color="FFFFFF", bold=True)
FONT_LABEL = Font(bold=True)
THIN = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)
WRAP = Alignment(wrap_text=True, vertical="top")


def lots_to_clear(inventory_position: float, reorder_point: float, order_qty: int) -> int:
    """Smallest number of lots that puts the position strictly above the reorder point.

    Called only when the position is already at or under the reorder point.
    One lot when the position equals the reorder point: floor(0 / Q) + 1 = 1.
    Two lots when the position is a full order quantity under the reorder
    point, because one lot would land exactly on the reorder point and the
    rule orders when the position is <= the reorder point.
    """
    # gap is how far the position sits under the reorder point, in units.
    gap = reorder_point - inventory_position
    # floor(gap / Q) + 1 is the smallest integer lots with lots * Q > gap.
    lots = int(math.floor(gap / order_qty)) + 1
    if lots < 1:
        # A tiny negative gap from binary float still means "at the trigger".
        lots = 1
    return lots


def simulate(demand: np.ndarray, reorder_point: float, order_qty: int, trace: bool = False) -> dict:
    """One item, 28 days, continuous review, lost sales, fixed lead time.

    demand is the holdout actual, in whole units, oldest day first.
    The reorder point and the order quantity are already decided.
    This function does not look at the forecast. Expected demand was used
    to set the reorder point before the call. Scoring uses actual only.
    """
    n_days = int(len(demand))
    if n_days != HOLDOUT_DAYS:
        raise SystemExit(f"simulation horizon is {n_days}, not {HOLDOUT_DAYS}")
    if order_qty < 1:
        raise SystemExit("order quantity must be at least 1 unit")

    # Opening balance. On-hand equals the reorder point. Nothing is on order.
    # There is no historical on-hand in the files. This is an assumption.
    # The 28-day window is short, so the opening balance is part of the result.
    on_hand = float(reorder_point)
    on_order = 0.0
    # arrivals[t] is the units that become available at the start of day t.
    arrivals = np.zeros(n_days + LEAD_TIME_DAYS, dtype=np.float64)

    units_short = 0.0
    units_demanded = 0.0
    days_stocked_out = 0
    end_on_hand_sum = 0.0
    multi_lot_days = 0
    order_days: list[int] = []
    stocked_out = np.zeros(n_days, dtype=bool)
    end_on_hand = np.zeros(n_days, dtype=np.float64) if trace else None
    short_by_day = np.zeros(n_days, dtype=np.float64) if trace else None
    lots_by_day = np.zeros(n_days, dtype=np.int64) if trace else None

    for t in range(n_days):
        # Step 1. Receipt. An order placed on day t - 7 arrives at the start
        # of today, before the review and before demand. Lead time is 7 days,
        # fixed. Moving units from on-order to on-hand does not change the
        # inventory position.
        receipt = float(arrivals[t])
        on_hand += receipt
        on_order -= receipt

        lots_today = 0

        # Step 2. Morning review, before demand. Continuous review orders as
        # soon as the position is at the reorder point. The opening morning
        # is included: we start exactly at the reorder point, so the first
        # order goes out before any holdout demand. A lot ordered today
        # arrives at the start of day t+7. It cannot serve today's demand.
        inventory_position = on_hand + on_order
        if inventory_position <= reorder_point:
            lots = lots_to_clear(inventory_position, reorder_point, order_qty)
            on_order += lots * order_qty
            arrivals[t + LEAD_TIME_DAYS] += lots * order_qty
            lots_today += lots

        # Step 3. Demand. actual units, not the forecast. Lost sales: on-hand
        # does not go negative, and unmet units are not carried as a backorder.
        # The position falls only by the units that were actually sold.
        day_demand = float(demand[t])
        units_demanded += day_demand
        if on_hand + SHORT_EPS >= day_demand:
            on_hand -= day_demand
            day_short = 0.0
        else:
            day_short = day_demand - on_hand
            on_hand = 0.0
            days_stocked_out += 1
            stocked_out[t] = True
        units_short += day_short

        # Step 4. Review again after demand. A spike can pull the position
        # back to the reorder point on the same day. Continuous review places
        # the extra lots now, not on the next morning. Those lots still
        # arrive on day t+7. They do not refill today's lost sales.
        inventory_position = on_hand + on_order
        if inventory_position <= reorder_point:
            lots = lots_to_clear(inventory_position, reorder_point, order_qty)
            on_order += lots * order_qty
            arrivals[t + LEAD_TIME_DAYS] += lots * order_qty
            lots_today += lots

        if lots_today > 0:
            order_days.append(t)
        if lots_today > 1:
            multi_lot_days += 1

        # End-of-day on-hand is after demand and after the review. The review
        # does not change on-hand. This is the balance that is averaged.
        end_on_hand_sum += on_hand
        if trace:
            end_on_hand[t] = on_hand
            short_by_day[t] = day_short
            lots_by_day[t] = lots_today

    # A replenishment cycle is one day on which any lots were ordered.
    # The cycle covers that day through the day before the next order
    # (or through the last holdout day). A stockout on the order day counts,
    # because the order placed that day arrives 7 days later.
    cycles = len(order_days)
    cycles_with_stockout = 0
    if cycles:
        bounds = order_days + [n_days]
        for i, start in enumerate(order_days):
            stop = bounds[i + 1]
            if bool(stocked_out[start:stop].any()):
                cycles_with_stockout += 1

    out = {
        "units_short": float(units_short),
        "units_demanded": float(units_demanded),
        "days_stocked_out": int(days_stocked_out),
        "cycles": int(cycles),
        "cycles_with_stockout": int(cycles_with_stockout),
        "avg_on_hand": float(end_on_hand_sum / n_days),
        "multi_lot_days": int(multi_lot_days),
        "order_days": order_days,
    }
    if trace:
        out["end_on_hand"] = end_on_hand
        out["short_by_day"] = short_by_day
        out["lots_by_day"] = lots_by_day
    return out


def assert_simulation_timing() -> None:
    """Lock the review timing on two paths that can be counted by hand.

    Constant demand of 1, reorder point 7, order quantity 7.
    The position starts at 7, so day 0 orders one lot, due on day 7.
    On-hand then falls 6,5,4,3,2,1,0. It hits the reorder point again at
    the end of day 6 (on-hand 0, the in-transit lot still 7). The next
    orders fall on days 13, 20, and 27. Five cycles in 28 days, no stockout.
    End-of-day on-hand averages 3.75. Textbook Q/2 is 3.5; the 3.75 is the
    short window, not a second definition of cycle stock.

    A one-day spike of 20 against a reorder point of 10 and an order
    quantity of 6 must place two lots on that same day. One lot in the
    morning, because the position starts at the reorder point, and a
    second lot after the shelf hits zero. Lost sales are 10. The unmet
    units do not deepen the position, so a third lot is not placed.
    """
    if lots_to_clear(7.0, 7.0, 7) != 1:
        raise SystemExit("a position at the reorder point must order one lot")
    if lots_to_clear(0.0, 7.0, 7) != 2:
        raise SystemExit("a full order quantity under the reorder point needs two lots")
    if lots_to_clear(0.1, 7.0, 7) != 1:
        raise SystemExit("a gap smaller than one lot needs one lot")

    steady = simulate(np.ones(HOLDOUT_DAYS, dtype=np.float64), 7.0, 7, trace=True)
    if steady["order_days"] != [0, 6, 13, 20, 27]:
        raise SystemExit(f"constant-demand order days changed: {steady['order_days']}")
    if steady["units_short"] != 0.0 or steady["days_stocked_out"] != 0:
        raise SystemExit("constant demand of 1 should not stock out at reorder point 7")
    if steady["cycles"] != 5 or steady["cycles_with_stockout"] != 0:
        raise SystemExit("constant-demand cycle count changed")
    if abs(steady["avg_on_hand"] - 3.75) > 1e-9:
        raise SystemExit(f"constant-demand average on-hand changed: {steady['avg_on_hand']}")

    spike = np.zeros(HOLDOUT_DAYS, dtype=np.float64)
    spike[0] = 20.0
    spiked = simulate(spike, 10.0, 6, trace=True)
    if int(spiked["lots_by_day"][0]) != 2:
        raise SystemExit(f"spike should place two lots on day 0, got {spiked['lots_by_day'][0]}")
    if abs(spiked["units_short"] - 10.0) > 1e-9:
        raise SystemExit(f"spike shortfall changed: {spiked['units_short']}")
    if spiked["cycles_with_stockout"] < 1:
        raise SystemExit("the spike cycle should count as a stockout cycle")


def ceil_order_qty(expected_lead_time_demand: float) -> int:
    """Smallest whole number of units that is at least the expected lead-time demand.

    At least 1. This is a rounding rule, not a cost. math.ceil on a positive
    number matches Excel ROUNDUP(x, 0). An exact integer stays that integer.
    """
    # ceil(10.0) is 10. ceil(10.1) is 11.
    qty = int(math.ceil(float(expected_lead_time_demand)))
    if qty < 1:
        qty = 1
    return qty


def normal_loss(z: float) -> float:
    """Standard normal loss n(z) = phi(z) - z * (1 - Phi(z)).

    This is the textbook expected shortage per lead time, in units of the
    lead-time standard deviation, for a normal demand and a backorder model.
    It is used only to build a candidate the simulation is then allowed to
    reject. It is not the policy.
    """
    # phi(z) is the standard normal density.
    phi = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    # 1 - Phi(z) is the upper tail.
    tail = 0.5 * math.erfc(z / math.sqrt(2.0))
    return phi - z * tail


def z_for_unit_short_fraction(target_loss: float) -> float:
    """Invert n(z) = target_loss. n(z) falls as z rises.

    A larger target loss is an easier fill-rate bar and a smaller z.
    The search is a bisection. It is not a table lookup pasted from a book.
    """
    if target_loss <= 0.0:
        return 8.0
    lo = -12.0
    hi = 8.0
    # If even z = -12 cannot produce this much loss, the candidate z is -12
    # and the candidate safety stock will floor at 0.
    if normal_loss(lo) < target_loss:
        return lo
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        # Loss at mid is still above the target, so the z that matches is higher.
        if normal_loss(mid) > target_loss:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def candidate_safety_stock(daily_error_std: float, order_qty: int) -> tuple[float, int]:
    """Normal-loss candidate. Not the decision.

    sigma over the lead time = (sample std of daily lgbm - actual) * sqrt(7).
    That is the independent-days scale. The target loss in lead-time-sigma
    units is 0.05 * Q / sigma_L, because the textbook shortfall per cycle is
    n(z) * sigma_L and that shortfall divided by Q is the unit-short fraction
    in a backorder model. Safety stock = z * sigma_L, ceiled, and floored at 0.
    A negative z means the formula thinks the order quantity alone covers a
    5% shortfall, so the candidate is 0. The forecast is not debiased first.
    """
    # Independent-days lead-time sigma. Not adopted as the policy by itself.
    sigma_lead = float(daily_error_std) * math.sqrt(LEAD_TIME_DAYS)
    if not np.isfinite(sigma_lead) or sigma_lead <= 0.0:
        return 0.0, 0
    # 0.05 * Q / sigma_L is the loss value that lines up with a 5% unit shortfall.
    target_loss = FILL_CAP * float(order_qty) / sigma_lead
    z = z_for_unit_short_fraction(target_loss)
    if z <= 0.0:
        return z, 0
    # Ceil so the candidate is an integer unit and not a fraction under the formula.
    units = int(math.ceil(z * sigma_lead - 1e-9))
    if units < 0:
        units = 0
    return z, units


def stockout_proof_upper_bound(total_demand: float, expected_lead_time_demand: float) -> int:
    """A safety stock that cannot stock out on this finite series.

    Starting on-hand is expected lead-time demand plus safety stock.
    If that opening on-hand is at least the sum of actual demand over all
    28 days, the shelf covers the horizon even if no receipt ever helps.
    One extra unit covers a binary-float shortfall in the subtraction.
    The search uses this only as a bound. It is not a recommended buffer.
    """
    gap = float(total_demand) - float(expected_lead_time_demand)
    # ceil(gap) reaches the total when gap is not an integer.
    bound = max(0, int(math.ceil(gap)))
    if expected_lead_time_demand + bound + 1e-6 < float(total_demand):
        bound += 1
    return bound


def choose_safety_stock(demand: np.ndarray, expected_lead_time_demand: float, order_qty: int) -> dict:
    """Enumerate safety stock = 0, 1, 2, ... and keep the feasible minimum inventory.

    Feasible means units short / units demanded < 0.05 on this item's actuals.
    The objective is average end-of-day on-hand from the simulation, not
    Q/2 + safety stock. Ties within ON_HAND_TIE break toward the smaller
    safety stock. The order quantity does not change inside the loop.
    """
    upper = stockout_proof_upper_bound(float(demand.sum()), expected_lead_time_demand)
    best = None
    min_feasible = None
    records = []
    for safety_stock in range(upper + 1):
        # Reorder point = expected lead-time demand + this integer safety stock.
        # Expected lead-time demand is not re-estimated inside the search.
        reorder_point = expected_lead_time_demand + float(safety_stock)
        result = simulate(demand, reorder_point, order_qty, trace=False)
        demanded = result["units_demanded"]
        # The cap is the shortfall share. Zero demand would be a shortfall of 0.
        if demanded <= 0.0:
            fill_rate = 0.0
        else:
            fill_rate = result["units_short"] / demanded
        row = {
            "safety_stock": safety_stock,
            "fill_rate": fill_rate,
            "units_short": result["units_short"],
            "avg_on_hand": result["avg_on_hand"],
            "reorder_point": reorder_point,
        }
        records.append(row)
        if fill_rate < FILL_CAP:
            if min_feasible is None:
                min_feasible = safety_stock
            take = False
            if best is None:
                take = True
            elif row["avg_on_hand"] < best["avg_on_hand"] - ON_HAND_TIE:
                take = True
            elif (
                abs(row["avg_on_hand"] - best["avg_on_hand"]) <= ON_HAND_TIE
                and safety_stock < best["safety_stock"]
            ):
                take = True
            if take:
                best = row
                best["result"] = result
    if best is None or min_feasible is None:
        raise SystemExit("no safety stock met the cap; the upper bound should have")
    # The bound itself must be feasible. If it is not, the opening-stock proof failed.
    if records[-1]["fill_rate"] >= FILL_CAP:
        raise SystemExit("stockout-proof upper bound still missed the cap")
    return {
        "chosen": best,
        "min_feasible": int(min_feasible),
        "upper": int(upper),
        "records": records,
    }


def dependence_diagnostics(daily: pd.DataFrame, per: pd.DataFrame, blocks: pd.DataFrame) -> dict:
    """Compare the independent-days scale with the four 7-day blocks.

    Per item, four block errors are not a sigma we will use. The ratio of
    that four-point sample std to (daily std * sqrt(7)) says whether the
    independent-days scale is even in the right neighborhood. Lag correlations
    of the daily error say the same thing at a one-day lag.
    """
    block_std = (
        blocks.groupby("item_id", sort=False)["seven_day_error"]
        .std(ddof=1)
        .rename("block_std")
    )
    merged = per[["item_id", "daily_error_std"]].merge(block_std, on="item_id", how="left")
    if merged["block_std"].isna().any():
        raise SystemExit("a class A item is missing a 7-day block std")
    sigma_indep = merged["daily_error_std"].to_numpy(dtype=np.float64) * math.sqrt(LEAD_TIME_DAYS)
    ratio = merged["block_std"].to_numpy(dtype=np.float64) / sigma_indep
    # Mean of variances, not the variance of the pooled errors. Large items
    # pull this ratio. It is reported so it is not quietly used as a factor.
    mean_block_var = float(np.mean(np.square(merged["block_std"].to_numpy(dtype=np.float64))))
    mean_indep_var = float(np.mean(np.square(sigma_indep)))

    lag_means = []
    lag_medians = []
    # Errors in calendar order within the item. The frame is already sorted.
    for lag in range(1, LEAD_TIME_DAYS + 1):
        rhos = []
        for _, grp in daily.groupby("item_id", sort=False):
            err = grp["error"].to_numpy(dtype=np.float64)
            if err.size <= lag:
                continue
            if float(np.std(err, ddof=1)) == 0.0:
                continue
            rhos.append(float(np.corrcoef(err[:-lag], err[lag:])[0, 1]))
        lag_means.append(float(np.mean(rhos)))
        lag_medians.append(float(np.median(rhos)))

    return {
        "n_items": int(len(merged)),
        "median_daily_error_std": float(merged["daily_error_std"].median()),
        "median_block_std": float(merged["block_std"].median()),
        "median_sigma_indep": float(np.median(sigma_indep)),
        "median_block_over_indep": float(np.median(ratio)),
        "mean_block_over_indep": float(np.mean(ratio)),
        "p25_block_over_indep": float(np.quantile(ratio, 0.25)),
        "p75_block_over_indep": float(np.quantile(ratio, 0.75)),
        "mean_block_var": mean_block_var,
        "mean_indep_var": mean_indep_var,
        "mean_var_ratio": mean_block_var / mean_indep_var,
        "lag_mean_corr": lag_means,
        "lag_median_corr": lag_medians,
    }


def plot_policy(policy: pd.DataFrame, path: Path) -> None:
    """Two panels: where the shortfall landed, and safety stock against volume."""
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.4))

    fill = policy["fill_rate"].to_numpy(dtype=np.float64)
    bins = np.linspace(0.0, FILL_CAP, 21)
    axes[0].hist(fill, bins=bins, color="#4C78A8", edgecolor="white", linewidth=0.3)
    axes[0].axvline(FILL_CAP, color="#B85C38", ls="--", lw=1.0, label="Cap 0.05")
    axes[0].set_xlim(0.0, FILL_CAP)
    axes[0].set_xlabel("Unit shortfall (units short / units demanded)")
    axes[0].set_ylabel("Class A items")
    axes[0].set_title("Shortfall at the chosen safety stock")
    axes[0].legend(frameon=False, loc="upper left")

    axes[1].scatter(
        policy["units_demanded"],
        policy["safety_stock"],
        s=12,
        c="#0B3A6A",
        alpha=0.75,
        linewidths=0,
    )
    highlight = policy.loc[policy["item_id"].isin([EXAMPLE_ITEM]) | (policy["safety_stock"] == policy["safety_stock"].max())]
    for _, row in highlight.iterrows():
        axes[1].scatter([row["units_demanded"]], [row["safety_stock"]], s=28, c="#B85C38", zorder=3)
        axes[1].annotate(
            str(row["item_id"]),
            (row["units_demanded"], row["safety_stock"]),
            textcoords="offset points",
            xytext=(6, 4),
            fontsize=7,
            color="#B85C38",
        )
    axes[1].set_xlabel("Holdout units demanded (actual)")
    axes[1].set_ylabel("Safety stock (units)")
    axes[1].set_title("Safety stock is not a volume ranking")
    fig.suptitle("CA_3 FOODS class A, holdout 2016-04-25 to 2016-05-22", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _note(cell, text: str) -> None:
    cell.comment = Comment(text, "Construct")
    cell.comment.width = 280
    cell.comment.height = 80


def write_workbook(
    policy: pd.DataFrame,
    example_days: pd.DataFrame,
    example_trace: dict,
    example_search: list[dict],
    example_chosen_ss: int,
    example_candidate_ss: int,
    example_candidate_z: float,
    example_candidate_fill: float,
    summary: pd.Series,
) -> None:
    """A workbook a person can open. The example sheet is a formula simulation.

    Excel Solver is not installed here and was not run. The safety stock on
    the example sheet is the Python enumeration. Changing that cell recalculates
    the 28-day simulation, the average on-hand, and the shortfall, because
    those are formulas. The class A sheet records every item's result. Its
    safety-stock column will not rerun 558 simulations if someone types over it.
    """
    wb = openpyxl.Workbook()
    wb.calculation.calcMode = "auto"

    example = wb.active
    example.title = "Example_FOODS_3_090"
    notes = wb.create_sheet("Notes")
    search = wb.create_sheet("Example_search")
    klass = wb.create_sheet("Class_A")

    _write_example(
        example,
        example_days,
        example_trace,
        example_chosen_ss,
        example_candidate_ss,
        example_candidate_z,
        example_candidate_fill,
    )
    _write_search(search, example_search, example_chosen_ss)
    _write_class(klass, policy)
    _write_notes(notes, summary, example_chosen_ss, example_candidate_ss, example_candidate_fill)

    # Names a Solver dialog can point at. They refer to the example sheet.
    wb.defined_names.add(DefinedName(name="SafetyStock", attr_text="Example_FOODS_3_090!$B$8"))
    wb.defined_names.add(DefinedName(name="AvgOnHand", attr_text="Example_FOODS_3_090!$B$11"))
    wb.defined_names.add(DefinedName(name="FillRate", attr_text="Example_FOODS_3_090!$B$14"))
    wb.defined_names.add(DefinedName(name="OrderQty", attr_text="Example_FOODS_3_090!$B$7"))
    wb.defined_names.add(DefinedName(name="ReorderPoint", attr_text="Example_FOODS_3_090!$B$9"))

    path = PROJECT / "reports" / "03-construct-solver.xlsx"
    wb.save(path)


def _write_example(ws, days, trace, chosen_ss, candidate_ss, candidate_z, candidate_fill) -> None:
    ws["A1"] = "FOODS_3_090 — continuous review, one item, formula simulation"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:H1")
    ws["A2"] = (
        "Decision variable is safety stock (B8), yellow. Objective is average end-of-day "
        "on-hand (B11), green. Constraint is the unit shortfall (B14) strictly under 0.05, orange. "
        "Order quantity is not a decision. Lead time is the 7-day assumption. "
        "Excel Solver was not run. B8 is the Python integer search."
    )
    ws["A2"].alignment = WRAP
    ws.merge_cells("A2:H2")
    ws.row_dimensions[2].height = 48

    labels = [
        (3, "item_id", EXAMPLE_ITEM, "Busiest class A item by actual holdout units. The example, not the whole policy."),
        (4, "lead_time_days", LEAD_TIME_DAYS, "Assumption. Fixed. No variability. Not a column in the data. Orders placed on day t arrive at the start of day t+7."),
        (5, "mean_daily_lgbm", "=AVERAGE(D21:D48)", "Mean of this item's 28 LightGBM forecasts. Not the mean of actual. The forecast is not debiased."),
        (6, "expected_lead_time_demand", "=B5*B4", "Mean daily lgbm times 7. The forecast changes by day, so this is the mean day times the lead time, not one particular week and not actual."),
        (7, "order_qty", "=MAX(1,ROUNDUP(B6,0))", "Smallest whole number of units at least the expected lead-time demand, and at least 1. Not an EOQ. Solver must not change this cell."),
        (8, "safety_stock", int(chosen_ss), "DECISION VARIABLE. Integer units. Python enumerated 0, 1, 2, ... The value is that search, not an Excel Solver answer."),
        (9, "reorder_point", "=B6+B8", "Expected lead-time demand plus safety stock. Not rounded to a whole unit."),
        (10, "starting_on_hand", "=B9", "Assumption. Opening on-hand equals the reorder point. On-order is zero until the day-0 morning review, which orders because the position is already at the reorder point."),
        (11, "objective_avg_on_hand", "=AVERAGE(R21:R48)", "OBJECTIVE. Minimize. Mean of end-of-day on-hand over the 28 holdout days, in units. Not dollars."),
        (12, "units_short", "=SUM(L21:L48)", "Units demanded that the shelf did not have. Lost sales. Not backordered."),
        (13, "units_demanded", "=SUM(C21:C48)", "Sum of actual. The simulation consumes actual. The reorder point does not."),
        (14, "fill_rate", "=IF(B13=0,0,B12/B13)", "CONSTRAINT. Units short / units demanded. Must be strictly under 0.05. This is the unfilled share, which is how the plan defined the cap."),
        (15, "cap", FILL_CAP, "Strict. An exact 0.05 fails. Excel Solver's dialog has <= rather than <. Use <= 0.049999, or reject a result of exactly 0.05."),
        (16, "meets_cap", "=B14<B15", "TRUE only when the shortfall is strictly under the cap."),
        (17, "cycle_stock_units", "=B7/2", "Textbook half of the order quantity. Not the objective. Not a simulated average."),
        (18, "textbook_units_held", "=B17+B8", "Cycle stock plus safety stock. Reported so it can be compared with B11. Not the objective, and not dollars."),
        (19, "formula_minus_python", "=MAX(V21:V48)+MAX(W21:W48)", "Audit. Max absolute gap between the formula on-hand and shortfall and the Python trace at this safety stock. Should be about 0. The Python columns do not drive the model."),
    ]
    for row, label, value, note in labels:
        ws.cell(row, 1, label).font = FONT_LABEL
        cell = ws.cell(row, 2, value)
        ws.cell(row, 3, note).alignment = WRAP
        if label == "safety_stock":
            cell.fill = FILL_DECISION
            cell.font = Font(bold=True)
            _note(cell, "Decision variable. Integer >= 0. Do not hand this to GRG Nonlinear.")
        elif label == "objective_avg_on_hand":
            cell.fill = FILL_OBJECTIVE
            cell.font = Font(bold=True)
            _note(cell, "Objective. Minimize average on-hand in units.")
        elif label == "fill_rate":
            cell.fill = FILL_CONSTRAINT
            cell.font = Font(bold=True)
            _note(cell, "Constraint. Units short / units demanded < 0.05.")
        elif label == "meets_cap":
            cell.fill = FILL_CONSTRAINT

    ws["E3"] = "normal_loss_candidate_safety_stock"
    ws["F3"] = int(candidate_ss)
    ws["G3"] = "Not the decision. z from the normal loss, times daily error std * sqrt(7), ceiled, floored at 0."
    ws["E4"] = "normal_loss_z"
    ws["F4"] = float(candidate_z)
    ws["G4"] = "Solved so n(z) = 0.05 * order_qty / sigma_L. Negative z becomes a candidate of 0."
    ws["E5"] = "candidate_fill_rate_at_its_own_ss"
    ws["F5"] = float(candidate_fill)
    ws["G5"] = "Python simulation of that candidate on this item's actuals. If this is 0.05 or higher, the candidate misses the cap."
    ws["E6"] = "candidate_misses_cap"
    ws["F6"] = bool(candidate_fill >= FILL_CAP)
    for col in (5, 6):
        ws.cell(3, col).font = FONT_LABEL if col == 5 else Font(italic=True)
    ws["E3"].font = FONT_LABEL
    ws["E4"].font = FONT_LABEL
    ws["E5"].font = FONT_LABEL
    ws["E6"].font = FONT_LABEL

    headers = [
        "day_index",
        "date",
        "actual",
        "lgbm",
        "receipt",
        "on_hand_after_receipt",
        "on_order_after_receipt",
        "ip_morning",
        "lots_morning",
        "on_order_after_morning",
        "sales",
        "units_short",
        "on_hand_after_demand",
        "ip_after_demand",
        "lots_after_demand",
        "lots_today",
        "order_units",
        "on_hand_end",
        "on_order_end",
        "python_on_hand_end",
        "python_units_short",
        "abs_on_hand_gap",
        "abs_short_gap",
    ]
    header_row = 20
    first = 21
    for c, name in enumerate(headers, start=1):
        cell = ws.cell(header_row, c, name)
        cell.fill = FILL_HEADER
        cell.font = FONT_HEADER
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[header_row].height = 32
    ws.auto_filter.ref = f"A20:W{first + HOLDOUT_DAYS - 1}"
    ws.freeze_panes = "A21"
    ws.auto_filter.ref = f"A{header_row}:W{first + HOLDOUT_DAYS - 1}"

    letter = {name: get_column_letter(i + 1) for i, name in enumerate(headers)}
    last = first + HOLDOUT_DAYS - 1
    qcol = letter["order_units"]

    for i in range(HOLDOUT_DAYS):
        r = first + i
        prev = r - 1
        ws.cell(r, 1, i)
        ws.cell(r, 2, pd.Timestamp(days["day"].iloc[i]).date())
        ws.cell(r, 2).number_format = "YYYY-MM-DD"
        ws.cell(r, 3, int(days["actual"].iloc[i]))
        ws.cell(r, 4, float(days["lgbm"].iloc[i]))
        # Receipt from the order placed 7 days ago. Day index is column A.
        ws.cell(r, 5, f'=IF(A{r}<$B$4,0,INDEX(${qcol}${first}:${qcol}${last},A{r}-$B$4+1))')
        if i == 0:
            # Opening on-hand is the reorder point. Opening on-order is zero.
            ws.cell(r, 6, f"=$B$10+E{r}")
            ws.cell(r, 7, f"=0-E{r}")
        else:
            ws.cell(r, 6, f"=R{prev}+E{r}")
            ws.cell(r, 7, f"=S{prev}-E{r}")
        # Morning position, then lots if it is at or under the reorder point.
        ws.cell(r, 8, f"=F{r}+G{r}")
        ws.cell(r, 9, f'=IF(H{r}<=$B$9,INT(($B$9-H{r})/$B$7)+1,0)')
        ws.cell(r, 10, f"=G{r}+I{r}*$B$7")
        # Demand. Sales cannot exceed on-hand. Shortfall is lost.
        ws.cell(r, 11, f"=MIN(F{r},C{r})")
        ws.cell(r, 12, f"=C{r}-K{r}")
        ws.cell(r, 13, f"=F{r}-K{r}")
        # Position after the sale, then a second review the same day.
        ws.cell(r, 14, f"=M{r}+J{r}")
        ws.cell(r, 15, f'=IF(N{r}<=$B$9,INT(($B$9-N{r})/$B$7)+1,0)')
        ws.cell(r, 16, f"=I{r}+O{r}")
        ws.cell(r, 17, f"=P{r}*$B$7")
        ws.cell(r, 18, f"=M{r}")
        ws.cell(r, 19, f"=J{r}+O{r}*$B$7")
        ws.cell(r, 20, float(trace["end_on_hand"][i]))
        ws.cell(r, 21, float(trace["short_by_day"][i]))
        ws.cell(r, 22, f"=ABS(R{r}-T{r})")
        ws.cell(r, 23, f"=ABS(L{r}-U{r})")

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 88
    for col in range(4, 24):
        ws.column_dimensions[get_column_letter(col)].width = 16
    ws.row_dimensions[3].height = 32
    for row in range(4, 20):
        ws.row_dimensions[row].height = 36

    ws["B5"].number_format = "0.000000"
    ws["B6"].number_format = "0.000000"
    ws["B9"].number_format = "0.000000"
    ws["B11"].number_format = "0.000000"
    ws["B12"].number_format = "0.000000"
    ws["B14"].number_format = "0.000000"
    ws["B17"].number_format = "0.00"
    ws["B18"].number_format = "0.00"
    ws["B19"].number_format = "0.00000000"
    ws["F4"].number_format = "0.000000"
    ws["F5"].number_format = "0.000000"


def _write_search(ws, records: list[dict], chosen_ss: int) -> None:
    ws["A1"] = "FOODS_3_090 safety-stock enumeration (Python)"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:H1")
    ws["A2"] = (
        "Every integer safety stock from 0 through the stockout-proof upper bound. "
        "meets_cap is fill_rate < 0.05. The chosen row is the feasible safety stock "
        "with the lowest average on-hand. A tie would keep the smaller safety stock. "
        "These are values from Python, not Excel Solver."
    )
    ws["A2"].alignment = WRAP
    ws.merge_cells("A2:H2")
    ws.row_dimensions[2].height = 48

    last = 7 + len(records)
    ws["A3"] = "min_feasible_ss"
    # MIN of a helper column, not MINIFS. LibreOffice in this environment has
    # no MINIFS. Excel and LibreOffice both have MIN and IF.
    ws["B3"] = f"=MIN(G8:G{last})"
    ws["C3"] = "Smallest safety stock whose shortfall is strictly under 0.05. Column G is that safety stock, or 1000000000 when the row misses the cap, so MIN skips the miss."
    ws["A4"] = "min_avg_on_hand_among_feasible"
    ws["B4"] = f"=MIN(H8:H{last})"
    ws["C4"] = "Objective among the rows that meet the cap. Column H is average on-hand on those rows only."
    ws["A5"] = "python_chosen_ss"
    ws["B5"] = int(chosen_ss)
    ws["C5"] = "The safety stock the script kept. It should equal B3 when the lowest on-hand is at the smallest feasible integer."
    ws["A6"] = "chosen_matches_min_feasible"
    ws["B6"] = "=B3=B5"
    for row in range(3, 7):
        ws.cell(row, 1).font = FONT_LABEL

    headers = [
        "safety_stock",
        "units_short",
        "fill_rate",
        "avg_on_hand",
        "meets_cap",
        "is_python_choice",
        "ss_if_feasible",
        "avg_on_hand_if_feasible",
    ]
    for c, name in enumerate(headers, start=1):
        cell = ws.cell(7, c, name)
        cell.fill = FILL_HEADER
        cell.font = FONT_HEADER
    for i, rec in enumerate(records):
        r = 8 + i
        ws.cell(r, 1, int(rec["safety_stock"]))
        ws.cell(r, 2, float(rec["units_short"]))
        ws.cell(r, 3, float(rec["fill_rate"]))
        ws.cell(r, 4, float(rec["avg_on_hand"]))
        ws.cell(r, 5, f"=C{r}<0.05")
        ws.cell(r, 6, f"=A{r}=$B$5")
        # 10^9 stands in for an infeasible row so MIN ignores it without MINIFS.
        ws.cell(r, 7, f"=IF(E{r},A{r},10^9)")
        ws.cell(r, 8, f"=IF(E{r},D{r},10^9)")
        if rec["safety_stock"] == chosen_ss:
            for c in range(1, 7):
                ws.cell(r, c).fill = FILL_DECISION
    ws.freeze_panes = "A8"
    ws.auto_filter.ref = f"A7:H{7+len(records)}"
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 78
    for col in ("D", "E", "F", "G", "H"):
        ws.column_dimensions[col].width = 22
    ws["B4"].number_format = "0.000000"


def _write_class(ws, policy: pd.DataFrame) -> None:
    ws["A1"] = "Class A results — CA_3 FOODS holdout"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:P1")
    ws["A2"] = (
        "One row per class A item. safety_stock is the decision from the Python search. "
        "reorder_point, fill_rate, cycle_stock_units, textbook_units_held, and meets_cap are formulas. "
        "units_short, the cycle counts, and avg_on_hand are the simulation at that safety stock. "
        "Editing safety_stock on this sheet does not rerun the simulation. The live model is Example_FOODS_3_090. "
        "The portfolio objective is the sum of avg_on_hand. The cap is each item's fill_rate < 0.05. No dollars."
    )
    ws["A2"].alignment = WRAP
    ws.merge_cells("A2:P2")
    ws.row_dimensions[2].height = 48

    # Dashboard. Row numbers of the table are fixed once the header row is chosen.
    header_row = 18
    first = 19
    last = first + len(policy) - 1
    dashboard = [
        (4, "n_items", f"=COUNTA(A{first}:A{last})", "Class A items in the table."),
        (5, "units_demanded", f"=SUM(H{first}:H{last})", "Sum of actual holdout units."),
        (6, "units_short", f"=SUM(G{first}:G{last})", "Sum of simulated units short."),
        (7, "fill_rate", "=IF(B5=0,0,B6/B5)", "Portfolio shortfall. Sum of units short / sum of units demanded. Not the average of the item rates."),
        (8, "OBJECTIVE_total_avg_on_hand", f"=SUM(M{first}:M{last})", "Sum across items of average end-of-day on-hand. This is the portfolio objective, in units."),
        (9, "total_safety_stock", f"=SUM(E{first}:E{last})", "Sum of the decision variable. Not the objective by itself, because on-hand also depends on the order quantity and the path."),
        (10, "items_missing_cap", f'=COUNTIF(P{first}:P{last},FALSE)', "Must be 0. A FALSE meets_cap is an item whose shortfall is not strictly under 0.05."),
        (11, "total_days_stocked_out", f"=SUM(J{first}:J{last})", "Item-days with any shortfall."),
        (12, "day_stockout_rate", f"=IF(B4=0,0,B11/(B4*{HOLDOUT_DAYS}))", "Share of item-days with a shortfall. Not the cap."),
        (13, "total_cycles", f"=SUM(K{first}:K{last})", "Order days across items."),
        (14, "total_cycles_with_stockout", f"=SUM(L{first}:L{last})", "Order days whose cycle contains a shortfall."),
        (15, "cycle_stockout_share", "=IF(B13=0,0,B14/B13)", "Cycles with a stockout / cycles. Not the cap. A 28-day window has few cycles per item."),
        (16, "cycle_service_level", "=1-B15", "Share of cycles with no stockout. Textbook cycle service. Not the cap."),
    ]
    for row, label, formula, note in dashboard:
        ws.cell(row, 1, label).font = FONT_LABEL
        cell = ws.cell(row, 2, formula)
        ws.cell(row, 3, note).alignment = WRAP
        if "OBJECTIVE" in label:
            cell.fill = FILL_OBJECTIVE
        if label in ("fill_rate", "items_missing_cap"):
            cell.fill = FILL_CONSTRAINT
    ws["B7"].number_format = "0.000000"
    ws["B8"].number_format = "0.000000"
    ws["B12"].number_format = "0.000000"
    ws["B15"].number_format = "0.000000"
    ws["B16"].number_format = "0.000000"

    headers = [
        "item_id",
        "mean_daily_lgbm",
        "expected_lead_time_demand",
        "order_qty",
        "safety_stock",
        "reorder_point",
        "units_short",
        "units_demanded",
        "fill_rate",
        "days_stocked_out",
        "cycles",
        "cycles_with_stockout",
        "avg_on_hand",
        "cycle_stock_units",
        "textbook_units_held",
        "meets_cap",
    ]
    for c, name in enumerate(headers, start=1):
        cell = ws.cell(header_row, c, name)
        cell.fill = FILL_HEADER
        cell.font = FONT_HEADER
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[header_row].height = 32
    _note(ws.cell(header_row, 5), "Decision variable, one per item. Integer units from the Python search.")

    ordered = policy.sort_values("item_id", kind="mergesort")
    for i, row in enumerate(ordered.itertuples(index=False)):
        r = first + i
        ws.cell(r, 1, row.item_id)
        ws.cell(r, 2, float(row.mean_daily_lgbm))
        ws.cell(r, 3, float(row.expected_lead_time_demand))
        ws.cell(r, 4, int(row.order_qty))
        cell_ss = ws.cell(r, 5, int(row.safety_stock))
        cell_ss.fill = FILL_DECISION
        # Reorder point is a formula of expected lead-time demand and safety stock.
        ws.cell(r, 6, f"=C{r}+E{r}")
        ws.cell(r, 7, float(row.units_short))
        ws.cell(r, 8, int(row.units_demanded))
        ws.cell(r, 9, f"=IF(H{r}=0,0,G{r}/H{r})")
        ws.cell(r, 10, int(row.days_stocked_out))
        ws.cell(r, 11, int(row.cycles))
        ws.cell(r, 12, int(row.cycles_with_stockout))
        ws.cell(r, 13, float(row.avg_on_hand))
        ws.cell(r, 14, f"=D{r}/2")
        ws.cell(r, 15, f"=N{r}+E{r}")
        ws.cell(r, 16, f"=I{r}<0.05")

    ws.freeze_panes = "A19"
    ws.auto_filter.ref = f"A{header_row}:P{last}"
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 55
    for col in range(4, 17):
        ws.column_dimensions[get_column_letter(col)].width = 18
    ws.auto_filter.ref = f"A{header_row}:P{last}"


def _write_notes(ws, summary: pd.Series, chosen_ss: int, candidate_ss: int, candidate_fill: float) -> None:
    paragraphs = [
        "Notes for the workbook. The interview write-up is reports/03-construct.md. This sheet is the Solver setup and the definitions the sheet uses.",
        "Excel Solver was not executed. No Solver binary is installed in the environment that built this file. The safety stock values were computed by enumerating integers in construct_policy.py. Writing those values into B8 and into the Class_A safety_stock column is the record of that search. It is not a claim that Excel's Solver dialog produced them.",
        "Example_FOODS_3_090 is the model. SafetyStock (B8) is the only decision. AvgOnHand (B11) is the objective, and it is a formula of the 28-day simulation below it. FillRate (B14) is units short divided by units demanded. The constraint is FillRate < 0.05. OrderQty (B7) is ROUNDUP of mean daily lgbm times 7, at least 1. A Solver run must not change OrderQty, the lead time, the lgbm column, or the actual column.",
        "How to set Excel Solver on the example sheet: Data > Solver. Set Objective: AvgOnHand, To: Min, By Changing: SafetyStock. Constraints: SafetyStock >= 0, SafetyStock integer, and FillRate under the cap. The Solver dialog offers <= and not a strict <. The cap in the plan is strict, so either constrain FillRate <= 0.049999 or throw away a solution that lands on exactly 0.05. Make Unconstrained Variables Non-Negative can stay on. Solving method: Evolutionary. GRG Nonlinear is the wrong method: the simulation is a step function of safety stock, and GRG assumes a smooth function it can differentiate. It can stop on a flat step between two integers. Simplex LP does not apply, because lost-sales inventory is not a linear program. Evolutionary is the method that matches an integer search on a non-smooth simulation. Example_search is that integer search already done, for this one item, from 0 through a stockout-proof upper bound.",
        f"On this build, the Python choice for FOODS_3_090 is safety stock {int(chosen_ss)}. The normal-loss candidate is {int(candidate_ss)}, and the simulation of that candidate has fill rate {candidate_fill}. If the candidate fill rate is 0.05 or higher, the formula missed the cap and the search raised safety stock. The candidate cell is labeled so it is not mistaken for B8.",
        "Class_A is the record for all 558 items. The portfolio objective cell sums average on-hand. The items_missing_cap cell counts rows whose meets_cap formula is FALSE. Those two cells are the class-level objective and the class-level check. They are formulas of the recorded simulation columns, not a second optimization.",
        "Definitions used in every sheet. Inventory position = on-hand + on-order. Lost sales, so unmet demand is not subtracted as a backorder. Review is continuous inside the day: morning, before demand, and again after demand if the position is back at the reorder point. Both orders arrive at the start of day t+7. Opening on-hand equals the reorder point and opening on-order is zero; the day-0 morning review therefore places the first order. Expected lead-time demand = mean of the item's 28 lgbm values times 7. Reorder point = that expectation plus safety stock. The simulation consumes actual. The expectation does not.",
        "Cycle stock on the sheet is order quantity / 2. It is the textbook half-batch. The objective is the simulated average on-hand, which is not that expression. Neither number is a dollar holding cost. sell_price is not in this workbook. There is no holding-cost rate and no order cost.",
        (
            "Class A totals written by the same run, so the sheet and the CSV start from the same search: "
            f"items {int(summary['n_items'])}, "
            f"units demanded {summary['units_demanded']}, "
            f"units short {summary['units_short']}, "
            f"fill rate {summary['fill_rate']}, "
            f"total average on-hand {summary['total_avg_on_hand']}, "
            f"total safety stock {summary['total_safety_stock']}, "
            f"items missing the cap {int(summary['n_items_missing_cap'])}."
        ),
    ]
    ws["A1"] = "Solver setup and definitions"
    ws["A1"].font = Font(bold=True, size=14)
    for i, text in enumerate(paragraphs):
        cell = ws.cell(i + 3, 1, text)
        cell.alignment = WRAP
        ws.row_dimensions[i + 3].height = 72
    ws.column_dimensions["A"].width = 120


def main() -> None:
    if LEAD_TIME_DAYS != 7 or HOLDOUT_DAYS != 28:
        raise SystemExit("lead time or holdout length no longer matches the plan")
    assert_simulation_timing()

    PROC.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    (PROJECT / "reports").mkdir(parents=True, exist_ok=True)

    # Same loader and the same signed error as the analyze stage.
    # error = lgbm - actual. Positive means the forecast was above the units sold.
    daily = inventory_analyze.add_errors(inventory_analyze.load_forecast(FORECAST))
    per = inventory_analyze.per_item_errors(daily)
    abc = inventory_analyze.assign_abc(per)
    _calendar, block_rows = inventory_analyze.seven_day_blocks(daily)

    class_a_ids = set(abc.loc[abc["abc_class"] == "A", "item_id"])
    if len(class_a_ids) != 558:
        raise SystemExit(f"class A is {len(class_a_ids)} items, not 558")
    class_a_units = int(abc.loc[abc["abc_class"] == "A", "holdout_units"].sum())
    if class_a_units != 88230:
        raise SystemExit(f"class A units are {class_a_units}, not 88230")

    daily_a = daily.loc[daily["item_id"].isin(class_a_ids)].sort_values(
        ["item_id", "day"], kind="mergesort"
    )
    per_a = per.loc[per["item_id"].isin(class_a_ids)].copy()
    blocks_a = block_rows.loc[block_rows["item_id"].isin(class_a_ids)].copy()

    # The analyze-stage class A bias, recomputed so this stage is using that definition.
    bias_units = float(daily_a["error"].sum())
    actual_units = float(daily_a["actual"].sum())
    bias_share = bias_units / actual_units
    if not np.isclose(bias_units, -5020.5579692516685):
        raise SystemExit(f"class A bias changed: {bias_units}")
    if not np.isclose(bias_share, -0.05690307116912239):
        raise SystemExit(f"class A bias share changed: {bias_share}")

    diagnostics = dependence_diagnostics(daily_a, per_a, blocks_a)
    std_by_item = per_a.set_index("item_id")["daily_error_std"]

    rows = []
    example_pack = None
    candidate_misses = 0
    candidate_ss_total = 0
    multi_lot_days_total = 0
    chosen_above_min = 0

    for item_id, grp in daily_a.groupby("item_id", sort=False):
        grp = grp.sort_values("day", kind="mergesort")
        demand = grp["actual"].to_numpy(dtype=np.int64)
        lgbm = grp["lgbm"].to_numpy(dtype=np.float64)
        # Mean daily forecast. The reorder point uses this, not actual.
        mean_daily_lgbm = float(lgbm.mean())
        # Expected lead-time demand = mean daily lgbm * 7. The forecast varies
        # by day, so a single week's sum would depend on which week. The mean
        # day times 7 does not. Actual is not in this line.
        expected_lead_time_demand = mean_daily_lgbm * float(LEAD_TIME_DAYS)
        order_qty = ceil_order_qty(expected_lead_time_demand)

        z_candidate, ss_candidate = candidate_safety_stock(float(std_by_item.loc[item_id]), order_qty)
        candidate_result = simulate(
            demand, expected_lead_time_demand + float(ss_candidate), order_qty, trace=False
        )
        candidate_fill = candidate_result["units_short"] / candidate_result["units_demanded"]
        if candidate_fill >= FILL_CAP:
            candidate_misses += 1
        candidate_ss_total += int(ss_candidate)

        search = choose_safety_stock(demand, expected_lead_time_demand, order_qty)
        chosen = search["chosen"]
        result = chosen["result"]
        if int(chosen["safety_stock"]) != int(search["min_feasible"]):
            chosen_above_min += 1

        # Reorder point of the kept policy. Same expression as inside the search.
        reorder_point = expected_lead_time_demand + float(chosen["safety_stock"])
        if abs(reorder_point - chosen["reorder_point"]) > 1e-9:
            raise SystemExit("reorder point drifted between the search and the row")
        if result["order_days"][0] != 0:
            raise SystemExit(f"{item_id} did not order on the opening morning")

        fill_rate = chosen["fill_rate"]
        if fill_rate >= FILL_CAP:
            raise SystemExit(f"{item_id} kept a safety stock that misses the cap")

        multi_lot_days_total += int(result["multi_lot_days"])
        row = {
            "item_id": item_id,
            "mean_daily_lgbm": mean_daily_lgbm,
            "expected_lead_time_demand": expected_lead_time_demand,
            "order_qty": int(order_qty),
            "safety_stock": int(chosen["safety_stock"]),
            "reorder_point": float(reorder_point),
            "fill_rate": float(fill_rate),
            "units_short": float(result["units_short"]),
            "units_demanded": int(result["units_demanded"]),
            "days_stocked_out": int(result["days_stocked_out"]),
            "cycles": int(result["cycles"]),
            "cycles_with_stockout": int(result["cycles_with_stockout"]),
            "avg_on_hand": float(result["avg_on_hand"]),
            # Textbook cycle stock. Half the order quantity. Not average on-hand.
            "cycle_stock_units": float(order_qty) / 2.0,
        }
        rows.append(row)
        if item_id == EXAMPLE_ITEM:
            trace = simulate(demand, reorder_point, order_qty, trace=True)
            example_pack = {
                "days": grp,
                "trace": trace,
                "search": search["records"],
                "chosen_ss": int(chosen["safety_stock"]),
                "candidate_ss": int(ss_candidate),
                "candidate_z": float(z_candidate),
                "candidate_fill": float(candidate_fill),
                "upper": int(search["upper"]),
            }

    if example_pack is None:
        raise SystemExit(f"{EXAMPLE_ITEM} was not in class A")
    if len(rows) != 558:
        raise SystemExit("policy row count is not 558")

    policy = pd.DataFrame(rows).sort_values("item_id", kind="mergesort").reset_index(drop=True)
    # Identities the CSV must satisfy before it is written.
    if not np.allclose(
        policy["reorder_point"],
        policy["expected_lead_time_demand"] + policy["safety_stock"],
    ):
        raise SystemExit("reorder point is not expected lead-time demand plus safety stock")
    if not np.allclose(
        policy["expected_lead_time_demand"],
        policy["mean_daily_lgbm"] * LEAD_TIME_DAYS,
    ):
        raise SystemExit("expected lead-time demand is not mean daily lgbm times 7")
    if not np.allclose(policy["fill_rate"], policy["units_short"] / policy["units_demanded"]):
        raise SystemExit("fill rate is not units short / units demanded")
    if int(policy["units_demanded"].sum()) != 88230:
        raise SystemExit("policy units demanded are not the class A total")
    if int((policy["fill_rate"] >= FILL_CAP).sum()) != 0:
        raise SystemExit("an item misses the cap")

    column_order = [
        "item_id",
        "mean_daily_lgbm",
        "expected_lead_time_demand",
        "order_qty",
        "safety_stock",
        "reorder_point",
        "fill_rate",
        "units_short",
        "units_demanded",
        "days_stocked_out",
        "cycles",
        "cycles_with_stockout",
        "avg_on_hand",
        "cycle_stock_units",
    ]
    policy = policy[column_order]
    policy_path = PROC / "policy.csv"
    policy.to_csv(policy_path, index=False)

    units_demanded = int(policy["units_demanded"].sum())
    units_short = float(policy["units_short"].sum())
    total_cycles = int(policy["cycles"].sum())
    total_cycles_with_stockout = int(policy["cycles_with_stockout"].sum())
    total_days = int(policy["days_stocked_out"].sum())
    n_items = int(len(policy))
    cycle_stockout_share = total_cycles_with_stockout / total_cycles
    summary = {
        "abc_class": "A",
        "n_items": n_items,
        "units_demanded": units_demanded,
        "units_short": units_short,
        "fill_rate": units_short / units_demanded,
        "total_avg_on_hand": float(policy["avg_on_hand"].sum()),
        "total_safety_stock": int(policy["safety_stock"].sum()),
        "total_cycle_stock_units": float(policy["cycle_stock_units"].sum()),
        "total_textbook_units_held": float(
            (policy["cycle_stock_units"] + policy["safety_stock"]).sum()
        ),
        "n_items_missing_cap": int((policy["fill_rate"] >= FILL_CAP).sum()),
        "n_items_safety_stock_zero": int((policy["safety_stock"] == 0).sum()),
        "n_items_chosen_above_min_ss": int(chosen_above_min),
        "total_days_stocked_out": total_days,
        "day_stockout_rate": total_days / (n_items * HOLDOUT_DAYS),
        "total_cycles": total_cycles,
        "total_cycles_with_stockout": total_cycles_with_stockout,
        "cycle_stockout_share": cycle_stockout_share,
        "cycle_service_level": 1.0 - cycle_stockout_share,
        "n_normal_candidate_missing_cap": int(candidate_misses),
        "total_normal_candidate_safety_stock": int(candidate_ss_total),
    }
    summary_df = pd.DataFrame([summary])
    summary_path = PROC / "policy_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    plot_policy(policy, IMG / "class_a_safety_stock.png")
    write_workbook(
        policy,
        example_pack["days"],
        example_pack["trace"],
        example_pack["search"],
        example_pack["chosen_ss"],
        example_pack["candidate_ss"],
        example_pack["candidate_z"],
        example_pack["candidate_fill"],
        pd.Series(summary),
    )

    # Quantiles the report quotes. Computed from the frame that was written.
    fill = policy["fill_rate"]
    cycles = policy["cycles"]
    ss = policy["safety_stock"]
    max_ss_row = policy.loc[policy["safety_stock"].idxmax()]
    max_fill_row = policy.loc[policy["fill_rate"].idxmax()]
    example_row = policy.loc[policy["item_id"] == EXAMPLE_ITEM].iloc[0]
    positive_ss = policy.loc[policy["safety_stock"] > 0, "fill_rate"]
    stats = {
        "bias_units": bias_units,
        "bias_share": bias_share,
        "diagnostics": diagnostics,
        "multi_lot_days_total": multi_lot_days_total,
        "example_upper": example_pack["upper"],
        "example_candidate_z": example_pack["candidate_z"],
        "example_candidate_ss": example_pack["candidate_ss"],
        "example_candidate_fill": example_pack["candidate_fill"],
        "example": {k: example_row[k] for k in column_order},
        "max_ss_item": max_ss_row["item_id"],
        "max_ss": int(max_ss_row["safety_stock"]),
        "max_ss_fill": float(max_ss_row["fill_rate"]),
        "max_ss_units": int(max_ss_row["units_demanded"]),
        "max_ss_avg": float(max_ss_row["avg_on_hand"]),
        "max_fill_item": max_fill_row["item_id"],
        "max_fill": float(max_fill_row["fill_rate"]),
        "fill_min": float(fill.min()),
        "fill_p25": float(fill.quantile(0.25)),
        "fill_p50": float(fill.quantile(0.50)),
        "fill_p75": float(fill.quantile(0.75)),
        "fill_mean_unweighted": float(fill.mean()),
        "n_fill_zero": int((fill == 0.0).sum()),
        "n_positive_ss_fill_zero": int(((policy["safety_stock"] > 0) & (fill == 0.0)).sum()),
        "positive_ss_fill_median": float(positive_ss.median()) if len(positive_ss) else None,
        "ss_min": int(ss.min()),
        "ss_p25": float(ss.quantile(0.25)),
        "ss_p50": float(ss.quantile(0.50)),
        "ss_p75": float(ss.quantile(0.75)),
        "ss_max": int(ss.max()),
        "cycles_min": int(cycles.min()),
        "cycles_p50": float(cycles.median()),
        "cycles_mean": float(cycles.mean()),
        "cycles_max": int(cycles.max()),
        "n_cycles_le_4": int((cycles <= 4).sum()),
        "n_cycles_eq_1": int((cycles == 1).sum()),
        "summary": summary,
    }
    # Numpy scalars are not JSON. The default handles them via a string fallback.
    def convert(obj):
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        raise TypeError(type(obj))

    print(json.dumps(stats, default=convert))
    print("wrote", policy_path)
    print("wrote", summary_path)


if __name__ == "__main__":
    main()
