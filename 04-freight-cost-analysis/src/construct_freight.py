#!/usr/bin/env python3
"""Construct stage: what lines up with freight per kilogram.

The outcome is freight per kilogram on the weighed set from the Yes-line
rollup. The model that is interpreted is OLS of the log of that rate, not
OLS of the raw rate and not a model of raw freight dollars. This stage
does not price a savings scenario, write an executive summary, or publish
a Tableau workbook. Those belong to Execute.

Run from the repo root:
    python 04-freight-cost-analysis/src/construct_freight.py

Run from the project folder (04-freight-cost-analysis):
    python src/construct_freight.py

Needs pandas, numpy, matplotlib, and statsmodels. This run used
statsmodels 0.14.4 (Debian python3-statsmodels). If `import statsmodels`
fails:

    sudo apt-get install python3-statsmodels

Paths are anchored to this file, not to the shell's current directory.

Input (git-ignored, already on disk; this script does not copy it):
    04-freight-cost-analysis/data/raw/SCMS_Delivery_History_Dataset.csv
    Latin-1. Read only through analyze_freight.load_raw and the Yes-line
    rollup. This file does not re-decide the grain.

Outputs under 04-freight-cost-analysis/:
    data/processed/construct_*.csv
    images/construct_mode_coefficients.png
    dashboards/shipment_weighed.csv

The shipment dashboard file is one row per weighed ASN/DN. It is not a
second copy of the line extract. Insurance and manufacturing site are
not written.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save a file; do not open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Same directory as this file, whether the shell was the repo root or the
# project folder. The rollup lives in analyze_freight so the grain rule
# cannot drift into a second implementation.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_freight as af  # noqa: E402

try:
    import statsmodels
    import statsmodels.formula.api as smf
except ImportError as exc:
    raise SystemExit(
        "statsmodels is not installed. On this machine: "
        "sudo apt-get install python3-statsmodels"
    ) from exc

# parents[1] is 04-freight-cost-analysis. Same anchor as analyze_freight.
PROJECT = Path(__file__).resolve().parents[1]
PROC = PROJECT / "data" / "processed"
IMG = PROJECT / "images"
DASH = PROJECT / "dashboards"

# The Analyze stage locked these counts under the Yes-line rule. They are
# a tripwire, not a rate. If the rollup no longer produces them, this
# script stops instead of fitting a different population.
EXPECTED_SHIPMENTS = 7030
EXPECTED_WEIGHED = 6174
EXPECTED_PRICED = 6198
EXPECTED_INCLUDED = 593
EXPECTED_INVOICED = 239
EXPECTED_SEE_ON_YES = 0
EXPECTED_WEIGHT_NOT_NUMERIC = 23
EXPECTED_WEIGHT_NOT_POSITIVE = 1
ZERO_WEIGHT_ASN = "ASN-22365"
# Weighed shipments whose mode is blank. Analyze counted 211. They are
# dropped from the model below, and the script stops if that count moves,
# so a relabeled blank cannot quietly become a mode.
EXPECTED_BLANK_WEIGHED = 211

# Rare INCO terms are pooled so the model does not carry a coefficient
# for a 1-shipment level. 50 is above the scorecard's rank threshold of
# 20: a level that is only large enough to rank a median is still a noisy
# dummy. The count is taken on the model rows (named mode), which is the
# sample the dummy is fit on. N/A - From RDC stays if it clears 50.
MIN_LEVEL_N = 50
OTHER_LABEL = "Other"
ORGENICS_MARK = "orgenics"

# Intervals the report quotes. HC1, not the classical OLS variance.
# The log compresses the tail. It does not make every mode equally noisy.
COV_TYPE = "HC1"
CI_ALPHA = 0.05


def save_csv(df: pd.DataFrame, name: str) -> Path:
    """Write one small table. Names stay under construct_ so Analyze files stay put."""
    if not name.startswith("construct_") or not name.endswith(".csv"):
        raise SystemExit(f"refusing to write {name}")
    PROC.mkdir(parents=True, exist_ok=True)
    path = PROC / name
    df.to_csv(path, index=False)
    return path


def build_shipments() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Yes-line rollup, then stop if the locked population moved.

    Grain, the priced set, and the weighed set are analyze_freight's
    rule. This function does not parse freight a second way and does not
    copy a manufacturing site. date_window is the same parser Analyze
    used, so the years in the writeup are this run, not a pasted date.
    """
    df = af.load_raw(af.RAW)
    df["freight_class"] = df["Freight Cost (USD)"].map(af.freight_class)
    df["weight_class"] = df["Weight (Kilograms)"].map(af.weight_class)
    if (df["freight_class"] == "other").any() or (df["weight_class"] == "other").any():
        raise SystemExit("unclassified freight or weight text")
    patterns = af.shipment_patterns(df)
    shipments = af.yes_line_rollup(df, patterns)
    if "Manufacturing Site" in shipments.columns:
        raise SystemExit("manufacturing site leaked into the construct rollup")
    if len(shipments) != EXPECTED_SHIPMENTS:
        raise SystemExit(f"shipment count changed: {len(shipments)}")
    if int(shipments["in_weighed"].sum()) != EXPECTED_WEIGHED:
        raise SystemExit(f"weighed count changed: {int(shipments['in_weighed'].sum())}")
    if int(shipments["in_priced"].sum()) != EXPECTED_PRICED:
        raise SystemExit(f"priced count changed: {int(shipments['in_priced'].sum())}")

    reasons = shipments["exclusion_reason"].value_counts()
    expected_reasons = {
        "kept": EXPECTED_WEIGHED,
        "included_in_price": EXPECTED_INCLUDED,
        "invoiced_separately": EXPECTED_INVOICED,
        "see_another_note": EXPECTED_SEE_ON_YES,
        "weight_not_numeric": EXPECTED_WEIGHT_NOT_NUMERIC,
        "weight_not_positive": EXPECTED_WEIGHT_NOT_POSITIVE,
    }
    for reason, n_expected in expected_reasons.items():
        got = int(reasons.get(reason, 0))
        if got != n_expected:
            raise SystemExit(f"exclusion {reason} is {got}, expected {n_expected}")

    zero = shipments.loc[shipments["asn_dn"] == ZERO_WEIGHT_ASN]
    if len(zero) != 1:
        raise SystemExit(f"{ZERO_WEIGHT_ASN} is missing from the rollup")
    if int(zero["in_weighed"].iloc[0]) != 0:
        raise SystemExit(f"{ZERO_WEIGHT_ASN} entered the weighed set")
    if zero["exclusion_reason"].iloc[0] != "weight_not_positive":
        raise SystemExit(f"{ZERO_WEIGHT_ASN} exclusion reason changed")
    # A zero weight is not a denominator. The string parsed. It is still out.
    if float(zero["weight_kg"].iloc[0]) != 0.0:
        raise SystemExit(f"{ZERO_WEIGHT_ASN} weight is no longer zero")

    dates = af.date_window(df)
    return shipments, dates


