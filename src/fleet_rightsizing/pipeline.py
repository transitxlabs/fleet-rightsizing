"""End-to-end analysis pipeline."""

from __future__ import annotations

import base64
import platform
import resource
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from fleet_rightsizing.baseline import (
    compute_baseline,
    load_laval_fleet,
    load_nyc_measured,
    load_seattle_fleet,
)
from fleet_rightsizing.config import (
    ANALYSIS_YEAR,
    BOOTSTRAP_SEED,
    BOOTSTRAP_WIDTH_THRESHOLD,
    DEFAULT_FIGURES_DIR,
    DEFAULT_RESULTS_DIR,
    DIESEL_PRICE,
    GASOLINE_PRICE,
    MATCH_RATE_THRESHOLD,
    MEMORY_LIMIT_MB,
    SENSITIVITY,
)
from fleet_rightsizing.data_io import count_csv_rows, sha256_file
from fleet_rightsizing.emissions import ELIGIBLE_MATCH_PROVENANCES, RatingsIndex
from fleet_rightsizing.evaluation import StopRuleReport, evaluate
from fleet_rightsizing.federal_check import federal_fleet_factor_check
from fleet_rightsizing.figures import (
    plot_fictional_sensitivity,
    plot_ghg_by_department,
    plot_utilization_distribution,
)
from fleet_rightsizing.ingest import ensure_datasets
from fleet_rightsizing.report import render_report, write_results_json, write_results_markdown
from fleet_rightsizing.tco import hypothetical_cost_case, scenario_comparison
from fleet_rightsizing.utilization import (
    bootstrap_fleet_ghg,
    class_miles_per_vehicle,
    diagnostic_cohort,
    measured_underutilized,
    miles_to_km,
    proxy_annual_km,
    proxy_underutilized,
)


def peak_memory_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def _stage_memory_mb() -> float:
    return peak_memory_mb()


