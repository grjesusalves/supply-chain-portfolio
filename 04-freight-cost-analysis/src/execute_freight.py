#!/usr/bin/env python3
"""Execute stage: a labeled freight what-if, not a coefficient and not a saving.

The dollar figure is a scenario. It is not the regression, and it is not
money that was saved. Population: weighed Air shipments whose Yes-line
weight is at least the median weight of the weighed set. Counterfactual
rate: the observed median freight per kilogram of weighed Truck shipments
on that same weight slice. A note contributes weight * (air rate - truck
median) only when the air rate is above that median.

The plan asked for heavy air above a stated weight and did not name the
kilograms or the share. The weighed-set median is the stated weight,
because it is the typical weighed shipment in this file. Air's own median
weight is lighter, so using it would call a typical air note heavy. The
share the plan did not name is reported two ways, both labeled as upper
bounds: the full gap, and 25 percent of that gap.

Run from the repo root:
    python 04-freight-cost-analysis/src/execute_freight.py

Run from the project folder:
    python src/execute_freight.py

The rollup and the OLS fits are the Construct functions. This file does
not parse freight a second way and does not re-download the CSV.

Outputs:
    data/processed/execute_scenario_air_notes.csv
    data/processed/execute_scenario_truck_notes.csv
    data/processed/execute_scenario_result.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_freight as af  # noqa: E402
import construct_freight as cf  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]
PROC = PROJECT / "data" / "processed"
DASH = PROJECT / "dashboards"

# The plan said "a stated share" and did not name one. 25 percent of the
# full gap is the sensitivity this stage reports. It is not a selected
# list of lanes, and it is not a claim that a quarter of the notes moved.
SHARE = 0.25

# Scorecard rank threshold from Analyze. A country or vendor is not called
# expensive off a smaller controlled count. Recomputed here so the writeup
# does not borrow the earlier page's sentence without this run.
RANK_MIN = 20
ORGENICS_NAME = "Orgenics, Ltd"
RDC_NAME = "SCMS from RDC"


def save_csv(df: pd.DataFrame, name: str) -> Path:
    """Scenario tables only. Analyze and Construct files stay where they are."""
    if not name.startswith("execute_") or not name.endswith(".csv"):
        raise SystemExit(f"refusing to write {name}")
    PROC.mkdir(parents=True, exist_ok=True)
    path = PROC / name
    df.to_csv(path, index=False)
    return path


def metric_frame(rows: list[tuple[str, object]]) -> pd.DataFrame:
    """One metric per row, value as text, so a float is not quietly rounded."""
    return pd.DataFrame(
        [{"metric": name, "value": "" if value is None else str(value)} for name, value in rows]
    )


def coef_of(robust, needle: str) -> tuple[str, float, float, float, float]:
    """One HC1 coefficient whose patsy name contains needle. A missing name stops."""
    hits = [name for name in robust.params.index if needle in name]
    if len(hits) != 1:
        raise SystemExit(f"expected one coefficient containing {needle!r}, found {hits}")
    name = hits[0]
    coef = float(robust.params[name])
    lo, hi = (float(x) for x in robust.conf_int().loc[name])
    return name, coef, lo, hi, float(np.expm1(coef))


def verify_extract(shipments: pd.DataFrame, model: pd.DataFrame) -> dict:
    """The Tableau extract is the weighed set. Stale means a different population.

    This does not add a savings column. A summed counterfactual on the
    extract would look like an invoice. The what-if stays in the scenario
    CSVs. If the file is missing or the rows do not match, rewrite it with
    the Construct writer, which is the same Yes-line rule.
    """
    path = DASH / "shipment_weighed.csv"
    weighed = shipments.loc[shipments["in_weighed"] == 1].copy()
    if len(weighed) != cf.EXPECTED_WEIGHED:
        raise SystemExit("weighed set moved before the extract check")
    rewrite = not path.exists()
    reason = "missing"
    if path.exists():
        extract = pd.read_csv(path)
        reason = "matches"
        if len(extract) != len(weighed):
            rewrite = True
            reason = f"row_count {len(extract)} != {len(weighed)}"
        elif set(extract["asn_dn"]) != set(weighed["asn_dn"]):
            rewrite = True
            reason = "asn set differs"
        else:
            merged = extract.merge(
                weighed[
                    [
                        "asn_dn",
                        "shipment_mode",
                        "weight_kg",
                        "freight_usd",
                        "freight_per_kg",
                    ]
                ],
                on="asn_dn",
                how="inner",
                suffixes=("_file", "_rollup"),
            )
            if len(merged) != len(weighed):
                rewrite = True
                reason = "join dropped a row"
            else:
                for column in ("weight_kg", "freight_usd", "freight_per_kg"):
                    delta = (merged[f"{column}_file"] - merged[f"{column}_rollup"]).abs().max()
                    if float(delta) > 1e-6:
                        rewrite = True
                        reason = f"{column} drifted by {delta}"
                        break
                mode_bad = int((merged["shipment_mode_file"] != merged["shipment_mode_rollup"]).sum())
                if mode_bad:
                    rewrite = True
                    reason = f"{mode_bad} modes differ"
    if rewrite:
        # Same columns Construct wrote. Not a new savings field.
        cf.write_dashboard(shipments, model["asn_dn"])
        extract = pd.read_csv(path)
    else:
        extract = pd.read_csv(path)
    if len(extract) != cf.EXPECTED_WEIGHED:
        raise SystemExit(f"extract row count is {len(extract)}")
    return {
        "path": str(path.relative_to(PROJECT)),
        "rows": int(len(extract)),
        "rewritten": int(rewrite),
        "check": reason if not rewrite else f"rewritten because {reason}",
    }


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    shipments, dates = cf.build_shipments()
    model, _grouping, meta = cf.estimation_frame(shipments)

    weighed = shipments.loc[shipments["in_weighed"] == 1].copy()
    if len(weighed) != cf.EXPECTED_WEIGHED:
        raise SystemExit("weighed filter drifted")

    # Stated weight. Even count: pandas averages the two middle weights.
    # That value is the rule. It is not re-picked to make the gap larger.
    weight_cutoff = float(weighed["weight_kg"].median())
    if not np.isfinite(weight_cutoff) or weight_cutoff <= 0:
        raise SystemExit(f"weight cutoff is not a positive weight: {weight_cutoff}")

    air_all = weighed.loc[weighed["shipment_mode"] == "Air"].copy()
    heavy_air = air_all.loc[air_all["weight_kg"] >= weight_cutoff].copy()
    if heavy_air.empty:
        raise SystemExit("no weighed air shipment is at or above the weight cutoff")

    # Same slice, cheaper mode. Truck, not ocean. Ocean's cheap median is
    # tangled with DDP, and DDP is in the model only when freight was a
    # visible number. Charter is not the population and not the rate.
    truck_slice = weighed.loc[
        (weighed["shipment_mode"] == "Truck") & (weighed["weight_kg"] >= weight_cutoff)
    ].copy()
    if len(truck_slice) < RANK_MIN:
        raise SystemExit(
            f"truck slice has {len(truck_slice)} rows; refusing a median from a thin slice"
        )
    truck_median = float(truck_slice["freight_per_kg"].median())
    if not np.isfinite(truck_median) or truck_median <= 0:
        raise SystemExit(f"truck median rate is not positive: {truck_median}")

    heavy_air["counterfactual_mode"] = "Truck"
    heavy_air["counterfactual_median_freight_per_kg"] = truck_median
    heavy_air["rate_gap_per_kg"] = heavy_air["freight_per_kg"] - truck_median
    # Strictly above. A note already at the truck median is not a gap.
    heavy_air["enters_dollar_gap"] = (heavy_air["freight_per_kg"] > truck_median).astype(int)
    heavy_air["dollar_gap"] = np.where(
        heavy_air["enters_dollar_gap"] == 1,
        heavy_air["weight_kg"] * heavy_air["rate_gap_per_kg"],
        0.0,
    )
    # The dollar gap is also freight minus weight times the truck median.
    # The two expressions have to match. A mismatch is a coding error,
    # not a rounding choice.
    entering = heavy_air.loc[heavy_air["enters_dollar_gap"] == 1]
    from_rate = float(entering["dollar_gap"].sum())
    from_bill = float(
        (entering["freight_usd"] - entering["weight_kg"] * truck_median).sum()
    )
    if abs(from_rate - from_bill) > 1e-4:
        raise SystemExit(f"dollar gap identity failed: {from_rate} vs {from_bill}")
    if (entering["dollar_gap"] <= 0).any():
        raise SystemExit("a note entered the gap with a non-positive dollar difference")

    # Not in this dollar figure, and not zeros. Counted so the writeup
    # cannot drop them silently.
    reasons = shipments["exclusion_reason"].value_counts()
    charter_heavy = int(
        (
            (weighed["shipment_mode"] == "Air Charter")
            & (weighed["weight_kg"] >= weight_cutoff)
        ).sum()
    )
    ocean_heavy = int(
        (
            (weighed["shipment_mode"] == "Ocean")
            & (weighed["weight_kg"] >= weight_cutoff)
        ).sum()
    )
    blank_heavy = int(
        (
            (weighed["shipment_mode"] == "(blank)")
            & (weighed["weight_kg"] >= weight_cutoff)
        ).sum()
    )

    air_notes = heavy_air[
        [
            "asn_dn",
            "country",
            "vendor",
            "vendor_inco_term",
            "weight_kg",
            "freight_usd",
            "freight_per_kg",
            "counterfactual_mode",
            "counterfactual_median_freight_per_kg",
            "rate_gap_per_kg",
            "enters_dollar_gap",
            "dollar_gap",
        ]
    ].sort_values("asn_dn")
    truck_notes = truck_slice[
        ["asn_dn", "country", "vendor", "vendor_inco_term", "weight_kg", "freight_usd", "freight_per_kg"]
    ].sort_values("asn_dn")

    # Headline model, refit with Construct's formula and HC1 intervals.
    # Printed so the writeup quotes this run. The fit is not the savings.
    fit = model.rename(columns={"shipment_mode": "mode"}).copy()
    for column in ("mode", "inco_grouped", "country_grouped", "vendor", "country"):
        fit[column] = fit[column].astype(object)
    mode_piece = cf.treatment("mode", meta["mode_reference"])
    inco_piece = cf.treatment("inco_grouped", meta["inco_reference"])
    formula_full = f"log_rate ~ {mode_piece} + log_weight + {inco_piece} + orgenics"
    formula_mode = f"log_rate ~ {mode_piece}"
    formula_mode_weight = f"log_rate ~ {mode_piece} + log_weight"
    _c_mode, r_mode = cf.fit_ols(formula_mode, fit)
    _c_mw, r_mw = cf.fit_ols(formula_mode_weight, fit)
    c_full, r_full = cf.fit_ols(formula_full, fit)
    trimmed = fit.loc[fit["above_weighed_p95"] == 0].copy()
    c_p95, r_p95 = cf.fit_ols(formula_full, trimmed)

    def pack(label: str, robust) -> dict:
        out = {}
        for needle in ("Air Charter", "Ocean", "Truck", "log_weight", "orgenics"):
            if needle == "orgenics" and needle not in list(robust.params.index):
                continue
            if needle == "log_weight" and "log_weight" not in list(robust.params.index):
                continue
            name, coef, lo, hi, gap = coef_of(robust, needle)
            key = {
                "Air Charter": "air_charter",
                "Ocean": "ocean",
                "Truck": "truck",
                "log_weight": "log_weight",
                "orgenics": "orgenics",
            }[needle]
            out[f"{label}_{key}_coef"] = coef
            out[f"{label}_{key}_ci_low"] = lo
            out[f"{label}_{key}_ci_high"] = hi
            out[f"{label}_{key}_expm1"] = gap
            out[f"{label}_{key}_contains_0"] = int(lo <= 0.0 <= hi)
            out[f"{label}_{key}_term"] = name
        return out

    fits = {}
    fits.update(pack("mode_only", r_mode))
    fits.update(pack("mode_weight", r_mw))
    fits.update(pack("full", r_full))
    fits.update(pack("p95", r_p95))

    ocean = model.loc[model["shipment_mode"] == "Ocean"]
    ocean_ddp = int((ocean["vendor_inco_term"] == "DDP").sum())
    orgenics = model.loc[model["orgenics"] == 1]
    orgenics_air = int((orgenics["shipment_mode"] == "Air").sum())

    band = (weighed["weight_kg"] >= af.WEIGHT_BAND_LO_KG) & (
        weighed["weight_kg"] <= af.WEIGHT_BAND_HI_KG
    )
    air_band = weighed.loc[(weighed["shipment_mode"] == "Air") & band]
    org_band = air_band.loc[air_band["vendor"] == ORGENICS_NAME]
    rdc_band = air_band.loc[air_band["vendor"] == RDC_NAME]
    air_ref = float(air_band["freight_per_kg"].median())

    # Uncontrolled country lead: highest median on the weighed set among
    # countries with at least 20 weighed shipments. "Keeps the lead" would
    # mean that same country still has at least 20 weighed air shipments
    # inside the 500–5,000 kg band. This run checks the top of that list.
    country_rows = []
    for country, sub in weighed.groupby("country", dropna=False):
        if len(sub) < RANK_MIN:
            continue
        country_rows.append(
            (
                str(country),
                int(len(sub)),
                float(sub["freight_per_kg"].median()),
            )
        )
    country_rows.sort(key=lambda rec: (-rec[2], rec[0]))
    top_country, top_n, top_median = country_rows[0]
    top_air_band = weighed.loc[
        (weighed["country"] == top_country) & (weighed["shipment_mode"] == "Air") & band
    ]
    leaders_keeping = []
    for country, n_all, med in country_rows[:5]:
        n_band = int(
            (
                (weighed["country"] == country)
                & (weighed["shipment_mode"] == "Air")
                & band
            ).sum()
        )
        if n_band >= RANK_MIN:
            leaders_keeping.append(country)

    delivered = dates.loc[dates["column_name"] == "Delivered to Client Date"].iloc[0]
    max_row = weighed.loc[weighed["freight_per_kg"].idxmax()]

    n_enter = int(entering.shape[0])
    kg_enter = float(entering["weight_kg"].sum())
    freight_enter = float(entering["freight_usd"].sum())
    # Both figures are upper bounds. The full gap assumes every entering
    # note could have moved at the truck median. The 25 percent share is
    # the same assumption on a quarter of that gap, not a chosen subset.
    share_usd = from_rate * SHARE

    rows: list[tuple[str, object]] = [
        ("scenario_label", "what_if_not_a_saving"),
        (
            "population_rule",
            "Weighed Air shipments whose Yes-line weight is at or above "
            "the median Yes-line weight of the weighed set",
        ),
        (
            "counterfactual_rule",
            "Observed median freight per kg of weighed Truck shipments "
            "on that same weight slice, not a regression coefficient",
        ),
        ("weight_cutoff_kg", weight_cutoff),
        ("weight_cutoff_source", "median weight_kg on the weighed set"),
        ("weighed_n", int(len(weighed))),
        ("weighed_median_freight_per_kg", float(weighed["freight_per_kg"].median())),
        ("weighed_mean_freight_per_kg", float(weighed["freight_per_kg"].mean())),
        ("weighed_max_freight_per_kg", float(weighed["freight_per_kg"].max())),
        ("weighed_p95_freight_per_kg", float(weighed["freight_per_kg"].quantile(0.95))),
        ("max_rate_asn", str(max_row["asn_dn"])),
        ("max_rate_mode", str(max_row["shipment_mode"])),
        ("max_rate_weight_kg", float(max_row["weight_kg"])),
        ("max_rate_freight_usd", float(max_row["freight_usd"])),
        (
            "freight_to_value_n",
            int(shipments["in_freight_to_value"].sum()),
        ),
        (
            "median_freight_to_value",
            float(shipments.loc[shipments["in_freight_to_value"] == 1, "freight_to_value"].median()),
        ),
        ("total_numeric_freight", float(shipments.loc[shipments["in_priced"] == 1, "freight_usd"].sum())),
        ("total_numeric_freight_weighed", float(weighed["freight_usd"].sum())),
        ("priced_n", int(shipments["in_priced"].sum())),
        ("excluded_included_in_price", int(reasons.get("included_in_price", 0))),
        ("excluded_invoiced_separately", int(reasons.get("invoiced_separately", 0))),
        ("excluded_see_another_note", int(reasons.get("see_another_note", 0))),
        ("excluded_weight_not_numeric", int(reasons.get("weight_not_numeric", 0))),
        ("excluded_weight_not_positive", int(reasons.get("weight_not_positive", 0))),
        ("zero_weight_asn", cf.ZERO_WEIGHT_ASN),
        ("air_weighed_n", int(len(air_all))),
        ("air_median_weight_kg", float(air_all["weight_kg"].median())),
        ("air_median_freight_per_kg", float(air_all["freight_per_kg"].median())),
        ("heavy_air_n", int(len(heavy_air))),
        ("heavy_air_total_kg", float(heavy_air["weight_kg"].sum())),
        ("heavy_air_total_freight_usd", float(heavy_air["freight_usd"].sum())),
        ("heavy_air_not_above_truck_median_n", int((heavy_air["enters_dollar_gap"] == 0).sum())),
        ("truck_slice_n", int(len(truck_slice))),
        ("truck_slice_median_freight_per_kg", truck_median),
        ("truck_slice_total_kg", float(truck_slice["weight_kg"].sum())),
        ("entering_n", n_enter),
        ("entering_total_kg", kg_enter),
        ("entering_total_freight_usd", freight_enter),
        ("dollar_difference_usd", from_rate),
        ("dollar_difference_from_bill_usd", from_bill),
        ("share", SHARE),
        ("share_25_of_gap_usd", share_usd),
        (
            "share_25_meaning",
            "25 percent of the full dollar gap. Not a selected subset of notes. "
            "Both the full gap and this share are upper-bound what-ifs.",
        ),
        ("charter_weighed_at_or_above_cutoff_not_moved", charter_heavy),
        ("ocean_weighed_at_or_above_cutoff_not_counterfactual", ocean_heavy),
        ("blank_weighed_at_or_above_cutoff_not_in_scenario", blank_heavy),
        ("air_band_n", int(len(air_band))),
        ("air_band_median_freight_per_kg", air_ref),
        ("orgenics_air_band_n", int(len(org_band))),
        ("orgenics_air_band_median_freight_per_kg", float(org_band["freight_per_kg"].median())),
        ("rdc_air_band_n", int(len(rdc_band))),
        ("rdc_air_band_median_freight_per_kg", float(rdc_band["freight_per_kg"].median())),
        ("top_uncontrolled_country", top_country),
        ("top_uncontrolled_country_weighed_n", top_n),
        ("top_uncontrolled_country_median_freight_per_kg", top_median),
        ("top_uncontrolled_country_air_band_n", int(len(top_air_band))),
        ("uncontrolled_top5_keeping_air_band_n_ge_20", "|".join(leaders_keeping) if leaders_keeping else "(none)"),
        ("model_n", int(meta["model_n"])),
        ("blank_weighed_n", int(meta["blank_weighed_n"])),
        ("air_model_n", int((model["shipment_mode"] == "Air").sum())),
        ("full_n", int(c_full.nobs)),
        ("full_r_squared", float(c_full.rsquared)),
        ("mode_only_r_squared", float(_c_mode.rsquared)),
        ("mode_weight_r_squared", float(_c_mw.rsquared)),
        ("p95_n", int(c_p95.nobs)),
        ("p95_r_squared", float(c_p95.rsquared)),
        ("ocean_model_n", int(len(ocean))),
        ("ocean_model_ddp_n", ocean_ddp),
        ("orgenics_model_n", int(len(orgenics))),
        ("orgenics_model_air_n", orgenics_air),
        ("delivered_min", str(delivered["min_date"])),
        ("delivered_max", str(delivered["max_date"])),
        ("mode_reference", meta["mode_reference"]),
        ("inco_reference", meta["inco_reference"]),
    ]
    for key in sorted(fits):
        rows.append((key, fits[key]))

    extract_info = verify_extract(shipments, model)
    rows.append(("extract_path", extract_info["path"]))
    rows.append(("extract_rows", extract_info["rows"]))
    rows.append(("extract_rewritten", extract_info["rewritten"]))
    rows.append(("extract_check", extract_info["check"]))
    rows.append(("tableau_published", 0))

    result = metric_frame(rows)
    air_path = save_csv(air_notes, "execute_scenario_air_notes.csv")
    truck_path = save_csv(truck_notes, "execute_scenario_truck_notes.csv")
    result_path = save_csv(result, "execute_scenario_result.csv")

    # Stdout is the source the writeup quotes. Keys stay stable.
    print(f"wrote {air_path}")
    print(f"wrote {truck_path}")
    print(f"wrote {result_path}")
    for name, value in rows:
        print(f"{name}={value}")


if __name__ == "__main__":
    main()