def estimation_frame(shipments: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Weighed shipments with a named mode. Blank mode is counted, then dropped.

    A blank is a null, not a mode someone chose. Imputing a mode would
    invent the coefficient's comparison. Keeping blank as its own level
    would report a rate for a label that is not a decision. The drop is
    the model sample. The weighed set stays the outcome's population and
    is what the dashboard file contains.

    log(freight per kg) is undefined at zero. A non-positive rate stops
    the script. It is not replaced with a small number.
    """
    weighed = shipments.loc[shipments["in_weighed"] == 1].copy()
    if len(weighed) != EXPECTED_WEIGHED:
        raise SystemExit("weighed filter drifted")
    if (weighed["freight_per_kg"] <= 0).any():
        raise SystemExit("a weighed shipment has a non-positive rate; log is undefined")
    if (weighed["weight_kg"] <= 0).any():
        raise SystemExit("a weighed shipment has a non-positive weight")
    # The rate is the Yes-line freight over the Yes-line weight, once.
    rebuilt = weighed["freight_usd"] / weighed["weight_kg"]
    if float((rebuilt - weighed["freight_per_kg"]).abs().max()) > 1e-9:
        raise SystemExit("freight_per_kg is not freight divided by weight")

    blank_n = int((weighed["shipment_mode"] == "(blank)").sum())
    if blank_n != EXPECTED_BLANK_WEIGHED:
        raise SystemExit(f"blank weighed shipments changed: {blank_n}")
    model = weighed.loc[weighed["shipment_mode"] != "(blank)"].copy()
    if model["shipment_mode"].isna().any() or (model["shipment_mode"] == "").any():
        raise SystemExit("a blank mode survived the drop")
    if len(model) != EXPECTED_WEIGHED - EXPECTED_BLANK_WEIGHED:
        raise SystemExit("model rows are not weighed minus blank")

    # p95 is the weighed set, blank mode included. The sensitivity drops
    # model rows above that cut. It does not recompute p95 on the named
    # modes only, which would move the cut because blank was removed.
    p95 = float(weighed["freight_per_kg"].quantile(0.95))
    model["above_weighed_p95"] = (model["freight_per_kg"] > p95).astype(int)

    orgenics_names = sorted(
        v for v in model["vendor"].unique() if ORGENICS_MARK in str(v).lower()
    )
    if len(orgenics_names) != 1:
        raise SystemExit(f"expected one Orgenics vendor, found {orgenics_names}")
    orgenics_name = orgenics_names[0]
    model["orgenics"] = (model["vendor"] == orgenics_name).astype(int)
    # The indicator has to vary inside the sample. If every Orgenics row
    # were a mode by itself, the dummy would be the mode.
    if model["orgenics"].nunique() != 2:
        raise SystemExit("Orgenics indicator does not vary")

    model["log_rate"] = np.log(model["freight_per_kg"])
    model["log_weight"] = np.log(model["weight_kg"])
    # log_freight is the outcome of the dollar comparison only. It is not
    # a regressor in the headline formula. That check is after the formulas
    # are built.
    model["log_freight"] = np.log(model["freight_usd"])

    inco_grouped, inco_table = pool_rare(
        model["vendor_inco_term"], "vendor_inco_term", model["vendor_inco_term"]
    )
    # Country is not in the headline model. The grouped column is the
    # separate check: does place add fit after mode, size, INCO, and
    # Orgenics. Same minimum n, so a 1-shipment country is not a story.
    country_grouped, country_table = pool_rare(
        model["country"], "country", model["country"]
    )
    model["inco_grouped"] = inco_grouped
    model["country_grouped"] = country_grouped
    grouping = pd.concat([inco_table, country_table], ignore_index=True)

    mode_reference = most_common(model["shipment_mode"], "shipment mode")
    inco_reference = most_common(model["inco_grouped"], "grouped INCO term")
    if inco_reference == OTHER_LABEL:
        raise SystemExit("the INCO reference would be the pooled tail")
    # Country reference is the most common kept country, not Other, so a
    # country coefficient is versus a real place.
    kept_countries = model.loc[model["country_grouped"] != OTHER_LABEL, "country_grouped"]
    country_reference = most_common(kept_countries, "kept country")

    meta = {
        "orgenics_name": orgenics_name,
        "p95_freight_per_kg": p95,
        "mode_reference": mode_reference,
        "inco_reference": inco_reference,
        "country_reference": country_reference,
        "weighed_n": int(len(weighed)),
        "blank_weighed_n": blank_n,
        "model_n": int(len(model)),
        "model_above_p95": int(model["above_weighed_p95"].sum()),
        "model_at_or_below_p95": int((model["above_weighed_p95"] == 0).sum()),
        "blank_above_p95": int(
            (
                (weighed["shipment_mode"] == "(blank)")
                & (weighed["freight_per_kg"] > p95)
            ).sum()
        ),
        "weighed_median_rate": float(weighed["freight_per_kg"].median()),
        "weighed_mean_rate": float(weighed["freight_per_kg"].mean()),
        "weighed_max_rate": float(weighed["freight_per_kg"].max()),
        "model_median_rate": float(model["freight_per_kg"].median()),
        "model_mean_rate": float(model["freight_per_kg"].mean()),
        "model_max_rate": float(model["freight_per_kg"].max()),
    }
    max_row = weighed.loc[weighed["freight_per_kg"].idxmax()]
    meta["max_rate_asn"] = str(max_row["asn_dn"])
    meta["max_rate_mode"] = str(max_row["shipment_mode"])
    meta["max_rate_vendor"] = str(max_row["vendor"])
    meta["max_rate_weight_kg"] = float(max_row["weight_kg"])
    meta["max_rate_freight_usd"] = float(max_row["freight_usd"])
    return model, grouping, meta


def pool_rare(series: pd.Series, factor: str, original: pd.Series) -> tuple[pd.Series, pd.DataFrame]:
    """Keep levels with at least MIN_LEVEL_N rows. Pool the rest as Other.

    The threshold is counted on `series`, which is the model sample.
    `original` is the same column before pooling, so the table can show
    the unpooled name. A stored level that is already called Other would
    be mixed with the pool. That has to stop.
    """
    if (series == OTHER_LABEL).any():
        raise SystemExit(f"{factor} already has a level named {OTHER_LABEL}")
    counts = series.value_counts()
    keep = set(counts[counts >= MIN_LEVEL_N].index)
    if not keep:
        raise SystemExit(f"{factor} has no level with n >= {MIN_LEVEL_N}")
    grouped = series.where(series.isin(keep), OTHER_LABEL)
    rows = []
    for level, n in counts.items():
        rows.append(
            {
                "factor": factor,
                "level": level,
                "n_model_rows": int(n),
                "kept": int(n >= MIN_LEVEL_N),
                "grouped_as": level if n >= MIN_LEVEL_N else OTHER_LABEL,
                "min_n": MIN_LEVEL_N,
                "rule": (
                    f"keep levels with at least {MIN_LEVEL_N} model rows "
                    "(weighed, named mode); pool the rest as Other"
                ),
            }
        )
    other_n = int((grouped == OTHER_LABEL).sum())
    rows.append(
        {
            "factor": factor,
            "level": OTHER_LABEL,
            "n_model_rows": other_n,
            "kept": 0,
            "grouped_as": OTHER_LABEL,
            "min_n": MIN_LEVEL_N,
            "rule": "pooled tail, not a commercial term and not a country",
        }
    )
    if int(grouped.isin(list(keep) + [OTHER_LABEL]).sum()) != len(series):
        raise SystemExit(f"{factor} grouping dropped a row")
    # original is accepted so a future caller can pass a pre-filter count.
    # Today it is the same series. A length mismatch means the caller
    # changed one and not the other.
    if len(original) != len(series):
        raise SystemExit(f"{factor} original length does not match the model rows")
    return grouped, pd.DataFrame(rows)


def most_common(series: pd.Series, label: str) -> str:
    """Modal level. A tie stops the script. Alphabetical order is not a reference."""
    counts = series.value_counts()
    if len(counts) < 1:
        raise SystemExit(f"no levels for {label}")
    if len(counts) > 1 and int(counts.iloc[0]) == int(counts.iloc[1]):
        raise SystemExit(f"{label} has a tie for the most common level: {list(counts.index[:2])}")
    return str(counts.index[0])


def treatment(column: str, reference: str) -> str:
    """Patsy treatment coding. The reference is a quoted level, not the first alphabetically."""
    if "'" in reference:
        raise SystemExit(f"reference {reference!r} contains a quote; refusing to build the formula")
    return f"C({column}, Treatment(reference='{reference}'))"


def fit_ols(formula: str, data: pd.DataFrame):
    """OLS point estimates, with HC1 covariance for the intervals.

    WLS by kilograms is not used. Weighting by weight would answer the
    rate of the typical kilogram and let the heaviest shipments dominate.
    The scorecard's headline is the typical shipment. The log outcome is
    how the heavy tail is handled. HC1 is how unequal mode variance is
    handled after that log. Classical standard errors are fit only so the
    coefficient file can show both.
    """
    classical = smf.ols(formula, data=data).fit()
    robust = smf.ols(formula, data=data).fit(cov_type=COV_TYPE)
    # Same point estimates. If HC1 changed the coefficient, the two fits
    # are not the same model.
    if float(np.max(np.abs(classical.params - robust.params))) > 1e-8:
        raise SystemExit("HC1 fit changed a coefficient")
    return classical, robust


def clean_term(name: str) -> tuple[str, str]:
    """Split a patsy name into the factor and the level the report can say."""
    if name == "Intercept":
        return "Intercept", "(intercept)"
    if name == "log_weight":
        return "log_weight", "log(weight_kg)"
    if name == "orgenics":
        return "orgenics", "Orgenics versus everyone else"
    match = re.fullmatch(
        r"C\((?P<var>[^,]+), Treatment\(reference='[^']*'\)\)\[T\.(?P<level>.*)\]",
        name,
    )
    if not match:
        raise SystemExit(f"unrecognized coefficient name: {name}")
    return match.group("var"), match.group("level")


def coef_rows(
    classical,
    robust,
    model_name: str,
    n: int,
    level_n: dict[tuple[str, str], int],
    log_outcome: bool,
) -> list[dict]:
    """One row per coefficient. The interval that is interpreted is HC1."""
    ci = robust.conf_int(alpha=CI_ALPHA)
    classical_ci = classical.conf_int(alpha=CI_ALPHA)
    rows = []
    for name in robust.params.index:
        factor, level = clean_term(str(name))
        coef = float(robust.params[name])
        lo = float(ci.loc[name, 0])
        hi = float(ci.loc[name, 1])
        if hi < lo:
            raise SystemExit(f"interval reversed for {name}")
        # exp(coef)-1 is a multiplicative change only when the outcome is
        # a log. On the raw rate it is not a percent, and a large positive
        # coefficient overflows into a useless number. The intercept is
        # the log outcome at the reference, not a gap, so it stays blank
        # even on a log model.
        if factor == "Intercept" or not log_outcome:
            mult = np.nan
        else:
            mult = float(np.exp(coef) - 1.0)
        key = (factor, level)
        rows.append(
            {
                "model": model_name,
                "n": int(n),
                "term": str(name),
                "factor": factor,
                "level": level,
                "level_n": int(level_n.get(key, n if factor in ("Intercept", "log_weight") else -1)),
                "coefficient": coef,
                "std_err_hc1": float(robust.bse[name]),
                "ci_low_hc1": lo,
                "ci_high_hc1": hi,
                "pvalue_hc1": float(robust.pvalues[name]),
                "std_err_classical": float(classical.bse[name]),
                "ci_low_classical": float(classical_ci.loc[name, 0]),
                "ci_high_classical": float(classical_ci.loc[name, 1]),
                "exp_coef_minus_1": mult,
                "interval_contains_zero": int(lo <= 0.0 <= hi),
                "cov_type_interpreted": COV_TYPE,
            }
        )
    return rows


def level_counts(data: pd.DataFrame, meta: dict) -> dict[tuple[str, str], int]:
    """Rows behind each dummy, so a coefficient is not quoted without its n."""
    counts: dict[tuple[str, str], int] = {}
    for level, n in data["mode"].value_counts().items():
        counts[("mode", str(level))] = int(n)
    for level, n in data["inco_grouped"].value_counts().items():
        counts[("inco_grouped", str(level))] = int(n)
    for level, n in data["country_grouped"].value_counts().items():
        counts[("country_grouped", str(level))] = int(n)
    counts[("orgenics", "Orgenics versus everyone else")] = int(data["orgenics"].sum())
    counts[("log_weight", "log(weight_kg)")] = int(len(data))
    counts[("Intercept", "(intercept)")] = int(len(data))
    # The reference levels have no dummy. Store them so the file still
    # says how large the baseline is. The coefficient rows skip these.
    counts[("mode_reference", meta["mode_reference"])] = int(
        (data["mode"] == meta["mode_reference"]).sum()
    )
    return counts


def metric_row(model_name: str, classical, n: int, extra: dict | None = None) -> dict:
    row = {
        "model": model_name,
        "n": int(n),
        "r_squared": float(classical.rsquared),
        "r_squared_adj": float(classical.rsquared_adj),
        "aic": float(classical.aic),
        "bic": float(classical.bic),
        "df_model": float(classical.df_model),
        "df_resid": float(classical.df_resid),
        "outcome": "",
        "formula": str(classical.model.formula),
        "interpreted": 0,
    }
    if extra:
        row.update(extra)
    return row


def wald_extra(robust, prefixes: tuple[str, ...]) -> dict:
    """Joint HC1 Wald test that every coefficient whose factor starts with a prefix is zero."""
    names = []
    for name in robust.params.index:
        factor, _level = clean_term(str(name))
        if factor in prefixes:
            names.append(str(name))
    if not names:
        raise SystemExit(f"no terms to test for {prefixes}")
    result = robust.wald_test(names, scalar=True)
    return {
        "terms": len(names),
        "statistic": float(np.asarray(result.statistic).reshape(-1)[0]),
        "pvalue": float(np.asarray(result.pvalue).reshape(-1)[0]),
        "df_constraint": len(names),
    }


def orgenics_mix(model: pd.DataFrame, name: str) -> pd.DataFrame:
    """Where the Orgenics rows sit, so the dummy is not read as a mode in disguise."""
    rows = []
    for mode, sub in model.groupby("mode", dropna=False):
        flagged = sub.loc[sub["orgenics"] == 1, "freight_per_kg"]
        other = sub.loc[sub["orgenics"] == 0, "freight_per_kg"]
        rows.append(
            {
                "vendor": name,
                "shipment_mode": mode,
                "n": int(len(sub)),
                "orgenics_n": int(len(flagged)),
                "other_n": int(len(other)),
                "orgenics_median_freight_per_kg": float(flagged.median()) if len(flagged) else np.nan,
                "other_median_freight_per_kg": float(other.median()) if len(other) else np.nan,
            }
        )
    out = pd.DataFrame(rows).sort_values("orgenics_n", ascending=False)
    if int(out["orgenics_n"].sum()) != int(model["orgenics"].sum()):
        raise SystemExit("Orgenics mode mix does not cover the indicator")
    return out


def mode_chart(coef: pd.DataFrame, meta: dict) -> None:
    """Mode coefficients versus Air, full model and the p95 sensitivity.

    The title names the outcome and the sample. A bar of raw dollars is
    not this chart. Zero is Air, the reference, not a missing coefficient.
    """
    full = coef.loc[(coef["model"] == "full_log_rate") & (coef["factor"] == "mode")].copy()
    sens = coef.loc[(coef["model"] == "full_log_rate_at_or_below_p95") & (coef["factor"] == "mode")].copy()
    if full.empty or sens.empty:
        raise SystemExit("mode chart is missing a model")
    order = full.sort_values("coefficient", ascending=True)["level"].tolist()
    full = full.set_index("level").loc[order]
    sens = sens.set_index("level").loc[order]

    y = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    ax.errorbar(
        full["coefficient"],
        y + 0.12,
        xerr=[
            full["coefficient"] - full["ci_low_hc1"],
            full["ci_high_hc1"] - full["coefficient"],
        ],
        fmt="o",
        color="#4C78A8",
        ecolor="#4C78A8",
        capsize=3,
        label=f"Full model, n={meta['model_n']:,}",
    )
    ax.errorbar(
        sens["coefficient"],
        y - 0.12,
        xerr=[
            sens["coefficient"] - sens["ci_low_hc1"],
            sens["ci_high_hc1"] - sens["coefficient"],
        ],
        fmt="o",
        color="#E45756",
        ecolor="#E45756",
        capsize=3,
        label=f"Rates at or below weighed-set p95, n={meta['model_at_or_below_p95']:,}",
    )
    ax.axvline(0.0, color="#333333", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{level} vs Air" for level in order])
    ax.set_xlabel("OLS coefficient on log(freight per kg). HC1 95% interval. 0 is Air.")
    ax.set_title(
        "Log freight per kg versus Air\n"
        "Weighed shipments with a named mode, Yes-line rule. Not a dollar saving."
    )
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    IMG.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG / "construct_mode_coefficients.png", dpi=120)
    plt.close(fig)


def write_dashboard(shipments: pd.DataFrame, model_keys: pd.Series) -> Path:
    """Weighed shipments only, with the columns a mode/country/vendor view needs.

    Blank mode stays in this file, labeled (blank), because the file is
    the weighed set and not the regression sample. in_regression_sample
    is 1 when the row was in the model. Included-in-price and invoiced
    shipments are not here and are not zeros. Insurance and manufacturing
    site are not columns.
    """
    weighed = shipments.loc[shipments["in_weighed"] == 1].copy()
    if len(weighed) != EXPECTED_WEIGHED:
        raise SystemExit("dashboard population is not the weighed set")
    out = pd.DataFrame(
        {
            "asn_dn": weighed["asn_dn"],
            "shipment_mode": weighed["shipment_mode"],
            "country": weighed["country"],
            "vendor": weighed["vendor"],
            "vendor_inco_term": weighed["vendor_inco_term"],
            "weight_kg": weighed["weight_kg"],
            "freight_usd": weighed["freight_usd"],
            "freight_per_kg": weighed["freight_per_kg"],
            "line_item_value_sum": weighed["line_item_value_sum"],
            "in_regression_sample": weighed["asn_dn"].isin(set(model_keys)).astype(int),
        }
    )
    if int(out["in_regression_sample"].sum()) != EXPECTED_WEIGHED - EXPECTED_BLANK_WEIGHED:
        raise SystemExit("dashboard regression flag does not match the model sample")
    if (out["shipment_mode"] == "(blank)").sum() != EXPECTED_BLANK_WEIGHED:
        raise SystemExit("blank mode missing from the dashboard file")
    DASH.mkdir(parents=True, exist_ok=True)
    path = DASH / "shipment_weighed.csv"
    out.sort_values("asn_dn").to_csv(path, index=False)
    return path


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    shipments, dates = build_shipments()
    model, grouping, meta = estimation_frame(shipments)

    # Formula columns are short on purpose. The source fields stay on the
    # shipment frame. mode is Shipment Mode after the blank drop.
    model = model.rename(columns={"shipment_mode": "mode"})
    # Patsy on this machine rejects pandas' StringDtype. Object dtype is
    # the same text, and it is what the formula interface can sniff.
    for column in ("mode", "inco_grouped", "country_grouped", "vendor", "country"):
        model[column] = model[column].astype(object)
    counts = level_counts(model, meta)

    mode_piece = treatment("mode", meta["mode_reference"])
    inco_piece = treatment("inco_grouped", meta["inco_reference"])
    country_piece = treatment("country_grouped", meta["country_reference"])
    # Headline. log(weight) is a size control on the rate. The rate already
    # divides by weight, so this coefficient is not "heavier costs more
    # dollars." It is whether the per-kilogram rate falls as shipments get
    # heavier. Raw freight is not on the right-hand side.
    formula_full = f"log_rate ~ {mode_piece} + log_weight + {inco_piece} + orgenics"
    formula_mode = f"log_rate ~ {mode_piece}"
    # Bridges, not a second headline. Mode plus log weight shows what the
    # size control does by itself. Adding grouped INCO, still without
    # Orgenics, shows whether a mode gap was the commercial term. The
    # ocean result in the headline model is not readable without these.
    formula_mode_weight = f"log_rate ~ {mode_piece} + log_weight"
    formula_mode_weight_inco = f"log_rate ~ {mode_piece} + log_weight + {inco_piece}"
    formula_country = formula_full + f" + {country_piece}"
    # Not interpreted. Same right-hand side, raw rate, to show the tail.
    formula_raw = f"freight_per_kg ~ {mode_piece} + log_weight + {inco_piece} + orgenics"
    # Not interpreted. Dollars, to show that a dollar model mostly finds weight.
    formula_dollars_weight = "log_freight ~ log_weight"
    formula_dollars_mode = f"log_freight ~ log_weight + {mode_piece}"
    # The headline explains the rate. Raw freight on the right-hand side
    # would put the numerator of the outcome into the regression.
    for headline in (formula_full, formula_mode, formula_mode_weight, formula_mode_weight_inco):
        if "freight_usd" in headline or "log_freight" in headline:
            raise SystemExit("raw freight leaked into a rate formula")

    samples = {
        "mode_only": model,
        "mode_and_log_weight": model,
        "mode_log_weight_inco": model,
        "full_log_rate": model,
        "full_log_rate_plus_country": model,
        "raw_rate_not_interpreted": model,
        "log_dollars_weight_only": model,
        "log_dollars_weight_and_mode": model,
    }
    formulas = {
        "mode_only": formula_mode,
        "mode_and_log_weight": formula_mode_weight,
        "mode_log_weight_inco": formula_mode_weight_inco,
        "full_log_rate": formula_full,
        "full_log_rate_plus_country": formula_country,
        "raw_rate_not_interpreted": formula_raw,
        "log_dollars_weight_only": formula_dollars_weight,
        "log_dollars_weight_and_mode": formula_dollars_mode,
    }
    outcomes = {
        "mode_only": "log(freight_per_kg)",
        "mode_and_log_weight": "log(freight_per_kg)",
        "mode_log_weight_inco": "log(freight_per_kg)",
        "full_log_rate": "log(freight_per_kg)",
        "full_log_rate_plus_country": "log(freight_per_kg)",
        "raw_rate_not_interpreted": "freight_per_kg",
        "log_dollars_weight_only": "log(freight_usd)",
        "log_dollars_weight_and_mode": "log(freight_usd)",
    }
    interpreted = {
        "mode_only": 1,
        "mode_and_log_weight": 0,
        "mode_log_weight_inco": 0,
        "full_log_rate": 1,
        "full_log_rate_plus_country": 0,
        "raw_rate_not_interpreted": 0,
        "log_dollars_weight_only": 0,
        "log_dollars_weight_and_mode": 0,
    }

    sens = model.loc[model["above_weighed_p95"] == 0].copy()
    if len(sens) != meta["model_at_or_below_p95"]:
        raise SystemExit("p95 sample size drifted")
    # The sensitivity keeps the same reference levels even if a pooled
    # tail would have been empty. It does not re-pick the reference from
    # the trimmed sample, which would make the coefficients incomparable.
    samples["full_log_rate_at_or_below_p95"] = sens
    formulas["full_log_rate_at_or_below_p95"] = formula_full
    outcomes["full_log_rate_at_or_below_p95"] = "log(freight_per_kg)"
    interpreted["full_log_rate_at_or_below_p95"] = 0

    # One row dropped: the charter at the max rate. Only for the raw-rate
    # demonstration. The log model's sensitivity is the p95 cut, not this.
    without_max = model.loc[model["freight_per_kg"] < meta["model_max_rate"]].copy()
    if len(without_max) != len(model) - 1:
        raise SystemExit("dropping the max rate did not drop one row")
    samples["raw_rate_without_max_not_interpreted"] = without_max
    formulas["raw_rate_without_max_not_interpreted"] = formula_raw
    outcomes["raw_rate_without_max_not_interpreted"] = "freight_per_kg"
    interpreted["raw_rate_without_max_not_interpreted"] = 0

    coef_all = []
    metrics = []
    fitted = {}
    for name, data in samples.items():
        classical, robust = fit_ols(formulas[name], data)
        fitted[name] = (classical, robust)
        # Level n is counted on the rows that were fit, including the p95 cut.
        sample_counts = level_counts(data, meta)
        log_outcome = not name.startswith("raw_rate")
        coef_all.extend(
            coef_rows(classical, robust, name, len(data), sample_counts, log_outcome)
        )
        metrics.append(
            metric_row(
                name,
                classical,
                len(data),
                {
                    "outcome": outcomes[name],
                    "interpreted": interpreted[name],
                },
            )
        )

    full_classical, full_robust = fitted["full_log_rate"]
    country_classical, country_robust = fitted["full_log_rate_plus_country"]
    mode_classical, _mode_robust = fitted["mode_only"]

    # Beyond mode: log weight, the INCO dummies, and Orgenics, jointly.
    beyond_mode = wald_extra(full_robust, ("log_weight", "inco_grouped", "orgenics"))
    country_block = wald_extra(country_robust, ("country_grouped",))

    wald = pd.DataFrame(
        [
            {
                "comparison": "full versus mode-only",
                "question": "Do log weight, grouped INCO, and Orgenics add fit beyond mode?",
                "cov_type": COV_TYPE,
                "r_squared_restricted": float(mode_classical.rsquared),
                "r_squared_full": float(full_classical.rsquared),
                "delta_r_squared": float(full_classical.rsquared - mode_classical.rsquared),
                **beyond_mode,
            },
            {
                "comparison": "country check versus full",
                "question": "Does grouped country add fit beyond the headline model?",
                "cov_type": COV_TYPE,
                "r_squared_restricted": float(full_classical.rsquared),
                "r_squared_full": float(country_classical.rsquared),
                "delta_r_squared": float(country_classical.rsquared - full_classical.rsquared),
                **country_block,
            },
        ]
    )

    coef_df = pd.DataFrame(coef_all)
    # Sensitivity is the full log model against the same formula under p95.
    base = coef_df.loc[coef_df["model"] == "full_log_rate"].set_index("term")
    trimmed = coef_df.loc[coef_df["model"] == "full_log_rate_at_or_below_p95"].set_index("term")
    if list(base.index) != list(trimmed.index):
        raise SystemExit("p95 model does not have the same coefficients as the full model")
    sensitivity = pd.DataFrame(
        {
            "term": base.index,
            "factor": base["factor"].to_numpy(),
            "level": base["level"].to_numpy(),
            "n_full": base["n"].to_numpy(),
            "n_at_or_below_p95": trimmed["n"].to_numpy(),
            "p95_freight_per_kg_weighed_set": meta["p95_freight_per_kg"],
            "coefficient_full": base["coefficient"].to_numpy(),
            "ci_low_hc1_full": base["ci_low_hc1"].to_numpy(),
            "ci_high_hc1_full": base["ci_high_hc1"].to_numpy(),
            "coefficient_at_or_below_p95": trimmed["coefficient"].to_numpy(),
            "ci_low_hc1_at_or_below_p95": trimmed["ci_low_hc1"].to_numpy(),
            "ci_high_hc1_at_or_below_p95": trimmed["ci_high_hc1"].to_numpy(),
            "coefficient_change": (
                trimmed["coefficient"].to_numpy() - base["coefficient"].to_numpy()
            ),
            "interval_contains_zero_full": base["interval_contains_zero"].to_numpy(),
            "interval_contains_zero_p95": trimmed["interval_contains_zero"].to_numpy(),
        }
    )

    delivered = dates.loc[dates["column_name"] == "Delivered to Client Date"].iloc[0]
    references = pd.DataFrame(
        [
            {
                "model": "full_log_rate",
                "factor": "mode",
                "reference_level": meta["mode_reference"],
                "rule": "most common shipment mode among model rows (weighed, named mode)",
                "n_at_reference": int((model["mode"] == meta["mode_reference"]).sum()),
            },
            {
                "model": "full_log_rate",
                "factor": "inco_grouped",
                "reference_level": meta["inco_reference"],
                "rule": (
                    f"most common grouped INCO term among model rows; "
                    f"terms with fewer than {MIN_LEVEL_N} model rows are Other"
                ),
                "n_at_reference": int((model["inco_grouped"] == meta["inco_reference"]).sum()),
            },
            {
                "model": "full_log_rate",
                "factor": "orgenics",
                "reference_level": "0 (not Orgenics)",
                "rule": f"indicator for vendor {meta['orgenics_name']} versus every other vendor",
                "n_at_reference": int((model["orgenics"] == 0).sum()),
            },
            {
                "model": "full_log_rate_plus_country",
                "factor": "country_grouped",
                "reference_level": meta["country_reference"],
                "rule": (
                    f"not in the headline model; most common country with at least "
                    f"{MIN_LEVEL_N} model rows; smaller countries are Other"
                ),
                "n_at_reference": int((model["country_grouped"] == meta["country_reference"]).sum()),
            },
        ]
    )

    sample_rows = [
        ("rule", "yes_line"),
        ("outcome", "freight_per_kg"),
        ("outcome_population", "weighed set: Yes-line freight is a plain decimal and Yes-line weight is a plain decimal > 0"),
        ("weighed_n", meta["weighed_n"]),
        ("blank_mode_decision", "dropped from the model; blank is not a mode and is not imputed"),
        ("blank_weighed_n_dropped", meta["blank_weighed_n"]),
        ("model_n", meta["model_n"]),
        ("model_definition", "weighed set minus blank shipment mode"),
        ("holdout_split", "none; this is an explanation of the observed shipments, not a predictor"),
        ("manufacturing_site", "out; mixed on 880 notes in Analyze and not copied by the rollup"),
        ("insurance", "out; not read"),
        ("raw_freight_as_regressor", "out"),
        ("p95_population", "weighed set, including blank mode"),
        ("p95_freight_per_kg", meta["p95_freight_per_kg"]),
        ("model_n_above_p95", meta["model_above_p95"]),
        ("model_n_at_or_below_p95", meta["model_at_or_below_p95"]),
        ("blank_weighed_n_above_p95", meta["blank_above_p95"]),
        ("weighed_median_freight_per_kg", meta["weighed_median_rate"]),
        ("weighed_mean_freight_per_kg", meta["weighed_mean_rate"]),
        ("weighed_max_freight_per_kg", meta["weighed_max_rate"]),
        ("model_median_freight_per_kg", meta["model_median_rate"]),
        ("model_mean_freight_per_kg", meta["model_mean_rate"]),
        ("model_max_freight_per_kg", meta["model_max_rate"]),
        ("max_rate_asn", meta["max_rate_asn"]),
        ("max_rate_mode", meta["max_rate_mode"]),
        ("max_rate_vendor", meta["max_rate_vendor"]),
        ("max_rate_weight_kg", meta["max_rate_weight_kg"]),
        ("max_rate_freight_usd", meta["max_rate_freight_usd"]),
        ("orgenics_vendor", meta["orgenics_name"]),
        ("orgenics_n_model", int(model["orgenics"].sum())),
        ("mode_reference", meta["mode_reference"]),
        ("inco_reference", meta["inco_reference"]),
        ("country_reference_check_only", meta["country_reference"]),
        ("min_level_n", MIN_LEVEL_N),
        ("delivered_to_client_min", delivered["min_date"]),
        ("delivered_to_client_max", delivered["max_date"]),
        ("zero_weight_asn_excluded", ZERO_WEIGHT_ASN),
        ("included_in_price_excluded", EXPECTED_INCLUDED),
        ("invoiced_separately_excluded", EXPECTED_INVOICED),
        ("weight_not_numeric_excluded", EXPECTED_WEIGHT_NOT_NUMERIC),
    ]
    sample = pd.DataFrame(
        [{"item": key, "value": value} for key, value in sample_rows]
    )

    run = pd.DataFrame(
        [
            {
                "statsmodels": statsmodels.__version__,
                "pandas": pd.__version__,
                "numpy": np.__version__,
                "cov_type": COV_TYPE,
                "estimator": "OLS",
                "wls": "not used; log outcome instead of weighting by kilograms",
                "headline_formula": formula_full,
                "mode_only_formula": formula_mode,
                "country_check_formula": formula_country,
            }
        ]
    )

    save_csv(pd.DataFrame(metrics), "construct_metrics.csv")
    save_csv(coef_df, "construct_coefficients.csv")
    save_csv(references, "construct_reference_levels.csv")
    save_csv(sensitivity, "construct_sensitivity.csv")
    save_csv(sample, "construct_sample.csv")
    save_csv(grouping, "construct_grouping.csv")
    save_csv(wald, "construct_wald.csv")
    save_csv(orgenics_mix(model, meta["orgenics_name"]), "construct_orgenics_by_mode.csv")
    # Weight by mode is why a low unconditional rate can flip once log(weight)
    # is on the right-hand side. INCO by mode is why ocean can then lose
    # the gap that weight alone did not remove. Neither table is a model.
    descriptives = []
    for mode, sub in model.groupby("mode", dropna=False):
        descriptives.append(
            {
                "shipment_mode": mode,
                "n": int(len(sub)),
                "median_weight_kg": float(sub["weight_kg"].median()),
                "mean_weight_kg": float(sub["weight_kg"].mean()),
                "median_freight_per_kg": float(sub["freight_per_kg"].median()),
                "mean_freight_per_kg": float(sub["freight_per_kg"].mean()),
            }
        )
    save_csv(pd.DataFrame(descriptives), "construct_mode_weight.csv")
    inco_by_mode = (
        pd.crosstab(model["mode"], model["inco_grouped"])
        .reset_index()
        .rename(columns={"mode": "shipment_mode"})
    )
    save_csv(inco_by_mode, "construct_inco_by_mode.csv")
    save_csv(run, "construct_run.csv")
    mode_chart(coef_df, meta)
    dashboard = write_dashboard(shipments, model["asn_dn"])

    full_r2 = float(full_classical.rsquared)
    mode_r2 = float(mode_classical.rsquared)
    print(
        "confirmation "
        f"weighed_n={meta['weighed_n']} "
        f"blank_dropped={meta['blank_weighed_n']} "
        f"model_n={meta['model_n']} "
        f"reference_mode={meta['mode_reference']} "
        f"inco_reference={meta['inco_reference']} "
        f"orgenics_n={int(model['orgenics'].sum())} "
        f"p95={meta['p95_freight_per_kg']} "
        f"sensitivity_n={meta['model_at_or_below_p95']} "
        f"r2_mode_only={mode_r2} "
        f"r2_full={full_r2} "
        f"r2_country={float(country_classical.rsquared)} "
        f"dashboard={dashboard.name}"
    )
    print(f"processed_dir={PROC}")


if __name__ == "__main__":
    main()