def run_pipeline(
    data_dir: Path | None = None,
    results_dir: Path | None = None,
    figures_dir: Path | None = None,
) -> dict[str, Any]:
    wall_start = time.perf_counter()
    timings: dict[str, float] = {}
    stage_memory: dict[str, float] = {}

    t0 = time.perf_counter()
    paths = ensure_datasets(data_dir)
    timings["download_s"] = time.perf_counter() - t0
    stage_memory["download_mb"] = _stage_memory_mb()

    t1 = time.perf_counter()
    ratings = RatingsIndex.from_files(paths["nrcan_ratings"], paths["nrcan_bev"])
    seattle = load_seattle_fleet(paths["seattle_fleet"])
    nyc = load_nyc_measured(paths["nyc_efficiency"])
    laval = load_laval_fleet(paths["laval_fleet"])
    federal_check = federal_fleet_factor_check(paths["federal_fleet_fuel"])
    timings["load_s"] = time.perf_counter() - t1
    stage_memory["load_mb"] = _stage_memory_mb()

    t2 = time.perf_counter()
    nyc_scored = measured_underutilized(nyc)
    class_medians = class_miles_per_vehicle(nyc).apply(miles_to_km)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    proxy_km = proxy_annual_km(seattle, class_medians, rng)
    baseline_df, summary = compute_baseline(
        seattle,
        proxy_km,
        GASOLINE_PRICE,
        DIESEL_PRICE,
        ratings,
    )
    cohort = diagnostic_cohort(baseline_df)
    seattle_proxy = proxy_underutilized(cohort, proxy_km.loc[cohort.index])
    seattle_scored = baseline_df.merge(
        seattle_proxy[
            ["illustrative_underutilized", "toronto_rule", "mileage_mode", "threshold_km"]
        ],
        left_index=True,
        right_index=True,
        how="left",
    )
    for flag in ("illustrative_underutilized", "toronto_rule"):
        seattle_scored[flag] = seattle_scored[flag].eq(True)
    seattle_scored["mileage_mode"] = "simulated_proxy"
    seattle_scored["annual_km"] = proxy_km.values
    timings["baseline_s"] = time.perf_counter() - t2
    stage_memory["baseline_mb"] = _stage_memory_mb()

    stop_messages: list[str] = []
    match_rate_ok = summary.nrcan_eligible_match_rate >= MATCH_RATE_THRESHOLD
    if not match_rate_ok:
        stop_messages.append(
            "Stop rule: eligible NRCan match rate "
            f"{summary.nrcan_eligible_match_rate:.2%} below {MATCH_RATE_THRESHOLD:.0%}"
        )

    t3 = time.perf_counter()
    supported_ghg = seattle_scored.loc[seattle_scored["estimate_supported"], "annual_co2_kg"]
    ghg_point, ghg_low, ghg_high = bootstrap_fleet_ghg(supported_ghg.to_numpy())
    ci_width = (ghg_high - ghg_low) / ghg_point if ghg_point else 0.0
    bootstrap_width_ok = ci_width <= BOOTSTRAP_WIDTH_THRESHOLD
    if not bootstrap_width_ok:
        stop_messages.append(
            f"Stop rule: GHG bootstrap CI width ratio {ci_width:.2%} exceeds "
            f"{BOOTSTRAP_WIDTH_THRESHOLD:.0%}"
        )

    scenario = scenario_comparison(seattle_scored, ratings)

    def intensity_lookup(year: int, make: str, model: str, standard_type: str) -> float:
        return ratings.lookup(year, make, model, standard_type).co2_g_per_km

    stop_rules = StopRuleReport(
        memory_ok=True,
        match_rate_ok=match_rate_ok,
        bootstrap_width_ok=bootstrap_width_ok,
        messages=tuple(stop_messages),
    )
    eval_result = evaluate(
        seattle_scored,
        nyc,
        nyc_scored,
        scenario,
        ghg_point,
        ghg_low / 1000.0,
        ghg_high / 1000.0,
        stop_rules,
        intensity_lookup,
    )

    sensitivity_rows = []
    for name, span in SENSITIVITY.items():
        for label, value in (("low", span.low), ("high", span.high)):
            sensitivity_rows.append(
                {
                    "parameter": name,
                    "level": label,
                    "value": value,
                    **hypothetical_cost_case(**{name: value}),
                }
            )
    sensitivity = pd.DataFrame(sensitivity_rows)
    timings["evaluate_s"] = time.perf_counter() - t3
    stage_memory["evaluate_mb"] = _stage_memory_mb()

    out_results = results_dir or DEFAULT_RESULTS_DIR
    out_figures = figures_dir or DEFAULT_FIGURES_DIR
    out_results.mkdir(parents=True, exist_ok=True)
    out_figures.mkdir(parents=True, exist_ok=True)

    t4 = time.perf_counter()
    fig1 = plot_ghg_by_department(seattle_scored, out_figures / "ghg_by_department.png")
    fig2 = plot_utilization_distribution(seattle_scored, out_figures / "utilization_proxy.png")
    fig3 = plot_fictional_sensitivity(sensitivity, out_figures / "fictional_sensitivity.png")
    timings["figures_s"] = time.perf_counter() - t4
    stage_memory["figures_mb"] = _stage_memory_mb()

    memory_mb = peak_memory_mb()
    memory_ok = memory_mb <= MEMORY_LIMIT_MB
    if not memory_ok:
        stop_messages.append(
            f"Stop rule: peak memory {memory_mb:.0f} MB exceeds {MEMORY_LIMIT_MB} MB"
        )
    stop_rules = StopRuleReport(
        memory_ok=memory_ok,
        match_rate_ok=match_rate_ok,
        bootstrap_width_ok=bootstrap_width_ok,
        messages=tuple(stop_messages),
    )
    eval_result = eval_result.__class__(**{**asdict(eval_result), "stop_rules": stop_rules})

    wall_seconds = time.perf_counter() - wall_start
    timings["total_instrumented_s"] = sum(
        timings[k] for k in ("download_s", "load_s", "baseline_s", "evaluate_s", "figures_s")
    )
    timings["before_output_s"] = wall_seconds

    captions = [
        "Simulated light-duty annual tailpipe CO2 by factor provenance. Class proxies are "
        "separate from unresolved catalogue variants; excluded assets contribute no estimate.",
        "Seattle estimated cohort only (same records as descriptive flags, including trucks): "
        "invented annual kilometres from NYC unweighted group medians plus 15% Gaussian noise; "
        "class quartile flags do not establish surplus.",
        "Synthetic sensitivity illustration for two fictional equivalent base vehicles: "
        "one economic input varies at a time over six low/high ranges, with other inputs "
        "fixed. Circles mark low inputs; squares mark high inputs. No public asset IDs "
        "or municipal fleet savings are represented; values are in sensitivity.csv.",
    ]
    figure_refs = [
        {
            "name": caption,
            "path": "data:image/png;base64," + base64.b64encode(fig.read_bytes()).decode("ascii"),
        }
        for caption, fig in zip(captions, (fig1, fig2, fig3), strict=True)
    ]
    observed_at = datetime.now(UTC).isoformat()
    inputs = {
        key: {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "raw_rows": count_csv_rows(path),
            "observed_at_utc": observed_at,
        }
        for key, path in paths.items()
    }
    provenance_totals = (
        seattle_scored.groupby("match_provenance")
        .agg(records=("vehicle_id", "size"), co2_kg=("annual_co2_kg", "sum"))
        .to_dict(orient="index")
    )
    # Assumption envelope, not a probability interval: mileage ±30% (chosen),
    # times min/max observed factors among compatible catalogue variants/classes.
    estimated = seattle_scored[seattle_scored["estimate_supported"]]
    assumption_range = [
        float((estimated["annual_km"] * 0.7 * estimated["factor_co2_low_g_per_km"]).sum() / 1e6),
        float((estimated["annual_km"] * 1.3 * estimated["factor_co2_high_g_per_km"]).sum() / 1e6),
    ]
    ingestion = {
        "seattle_fleet": seattle.attrs["ingestion"],
        "laval_fleet": laval.attrs["ingestion"],
        "nyc_efficiency": nyc.attrs["ingestion"],
        **ratings.ingestion,
        "federal_fleet_fuel": federal_check.pop("ingestion"),
    }
    eligible = seattle_scored[
        seattle_scored["standard_type"].isin(["SEDAN", "SUV", "VAN", "TRUCK"])
        & seattle_scored["light_duty_scope"]
        & seattle_scored["emissions_supported"]
    ]
    matched = int(eligible["match_provenance"].isin(ELIGIBLE_MATCH_PROVENANCES).sum())
    coverage = {
        "matched_records": matched,
        "eligible_records": len(eligible),
        "estimated_records": len(estimated),
        "eligible_without_supported_factors": int((~eligible["estimate_supported"]).sum()),
        "definition": "Catalogue gate denominator is scope/fuel-eligible records before "
        "factor support; estimated cohort excludes eligible records lacking supported factors",
    }
    payload: dict[str, Any] = {
        "analysis_year": ANALYSIS_YEAR,
        "catalogue_coverage": coverage,
        "ingestion": ingestion,
        "baseline": asdict(summary),
        "inputs": inputs,
        "recommendations_status": "withheld",
        "scenario_value_status": "withheld placeholders; not evaluated fleet outcomes",
        "diagnostic_cohort": {
            "definition": "estimate_supported records; known weights and identified duty tokens "
            "screened; specialization remains unresolved",
            "records": len(cohort),
            "excluded_records": len(seattle_scored) - len(cohort),
            "standard_type_counts": cohort["standard_type"].value_counts().to_dict(),
            "quartile_scope": "within standard_type on this estimated cohort only",
            "chart_population": "same estimated cohort, including light-duty TRUCK",
        },
        "laval_role": "ingestion only; no replicated analysis or validation",
        "provenance_totals": provenance_totals,
        "hypothetical_cost_case": hypothetical_cost_case(),
        "uncertainty": {
            "kind": "conditional_row_bootstrap",
            "estimand": "sum of n iid draws from the empirical distribution of fixed simulated "
            "light-duty record emissions; not this finite fleet's real emissions",
            "assumption_range_tonnes": assumption_range,
            "range_scope": "Chosen mileage multipliers 0.7/1.3 times observed catalogue variant "
            "or class extrema; no coverage guarantee or NYC sampling uncertainty",
        },
        "evaluation": asdict(eval_result),
        "match_provenance": ratings.provenance_counts(seattle_scored),
        "federal_factor_check": federal_check,
        "timings_seconds": timings,
        "stage_memory_mb": stage_memory,
        "memory_scope": "process high-water RSS observed after each stage; not isolated usage",
        "peak_memory_mb": memory_mb,
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "laval_vehicle_count": len(laval),
        "laval_supported_count": int(laval["emissions_supported"].sum()),
        "nyc_group_count": len(nyc),
        "plan_top_ids": [],
        "reallocation_groups": [],
        "stop_rules_passed": all(
            (stop_rules.memory_ok, stop_rules.match_rate_ok, stop_rules.bootstrap_width_ok)
        ),
    }
    seattle_scored.to_csv(out_results / "seattle_scored.csv", index=False)
    (out_results / "replacement_plan.csv").unlink(missing_ok=True)
    if not scenario.empty:
        scenario.to_csv(out_results / "scenario_ledger.csv", index=False)
    sensitivity.to_csv(out_results / "sensitivity.csv", index=False)
    rejected = [
        {"source": name, **row}
        for name, item in ingestion.items()
        for row in item["rejected_records"]
    ]
    pd.DataFrame(rejected, columns=["source", "source_row", "reason", "field", "value"]).to_csv(
        out_results / "ingestion_rejections.csv",
        index=False,
    )

    render_report(
        out_results / "report.html",
        "Seattle Active Fleet Complement",
        summary,
        eval_result,
        figure_refs,
        payload,
    )
    # Time includes CSV, figures and HTML output. Final metadata serialization is
    # necessarily outside this measurement; never call it process end-to-end time.
    timings["through_output_s"] = time.perf_counter() - wall_start
    payload["peak_memory_mb"] = peak_memory_mb()
    write_results_json(out_results / "results.json", payload)
    project_root = (results_dir or DEFAULT_RESULTS_DIR).parent
    write_results_markdown(
        project_root / "RESULTS.md",
        payload,
        summary,
        eval_result,
    )
    docs_dir = project_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "results.md").write_bytes((project_root / "RESULTS.md").read_bytes())
    assets = docs_dir / "figures"
    assets.mkdir(exist_ok=True)
    for fig in (fig1, fig2, fig3):
        (assets / fig.name).write_bytes(fig.read_bytes())
    from importlib.resources import files

    attribution = files("fleet_rightsizing").joinpath("attribution.md").read_text()
    (out_results / "ATTRIBUTION.md").write_text(attribution, encoding="utf-8")
    readme = project_root / "README.md"
    if readme.exists():
        text = readme.read_text()
        start, end = "<!-- CASE_STUDY_START -->", "<!-- CASE_STUDY_END -->"
        if start in text and end in text:
            case = (
                f"Simulated light-duty cohort: {summary.supported_vehicle_count:,} of "
                f"{summary.vehicle_count:,} loaded Seattle records; "
                f"{summary.annual_co2_tonnes:,.1f} t tailpipe CO2 under proxy assumptions. "
                f"NRCan catalogue matches: {matched:,}/{len(eligible):,} "
                f"({summary.nrcan_eligible_match_rate:.1%}). "
                f"Stop rules passed: {payload['stop_rules_passed']}. "
                "Fleet savings and operational recommendations are withheld."
            )
            readme.write_text(
                text.split(start)[0] + start + "\n" + case + "\n" + end + text.split(end)[1],
                encoding="utf-8",
            )
    return payload
